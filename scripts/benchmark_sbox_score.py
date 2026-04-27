"""Benchmark S-Box scoring performance.

Compares two modes:
1) Pure Python path (POUW_SBOX_DISABLE_ACCEL=true)
2) Auto accel path (if core._sbox_accel is available)

Usage:
    py -3 scripts/benchmark_sbox_score.py --rounds 8
"""

from __future__ import annotations

import argparse
import importlib
import os
import statistics
import time
from typing import Dict, List


def _reload_engine(use_accel: bool):
    if use_accel:
        os.environ.pop("POUW_SBOX_DISABLE_ACCEL", None)
    else:
        os.environ["POUW_SBOX_DISABLE_ACCEL"] = "true"

    import core.sbox_engine as se

    return importlib.reload(se)


def _run_mode(rounds: int, use_accel: bool) -> Dict[str, float]:
    se = _reload_engine(use_accel)

    samples: List[List[int]] = [se.generate_random_sbox() for _ in range(rounds)]
    latencies_ms: List[float] = []

    for sbox in samples:
        t0 = time.perf_counter()
        _ = se.compute_sbox_score(sbox)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = statistics.fmean(latencies_ms)
    p95_ms = sorted(latencies_ms)[max(0, int(len(latencies_ms) * 0.95) - 1)]

    return {
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
        "min_ms": min(latencies_ms),
        "max_ms": max(latencies_ms),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark S-Box scoring performance")
    parser.add_argument("--rounds", type=int, default=6, help="number of scoring rounds per mode")
    args = parser.parse_args()

    rounds = max(2, int(args.rounds))

    try:
        import core._sbox_accel  # noqa: F401

        accel_available = True
    except Exception:
        accel_available = False

    py_stats = _run_mode(rounds=rounds, use_accel=False)
    accel_stats = _run_mode(rounds=rounds, use_accel=True)

    print("S-Box score benchmark")
    print(f"rounds={rounds}, accel_available={accel_available}")
    print(
        "python_only: "
        f"avg={py_stats['avg_ms']:.2f}ms, p95={py_stats['p95_ms']:.2f}ms, "
        f"min={py_stats['min_ms']:.2f}ms, max={py_stats['max_ms']:.2f}ms"
    )
    print(
        "auto_accel: "
        f"avg={accel_stats['avg_ms']:.2f}ms, p95={accel_stats['p95_ms']:.2f}ms, "
        f"min={accel_stats['min_ms']:.2f}ms, max={accel_stats['max_ms']:.2f}ms"
    )

    if accel_available and py_stats["avg_ms"] > 0:
        speedup = py_stats["avg_ms"] / accel_stats["avg_ms"]
        print(f"speedup(avg)={speedup:.2f}x")


if __name__ == "__main__":
    main()
