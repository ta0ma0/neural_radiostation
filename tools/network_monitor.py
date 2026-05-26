#!/usr/bin/env python3
"""Мониторинг сети до удалённого Icecast-сервера.

Записывает в лог тайминги HTTP-запросов к серверу.
Лог пишется в тот же файл, что и радио (dj_alyx_radio.log),
чтобы можно было сопоставить падения мастер-стрима с сетью.

Запуск:
  python tools/network_monitor.py
"""

import os
import sys
import time
import socket
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOST = "132.243.22.20"
PORT = 8000
INTERVAL = 2
LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "django-aws-terminal-websocket",
    "dj_alyx_radio.log",
)


def log(msg, style="info"):
    colors = {
        "info": "\033[32m[NET]\033[0m",
        "error": "\033[31m[NET]\033[0m",
        "time": f"\033[90m{datetime.now().strftime('%H:%M:%S')}\033[0m",
    }
    prefix = colors.get(style, colors["info"])
    full = f"{colors['time']} {prefix} {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{full}\n")
    except OSError:
        pass
    print(full, flush=True)


def measure():
    ok = 0
    fail = 0
    total = 0
    last_fail = 0
    rtts = []

    log(f"Старт мониторинга {HOST}:{PORT} (интервал {INTERVAL}с)", "info")

    try:
        while True:
            total += 1
            start = time.monotonic()
            try:
                sock = socket.create_connection((HOST, PORT), timeout=5)
                rtt = time.monotonic() - start
                sock.close()
                ok += 1
                rtts.append(rtt)
                last_fail = 0
                log(f"OK {rtt*1000:.0f}ms | ok={ok} fail={fail} loss={fail/total*100:.1f}%", "info")
            except socket.timeout:
                fail += 1
                last_fail += 1
                log(f"TIMEOUT 5s | ok={ok} fail={fail} loss={fail/total*100:.1f}%", "error")
            except OSError as e:
                fail += 1
                last_fail += 1
                log(f"ОШИБКА {e} | ok={ok} fail={fail} loss={fail/total*100:.1f}%", "error")

            if len(rtts) > 0:
                avg = sum(rtts[-60:]) / max(len(rtts[-60:]), 1) * 1000
                loss = fail / max(total, 1) * 100
                log(f"--- за 60с avg={avg:.0f}ms loss={loss:.1f}% ---", "info")

            if last_fail >= 10:
                log(f"КРИТИЧНО: {last_fail} последовательных отказов!", "error")

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        log(f"Остановлен. Итого: ok={ok} fail={fail} loss={fail/total*100:.1f}%", "info")


if __name__ == "__main__":
    measure()
