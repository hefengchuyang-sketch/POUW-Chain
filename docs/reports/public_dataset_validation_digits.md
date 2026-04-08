# Public Dataset Validation Report (Digits)

## Executive Summary
- Dataset: Digits (1797 rows, 64 features)
- Total runs: 10
- Successful runs: 10
- End-to-end success rate: 100.0%
- Owner-only file access enforcement: 100.0%
- Owner-only result access enforcement: 100.0%

## Latency Metrics (ms)
- Avg total latency: 6.692
- Median total latency: 6.223
- P95 total latency: 9.152
- Max total latency: 9.152
- Avg upload: 6.429
- Avg submit: 0.054
- Avg accept: 0.018
- Avg complete: 0.071
- Avg output fetch: 0.071

## Methodology
1. Upload publicly available Digits dataset as a task input artifact.
2. Submit compute order with inputDataRef and deterministic program payload.
3. Accept and complete task via compute workflow.
4. Verify buyer can read outputs while non-owner is denied.
5. Repeat for multiple independent runs and aggregate metrics.

## Reproducibility
- Generated at (UTC): 2026-04-08T13:10:57Z
- Command: python scripts/generate_public_dataset_report.py --dataset digits --runs 10 --warmup 1
- Warm-up runs excluded from metrics: 1

## Sample IDs (from one successful run)
- fileRef: 25aaf677061d49b9
- orderId: order_5d29e595
- taskId: task_order_5d29e595

## Reviewer Interpretation
This report demonstrates protocol-level evidence for a compute-blockchain workflow: input artifact ingestion, order lifecycle completion, output return, and owner-scoped access control.