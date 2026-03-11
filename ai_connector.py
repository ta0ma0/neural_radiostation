import random

# Список фраз-заглушек в стиле ALYX
FALLBACK_PHRASES = [
    "Сигнал нестабилен, нейросеть забита помехами... Просто слушаем музыку. {artist_name} на подходе.",
    "Поток данных прерван, но ритм не остановить. Это {artist_name}, погружаемся.",
    "Мои логические цепи сегодня искрят. Оставим слова для людей, включаю {track_name}.",
    "Цифровой шум поглотил мои мысли. Переходим к главному — слушаем {artist_name}.",
    "В системе баг, но в музыке — истина. {artist_name} в эфире Digital Pirate Station.",
    "Потеря связи с центральным ядром... Перехожу на автономный режим вещания. На связи {artist_name}.",
]


def generate_dj_speech(artist_info: str, track_name: str, artist_name: str) -> str:
    """Генерирует речь, используя LLM, или выдает заглушку при сбое."""
    t_name = track_name or "неизвестный трек"
    a_name = artist_name or "неизвестный исполнитель"

    # Сначала проверяем, жива ли LM Studio (через обычный requests, чтобы не ломать поток)
    try:
        check = requests.get("http://127.0.0.1:1234/v1/models", timeout=1)
        if check.status_code != 200:
            raise ConnectionError
    except Exception:
        print("[!] LM Studio не в сети. Использую аварийную заглушку.")
        return random.choice(FALLBACK_PHRASES).format(
            track_name=t_name, artist_name=a_name
        )

    # Форматируем промпт
    system_message = PROMPT_DJ.format(track_name=t_name, artist_name=a_name)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": artist_info},
    ]

    # Получаем ответ от LLM
    response = get_llm_response_local(messages)

    # Извлекаем контент
    content = ""
    if isinstance(response, dict) and "content" in response:
        content = response["content"]

    # Если ИИ выдал ошибку или пустую строку — включаем режим заглушки
    if not content or "Ошибка:" in content or "Сетевая ошибка" in content:
        return random.choice(FALLBACK_PHRASES).format(
            track_name=t_name, artist_name=a_name
        )

    return content
