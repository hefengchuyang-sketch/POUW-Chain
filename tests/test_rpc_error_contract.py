from core.rpc_service import NodeRPCService


class _BrokenEstimator:
    def estimate_task_cost(self, **kwargs):
        raise RuntimeError("boom")


def test_orderbook_submit_ask_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_orderbook_system", lambda: {"matching_engine": object()})

    result = service._orderbook_submit_ask(minerId="m1", gpuType="RTX4090", price=1.2, availableHours=2)

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "orderbook_submitAsk"
    assert result["status"] == "failed"
    assert result["matched"] is False


def test_orderbook_get_orderbook_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_orderbook_system", lambda: {"matching_engine": object()})

    result = service._orderbook_get_orderbook(gpuType="H100")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "orderbook_getOrderbook"
    assert result["asks"] == []
    assert result["bids"] == []


def test_futures_list_contracts_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()

    class _BrokenContractManager:
        @property
        def contracts(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(service, "_get_futures_system", lambda: {"contract_manager": _BrokenContractManager()})

    result = service._futures_list_contracts()

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "futures_listContracts"
    assert result["contracts"] == []
    assert result["total"] == 0


def test_billing_estimate_task_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_billing_system", lambda: {"estimator": _BrokenEstimator()})

    result = service._billing_estimate_task(gpuType="RTX4090", durationHours=1)

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "billing_estimateTask"
    assert result["estimatedCost"] == 0


def test_tee_get_pricing_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "_get_tee_system", _boom)

    result = service._tee_get_pricing(gpuType="H100")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "tee_getPricing"
    assert result["gpuType"] == "H100"


def test_tee_list_nodes_keeps_list_contract_on_error(monkeypatch):
    service = NodeRPCService()

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "_get_tee_system", _boom)

    result = service._tee_list_nodes()
    assert result == []


def test_orderbook_get_matches_keeps_list_contract_on_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_orderbook_system", lambda: {"matching_engine": object()})

    result = service._orderbook_get_matches(gpuType="RTX4090")
    assert result == []


def test_sbox_get_downgrade_audit_returns_consistent_internal_error():
    service = NodeRPCService()

    result = service._sbox_get_downgrade_audit(limit="invalid")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "sbox_getDowngradeAudit"
    assert result["status"] == "failed"
    assert result["events"] == []


def test_dao_get_treasury_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_dao_system", lambda: {"treasury": object()})

    result = service._dao_get_treasury()

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "dao_getTreasury"
    assert result["recentTransactions"] == []


def test_dao_get_governance_params_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_dao_system", lambda: {"governance": object()})

    result = service._dao_get_governance_params()

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "dao_getGovernanceParams"
    assert result["quorumPercentage"] == 10


def test_dao_get_staking_info_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_dao_system", lambda: {"governance": object()})

    result = service._dao_get_staking_info(userId="u1")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "dao_getStakingInfo"
    assert result["userId"] == "u1"
    assert result["stakedAmount"] == 0


def test_order_get_detail_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()

    import sqlite3

    monkeypatch.setattr("core.rpc_service.os.path.exists", lambda _: True)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(sqlite3, "connect", _boom)

    result = service._order_get_detail(orderId="o1")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "order_getDetail"
    assert result["id"] == "o1"


def test_load_test_get_results_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_load_test_engine", lambda: object())

    result = service._load_test_get_results(testId="t1")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "load_test_getResults"
    assert result["testId"] == "t1"
    assert result["status"] == "error"


def test_security_check_sybil_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "_get_attack_prevention", _boom)

    result = service._security_check_sybil(address="a1")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "security_checkSybil"
    assert result["isSybil"] is False


def test_audit_get_report_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_contract_audit", lambda: object())

    result = service._audit_get_report(auditId="a1")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "audit_getReport"
    assert result["auditId"] == "a1"
    assert result["status"] == "error"


def test_audit_get_settlement_history_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_contract_audit", lambda: object())

    result = service._audit_get_settlement_history(userId="u1")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "audit_getSettlementHistory"
    assert result["settlements"] == []


def test_revenue_get_miner_stats_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_revenue_tracking", lambda: object())

    result = service._revenue_get_miner_stats(minerId="m1")

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "revenue_getMinerStats"
    assert result["minerId"] == "m1"
    assert result["totalEarnings"] == 0


def test_revenue_get_forecast_returns_consistent_internal_error(monkeypatch):
    service = NodeRPCService()
    monkeypatch.setattr(service, "_get_revenue_tracking", lambda: object())

    result = service._revenue_get_forecast(minerId="m1", days=7)

    assert result["success"] is False
    assert result["error"] == "internal_error"
    assert result["method"] == "revenue_getForecast"
    assert result["minerId"] == "m1"
    assert result["predictedEarnings"] == 0


def test_frontend_sector_list_keeps_fallback_contract(monkeypatch):
    service = NodeRPCService()

    # Force import failure in try branch to exercise fallback path.
    original_import = __import__

    def _mocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.endswith("sector_coin"):
            raise RuntimeError("boom")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _mocked_import)

    result = service._frontend_miner_get_sector_list()

    assert isinstance(result.get("sectors"), list)
    assert result.get("total") == 5


def test_frontend_data_lifecycle_get_status_keeps_fallback_contract(monkeypatch):
    service = NodeRPCService()

    original_import = __import__

    def _mocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.endswith("data_lifecycle"):
            raise RuntimeError("boom")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _mocked_import)

    result = service._frontend_data_lifecycle_get_status(dataId="d1")

    assert result["dataId"] == "d1"
    assert result["status"] == "not_found"
