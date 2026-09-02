"""Generic latency + memory benchmark: wrap any callable, get p50/p95 latency
and peak RSS. Reused by every later phase to keep "CPU-efficient" a measured
claim rather than an assumed one.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow `python -m bench.benchmark` from repo root

from config import get_settings  # noqa: E402


@dataclass
class BenchResult:
    label: str
    iterations: int
    p50_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    peak_rss_bytes: int
    baseline_rss_bytes: int

    def peak_rss_delta_bytes(self) -> int:
        return self.peak_rss_bytes - self.baseline_rss_bytes


class _RssSampler:
    """Background thread that polls the current process's RSS to catch peaks
    that happen inside a single call, not just between calls."""

    def __init__(self, interval_s: float = 0.005):
        self._interval_s = interval_s
        self._process = psutil.Process()
        self._peak = self._process.memory_info().rss
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            rss = self._process.memory_info().rss
            if rss > self._peak:
                self._peak = rss
            self._stop.wait(self._interval_s)

    def __enter__(self) -> "_RssSampler":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)

    @property
    def peak_rss_bytes(self) -> int:
        return self._peak


def benchmark(fn: Callable[..., Any], *args: Any, iterations: int = 50, label: str | None = None, **kwargs: Any) -> BenchResult:
    """Run `fn(*args, **kwargs)` `iterations` times, measuring wall-clock
    latency per call and peak RSS across the whole run."""
    process = psutil.Process()
    baseline_rss = process.memory_info().rss
    latencies_ms: list[float] = []

    with _RssSampler() as sampler:
        for _ in range(iterations):
            start = time.perf_counter()
            fn(*args, **kwargs)
            latencies_ms.append((time.perf_counter() - start) * 1000)

    latencies_ms.sort()
    return BenchResult(
        label=label or getattr(fn, "__name__", "benchmarked_fn"),
        iterations=iterations,
        p50_ms=statistics.median(latencies_ms),
        p95_ms=latencies_ms[max(0, int(round(0.95 * (len(latencies_ms) - 1))))],
        min_ms=latencies_ms[0],
        max_ms=latencies_ms[-1],
        peak_rss_bytes=sampler.peak_rss_bytes,
        baseline_rss_bytes=baseline_rss,
    )


def print_report(result: BenchResult) -> None:
    print(f"=== Benchmark report: {result.label} ===")
    print(f"iterations   : {result.iterations}")
    print(f"p50 latency  : {result.p50_ms:.3f} ms")
    print(f"p95 latency  : {result.p95_ms:.3f} ms")
    print(f"min / max    : {result.min_ms:.3f} ms / {result.max_ms:.3f} ms")
    print(f"peak RSS     : {result.peak_rss_bytes / 1e6:.2f} MB")
    print(f"baseline RSS : {result.baseline_rss_bytes / 1e6:.2f} MB")
    print(f"RSS delta    : {result.peak_rss_delta_bytes() / 1e6:.2f} MB")


def _log_result(result: BenchResult, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    out_path = log_dir / f"bench_{result.label}_{int(time.time())}.json"
    out_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return out_path


def _sample_operation(n: int = 5000) -> int:
    """Sample operation for the CLI demo: nothing-domain-specific, just enough
    CPU + allocation to produce a non-trivial, non-zero measurement."""
    data = [i * i for i in range(n)]
    return sum(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generic latency + peak-RSS benchmark")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--label", default="sample_operation")
    parser.add_argument("--n", type=int, default=5000, help="workload size for the sample operation")
    parser.add_argument("--log", action="store_true", help="write a JSON result file to the configured bench_log_dir")
    args = parser.parse_args(argv)

    result = benchmark(_sample_operation, args.n, iterations=args.iterations, label=args.label)
    print_report(result)

    if args.log:
        settings = get_settings()
        out_path = _log_result(result, settings.bench_log_dir)
        print(f"logged to    : {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
