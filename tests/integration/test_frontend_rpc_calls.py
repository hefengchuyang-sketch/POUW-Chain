"""
Test frontend RPC calls with EXACT parameters the frontend sends.
Tests the methods listed in api/index.ts against the running backend on port 8545.
"""
import json
import requests
import sys
import traceback
from datetime import datetime
import rpc_auth_helper as auth_helper

RPC_URL = auth_helper.get_default_rpc_url("/rpc")
RESULTS = []
rpc_id = 1
_ACTIVE_API_KEY = None
_API_KEY_CANDIDATES = auth_helper.build_api_key_candidates()

def rpc_call(method, params=None):
    global _ACTIVE_API_KEY
    keys_to_try = auth_helper.build_key_try_list(_ACTIVE_API_KEY, _API_KEY_CANDIDATES)

    global rpc_id
    payload = {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": method,
        "params": params or {}
    }
    rpc_id += 1
    for api_key in keys_to_try:
        headers = auth_helper.build_rpc_headers(api_key=api_key, auth_user="test_wallet_address")
        try:
            resp = requests.post(RPC_URL, json=payload, headers=headers, timeout=10, verify=False)
            if resp.status_code == 403:
                continue
            data = resp.json()
            _ACTIVE_API_KEY = api_key
            return data
        except Exception as e:
            return {"error": {"code": -1, "message": str(e)}, "id": rpc_id - 1}
    return {"error": {"code": -32003, "message": "authentication failed"}, "id": rpc_id - 1}

def _test_method(name, method, params, notes=""):
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"  Method: {method}")
    print(f"  Params: {json.dumps(params, ensure_ascii=False)}")
    
    result = rpc_call(method, params)
    
    has_error = "error" in result and result["error"] is not None
    error_msg = ""
    if has_error:
        err = result["error"]
        error_msg = f"Code {err.get('code','?')}: {err.get('message','?')}"
    
    status = "FAIL" if has_error else "OK"
    result_data = result.get("result", None) if not has_error else None
    
    print(f"  Status: {status}")
    if has_error:
        print(f"  Error: {error_msg}")
    else:
        # Truncate result for display
        result_str = json.dumps(result_data, ensure_ascii=False, default=str)
        if len(result_str) > 300:
            result_str = result_str[:300] + "..."
        print(f"  Result: {result_str}")
    
    entry = {
        "name": name,
        "method": method,
        "params": params,
        "status": status,
        "error": error_msg if has_error else None,
        "result_snippet": result_data if not has_error else None,
        "notes": notes,
        "raw_response": result,
    }
    RESULTS.append(entry)
    return entry

def main():
    print("=" * 60)
    print(f"Frontend RPC Test - {datetime.now().isoformat()}")
    print(f"Backend URL: {RPC_URL}")
    print("=" * 60)
    
    # ============================================================
    # 1. wallet_transfer
    # Frontend: transferApi.send(toAddress, amount, sector, memo)
    # api/index.ts line ~192: rpcCall('wallet_transfer', {toAddress, amount, sector, memo})
    # ============================================================
    _test_method(
        "1. wallet_transfer",
        "wallet_transfer",
        {"toAddress": "MAIN_TEST", "amount": 1.0, "sector": "MAIN", "memo": ""},
        notes="Frontend sends: {toAddress, amount, sector, memo}"
    )
    
    # ============================================================
    # 2. governance_createProposal
    # Frontend: governanceApi.createProposal({title, description, category})
    # api/index.ts line ~1062: rpcCall('governance_createProposal', {...input})  
    # Governance.tsx line ~330: governanceApi.createProposal({title, description, category})
    # SUSPECTED BUG: uses datetime.datetime.now() but datetime not imported at top level
    # ============================================================
    _test_method(
        "2. governance_createProposal",
        "governance_createProposal",
        {"title": "Test", "description": "Test", "category": "parameter"},
        notes="Frontend sends: {title, description, category}. CHECK: datetime import issue?"
    )
    
    # ============================================================
    # 3. staking_stake
    # Frontend: stakingApi.stake(amount, sector, duration)
    # api/index.ts line ~1390: rpcCall('staking_stake', {amount, sector, duration})
    # ============================================================
    _test_method(
        "3. staking_stake",
        "staking_stake",
        {"amount": 100, "sector": "MAIN", "duration": 30},
        notes="Frontend sends: {amount, sector, duration}"
    )
    
    # ============================================================
    # 4. orderbook_submitBid
    # Frontend: orderbookApi.submitBid({gpuType, gpuCount, maxPricePerHour, duration, taskId?})
    # api/index.ts line ~1537: rpcCall('orderbook_submitBid', params)
    # Backend: _orderbook_submit_bid(userId, gpuType, maxPrice, requiredHours, ...)
    # SUSPECTED BUG: param name mismatch!
    #   Frontend sends: gpuCount, maxPricePerHour, duration
    #   Backend expects: userId (REQUIRED, no default!), maxPrice, requiredHours
    # ============================================================
    _test_method(
        "4. orderbook_submitBid (frontend params)",
        "orderbook_submitBid",
        {"gpuType": "RTX4090", "gpuCount": 1, "maxPricePerHour": 5.0, "duration": 1},
        notes="Frontend sends: {gpuType, gpuCount, maxPricePerHour, duration}. Backend expects: {userId, gpuType, maxPrice, requiredHours}. PARAM MISMATCH!"
    )
    
    # Also test with backend's expected params to confirm backend works when params are correct
    _test_method(
        "4b. orderbook_submitBid (backend params)",
        "orderbook_submitBid",
        {"userId": "test_user", "gpuType": "RTX4090", "maxPrice": 5.0, "requiredHours": 1.0},
        notes="Using backend's expected param names to verify handler works"
    )
    
    # ============================================================
    # 5. orderbook_cancelOrder
    # Frontend: orderbookApi.cancelOrder(orderId) 
    # api/index.ts line ~1544: rpcCall('orderbook_cancelOrder', {orderId})
    # Backend: _orderbook_cancel_order(orderId)
    # ============================================================
    _test_method(
        "5. orderbook_cancelOrder",
        "orderbook_cancelOrder",
        {"orderId": "test_order"},
        notes="Frontend sends: {orderId}"
    )
    
    # ============================================================
    # 6. settlement_getRecord
    # Frontend: settlementApi.getRecord(taskId)
    # api/index.ts line ~1765: rpcCall('settlement_getRecord', {taskId})
    # Backend: _settlement_get_record(taskId)
    # ============================================================
    _test_method(
        "6. settlement_getRecord",
        "settlement_getRecord",
        {"taskId": "test_task"},
        notes="Frontend sends: {taskId}"
    )
    
    # ============================================================
    # 7. settlement_getDetailedBill
    # Frontend: settlementApi.getDetailedBill(taskId)
    # api/index.ts line ~1779: rpcCall('settlement_getDetailedBill', {taskId})
    # Backend: _settlement_get_detailed_bill(taskId)
    # ============================================================
    _test_method(
        "7. settlement_getDetailedBill",
        "settlement_getDetailedBill",
        {"taskId": "test_task"},
        notes="Frontend sends: {taskId}"
    )
    
    # ============================================================
    # 8. encryptedTask_submit
    # Frontend: encryptedTaskApi.submit(taskId, userPrivateKey)
    # api/index.ts line ~880: rpcCall('encryptedTask_submit', {taskId, userPrivateKey})
    # Backend: _encrypted_task_submit(taskId, userPrivateKey="")
    # ============================================================
    _test_method(
        "8. encryptedTask_submit",
        "encryptedTask_submit",
        {"taskId": "test_task", "userPrivateKey": ""},
        notes="Frontend sends: {taskId, userPrivateKey}"
    )
    
    # ============================================================
    # 9. encryptedTask_getStatus
    # Frontend: encryptedTaskApi.getStatus(taskId)
    # api/index.ts line ~890: rpcCall('encryptedTask_getStatus', {taskId})
    # Backend: _encrypted_task_get_status(taskId)
    # ============================================================
    _test_method(
        "9. encryptedTask_getStatus",
        "encryptedTask_getStatus",
        {"taskId": "test_task"},
        notes="Frontend sends: {taskId}"
    )
    
    # ============================================================
    # 10. encryptedTask_getResult
    # Frontend: encryptedTaskApi.getResult(taskId, userPrivateKey)
    # api/index.ts line ~902: rpcCall('encryptedTask_getResult', {taskId, userPrivateKey})
    # Backend: _encrypted_task_get_result(taskId, userPrivateKey="")
    # ============================================================
    _test_method(
        "10. encryptedTask_getResult",
        "encryptedTask_getResult",
        {"taskId": "test_task", "userPrivateKey": ""},
        notes="Frontend sends: {taskId, userPrivateKey}"
    )
    
    # ============================================================
    # 11. encryptedTask_getBillingReport
    # Frontend: encryptedTaskApi.getBillingReport(taskId)
    # api/index.ts line ~915: rpcCall('encryptedTask_getBillingReport', {taskId})
    # Backend: _encrypted_task_billing(taskId)
    # ============================================================
    _test_method(
        "11. encryptedTask_getBillingReport",
        "encryptedTask_getBillingReport",
        {"taskId": "test_task"},
        notes="Frontend sends: {taskId}"
    )
    
    # ============================================================
    # 12. contrib_createProposal
    # Frontend Governance.tsx calls governanceApi.createProposal() -> governance_createProposal
    # NOT contrib_createProposal! But test it anyway as requested.
    # Backend: _contrib_create_proposal(proposer, proposalType, title, description, ...)
    # ============================================================
    _test_method(
        "12. contrib_createProposal (NOT called by frontend Governance.tsx)",
        "contrib_createProposal",
        {
            "proposer": "test_user",
            "proposalType": "weight_adjustment",
            "title": "Test Contrib Proposal",
            "description": "Testing",
            "targetParam": "compute_weight",
            "oldValue": 0.3,
            "newValue": 0.4,
        },
        notes="Governance.tsx actually calls governance_createProposal, NOT this method"
    )
    
    # ============================================================
    # 13. contrib_vote
    # Frontend ProposalDetail.tsx calls governanceApi.vote() -> governance_vote
    # NOT contrib_vote! But test it anyway as requested.
    # Backend: _contrib_vote(proposalId, voter, choice, currentBlock)
    # ============================================================
    _test_method(
        "13. contrib_vote (NOT called by frontend ProposalDetail.tsx)",
        "contrib_vote",
        {
            "proposalId": "test_proposal",
            "voter": "test_user",
            "choice": "support",
        },
        notes="ProposalDetail.tsx actually calls governance_vote, NOT this method"
    )
    
    # ============================================================
    # 14. dao_stake / dao_unstake / dao_createProposal / dao_vote
    # These are registered via DAOHandler (core/rpc_handlers/dao_handler.py)
    # Frontend does NOT call these - it uses staking_* and governance_*
    # ============================================================
    _test_method(
        "14a. dao_stake (NOT called by frontend)",
        "dao_stake",
        {"amount": 100},
        notes="Frontend uses staking_stake, not dao_stake"
    )
    
    _test_method(
        "14b. dao_unstake (NOT called by frontend)",
        "dao_unstake",
        {"amount": 50},
        notes="Frontend uses staking_unstake, not dao_unstake"
    )
    
    _test_method(
        "14c. dao_createProposal (NOT called by frontend)",
        "dao_createProposal",
        {"title": "Test DAO Proposal", "description": "Testing", "proposalType": "parameter"},
        notes="Frontend uses governance_createProposal, not dao_createProposal"
    )
    
    _test_method(
        "14d. dao_vote (NOT called by frontend)",
        "dao_vote",
        {"proposalId": "test_proposal", "vote": "for"},
        notes="Frontend uses governance_vote, not dao_vote"
    )
    
    # ============================================================
    # BONUS: governance_vote (actually called by frontend ProposalDetail.tsx)
    # Frontend: governanceApi.vote(proposalId, vote)
    # api/index.ts line ~1069: rpcCall('governance_vote', {proposal_id: proposalId, vote})
    # ============================================================
    # First create a proposal so we have something to vote on
    create_result = rpc_call("governance_createProposal", {"title": "VoteTest", "description": "Test", "category": "parameter"})
    prop_id = None
    if create_result.get("result") and create_result["result"].get("proposal"):
        prop_id = create_result["result"]["proposal"]["proposalId"]
    
    _test_method(
        "BONUS: governance_vote (actually called by ProposalDetail.tsx)",
        "governance_vote",
        {"proposal_id": prop_id or "test_proposal", "vote": "for"},
        notes="Frontend sends: {proposal_id, vote}"
    )
    
    # ============================================================
    # Generate Report
    # ============================================================
    print("\n\n" + "=" * 80)
    print("FINAL REPORT")
    print("=" * 80)
    
    report_lines = []
    report_lines.append(f"Frontend RPC Test Report")
    report_lines.append(f"Generated: {datetime.now().isoformat()}")
    report_lines.append(f"Backend: {RPC_URL}")
    report_lines.append("=" * 80)
    
    for r in RESULTS:
        report_lines.append("")
        report_lines.append(f"### {r['name']}")
        report_lines.append(f"  Method: {r['method']}")
        report_lines.append(f"  Params: {json.dumps(r['params'], ensure_ascii=False)}")
        report_lines.append(f"  Status: {r['status']}")
        if r['error']:
            report_lines.append(f"  Error:  {r['error']}")
        if r['result_snippet'] is not None:
            snippet = json.dumps(r['result_snippet'], ensure_ascii=False, default=str)
            if len(snippet) > 500:
                snippet = snippet[:500] + "..."
            report_lines.append(f"  Result: {snippet}")
        if r['notes']:
            report_lines.append(f"  Notes:  {r['notes']}")
        
        # Diagnosis
        diagnosis = ""
        if r['status'] == 'FAIL':
            err_msg = r['error'] or ""
            if "missing" in err_msg.lower() and "required" in err_msg.lower():
                diagnosis = "BUG: Backend handler requires params that frontend doesn't send (PARAM MISMATCH)"
            elif "datetime" in err_msg.lower() or "NameError" in err_msg.lower():
                diagnosis = "BUG: Backend handler has missing import (likely `import datetime`)"
            elif "not found" in err_msg.lower() or "Task not found" in err_msg.lower():
                diagnosis = "EXPECTED: Test data doesn't exist, but handler works correctly"
            elif "wallet" in err_msg.lower() or "connect" in err_msg.lower():
                diagnosis = "EXPECTED: No wallet connected in test, handler logic is correct"
            elif "method not found" in err_msg.lower():
                diagnosis = "BUG: Method not registered in RPC service"
            else:
                diagnosis = f"NEEDS INVESTIGATION: {err_msg}"
        else:
            # Check if the result indicates a logical issue
            result_str = json.dumps(r.get('result_snippet', {}), default=str)
            if r.get('result_snippet') and isinstance(r['result_snippet'], dict):
                if r['result_snippet'].get('success') == False:
                    diagnosis = f"RETURNED OK but success=False: {r['result_snippet'].get('error', r['result_snippet'].get('message', ''))}"
                else:
                    diagnosis = "OK - Handler works correctly"
            else:
                diagnosis = "OK - Handler returned data"
        
        report_lines.append(f"  Diagnosis: {diagnosis}")
    
    # Summary
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("SUMMARY")
    report_lines.append("=" * 80)
    
    ok_count = sum(1 for r in RESULTS if r['status'] == 'OK')
    fail_count = sum(1 for r in RESULTS if r['status'] == 'FAIL')
    report_lines.append(f"Total: {len(RESULTS)} | OK: {ok_count} | FAIL: {fail_count}")
    
    report_lines.append("")
    report_lines.append("KNOWN BUGS FOUND:")
    report_lines.append("-" * 40)
    
    # Bug 1: governance_createProposal datetime
    report_lines.append("")
    report_lines.append("BUG 1: governance_createProposal - missing `import datetime`")
    report_lines.append("  File: core/rpc_service.py, line ~3991")
    report_lines.append("  The handler uses `datetime.datetime.now()` and `datetime.timedelta()`")
    report_lines.append("  but `datetime` is NOT imported at module level (only inside other functions).")
    report_lines.append("  This will cause NameError when called.")
    gov_result = next((r for r in RESULTS if r['method'] == 'governance_createProposal'), None)
    if gov_result:
        report_lines.append(f"  Test result: {gov_result['status']} - {gov_result.get('error', 'no error')}")
    
    # Bug 2: orderbook_submitBid param mismatch
    report_lines.append("")
    report_lines.append("BUG 2: orderbook_submitBid - frontend/backend parameter name MISMATCH")
    report_lines.append("  Frontend sends: {gpuType, gpuCount, maxPricePerHour, duration}")
    report_lines.append("  Backend expects: {userId (REQUIRED!), gpuType, maxPrice, requiredHours}")
    report_lines.append("  Mismatches:")
    report_lines.append("    - userId: frontend doesn't send it, backend requires it (no default)")
    report_lines.append("    - maxPricePerHour vs maxPrice: different param names")
    report_lines.append("    - duration vs requiredHours: different param names")
    report_lines.append("    - gpuCount: frontend sends it, backend ignores it")
    ob_result = next((r for r in RESULTS if "frontend params" in r['name'] and "orderbook" in r['name']), None)
    if ob_result:
        report_lines.append(f"  Test result: {ob_result['status']} - {ob_result.get('error', 'no error')}")
    
    # Frontend mapping info
    report_lines.append("")
    report_lines.append("FRONTEND CALL MAPPING:")
    report_lines.append("-" * 40)
    report_lines.append("Governance.tsx CreateProposalModal -> governanceApi.createProposal()")
    report_lines.append("  -> rpcCall('governance_createProposal', {title, description, category})")
    report_lines.append("  Does NOT call contrib_createProposal")
    report_lines.append("")
    report_lines.append("ProposalDetail.tsx handleVote -> governanceApi.vote(proposalId, selectedVote)")
    report_lines.append("  -> rpcCall('governance_vote', {proposal_id, vote})")
    report_lines.append("  Does NOT call contrib_vote")
    report_lines.append("")
    report_lines.append("Frontend does NOT call dao_stake/dao_unstake/dao_createProposal/dao_vote")
    report_lines.append("  It uses staking_stake, staking_unstake, governance_createProposal, governance_vote")
    
    report_text = "\n".join(report_lines)
    print(report_text)
    
    # Save to file
    with open(r"c:\Users\17006\Desktop\maincoin\test_frontend_rpc.txt", "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(f"\n\nResults saved to test_frontend_rpc.txt")

if __name__ == "__main__":
    main()
