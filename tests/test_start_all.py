import os
import signal
import subprocess
import sys
from unittest.mock import Mock, patch, MagicMock, call

import pytest
import requests
import start_all


# ── Phase 1 tests (keep) ──

def test_backoff_delay_first():
    start_all._restart_attempt = 0
    assert start_all.backoff_delay() == 1


def test_backoff_delay_exponential():
    start_all._restart_attempt = 0
    results = [start_all.backoff_delay() for _ in range(6)]
    assert results == [1, 2, 4, 8, 16, 32]


def test_backoff_delay_capped():
    start_all._restart_attempt = 10
    assert start_all.backoff_delay() == 60


# ── Phase 3: Lock ──

class TestLock:
    def test_acquire_lock_creates_pid_file(self, tmp_path):
        pid_file = tmp_path / "dj_alyx_test.pid"
        with patch("start_all.PID_FILE", str(pid_file)):
            with patch("start_all.os.kill", side_effect=ProcessLookupError):
                start_all.acquire_lock()
                assert pid_file.exists()
                assert pid_file.read_text().strip() == str(os.getpid())
                pid_file.unlink()

    def test_acquire_lock_exits_if_running(self, tmp_path):
        pid_file = tmp_path / "dj_alyx_test.pid"
        pid_file.write_text("999999")
        with patch("start_all.PID_FILE", str(pid_file)):
            with patch("start_all.os.kill", return_value=None):
                with pytest.raises(SystemExit):
                    start_all.acquire_lock()

    def test_release_lock_removes_file(self, tmp_path):
        pid_file = tmp_path / "dj_alyx_test.pid"
        pid_file.write_text("1234")
        with patch("start_all.PID_FILE", str(pid_file)):
            start_all.release_lock()
            assert not pid_file.exists()

    def test_release_lock_nonexistent(self, tmp_path):
        pid_file = tmp_path / "nonexistent.pid"
        with patch("start_all.PID_FILE", str(pid_file)):
            start_all.release_lock()  # should not raise


# ── Phase 3: KillOldProcesses ──

class TestKillOldProcesses:
    def test_kills_all_patterns(self):
        with patch("start_all.os.system") as mock_sys:
            with patch("start_all.time.sleep"):
                start_all.kill_old_processes()
                assert mock_sys.call_count == 4
                calls = [c[0][0] for c in mock_sys.call_args_list]
                assert any("play_music.py" in c for c in calls)
                assert any("ezstream" in c for c in calls)
                assert any("ffmpeg.*s16le.*pipe" in c for c in calls)
                assert any("network_monitor.py" in c for c in calls)


# ── Phase 3: CheckRemote ──

class TestCheckRemote:
    def test_online(self):
        mock_resp = Mock()
        mock_resp.status_code = 200
        with patch("start_all.requests.get", return_value=mock_resp):
            assert start_all.check_remote() is True

    def test_offline(self):
        mock_resp = Mock()
        mock_resp.status_code = 503
        with patch("start_all.requests.get", return_value=mock_resp):
            assert start_all.check_remote() is False

    def test_exception(self):
        with patch("start_all.requests.get", side_effect=requests.exceptions.ConnectionError):
            assert start_all.check_remote() is False


# ── Phase 3: ReadNetworkStatus ──

class TestReadNetworkStatus:
    def test_reads_file(self, tmp_path):
        sf = tmp_path / "status"
        sf.write_text("LOST\n")
        with patch("start_all.NET_STATUS_FILE", str(sf)):
            assert start_all.read_network_status() == "LOST"

    def test_missing_file(self, tmp_path):
        sf = tmp_path / "nonexistent"
        with patch("start_all.NET_STATUS_FILE", str(sf)):
            assert start_all.read_network_status() == "OK"

    def test_empty_file(self, tmp_path):
        sf = tmp_path / "status"
        sf.write_text("")
        with patch("start_all.NET_STATUS_FILE", str(sf)):
            assert start_all.read_network_status() == ""

    def test_oserror(self, tmp_path):
        sf = tmp_path / "noaccess"
        with patch("start_all.NET_STATUS_FILE", str(sf)):
            with patch("start_all.open", side_effect=OSError):
                assert start_all.read_network_status() == "OK"


# ── Phase 3: StartCommands ──

class TestStartCommands:
    def test_start_netmon(self):
        with patch("start_all.subprocess.Popen") as mock_popen:
            start_all.start_netmon()
            cmd = " ".join(mock_popen.call_args[0][0])
            assert "tools/network_monitor.py" in cmd
            assert mock_popen.call_args[1].get("stdout") is subprocess.DEVNULL

    def test_start_radio_conda(self):
        start_all.FM_ENABLED = False
        with patch("start_all.subprocess.Popen") as mock_popen:
            proc = start_all.start_radio()
            cmd = " ".join(mock_popen.call_args[0][0])
            assert "conda" in cmd
            assert "play_music.py" in cmd
            assert "--fm" not in cmd

    def test_start_radio_with_fm(self):
        start_all.FM_ENABLED = True
        with patch("start_all.subprocess.Popen") as mock_popen:
            proc = start_all.start_radio()
            cmd = " ".join(mock_popen.call_args[0][0])
            assert "--fm" in cmd

    def test_check_gnuradio_success(self):
        with patch("start_all.subprocess.run", return_value=Mock()):
            assert start_all.check_gnuradio() is True

    def test_check_gnuradio_failure(self):
        with patch("start_all.subprocess.run", side_effect=FileNotFoundError):
            assert start_all.check_gnuradio() is False

    def test_start_fm_popen(self):
        with patch("os.path.exists", return_value=True):
            with patch("start_all.subprocess.Popen") as mock_popen:
                proc = start_all.start_fm()
                cmd = " ".join(mock_popen.call_args[0][0])
                assert "fm.py" in cmd

    def test_start_fm_creates_fifo(self):
        with patch("os.path.exists", return_value=False):
            with patch("os.mkfifo") as mock_fifo:
                with patch("start_all.subprocess.Popen"):
                    start_all.start_fm()
                    mock_fifo.assert_called_once_with("/tmp/grc_pipe")

    def test_start_radio_devnull_stdout(self):
        start_all.FM_ENABLED = False
        with patch("start_all.subprocess.Popen") as mock_popen:
            start_all.start_radio()
            kwargs = mock_popen.call_args[1]
            assert kwargs["stdout"] is subprocess.DEVNULL


# ── Phase 3: start_station() — main orchestrator loop ──

class TestStartStation:
    def make_mocks(self, poll_results=None):
        """Helper: создаёт замоканный radio_proc с последовательностью poll()."""
        if poll_results is None:
            poll_results = [None, 1]  # alive then dies

        radio_proc = MagicMock()
        radio_proc.poll.side_effect = poll_results
        radio_proc.returncode = 1

        netmon_proc = MagicMock()
        netmon_proc.poll.return_value = None

        return radio_proc, netmon_proc

    def test_starts_netmon_and_radio(self):
        radio_proc = MagicMock()
        radio_proc.poll.return_value = 1  # always dead
        radio_proc.returncode = 1
        netmon_proc = MagicMock()
        netmon_proc.poll.return_value = None

        with patch.multiple(
            start_all,
            kill_old_processes=Mock(),
            start_netmon=Mock(return_value=netmon_proc),
            start_radio=Mock(return_value=radio_proc),
            check_gnuradio=Mock(return_value=False),
            check_remote=Mock(),
            read_network_status=Mock(return_value="OK"),
            backoff_delay=Mock(return_value=0.01),
            MAX_RESTARTS=0,  # break immediately
            RESTART_WINDOW=3600,
        ):
            start_all.FM_ENABLED = False
            start_all._restart_attempt = 0
            start_all._progressive_attempt = 0
            start_all._restart_times.clear()
            start_all._fm_restart_times.clear()
            with patch.object(start_all, 'processes', []):
                with pytest.raises(SystemExit):
                    start_all.start_station()
                assert len(start_all.processes) >= 2

    def test_restarts_radio_on_crash(self):
        radio_proc = MagicMock()
        radio_proc.poll.return_value = 1  # always dead
        radio_proc.returncode = 1
        netmon_proc = MagicMock()
        netmon_proc.poll.return_value = None

        with patch.multiple(
            start_all,
            kill_old_processes=Mock(),
            start_netmon=Mock(return_value=netmon_proc),
            start_radio=Mock(return_value=radio_proc),
            check_gnuradio=Mock(return_value=False),
            check_remote=Mock(),
            read_network_status=Mock(return_value="OK"),
            backoff_delay=Mock(return_value=0.01),
            MAX_RESTARTS=0,  # break immediately
            RESTART_WINDOW=3600,
        ):
            start_all.FM_ENABLED = False
            start_all._restart_attempt = 0
            start_all._progressive_attempt = 0
            start_all._restart_times.clear()
            with patch.object(start_all, 'processes', []):
                start_radio_mock = start_all.start_radio
                with pytest.raises(SystemExit):
                    start_all.start_station()
                assert start_radio_mock.call_count >= 1

    def test_stops_after_max_restarts(self):
        radio_proc = MagicMock()
        radio_proc.poll.return_value = 1
        radio_proc.returncode = 1
        netmon_proc = MagicMock()
        netmon_proc.poll.return_value = None

        with patch.multiple(
            start_all,
            kill_old_processes=Mock(),
            start_netmon=Mock(return_value=netmon_proc),
            start_radio=Mock(return_value=radio_proc),
            check_gnuradio=Mock(return_value=False),
            check_remote=Mock(),
            read_network_status=Mock(return_value="OK"),
            backoff_delay=Mock(return_value=0.01),
            MAX_RESTARTS=0,
            RESTART_WINDOW=3600,
        ):
            start_all.FM_ENABLED = False
            start_all._restart_attempt = 0
            start_all._progressive_attempt = 0
            start_all._restart_times.clear()
            with patch.object(start_all, 'processes', []):
                print_calls = []
                with patch('builtins.print', side_effect=lambda *a: print_calls.append(a)):
                    with pytest.raises(SystemExit):
                        start_all.start_station()
                    assert any('Превышен лимит' in str(c) for c in print_calls)

    def test_uses_progressive_on_lost(self):
        radio_proc = MagicMock()
        radio_proc.poll.return_value = 1
        radio_proc.returncode = 1
        netmon_proc = MagicMock()
        netmon_proc.poll.return_value = None

        with patch.multiple(
            start_all,
            kill_old_processes=Mock(),
            start_netmon=Mock(return_value=netmon_proc),
            start_radio=Mock(return_value=radio_proc),
            check_gnuradio=Mock(return_value=False),
            check_remote=Mock(),
            read_network_status=Mock(return_value="LOST"),
            PROGRESSIVE_DELAYS=[0.01],
            MAX_RESTARTS=5,
            RESTART_WINDOW=3600,
        ):
            start_all.FM_ENABLED = False
            start_all._restart_attempt = 0
            start_all._progressive_attempt = 0
            start_all._restart_times.clear()
            with patch.object(start_all, 'processes', []):
                with patch('builtins.print') as mock_print:
                    with pytest.raises(SystemExit):
                        start_all.start_station()
                    lost_calls = [c for c in mock_print.call_args_list if 'Связь потеряна' in str(c)]
                    assert len(lost_calls) >= 1

    def test_writes_shutdown_when_progressive_exhausted(self):
        radio_proc = MagicMock()
        radio_proc.poll.return_value = 1
        radio_proc.returncode = 1
        netmon_proc = MagicMock()
        netmon_proc.poll.return_value = None

        with patch.multiple(
            start_all,
            kill_old_processes=Mock(),
            start_netmon=Mock(return_value=netmon_proc),
            start_radio=Mock(return_value=radio_proc),
            check_gnuradio=Mock(return_value=False),
            check_remote=Mock(),
            read_network_status=Mock(return_value="LOST"),
            PROGRESSIVE_DELAYS=[0.01],
            MAX_RESTARTS=5,
            RESTART_WINDOW=3600,
        ):
            start_all.FM_ENABLED = False
            start_all._restart_attempt = 0
            start_all._progressive_attempt = 0
            start_all._restart_times.clear()
            with patch.object(start_all, 'processes', []):
                with patch('builtins.print'):
                    with patch("start_all.open", create=True) as mock_open:
                        with pytest.raises(SystemExit):
                            start_all.start_station()
                        # Проверяем что shutdown файл был создан
                        write_calls = [c for c in mock_open.call_args_list if 'dj_alyx_shutdown' in str(c)]
                        assert len(write_calls) >= 1
