import json
from pathlib import Path

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
    return render(request, "terminal/terminal.html")


@traced_function()
def health_check_view(request):
    key = "health_check_key"
    value = "pong"
    cache.set(key, value, timeout=30)
    cached_value = cache.get(key)
    cache.delete(key)
    return JsonResponse({"status": "ok", "cache_value": cached_value})


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
