import os
import sqlite3
import warnings

import librosa
import numpy as np
from dotenv import load_dotenv
from tqdm import tqdm

# Подавляем UserWarning от librosa (метаданные mp3)
warnings.filterwarnings("ignore", category=UserWarning)

# Загружаем переменные из .env файла в корне проекта
load_dotenv()

MUSIC_DIR = os.getenv("MUSIC_DIR")
DB_PATH = "music_collection.db"


def setup_database(cursor):
    """Проверяет наличие колонки bpm и создает её, если нужно."""
    try:
        cursor.execute("ALTER TABLE tracks ADD COLUMN bpm INTEGER")
        print("Колонка 'bpm' успешно добавлена в таблицу 'tracks'.")
    except sqlite3.OperationalError:
        pass


def calculate_bpm(file_path):
    """Вычисляет BPM трека с помощью librosa."""
    y, sr = librosa.load(file_path, sr=None)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

    if isinstance(tempo, (list, np.ndarray)):
        bpm_value = tempo[0]
    else:
        bpm_value = tempo

    return int(round(bpm_value))


def main():
    if not MUSIC_DIR:
        print("[ОШИБКА] Переменная MUSIC_DIR не найдена в .env файле.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    setup_database(cursor)

    # Выбираем только те треки, где bpm еще не просчитан
    cursor.execute("SELECT id, path FROM tracks WHERE bpm IS NULL")
    tracks = cursor.fetchall()

    if not tracks:
        print("Все треки в базе уже имеют проставленный BPM!")
        conn.close()
        return

    print(f"Базовая директория: {MUSIC_DIR}")
    print(f"К анализу подготовлено треков: {len(tracks)}")

    for track_id, rel_path in tqdm(tracks, desc="Анализ BPM"):
        # Убираем начальный слэш из пути БД, если он есть, чтобы os.path.join сработал корректно
        clean_rel_path = rel_path.lstrip("/")
        abs_path = os.path.join(MUSIC_DIR, clean_rel_path)

        if not os.path.exists(abs_path):
            tqdm.write(f"[ПРОПУСК] Файл не найден на диске: {abs_path}")
            continue

        try:
            bpm = calculate_bpm(abs_path)

            cursor.execute("UPDATE tracks SET bpm = ? WHERE id = ?", (bpm, track_id))
            conn.commit()

        except Exception as e:
            tqdm.write(f"[ОШИБКА] Не удалось обработать {abs_path}. Причина: {e}")

    conn.close()
    print("Индексация BPM успешно завершена.")


if __name__ == "__main__":
    main()
