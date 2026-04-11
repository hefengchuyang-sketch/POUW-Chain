import tempfile
import time
import json
from pathlib import Path

from core.compute_market_v3 import (
    ComputeMarketV3,
    ComputeOrder,
    MinerNode,
    MinerStatus,
    ResourceDeclaration,
    TaskExecutionMode,
)


def _mk_db() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="market_dispatch_")
    return str(Path(tmp_dir) / "compute_market_v3.db")


def _mk_miner(miner_id: str, available_gpus: int, completed: int, failed: int, score: float) -> MinerNode:
    decl = ResourceDeclaration(
        miner_id=miner_id,
        address=f"MAIN_{miner_id}",
        sector="RTX4090",
        total_gpus=max(available_gpus, 1),
        allocatable_gpus=max(available_gpus, 1),
        forced_ratio=0.2,
        price_floor=1.0,
    )
    return MinerNode(
        miner_id=miner_id,
        address=f"MAIN_{miner_id}",
        sector="RTX4090",
        declaration=decl,
        status=MinerStatus.AVAILABLE,
        available_gpus=available_gpus,
        system_score=min(max(score * 2.0, 0.1), 2.0),
        user_rating_weighted=score * 5.0,
        user_rating_count=5,
        tasks_completed=completed,
        tasks_failed=failed,
        last_heartbeat=time.time(),
    )


def _persist_miner(market: ComputeMarketV3, miner: MinerNode) -> None:
    with market._conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO miners
            (miner_id, miner_data, sector, status, available_gpus, combined_score, last_heartbeat, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                miner.miner_id,
                json.dumps(miner.to_dict()),
                miner.sector,
                miner.status.value,
                miner.available_gpus,
                miner.combined_score,
                miner.last_heartbeat,
                time.time(),
            ),
        )


def test_dispatch_weight_prefers_reliable_miner():
    market = ComputeMarketV3(db_path=_mk_db())
    try:
        good = _mk_miner("good", 2, completed=20, failed=1, score=0.9)
        bad = _mk_miner("bad", 2, completed=2, failed=10, score=0.9)

        cg = market._protocol_challenge_score("order_x", good)
        cb = market._protocol_challenge_score("order_x", bad)
        wg = market._compute_dispatch_weight(good, cg)
        wb = market._compute_dispatch_weight(bad, cb)

        assert wg > wb
    finally:
        market.close()


def test_dispatch_weight_considers_ux_stake_factor():
    market = ComputeMarketV3(db_path=_mk_db())
    try:
        low_stake = _mk_miner("low_stake", 2, completed=12, failed=1, score=0.8)
        high_stake = _mk_miner("high_stake", 2, completed=12, failed=1, score=0.8)

        low_stake.total_stake_burned = 0.0
        high_stake.total_stake_burned = 12.0

        c1 = market._protocol_challenge_score("order_stake", low_stake)
        c2 = market._protocol_challenge_score("order_stake", high_stake)
        w1 = market._compute_dispatch_weight(low_stake, c1)
        w2 = market._compute_dispatch_weight(high_stake, c2)

        assert w2 > w1
    finally:
        market.close()


def test_deterministic_weighted_order_is_stable_for_same_input():
    market = ComputeMarketV3(db_path=_mk_db())
    try:
        m1 = _mk_miner("m1", 1, completed=10, failed=1, score=0.8)
        m2 = _mk_miner("m2", 1, completed=10, failed=1, score=0.7)
        m3 = _mk_miner("m3", 1, completed=10, failed=1, score=0.6)

        cands = []
        for m in (m1, m2, m3):
            c = market._protocol_challenge_score("order_det", m)
            w = market._compute_dispatch_weight(m, c)
            cands.append((m, w, c))

        a = [x[0].miner_id for x in market._deterministic_weighted_order("order_det", cands)]
        b = [x[0].miner_id for x in market._deterministic_weighted_order("order_det", cands)]

        assert a == b
        assert sorted(a) == ["m1", "m2", "m3"]
    finally:
        market.close()


def test_protocol_challenge_score_reproducible_with_chain_seed_provider():
    market = ComputeMarketV3(db_path=_mk_db())
    try:
        market._dispatch_challenge_source = "chain"
        market.set_dispatch_seed_provider(lambda: {
            "prev_hash": "ab" * 32,
            "height": 123,
            "epoch": 7,
        })

        miner = _mk_miner("m_chain", 1, completed=5, failed=1, score=0.8)
        seed = market._build_dispatch_seed("order_chain")
        s1 = market._protocol_challenge_score("order_chain", miner, seed)
        s2 = market._protocol_challenge_score("order_chain", miner, seed)

        assert s1 == s2
    finally:
        market.close()


def test_match_order_assigns_required_gpus_using_weighted_dispatch():
    market = ComputeMarketV3(db_path=_mk_db())
    try:
        order = ComputeOrder(
            order_id="order_weighted_1",
            buyer_address="MAIN_buyer",
            sector="RTX4090",
            gpu_count=2,
            duration_hours=1,
            max_price=2.0,
            execution_mode=TaskExecutionMode.NORMAL,
            task_hash="task_h",
            task_encrypted_blob="",
        )

        m1 = _mk_miner("m1", 1, completed=10, failed=1, score=0.9)
        m2 = _mk_miner("m2", 2, completed=8, failed=2, score=0.7)

        market._get_available_miners_for_order = lambda _order: [m1, m2]

        ok, msg = market._match_order(order)
        assert ok, msg
        assert sum(order.assigned_gpus.values()) == 2
        assert order.status.value == "matched"
    finally:
        market.close()


def test_halfhour_trap_penalizes_unsubmitted_dispatch_weight():
    market = ComputeMarketV3(db_path=_mk_db())
    try:
        miner = _mk_miner("trap_penalty", 2, completed=12, failed=1, score=0.8)
        _persist_miner(market, miner)
        c = market._protocol_challenge_score("order_trap_penalty", miner)

        # 未提交当前窗口陷阱题时，会触发降权倍率。
        w_without_submit = market._compute_dispatch_weight(miner, c)

        ok, trap = market.get_performance_trap(miner.miner_id)
        assert ok
        answer = market._performance_traps[miner.miner_id]["expected_answer_hash"]
        ok_submit, res = market.submit_performance_trap(miner.miner_id, trap["challenge_id"], answer)
        assert ok_submit, res

        refreshed = market.get_miner(miner.miner_id)
        assert refreshed is not None
        w_after_submit = market._compute_dispatch_weight(refreshed, c)
        assert w_after_submit > w_without_submit
    finally:
        market.close()


def test_halfhour_trap_submission_updates_system_score():
    market = ComputeMarketV3(db_path=_mk_db())
    try:
        miner = _mk_miner("trap_score_update", 1, completed=8, failed=2, score=0.6)
        _persist_miner(market, miner)

        ok, trap = market.get_performance_trap(miner.miner_id)
        assert ok
        answer = market._performance_traps[miner.miner_id]["expected_answer_hash"]
        ok_submit, res = market.submit_performance_trap(miner.miner_id, trap["challenge_id"], answer)
        assert ok_submit, res

        updated = market.get_miner(miner.miner_id)
        assert updated is not None
        assert updated.trap_total == 1
        assert updated.trap_passed == 1
        assert updated.trap_score > 0.5
        assert updated.system_score > 0.0
    finally:
        market.close()
