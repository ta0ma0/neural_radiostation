from unittest.mock import patch, MagicMock

from tools.network_monitor import status_from_loss, write_status, log_event


def test_status_from_loss_ok():
    assert status_from_loss(0, 10) == "OK"
    assert status_from_loss(0, 5) == "OK"


def test_status_from_loss_degradation():
    assert status_from_loss(8, 10) == "DEGRADATION"
    assert status_from_loss(9, 10) == "DEGRADATION"
    assert status_from_loss(4, 5) == "DEGRADATION"


def test_status_from_loss_lost():
    assert status_from_loss(10, 10) == "LOST"
    assert status_from_loss(5, 5) == "LOST"


def test_status_from_loss_mild_ok():
    assert status_from_loss(1, 10) == "OK"
    assert status_from_loss(3, 10) == "OK"
    assert status_from_loss(2, 5) == "OK"


def test_write_status(tmp_path):
    sf = tmp_path / "status"
    with patch("tools.network_monitor.STATUS_FILE", str(sf)):
        write_status("OK")
        assert sf.read_text().strip() == "OK"


def test_write_status_lost(tmp_path):
    sf = tmp_path / "status"
    with patch("tools.network_monitor.STATUS_FILE", str(sf)):
        write_status("LOST")
        assert sf.read_text().strip() == "LOST"


def test_log_event_creates_file(tmp_path):
    lf = tmp_path / "test.log"
    with patch("tools.network_monitor.LOG_FILE", str(lf)):
        log_event("OK", 0, 5, "72ms")
        assert lf.exists()
        content = lf.read_text()
        assert "OK" in content
        assert "0%" in content
        assert "ping=5/5" in content
