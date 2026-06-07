import logging
import os
import subprocess
import time

import requests
from celery import shared_task
from django.conf import settings
from terminal.otel_tracing import traced_function

logger = logging.getLogger(__name__)

COMPLAINT_FILE = "/app/terminal/static/terminal/complaints/complaint.mp3"
ICECAST_URL = "http://host.docker.internal:8000"
SOURCE_PASS = os.getenv("ICECAST_SOURCE_PASSWORD", "change_me_in_env")

_complaint_proc = None
_icecast_empty_since = None


@shared_task
@traced_function()
def health_check_task():
    url = settings.HEALTH_CHECK_URL
    try:
        response = requests.get(url, timeout=10)
        logger.info(
            f"Health check status: {response.status_code}, body: {response.text}"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")


@shared_task
@traced_function()
def complaint_task():
    global _complaint_proc, _icecast_empty_since

    try:
        resp = requests.get(f"{ICECAST_URL}/status-json.xsl", timeout=5)
        data = resp.json()
        sources = data.get("icestats", {}).get("source", [])
        if isinstance(sources, dict):
            sources = [sources]
        has_source = bool(sources)
    except Exception:
        has_source = False

    now = time.time()
    if not has_source:
        if _icecast_empty_since is None:
            _icecast_empty_since = now
            logger.info("[COMPLAINT] Mount пуст, запускаю таймер 60с")
        elif now - _icecast_empty_since > 60 and _complaint_proc is None:
            if os.path.exists(COMPLAINT_FILE):
                logger.info("[COMPLAINT] Запуск complaint.mp3 в Icecast")
                _complaint_proc = subprocess.Popen(
                    [
                        "ffmpeg", "-re", "-i", COMPLAINT_FILE,
                        "-c:a", "libmp3lame", "-b:a", "64k", "-f", "mp3",
                        f"icecast://source:{SOURCE_PASS}@{ICECAST_URL.lstrip('http://')}/djalyx",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                logger.warning(f"[COMPLAINT] Файл не найден: {COMPLAINT_FILE}")
    else:
        _icecast_empty_since = None
        if _complaint_proc is not None:
            logger.info("[COMPLAINT] Mount активен, останавливаю complaint")
            _complaint_proc.kill()
            _complaint_proc = None
