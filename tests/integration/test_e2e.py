"""
End-to-end functional verification of the POUW blockchain system.
Tests complete user flows: wallet 鈫?mining 鈫?governance 鈫?transfer 鈫?exchange 鈫?tasks
"""
import json
import urllib.request
import urllib.error
import time
import os
import pytest
import rpc_auth_helper as auth_helper

BASE_URL = auth_helper.get_default_rpc_url()
WALLET_PASSWORD = os.getenv("POUW_E2E_WALLET_PASSWORD", "E2Epass123")
_SSL_CTX = auth_helper.create_insecure_ssl_context()

_API_KEY_CANDIDATES = auth_helper.build_api_key_candidates()
_ACTIVE_API_KEY = None
_INLINE_RUN = (__name__ == "__main__")


def _is_node_reachable() -> bool:
    try:
        req = urllib.request.Request(BASE_URL)
        urllib.request.urlopen(req, timeout=2, context=_SSL_CTX)
        return True
    except urllib.error.HTTPError:
        # 能连上但状态码非 2xx，也视为节点可达
        return True
    except Exception:
        return False


def ensure_wallet_ready():
    """Ensure wallet-dependent E2E cases have an active local wallet."""
    info = rpc("wallet_getInfo")
    if info.get("connected") or info.get("address"):
        return

    created = rpc("wallet_create", {"password": WALLET_PASSWORD})
    if not created or not created.get("success"):
        raise Exception(f"wallet_create failed: {created}")

    verify = rpc("wallet_getInfo")
    if not (verify.get("connected") or verify.get("address")):
        raise Exception("wallet is still not connected after wallet_create")


def rpc(method, params=None, auth_user=None):
    """Call JSON-RPC method"""
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
        headers = auth_helper.build_rpc_headers(api_key=api_key, auth_user=(auth_user or ""))

        req = urllib.request.Request(BASE_URL, data=data, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=15, context=_SSL_CTX)
            result = json.loads(resp.read().decode())
            if "error" in result:
                raise Exception(f"RPC Error {result['error'].get('code')}: {result['error']['message']}")
            _ACTIVE_API_KEY = api_key
            return result.get("result")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                last_err = e
                continue
            raise

    if last_err is not None:
        raise last_err
    raise Exception("RPC request failed without HTTP response")


if _INLINE_RUN:
    ensure_wallet_ready()

passed = 0
failed = 0

def _run_test(name, fn):
    if not _INLINE_RUN:
        return
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        print(f"  [FAIL] {name}: {e}")

# ========== 1. Wallet Flow ==========
print("\n===== 1. WALLET FLOW =====")


@pytest.fixture(scope="module", autouse=True)
def _ensure_wallet_ready_for_pytest():
    if not _is_node_reachable():
        pytest.skip("需要运行中的本地 RPC 节点以执行 E2E 测试")
    ensure_wallet_ready()

wallet_address = None

def test_wallet_info():
    global wallet_address
    info = rpc("wallet_getInfo")
    assert info.get("connected") or info.get("address"), "Wallet should have address"
    wallet_address = info.get("address", "")
    
_run_test("wallet_getInfo", test_wallet_info)

def test_wallet_balance():
    bal = rpc("account_getBalance")
    assert "balance" in bal or "mainBalance" in bal, "Should return balance"
    print(f"           Balance: {bal.get('balance', 0)}")

_run_test("account_getBalance", test_wallet_balance)

def test_wallet_transactions():
    txs = rpc("account_getTransactions", {"limit": 5})
    assert "transactions" in txs, "Should return transactions array"

_run_test("account_getTransactions", test_wallet_transactions)

def test_wallet_sub_addresses():
    addrs = rpc("account_getSubAddresses")
    assert isinstance(addrs, list), "Should return list"

_run_test("account_getSubAddresses", test_wallet_sub_addresses)

def test_wallet_export():
    result = rpc("wallet_exportKeystore", {"password": "test123"})
    assert result is not None, "Should return keystore"

_run_test("wallet_exportKeystore", test_wallet_export)

# ========== 2. Dashboard Flow ==========
print("\n===== 2. DASHBOARD FLOW =====")

def test_dashboard_stats():
    stats = rpc("dashboard_getStats")
    assert "blockHeight" in stats or "balance" in stats, "Should return stats"
    print(f"           Block Height: {stats.get('blockHeight', 'N/A')}")

_run_test("dashboard_getStats", test_dashboard_stats)

def test_dashboard_recent_tasks():
    tasks = rpc("dashboard_getRecentTasks", {"limit": 5})
    assert isinstance(tasks, list), "Should return list"

_run_test("dashboard_getRecentTasks", test_dashboard_recent_tasks)

def test_dashboard_block_chart():
    chart = rpc("dashboard_getBlockChart")
    assert "data" in chart or "total" in chart, "Should return chart data"

_run_test("dashboard_getBlockChart", test_dashboard_block_chart)

def test_dashboard_reward_trend():
    trend = rpc("dashboard_getRewardTrend")
    assert "data" in trend, "Should return trend data"

_run_test("dashboard_getRewardTrend", test_dashboard_reward_trend)

# ========== 3. Mining Flow ==========
print("\n===== 3. MINING FLOW =====")

def test_mining_status():
    status = rpc("mining_getStatus")
    assert "isMining" in status, "Should return mining status"
    print(f"           Mining: {status.get('isMining')}, Address: {status.get('minerAddress', 'N/A')[:20]}")

_run_test("mining_getStatus", test_mining_status)

def test_mining_start():
    result = rpc("mining_start", {"mode": "mine_only"})
    assert result is not None, "Should return result"

_run_test("mining_start", test_mining_start)

def test_mining_set_mode():
    result = rpc("mining_setMode", {"mode": "mine_and_task"})
    assert result is not None, "Should return result"

_run_test("mining_setMode", test_mining_set_mode)

def test_mining_score():
    score = rpc("mining_getScore")
    assert score is not None, "Should return score"

_run_test("mining_getScore", test_mining_score)

def test_mining_rewards():
    rewards = rpc("mining_getRewards", {"period": "7d"})
    assert "rewards" in rewards or "totalAmount" in rewards, "Should return rewards"

_run_test("mining_getRewards", test_mining_rewards)

def test_mining_stop():
    result = rpc("mining_stop")
    assert result is not None, "Should return result"

_run_test("mining_stop", test_mining_stop)

# ========== 4. Chain & Stats ==========
print("\n===== 4. CHAIN & STATISTICS =====")

def test_chain_info():
    info = rpc("chain_getInfo")
    assert "height" in info or "totalBlocks" in info, "Should return chain info"
    print(f"           Height: {info.get('height', 'N/A')}, Blocks: {info.get('totalBlocks', 'N/A')}")

_run_test("chain_getInfo", test_chain_info)

def test_block_latest():
    block = rpc("block_getLatest")
    assert block is not None, "Should return latest block"

_run_test("block_getLatest", test_block_latest)

def test_stats_network():
    stats = rpc("stats_getNetwork")
    assert stats is not None, "Should return network stats"

_run_test("stats_getNetwork", test_stats_network)

def test_stats_blocks():
    stats = rpc("stats_getBlocks", {"period": "7d"})
    assert "taskBlocks" in stats or "totalRewards" in stats, "Should return block stats"

_run_test("stats_getBlocks", test_stats_blocks)

def test_stats_tasks():
    stats = rpc("stats_getTasks", {"period": "7d"})
    assert "totalTasks" in stats, "Should return task stats"

_run_test("stats_getTasks", test_stats_tasks)

# ========== 5. Governance Flow ==========
print("\n===== 5. GOVERNANCE FLOW =====")

proposal_id = None

def test_gov_create_proposal():
    global proposal_id
    result = rpc("governance_createProposal", {
        "title": "E2E Test Proposal",
        "description": "This is an end-to-end test proposal",
        "category": "parameter"
    })
    assert result.get("success"), f"Should create proposal: {result.get('message', '')}"
    proposal_id = result.get("proposal", {}).get("proposalId")
    print(f"           Proposal ID: {proposal_id}")

_run_test("governance_createProposal", test_gov_create_proposal)

def test_gov_list_proposals():
    result = rpc("governance_getProposals")
    assert isinstance(result, list) or isinstance(result, dict), "Should return proposals"

_run_test("governance_getProposals", test_gov_list_proposals)

def test_gov_get_proposal():
    if not proposal_id:
        raise Exception("No proposal created")
    result = rpc("governance_getProposal", {"proposal_id": proposal_id})
    assert result is not None, "Should return proposal"

_run_test("governance_getProposal", test_gov_get_proposal)

def test_gov_vote():
    if not proposal_id:
        raise Exception("No proposal created")
    result = rpc("governance_vote", {"proposal_id": proposal_id, "vote": "for"})
    assert result is not None, "Should return vote result"

_run_test("governance_vote", test_gov_vote)

# ========== 6. Transfer Flow ==========
print("\n===== 6. TRANSFER FLOW =====")

def test_transfer():
    result = rpc("wallet_transfer", {"toAddress": "MAIN_TESTADDRESS", "amount": 0.01, "sector": "MAIN"})
    # Even if transfer fails due to insufficient funds, the RPC should work
    assert result is not None, "Should return transfer result"

_run_test("wallet_transfer", test_transfer)

# ========== 7. Exchange Flow ==========
print("\n===== 7. EXCHANGE (SECTOR SWAP) =====")

def test_exchange_rates():
    rates = rpc("sector_getExchangeRates")
    assert rates is not None, "Should return rates"

_run_test("sector_getExchangeRates", test_exchange_rates)

def test_exchange_request():
    result = rpc("sector_requestExchange", {"sector": "RTX4090", "amount": 1.0})
    assert result is not None, "Should return exchange result"

_run_test("sector_requestExchange", test_exchange_request)

def test_exchange_history():
    result = rpc("sector_getExchangeHistory", {"limit": 10})
    assert "exchanges" in result, "Should return exchange history"

_run_test("sector_getExchangeHistory", test_exchange_history)

# ========== 8. Task Flow ==========
print("\n===== 8. TASK FLOW =====")

task_id = None

def test_task_create():
    global task_id
    result = rpc("task_create", {
        "title": "E2E Test GPU Training",
        "description": "End-to-end test task",
        "task_type": "ai_training",
        "gpu_type": "RTX4090",
        "gpu_count": 1,
        "estimated_hours": 1,
        "max_price": 10.0
    })
    assert result is not None, "Should create task"
    task_id = result.get("taskId") or result.get("task_id")
    print(f"           Task ID: {task_id}")

_run_test("task_create", test_task_create)

def test_task_list():
    result = rpc("task_getList")
    assert "tasks" in result, "Should return task list"
    print(f"           Total tasks: {result.get('total', len(result['tasks']))}")

_run_test("task_getList", test_task_list)

def test_task_info():
    if not task_id:
        raise Exception("No task created")
    result = rpc("task_getInfo", {"task_id": task_id})
    assert result is not None, "Should return task info"

_run_test("task_getInfo", test_task_info)

# ========== 9. Orderbook Flow ==========
print("\n===== 9. ORDERBOOK FLOW =====")

def test_orderbook_submit_bid():
    result = rpc("orderbook_submitBid", {
        "gpuType": "RTX4090",
        "gpuCount": 1,
        "maxPricePerHour": 5.0,
        "duration": 3600
    })
    assert "orderId" in result, "Should return orderId"
    print(f"           Bid Order: {result['orderId']}")

_run_test("orderbook_submitBid", test_orderbook_submit_bid)

def test_orderbook_get():
    result = rpc("orderbook_getOrderBook", {"gpuType": "RTX4090"})
    assert result is not None, "Should return orderbook"

_run_test("orderbook_getOrderBook", test_orderbook_get)

def test_orderbook_market_price():
    result = rpc("orderbook_getMarketPrice", {"gpuType": "RTX4090"})
    assert result is not None, "Should return price"

_run_test("orderbook_getMarketPrice", test_orderbook_market_price)

def test_orderbook_my_orders():
    result = rpc("orderbook_getMyOrders")
    assert result is not None, "Should return orders"

_run_test("orderbook_getMyOrders", test_orderbook_my_orders)

# ========== 10. Privacy ==========
print("\n===== 10. PRIVACY =====")

def test_privacy_status():
    result = rpc("privacy_getStatus")
    assert "currentLevel" in result or "riskLevel" in result, "Should return privacy status"

_run_test("privacy_getStatus", test_privacy_status)

def test_privacy_rotate():
    result = rpc("privacy_rotateAddress")
    assert result is not None, "Should return rotation result"

_run_test("privacy_rotateAddress", test_privacy_rotate)

# ========== 11. Pricing & Billing ==========
print("\n===== 11. PRICING & BILLING =====")

def test_pricing_calculate():
    result = rpc("pricing_calculatePrice", {"gpuType": "RTX4090", "hours": 1, "gpuCount": 1})
    assert result is not None, "Should return price"

_run_test("pricing_calculatePrice", test_pricing_calculate)

def test_billing_rates():
    result = rpc("billing_getRates")
    assert result is not None, "Should return rates"

_run_test("billing_getRates", test_billing_rates)

# ========== 12. Node ==========
print("\n===== 12. NODE INFO =====")

def test_node_info():
    result = rpc("node_getInfo")
    assert result is not None, "Should return node info"

_run_test("node_getInfo", test_node_info)

def test_node_peers():
    result = rpc("node_getPeers")
    assert result is not None, "Should return peers"

_run_test("node_getPeers", test_node_peers)

# ========== Summary ==========
print(f"\n{'='*60}")
print(f"END-TO-END TEST RESULTS")
print(f"{'='*60}")
print(f"  PASSED: {passed}")
print(f"  FAILED: {failed}")
print(f"  TOTAL:  {passed + failed}")
print(f"{'='*60}")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"{failed} test(s) need attention")

