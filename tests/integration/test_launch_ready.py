"""
POUW Chain - Final Pre-Launch Comprehensive Test
Tests ALL frontend RPC methods against the running backend
"""
import json
import urllib.request
import urllib.error
import sys
import time
import rpc_auth_helper as auth_helper

RPC_URL = auth_helper.get_default_rpc_url()
_SSL_CTX = auth_helper.create_insecure_ssl_context()
_ACTIVE_API_KEY = None
_API_KEY_CANDIDATES = auth_helper.build_api_key_candidates()

def rpc(method, params=None):
    global _ACTIVE_API_KEY
    data = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params if isinstance(params, dict) else (params or {}),
        "id": 1
    }).encode()
    keys_to_try = auth_helper.build_key_try_list(_ACTIVE_API_KEY, _API_KEY_CANDIDATES)

    for api_key in keys_to_try:
        headers = auth_helper.build_rpc_headers(api_key=api_key)
        req = urllib.request.Request(RPC_URL, data=data, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=10, context=_SSL_CTX)
            _ACTIVE_API_KEY = api_key
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 403:
                continue
            return {"connection_error": str(e)}
        except Exception as e:
            return {"connection_error": str(e)}
    return {"connection_error": "authentication failed"}

# All frontend rpcCall methods with their exact params
FRONTEND_METHODS = [
    # === Wallet ===
    ("wallet_create", {"password": "test123"}),
    ("wallet_getInfo", {}),
    ("wallet_unlock", {"password": "test123"}),
    
    # === Dashboard ===
    ("dashboard_getStats", {}),
    ("dashboard_getRecentTasks", {"limit": 5}),
    ("dashboard_getRecentProposals", {"limit": 5}),
    ("dashboard_getRewardTrend", {}),
    
    # === Mining ===
    ("mining_getStatus", {}),
    ("mining_getScore", {"miner_id": "test"}),
    ("mining_getRewards", {"period": "day"}),
    ("mining_setMode", {"mode": "normal"}),
    
    # === Exchange / Sector ===
    ("sector_getExchangeRates", {}),
    ("sector_requestExchange", {"sector": "H100", "amount": 1.0}),
    ("sector_getExchangeHistory", {"limit": 10}),
    ("sector_cancelExchange", {"exchangeId": "test_id"}),
    
    # === Account ===
    ("account_getSubAddresses", {"address": "test_addr"}),
    ("account_createSubAddress", {"label": "test"}),
    
    # === Chain / Blockchain ===
    ("chain_getInfo", {}),
    ("blockchain_getHeight", {}),
    ("blockchain_getBlock", {"height": 0}),
    ("blockchain_getLatestBlocks", {"limit": 5}),
    
    # === Tasks ===
    ("task_getList", {}),
    ("task_create", {
        "title": "Test Task", "taskType": "ai_training",
        "gpuType": "RTX_4090", "estimatedHours": 1,
        "pricingStrategy": "standard", "submitter": "test"
    }),
    ("task_cancel", {"task_id": "nonexistent"}),
    ("task_getInfo", {"task_id": "test_task"}),
    ("task_getFiles", {"task_id": "test"}),
    ("task_getLogs", {"task_id": "test"}),
    ("task_getOutputs", {"task_id": "test"}),
    ("task_getRuntimeStatus", {"task_id": "test"}),
    ("task_raiseDispute", {"task_id": "test", "reason": "test"}),
    ("task_acceptResult", {"task_id": "test", "rating": 5, "comment": "ok"}),
    
    # === Encrypted Tasks ===
    ("encryptedTask_generateKeypair", {}),
    ("encryptedTask_create", {
        "taskType": "ai_training", "gpuType": "RTX_4090",
        "estimatedHours": 1, "encryptedData": "test"
    }),
    ("encryptedTask_getStatus", {"taskId": "test"}),
    ("encryptedTask_getResult", {"taskId": "test", "privateKey": "test"}),
    ("encryptedTask_getBillingReport", {"taskId": "test"}),
    
    # === Compute Market ===
    ("compute_getMarket", {"gpu_type": "RTX_4090"}),
    ("compute_acceptOrder", {"order_id": "test", "task_id": "test"}),
    ("compute_cancelOrder", {"order_id": "test"}),
    ("compute_getOrder", {"order_id": "test"}),
    ("market_getQuotes", {"task_id": "test"}),
    ("market_acceptQuote", {"quote_id": "test"}),
    
    # === Governance ===
    ("governance_getProposals", {"status": "all"}),
    ("governance_getProposal", {"proposal_id": "test"}),
    ("governance_createProposal", {
        "title": "Test", "description": "Test proposal",
        "proposalType": "parameter_change", "duration": 7
    }),
    ("governance_vote", {"proposal_id": "test", "vote": "yes"}),
    
    # === Miner ===
    ("miner_getList", {"sort_by": "score"}),
    ("miner_getInfo", {"miner_id": "test"}),
    ("miner_getBehaviorReport", {"miner_id": "test"}),
    
    # === Stats ===
    ("stats_getBlocks", {"period": "24h"}),
    ("stats_getTasks", {"period": "24h"}),
    ("stats_getNetwork", {}),
    
    # === Privacy ===
    ("privacy_getStatus", {}),
    ("privacy_rotateAddress", {}),
    
    # === Orders ===
    ("order_getList", {"status": "all", "limit": 10}),
    ("order_getDetail", {"orderId": "test"}),
    
    # === Staking ===
    ("staking_getRecords", {"address": "test"}),
    ("staking_stake", {"amount": 100, "sector": "H100", "duration": 30}),
    ("staking_unstake", {"stakeId": "test"}),
    
    # === Pricing ===
    ("pricing_getBaseRates", {}),
    ("pricing_getRealTimePrice", {"gpuType": "RTX_4090"}),
    ("pricing_calculatePrice", {"gpuType": "RTX_4090", "hours": 1, "gpuCount": 1}),
    ("pricing_getMarketState", {}),
    ("pricing_getPriceForecast", {"gpuType": "RTX_4090", "hours": 24}),
    ("pricing_getTimeSlotSchedule", {}),
    ("pricing_getStrategies", {}),
    
    # === Orderbook ===
    ("orderbook_getOrderBook", {"gpuType": "RTX_4090"}),
    ("orderbook_getMarketPrice", {"gpuType": "RTX_4090"}),
    ("orderbook_getMyOrders", {}),
    ("orderbook_getMatches", {"limit": 10}),
    ("orderbook_submitBid", {
        "gpuType": "RTX_4090", "gpuCount": 1,
        "maxPricePerHour": 30.0, "duration": 3600
    }),
    ("orderbook_submitAsk", {
        "gpuType": "RTX_4090", "gpuCount": 1,
        "pricePerHour": 25.0, "duration": 3600
    }),
    ("orderbook_cancelOrder", {"orderId": "test"}),
    
    # === Billing ===
    ("billing_calculateCost", {"gpuType": "RTX_4090", "hours": 1}),
    ("billing_getRates", {}),
    ("billing_estimateTask", {"taskId": "test"}),
    
    # === Settlement ===
    ("settlement_getDetailedBill", {"taskId": "test"}),
    ("settlement_getMinerEarnings", {"period": "day"}),
    
    # === P2P Tasks ===
    ("p2pTask_create", {"title": "test", "taskType": "compute"}),
    ("p2pTask_distribute", {"taskId": "test"}),
    ("p2pTask_getList", {}),
    ("p2pTask_cancel", {"taskId": "test"}),
    ("p2pTask_registerMiner", {"minerId": "test", "gpuType": "RTX_4090"}),
    ("p2pTask_getMiners", {}),
    ("p2pTask_getResult", {"taskId": "test"}),
    
    # === Queue ===
    ("queue_enqueue", {"taskId": "test", "priority": "normal"}),
    ("queue_getEstimatedWaitTime", {"gpuType": "RTX_4090", "priority": "normal"}),
    ("queue_getStats", {}),
    
    # === Market Dashboard ===
    ("market_getDashboard", {}),
    ("market_getSupplyDemandCurve", {}),
    ("market_getQueueStatus", {}),
    
    # === Node ===
    ("node_getInfo", {}),
    ("node_getPeers", {}),
    ("node_isSyncing", {}),
    
    # === Network ===
    ("network_getStatus", {}),
    ("network_getPeerList", {}),
]

# Backend registered methods (for cross-check)
REGISTERED = set()

def get_registered_methods():
    r = rpc("rpc_listMethods")
    if "result" in r:
        for m in r["result"]:
            name = m["name"] if isinstance(m, dict) else m
            REGISTERED.add(name)
    return REGISTERED

if __name__ == "__main__":
    print("=" * 70)
    print("  POUW CHAIN - FINAL PRE-LAUNCH RPC VERIFICATION")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Get registered methods
    registered = get_registered_methods()
    print(f"\n  Backend registered methods: {len(registered)}")
    
    # Check which frontend methods are NOT registered
    frontend_names = set(m for m, _ in FRONTEND_METHODS)
    missing = frontend_names - registered
    if missing:
        print(f"\n  WARNING: {len(missing)} frontend methods NOT registered in backend:")
        for m in sorted(missing):
            print(f"    - {m}")
    
    # Test all methods
    print(f"\n  Testing {len(FRONTEND_METHODS)} frontend RPC calls...\n")
    
    ok = 0
    auth = 0  # Permission denied (expected for some)
    biz_err = 0  # Business logic errors (expected, e.g. "not found")
    not_found = 0  # Method not found
    internal_err = 0  # Internal Server Error (BUGS)
    conn_err = 0  # Connection errors
    
    failures = []
    
    for method, params in FRONTEND_METHODS:
        r = rpc(method, params)
        
        if "connection_error" in r:
            conn_err += 1
            failures.append(f"CONN  {method}: {r['connection_error']}")
            continue
        
        if "result" in r:
            ok += 1
            continue
        
        if "error" in r:
            err = r["error"]
            if isinstance(err, dict):
                code = err.get("code", 0)
                msg = err.get("message", "")
                detail = err.get("data", "")
                
                if code == -32601:  # Method not found
                    not_found += 1
                    failures.append(f"MISS  {method}: Method not found")
                elif code == -32001 or "permission" in msg.lower() or "denied" in msg.lower():
                    auth += 1  # Expected
                elif code == -32603:  # Internal Server Error
                    internal_err += 1
                    failures.append(f"BUG!  {method}: Internal Error - {detail}")
                else:
                    # Business logic error (e.g. "wallet not loaded", "not found")
                    biz_err += 1
            else:
                biz_err += 1
    
    total = len(FRONTEND_METHODS)
    print("-" * 70)
    print(f"  RESULTS: {total} methods tested")
    print(f"    OK (success response):    {ok}")
    print(f"    Business logic errors:    {biz_err}  (expected - e.g. 'not found')")
    print(f"    Auth/Permission denied:   {auth}  (expected for protected methods)")
    print(f"    Method NOT FOUND:         {not_found}  {'*** NEEDS FIX ***' if not_found > 0 else '(none)'}")
    print(f"    Internal Server Error:    {internal_err}  {'*** BUG ***' if internal_err > 0 else '(none)'}")
    print(f"    Connection Error:         {conn_err}  {'*** BACKEND DOWN? ***' if conn_err > 0 else '(none)'}")
    print("-" * 70)
    
    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for f in failures:
            print(f"    {f}")
    
    # Verdict
    critical = not_found + internal_err + conn_err
    print("\n" + "=" * 70)
    if critical == 0:
        print("  VERDICT: ALL FRONTEND RPC METHODS WORKING")
        print("  Zero Method-Not-Found, Zero Internal Errors")
        print("  ==> READY FOR LAUNCH")
    else:
        print(f"  VERDICT: {critical} CRITICAL ISSUES FOUND")
        if not_found > 0:
            print(f"    - {not_found} methods called by frontend don't exist in backend")
        if internal_err > 0:
            print(f"    - {internal_err} methods crash with Internal Server Error")
        print("  ==> NOT READY - NEEDS FIXES")
    print("=" * 70)
    
    sys.exit(0 if critical == 0 else 1)
