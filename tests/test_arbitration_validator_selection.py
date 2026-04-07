from core.arbitration import ArbitrationSystem, Dispute, DisputeReason, DisputeStatus


def _make_dispute() -> Dispute:
    return Dispute(
        dispute_id="d1",
        task_id="t1",
        renter_id="r1",
        miner_id="m1",
        reason=DisputeReason.OTHER,
        description="test",
        evidence={},
        status=DisputeStatus.VOTING,
        selected_validators=["v1", "v2", "v3"],
    )


def test_cast_vote_rejects_non_selected_validator():
    system = ArbitrationSystem(validator_pool=["v1", "v2", "v3", "v4"], log_fn=lambda _: None)
    dispute = _make_dispute()
    system.disputes[dispute.dispute_id] = dispute

    ok = system.cast_vote(dispute_id="d1", validator_id="v4", vote="RENTER")

    assert ok is False
    assert "v4" not in dispute.votes


def test_cast_vote_accepts_selected_validator():
    system = ArbitrationSystem(validator_pool=["v1", "v2", "v3", "v4"], log_fn=lambda _: None)
    dispute = _make_dispute()
    system.disputes[dispute.dispute_id] = dispute

    ok = system.cast_vote(dispute_id="d1", validator_id="v2", vote="MINER")

    assert ok is True
    assert dispute.votes["v2"] == "MINER"
