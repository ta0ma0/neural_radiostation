import datetime
import os
from unittest.mock import patch, MagicMock

from play_music import read_network_status


def test_read_network_status_ok(tmp_path):
    sf = tmp_path / "status"
    sf.write_text("OK\n")
    with patch("play_music.NET_STATUS_FILE", str(sf)):
        assert read_network_status() == "OK"


def test_read_network_status_lost(tmp_path):
    sf = tmp_path / "status"
    sf.write_text("LOST\n")
    with patch("play_music.NET_STATUS_FILE", str(sf)):
        assert read_network_status() == "LOST"


def test_read_network_status_shutdown(tmp_path):
    sf = tmp_path / "status"
    sf.write_text("SHUTDOWN\n")
    with patch("play_music.NET_STATUS_FILE", str(sf)):
        assert read_network_status() == "SHUTDOWN"


def test_read_network_status_missing(tmp_path):
    sf = tmp_path / "nonexistent"
    with patch("play_music.NET_STATUS_FILE", str(sf)):
        assert read_network_status() == "OK"


def test_read_network_status_empty(tmp_path):
    sf = tmp_path / "status"
    sf.write_text("")
    with patch("play_music.NET_STATUS_FILE", str(sf)):
        assert read_network_status() == ""
