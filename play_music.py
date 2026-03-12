#!/usr/bin/env python3
import asyncio
import json
import os
import random
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

# Сторонние модули
from tools.ai_connector import generate_dj_speech
from tools.last_fm import main as search_artist_info
from tools.voice_engine import AlyxVoice

# Вместо buffering=0 используем line_buffering=True
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", encoding="utf-8", buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), "w", encoding="utf-8", buffering=1)
# Настройки путей
ARCHIVE_DIR = ".data/archives/"
os.makedirs(ARCHIVE_DIR, exist_ok=True)
TEMP_DIR = ".data/temp_speech/"
os.makedirs(TEMP_DIR, exist_ok=True)
LOG_FILE = "django-aws-terminal-websocket/dj_alyx_radio.log"  # Пишем лог для стрима на фронэнд https://github.com/agusmakmun/django-aws-terminal-websocket.git


def tty_log(message, style="info"):
    colors = {
        "info": "\033[32m[SYSTEM]\033[0m",
        "on_air": "\033[36m[ON AIR]\033[0m",
        "ai": "\033[35m[⚙️ AI]\033[0m",
        "error": "\033[31m[ERROR]\033[0m",
        "time": f"\033[90m{datetime.now().strftime('%H:%M:%S')}\033[0m",
    }
    prefix = colors.get(style, colors["info"])

    # 1. Формируем строку сообщения
    full_message = f"{colors['time']} {prefix} {message}"

    # 2. Пишем в файл (для контейнера фронтэнда)
    with open(
        "/home/ruslan/Develop/Music/dj_alyx/django-aws-terminal-websocket/dj_alyx_radio.log",
        "a",
        encoding="utf-8",
    ) as f:
        f.write(f"{full_message}\n")

    # 3. Выводим в консоль с flush=True
    print(full_message, flush=True)


# Инициализация голоса
alyx = AlyxVoice(
    model_path="/home/ruslan/Develop/Voice/f5-tts/f5-tts-model/F5-TTS_RUSSIA/f5-tts-model/F5TTS_Russian/F5TTS_v1_Base_v2/model_last.pt",
    ref_audio="F5-TTS/rachel.capell_audiobook_16_07_24_short.wav",
    ref_text="How could he get back his title as the smelliest, stinkiest skunk?",
    device="cpu",
)

load_dotenv()
music_dir = os.getenv("MUSIC_DIR")
db_path = "music_collection.db"
JINGLES_DIR = "/home/ruslan/Develop/Music/dj_alyx/jingles/"


class CyberRadio:
    def __init__(self):
        self.is_running = True
        self.playlist = []  # Теперь тут строгая очередь (FIFO)

        self.speech_buffer = None
        self.is_generating = False

        # Master-процесс FFmpeg
        self.master_stream = None
        safe_pass = quote("ice1984Ocean", safe="")
        self.icecast_url = f"icecast://source:{safe_pass}@localhost:8000/djalyx"

    async def get_random_atmospherics(self):
        """Выбирает случайный звук из папки ЭВМ. Для атмосферы"""
        path = (
            "/home/ruslan/Develop/Music/dj_alyx/Мелодии и ритмы ЭВМ"  # Укажи свой путь
        )
        files = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.endswith(".mp3") or f.endswith(".wav")
        ]
        return random.choice(files)

    def get_random_track(self):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tracks.id, tracks.title, artists.name, tracks.path, tracks.artist_id, artists.summary
            FROM tracks
            LEFT JOIN artists ON tracks.artist_id = artists.id
        """)
        tracks = cursor.fetchall()
        conn.close()
        if not tracks:
            return None
        t = random.choice(tracks)
        return {
            "title": t[1],
            "artist": t[2],
            "path": t[3],
            "cached_bio": t[5],
        }

    async def start_master_stream(self):
        """Запускает непрерывный процесс вещания."""
        tty_log(f"[*] [System]: Подъем Master-узла вещания...")

        cmd = [
            "ffmpeg",
            "-re",
            "-f",
            "s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-i",
            "pipe:0",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            "-f",
            "mp3",
            self.icecast_url,
        ]

        self.master_stream = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Даем время на запуск
        await asyncio.sleep(2)

        # Проверяем, жив ли процесс
        if self.master_stream.returncode is not None:
            # Если он умер сразу, читаем ошибку
            _, err = await self.master_stream.communicate()
            tty_log(f"[❌] FFmpeg не запустился! Ошибка: {err.decode()}")
        else:
            tty_log("[✅] Master-узел вещает в http://localhost:8000/djalyx")

    async def play_single_file(self, file_path):
        """Декодирует один файл и льет его в Мастер-процесс."""
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path) or not self.master_stream:
            return

        tty_log(f"[ON AIR] {os.path.basename(abs_path)}")

        # Распаковываем аудио в сырой PCM звук
        cmd = [
            "ffmpeg",
            "-i",
            abs_path,
            "-f",
            "s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            "pipe:1",
        ]

        decoder = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )

        # Перекачиваем аудио-данные из декодера в мастер-процесс
        try:
            while True:
                chunk = await decoder.stdout.read(16384)  # Читаем по 16КБ
                if not chunk:
                    break  # Файл закончился

                self.master_stream.stdin.write(chunk)
                await (
                    self.master_stream.stdin.drain()
                )  # Ждем, пока Мастер проглотит кусок
        except Exception as e:
            tty_log(f"[!] Ошибка при передаче аудио: {e}")

        await decoder.wait()

        if decoder.returncode != 0:
            await asyncio.sleep(0.5)  # Защита от спама ошибками, если файл битый

    def split_text_to_chunks(self, text, max_chunk_size=150):
        if not isinstance(text, str):
            return []
        sentences = re.split(r"(?<=[.!?])\s+|(?<=,)\s+", text)
        chunks, current_chunk = [], ""
        for sentence in sentences:
            if len(sentence) > max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                for i in range(0, len(sentence), max_chunk_size):
                    chunks.append(sentence[i : i + max_chunk_size].strip())
            elif len(current_chunk) + len(sentence) + 1 <= max_chunk_size:
                current_chunk += (" " + sentence) if current_chunk else sentence
            else:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
        if current_chunk:
            chunks.append(current_chunk.strip())
        return [c for c in chunks if c]

    async def background_speech_generator(self, track):
        if self.is_generating:
            return
        self.is_generating = True
        artist_name = track["artist"]
        gen_id = random.randint(100, 999)

        try:
            loop = asyncio.get_event_loop()
            lastfm_data = await loop.run_in_executor(
                None, search_artist_info, artist_name
            )
            bio = (
                lastfm_data.get("artist", {}).get("bio", {}).get("summary")
                or track.get("cached_bio")
                or f"Исполнитель {artist_name}."
            )

            raw_response = await loop.run_in_executor(
                None, generate_dj_speech, bio, track["title"], artist_name
            )

            speech_text = ""
            if isinstance(raw_response, str):
                try:
                    speech_text = json.loads(raw_response).get("content", raw_response)
                except:
                    speech_text = raw_response
            elif isinstance(raw_response, dict):
                speech_text = raw_response.get("content", "")

            if not speech_text or len(speech_text) < 10:
                return

            chunks = self.split_text_to_chunks(speech_text)
            speech_files = []
            for i, chunk in enumerate(chunks):
                path = os.path.join(TEMP_DIR, f"gen_{gen_id}_{i}.mp3")
                if await loop.run_in_executor(None, alyx.generate, chunk, path):
                    speech_files.append({"path": path})

            if speech_files:
                self.speech_buffer = {"track": track, "speech_files": speech_files}
                tty_log(f"[⚙️ AI] Эфирный блок для {artist_name} подготовлен.")

        except Exception as e:
            tty_log(f"[‼️ AI ERROR]: {e}")
        finally:
            self.is_generating = False

    async def run_radio(self):
        # 1. Начальная очистка временных файлов
        for f in Path(TEMP_DIR).glob("*.mp3"):
            try:
                os.remove(f)
            except:
                pass

        tty_log("═" * 50)
        tty_log("    STATION DJ ALYX IS NOW ONLINE    ".center(50, "═"))
        tty_log("═" * 50 + "\n")

        await self.start_master_stream()

        self.min_tracks_before_dj = 3  # Регулирует сколько треков будет звучать до выступления диджея, в это время просихоит генерация.
        self.tracks_played_counter = 0

        while self.is_running:
            # Проверка: если мастер-стрим упал, пробуем поднять (защита от краша FFmpeg)
            if self.master_stream.returncode is not None:
                tty_log("[!] Master-стрим упал, перезапуск...", "error")
                await self.start_master_stream()

            # 2. Фоновая подготовка AI-контента
            if not self.is_generating and not self.speech_buffer:
                future_track = self.get_random_track()
                if future_track:
                    asyncio.create_task(self.background_speech_generator(future_track))

            # 3. Внедрение DJ-блока по расписанию
            if (
                self.speech_buffer
                and self.tracks_played_counter >= self.min_tracks_before_dj
            ):
                tty_log(f"\n--- [ DJ ALYX ENTERING THE CHANNEL ] ---")
                data = self.speech_buffer
                self.speech_buffer = None
                self.tracks_played_counter = 0

                self.playlist.clear()

                # Собираем блок (Джингл -> Речь -> Трек)
                track_path = os.path.join(music_dir, data["track"]["path"])
                self.playlist.insert(0, track_path)

                for chunk in reversed(data["speech_files"]):
                    self.playlist.insert(0, chunk["path"])

                jingles = [f for f in os.listdir(JINGLES_DIR) if f.endswith(".mp3")]
                if jingles:
                    self.playlist.insert(
                        0, os.path.join(JINGLES_DIR, random.choice(jingles))
                    )

                tty_log(f"[DJ BLOCK] Блок подготовлен: {data['track']['artist']}")

            # 4. Поддержание наполнения плейлиста
            if not self.playlist:
                if random.random() < 0.2:
                    atm_file = await self.get_random_atmospherics()
                    if atm_file:
                        self.playlist.append(atm_file)
                else:
                    track = self.get_random_track()
                    if track:
                        self.playlist.append(os.path.join(music_dir, track["path"]))

            # 5. Единственная точка воспроизведения
            if self.playlist:
                current_file = self.playlist.pop(0)

                # Логика определения типа контента
                is_music = music_dir in current_file
                # Проверяем, не является ли файл атмосферным или джинглом
                is_special = (
                    "Atmosphere" in current_file
                    or JINGLES_DIR in current_file
                    or TEMP_DIR in current_file
                )

                # Играем файл
                await self.play_single_file(current_file)

                # Считаем только музыку, которая не спец-сигнал
                if is_music and not is_special:
                    self.tracks_played_counter += 1
                    tty_log(
                        f"[*] Прогресс блока: {self.tracks_played_counter}/{self.min_tracks_before_dj}"
                    )

                # 6. Очистка временных файлов AI
                if TEMP_DIR in current_file and os.path.exists(current_file):
                    try:
                        os.remove(current_file)
                    except:
                        pass
            else:
                await asyncio.sleep(1)


if __name__ == "__main__":
    radio = CyberRadio()
    try:
        asyncio.run(radio.run_radio())
    except KeyboardInterrupt:
        if radio.master_stream:
            radio.master_stream.terminate()
        tty_log("\n[*] DJ ALYX: Сигнал потерян.")
