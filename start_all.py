#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
import time
import traceback

import requests

# --- НАСТРОЙКИ ---
ENV_NAME = "f5-tts"
PROJECT_DIR = os.path.expanduser("~/Develop/Music/dj_alyx")
GR_SCRIPT = os.path.join(PROJECT_DIR, "fm.py")
FIFO_PATH = "/tmp/grc_pipe"
RADIO_SCRIPT = os.path.join(PROJECT_DIR, "play_music.py")

REMOTE_URL = "https://djalyx.2077911.xyz"
REMOTE_CHECK_INTERVAL = 30

FM_ENABLED = "--fm" in sys.argv

CUSTOM_ENV = os.environ.copy()
CUSTOM_ENV.update(
    {
        "CC": "/usr/local/bin/gcc",
        "CXX": "/usr/local/bin/g++",
        "LD_LIBRARY_PATH": f"/usr/local/lib:{CUSTOM_ENV.get('LD_LIBRARY_PATH', '')}",
        "PATH": f"/usr/local/bin:{CUSTOM_ENV.get('PATH', '')}",
        "PYTHONUNBUFFERED": "1",
    }
)

processes = []
last_remote_ok = False


def cleanup(sig=None, frame=None):
    print("\n[!] Останавливаем все процессы...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)


def check_remote():
    global last_remote_ok
    try:
        r = requests.get(f"{REMOTE_URL}/health-check/", timeout=5)
        ok = r.status_code == 200
        if ok != last_remote_ok:
            status = "ONLINE" if ok else "OFFLINE"
            print(f"[REMOTE] Сервер {status}")
        last_remote_ok = ok
    except requests.RequestException as e:
        if last_remote_ok:
            print(f"[REMOTE] Сервер недоступен: {e}")
        last_remote_ok = False
    return last_remote_ok


def start_radio():
    cmd = [
        "conda", "run", "-n", ENV_NAME, "--no-capture-output",
        "python", "-u", RADIO_SCRIPT,
    ]
    if FM_ENABLED:
        cmd.append("--fm")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def start_fm():
    if not os.path.exists(FIFO_PATH):
        print(f"[FM] Создаю FIFO: {FIFO_PATH}")
        os.mkfifo(FIFO_PATH)
    return subprocess.Popen([sys.executable, "-u", GR_SCRIPT], env=CUSTOM_ENV)


def start_station():
    try:
        os.chdir(PROJECT_DIR)

        # 1. Запуск нейродиджея
        print(f"[1/2] Запуск Alyx Neural DJ (Conda: {ENV_NAME})...")
        radio_proc = start_radio()
        processes.append(radio_proc)

        time.sleep(1)

        # 2. Опционально: FM-трансмиттер
        gr_proc = None
        if FM_ENABLED:
            print("[2/2] Запуск GNU Radio (FM)...")
            gr_proc = start_fm()
            processes.append(gr_proc)
        else:
            print("[2/2] FM отключён (добавь --fm для включения)")
            gr_proc = None

        print("\n[READY] Радиостанция DJ ALYX вещает.")
        print(f"      Сайт: {REMOTE_URL}")
        print(f"      Стрим: {REMOTE_URL}/stream/djalyx")
        if FM_ENABLED:
            print("      FM: 95 MHz (HackRF)")
        print("Нажми Ctrl+C, чтобы выключить.\n")

        remote_timer = 0

        while True:
            # Мониторинг нейродиджея
            if radio_proc.poll() is not None:
                print(f"[CRITICAL] Alyx упал (Код: {radio_proc.returncode}). Рестарт...")
                radio_proc = start_radio()
                processes.append(radio_proc)

            # Мониторинг FM
            if FM_ENABLED and gr_proc and gr_proc.poll() is not None:
                print(f"[CRITICAL] GNU Radio упал (Код: {gr_proc.returncode}). Рестарт...")
                gr_proc = start_fm()
                processes.append(gr_proc)

            # Проверка удалённого сервера раз в REMOTE_CHECK_INTERVAL
            remote_timer += 2
            if remote_timer >= REMOTE_CHECK_INTERVAL:
                remote_timer = 0
                check_remote()

            time.sleep(2)

    except Exception:
        print(f"Ошибка оркестрации:\n{traceback.format_exc()}")
    finally:
        cleanup()


if __name__ == "__main__":
    start_station()
