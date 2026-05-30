#!/usr/bin/env python3
import asyncio
import json
import os
import random
import re
import signal
import sqlite3
import subprocess
import sys
import time
import datetime
from pathlib import Path
from urllib.parse import quote

signal.signal(signal.SIGPIPE, signal.SIG_IGN)

import requests as http_requests
from dotenv import load_dotenv

from num2words import num2words

# Сторонние модули
from ai_connector import generate_dj_speech
from last_fm import main as search_artist_info
from voice_engine import AlyxVoice

# Настройка буферизации для логов
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", encoding="utf-8", buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), "w", encoding="utf-8", buffering=1)

# Настройки путей
load_dotenv()
PROJECT_DIR = "/home/ruslan/Develop/Music/dj_alyx"
ARCHIVE_DIR = os.path.join(PROJECT_DIR, "archives")
TEMP_DIR = os.path.join(PROJECT_DIR, "temp_speech")
JINGLES_DIR = os.path.join(PROJECT_DIR, "jingles")
LOG_FILE = os.path.join(PROJECT_DIR, "django-aws-terminal-websocket/dj_alyx_radio.log")
REMOTE_LOG_URL = "https://djalyx.2077911.xyz/api/log/"

os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

MUSIC_DIR = os.getenv("MUSIC_DIR")
DB_PATH = os.getenv("DATA_BASE")
ICECAST_PASSWORD = os.getenv("ICECAST_SOURCE_PASSWORD", "change_me_in_env")


def tty_log(message, style="info"):
    colors = {
        "info": "\033[32m[SYSTEM]\033[0m",
        "on_air": "\033[36m[ON AIR]\033[0m",
        "ai": "\033[35m[⚙️ AI]\033[0m",
        "error": "\033[31m[ERROR]\033[0m",
        "time": f"\033[90m{datetime.datetime.now().strftime('%H:%M:%S')}\033[0m",
    }
    prefix = colors.get(style, colors["info"])
    full_message = f"{colors['time']} {prefix} {message}"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{full_message}\n")

    try:
        http_requests.post(REMOTE_LOG_URL, data=f"{full_message}\n".encode("utf-8"), timeout=2)
    except Exception:
        pass

    print(full_message, flush=True)


# Инициализация голоса
alyx = AlyxVoice(
    model_path="/home/ruslan/Develop/Voice/f5-tts/f5-tts-model/F5-TTS_RUSSIA/f5-tts-model/F5TTS_Russian/F5TTS_v1_Base_v2/model_last.pt",
    ref_audio="F5-TTS/rachel.capell_audiobook_16_07_24_short.wav",
    ref_text="How could he get back his title as the smelliest, stinkiest skunk?",
    device="cpu",
)


class CyberRadio:
    def __init__(self):
        self.is_running = True
        self.playlist = []
        self.speech_buffer = None
        self.news_buffer = None
        self.is_generating = False
        self.master_stream = None
        self.fm_enabled = False
        self._playing = False

        safe_pass = quote(ICECAST_PASSWORD, safe="")
        self.icecast_url = f"icecast://source:{safe_pass}@132.243.22.20:8000/djalyx"

    async def get_random_atmospherics(self):
        path = os.path.join(PROJECT_DIR, "Мелодии и ритмы ЭВМ")
        if not os.path.exists(path):
            return None
        files = [
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.endswith((".mp3", ".wav"))
        ]
        return random.choice(files) if files else None

    def get_random_track(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tracks.title, artists.name, tracks.path, artists.summary
                FROM tracks
                LEFT JOIN artists ON tracks.artist_id = artists.id
                ORDER BY RANDOM() LIMIT 1
            """)
            t = cursor.fetchone()
            conn.close()
            if t:
                return {"title": t[0], "artist": t[1], "path": t[2], "cached_bio": t[3]}
        except Exception as e:
            tty_log(f"Ошибка БД: {e}", "error")
        return None

    async def start_master_stream(self):
        """Запуск вещания (ffmpeg→ezstream pipeline, опционально FM)"""
        if self.master_stream is not None and self.master_stream.returncode is None:
            return
        tty_log("[*] [System]: Подъем Master-узла вещания...")

        if self.fm_enabled:
            cmd = [
                "ffmpeg", "-y", "-re", "-f", "s16le", "-ar", "44100", "-ac", "2",
                "-i", "pipe:0",
                "-filter_complex", "[0:a]asplit=2[ice][fm]",
                "-map", "[ice]", "-c:a", "libmp3lame", "-b:a", "64k",
                "-f", "mp3", self.icecast_url,
                "-map", "[fm]", "-f", "s16le", "-ar", "48000", "-ac", "1",
                "-flush_packets", "1", "/tmp/grc_pipe",
            ]
            self.master_stream = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            ez_template = os.path.join(PROJECT_DIR, "tools", "ezstream.xml.template")
            ez_config = os.path.join(PROJECT_DIR, "tools", "ezstream.xml")
            with open(ez_template, "r") as f:
                xml = f.read()
            xml = xml.replace("__HOSTNAME__", "132.243.22.20")
            xml = xml.replace("__PORT__", "8000")
            xml = xml.replace("__PASSWORD__", ICECAST_PASSWORD)
            with open(ez_config, "w") as f:
                f.write(xml)
            os.chmod(ez_config, 0o600)
            cmd = f"ffmpeg -y -f s16le -ar 44100 -ac 2 -i pipe:0 -f mp3 -b:a 64k - | ezstream -c {ez_config}"
            self.master_stream = await asyncio.create_subprocess_shell(
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )

        asyncio.create_task(self._monitor_master_stderr())
        await asyncio.sleep(2)

    async def _monitor_master_stderr(self):
        if not self.master_stream or not self.master_stream.stderr:
            return
        while True:
            try:
                line = await self.master_stream.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="ignore").strip()
                if any(p in text.lower() for p in ["error", "failed", "auth", "refused"]):
                    tty_log(f"[EZSTREAM] {text}", "error")
            except Exception:
                break

    async def play_single_file(self, track):
        if isinstance(track, str):
            track = {
                "path": track,
                "artist": "System",
                "title": os.path.basename(track),
            }

        abs_path = os.path.abspath(track.get("path"))
        if not os.path.exists(abs_path) or not self.master_stream:
            tty_log(f"Файл не найден: {abs_path}", "error")
            return

        tty_log(f"{track.get('artist')} — {track.get('title')}", "on_air")
        self._playing = True

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

        try:
            await self._stream_track(decoder)
        except Exception as e:
            tty_log(f"Ошибка трансляции трека: {repr(e)}", "error")
        finally:
            self._playing = False
            try:
                if decoder.returncode is None:
                    decoder.terminate()
                    try:
                        await asyncio.wait_for(decoder.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        decoder.kill()
                        await asyncio.wait_for(decoder.wait(), timeout=3)
                else:
                    await asyncio.wait_for(decoder.wait(), timeout=3)
            except Exception:
                pass

    async def _stream_track(self, decoder):
        while True:
            chunk = await asyncio.wait_for(decoder.stdout.read(16384), timeout=30)
            if not chunk:
                break
            self.master_stream.stdin.write(chunk)
            await asyncio.wait_for(self.master_stream.stdin.drain(), timeout=120)

    def split_text_to_chunks(self, text, max_chunk_size=150):
        if not text:
            return []
        sentences = re.split(r"(?<=[.!?])\s+|(?<=,)\s+", text)
        chunks, current = [], ""
        for s in sentences:
            if len(current) + len(s) < max_chunk_size:
                current += (" " + s) if current else s
            else:
                chunks.append(current.strip())
                current = s
        if current:
            chunks.append(current.strip())
        return chunks

    async def archive_speech(self, track, speech_files):
        artist = str(track.get("artist", "Unknown")).replace("/", "_")
        title = str(track.get("title", "Unknown")).replace("/", "_")
        ts = time.strftime("%Y%m%d-%H%M%S")
        out_path = os.path.join(ARCHIVE_DIR, f"{ts}_{artist}_{title}.mp3")
        list_path = os.path.join(TEMP_DIR, f"list_{ts}.txt")

        try:
            with open(list_path, "w") as f:
                for sf in speech_files:
                    f.write(f"file '{os.path.abspath(sf['path'])}'\n")

            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c",
                "copy",
                out_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode == 0:
                print(f"[💾 ARCHIVE] Сохранено: {os.path.basename(out_path)}")
        except Exception as e:
            print(f"Ошибка архивации: {e}")
        finally:
            if os.path.exists(list_path):
                os.remove(list_path)

    async def background_speech_generator(self, track):
        if self.is_generating:
            return
        self.is_generating = True
        try:
            loop = asyncio.get_event_loop()
            artist = track["artist"]

            try:
                lastfm = await loop.run_in_executor(None, search_artist_info, artist)
                bio = (
                    lastfm.get("artist", {}).get("bio", {}).get("summary")
                    if lastfm
                    else None
                )
            except Exception:
                bio = None

            bio = bio or track.get("cached_bio") or f"Artist: {artist}"

            raw_speech = await loop.run_in_executor(
                None, generate_dj_speech, bio, track["title"], artist
            )
            speech_text = raw_speech
            if isinstance(raw_speech, str) and raw_speech.startswith("{"):
                try:
                    speech_text = json.loads(raw_speech).get("content", raw_speech)
                except:
                    pass
            if not speech_text:
                tty_log("[⚙️ AI] LLM (LM Studio) недоступна на localhost:1234 — заглушка", "error")
                speech_text = f"Next track is {track['title']} by {artist}. Here we go!"

            chunks = self.split_text_to_chunks(speech_text)
            speech_files = []
            gen_id = random.randint(1000, 9999)

            for i, chunk in enumerate(chunks):
                p = os.path.join(TEMP_DIR, f"gen_{gen_id}_{i}.mp3")
                if await loop.run_in_executor(None, alyx.generate, chunk, p):
                    speech_files.append({"path": p})

            if speech_files:
                self.speech_buffer = {"track": track, "speech_files": speech_files}
                tty_log(f"Подготовлена подводка для {artist}", "ai")
                asyncio.create_task(self.archive_speech(track, speech_files))
            else:
                tty_log(f"[⚙️ AI] TTS не сгенерировал аудио для {artist} — проверь F5-TTS", "error")
        except Exception as e:
            tty_log(f"[⚙️ AI] Ошибка генерации: {repr(e)}", "error")
        finally:
            self.is_generating = False

    def _time_to_words(self, dt):
        weekdays = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
        months = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
        d = num2words(dt.day, lang='ru')
        m = months[dt.month - 1]
        h = num2words(dt.hour, lang='ru')
        mi = num2words(dt.minute, lang='ru')
        return f"{weekdays[dt.weekday()]}, {d} {m}, {h} часов {mi} минут по UTC"

    async def _news_speech_generator(self):
        db_path = os.path.join(PROJECT_DIR, "tools", "xakep_ru.db")
        while self.is_running:
            await asyncio.sleep(1)
            if self.news_buffer is not None:
                continue
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                today_start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
                c.execute("""
                    SELECT id, text FROM description
                    WHERE added_date >= ? AND (read IS NULL OR read = 0)
                    ORDER BY id DESC LIMIT 3
                """, (today_start,))
                rows = c.fetchall()
                if not rows:
                    conn.close()
                    await asyncio.sleep(300)
                    continue
                ids = [r[0] for r in rows]
                c.execute("UPDATE description SET read = 1, read_date = CURRENT_TIMESTAMP WHERE id IN ({})".format(",".join("?" * len(ids))), ids)
                conn.commit()
                conn.close()

                now = datetime.datetime.now(datetime.timezone.utc)
                intro = f"Сегодня {self._time_to_words(now)}. "
                news_texts = []
                for r in rows:
                    clean = re.sub(r'<[^>]+>', '', r[1]).strip()
                    if len(clean) > 500:
                        clean = clean[:500] + "..."
                    news_texts.append(clean)
                full_text = intro + " ".join(news_texts)

                loop = asyncio.get_event_loop()
                raw = await loop.run_in_executor(None, generate_dj_speech, full_text, "", "", "news")
                speech_text = raw
                if isinstance(raw, str) and raw.startswith("{"):
                    try:
                        speech_text = json.loads(raw).get("content", raw)
                    except Exception:
                        pass
                if not speech_text:
                    speech_text = f"Новости. {full_text} А теперь продолжим музыку."

                chunks = self.split_text_to_chunks(speech_text, max_chunk_size=250)
                speech_files = []
                gen_id = random.randint(1000, 9999)
                for i, chunk in enumerate(chunks):
                    p = os.path.join(TEMP_DIR, f"news_{gen_id}_{i}.mp3")
                    if await loop.run_in_executor(None, alyx.generate, chunk, p):
                        speech_files.append({"path": p})
                if speech_files:
                    self.news_buffer = {"speech_files": speech_files}
                    tty_log(f"Подготовлены новости ({len(rows)} шт)", "ai")
            except Exception as e:
                tty_log(f"[⚙️ AI] Ошибка генерации новостей: {repr(e)}", "error")
                await asyncio.sleep(60)

    async def run_radio(self):
        # 1. Очистка старья (пути приводим к абсолютному виду сразу)
        temp_base = os.path.abspath(TEMP_DIR)
        music_base = os.path.abspath(MUSIC_DIR)
        jingle_base = os.path.abspath(JINGLES_DIR)

        for f in Path(temp_base).glob("*.mp3"):
            try:
                os.remove(f)
            except:
                pass

        tty_log("═" * 50)
        tty_log(" STATION DJ ALYX IS ONLINE ".center(50, "═"))
        tty_log("═" * 50)

        await self.start_master_stream()

        asyncio.create_task(self._news_speech_generator())

        tracks_played = 0
        min_before_dj = 5

        while self.is_running:
            try:
                await asyncio.wait_for(
                    self._radio_cycle(tracks_played, min_before_dj, music_base, jingle_base, temp_base),
                    timeout=1800,
                )
                tracks_played = self.tp
            except asyncio.TimeoutError:
                tty_log("[WATCHDOG] Цикл радио завис — перезапуск", "error")
                if self.master_stream:
                    self.master_stream.terminate()
                    try:
                        await asyncio.wait_for(self.master_stream.wait(), timeout=3)
                    except Exception:
                        pass
                    self.master_stream = None
                await self.start_master_stream()
            except Exception as e:
                tty_log(f"[WATCHDOG] Ошибка цикла: {repr(e)}", "error")
                await asyncio.sleep(3)

    async def _radio_cycle(self, tracks_played, min_before_dj, music_base, jingle_base, temp_base):
        if self.master_stream is None or self.master_stream.returncode is not None:
            tty_log("Master-стрим упал, рестарт...", "error")
            await self.start_master_stream()
            await asyncio.sleep(2)

        if not self.is_generating and not self.speech_buffer:
            future = self.get_random_track()
            if future:
                asyncio.create_task(self.background_speech_generator(future))

        if not self.playlist:
            if self.speech_buffer and tracks_played >= min_before_dj:
                tty_log(
                    f"--- [ DJ ALYX НА ВЫЛЕТЕ: {tracks_played} трека пройдено ] ---",
                    "on_air",
                )
                data = self.speech_buffer
                self.speech_buffer = None
                tracks_played = 0

                if self.news_buffer:
                    for sf in self.news_buffer["speech_files"]:
                        self.playlist.append(
                            {"path": sf["path"], "artist": "DJ Alyx", "title": "News"}
                        )
                    self.news_buffer = None

                for sf in data["speech_files"]:
                    self.playlist.append(
                        {"path": sf["path"], "artist": "DJ Alyx", "title": "Speech"}
                    )

                t_info = data["track"]
                t_info["path"] = os.path.join(music_base, t_info["path"])
                self.playlist.append(t_info)
            else:
                t = self.get_random_track()
                if t:
                    t["path"] = os.path.join(music_base, t["path"])
                    self.playlist.append(t)

        if self.playlist:
            item = self.playlist.pop(0)
            current_path = os.path.normpath(os.path.abspath(item["path"]))
            await self.play_single_file(item)

            is_jingle = current_path.startswith(os.path.normpath(jingle_base))
            is_speech = current_path.startswith(os.path.normpath(temp_base))
            is_music = current_path.startswith(os.path.normpath(music_base))

            if is_music and not is_jingle and not is_speech:
                tracks_played += 1
                tty_log(f"📈 Счетчик: {tracks_played}/{min_before_dj}", "info")
            else:
                tty_log(f"⏸ Технический блок (не в счет)", "info")

            if is_speech:
                try:
                    os.remove(current_path)
                except:
                    pass
        else:
            await asyncio.sleep(1)

        self.tp = tracks_played


if __name__ == "__main__":
    radio = CyberRadio()
    radio.fm_enabled = "--fm" in sys.argv
    try:
        asyncio.run(radio.run_radio())
    except KeyboardInterrupt:
        if radio.master_stream:
            radio.master_stream.terminate()
        tty_log("Сигнал потерян.")
