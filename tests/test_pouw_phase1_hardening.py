import json
import tempfile
from pathlib import Path

from core.consensus import ConsensusEngine
from core.pouw_executor import PoUWExecutor, RealTaskType


def _tmp_chain_db() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="pouw_phase1_")
    return str(Path(tmp_dir) / "chain.db")


def test_hash_search_challenge_is_chain_context_bound():
    executor = PoUWExecutor(min_score_threshold=0.1)

    t1 = executor.generate_task(
        RealTaskType.HASH_SEARCH,
        difficulty=3,
        task_seed="seed-fixed",
        prev_hash="a" * 64,
        block_height=100,
        miner_id="miner_a",
        challenge_window=12345,
    )
    t2 = executor.generate_task(
        RealTaskType.HASH_SEARCH,
        difficulty=3,
        task_seed="seed-fixed",
        prev_hash="b" * 64,
        block_height=100,
        miner_id="miner_a",
        challenge_window=12345,
    )

    assert t1.params["challenge"] != t2.params["challenge"]
    assert t1.params["data"] != t2.params["data"]

    expected_commit = __import__("hashlib").sha256(
        f"{t1.params['challenge']}:{t1.params['challenge_reveal']}".encode()
    ).hexdigest()
    assert t1.params["challenge_commitment"] == expected_commit


def test_executor_outputs_structured_process_proof():
    executor = PoUWExecutor(min_score_threshold=0.1)
    task = executor.generate_task(
        RealTaskType.HASH_SEARCH,
        difficulty=2,
        task_seed="proof-seed",
        prev_hash="c" * 64,
        block_height=101,
        miner_id="miner_b",
        challenge_window=22334,
    )

    result = executor.execute_task(task, miner_id="miner_b")
    assert result.computation_proof.startswith("proof_json=")

    payload = json.loads(result.computation_proof[len("proof_json="):])
    required = {
        "task_id",
        "task_type",
        "input_digest",
        "challenge",
        "challenge_commitment",
        "challenge_reveal",
        "trace_digest",
        "output_digest",
        "timestamp_ms",
        "proof_hash",
    }
    assert required.issubset(set(payload.keys()))
    assert payload["task_id"] == task.task_id
    assert executor.verify_result(task, result) is True


def test_consensus_rejects_tampered_structured_proof_hash():
    engine = ConsensusEngine(node_id="phase1_node", sector="MAIN", db_path=_tmp_chain_db())
    engine.configure_consensus_mode(mode="pouw_only", sbox_ratio=0.0)

    # 先累积证明，再打一个 POUW 区块
    engine._auto_generate_pouw(count=8)
    block = engine.create_block("miner_addr")
    assert block is not None
    assert engine.mine_pouw(block) is True

    ok, msg = engine.validate_block(block)
    assert ok is True, msg

    first = block.pouw_proofs[0]
    payload = json.loads(first["compute_hash"][len("proof_json="):])
    payload["output_digest"] = "0" * 64
    first["compute_hash"] = "proof_json=" + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    ok2, msg2 = engine.validate_block(block)
    assert ok2 is False
    assert "proof_hash mismatch" in msg2
