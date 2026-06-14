"""
URL configuration for vmwebsocket project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, re_path
from django.http import FileResponse
from pathlib import Path

from terminal.views import terminal_view
from terminal.views import mobile_view
from terminal.views import health_check_view
from terminal.views import log_receive_view
from terminal.views import stream_status_view

BASE = Path(__file__).resolve().parent.parent
STATIC = BASE / "terminal" / "static" / "terminal"


def static_file(path, content_type):
    return lambda r: FileResponse(open(STATIC / path, "rb"), content_type=content_type)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", terminal_view, name="terminal"),
    path("mobile/", mobile_view, name="mobile"),
    path("health-check/", health_check_view, name="health-check"),
    path("api/log/", log_receive_view, name="log-receive"),
    path("api/status/", stream_status_view, name="stream-status"),
    path("manifest.json", lambda r: FileResponse(
        open(BASE / "terminal" / "templates" / "terminal" / "manifest.json", "rb"),
        content_type="application/json",
    )),
    path("sw.js", static_file("sw.js", "application/javascript")),
    path("static/terminal/icon-192.png", static_file("icon-192.png", "image/png")),
    path("static/terminal/icon-512.png", static_file("icon-512.png", "image/png")),
    path("static/terminal/howler.min.js", static_file("howler.min.js", "application/javascript")),
    path("static/terminal/xterm.js", static_file("xterm.js", "application/javascript")),
    path("static/terminal/xterm.css", static_file("xterm.css", "text/css")),
]
