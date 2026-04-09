import json
import os
import ssl
import urllib.request
import urllib.error
from pathlib import Path

URL = "https://127.0.0.1:8545"


def _resolve_api_key() -> str:
    env_key = (os.getenv("POUW_ADMIN_KEY") or "").strip()
    if env_key:
        return env_key

    key_file = Path.home() / ".pouw_admin_key"
    if key_file.exists():
        try:
            key = key_file.read_text(encoding="utf-8").strip()
            if key:
                return key
        except Exception:
            pass
    return ""


API_KEY = _resolve_api_key()
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

_request_id = 1


def call(method, params):
    global _request_id
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": _request_id,
    }
    _request_id += 1
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return {
            "jsonrpc": "2.0",
            "id": payload["id"],
            "error": {
                "code": e.code,
                "message": err_body,
            },
        }


def main():
    if not API_KEY:
        print("warning=missing_api_key")

    submit = call(
        "compute_submitOrder",
        {
            "gpu_type": "RTX3080",
            "gpu_count": 1,
            "price_per_hour": 1.2,
            "duration_hours": 1,
            "buyer_address": "MAIN_SMOKE_USER",
        },
    )
    print("submit=", json.dumps(submit, ensure_ascii=False))

    order_id = ((submit.get("result") or {}).get("orderId") or "missing-order")

    checks = [
        ("compute_getOrder", {"order_id": order_id}),
        ("compute_getMarket", {}),
        ("compute_acceptOrder", {"order_id": order_id, "miner_id": "miner_smoke_1"}),
        ("compute_completeOrder", {"order_id": order_id, "result_data": "smoke_result"}),
        ("compute_getOrderEvents", {"order_id": order_id, "limit": 20}),
    ]

    for method, params in checks:
        result = call(method, params)
        print(f"{method}=", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
