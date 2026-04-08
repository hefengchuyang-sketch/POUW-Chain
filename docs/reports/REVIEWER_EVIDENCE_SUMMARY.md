# Reviewer Evidence Summary

## Project
POUW-Chain: protocol-level validation for verifiable outsourced compute with owner-scoped output access.

## Evidence Package Scope
This summary consolidates four independently generated experiment reports:

1. `public_dataset_validation_iris.md`
2. `public_dataset_validation_digits.md`
3. `adversarial_access_report.md`
4. `large_chunk_integrity_report.md`

## Key Results

### 1) Public Dataset End-to-End Validation (Iris)
Source: `docs/reports/public_dataset_validation_iris.md`

- Dataset: Iris (150 rows, 4 features)
- Runs: 20
- End-to-end success rate: 100.0%
- Owner-only file access enforcement: 100.0%
- Owner-only result access enforcement: 100.0%
- Avg total latency: 3.402 ms
- P95 total latency: 3.922 ms

### 2) Medium-Scale Public Dataset Validation (Digits)
Source: `docs/reports/public_dataset_validation_digits.md`

- Dataset: Digits (1797 rows, 64 features)
- Runs: 10
- End-to-end success rate: 100.0%
- Owner-only file access enforcement: 100.0%
- Owner-only result access enforcement: 100.0%
- Avg total latency: 6.692 ms
- P95 total latency: 9.152 ms

### 3) Adversarial Access-Control Testing
Source: `docs/reports/adversarial_access_report.md`

- Rounds: 20
- Non-owner upload-session denial: 100.0%
- Non-owner file metadata denial: 100.0%
- Non-owner file download denial: 100.0%
- Non-owner task-output denial: 100.0%
- Malformed fileRef rejection: 100.0%
- Admin cross-owner access allowed: 100.0% (expected behavior)

### 4) Large-Chunk Integrity and Robustness
Source: `docs/reports/large_chunk_integrity_report.md`

- Rounds: 6
- Payload size: 9,437,307 bytes (~9 MB)
- Chunk size: 4,194,304 bytes (4 MB)
- Expected chunks per upload: 3
- Multi-chunk upload success: 100.0%
- End-to-end integrity verification: 100.0%
- Owner-only download enforcement: 100.0%
- Invalid chunk rejection: 100.0%
- Malformed fileRef rejection: 100.0%

## What This Demonstrates

1. Protocol workflow reliability
- The full compute lifecycle (upload -> order -> accept -> execute -> result return) consistently completes on public workloads.

2. Enforced ownership semantics
- Task outputs and uploaded artifacts are consistently restricted to owner/admin contexts.

3. Security behavior under adversarial probes
- Unauthorized access attempts and malformed references are consistently rejected.

4. Data-path robustness
- Multi-chunk transport and recomputed checksum validation hold under repeated large-payload runs.

## Reproducibility
All results were generated with runnable scripts in this repository:

- `scripts/generate_public_dataset_report.py`
- `scripts/run_adversarial_access_tests.py`
- `scripts/run_large_chunk_integrity_tests.py`

Example commands:

```bash
python scripts/generate_public_dataset_report.py --dataset iris --runs 20 --warmup 1
python scripts/generate_public_dataset_report.py --dataset digits --runs 10 --warmup 1
python scripts/run_adversarial_access_tests.py --rounds 20
python scripts/run_large_chunk_integrity_tests.py --rounds 6 --payload-mb 9
```

## Reviewer Note
This evidence package is intentionally privacy-preserving (public datasets, no personal user data), while still providing repeatable protocol-level validation for reliability, access control, and integrity.
