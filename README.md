# neural_radiostation
Radiostation based on local music collection with LLM and tts DJ

#### Данный README не является руководcтвом по инсталляции. Это скорее пояснение к сборке.

## Описание проекта
Автономная радиостанция на базе локальной коллекции с LLM диджеем и синтезацией голоса (TTS) с помощью
F5-TTS.

## Логика работы
1. Перед запуском станции сканируй вручную локальную коллекция, создается БД music_collection.db tools/collection_parser.py (путь до коллекции надо указать вручную)
2. Текущая версия адаптирована под локальную LLM (LM Studio) tools/ai_connector.py (OpenAI совместимо можно использовать любой сервис)
3. Jingles data/jingles созданы в Suno (free tier хватило)
4. Frontend https://github.com/agusmakmun/django-aws-terminal-websocket.git но можно использовать аналоги, получает данные из django-aws-terminal-websocket/dj_alyx_radio.log, которые туда пишутся всеми рабочими процессами.
5. Генерация и клонирование голоса F5-TTS, здесь использовался форк F5-TTS_RUSSIA cli скрипт для генерации с клонированием tts_run.sh,в github проекта подробнее.
6. Промпты для LLM tools/journal_prompt_generic.py, легко изменить вещание на английский или любой другой язык, если модель позволяет.
7. Запуск всего pipeline play_music.py
8. Выход в интернет через icecast ссылка на поток встраивается в xterm.js фронтенда у меня django-aws-terminal-websocket
9. "Мелодии и ритмы ЭВМ" - атмосферный звуки ЭВМ из музея Яндекса.


![screenshot](./data/images/Screenshot_2026-03-12_03-45-20.png?raw=true "Frontend")
