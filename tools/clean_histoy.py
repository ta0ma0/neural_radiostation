import sqlite3
import os
import sys

# --- Конфигурация ---
DB_NAME = "tools/xakep_ru.db"

def clear_history_table(db_path):
    """
    Удаляет все записи из таблицы 'history' в указанной базе данных SQLite.

    Args:
        db_path (str): Путь к файлу базы данных SQLite.

    Returns:
        bool: True, если операция прошла успешно, False в противном случае.
    """
    # Проверяем, существует ли файл базы данных
    if not os.path.exists(db_path):
        print(f"Ошибка: Файл базы данных '{db_path}' не найден.")
        return False

    print("-" * 50)
    print(f"Подготовка к удалению ВСЕХ записей из таблицы 'history'")
    print(f"в базе данных: {os.path.abspath(db_path)}")
    print("-" * 50)

    # Запрашиваем подтверждение у пользователя
    # Делаем проверку чуть строже, чтобы случайно не нажать Enter
    confirm = input("Вы АБСОЛЮТНО уверены? Это действие необратимо! Введите 'yes' для подтверждения: ")

    if confirm.lower().strip() != 'yes':
        print("Операция отменена пользователем.")
        return False

    try:
        # Подключаемся к базе данных
        # Используем 'with', чтобы гарантировать закрытие соединения
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            print("Выполнение команды DELETE FROM history...")
            # Выполняем SQL команду для удаления всех строк
            cursor.execute("DELETE FROM description;")

            # Получаем количество удаленных строк (может быть не всегда точно для DELETE без WHERE)
            rows_deleted = cursor.rowcount

            # Применяем изменения к базе данных
            conn.commit()

            print(f"Таблица 'history' успешно очищена.")
            # cursor.rowcount может вернуть -1, если количество не определено
            if rows_deleted != -1:
                 print(f"(Удалено записей: {rows_deleted})")

            # Опционально: Выполняем VACUUM для оптимизации файла БД после удаления
            # Это может занять время на больших базах данных
            print("Выполнение VACUUM для оптимизации файла базы данных...")
            conn.execute("VACUUM;")
            print("VACUUM завершен.")

            return True # Операция успешна

    except sqlite3.OperationalError as e:
        # Обработка случая, если таблицы 'history' не существует
        if "no such table: history" in str(e):
            print(f"Ошибка: Таблица 'history' не найдена в базе данных '{db_path}'. Нечего удалять.")
            return False # Не ошибка приложения, но операция не выполнена
        else:
            print(f"Ошибка SQLite при выполнении операции: {e}")
            return False
    except sqlite3.Error as e:
        # Обработка других ошибок SQLite
        print(f"Произошла ошибка SQLite: {e}")
        return False
    except Exception as e:
        # Обработка других непредвиденных ошибок
        print(f"Произошла непредвиденная ошибка: {e}")
        return False

# --- Запуск скрипта ---
if __name__ == "__main__":
    print("--- Скрипт очистки таблицы 'history' ---")
    success = clear_history_table(DB_NAME)

    if success:
        print("\nОперация завершена успешно.")
        sys.exit(0) # Выход с кодом 0 (успех)
    else:
        print("\nОперация НЕ была выполнена или завершилась с ошибкой.")
        sys.exit(1) # Выход с кодом 1 (ошибка)