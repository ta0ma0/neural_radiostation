import os
import signal
import subprocess
import sys
import time

# --- НАСТРОЙКИ ---
ENV_NAME = "f5-tts"
PROJECT_DIR = os.path.expanduser("~/Develop/Music/dj_alyx")
GR_SCRIPT = os.path.join(PROJECT_DIR, "fm.py")
FIFO_PATH = "/tmp/grc_pipe"
SSH_TUNNEL_CMD = ["ssh", "-N", "-T", "-R", "80:127.0.0.1:8884", "aeza"]

# Переменные окружения
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


def cleanup(sig=None, frame=None):
    print("\n[!] Останавливаем все процессы...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
            # Ждем немного, чтобы процессы закрылись чисто
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)


def start_station():
    if not os.path.exists(FIFO_PATH):
        print(f"[*] Создаю FIFO: {FIFO_PATH}")
        os.mkfifo(FIFO_PATH)

    try:
        os.chdir(PROJECT_DIR)

        # 1. Запуск радиостанции (Conda)
        print(f"[1/3] Запуск Alyx (Conda: {ENV_NAME})...")
        radio_cmd = [
            "conda",
            "run",
            "-n",
            ENV_NAME,
            "--no-capture-output",
            "python",
            "-u",
            os.path.join(PROJECT_DIR, "play_music.py"),
        ]
        radio_proc = subprocess.Popen(
            radio_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
        processes.append(radio_proc)

        time.sleep(1)

        # 2. Запуск GNU Radio (Системный Python)
        print("[2/3] Запуск GNU Radio...")
        gr_proc = subprocess.Popen([sys.executable, "-u", GR_SCRIPT], env=CUSTOM_ENV)
        processes.append(gr_proc)

        # 3. Запуск SSH Туннеля
        print("[3/3] Проброс порта на aeza (Reverse Tunnel)...")
        # Добавляем ExitOnForwardFailure, чтобы скрипт сразу упал, если порт на сервере занят
        tunnel_cmd = SSH_TUNNEL_CMD + ["-o", "ExitOnForwardFailure=yes"]
        ssh_proc = subprocess.Popen(
            tunnel_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        processes.append(ssh_proc)

        print("\n[READY] Радио вещает локально и через туннель.")
        print("Нажми Ctrl+C, чтобы выключить всё сразу.")

        while True:
            if gr_proc.poll() is not None:
                print(f"[CRITICAL] GNU Radio упал (Код: {gr_proc.returncode})")
                break
                # Стало:
                radio_proc = subprocess.Popen(
                    radio_cmd, stdout=sys.stdout, stderr=sys.stderr
                )
            if ssh_proc.poll() is not None:
                err = ssh_proc.stderr.read().decode()
                print(f"[ERROR] SSH Туннель закрылся: {err}")
                break
            time.sleep(2)

    except Exception as e:
        print(f"Ошибка оркестрации: {e}")
    finally:
        cleanup()


if __name__ == "__main__":
    start_station()
