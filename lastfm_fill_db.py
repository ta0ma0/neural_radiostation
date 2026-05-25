#!/usr/bin/env python3
import json
import os
import random
import sqlite3
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv


# --------------------------- Логирование ---------------------------
def tty_log(message, style="info"):
    colors = {
        "info": "\033[32m[SYSTEM]\033[0m",
        "on_air": "\033[36m[ON AIR]\033[0m",
        "ai": "\033[35m[⚙️ AI]\033[0m",
        "error": "\033[31m[ERROR]\033[0m",
        "time": f"\033[90m{datetime.now().strftime('%H:%M:%S')}\033[0m",
    }
    prefix = colors.get(style, colors["info"])

    full_message = f"{colors['time']} {prefix} {message}"

    # Лог-файл (путь можно изменить)
    log_path = "/home/ruslan/Develop/Music/dj_alyx/django-aws-terminal-websocket/dj_alyx_radio.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{full_message}\n")

    print(full_message, flush=True)


# --------------------------- Last.fm API ---------------------------
load_dotenv()
LAST_FM_KEY = os.getenv("LAST_FM_KEY")
if not LAST_FM_KEY:
    tty_log("LAST_FM_KEY не найден в .env файле", "error")
    sys.exit(1)

# Прокси и User-Agent
PROXY = {"http": "http://127.0.0.1:2080", "https": "http://127.0.0.1:2080"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
}


def search_artist(artist_name):
    """Поиск артиста, возвращает JSON ответа или None."""
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.search&artist={artist_name}&api_key={LAST_FM_KEY}&format=json"
    try:
        response = requests.get(url, proxies=PROXY, headers=HEADERS, timeout=15)
        tty_log(f"Поиск '{artist_name}' → статус {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            tty_log(
                f"Ошибка поиска {artist_name}: {response.status_code} {response.text}",
                "error",
            )
            return None
    except Exception as e:
        tty_log(f"Исключение при поиске {artist_name}: {e}", "error")
        return None


def get_artist_info(artist_name):
    """Получает подробную информацию об артисте (био, теги и т.д.)."""
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name}&api_key={LAST_FM_KEY}&format=json"
    try:
        response = requests.get(url, proxies=PROXY, headers=HEADERS, timeout=15)
        tty_log(f"Инфо '{artist_name}' → статус {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            tty_log(
                f"Ошибка получения инфо {artist_name}: {response.status_code} {response.text}",
                "error",
            )
            return None
    except Exception as e:
        tty_log(f"Исключение при получении инфо {artist_name}: {e}", "error")
        return None


def fetch_artist_summary(artist_name):
    """
    Возвращает строку summary (биографию) для артиста или None, если не найдено.
    """
    search_data = search_artist(artist_name)
    if not search_data:
        return None

    try:
        artists = search_data["results"]["artistmatches"]["artist"]
        if not artists:
            tty_log(f"Артист '{artist_name}' не найден в Last.fm", "error")
            return None

        first_artist = artists[0]
        correct_name = first_artist["name"]
        tty_log(f"Найден артист: {correct_name}")

        info = get_artist_info(correct_name)
        if not info:
            return None

        summary = info.get("artist", {}).get("bio", {}).get("summary", "").strip()
        if not summary:
            tty_log(f"У артиста '{correct_name}' нет summary", "error")
            return None

        # Last.fm часто добавляет в конец ссылку — можно оставить как есть
        return summary
    except (KeyError, IndexError, TypeError) as e:
        tty_log(f"Ошибка парсинга ответа для '{artist_name}': {e}", "error")
        return None


# --------------------------- Работа с БД ---------------------------
DB_PATH = "music_collection.db"  # путь к твоей БД


def init_db():
    """Проверяет наличие колонки summary в таблице artists и создаёт её при необходимости."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Проверим, есть ли колонка summary
    cursor.execute("PRAGMA table_info(artists)")
    columns = [col[1] for col in cursor.fetchall()]
    if "summary" not in columns:
        tty_log("Добавляем колонку summary в таблицу artists")
        cursor.execute("ALTER TABLE artists ADD COLUMN summary TEXT")
        conn.commit()
    conn.close()


def get_artists_without_summary():
    """Возвращает список кортежей (id, name) артистов, у которых summary NULL или пустая строка."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM artists WHERE summary IS NULL OR summary = '' ORDER BY id"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_artist_summary(artist_id, summary):
    """Сохраняет summary в БД для указанного artist_id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE artists SET summary = ? WHERE id = ?", (summary, artist_id))
    conn.commit()
    conn.close()
    tty_log(
        f"Обновлён artist id={artist_id}, summary сохранён (длина {len(summary)} симв.)",
        "info",
    )


# --------------------------- Основной цикл ---------------------------
def main():
    init_db()

    artists = get_artists_without_summary()
    if not artists:
        tty_log("Нет артистов без summary. Работа завершена.", "info")
        return

    tty_log(f"Найдено артистов для обработки: {len(artists)}", "info")

    for idx, (artist_id, name) in enumerate(artists, 1):
        tty_log(f"[{idx}/{len(artists)}] Обработка: {name} (id={artist_id})", "info")

        summary = fetch_artist_summary(name)
        if summary:
            update_artist_summary(artist_id, summary)
            tty_log(f"✅ Успешно получена биография для {name}", "info")
        else:
            tty_log(f"❌ Не удалось получить summary для {name}, пропускаем", "error")
            # Можно оставить поле NULL — при следующем запуске попробуем снова

        # Пауза перед следующим запросом (кроме последнего)
        if idx < len(artists):
            delay = random.uniform(2, 9)
            tty_log(f"Ожидание {delay:.1f} секунд...", "info")
            time.sleep(delay)

    tty_log("Все доступные артисты обработаны.", "info")


if __name__ == "__main__":
    # Если передан аргумент командной строки – обработать только одного артиста (для отладки)
    if len(sys.argv) > 1:
        single_artist = " ".join(sys.argv[1:])
        tty_log(f"Режим одного артиста: {single_artist}", "info")
        summary = fetch_artist_summary(single_artist)
        if summary:
            print("\n=== SUMMARY ===\n", summary)
        else:
            print("Не удалось получить summary.")
    else:
        main()
