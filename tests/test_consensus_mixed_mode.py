import pytest

from core.consensus import ConsensusEngine, ConsensusType


def _make_engine() -> ConsensusEngine:
    engine = ConsensusEngine(node_id="test_mixed", sector="MAIN")
    engine._auto_generate_pouw = lambda count=4: None
    return engine


def test_configure_consensus_mode_clamps_ratio_and_defaults_invalid_mode():
    engine = _make_engine()
    engine.configure_consensus_mode(mode="invalid_mode", sbox_ratio=2.5, sbox_enabled=True)

    assert engine.consensus_mode == "mixed"
    assert engine.consensus_sbox_ratio == 1.0
    assert engine._sbox_mining_enabled is True


def test_mixed_mode_uses_sbox_when_ratio_is_one():
    engine = _make_engine()
    engine.configure_consensus_mode(mode="mixed", sbox_ratio=1.0, sbox_enabled=True)

    engine.has_pouw_tasks = lambda: True
    engine._get_sbox_miner = lambda: object()

    assert engine.select_consensus() == ConsensusType.SBOX_POUW


def test_mixed_mode_uses_pouw_when_ratio_is_zero():
    engine = _make_engine()
    engine.configure_consensus_mode(mode="mixed", sbox_ratio=0.0, sbox_enabled=True)

    engine.has_pouw_tasks = lambda: True
    engine._get_sbox_miner = lambda: object()

    assert engine.select_consensus() == ConsensusType.POUW


def test_sbox_only_falls_back_to_pouw_when_sbox_unavailable():
    engine = _make_engine()
    engine.configure_consensus_mode(mode="sbox_only", sbox_ratio=0.5, sbox_enabled=True)

    engine.has_pouw_tasks = lambda: True
    engine._get_sbox_miner = lambda: None

    assert engine.select_consensus() == ConsensusType.POUW


def test_pouw_only_uses_pouw_even_if_sbox_available():
    engine = _make_engine()
    engine.configure_consensus_mode(mode="pouw_only", sbox_ratio=0.5, sbox_enabled=True)

    engine.has_pouw_tasks = lambda: True
    engine._get_sbox_miner = lambda: object()

    assert engine.select_consensus() == ConsensusType.POUW


def test_mixed_mode_ratio_produces_both_consensus_types():
    engine = _make_engine()
    engine.configure_consensus_mode(mode="mixed", sbox_ratio=0.65, sbox_enabled=True)

    engine.has_pouw_tasks = lambda: True
    engine._get_sbox_miner = lambda: object()

    class _Latest:
        hash = "h" * 64

    engine.get_latest_block = lambda: _Latest()

    picks = [engine.select_consensus() for _ in range(200)]
    sbox_count = sum(1 for x in picks if x == ConsensusType.SBOX_POUW)
    pouw_count = sum(1 for x in picks if x == ConsensusType.POUW)

    assert sbox_count > 0
    assert pouw_count > 0

    ratio = sbox_count / len(picks)
    assert 0.45 <= ratio <= 0.85, f"Unexpected mixed ratio drift: {ratio}"


def test_chain_info_contains_consensus_distribution_stats():
    engine = _make_engine()
    engine.configure_consensus_mode(mode="mixed", sbox_ratio=0.5, sbox_enabled=True)

    engine._record_selected_consensus(ConsensusType.SBOX_POUW)
    engine._record_selected_consensus(ConsensusType.POUW)
    engine._record_mined_consensus(ConsensusType.SBOX_POUW)

    info = engine.get_chain_info()

    assert "consensus_selected_distribution" in info
    assert "consensus_mined_distribution" in info
    assert info["consensus_selected_distribution"]["window"] >= 2
    assert info["consensus_mined_distribution"]["window"] >= 1
