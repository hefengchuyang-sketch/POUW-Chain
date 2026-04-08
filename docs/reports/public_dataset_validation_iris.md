# Public Dataset Validation Report (Iris)

## Executive Summary
- Dataset: Iris (150 rows, 4 features)
- Total runs: 20
- Successful runs: 20
- End-to-end success rate: 100.0%
- Owner-only file access enforcement: 100.0%
- Owner-only result access enforcement: 100.0%

## Latency Metrics (ms)
- Avg total latency: 3.402
- Median total latency: 3.367
- P95 total latency: 3.922
- Max total latency: 4.144
- Avg upload: 3.145
- Avg submit: 0.051
- Avg accept: 0.017
- Avg complete: 0.072
- Avg output fetch: 0.067

## Methodology
1. Upload publicly available Iris dataset as a task input artifact.
2. Submit compute order with inputDataRef and deterministic program payload.
3. Accept and complete task via compute workflow.
4. Verify buyer can read outputs while non-owner is denied.
5. Repeat for multiple independent runs and aggregate metrics.

## Reproducibility
- Generated at (UTC): 2026-04-08T13:03:59Z
- Command: python scripts/generate_public_dataset_report.py --runs 20 --warmup 1
- Warm-up runs excluded from metrics: 1

## Sample IDs (from one successful run)
- fileRef: 6cebcfe2a973439a
- orderId: order_0659b585
- taskId: task_order_0659b585

## Reviewer Interpretation
This report demonstrates protocol-level evidence for a compute-blockchain workflow: input artifact ingestion, order lifecycle completion, output return, and owner-scoped access control.