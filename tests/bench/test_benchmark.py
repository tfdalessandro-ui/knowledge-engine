import time

from bench.benchmark import benchmark


def _fast_noop():
    return 1 + 1


def _sleep_a_bit():
    time.sleep(0.01)


def test_benchmark_reports_sane_latency_fields():
    result = benchmark(_fast_noop, iterations=20, label="fast_noop")
    assert result.iterations == 20
    assert result.min_ms <= result.p50_ms <= result.p95_ms <= result.max_ms
    assert result.p50_ms >= 0


def test_benchmark_p50_reflects_workload_duration():
    result = benchmark(_sleep_a_bit, iterations=10, label="sleep_10ms")
    assert result.p50_ms >= 8  # allow scheduler jitter below the 10ms nominal sleep


def test_benchmark_peak_rss_is_positive():
    result = benchmark(_fast_noop, iterations=5, label="fast_noop_rss")
    assert result.peak_rss_bytes > 0
    assert result.baseline_rss_bytes > 0
