import start_all


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
