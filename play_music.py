#!/usr/bin/env python3
import asyncio
import json
import os
import random
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

# Сторонние модули
from ai_connector import generate_dj_speech
from last_fm import main as search_artist_info
from voice_engine import AlyxVoice

# Настройки путей
ARCHIVE_DIR = "./archives/"
os.makedirs(ARCHIVE_DIR, exist_ok=True)
TEMP_DIR = "./temp_speech/"
os.makedirs(TEMP_DIR, exist_ok=True)

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
        self.current_track = None
        self.is_running = True
        self.track_counter = 1
        self.announced_artists = set()
        self.tracks_since_last_speech = 5

        # Очередь и флаги
        self.speech_buffer = None
        self.is_generating = False

        # Параметры вещания
        self.ezstream_proc = None

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

    async def start_stream(self):
        """Запускает ezstream для стриминга на Icecast."""
        if (
            hasattr(self, "ezstream_proc")
            and self.ezstream_proc is not None
            and self.ezstream_proc.returncode is None
        ):
            return

        print(f"[*] [System]: Инициализация вещательного узла через ezstream...")

        cmd = [
            "ezstream",
            "-c",
            "ezstream.xml",  # путь к конфигурационному файлу
        ]

        self.ezstream_proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        await asyncio.sleep(2)
        if self.ezstream_proc.returncode is not None:
            print("[❌] Критическая ошибка: ezstream не смог подключиться к Icecast.")
        else:
            print("[✅] Сигнал подан на http://localhost:8000/djalyx")

    async def play_audio(self, file_path):
        """Вливает аудиофайл в stdin ezstream."""
        if (
            not hasattr(self, "ezstream_proc")
            or self.ezstream_proc is None
            or self.ezstream_proc.returncode is not None
        ):
            await self.start_stream()

        abs_path = os.path.abspath(file_path)
        print(f"[ON AIR] {os.path.basename(abs_path)}")

        try:
            with open(abs_path, "rb") as f:
                while True:
                    chunk = f.read(16384)
                    if not chunk:
                        break
                    self.ezstream_proc.stdin.write(chunk)
                    await self.ezstream_proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            print("[!] Обрыв связи с ezstream. Перезапуск...")
            self.ezstream_proc = None

    async def play_jingle(self):
        jingles = [f for f in os.listdir(JINGLES_DIR) if f.endswith(".mp3")]
        if jingles:
            jingle_path = os.path.join(JINGLES_DIR, random.choice(jingles))
            await self.play_audio(jingle_path)

    async def play_dj_block(self, speech_files):
        """Сборка джингла и AI-речи в монолитный блок."""
        if not speech_files:
            return

        full_output = os.path.join(TEMP_DIR, "final_dj_block.mp3")
        list_filename = os.path.join(TEMP_DIR, "concat.txt")

        try:
            jingles = [f for f in os.listdir(JINGLES_DIR) if f.endswith(".mp3")]
            jingle_path = (
                os.path.abspath(os.path.join(JINGLES_DIR, random.choice(jingles)))
                if jingles
                else None
            )

            with open(list_filename, "w") as f:
                if jingle_path:
                    f.write(f"file '{jingle_path}'\n")
                for chunk in speech_files:
                    f.write(f"file '{os.path.abspath(chunk['path'])}'\n")

            # Склеиваем быстро без перекодирования
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "quiet",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_filename,
                    "-c",
                    "copy",
                    full_output,
                ]
            )

            await self.play_audio(full_output)

        finally:
            if os.path.exists(list_filename):
                os.remove(list_filename)
            if os.path.exists(full_output):
                os.remove(full_output)
            for chunk in speech_files:
                if os.path.exists(chunk["path"]):
                    os.remove(chunk["path"])

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
                    data = json.loads(raw_response)
                    speech_text = data.get("content", raw_response)
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
                print(f"[⚙️ AI] Эфирный блок для {artist_name} подготовлен.")

        except Exception as e:
            print(f"[‼️ AI ERROR]: {e}")
        finally:
            self.is_generating = False

    async def run_radio(self):
        # Стартовая чистка
        for f in Path(TEMP_DIR).glob("*.mp3"):
            try:
                os.remove(f)
            except:
                pass

        print("\n" + "═" * 50)
        print("    STATION DJ ALYX IS NOW ONLINE    ".center(50, "═"))
        print("═" * 50 + "\n")

        await self.start_stream()
        await self.play_jingle()

        while self.is_running:
            # 1. Либо вещаем блок с DJ, либо просто трек
            if self.tracks_since_last_speech >= 4 and self.speech_buffer:
                data = self.speech_buffer
                self.speech_buffer = None
                print(f"\n--- [ DJ ALYX ENTERING THE CHANNEL ] ---")
                await self.play_dj_block(data["speech_files"])
                self.tracks_since_last_speech = 0
                track = data["track"]  # Играем трек, про который только что говорили
            else:
                track = self.get_random_track()
                self.tracks_since_last_speech += 1

            # 2. Подготовка AI-контента на будущее
            if not self.is_generating and not self.speech_buffer:
                future_track = self.get_random_track()
                asyncio.create_task(self.background_speech_generator(future_track))

            # 3. Вещание текущего трека
            music_file = os.path.join(music_dir, track["path"])
            await self.play_audio(music_file)

            self.track_counter += 1


if __name__ == "__main__":
    radio = CyberRadio()
    try:
        asyncio.run(radio.run_radio())
    except KeyboardInterrupt:
        if hasattr(radio, "ezstream_proc"):
            radio.ezstream_proc.terminate()
        print("\n[*] DJ ALYX: Сигнал потерян.")
