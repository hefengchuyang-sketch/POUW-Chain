# Large Chunk Integrity Report

## Executive Summary
- Rounds: 6
- Payload size: 9437307 bytes
- Chunk size: 4194304 bytes
- Expected chunks per file: 3
- Multi-chunk upload success: 100.0%
- End-to-end integrity verification: 100.0%
- Owner-only download enforcement: 100.0%
- Invalid chunk rejection: 100.0%
- Malformed fileRef rejection: 100.0%

## Timing (ms)
- Avg upload: 56.691
- P95 upload: 60.315
- Avg integrity verify: 46.567
- P95 integrity verify: 53.908

## Sample IDs
- uploadId: 90492aaba0e8498c
- fileRef: ce9f4471d461495a
- chunkCount: 3

## Reproducibility
- Generated at (UTC): 2026-04-08T13:23:56Z
- Command: python scripts/run_large_chunk_integrity_tests.py --rounds 6 --payload-mb 9