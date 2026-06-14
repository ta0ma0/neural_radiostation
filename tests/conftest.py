import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def radio():
    from play_music import CyberRadio

    r = CyberRadio()
    r.master_stream = AsyncMock()
    r.master_stream.stdin = AsyncMock()
    r.master_stream.stderr = AsyncMock()
    r.master_stream.returncode = None
    r._restart_fails = 0
    r._restarting = False
    r._logged_waiting = False
    r.is_running = True
    r.playlist = []
    r._drain_fails = 0
    return r
