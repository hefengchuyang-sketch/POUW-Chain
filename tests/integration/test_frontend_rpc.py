"""Test all RPC methods that the frontend actually calls"""
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
                return "ERROR", result["error"].get("code", 0), result["error"]["message"]
            return "OK", 0, str(result.get("result", {}))[:100]
        except urllib.error.HTTPError as e:
            if e.code == 403:
                last_err = e
                continue
            return "FAIL", -1, str(e)[:100]
        except Exception as e:
            return "FAIL", -1, str(e)[:100]
    return "FAIL", -1, str(last_err)[:100] if last_err else "auth failed"

# All methods the frontend actually calls (extracted from api/index.ts)
tests = [
    # Wallet
    ("wallet_create", {"password": "test123"}),
    ("wallet_getInfo", {}),
    ("wallet_unlock", {"password": "test123"}),
    ("wallet_transfer", {"toAddress": "MAIN_TEST", "amount": 0.01, "sector": "MAIN"}),
    ("wallet_exportKeystore", {"password": "test123"}),
    
    # Dashboard
    ("dashboard_getStats", {}),
    ("dashboard_getRecentTasks", {"limit": 5}),
    ("dashboard_getRecentProposals", {"limit": 5}),
    ("dashboard_getBlockChart", {}),
    ("dashboard_getRewardTrend", {}),
    
    # Mining
    ("mining_getStatus", {}),
    ("mining_start", {"mode": "mine_only"}),
    ("mining_stop", {}),
    ("mining_setMode", {"mode": "mine_and_task"}),
    ("mining_getScore", {}),
    ("mining_getRewards", {"period": "7d"}),
    
    # Account
    ("account_getBalance", {}),
    ("account_getTransactions", {"limit": 20}),
    ("account_getSubAddresses", {}),
    ("account_createSubAddress", {"label": "test"}),
    
    # Chain & Stats
    ("chain_getInfo", {}),
    ("chain_getHeight", {}),
    ("stats_getNetwork", {}),
    ("stats_getBlocks", {"period": "7d"}),
    ("stats_getTasks", {"period": "7d"}),
    
    # Tasks
    ("task_getList", {}),
    ("task_create", {"title": "Test", "description": "Test task", "task_type": "gpu_compute", "gpu_type": "RTX4090", "gpu_count": 1, "estimated_hours": 1, "max_price": 10}),
    ("task_getInfo", {"task_id": "test"}),
    ("task_cancel", {"task_id": "test"}),
    ("task_getFiles", {"task_id": "test"}),
    ("task_getLogs", {"task_id": "test"}),
    ("task_getOutputs", {"task_id": "test"}),
    ("task_getRuntimeStatus", {"task_id": "test"}),
    
    # Governance
    ("governance_getProposals", {}),
    ("governance_getProposal", {"proposal_id": "test"}),
    ("governance_createProposal", {"title": "Test", "description": "Test", "category": "parameter"}),
    ("governance_vote", {"proposal_id": "test", "vote": "for"}),
    
    # Exchange
    ("sector_getExchangeRates", {}),
    ("sector_requestExchange", {"sector": "RTX4090", "amount": 1.0}),
    ("sector_getExchangeHistory", {"limit": 20}),
    ("sector_cancelExchange", {"exchangeId": "test"}),
    
    # Privacy
    ("privacy_getStatus", {}),
    ("privacy_rotateAddress", {}),
    
    # Miners
    ("miner_getList", {}),
    ("miner_getInfo", {"miner_id": "test"}),
    ("miner_register", {"gpuType": "RTX4090", "gpuCount": 1, "pricePerHour": 5.0}),
    
    # Compute market
    ("compute_getMarket", {}),
    
    # Orderbook
    ("orderbook_submitBid", {"gpuType": "RTX4090", "gpuCount": 1, "maxPricePerHour": 5.0, "duration": 3600}),
    ("orderbook_submitAsk", {"gpuType": "RTX4090", "gpuCount": 1, "pricePerHour": 5.0, "duration": 3600}),
    ("orderbook_getOrderBook", {"gpuType": "RTX4090"}),
    ("orderbook_getMyOrders", {}),
    ("orderbook_getMarketPrice", {"gpuType": "RTX4090"}),
    ("orderbook_cancelOrder", {"orderId": "test"}),
    ("orderbook_getMatches", {"limit": 10}),
    
    # Pricing
    ("pricing_calculatePrice", {"gpuType": "RTX4090", "hours": 1, "gpuCount": 1}),
    ("pricing_getMarketState", {}),
    ("pricing_getTimeSlotSchedule", {}),
    
    # Queue
    ("queue_enqueue", {"taskId": "test", "priority": 1}),
    ("queue_getEstimatedWaitTime", {"gpuType": "RTX4090", "priority": 1}),
    ("queue_getStats", {}),
    
    # Market dashboard
    ("market_getDashboard", {}),
    ("market_getSupplyDemandCurve", {}),
    ("market_getQueueStatus", {}),
    
    # Settlement
    ("settlement_getDetailedBill", {"taskId": "test"}),
    ("settlement_getMinerEarnings", {}),
    
    # Billing
    ("billing_getRates", {}),
    ("billing_estimateTask", {"gpuType": "RTX4090", "gpuCount": 1, "hours": 1}),
    ("billing_calculateCost", {"gpuType": "RTX4090", "gpuCount": 1, "hours": 1}),
    
    # Encrypted tasks
    ("encryptedTask_generateKeypair", {}),
    ("encryptedTask_create", {"title": "Test", "description": "test", "codeData": "dGVzdA==", "taskType": "compute", "estimatedHours": 1, "budgetPerHour": 5}),
    
    # P2P Tasks
    ("p2pTask_getList", {}),
    ("p2pTask_getMiners", {}),
    ("p2pTask_create", {"title": "Test", "taskType": "compute", "requirements": {}}),
    
    # Block
    ("block_getLatest", {}),
    
    # Node
    ("node_getInfo", {}),
    ("node_getPeers", {}),
]

ok_count = 0
err_count = 0
not_found = 0
permission_denied = 0

for method, params in tests:
    status, code, msg = call_rpc(method, params)
    if status == "OK":
        ok_count += 1
        print(f"  [OK]   {method}")
    elif code == -32601:
        not_found += 1
        print(f"  [404]  {method} -> NOT FOUND")
    elif code == -32403:
        permission_denied += 1
        print(f"  [AUTH] {method} -> Permission denied (expected for write ops)")
    else:
        err_count += 1
        print(f"  [ERR]  {method} -> {msg}")

total = len(tests)
print(f"\n{'='*60}")
print(f"Total: {total}")
print(f"  OK:         {ok_count}")
print(f"  Auth:       {permission_denied} (correct behavior)")
print(f"  Not Found:  {not_found}")
print(f"  Error:      {err_count}")
print(f"\nReal bugs = Not Found + Error = {not_found + err_count}")
