"""Quick RPC test for key frontend methods"""
import json
import urllib.request
import urllib.error
import sys
import rpc_auth_helper as auth_helper

RPC_URL = auth_helper.get_default_rpc_url()
_SSL_CTX = auth_helper.create_insecure_ssl_context()
_ACTIVE_API_KEY = None
_API_KEY_CANDIDATES = auth_helper.build_api_key_candidates()

def call_rpc(method, params=None):
    global _ACTIVE_API_KEY
    if params is None:
        params = {}
    data = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }).encode()
    keys_to_try = auth_helper.build_key_try_list(_ACTIVE_API_KEY, _API_KEY_CANDIDATES)

    last_err = None
    for api_key in keys_to_try:
        headers = auth_helper.build_rpc_headers(api_key=api_key)
        req = urllib.request.Request(
            RPC_URL,
            data=data,
            headers=headers
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10, context=_SSL_CTX)
            result = json.loads(resp.read().decode())
            _ACTIVE_API_KEY = api_key
            if "error" in result:
                return "ERROR", result["error"]["message"]
            return "OK", result.get("result", {})
        except urllib.error.HTTPError as e:
            if e.code == 403:
                last_err = e
                continue
            return "FAIL", str(e)
        except Exception as e:
            return "FAIL", str(e)
    return "FAIL", str(last_err) if last_err else "authentication failed"

# Key frontend methods to test
tests = [
    ("wallet_getAddress", {}),
    ("wallet_getBalance", {}),
    ("chain_getInfo", {}),
    ("chain_getLatestBlock", {}),
    ("dashboard_getOverview", {}),
    ("dashboard_getRewardTrend", {}),
    ("mining_getStatus", {}),
    ("mining_getHistory", {"page": 1, "pageSize": 10}),
    ("stats_getNetworkStats", {}),
    ("stats_getBlockStats", {"period": "7d"}),
    ("stats_getTaskStats", {"period": "7d"}),
    ("governance_getProposals", {}),
    ("governance_createProposal", {"title": "Test", "description": "Test proposal", "category": "parameter"}),
    ("staking_getInfo", {}),
    ("exchange_getOrderbook", {}),
    ("exchange_getMarketStats", {}),
    ("task_getList", {}),
    ("task_submitTask", {"title": "Test GPU", "taskType": "gpu_compute", "gpuType": "RTX4090", "gpuCount": 1, "maxPrice": 10, "duration": 3600, "image": "pytorch:latest", "command": "python train.py"}),
    ("orderbook_getOrders", {}),
    ("orderbook_submitBid", {"gpuType": "RTX4090", "gpuCount": 1, "maxPricePerHour": 5.0, "duration": 3600}),
    ("wallet_getTransactions", {"page": 1, "pageSize": 10}),
    ("security_getOverview", {}),
]

ok_count = 0
err_count = 0

for method, params in tests:
    status, result = call_rpc(method, params)
    icon = "OK" if status == "OK" else "FAIL"
    if status == "OK":
        ok_count += 1
        # Show truncated result
        result_str = str(result)[:80]
        print(f"  [OK]   {method} -> {result_str}")
    else:
        err_count += 1
        print(f"  [FAIL] {method} -> {result}")

print(f"\n{'='*60}")
print(f"Results: {ok_count} OK, {err_count} FAIL out of {len(tests)} tests")
