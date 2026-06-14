# План: предотвращение множественных экземпляров и исчерпания памяти

## Что случилось
Множественные экземпляры `play_music.py` → каждый инициализирует `AlyxVoice` (модель TTS) и запускает генерацию речи → память 64GB исчерпана → система зависла.

## Изменения

### 1. start_all.py — PID-лок + зачистка + backoff + SIGTERM

Добавить ПЕРЕД `def acquire_lock()` и остальное:

```python
PID_FILE = "/tmp/dj_alyx_start_all.pid"
BACKOFF_BASE = 2
BACKOFF_MAX = 60
_restart_attempt = 0

def acquire_lock():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            print(f"[LOCK] start_all уже запущен (PID {old_pid}). Выход.")
            sys.exit(0)
        except (ValueError, ProcessLookupError, FileNotFoundError):
            pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def release_lock():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def kill_old_processes():
    procs = [
        "pkill -9 -f play_music.py 2>/dev/null",
        "pkill -9 ezstream 2>/dev/null",
        "pkill -9 -f 'ffmpeg.*s16le.*pipe' 2>/dev/null",
    ]
    for cmd in procs:
        os.system(cmd)
    time.sleep(1)
```

Изменить `cleanup()` — добавить `release_lock()` и `kill_old_processes()`:

```python
def cleanup(sig=None, frame=None):
    print("\n[!] Останавливаем все процессы...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
    kill_old_processes()
    release_lock()
    sys.exit(0)
```

Добавить SIGTERM-обработчик (после SIGINT):

```python
signal.signal(signal.SIGTERM, cleanup)
```

Добавить `backoff_delay()`:

```python
def backoff_delay():
    global _restart_attempt
    delay = min(BACKOFF_BASE ** _restart_attempt, BACKOFF_MAX)
    _restart_attempt += 1
    return delay
```

В `start_station()` — добавить `kill_old_processes()` перед запуском, и backoff при рестарте:

```python
def start_station():
    try:
        os.chdir(PROJECT_DIR)
        kill_old_processes()  # <-- НОВОЕ

        print(f"[1/2] Запуск Alyx Neural DJ (Conda: {ENV_NAME})...")
        radio_proc = start_radio()
        # ... остальное без изменений ...

        while True:
            if radio_proc.poll() is not None:
                # ... проверка лимита ...
                delay = backoff_delay()  # <-- НОВОЕ
                print(f"[CRITICAL] Alyx упал... Рестарт через {delay}с...")
                time.sleep(delay)
                radio_proc = start_radio()
            else:
                _restart_attempt = max(0, _restart_attempt - 1)  # <-- НОВОЕ: сброс при стабильной работе
            # ...
```

В `__main__`:

```python
if __name__ == "__main__":
    acquire_lock()
    start_station()
```

### 2. play_music.py — Ленивая инициализация AlyxVoice

**Убрать глобальную инициализацию** (строки 79-84):

```python
# УДАЛИТЬ ЭТО:
# alyx = AlyxVoice(
#     model_path="...",
#     ref_audio="...",
#     ref_text="...",
#     device="cpu",
# )
```

**Добавить ленивую инициализацию в CyberRadio.__init__**:

В `__init__` добавить:
```python
self._tts_model = None
self._tts_initialized = False
```

Добавить метод:
```python
def _get_tts(self):
    if not self._tts_initialized:
        try:
            self._tts_model = AlyxVoice(
                model_path="/home/ruslan/Develop/Voice/f5-tts/f5-tts-model/F5-TTS_RUSSIA/f5-tts-model/F5TTS_Russian/F5TTS_v1_Base_v2/model_last.pt",
                ref_audio="F5-TTS/rachel.capell_audiobook_16_07_24_short.wav",
                ref_text="How could he get back his title as the smelliest, stinkiest skunk?",
                device="cpu",
            )
            self._tts_initialized = True
            tty_log("[*] [System]: Voice Engine инициализирован.")
        except Exception as e:
            tty_log(f"Ошибка инициализации голоса: {e}", "error")
            self._tts_model = None
    return self._tts_model
```

**Заменить все использования `alyx` на `self._get_tts()`**:

Найти все вызовы `alyx.generate(...)` и заменить на:
```python
tts = self._get_tts()
if tts is None:
    tty_log("TTS недоступен, пропускаю генерацию речи", "error")
    return
tts_result = tts.generate(...)
```

## Ожидаемый результат
- Только ОДИН экземпляр `start_all.py` может работать одновременно
- Старые зомби-процессы убиваются при каждом запуске
- При падениях — задержка между рестартами (2с, 4с, 8с, 16с... максимум 60с)
- AlyxVoice инициализируется ТОЛЬКО при первой необходимости, не при импорте
- SIGTERM корректно очищает процессы и PID-файл
