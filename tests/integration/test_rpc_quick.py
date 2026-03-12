"""Quick RPC test for key frontend methods"""
import json
import urllib.request
import ssl
import sys

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

def call_rpc(method, params=None):
    if params is None:
        params = {}
    data = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }).encode()
    req = urllib.request.Request(
        "https://127.0.0.1:8545",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10, context=_SSL_CTX)
        result = json.loads(resp.read().decode())
        if "error" in result:
            return "ERROR", result["error"]["message"]
        return "OK", result.get("result", {})
    except Exception as e:
        return "FAIL", str(e)

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
