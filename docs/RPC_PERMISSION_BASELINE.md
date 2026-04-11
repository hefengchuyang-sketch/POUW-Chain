# RPC Permission Baseline

This document defines minimum RPC exposure rules for release gates.

## Baseline Rules

- Sensitive identity/asset/history methods must NOT be `PUBLIC`.
- New RPC methods must declare explicit permission and corresponding tests.
- `network.rpc.allowed_methods` should be used in production with a curated allowlist.

## Sensitive Methods (Minimum)

The following methods must remain non-public:

- `wallet_getInfo`
- `wallet_getBalance`
- `wallet_getTransactions`
- `account_getTransactions`
- `account_getSubAddresses`

## Gate Command

Run this before release:

```bash
python -m pytest tests/test_rpc_permission_baseline.py -q
```

## Notes

- If a new method returns wallet addresses, ownership metadata, balances, transaction history,
  decrypted payloads, private key material, or upload/session ownership info, treat it as sensitive.
- Keep this list aligned with `core/security.py` and RPC registry permissions.
