import tempfile
from pathlib import Path

from core.compute_market_v3 import ComputeMarketV3, OrderStatus


def _mk_db() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="market_tx_")
    return str(Path(tmp_dir) / "compute_market_v3.db")


def test_order_lifecycle_events_recorded():
    db_path = _mk_db()
    market = ComputeMarketV3(db_path=db_path)
    try:
        order, _ = market.create_order(
            buyer_address="MAIN_test_buyer",
            sector="RTX4090",
            gpu_count=1,
            duration_hours=1,
            max_price=1.0,
            task_hash="task_hash_demo",
        )
        assert order is not None

        # 模拟匹配完成，直接推进执行阶段（避免耦合矿工注册逻辑）
        order.assigned_miners = ["miner_demo"]
        order.assigned_gpus = {"miner_demo": 1}
        order.status = OrderStatus.MATCHED
        market._update_order(order)

        ok, _ = market.start_execution(order.order_id, "miner_demo")
        assert ok

        market._settlement_fn = lambda **kwargs: True
        ok, _ = market.submit_result(
            order.order_id,
            "miner_demo",
            result_hash="res_hash_001",
            result_encrypted="encrypted_blob",
        )
        assert ok

        actions = [e["action"] for e in market.get_order_events(order.order_id, limit=50)]
        assert "create" in actions
        assert "execute_start" in actions
        assert "result_commit" in actions
        assert "result_reveal" in actions
        assert "settle" in actions
    finally:
        market.close()


def test_order_event_submitter_callback_sets_submitted_flag():
    db_path = _mk_db()
    market = ComputeMarketV3(db_path=db_path)
    try:
        submitted_ids = []

        def submitter(tx_dict):
            submitted_ids.append(tx_dict["tx_id"])
            return True, "ok"

        market.set_order_tx_submitter(submitter)

        order, _ = market.create_order(
            buyer_address="MAIN_test_buyer_2",
            sector="RTX4090",
            gpu_count=1,
            duration_hours=1,
            max_price=1.0,
            task_hash="task_hash_demo_2",
        )
        assert order is not None

        events = market.get_order_events(order.order_id, limit=10)
        assert events
        assert events[0]["submitted"] is True
        assert events[0]["tx"]["tx_id"] in submitted_ids
    finally:
        market.close()
