# Security Baseline Checklist

This checklist is the minimum security baseline before exposing any RPC endpoint to non-local users.

## 1. Environment Flags

Required values in production:

- REQUIRE_LOCAL_AUTH=true
- ALLOW_AUTH_USER_OVERRIDE=false
- ALLOW_INPROCESS_FALLBACK=false

Notes:

- `REQUIRE_LOCAL_AUTH=true` blocks localhost auto-trust.
- `ALLOW_AUTH_USER_OVERRIDE=false` prevents identity switching through headers.
- `ALLOW_INPROCESS_FALLBACK=false` ensures real code execution requires Docker isolation.

## 2. RPC Exposure Rules

- Bind RPC to localhost when possible.
- Put RPC behind reverse proxy with TLS.
- Require API key for all write methods.
- Disable permissive CORS origins in production.

## 3. File Access Control

- Upload sessions must be accessible only by uploader or admin.
- File download and metadata endpoints must verify owner/admin.
- Task output endpoints must verify task owner/admin.
- Reject malformed `fileRef` values before path resolution.

## 4. Sandbox Execution Policy

- Real user code execution must run in Docker sandbox.
- If Docker is unavailable, fail closed in production.
- Do not enable in-process fallback on internet-facing nodes.
- Keep scanner rules updated for import and escape patterns.

## 5. Secrets and Keys

- Use strong random `POUW_ADMIN_KEY`.
- Rotate admin key at fixed interval.
- Never commit `.env` or private keys.
- Store TLS cert and private key outside repository.

## 6. Dependency Hygiene

- Pin dependencies in requirements file.
- Run `pip check` in CI.
- Track known vulnerable packages and patch quickly.

## 7. Release Gate

Before release, verify all items below:

- Security flags set to production-safe values.
- RPC auth checks pass for write methods.
- Owner-only file and result access tested.
- Docker-required execution path validated.
- No high-severity issues in latest security review.

## 8. Quick Verification Commands

```powershell
# Verify security env values
Get-ChildItem Env:REQUIRE_LOCAL_AUTH,Env:ALLOW_AUTH_USER_OVERRIDE,Env:ALLOW_INPROCESS_FALLBACK

# Basic node startup check
python main.py --help

# Optional dependency consistency check
python -m pip check
```

## 9. Incident Response Minimum

- Log auth failures and permission denials.
- Keep audit logs for task output access.
- Revoke and rotate admin key after suspected compromise.
- Disable external RPC access until investigation completes.
