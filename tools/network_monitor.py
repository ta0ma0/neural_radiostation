#!/usr/bin/env python3
import os
import re
import subprocess
import sys
import time
from datetime import datetime

TARGET = "djalyx.2077911.xyz"
STATUS_FILE = "/tmp/dj_alyx_network_status"
LOG_FILE = os.path.join(os.path.dirname(__file__), "network_monitor.log")

NORMAL_COUNT = 5
NORMAL_INTERVAL = 15
FAST_COUNT = 1
FAST_INTERVAL = 5


def ping(target, count, timeout=5):
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout), target],
            capture_output=True, text=True, timeout=count * (timeout + 1),
        )
        output = result.stdout + result.stderr
        m = re.search(r'(\d+)% packet loss', output)
        loss_pct = int(m.group(1)) if m else 100
        lost = loss_pct * count // 100
        rtt = ""
        m2 = re.search(r'(?:min/avg/max|round-trip).*= [\d.]+/([\d.]+)', output)
        if m2:
            rtt = m2.group(1)
        return lost, rtt
    except Exception:
        return count, ""


def status_from_loss(lost, count):
    if lost == 0:
        return "OK"
    if lost == count:
        return "LOST"
    if lost * 100 // count >= 80:
        return "DEGRADATION"
    return "OK"


def write_status(status):
    with open(STATUS_FILE, "w") as f:
        f.write(status + "\n")


def log_event(status, lost, count, rtt):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {status:<12} | {lost * 100 // count}% | rtt={rtt}ms | ping={count - lost}/{count}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"[NETMON] {line.strip()}")


def main():
    write_status("OK")
    fast_mode = False
    log_event("OK", 0, NORMAL_COUNT, "init")

    while True:
        if fast_mode:
            count = FAST_COUNT
            interval = FAST_INTERVAL
        else:
            count = NORMAL_COUNT
            interval = NORMAL_INTERVAL

        lost, rtt = ping(TARGET, count)
        status = status_from_loss(lost, count)
        log_event(status, lost, count, rtt)
        write_status(status)

        if status == "LOST":
            fast_mode = True
        elif status == "OK":
            fast_mode = False

        if os.path.exists("/tmp/dj_alyx_shutdown"):
            log_event("SHUTDOWN", 0, 0, "-")
            write_status("SHUTDOWN")
            break

        time.sleep(interval)


if __name__ == "__main__":
    main()
