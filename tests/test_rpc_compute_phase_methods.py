from types import SimpleNamespace

import pytest

from core.rpc.models import RPCError
from core.rpc_service import NodeRPCService


def _bare_service():
    svc = NodeRPCService.__new__(NodeRPCService)
    svc.compute_market = None
    svc.market_orders = {}
    svc.miner_address = None
    svc.node_id = "test-node"
    return svc


def test_rpc_registry_includes_compute_phase_methods():
    svc = NodeRPCService()
    assert svc.registry.has("compute_commitResult")
    assert svc.registry.has("compute_revealResult")
    assert svc.registry.has("compute_getOrderEvents")


def test_compute_commit_result_success_and_unavailable():
    svc = _bare_service()

    res_unavailable = svc._compute_commit_result("o1", "m1", "h1")
    assert res_unavailable["status"] == "failed"
    assert res_unavailable["message"] == "compute_market_commit_unavailable"

    svc.compute_market = SimpleNamespace(
        commit_result=lambda order_id, miner_id, commit_hash: (True, "ok")
    )
    res_ok = svc._compute_commit_result("o1", "m1", "h1")
    assert res_ok["status"] == "success"
    assert res_ok["orderId"] == "o1"
    assert res_ok["minerId"] == "m1"


def test_compute_reveal_result_success_and_failure():
    svc = _bare_service()
    svc.compute_market = SimpleNamespace(
        reveal_result=lambda order_id, miner_id, result_hash, result_encrypted: (False, "bad reveal")
    )
    res_fail = svc._compute_reveal_result("o1", "m1", "rh1", "enc")
    assert res_fail["status"] == "failed"
    assert res_fail["message"] == "bad reveal"

    svc.compute_market = SimpleNamespace(
        reveal_result=lambda order_id, miner_id, result_hash, result_encrypted: (True, "revealed")
    )
    res_ok = svc._compute_reveal_result("o1", "m1", "rh1", "enc")
    assert res_ok["status"] == "success"


def test_compute_get_order_events_success_and_unavailable():
    svc = _bare_service()

    res_unavailable = svc._compute_get_order_events("o1", 10)
    assert res_unavailable["status"] == "failed"
    assert res_unavailable["events"] == []
    assert res_unavailable["total"] == 0

    events = [{"eventType": "create"}, {"eventType": "result_commit"}]
    svc.compute_market = SimpleNamespace(
        get_order_events=lambda order_id, limit: events[:limit]
    )
    res_ok = svc._compute_get_order_events("o1", 10)
    assert res_ok["status"] == "success"
    assert res_ok["events"] == events
    assert res_ok["total"] == 2


def test_compute_cancel_order_prefers_compute_market_path():
    svc = _bare_service()
    svc.miner_address = "minerA"
    svc.compute_market = SimpleNamespace(
        cancel_order=lambda order_id, requester, reason: (True, "cancelled_v3")
    )

    res = svc._compute_cancel_order("o1", reason="manual")
    assert res["status"] == "success"
    assert res["message"] == "cancelled_v3"


def test_compute_cancel_order_fallback_path_and_missing_order():
    svc = _bare_service()
    svc.miner_address = "minerA"
    svc.compute_market = SimpleNamespace(
        cancel_order=lambda order_id, requester, reason: (False, "not cancelled")
    )
    svc.market_orders = {
        "o1": {"minerId": "minerA", "status": "active"}
    }

    res = svc._compute_cancel_order("o1")
    assert res["status"] == "success"
    assert "o1" not in svc.market_orders

    with pytest.raises(RPCError):
        svc._compute_cancel_order("missing-order")


def test_compute_submit_order_prefers_compute_market_v3():
    svc = _bare_service()

    class _Order:
        order_id = "v3_o1"
        status = type("S", (), {"value": "matched"})()
        buyer_address = "MAIN_buyer"
        sector = "RTX4090"
        gpu_count = 2
        duration_hours = 1
        max_price = 1.5
        total_budget = 3.0
        execution_mode = type("M", (), {"value": "normal"})()
        created_at = 123456.0

    svc.compute_market = SimpleNamespace(
        create_order=lambda **kwargs: (_Order(), "ok")
    )

    res = svc._compute_submit_order(
        gpu_type="RTX4090",
        gpu_count=2,
        price_per_hour=1.5,
        duration_hours=1,
        buyer_address="MAIN_buyer",
    )

    assert res["path"] == "compute_market_v3"
    assert res["orderId"] == "v3_o1"


def test_compute_get_order_and_market_prefer_compute_market_v3():
    svc = _bare_service()

    class _Order:
        order_id = "v3_o2"
        buyer_address = "MAIN_buyer"
        sector = "RTX4090"
        gpu_count = 1
        duration_hours = 2
        max_price = 2.0
        total_budget = 4.0
        status = type("S", (), {"value": "created"})()

        def to_dict(self):
            return {"order_id": self.order_id}

    svc.compute_market = SimpleNamespace(
        get_order=lambda order_id: _Order() if order_id == "v3_o2" else None,
        get_market_stats=lambda sector=None: {
            "active_orders": 1,
            "total_gpus": 8,
            "available_gpus": 6,
        },
    )

    got = svc._compute_get_order("v3_o2")
    assert got["path"] == "compute_market_v3"
    assert got["orderId"] == "v3_o2"

    market = svc._compute_get_market("RTX4090")
    assert market["path"] == "compute_market_v3"
    assert market["available"] == 6
