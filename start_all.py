#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
import time
import traceback

import requests

PID_FILE = "/tmp/dj_alyx_start_all.pid"
ENV_NAME = "f5-tts"
PROJECT_DIR = os.path.expanduser("~/Develop/Music/dj_alyx")
GR_SCRIPT = os.path.join(PROJECT_DIR, "fm.py")
FIFO_PATH = "/tmp/grc_pipe"
RADIO_SCRIPT = os.path.join(PROJECT_DIR, "play_music.py")

REMOTE_URL = "https://djalyx.2077911.xyz"
REMOTE_CHECK_INTERVAL = 30
MAX_RESTARTS = 5
RESTART_WINDOW = 3600
BACKOFF_BASE = 2
BACKOFF_MAX = 60

PROGRESSIVE_DELAYS = [300, 600, 600, 900, 900, 3600]
NET_STATUS_FILE = "/tmp/dj_alyx_network_status"

FM_ENABLED = "--fm" in sys.argv
FM_MAX_RESTARTS = 3
_restart_times = []
_fm_restart_times = []
_restart_attempt = 0
_progressive_attempt = 0

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
        "pkill -9 -f network_monitor.py 2>/dev/null",
    ]
    for cmd in procs:
        os.system(cmd)
    time.sleep(1)


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


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def backoff_delay():
    global _restart_attempt
    delay = min(BACKOFF_BASE**_restart_attempt, BACKOFF_MAX)
    _restart_attempt += 1
    return delay


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


def read_network_status():
    try:
        with open(NET_STATUS_FILE) as f:
            return f.read().strip()
    except (FileNotFoundError, OSError):
        return "OK"


def start_netmon():
    netmon_script = os.path.join(PROJECT_DIR, "tools", "network_monitor.py")
    return subprocess.Popen(
        [sys.executable, "-u", netmon_script],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )


def start_radio():
    cmd = [
        "/opt/miniconda3/condabin/conda", "run", "-n", ENV_NAME, "--no-capture-output",
        "python", "-u", RADIO_SCRIPT,
    ]
    if FM_ENABLED:
        cmd.append("--fm")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def check_gnuradio():
    try:
        subprocess.run(
            [sys.executable, "-c", "from gnuradio import gr, qtgui"],
            capture_output=True, timeout=5, env=CUSTOM_ENV,
        )
        return True
    except (subprocess.CalledProcessError, Exception):
        return False


def start_fm():
    if not os.path.exists(FIFO_PATH):
        print(f"[FM] Создаю FIFO: {FIFO_PATH}")
        os.mkfifo(FIFO_PATH)
    return subprocess.Popen([sys.executable, "-u", GR_SCRIPT], env=CUSTOM_ENV)


def start_station():
    try:
        os.chdir(PROJECT_DIR)

        kill_old_processes()

        global _restart_attempt, _progressive_attempt, FM_ENABLED

        # 0. Сетевой монитор
        print("[0/3] Запуск network monitor...")
        netmon_proc = start_netmon()
        processes.append(netmon_proc)

        # 1. Запуск нейродиджея
        print(f"[1/3] Запуск Alyx Neural DJ (Conda: {ENV_NAME})...")
        radio_proc = start_radio()
        processes.append(radio_proc)

        time.sleep(1)

        # 2. Опционально: FM-трансмиттер
        gr_proc = None
        if FM_ENABLED:
            if not check_gnuradio():
                print("[!] GNU Radio не найден. FM отключён.")
                FM_ENABLED = False
            else:
                print("[2/2] Запуск GNU Radio (FM)...")
                gr_proc = start_fm()
                processes.append(gr_proc)
        if not FM_ENABLED:
            print("[2/2] FM отключён (добавь --fm для включения)")

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
                now = time.time()
                _restart_times.append(now)
                _restart_times[:] = [
                    t for t in _restart_times if now - t < RESTART_WINDOW
                ]
                if len(_restart_times) > MAX_RESTARTS:
                    print(
                        f"[STOP] Превышен лимит ({MAX_RESTARTS}) перезапусков за час. Радио остановлено."
                    )
                    break

                net_status = read_network_status()
                if net_status == "LOST":
                    if _progressive_attempt >= len(PROGRESSIVE_DELAYS):
                        print("[NET] Все 6 попыток исчерпаны. Радио остановлено.")
                        with open("/tmp/dj_alyx_shutdown", "w") as f:
                            f.write("1\n")
                        break
                    delay = PROGRESSIVE_DELAYS[_progressive_attempt]
                    _progressive_attempt += 1
                    print(
                        f"[NET] Связь потеряна. Рестарт через {delay//60} мин "
                        f"(попытка {_progressive_attempt}/{len(PROGRESSIVE_DELAYS)})..."
                    )
                else:
                    delay = backoff_delay()
                    print(
                        f"[CRITICAL] Alyx упал (Код: {radio_proc.returncode}). "
                        f"Рестарт через {delay}с ({len(_restart_times)}/{MAX_RESTARTS})..."
                    )

                time.sleep(delay)
                radio_proc = start_radio()
                processes.append(radio_proc)
            else:
                _restart_attempt = max(0, _restart_attempt - 1)
                _progressive_attempt = max(0, _progressive_attempt - 1)

            # Мониторинг FM
            if FM_ENABLED and gr_proc and gr_proc.poll() is not None:
                now = time.time()
                _fm_restart_times[:] = [t for t in _fm_restart_times if now - t < RESTART_WINDOW]
                if len(_fm_restart_times) >= FM_MAX_RESTARTS:
                    print(f"[FM] Превышен лимит ({FM_MAX_RESTARTS}) рестартов. FM отключён.")
                    FM_ENABLED = False
                else:
                    _fm_restart_times.append(now)
                    print(f"[CRITICAL] GNU Radio упал (Код: {gr_proc.returncode}). Рестарт ({len(_fm_restart_times)}/{FM_MAX_RESTARTS})...")
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
    acquire_lock()
    start_station()
