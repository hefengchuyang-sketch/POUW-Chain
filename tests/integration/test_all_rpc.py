#!/usr/bin/env python3
"""
Comprehensive RPC Method Test Script
Tests ALL registered RPC methods on http://127.0.0.1:8545
"""

import json
import urllib.request
import urllib.error
import ssl
import time
import sys
from datetime import datetime

RPC_URL = "https://127.0.0.1:8545"
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
WALLET_ADDRESS = "MAIN_OSFMLGDAAZEXEENLLTUBER6W4FHI3PNJ"
OUTPUT_FILE = r"c:\Users\17006\Desktop\maincoin\test_rpc_results.txt"

request_id = 0

def rpc_call(method, params=None):
    """Make a JSON-RPC call and return (success, result_or_error, elapsed_ms)"""
    global request_id
    request_id += 1
    
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params is not None else {},
        "id": request_id
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            body = resp.read().decode("utf-8")
            elapsed = (time.time() - start) * 1000
            result = json.loads(body)
            if "error" in result and result["error"]:
                return False, result["error"], elapsed
            return True, result.get("result"), elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        try:
            body = e.read().decode("utf-8")
            err = json.loads(body)
            return False, err.get("error", body), elapsed
        except:
            return False, f"HTTP {e.code}: {e.reason}", elapsed
    except urllib.error.URLError as e:
        elapsed = (time.time() - start) * 1000
        return False, f"URLError: {e.reason}", elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return False, f"Exception: {str(e)}", elapsed


# ============================================================
# Define ALL RPC methods with appropriate test params
# ============================================================

ALL_METHODS = [
    # === Dashboard ===
    ("dashboard_getStats", {}),
    ("dashboard_getRecentTasks", {}),
    ("dashboard_getRecentProposals", {}),
    ("dashboard_getBlockChart", {}),
    ("dashboard_getRewardTrend", {}),
    
    # === Miner ===
    ("miner_getList", {}),
    ("miner_getInfo", {"miner_id": "test_miner_001"}),
    
    # === Stats ===
    ("stats_getNetwork", {}),
    ("stats_getBlocks", {}),
    ("stats_getTasks", {}),
    
    # === Task ===
    ("task_getList", {}),
    ("task_getInfo", {"task_id": "test_task_001"}),
    ("task_create", {"name": "test_task", "type": "compute", "requirements": {"gpu": "any"}}),
    ("task_cancel", {"task_id": "nonexistent_task"}),
    ("task_getFiles", {"task_id": "test_task_001"}),
    ("task_getLogs", {"task_id": "test_task_001"}),
    ("task_getOutputs", {"task_id": "test_task_001"}),
    ("task_getRuntimeStatus", {"task_id": "test_task_001"}),
    
    # === Scheduler ===
    ("scheduler_registerMiner", {"miner_id": "test_miner", "capabilities": {"gpu": "RTX4090"}}),
    ("scheduler_heartbeat", {"miner_id": "test_miner"}),
    ("scheduler_submitResult", {"task_id": "test_task", "miner_id": "test_miner", "result": {}}),
    ("scheduler_getTask", {"task_id": "test_task"}),
    ("scheduler_rateMiner", {"miner_id": "test_miner", "task_id": "test_task", "rating": 5}),
    ("scheduler_getBlindBatch", {"miner_id": "test_miner"}),
    ("scheduler_submitBlindBatch", {"miner_id": "test_miner", "batch_id": "test_batch", "results": []}),
    ("scheduler_getMinerTrust", {"miner_id": "test_miner"}),
    
    # === Transaction ===
    ("tx_send", {"from": WALLET_ADDRESS, "to": "MAIN_TEST_RECIPIENT", "amount": "0.001", "dry_run": True}),
    ("tx_get", {"txid": "0000000000000000000000000000000000000000000000000000000000000000"}),
    ("tx_getByAddress", {"address": WALLET_ADDRESS}),
    
    # === Mempool ===
    ("mempool_getInfo", {}),
    ("mempool_getPending", {}),
    
    # === Block ===
    ("block_getLatest", {}),
    ("block_getByHeight", {"height": 0}),
    ("block_getByHash", {"hash": "0000000000000000000000000000000000000000000000000000000000000000"}),
    
    # === Chain ===
    ("chain_getHeight", {}),
    ("chain_getInfo", {}),
    
    # === Account ===
    ("account_getBalance", {"address": WALLET_ADDRESS}),
    ("account_getUTXOs", {"address": WALLET_ADDRESS}),
    ("account_traceUTXO", {"address": WALLET_ADDRESS, "txid": "test", "vout": 0}),
    ("account_getNonce", {"address": WALLET_ADDRESS}),
    ("account_getTransactions", {"address": WALLET_ADDRESS}),
    ("account_getSubAddresses", {"address": WALLET_ADDRESS}),
    ("account_createSubAddress", {"address": WALLET_ADDRESS, "label": "test_sub"}),
    
    # === Wallet (from wallet_handler.py) ===
    ("wallet_getInfo", {}),
    ("wallet_lock", {}),
    ("wallet_create", {"password": "test_password_12345"}),  # test only, shouldn't overwrite existing
    ("wallet_unlock", {"password": "test_password_12345"}),
    ("wallet_exportKeystore", {"password": "test_password_12345"}),
    ("wallet_importKeystore", {"keystore": "{}", "password": "test_password_12345"}),
    ("wallet_getBalance", {"address": WALLET_ADDRESS}),
    ("wallet_getTransactions", {"address": WALLET_ADDRESS}),
    
    # === Miner Management ===
    ("miner_register", {"address": WALLET_ADDRESS, "gpu_model": "RTX4090", "vram": 24}),
    ("miner_updateProfile", {"address": WALLET_ADDRESS, "gpu_model": "RTX4090"}),
    
    # === Mining ===
    ("mining_getStatus", {}),
    ("mining_start", {}),
    ("mining_stop", {}),
    ("mining_getRewards", {}),
    ("mining_setMode", {"mode": "mine_only"}),
    ("mining_getScore", {"address": WALLET_ADDRESS}),
    
    # === Sector ===
    ("sector_getExchangeRates", {}),
    ("sector_requestExchange", {"from_sector": "AI", "amount": "1.0", "address": WALLET_ADDRESS}),
    ("sector_getExchangeHistory", {"address": WALLET_ADDRESS}),
    ("sector_cancelExchange", {"exchange_id": "test_exchange_001"}),
    
    # === Privacy ===
    ("privacy_getStatus", {}),
    ("privacy_rotateAddress", {"address": WALLET_ADDRESS}),
    
    # === Node ===
    ("node_getInfo", {}),
    ("node_getPeers", {}),
    ("node_isSyncing", {}),
    
    # === Compute Market ===
    ("compute_submitOrder", {"type": "buy", "gpu_type": "RTX4090", "hours": 1, "price": "10.0"}),
    ("compute_getOrder", {"order_id": "test_order_001"}),
    ("compute_getMarket", {}),
    ("compute_acceptOrder", {"order_id": "test_order_001", "miner_id": "test_miner"}),
    ("compute_cancelOrder", {"order_id": "test_order_001"}),
    
    # === Witness ===
    ("witness_request", {"tx_hash": "test_hash", "miner_id": "test_miner"}),
    ("witness_getStatus", {"tx_hash": "test_hash"}),
    
    # === Governance ===
    ("governance_vote", {"proposal_id": "test_proposal", "vote": "yes", "address": WALLET_ADDRESS}),
    ("governance_getProposals", {}),
    ("governance_getProposal", {"proposal_id": "test_proposal"}),
    ("governance_createProposal", {"title": "Test Proposal", "description": "Test", "type": "parameter_change"}),
    
    # === Contribution Governance ===
    ("contrib_createProposal", {"title": "Test", "description": "Test contrib proposal", "type": "weight_change"}),
    ("contrib_vote", {"proposal_id": "test_proposal", "vote": "yes"}),
    ("contrib_getProposals", {}),
    ("contrib_getProposal", {"proposal_id": "test_proposal"}),
    ("contrib_getVoterPower", {"address": WALLET_ADDRESS}),
    ("contrib_simulateVote", {"proposal_id": "test_proposal", "vote": "yes", "address": WALLET_ADDRESS}),
    ("contrib_stake", {"address": WALLET_ADDRESS, "amount": "100"}),
    ("contrib_unstake", {"address": WALLET_ADDRESS, "amount": "50"}),
    ("contrib_finalizeProposal", {"proposal_id": "test_proposal"}),
    ("contrib_executeProposal", {"proposal_id": "test_proposal"}),
    ("contrib_getStats", {}),
    ("contrib_checkProposerEligibility", {"address": WALLET_ADDRESS}),
    ("contrib_getProposalTimeRemaining", {"proposal_id": "test_proposal"}),
    ("contrib_checkExpiredProposals", {}),
    ("contrib_getPassRequirements", {"proposal_id": "test_proposal"}),
    
    # === Encrypted Task ===
    ("encryptedTask_create", {"task_type": "inference", "model": "test_model"}),
    ("encryptedTask_submit", {"task_id": "test_enc_task"}),
    ("encryptedTask_getStatus", {"task_id": "test_enc_task"}),
    ("encryptedTask_getResult", {"task_id": "test_enc_task"}),
    ("encryptedTask_process", {"task_id": "test_enc_task", "miner_id": "test_miner"}),
    ("encryptedTask_getBillingReport", {"task_id": "test_enc_task"}),
    ("encryptedTask_generateKeypair", {}),
    ("encryptedTask_registerMiner", {"miner_id": "test_miner", "public_key": "test_pubkey"}),
    
    # === Pricing ===
    ("pricing_getBaseRates", {}),
    ("pricing_getRealTimePrice", {"gpu_type": "RTX4090"}),
    ("pricing_calculatePrice", {"gpu_type": "RTX4090", "hours": 1}),
    ("pricing_getMarketState", {}),
    ("pricing_getStrategies", {}),
    ("pricing_getTimeSlotSchedule", {}),
    ("pricing_getPriceForecast", {"gpu_type": "RTX4090"}),
    
    # === Budget ===
    ("budget_deposit", {"address": WALLET_ADDRESS, "amount": "100"}),
    ("budget_getBalance", {"address": WALLET_ADDRESS}),
    ("budget_lockForTask", {"address": WALLET_ADDRESS, "task_id": "test_task", "amount": "10"}),
    ("budget_getLockInfo", {"address": WALLET_ADDRESS, "task_id": "test_task"}),
    
    # === Settlement ===
    ("settlement_settleTask", {"task_id": "test_task"}),
    ("settlement_getRecord", {"task_id": "test_task"}),
    ("settlement_getDetailedBill", {"task_id": "test_task"}),
    ("settlement_getMinerEarnings", {"miner_id": "test_miner"}),
    
    # === Market Monitor ===
    ("market_getDashboard", {}),
    ("market_getSupplyDemandCurve", {}),
    ("market_getQueueStatus", {}),
    ("market_updateSupplyDemand", {"gpu_type": "RTX4090", "available": 10, "demand": 5}),
    
    # === Queue ===
    ("queue_enqueue", {"task_id": "test_task", "priority": 1}),
    ("queue_getPosition", {"task_id": "test_task"}),
    ("queue_getEstimatedWaitTime", {"task_id": "test_task"}),
    ("queue_getStats", {}),
    
    # === RPC Meta ===
    ("rpc_listMethods", {}),
    
    # === Blockchain Query ===
    ("blockchain_getHeight", {}),
    ("blockchain_getBlock", {"height": 0}),
    ("blockchain_getLatestBlocks", {"count": 5}),
    
    # === Order ===
    ("order_getList", {}),
    ("order_getDetail", {"order_id": "test_order"}),
    
    # === Staking ===
    ("staking_getRecords", {"address": WALLET_ADDRESS}),
    ("staking_stake", {"address": WALLET_ADDRESS, "amount": "100"}),
    ("staking_unstake", {"address": WALLET_ADDRESS, "amount": "50"}),
    
    # === TEE ===
    ("tee_registerNode", {"node_id": "test_tee_node", "enclave_type": "SGX"}),
    ("tee_submitAttestation", {"node_id": "test_tee_node", "report": "test_report"}),
    ("tee_getNodeInfo", {"node_id": "test_tee_node"}),
    ("tee_listNodes", {}),
    ("tee_createConfidentialTask", {"task_type": "inference", "model": "test"}),
    ("tee_getTaskResult", {"task_id": "test_tee_task"}),
    ("tee_getPricing", {}),
    
    # === Orderbook ===
    ("orderbook_submitAsk", {"gpu_type": "RTX4090", "price": "5.0", "hours": 1}),
    ("orderbook_submitBid", {"gpu_type": "RTX4090", "price": "5.0", "hours": 1}),
    ("orderbook_cancelOrder", {"order_id": "test_order"}),
    ("orderbook_getOrderBook", {}),
    ("orderbook_getMarketPrice", {"gpu_type": "RTX4090"}),
    ("orderbook_getMyOrders", {"address": WALLET_ADDRESS}),
    ("orderbook_getMatches", {}),
    
    # === Futures ===
    ("futures_createContract", {"gpu_type": "RTX4090", "duration": 30, "price": "100"}),
    ("futures_depositMargin", {"contract_id": "test_contract", "amount": "50"}),
    ("futures_getContract", {"contract_id": "test_contract"}),
    ("futures_listContracts", {}),
    ("futures_cancelContract", {"contract_id": "test_contract"}),
    ("futures_settleContract", {"contract_id": "test_contract"}),
    ("futures_getPricingCurve", {"gpu_type": "RTX4090"}),
    
    # === Billing ===
    ("billing_recordUsage", {"task_id": "test_task", "resource": "gpu", "usage": 100}),
    ("billing_calculateCost", {"resource": "gpu", "hours": 1, "gpu_type": "RTX4090"}),
    ("billing_getDetailedBilling", {"task_id": "test_task"}),
    ("billing_getRates", {}),
    ("billing_estimateTask", {"gpu_type": "RTX4090", "hours": 1}),
    
    # === Data Lifecycle ===
    ("dataLifecycle_registerAsset", {"name": "test_data", "size": 1024, "type": "model"}),
    ("dataLifecycle_requestDestruction", {"asset_id": "test_asset"}),
    ("dataLifecycle_getDestructionProof", {"asset_id": "test_asset"}),
    ("dataLifecycle_listAssets", {"address": WALLET_ADDRESS}),
    
    # === Ephemeral Key ===
    ("ephemeralKey_createSession", {"address": WALLET_ADDRESS}),
    ("ephemeralKey_getSessionKey", {"session_id": "test_session"}),
    ("ephemeralKey_rotateKey", {"session_id": "test_session"}),
    
    # === P2P Direct ===
    ("p2p_setupConnection", {"peer_id": "test_peer"}),
    ("p2p_createOffer", {"peer_id": "test_peer"}),
    ("p2p_createAnswer", {"peer_id": "test_peer", "offer": "test_offer"}),
    ("p2p_getConnectionStatus", {"connection_id": "test_conn"}),
    ("p2p_listConnections", {}),
    ("p2p_closeConnection", {"connection_id": "test_conn"}),
    ("p2p_getNATInfo", {}),
    
    # === DID ===
    ("did_create", {"address": WALLET_ADDRESS}),
    ("did_resolve", {"did": "did:pouw:test"}),
    ("did_bindWallet", {"did": "did:pouw:test", "address": WALLET_ADDRESS}),
    ("did_issueCredential", {"did": "did:pouw:test", "type": "miner", "claims": {}}),
    ("did_verifyCredential", {"credential_id": "test_cred"}),
    ("did_getReputation", {"did": "did:pouw:test"}),
    ("did_getReputationTier", {"did": "did:pouw:test"}),
    ("did_checkSybilRisk", {"did": "did:pouw:test"}),
    
    # === DAO (from dao_handler.py) ===
    ("dao_stake", {"address": WALLET_ADDRESS, "amount": "100"}),
    ("dao_unstake", {"address": WALLET_ADDRESS, "amount": "50"}),
    ("dao_createProposal", {"title": "Test DAO Proposal", "description": "Test", "type": "funding"}),
    ("dao_vote", {"proposal_id": "test_dao_proposal", "vote": "yes", "address": WALLET_ADDRESS}),
    ("dao_executeProposal", {"proposal_id": "test_dao_proposal"}),
    ("dao_getProposalStatus", {"proposal_id": "test_dao_proposal"}),
    ("dao_listProposals", {}),
    ("dao_getTreasury", {}),
    ("dao_getTreasuryConfig", {}),
    ("dao_setTreasuryRate", {"rate": "0.05"}),
    ("dao_getTreasuryReport", {}),
    ("dao_createTreasuryProposal", {"title": "Test Treasury", "amount": "1000", "recipient": WALLET_ADDRESS}),
    ("dao_treasuryWithdraw", {"amount": "100", "recipient": WALLET_ADDRESS}),
    ("dao_getGovernanceParams", {}),
    ("dao_getStakingInfo", {"address": WALLET_ADDRESS}),
    
    # === Message Queue ===
    ("mq_publish", {"topic": "test_topic", "message": "hello"}),
    ("mq_subscribe", {"topic": "test_topic"}),
    ("mq_getQueueStats", {}),
    ("mq_emitEvent", {"event": "test_event", "data": {"key": "value"}}),
    
    # === Data Redundancy ===
    ("redundancy_storeData", {"data": "test_data", "replicas": 3}),
    ("redundancy_retrieveData", {"data_id": "test_data_001"}),
    ("redundancy_createBackup", {}),
    ("redundancy_getStats", {}),
    
    # === Load Testing ===
    ("loadTest_runScenario", {"scenario": "basic", "concurrent": 10}),
    ("loadTest_getResults", {"test_id": "latest"}),
    ("loadTest_getMetrics", {}),
    
    # === ZK ===
    ("zk_generateProof", {"data": "test_data", "type": "balance"}),
    ("zk_verifyProof", {"proof": "test_proof", "public_input": "test_input"}),
    ("zk_getProofStats", {}),
    
    # === Security ===
    ("security_checkRequest", {"request_type": "transfer", "address": WALLET_ADDRESS}),
    ("security_reportThreat", {"type": "suspicious_transfer", "details": "test"}),
    ("security_getStats", {}),
    ("security_checkSybil", {"address": WALLET_ADDRESS}),
    
    # === Audit ===
    ("audit_submitContract", {"code": "print('hello')", "language": "python"}),
    ("audit_getReport", {"audit_id": "test_audit"}),
    ("audit_autoSettle", {"task_id": "test_task"}),
    ("audit_getSettlementHistory", {"address": WALLET_ADDRESS}),
    
    # === Revenue ===
    ("revenue_recordEarning", {"miner_id": "test_miner", "amount": "10.0", "type": "mining"}),
    ("revenue_getMinerStats", {"miner_id": "test_miner"}),
    ("revenue_getLeaderboard", {}),
    ("revenue_getForecast", {"miner_id": "test_miner"}),
    
    # === Monitor ===
    ("monitor_getHealth", {}),
    ("monitor_getDashboard", {}),
    ("monitor_getAlerts", {}),
    ("monitor_recordMetric", {"name": "test_metric", "value": 42}),
    
    # === SDK ===
    ("sdk_getOpenAPISpec", {}),
    ("sdk_generateSDK", {"language": "python"}),
    ("sdk_getEndpoints", {}),
    ("sdk_getExamples", {"language": "python"}),
    
    # === Frontend Aliases ===
    ("status", {}),
    ("miner_getSectorList", {}),
    ("miner_getGpuList", {}),
    ("miner_getEarnings", {"miner_id": WALLET_ADDRESS}),
    ("market_getComputeOrders", {}),
    ("market_createOrder", {"type": "buy", "gpu_type": "RTX4090", "hours": 1, "price": "10.0"}),
    ("blockchain_getBlocks", {"count": 5}),
    ("blockchain_getTransaction", {"txid": "test_txid"}),
    ("network_getStatus", {}),
    ("network_getPeerList", {}),
    ("network_getRecentTransactions", {}),
    ("billing_getDetailed", {"task_id": "test_task"}),
    ("dashboard_getSummary", {}),
    ("dashboard_getSectorDistribution", {}),
    ("exchange_getOrderBook", {}),
    ("exchange_getMarketInfo", {"gpu_type": "RTX4090"}),
    ("exchange_createOrder", {"type": "buy", "gpu_type": "RTX4090", "price": "5.0", "amount": 1}),
    ("p2p_getStatus", {}),
    
    # === P2P Task ===
    ("p2pTask_create", {"name": "test_p2p_task", "type": "compute"}),
    ("p2pTask_distribute", {"task_id": "test_p2p_task"}),
    ("p2pTask_getStatus", {"task_id": "test_p2p_task"}),
    ("p2pTask_getList", {}),
    ("p2pTask_getStats", {}),
    ("p2pTask_cancel", {"task_id": "test_p2p_task"}),
    ("p2pTask_registerMiner", {"miner_id": "test_miner", "capabilities": {"gpu": "RTX4090"}}),
    ("p2pTask_getMiners", {}),
    ("p2pTask_getResult", {"task_id": "test_p2p_task"}),
    
    # === Data Lifecycle Alias ===
    ("dataLifecycle_getStatus", {}),
    
    # === wallet_transfer (test with dry_run / invalid to avoid real transfer) ===
    ("wallet_transfer", {"to": "MAIN_TEST_INVALID_ADDR", "amount": "0.001"}),
    
    # === wallet_import (test only, with dummy key) ===
    ("wallet_import", {"private_key": "0000000000000000000000000000000000000000000000000000000000000001"}),
]

def main():
    results = []
    success_count = 0
    fail_count = 0
    error_count = 0
    
    print(f"=" * 80)
    print(f"POUW RPC Comprehensive Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {RPC_URL}")
    print(f"Wallet: {WALLET_ADDRESS}")
    print(f"Total methods to test: {len(ALL_METHODS)}")
    print(f"=" * 80)
    
    # First, check server is reachable
    try:
        ok, res, ms = rpc_call("rpc_listMethods")
        if ok:
            print(f"\n[OK] Server reachable. rpc_listMethods returned {len(res) if isinstance(res, (list, dict)) else 'data'}")
            if isinstance(res, dict) and 'methods' in res:
                registered = res['methods']
                print(f"  Registered methods on server: {len(registered)}")
            elif isinstance(res, list):
                print(f"  Registered methods on server: {len(res)}")
        else:
            print(f"\n[WARN] Server reachable but rpc_listMethods returned error: {res}")
    except Exception as e:
        print(f"\n[FATAL] Cannot reach server at {RPC_URL}: {e}")
        sys.exit(1)
    
    print(f"\nStarting tests...\n")
    
    for method, params in ALL_METHODS:
        ok, result, elapsed_ms = rpc_call(method, params)
        
        status = "OK" if ok else "FAIL"
        if ok:
            success_count += 1
            # Truncate result for display
            result_str = json.dumps(result, ensure_ascii=False, default=str)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            detail = result_str
        else:
            fail_count += 1
            if isinstance(result, dict):
                detail = f"code={result.get('code','?')} msg={result.get('message','?')}"
                if 'data' in result:
                    d = str(result['data'])
                    if len(d) > 100:
                        d = d[:100] + "..."
                    detail += f" data={d}"
            else:
                detail = str(result)
                if len(detail) > 300:
                    detail = detail[:300] + "..."
        
        line = f"[{status:4s}] {method:45s} ({elapsed_ms:7.1f}ms) | {detail}"
        results.append(line)
        
        # Print progress
        idx = len(results)
        symbol = "+" if ok else "X"
        print(f"  [{symbol}] {idx:3d}/{len(ALL_METHODS)} {method:45s} {elapsed_ms:7.1f}ms {'OK' if ok else 'FAIL'}")
    
    # Summary
    total = len(ALL_METHODS)
    summary_lines = [
        "",
        "=" * 80,
        f"POUW RPC Test Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Server: {RPC_URL}",
        f"Wallet: {WALLET_ADDRESS}",
        "=" * 80,
        "",
        f"SUMMARY: {total} methods tested, {success_count} OK, {fail_count} FAIL",
        f"  Success rate: {success_count/total*100:.1f}%",
        "",
        "-" * 80,
        "DETAILED RESULTS:",
        "-" * 80,
    ]
    
    # Group by category
    for line in results:
        summary_lines.append(line)
    
    # Lists of OK and FAIL methods
    summary_lines.append("")
    summary_lines.append("-" * 80)
    summary_lines.append("SUCCEEDED METHODS:")
    summary_lines.append("-" * 80)
    for i, (method, _) in enumerate(ALL_METHODS):
        if results[i].startswith("[OK"):
            summary_lines.append(f"  + {method}")
    
    summary_lines.append("")
    summary_lines.append("-" * 80)
    summary_lines.append("FAILED METHODS:")
    summary_lines.append("-" * 80)
    for i, (method, _) in enumerate(ALL_METHODS):
        if results[i].startswith("[FAIL"):
            # Extract error detail
            detail = results[i].split(" | ", 1)[1] if " | " in results[i] else ""
            summary_lines.append(f"  X {method}")
            summary_lines.append(f"    -> {detail}")
    
    summary_lines.append("")
    summary_lines.append("=" * 80)
    summary_lines.append(f"END OF REPORT - {total} methods, {success_count} OK, {fail_count} FAIL")
    summary_lines.append("=" * 80)
    
    report = "\n".join(summary_lines)
    
    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n{'=' * 60}")
    print(f"DONE: {total} methods tested, {success_count} OK, {fail_count} FAIL")
    print(f"Success rate: {success_count/total*100:.1f}%")
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
