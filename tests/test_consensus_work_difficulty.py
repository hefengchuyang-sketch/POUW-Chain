import tempfile
from pathlib import Path

from core.consensus import ConsensusEngine, WorkDifficultyAdjuster
from core.pouw_block_types import BlockType as PoUWBlockType, RewardDecayRules


def _tmp_chain_db() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="consensus_work_diff_")
    return str(Path(tmp_dir) / "chain.db")


def test_work_difficulty_adjuster_step_limit():
    adjuster = WorkDifficultyAdjuster(
        target_block_time=30.0,
        adjustment_interval=4,
        min_threshold=20.0,
        max_threshold=180.0,
        max_step=6.0,
    )

    for _ in range(4):
        adjuster.record_observation(
            mining_time=8.0,
            avg_quality=95.0,
            has_real_orders=True,
            hash_difficulty=14,
        )

    new_threshold = adjuster.calculate_new_threshold(40.0)
    assert new_threshold <= 46.0
    assert new_threshold >= 34.0


def test_dynamic_work_threshold_in_idle_mode_has_bounded_jitter():
    engine = ConsensusEngine(node_id="wd_idle_node", sector="MAIN", db_path=_tmp_chain_db())
    engine.current_work_threshold = 44.0

    block = engine.create_block("miner_a")
    assert block is not None

    # 人工模拟无单空闲块场景
    block.transactions = []
    block.block_type = PoUWBlockType.IDLE_BLOCK.value
    threshold = engine._get_dynamic_work_threshold(block)

    assert 20.0 <= threshold <= 180.0
    assert threshold != engine.current_work_threshold


def test_idle_penalty_window_reduces_reward_more_aggressively():
    engine = ConsensusEngine(node_id="idle_penalty_node", sector="MAIN", db_path=_tmp_chain_db())

    # 避免 create_block 内部自动生成 POUW 影响 block_type 选择。
    engine.select_consensus = lambda: engine.current_consensus
    engine.current_consensus = engine.current_consensus.POW
    engine.pending_transactions = []
    engine.pending_pouw = []

    # 触发惩罚窗口
    engine._consecutive_idle = engine._idle_penalty_window + 2

    block = engine.create_block("miner_b")
    assert block is not None
    assert block.block_type == PoUWBlockType.IDLE_BLOCK.value

    base = engine.reward_calculator.get_block_reward(block.height)
    baseline_idle_reward = RewardDecayRules.calculate_reward(
        PoUWBlockType.IDLE_BLOCK,
        base,
        engine._consecutive_idle,
    )

    assert block.block_reward < baseline_idle_reward
