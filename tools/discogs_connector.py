#!/usr/bin/env python3
import os
import sqlite3
from pathlib import Path

import discogs_client
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DATA_BASE", "music_collection.db")
if DB_PATH and not os.path.isabs(DB_PATH):
    DB_PATH = str(PROJECT_DIR / DB_PATH)

load_dotenv(PROJECT_DIR / ".env")
TOKEN = os.getenv("DISCOGS_TOKEN", "")
USER_AGENT = "DJ_Alyx_Radio/1.0"

_discogs = None


def _get_client():
    global _discogs
    if _discogs is None:
        _discogs = discogs_client.Client(USER_AGENT, user_token=TOKEN if TOKEN else None)
    return _discogs


def search_artist_info(artist_name: str) -> dict | None:
    """Поиск артиста в Discogs. Результат кэшируется в artists.summary.

    Возвращает dict с ключом artist.bio.summary для совместимости с play_music.py.
    """
    if not artist_name:
        return None

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id, summary FROM artists WHERE name = ?", (artist_name,))
    row = c.fetchone()

    if row and row[1]:
        conn.close()
        return {"artist": {"bio": {"summary": row[1]}}}

    try:
        d = _get_client()
        results = d.search(artist_name, type="artist")
        if not results:
            conn.close()
            return None

        artist = results[0]
        profile = (artist.profile or "").strip()
        genres = ", ".join(getattr(artist, "genres", []) or [])
        summary = profile
        if genres:
            summary = f"[{genres}] {summary}" if summary else f"[{genres}]"

        if row:
            c.execute("UPDATE artists SET summary = ? WHERE id = ?", (summary, row[0]))
        else:
            c.execute("INSERT OR IGNORE INTO artists (name, summary) VALUES (?, ?)", (artist_name, summary))
        conn.commit()

        conn.close()
        return {"artist": {"bio": {"summary": summary}}}

    except Exception:
        conn.close()
        return None


if __name__ == "__main__":
    import sys
    name = " ".join(sys.argv[1:]) or "GusGus"
    result = search_artist_info(name)
    if result:
        print(f"Artist: {name}")
        print(f"Summary: {result['artist']['bio']['summary'][:300]}...")
    else:
        print(f"Not found: {name}")
