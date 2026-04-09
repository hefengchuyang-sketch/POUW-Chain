# Provider No-Leakage Write Test Report

## Executive Summary
- Generated at (UTC): 2026-04-09T07:43:53Z
- Scanner blocked suspicious write/exfil patterns: 6/6 (100.0%)
- Runtime write blocked rounds: 8/8 (100.0%)
- Probe file not created rounds: 8/8 (100.0%)

## Interpretation
- Provider task code could not persist probe files to workspace in this test scope.
- Static scanner rejected common write/exfil vectors before execution.

## Reproducibility
- Command: python scripts/run_provider_no_leakage_tests.py --rounds 8