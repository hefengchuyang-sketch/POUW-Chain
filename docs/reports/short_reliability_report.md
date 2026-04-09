# Short Reliability Validation Report

## Executive Summary
- Generated at (UTC): 2026-04-09T07:37:38Z
- Concurrency: 24/24 success (100.0%), workers=8
- Concurrency avg/p95 latency: 199.293 ms / 648.57 ms
- Restart recovery (owner file info): PASS
- Restart recovery (owner download): PASS
- Restart recovery (non-owner denied): PASS
- Reproducibility hash match: 20/20 (100.0%)

## Local Scope Note
- This suite is designed for local pre-production validation and does not model multi-region network faults.

## Reproducibility
- Command: python scripts/run_short_reliability_tests.py --cases 24 --workers 8 --repro-rounds 20