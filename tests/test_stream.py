import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


class TestStreamTrack:
    """_stream_track() — чтение из decoder, запись в encoder"""

    @pytest.mark.asyncio
    async def test_reads_chunks_and_writes(self, radio):
        decoder = AsyncMock()
        decoder.stdout = AsyncMock()
        decoder.stdout.read = AsyncMock()
        decoder.stdout.read.side_effect = [b'\x00' * 65536, b'\x00' * 65536, b'']

        await radio._stream_track(decoder)

        assert decoder.stdout.read.call_count == 3
        assert radio.master_stream.stdin.write.call_count == 2
        assert radio.master_stream.stdin.drain.call_count == 2

    @pytest.mark.asyncio
    async def test_eof_exits_cleanly(self, radio):
        decoder = AsyncMock()
        decoder.stdout = AsyncMock()
        decoder.stdout.read = AsyncMock(return_value=b'')

        await radio._stream_track(decoder)

        decoder.stdout.read.assert_called_once()
        radio.master_stream.stdin.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_broken_pipe_propagates(self, radio):
        decoder = AsyncMock()
        decoder.stdout = AsyncMock()
        decoder.stdout.read = AsyncMock(return_value=b'\x00' * 65536)
        radio.master_stream.stdin.drain = AsyncMock(
            side_effect=BrokenPipeError()
        )

        with pytest.raises(BrokenPipeError):
            await radio._stream_track(decoder)

    @pytest.mark.asyncio
    async def test_decoder_read_timeout_propagates(self, radio):
        decoder = AsyncMock()
        decoder.stdout = AsyncMock()
        decoder.stdout.read = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        with pytest.raises(asyncio.TimeoutError):
            await radio._stream_track(decoder)


class TestMonitorMasterStderr:
    """_monitor_master_stderr() — чтение stderr, guard"""

    @pytest.mark.asyncio
    async def test_eof_exits_without_actions(self, radio):
        stream = radio.master_stream
        stream.stderr.readline = AsyncMock(return_value=b'')

        await radio._monitor_master_stderr()

        assert radio._restart_fails == 0

    @pytest.mark.asyncio
    async def test_error_lines_not_logged_when_no_error(self, radio):
        stream = radio.master_stream
        stream.stderr.readline = AsyncMock(
            side_effect=[b'size=1234KiB time=00:01:23\n', b'']
        )

        with patch('play_music.tty_log') as mock_log:
            await radio._monitor_master_stderr()
            error_calls = [c for c in mock_log.call_args_list
                           if 'size=' in str(c[0][0])]
            assert len(error_calls) == 0

    @pytest.mark.asyncio
    async def test_error_keyword_triggers_log(self, radio):
        stream = radio.master_stream
        stream.stderr.readline = AsyncMock(
            side_effect=[b'[error] connection refused\n', b'']
        )

        with patch('play_music.tty_log') as mock_log:
            await radio._monitor_master_stderr()
            ez_calls = [c for c in mock_log.call_args_list if 'connection refused' in str(c[0][0])]
            assert len(ez_calls) >= 1

    @pytest.mark.asyncio
    async def test_guard_skips_when_stream_replaced(self, radio):
        old_stream = radio.master_stream
        old_stream.stderr.readline = AsyncMock(return_value=b'')

        task = asyncio.create_task(radio._monitor_master_stderr())
        await asyncio.sleep(0.02)

        radio.master_stream = AsyncMock()
        radio.master_stream.stderr = AsyncMock()
        await asyncio.sleep(0.02)
        task.cancel()

        assert radio._restart_fails == 0


class TestRestartMasterStream:
    """_restart_master_stream() — cooldown, counter, escalation"""

    @pytest.mark.asyncio
    async def test_already_restarting_returns(self, radio):
        radio._restarting = True

        with patch('play_music.read_network_status') as mock_net:
            await radio._restart_master_stream()
            mock_net.assert_not_called()

    @pytest.mark.asyncio
    async def test_lost_returns(self, radio):
        with patch('play_music.read_network_status', return_value="LOST"):
            await radio._restart_master_stream()
            assert not radio._restarting

    @pytest.mark.asyncio
    async def test_kills_old_stream(self, radio):
        old_stream = radio.master_stream

        with patch('play_music.read_network_status', return_value="OK"):
            with patch('play_music.tty_log'):
                with patch('asyncio.create_subprocess_exec') as mock_exec:
                    mock_exec.return_value = AsyncMock()
                    await radio._restart_master_stream()
                    old_stream.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_escalate_below_max(self, radio):
        radio._restart_fails = 3
        radio.master_stream = None

        with patch('play_music.read_network_status', return_value="OK"):
            with patch.object(radio, '_restart_all') as mock_all:
                with patch('play_music.tty_log'):
                    with patch('play_music.MAX_CONSECUTIVE_FAILS', 5):
                        await radio._restart_master_stream()
                        mock_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_caller_traceback_logged(self, radio):
        with patch('play_music.read_network_status', return_value="OK"):
            with patch('play_music.tty_log') as mock_log:
                with patch('play_music.MAX_CONSECUTIVE_FAILS', 5):
                    radio.master_stream = None
                    await radio._restart_master_stream()
                    # Проверяем что caller log был вызван
                    calls = [c for c in mock_log.call_args_list if 'Вызов из' in str(c)]
                    assert len(calls) >= 1


class TestPlaySingleFile:
    """play_single_file() — file check, decoder, restart"""

    @pytest.mark.asyncio
    async def test_file_not_found_returns(self, radio):
        track = {"path": "/nonexistent/file.mp3", "artist": "Test", "title": "Track"}

        with patch('os.path.exists', return_value=False):
            with patch('play_music.tty_log') as mock_log:
                await radio.play_single_file(track)
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_master_stream_returns(self, radio):
        radio.master_stream = None
        track = {"path": "/some/file.mp3", "artist": "Test", "title": "Track"}

        with patch('os.path.exists', return_value=True):
            with patch('play_music.tty_log') as mock_log:
                await radio.play_single_file(track)
                assert any('не найден' in str(c) for c in mock_log.call_args_list)

    @pytest.mark.asyncio
    async def test_creates_decoder_and_streams(self, radio):
        track = {"path": "/some/file.mp3", "artist": "Test", "title": "Track"}

        decoder_mock = AsyncMock()
        decoder_mock.stdout = AsyncMock()
        decoder_mock.stdout.read = AsyncMock(return_value=b'')

        with patch('os.path.exists', return_value=True):
            with patch('asyncio.create_subprocess_exec', return_value=decoder_mock):
                with patch('play_music.tty_log'):
                    await radio.play_single_file(track)

        decoder_mock.stdout.read.assert_called()

    @pytest.mark.asyncio
    async def test_broken_pipe_calls_restart(self, radio):
        track = {"path": "/some/file.mp3", "artist": "Test", "title": "Track"}
        decoder_mock = AsyncMock()
        decoder_mock.stdout = AsyncMock()
        decoder_mock.stdout.read = AsyncMock(return_value=b'\x00' * 65536)
        decoder_mock.returncode = None

        radio.master_stream.stdin.drain = AsyncMock(
            side_effect=BrokenPipeError()
        )

        with patch('os.path.exists', return_value=True):
            with patch('asyncio.create_subprocess_exec', return_value=decoder_mock):
                with patch.object(radio, '_restart_master_stream') as mock_restart:
                    with patch('play_music.tty_log'):
                        await radio.play_single_file(track)
                        mock_restart.assert_called_once()


class TestStartMasterStream:
    """start_master_stream() — LOST check, ffmpeg launch"""

    @pytest.mark.asyncio
    async def test_lost_returns(self, radio):
        with patch('play_music.read_network_status', return_value="LOST"):
            with patch('play_music.tty_log') as mock_log:
                await radio.start_master_stream()
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_exits(self, radio):
        with patch('play_music.read_network_status', return_value="SHUTDOWN"):
            with patch('play_music.os._exit') as mock_exit:
                with patch('play_music.tty_log'):
                    await radio.start_master_stream()
                    mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_already_running_returns(self, radio):
        radio.master_stream.returncode = None  # process alive

        with patch('play_music.read_network_status', return_value="OK"):
            with patch('play_music.tty_log'):
                with patch('asyncio.create_subprocess_exec') as mock_exec:
                    await radio.start_master_stream()
                    mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_launches_ffmpeg(self, radio):
        radio.master_stream = None
        mock_proc = AsyncMock()
        mock_proc.stderr = AsyncMock()

        with patch('play_music.read_network_status', return_value="OK"):
            with patch('play_music.tty_log'):
                with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
                    await radio.start_master_stream()
                    assert radio.master_stream is mock_proc


class TestRadioCycle:
    """_radio_cycle() — dead stream detection, restart trigger"""

    @pytest.mark.asyncio
    async def test_lost_sleeps_and_returns(self, radio):
        radio.master_stream = None

        with patch('play_music.read_network_status', return_value="LOST"):
            with patch('play_music.tty_log'):
                with patch.object(radio, '_restart_master_stream') as mock_restart:
                    await radio._radio_cycle(0, 5, "", "", "")
                    mock_restart.assert_not_called()

    @pytest.mark.asyncio
    async def test_restarting_sleeps_and_returns(self, radio):
        radio._restarting = True
        radio.master_stream.returncode = -9

        with patch('play_music.read_network_status', return_value="OK"):
            with patch('play_music.tty_log'):
                with patch.object(radio, '_restart_master_stream') as mock_restart:
                    await radio._radio_cycle(0, 5, "", "", "")
                    mock_restart.assert_not_called()

    @pytest.mark.asyncio
    async def test_dead_stream_increments_counter_and_restarts(self, radio):
        radio.master_stream.returncode = 152

        with patch('play_music.read_network_status', return_value="OK"):
            with patch('play_music.tty_log'):
                with patch.object(radio, '_restart_master_stream') as mock_restart:
                    with patch('play_music.MAX_CONSECUTIVE_FAILS', 5):
                        await radio._radio_cycle(0, 5, "", "", "")
                        assert radio._restart_fails == 1
                        mock_restart.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_fails_calls_restart_all(self, radio):
        radio._restart_fails = 5
        radio.master_stream.returncode = 152

        with patch('play_music.read_network_status', return_value="OK"):
            with patch('play_music.tty_log'):
                with patch.object(radio, '_restart_all') as mock_all:
                    with patch('play_music.MAX_CONSECUTIVE_FAILS', 5):
                        await radio._radio_cycle(0, 5, "", "", "")
                        assert radio._restart_fails == 6
                        mock_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_healthy_stream_passes_through(self, radio):
        radio.master_stream.returncode = None

        with patch('play_music.read_network_status', return_value="OK"):
            with patch.object(radio, '_restart_master_stream') as mock_restart:
                with patch.object(radio, '_restart_all') as mock_all:
                    with patch.object(radio, 'get_random_track', return_value=None):
                        await radio._radio_cycle(0, 5, "", "", "")
                        mock_restart.assert_not_called()
                        mock_all.assert_not_called()
