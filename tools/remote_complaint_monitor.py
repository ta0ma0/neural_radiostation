#!/usr/bin/env python3
"""
Remote complaint monitor — runs on the remote server (132.243.22.20).
Monitors Icecast mount and plays complaint.mp3 when source disappears.
"""
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ICECAST_URL = "http://127.0.0.1:8000"
COMPLAINT_FILE = "/opt/djalyx/django-aws-terminal-websocket/terminal/static/terminal/complaints/complaint.mp3"
LOG_FILE = "/opt/djalyx/django-aws-terminal-websocket/complaint_monitor.log"

SOURCE_PASS = os.getenv("ICECAST_SOURCE_PASSWORD", "")
if not SOURCE_PASS:
    env_file = Path("/opt/djalyx/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ICECAST_SOURCE_PASSWORD="):
                SOURCE_PASS = line.split("=", 1)[1].strip().strip("\"'")

_complaint_proc = None
_empty_since = None


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [{msg}]\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)


def check_mount():
    try:
        resp = urllib.request.urlopen(
            f"{ICECAST_URL}/status-json.xsl", timeout=5
        )
        data = json.loads(resp.read())
        sources = data.get("icestats", {}).get("source", [])
        if isinstance(sources, dict):
            sources = [sources]
        return bool(sources)
    except Exception as e:
        log(f"WARNING] Mount check error: {e}")
        return False


def main():
    global _complaint_proc, _empty_since
    log("INFO] Complaint monitor started")

    while True:
        has_source = check_mount()

        if not has_source:
            if _empty_since is None:
                _empty_since = time.time()
                log("INFO] Mount пуст, ждём 60с перед complaint")
            elif time.time() - _empty_since > 60 and _complaint_proc is None:
                if os.path.exists(COMPLAINT_FILE):
                    log("INFO] Запуск complaint в Icecast")
                    _complaint_proc = subprocess.Popen(
                        [
                            "ffmpeg", "-re", "-i", COMPLAINT_FILE,
                            "-c:a", "libmp3lame", "-b:a", "64k", "-f", "mp3",
                            f"icecast://source:{SOURCE_PASS}@127.0.0.1:8000/djalyx",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    log(f"WARNING] Файл complaint не найден: {COMPLAINT_FILE}")
        else:
            _empty_since = None
            if _complaint_proc is not None:
                log("INFO] Mount активен, останавливаю complaint")
                _complaint_proc.kill()
                _complaint_proc = None

        time.sleep(30)


if __name__ == "__main__":
    main()
