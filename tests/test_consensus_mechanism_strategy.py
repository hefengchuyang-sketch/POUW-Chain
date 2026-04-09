import tempfile
from pathlib import Path

from core.consensus import ConsensusEngine


def _tmp_chain_db() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="consensus_strategy_")
    return str(Path(tmp_dir) / "chain.db")


def test_mechanism_strategy_can_limit_ratio_step_and_rollback():
    engine = ConsensusEngine(node_id="strategy_node", sector="MAIN", db_path=_tmp_chain_db())

    assert engine.consensus_sbox_ratio == 0.5

    strategy = engine.configure_mechanism_strategy(
        actor_id="tester",
        version="v2.1",
        max_ratio_step=0.05,
        mode="mixed",
        sbox_ratio=1.0,
    )

    assert strategy["version"] == "v2.1"
    # 受 max_ratio_step 约束，0.5 -> 最多 0.55
    assert abs(engine.consensus_sbox_ratio - 0.55) < 1e-9

    rolled = engine.configure_mechanism_strategy(actor_id="tester", rollback_to_previous=True)
    assert rolled["version"] == "v2.0"
