import datetime  # Для работы с датами, хотя вставка делается через SQL DEFAULT
import os  # Для проверки существования файла (хотя connect сам создает)
import re  # Нужен для extract_descriptions_from_rss
import sqlite3
import xml.etree.ElementTree as ET  # Нужен для extract_descriptions_from_rss

import requests  # Нужен для fetch_rss_feed

# --- Функции из предыдущих шагов (fetch_rss_feed и extract_descriptions_from_rss) ---
# (Вставьте сюда код функций fetch_rss_feed и extract_descriptions_from_rss
#  из предыдущих ответов, или убедитесь, что они определены выше в вашем скрипте)


def fetch_rss_feed(url):
    """Загружает содержимое RSS-ленты по указанному URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)  # Увеличил таймаут
        response.raise_for_status()
        print(f"Успешно получены данные с {url}")
        return response.text
    except requests.exceptions.Timeout:
        print(f"Ошибка: Запрос к {url} превысил время ожидания (таймаут).")
        return None
    except requests.exceptions.HTTPError as http_err:
        print(f"Ошибка HTTP при запросе к {url}: {http_err}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Ошибка соединения при запросе к {url}: {conn_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Ошибка при выполнении запроса к {url}: {req_err}")
        return None
    except Exception as e:
        print(f"Непредвиденная ошибка при получении данных с {url}: {e}")
        return None


def extract_descriptions_from_rss(rss_input_string):
    """Извлекает описания из строки RSS."""
    descriptions = []
    actual_xml = ""
    if not isinstance(rss_input_string, str):  # Добавим проверку типа
        print("Ошибка парсинга: входные данные не являются строкой.")
        return []
    try:
        start_index = rss_input_string.find("<rss")
        if start_index == -1:
            start_index = rss_input_string.find("<?xml")
        if start_index != -1:
            actual_xml = rss_input_string[start_index:]
        else:
            print("Ошибка парсинга: Не удалось найти начало XML (<rss или <?xml).")
            return []

        actual_xml = actual_xml.strip()
        root = ET.fromstring(actual_xml)
        for item in root.findall(".//channel/item"):
            description_element = item.find("description")
            if description_element is not None and description_element.text is not None:
                descriptions.append(description_element.text.strip())
    except ET.ParseError as e:
        print(f"Ошибка парсинга XML: {e}")
        return []
    except Exception as e:
        print(f"Непредвиденная ошибка при парсинге: {e}")
        return []
    return descriptions


# --- Новая функция для сохранения в SQLite ---
def save_new_descriptions(descriptions_list, db_name="xakep_ru.db"):
    """
    Записывает новые описания новостей в базу данных SQLite.

    Проверяет наличие каждого описания в таблице 'description'
    и добавляет только те, которых там еще нет.

    Args:
        descriptions_list: Список строк с описаниями новостей.
        db_name (str): Имя файла базы данных SQLite. По умолчанию 'xakep_ru.db'.

    Returns:
        Количество успешно добавленных новых записей (int) или None в случае ошибки.
    """
    if not descriptions_list:
        print("Список описаний пуст, нечего записывать в БД.")
        return 0  # Нет новых записей

    added_count = 0
    conn = None  # Инициализируем соединение как None

    try:
        # 1 & 2: Подключаемся к БД. Файл будет создан, если не существует.
        # Проверка os.path.exists(db_name) не обязательна.
        print(f"SAVE: Пытаюсь подключиться к {os.path.abspath(db_name)}")
        conn = sqlite3.connect(
            db_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cursor = conn.cursor()
        print("Соединение установлено.")

        # 3. Создаем таблицу 'description', если она еще не существует.
        # Добавляем UNIQUE constraint к полю 'text', чтобы легко избегать дубликатов.
        # Добавляем поле 'added_date' с датой добавления по умолчанию.
        print("Проверка/создание таблицы 'description'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS description (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT UNIQUE NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                read INTEGER DEFAULT 0,
                read_date TIMESTAMP
            )
        """)
        # Опционально: можно создать индекс для ускорения поиска по тексту,
        # хотя UNIQUE constraint обычно сам создает индекс.
        # cursor.execute("CREATE INDEX IF NOT EXISTS idx_description_text ON description (text);")
        print("Таблица 'description' готова.")

        # 4 & 5: Обрабатываем каждое описание из списка
        print(f"Обработка {len(descriptions_list)} полученных описаний...")
        for desc_text in descriptions_list:
            if not isinstance(desc_text, str) or not desc_text.strip():
                print(f"Пропуск невалидной записи: {desc_text}")
                continue  # Пропускаем пустые или нестроковые описания

            # Используем INSERT OR IGNORE.
            # Эта команда пытается вставить запись. Если возникает конфликт
            # (в нашем случае - из-за UNIQUE constraint на поле 'text', т.е.
            # такое описание уже есть), команда просто игнорируется,
            # не вызывая ошибки. Это эффективный способ добавить только новые.
            cursor.execute(
                "INSERT OR IGNORE INTO description (text) VALUES (?)",
                (desc_text.strip(),),
            )

            # cursor.rowcount вернет 1, если строка была успешно вставлена,
            # и 0, если вставка была проигнорирована (т.е. запись уже была).
            if cursor.rowcount > 0:
                added_count += 1
                # print(f"Добавлено: {desc_text[:80]}...") # Для отладки

        # Фиксируем все изменения (INSERTы) в базе данных
        conn.commit()
        print(
            f"Обработка завершена. Успешно добавлено {added_count} новых записей в '{db_name}'."
        )
        return added_count

    except sqlite3.Error as e:
        print(f"Ошибка SQLite при работе с базой данных '{db_name}': {e}")
        # Можно добавить откат изменений при ошибке, если нужно
        # if conn:
        #    conn.rollback()
        return None  # Возвращаем None при ошибке
    except Exception as e:
        print(f"Непредвиденная ошибка при записи в БД '{db_name}': {e}")
        return None
    finally:
        # Шаг 6: Гарантированно закрываем соединение с БД, если оно было открыто
        if conn:
            conn.close()
            print("Соединение с базой данных закрыто.")


def main():
    # --- Пример полного цикла ---
    feed_url = "https://xakep.ru/feed"
    database_file = "tools/xakep_ru.db"

    print("--- Шаг 1: Получение RSS ленты ---")
    rss_content = fetch_rss_feed(feed_url)

    if rss_content:
        print("\n--- Шаг 2: Извлечение описаний ---")
        descriptions = extract_descriptions_from_rss(rss_content)

        if descriptions:
            print(f"Найдено {len(descriptions)} описаний.")
            # print("Первые несколько:", descriptions[:3]) # Для проверки

            print("\n--- Шаг 3: Сохранение новых описаний в БД ---")
            newly_added = save_new_descriptions(descriptions, database_file)

            if newly_added is not None:
                print(
                    f"\n--- Итог: Добавлено {newly_added} новых описаний в базу данных. ---"
                )
            else:
                print("\n--- Итог: Произошла ошибка при сохранении в базу данных. ---")
        else:
            print("\nНе удалось извлечь описания из RSS ленты.")
    else:
        print("\nНе удалось получить RSS ленту, дальнейшая обработка невозможна.")
    return newly_added


if __name__ == "__main__":
    main()
