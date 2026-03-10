#!/usr/bin/env python3
import asyncio
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Сторонние модули
from ai_connector import generate_dj_speech
from last_fm import main as search_artist_info
from voice_engine import AlyxVoice

ARCHIVE_DIR = "./archives/"
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# Инициализация голоса (глобально)
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
TEMP_DIR = "./temp_speech/"

os.makedirs(TEMP_DIR, exist_ok=True)


class CyberRadio:
    def __init__(self):
        self.current_track = None
        self.is_running = True
        self.track_counter = 1
        self.announced_artists = set()
        self.tracks_since_last_speech = (
            5  # Начинаем с высокого значения для первого эфира
        )

        # Очередь и флаги
        self.speech_buffer = None
        self.is_generating = False

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
            "id": t[0],
            "title": t[1],
            "artist": t[2],
            "path": t[3],
            "artist_id": t[4],
            "cached_bio": t[5],
        }

    # async def play_audio(self, file_path):
    #     abs_path = os.path.abspath(file_path)
    #     print(f"[DEBUG] Плеер: {os.path.basename(abs_path)}")
    #     process = await asyncio.create_subprocess_exec(
    #         "mpg123",
    #         "-q",
    #         abs_path,
    #         stdout=asyncio.subprocess.DEVNULL,
    #         stderr=asyncio.subprocess.PIPE,
    #     )
    #     _, stderr = await process.communicate()
    #     if stderr:
    #         print(f"[!] [mpg123 error]: {stderr.decode()}")
    #     await process.wait()

    async def play_audio(self, file_path):
        abs_path = os.path.abspath(file_path)

        # Экранируем @ в пароле: ice1984@Ocean -> ice1984%40Ocean
        cmd = [
            "ffmpeg",
            "-re",
            "-i",
            abs_path,
            "-acodec",
            "libmp3lame",
            "-ab",
            "128k",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-content_type",
            "audio/mpeg",  # <--- ОБЯЗАТЕЛЬНО ДОБАВЬ ЭТО
            "-f",
            "mp3",
            f"icecast://source:ice1984Ocean@localhost:8000/djalyx",
        ]

        print(f"[DEBUG] Стриминг в Icecast: {abs_path}")

        # Убираем stdout=DEVNULL, чтобы видеть, если FFmpeg ругнется на логин/пароль
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if stderr:
            err_msg = stderr.decode()
            if "Authentication failed" in err_msg:
                print("[!] Ошибка: Icecast не принял пароль!")
            elif "Connection refused" in err_msg:
                print("[!] Ошибка: Icecast не запущен на порту 8000!")

    async def play_joined_audio(self, speech_files):
        if not speech_files:
            return
        full_output = os.path.join(TEMP_DIR, "full_speech.mp3")
        list_filename = os.path.join(TEMP_DIR, "concat_list.txt")

        with open(list_filename, "w") as f:
            for chunk in speech_files:
                f.write(f"file '{os.path.abspath(chunk['path'])}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_filename,
            "-c",
            "copy",
            "-avoid_negative_ts",  # Убираем ошибки dts
            "make_zero",
            full_output,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await process.wait()

        await self.play_audio(full_output)

        # Чистка
        if os.path.exists(list_filename):
            os.remove(list_filename)
        if os.path.exists(full_output):
            os.remove(full_output)
        for chunk in speech_files:
            if os.path.exists(chunk["path"]):
                os.remove(chunk["path"])

    # def play_jingle(self):
    #     try:
    #         jingles = [f for f in os.listdir(JINGLES_DIR) if f.endswith(".mp3")]
    #         if jingles:
    #             jingle_path = os.path.join(JINGLES_DIR, random.choice(jingles))
    #             print(f"[*] [Alyx]: Отбивка...")
    #             subprocess.run(["mpg123", "-q", jingle_path])
    #     except Exception as e:
    #         print(f"[!] [Jingle error]: {e}")

    async def play_jingle(self):
        try:
            jingles = [f for f in os.listdir(JINGLES_DIR) if f.endswith(".mp3")]
            if not jingles:
                return

            jingle_path = os.path.abspath(
                os.path.join(JINGLES_DIR, random.choice(jingles))
            )
            print(f"[*] [Alyx]: Запуск отбивки в эфир...")

            # Тот же URL с экранированным паролем
            icecast_url = "icecast://source:ice1984%40Ocean@localhost:8000/djalyx"

            cmd = [
                "ffmpeg",
                "-re",
                "-i",
                jingle_path,
                "-acodec",
                "libmp3lame",
                "-ab",
                "128k",
                "-ac",
                "2",
                "-ar",
                "44100",
                "-f",
                "mp3",
                icecast_url,
            ]

            # Запускаем стриминг отбивки
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.wait()

        except Exception as e:
            print(f"[!] [Jingle error]: {e}")

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
        """Фоновый воркер с жесткой защитой."""
        if self.is_generating:
            return

        self.is_generating = True
        artist_name = track["artist"]
        track_title = track["title"]
        # Уникальный ID для этой сессии генерации, чтобы чанки не путались
        gen_id = random.randint(100, 999)

        print(
            f"\n[⚙️  AI]: Начинаю подготовку эфира для {artist_name} (ID: {gen_id})..."
        )

        try:
            # 1. Сбор инфо
            loop = asyncio.get_event_loop()
            lastfm_data = await loop.run_in_executor(
                None, search_artist_info, artist_name
            )
            bio = (
                lastfm_data.get("artist", {}).get("bio", {}).get("summary")
                or track.get("cached_bio")
                or f"Исполнитель {artist_name}."
            )

            # 2. Генерация текста
            raw_response = await loop.run_in_executor(
                None, generate_dj_speech, bio, track_title, artist_name
            )

            speech_text = ""
            if isinstance(raw_response, str):
                try:
                    data = json.loads(raw_response)
                    speech_text = data.get("content", raw_response)
                except:
                    speech_text = raw_response
            elif isinstance(raw_response, dict):
                speech_text = raw_response.get("content", "")

            if not speech_text or len(speech_text) < 10:
                print(f"[⚠️  AI]: Текст слишком короткий или пустой. Отмена.")
                return

            # 3. Синтез
            chunks = self.split_text_to_chunks(speech_text)
            speech_files = []
            print(f"[⚙️  AI]: Текст готов ({len(chunks)} чанков). Рендерим голос...")

            for i, chunk in enumerate(chunks):
                # Используем gen_id в имени файла
                chunk_path = os.path.join(TEMP_DIR, f"gen_{gen_id}_{i}.mp3")
                result = await loop.run_in_executor(
                    None, alyx.generate, chunk, chunk_path
                )
                if result:
                    speech_files.append({"text": chunk, "path": chunk_path})
                print(f"   > Чанк {i + 1}/{len(chunks)} готов")

            if speech_files:
                # ВАЖНО: сохраняем в буфер тот самый объект track
                self.speech_buffer = {
                    "track": track,
                    "speech_text": speech_text,
                    "speech_files": speech_files,
                }
                print(
                    f"[✅ AI]: Подготовка для {artist_name} ЗАВЕРШЕНА. Жду очереди в эфир."
                )
            else:
                print(f"[❌ AI]: Не удалось создать аудиофайлы.")

        except Exception as e:
            print(f"[‼️ AI ERROR]: Ошибка в фоновом процессе: {e}")
        finally:
            self.is_generating = False

    async def run_radio(self):
        # Чистим темп при старте
        print("[*] [System]: Чистка временных файлов...")
        for f in Path(TEMP_DIR).glob("*.mp3"):
            os.remove(f)

        print("\n" + "═" * 50)
        print("    STATION DJ ALYX IS NOW ONLINE    ".center(50, "═"))
        print("═" * 50 + "\n")

        self.play_jingle()

        while self.is_running:
            # Решаем: выходим в эфир или просто музыка
            if self.tracks_since_last_speech >= 4 and self.speech_buffer is not None:
                data = self.speech_buffer
                self.speech_buffer = None  # Сразу ОСВОБОЖДАЕМ буфер
                track = data["track"]  # Берем трек из буфера!
                speech_files = data["speech_files"]

                self.play_jingle()
                print("\n" + "⚡ " * 25)
                print(
                    f"[DJ ALYX ON AIR]: {track['artist']} - {track['title']}".center(50)
                )
                await self.play_joined_audio(speech_files)
                print("⚡ " * 25 + "\n")

                self.announced_artists.add(track["artist"])
                self.tracks_since_last_speech = 0
            else:
                track = self.get_random_track()
                print(
                    f"[*] [Radio]: Трек #{self.track_counter} | {track['artist']} - {track['title']} (До эфира: {4 - self.tracks_since_last_speech})"
                )
                self.tracks_since_last_speech += 1

            # Запускаем музыку (track теперь точно указывает либо на трек из буфера, либо на рандомный)
            music_file = os.path.join(music_dir, track["path"])
            music_task = asyncio.create_task(self.play_audio(music_file))

            # ТРИГГЕР: Начинаем готовить следующий эфир
            if not self.is_generating and self.speech_buffer is None:
                if self.track_counter == 1 or self.tracks_since_last_speech <= 1:
                    future_track = self.get_random_track()
                    if future_track:
                        asyncio.create_task(
                            self.background_speech_generator(future_track)
                        )

            self.track_counter += 1
            await music_task


if __name__ == "__main__":
    radio = CyberRadio()
    try:
        asyncio.run(radio.run_radio())
    except KeyboardInterrupt:
        print("\n[*] DJ ALYX: Сигнал потерян. Выключение...")
