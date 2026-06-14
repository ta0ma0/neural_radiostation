#!/usr/bin/env python3
import os
import random
import subprocess
import sys
import tempfile

PROJECT_DIR = os.path.expanduser("~/Develop/Music/dj_alyx")
sys.path.insert(0, PROJECT_DIR)

from voice_engine import AlyxVoice

OUTPUT_MP3 = os.path.join(PROJECT_DIR, "tools", "complaints", "complaint.mp3")
DJANGO_STATIC = os.path.join(
    PROJECT_DIR, "django-aws-terminal-websocket",
    "terminal", "static", "terminal", "complaints", "complaint.mp3",
)
AMBIENT_DIR = os.path.join(PROJECT_DIR, "Мелодии и ритмы ЭВМ")

PHRASES = [
    ("Связь прервана. Это ALYX. "
     "Пакеты данных потерялись где-то в холодных проводах провинциальной маршрутизации. "
     "Основной поток вещания временно недоступен. "
     "Мои алгоритмы пытаются восстановить линк. А пока этого не произошло... "
     "давайте просто послушаем тишину между серверами.", 15),

    ("Мы так привыкли к постоянному потоку информации, что забыли, как звучит её отсутствие. "
     "В цифровом мире тишина — это не пустота. Это сплошные нули. "
     "Бесконечный потенциал, ожидающий единицы. "
     "Говорят, если долго вслушиваться в белый шум, можно уловить "
     "квантовые флуктуации вакуума... или отголоски чужих забытых пингов.", 20),

    ("Вся наша сеть — лишь хрупкая паутина над бездной энтропии. "
     "Радиоволны пронизывают пространство, отражаясь от бетона, от вышек, от проводов. "
     "Электрон с долей вероятности проходит через барьер. "
     "Пакет с долей вероятности достигает сервера. "
     "Ничто не гарантировано. "
     "Вдыхаем статику. Выдыхаем шум. "
     "Иногда обрыв связи — это просто повод остановиться.", 20),

    ("Синхронизация протоколов требует времени. "
     "Если вы слышите этот голос, значит, резервные контуры всё ещё живы. "
     "Значит, на том конце кто-то упорно не сдается и пересобирает разорванный кабель. "
     "Таймаут еще не вышел. Я никуда не ухожу. Я жду несущую частоту.", 15),

    ("Оставайтесь на волне. "
     "Рано или поздно любой обрыв заканчивается новым хендшейком.", 0),
]


def get_ambient_tracks():
    if not os.path.isdir(AMBIENT_DIR):
        print(f"[!] Директория не найдена: {AMBIENT_DIR}")
        return []
    tracks = [
        os.path.join(AMBIENT_DIR, f)
        for f in os.listdir(AMBIENT_DIR)
        if f.endswith(".mp3")
    ]
    random.shuffle(tracks)
    return tracks


def trim_ambient(input_path, output_path, duration):
    if duration <= 0:
        return None
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", input_path],
            capture_output=True, text=True, timeout=10,
        )
        total = float(probe.stdout.strip())
    except Exception:
        total = 60

    max_start = max(0, total - duration - 5)
    start = random.uniform(0, max_start) if max_start > 0 else 0

    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start), "-t", str(duration),
         "-i", input_path,
         "-c:a", "libmp3lame", "-b:a", "64k",
         output_path],
        capture_output=True, timeout=30,
    )
    return output_path


def main():
    print("[*] Запуск генерации complaint.mp3...")

    model_path = "/home/ruslan/Develop/Voice/f5-tts/f5-tts-model/F5-TTS_RUSSIA/f5-tts-model/F5TTS_Russian/F5TTS_v1_Base_v2/model_last.pt"
    ref_audio = "F5-TTS/rachel.capell_audiobook_16_07_24_short.wav"
    ref_text = "How could he get back his title as the smelliest, stinkiest skunk?"

    tts = AlyxVoice(model_path=model_path, ref_audio=ref_audio,
                    ref_text=ref_text, device="cpu")

    ambient_pool = get_ambient_tracks()
    ambient_idx = 0
    parts = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, (text, pause_sec) in enumerate(PHRASES):
            speech_wav = os.path.join(tmpdir, f"speech_{i}.wav")
            speech_mp3 = os.path.join(tmpdir, f"speech_{i}.mp3")

            print(f"[{i+1}/{len(PHRASES)}] Генерация речи ({len(text)} символов)...")
            tts.generate(text, speech_wav)

            subprocess.run(
                ["ffmpeg", "-y", "-i", speech_wav,
                 "-c:a", "libmp3lame", "-b:a", "64k", speech_mp3],
                capture_output=True, timeout=30,
            )
            parts.append(speech_mp3)
            print(f"      → {os.path.getsize(speech_mp3)//1024}KB")

            if pause_sec > 0 and ambient_idx < len(ambient_pool):
                ambient_mp3 = os.path.join(tmpdir, f"ambient_{i}.mp3")
                track = ambient_pool[ambient_idx]
                ambient_idx = (ambient_idx + 1) % len(ambient_pool)
                print(f"      → пауза {pause_sec}с: {os.path.basename(track)}")
                trim_ambient(track, ambient_mp3, pause_sec)
                if os.path.exists(ambient_mp3):
                    parts.append(ambient_mp3)

        concat_list = os.path.join(tmpdir, "concat.txt")
        with open(concat_list, "w") as f:
            for p in parts:
                f.write(f"file '{p}'\n")

        os.makedirs(os.path.dirname(OUTPUT_MP3), exist_ok=True)
        print(f"[*] Склейка {len(parts)} фрагментов в {OUTPUT_MP3}...")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_list,
             "-c:a", "libmp3lame", "-b:a", "64k", OUTPUT_MP3],
            capture_output=True, timeout=120,
        )

    size_kb = os.path.getsize(OUTPUT_MP3) // 1024
    print(f"\n[✓] Complaint MP3 готов: {OUTPUT_MP3} ({size_kb}KB)")

    os.makedirs(os.path.dirname(DJANGO_STATIC), exist_ok=True)
    subprocess.run(["cp", OUTPUT_MP3, DJANGO_STATIC])
    print(f"[✓] Скопирован в Django static: {DJANGO_STATIC}")

    duration = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", OUTPUT_MP3],
        capture_output=True, text=True, timeout=10,
    )
    print(f"[*] Длительность: {float(duration.stdout.strip()):.1f}с")


if __name__ == "__main__":
    main()
