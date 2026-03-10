#!/usr/bin/env python3
"""
Скрипт для генерации речи радио-ведущего на основе информации об исполнителе из last.fm.
Использует локальную LLM (LM Studio).
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

from journal_prompt_generic import PROMPT_DJ2 as PROMPT

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
    """Генерирует речь, зная, какой трек идет следом."""
    t_name = track_name or "неизвестный трек"
    a_name = artist_name or "неизвестный исполнитель"
    # Форматируем системный промпт, вставляя данные о треке
    system_message = PROMPT_DJ.format(track_name=t_name, artist_name=a_name)

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": artist_info},
    ]

    # Получаем ответ
    response = get_llm_response_local(messages)

    # Обрабатываем ответ
    try:
        # Если ответ — это строка, пытаемся разобрать её как JSON
        if isinstance(response, str):
            response_dict = json.loads(response)
            # Извлекаем текст из 'content'
            content = response_dict.get("content", "")
            return content
        elif isinstance(response, dict):
            # Если ответ уже словарь, извлекаем текст из 'content'
            if "content" in response:
                return response["content"]
            elif "message" in response and isinstance(response["message"], dict):
                return response["message"].get("content", "")
        return "Сбой: нет content"
    except Exception as e:
        print(f"[!] Ошибка парсинга JSON: {e}")
        return "Ошибка обработки ответа ИИ"


def main(summary):
    # Пример: получаем информацию об исполнителе из last.fm
    # (здесь должен быть твой код для получения данных об исполнителе)
    artist_info = """
    Artist: Daft Punk
    Bio: Daft Punk were a French electronic music duo formed in 1993 in Paris by Thomas Bangalter and Guy-Manuel de Homem-Christo. They achieved popularity in the late 1990s as part of the French house movement. They are known for their elaborate live shows, which featured the duo wearing ornate helmets and gloves.
    Genres: House, Electronic, Disco, Synth-pop
    Years Active: 1993–2021
    Popular Tracks: One More Time, Harder, Better, Faster, Stronger, Get Lucky
    """

    # Генерируем речь радио-ведущего
    dj_speech = generate_dj_speech(summary)
    print(dj_speech)


if __name__ == "__main__":
    main()
