"""
tee_verifier_client.py - External attestation verifier integration.

Supports two modes:
1) local: run in-process verifier callback (default, no third-party server required)
2) http: forward to external verifier service over HTTP
"""

import json
import os
import time
import urllib.request
from typing import Any, Callable, Dict, Optional


class AttestationVerifierClient:
    """Client that forwards attestation verification to external verifier.

    Environment variables:
    - POUW_TEE_VERIFIER_MODE: local|http (default: local)
    - POUW_TEE_VERIFIER_URL: URL for HTTP verifier endpoint
    - POUW_TEE_VERIFIER_TIMEOUT_SECONDS: HTTP timeout seconds (default: 5)
    """

    def __init__(
        self,
        local_verifier: Callable[[Dict[str, Any]], Dict[str, Any]],
        mode: Optional[str] = None,
        verifier_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self._local_verifier = local_verifier
        self.mode = (mode or os.getenv("POUW_TEE_VERIFIER_MODE", "local")).strip().lower()
        self.verifier_url = (verifier_url or os.getenv("POUW_TEE_VERIFIER_URL", "")).strip()
        if timeout_seconds is None:
            try:
                timeout_seconds = int(os.getenv("POUW_TEE_VERIFIER_TIMEOUT_SECONDS", "5"))
            except Exception:
                timeout_seconds = 5
        self.timeout_seconds = max(1, int(timeout_seconds))

    def verify_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Verify attestation evidence.

        Returns a normalized dictionary:
        {
          "is_valid": bool,
          "reason": str,
          "verified_by": str,
          "verified_at": float,
          "verification_mode": "http"|"local",
        }
        """
        if self.mode == "http" and self.verifier_url:
            try:
                return self._verify_via_http(payload)
            except Exception as exc:
                # Fail-open to local verifier when third-party server is unavailable.
                local_result = self._verify_via_local(payload)
                local_result["reason"] = f"http_verifier_unavailable_fallback_local: {exc}"
                return local_result

        return self._verify_via_local(payload)

    def _verify_via_local(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self._local_verifier(payload)
        return {
            "is_valid": bool(result.get("is_valid")),
            "reason": str(result.get("reason", "")),
            "verified_by": str(result.get("verified_by", "local_verifier")),
            "verified_at": float(result.get("verified_at", time.time())),
            "verification_mode": "local",
        }

    def _verify_via_http(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.verifier_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return {
            "is_valid": bool(data.get("is_valid")),
            "reason": str(data.get("reason", "")),
            "verified_by": str(data.get("verified_by", "external_verifier")),
            "verified_at": float(data.get("verified_at", time.time())),
            "verification_mode": "http",
        }
