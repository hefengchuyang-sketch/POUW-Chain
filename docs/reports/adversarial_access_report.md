# Adversarial Access Control Report

## Executive Summary
- Rounds: 20
- Non-owner upload-session denial: 100.0%
- Non-owner file info denial: 100.0%
- Non-owner file download denial: 100.0%
- Non-owner task output denial: 100.0%
- Malformed fileRef rejection: 100.0%
- Admin cross-owner access allowed: 100.0%

## Scenarios
1. Cross-user upload session probing
2. Cross-user file metadata access
3. Cross-user file content download
4. Cross-user task output read
5. Path-traversal-like malformed fileRef input
6. Admin override verification

## Sample IDs
- uploadId: b1de5d96915c492b
- fileRef: dfe8b6356f514f82
- orderId: order_85e14632
- taskId: task_order_85e14632

## Reproducibility
- Generated at (UTC): 2026-04-08T13:14:16Z
- Command: python scripts/run_adversarial_access_tests.py --rounds 20