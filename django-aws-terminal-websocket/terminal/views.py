import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
VERSION = (BASE / "VERSION").read_text().strip()

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.cache import cache

LOG_HISTORY = Path(__file__).resolve().parent.parent / "radio_history.log"

try:
    from terminal.otel_tracing import traced_function
except ImportError:
    def traced_function(*args, **kwargs):
        return lambda f: f  # no-op fallback


@traced_function()
def terminal_view(request):
    return render(request, "terminal/terminal.html", {"version": VERSION})

@traced_function()
def mobile_view(request):
    return render(request, "terminal/mobile.html", {"version": VERSION})


@traced_function()
def health_check_view(request):
    key = "health_check_key"
    value = "pong"
    cache.set(key, value, timeout=30)
    cached_value = cache.get(key)
    cache.delete(key)
    return JsonResponse({"status": "ok", "cache_value": cached_value})


ICECAST_STATUS_URL = "http://127.0.0.1:8000/status-json.xsl"


@traced_function()
def stream_status_view(request):
    try:
        import urllib.request
        import xml.etree.ElementTree as ET

        resp = urllib.request.urlopen(ICECAST_STATUS_URL, timeout=5)
        data = json.loads(resp.read())
        sources = data.get("icestats", {}).get("source", [])
        if isinstance(sources, dict):
            sources = [sources]
    except Exception:
        return JsonResponse({"streaming": False, "listeners": 0, "source": None})

    source = sources[0] if sources else None
    return JsonResponse({
        "streaming": source is not None,
        "listeners": int(source.get("listeners", 0)) if source else 0,
        "source": source.get("server_name") if source else None,
        "bitrate": int(source.get("bitrate", 0)) if source else 0,
    })


@csrf_exempt
@require_POST
def log_receive_view(request):
    message = request.body.decode("utf-8", errors="replace")
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "logs",
        {"type": "log.message", "message": message},
    )

    try:
        with open(LOG_HISTORY, "a", encoding="utf-8") as f:
            f.write(message)
    except OSError:
        pass

    return JsonResponse({"status": "ok"})
