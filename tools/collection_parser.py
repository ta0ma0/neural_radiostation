import os
import random
import sqlite3

from dotenv import load_dotenv
from mutagen.id3 import ID3, ID3TimeStamp
from mutagen.mp3 import MP3

# Загрузка переменных окружения из .env файла
load_dotenv()
music_dir = os.getenv("MUSIC_DIR")


# Тест на 100 случайных файлах для определения версий тегов
def test_tag_versions(music_dir, sample_size=100):
    mp3_files = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]
    sample_files = random.sample(mp3_files, min(sample_size, len(mp3_files)))
    tag_versions = set()
    for filename in sample_files:
        filepath = os.path.join(music_dir, filename)
        try:
            audio = MP3(filepath, ID3=ID3)
            if "TIT2" in audio.tags:
                tag_versions.add("ID3v2")
            elif "TIT1" in audio.tags:
                tag_versions.add("ID3v1")
        except Exception as e:
            print(f"Error reading {filename}: {e}")
    return tag_versions


# Создание базы данных и таблиц
def create_database():
    conn = sqlite3.connect("music_collection.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            artist_id INTEGER,
            album TEXT,
            year TEXT,
            genre TEXT,
            path TEXT NOT NULL,
            FOREIGN KEY (artist_id) REFERENCES artists (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS album_covers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER,
            cover_path TEXT,
            FOREIGN KEY (track_id) REFERENCES tracks (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            summary TEXT
        )
    """)
    conn.commit()
    conn.close()


# Получение ID артиста или создание нового
def get_or_create_artist_id(conn, artist_name):
    if not artist_name:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM artists WHERE name = ?", (artist_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO artists (name) VALUES (?)", (artist_name,))
        conn.commit()
        return cursor.lastrowid


# Парсинг метаданных и запись в базу данных
def parse_and_store_metadata(music_dir):
    conn = sqlite3.connect("music_collection.db")
    cursor = conn.cursor()
    for root, dirs, files in os.walk(music_dir):
        for file in files:
            if file.endswith(".mp3"):
                filepath = os.path.join(root, file)
                relative_path = os.path.relpath(filepath, music_dir)
                try:
                    audio = MP3(filepath, ID3=ID3)
                    tags = audio.tags

                    # Безопасное извлечение тегов
                    title = (
                        tags.get("TIT2", [None])[0]
                        if tags and "TIT2" in tags and tags.get("TIT2")
                        else None
                    )
                    artist = (
                        tags.get("TPE1", [None])[0]
                        if tags and "TPE1" in tags and tags.get("TPE1")
                        else None
                    )
                    album = (
                        tags.get("TALB", [None])[0]
                        if tags and "TALB" in tags and tags.get("TALB")
                        else None
                    )
                    year = (
                        tags.get("TDRC", [None])[0]
                        if tags and "TDRC" in tags and tags.get("TDRC")
                        else None
                    )
                    genre = (
                        tags.get("TCON", [None])[0]
                        if tags and "TCON" in tags and tags.get("TCON")
                        else None
                    )

                    # Преобразование временных меток в строки
                    if isinstance(year, ID3TimeStamp):
                        year = str(year)

                    # Пропускаем треки без артиста
                    if not artist:
                        continue

                    # Получаем или создаём ID артиста
                    artist_id = get_or_create_artist_id(conn, artist)

                    cursor.execute(
                        """
                        INSERT INTO tracks (title, artist_id, album, year, genre, path)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (title, artist_id, album, year, genre, relative_path),
                    )
                    track_id = cursor.lastrowid

                    # Обработка обложки альбома
                    if tags and "APIC" in tags:
                        cover_data = tags["APIC"].data
                        cover_path = os.path.join(root, f"{file}.cover")
                        with open(cover_path, "wb") as f:
                            f.write(cover_data)
                        cursor.execute(
                            """
                            INSERT INTO album_covers (track_id, cover_path)
                            VALUES (?, ?)
                        """,
                            (track_id, os.path.relpath(cover_path, music_dir)),
                        )
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    if not music_dir:
        print("MUSIC_DIR not found in .env file")
    else:
        create_database()
        tag_versions = test_tag_versions(music_dir)
        print(f"Detected tag versions: {tag_versions}")
        parse_and_store_metadata(music_dir)
