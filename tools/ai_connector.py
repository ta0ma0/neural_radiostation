#!/usr/bin/env python3
"""
Скрипт для генерации речи радио-ведущего на основе информации об исполнителе из last.fm.
Использует локальную LLM (LM Studio).
"""

import os
import sys
from pathlib import Path

import requests

from tools.journal_prompt_generic import PROMPT_DJ2 as PROMPT

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Загрузка переменных окружения
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
ENV_PATH = os.path.join(ROOT_DIR, ".env")
load_dotenv(ENV_PATH)

# Конфигурация для локальной модели (LM Studio)
OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API", "lm-studio")
MODEL_NAME = os.getenv("LMSTUDIO_ROUTER_MODEL", "google/gemmi-2.5-pro")
LOCAL_API_URL = "http://127.0.0.1:1234/v1/chat/completions"
YOUR_SITE_URL = "http://localhost"
YOUR_APP_NAME = "DJ-Agent"

# Промпт для радио-ведущего
PROMPT_DJ = PROMPT


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

    # 2. Пишем в файл (для контейнера фронтэнд)
    with open(
        "/home/ruslan/Develop/Music/dj_alyx/django-aws-terminal-websocket/dj_alyx_radio.log",
        "a",
        encoding="utf-8",
    ) as f:
        f.write(f"{full_message}\n")

    # 3. Выводим в консоль с flush=True
    print(full_message, flush=True)


def get_llm_response_local(messages: list) -> dict:
    """
    Отправляет запрос на локальный сервер LM Studio.
    Возвращает ответ модели (словарь с полем 'content').
    """
    headers = {
        "Authorization": f"Bearer {OPEN_ROUTER_API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,
        "X-Title": YOUR_APP_NAME,
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.9,
    }
    try:
        response = requests.post(
            LOCAL_API_URL, headers=headers, json=payload, timeout=600
        )
        response.raise_for_status()
        data = response.json()
        if "choices" in data and data["choices"]:
            message = data["choices"][0]["message"]
            # Проверяем, что message — это словарь и в нём есть поле content
            if isinstance(message, dict) and "content" in message:
                message["content"] = message["content"].replace("*", "")
            return message
        else:
            return {"content": f"Ошибка: неожиданный формат ответа API: {data}"}
    except requests.exceptions.RequestException as e:
        return {"content": f"Сетевая ошибка: {e}"}
    except Exception as e:
        return {"content": f"Неизвестная ошибка: {e}"}


def generate_dj_speech(artist_info: str, track_name: str, artist_name: str) -> str:
    # 1. Проверка через requests (синхронно, так как это удобно внутри потока)
    try:
        response = requests.get("http://127.0.0.1:1234/v1/models", timeout=2)
        if response.status_code != 200:
            tty_log("[!] LM Studio не ответила 200. Переходим на заглушки.")
            return None  # Вернем None, чтобы caller использовал Fallback
    except Exception as e:
        tty_log(f"[!] Ошибка подключения к LM Studio: {e}")
        return None

    # 2. Формирование промпта
    system_message = PROMPT_DJ.format(track_name=track_name, artist_name=artist_name)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": artist_info},
    ]

    # 3. Вызов генерации
    response_data = get_llm_response_local(messages)

    # 4. Безопасный парсинг
    content = response_data.get("content", "")
    if "Сетевая ошибка" in content or "Ошибка" in content:
        return None

    return content


def main(summary):
    # Пример: получаем информацию об исполнителе из last.fm. Не используется в радиостанции, для теста.
    artist_info = """
    Artist: Daft Punk
    Bio: Daft Punk were a French electronic music duo formed in 1993 in Paris by Thomas Bangalter and Guy-Manuel de Homem-Christo. They achieved popularity in the late 1990s as part of the French house movement. They are known for their elaborate live shows, which featured the duo wearing ornate helmets and gloves.
    Genres: House, Electronic, Disco, Synth-pop
    Years Active: 1993–2021
    Popular Tracks: One More Time, Harder, Better, Faster, Stronger, Get Lucky
    """

    # Генерируем речь радио-ведущего
    dj_speech = generate_dj_speech(summary)
    tty_log(dj_speech)


if __name__ == "__main__":
    main()
