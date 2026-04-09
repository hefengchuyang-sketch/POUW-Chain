import json
import os
import tempfile
from pathlib import Path

from core.compute_market_v3 import (
    ComputeMarketV3,
    OrderStatus,
    TaskExecutionMode,
    ValidationType,
)
from core.rpc_service import NodeRPCService
from core.tee_computing import TEEType, get_tee_system


def _fresh_market_db() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="tee_market_test_")
    return str(Path(tmp_dir) / "compute_market_v3.db")


def test_tee_order_validation_detects_tampered_attestation_hash():
    system = get_tee_system()
    manager = system["tee_manager"]

    node_id = "tee_test_node_hash"
    manager.register_tee_node(node_id=node_id, tee_type=TEEType.INTEL_SGX)

    report = manager.submit_attestation(
        node_id=node_id,
        mrenclave="a" * 64,
        mrsigner="b" * 64,
        report_data=("a" * 64) + "::payload",
    )
    assert report.is_valid is True

    att = report.to_dict()
    att["report_hash"] = report.report_hash

    db_path = _fresh_market_db()
    market = ComputeMarketV3(db_path=db_path)
    try:
        order, _ = market.create_order(
            buyer_address="buyer_t1",
            sector="RTX4090",
            gpu_count=1,
            duration_hours=1,
            max_price=1.0,
            task_hash="task_hash_t1",
            execution_mode=TaskExecutionMode.TEE,
            tee_node_id=node_id,
            tee_attestation=att,
        )
        assert order is not None

        order.status = OrderStatus.FINISHED
        order.started_at = 1.0
        order.finished_at = 2.0
        market._update_order(order)

        ok, msg = market.request_validation(order.order_id, ValidationType.TEE_ATTESTATION)
        assert ok is True, msg

        order.tee_attestation = dict(att)
        order.tee_attestation["report_hash"] = "0" * 64
        market._update_order(order)

        ok2, msg2 = market.request_validation(order.order_id, ValidationType.TEE_ATTESTATION)
        assert ok2 is False
        assert "report_hash" in msg2
    finally:
        market.close()


def test_rpc_tee_methods_are_compatible_with_tee_manager_api():
    service = NodeRPCService()

    node = service._tee_register_node(nodeId="tee_rpc_node_1", teeType="INTEL_SGX")
    assert node["nodeId"] == "tee_rpc_node_1"

    report_data = json.dumps(
        {
            "mrenclave": "c" * 64,
            "mrsigner": "d" * 64,
        }
    )

    submit = service._tee_submit_attestation(
        nodeId="tee_rpc_node_1",
        reportData=report_data,
        signature="",
        platformInfo={"vendor": "mock"},
    )

    assert submit["reportId"]
    assert submit["isValid"] is True

    info = service._tee_get_node_info("tee_rpc_node_1")
    assert info is not None
    assert info["nodeId"] == "tee_rpc_node_1"


def _make_valid_tee_order(market: ComputeMarketV3, node_id: str, attestation: dict):
    order, _ = market.create_order(
        buyer_address="buyer_t2",
        sector="RTX4090",
        gpu_count=1,
        duration_hours=1,
        max_price=1.0,
        task_hash="task_hash_t2",
        execution_mode=TaskExecutionMode.TEE,
        tee_node_id=node_id,
        tee_attestation=attestation,
    )
    assert order is not None
    return order


def test_tee_validation_fails_for_expired_or_node_mismatch_or_missing_report():
    system = get_tee_system()
    manager = system["tee_manager"]

    node_a = "tee_node_a"
    node_b = "tee_node_b"
    manager.register_tee_node(node_id=node_a, tee_type=TEEType.INTEL_SGX)
    manager.register_tee_node(node_id=node_b, tee_type=TEEType.INTEL_SGX)

    report = manager.submit_attestation(
        node_id=node_a,
        mrenclave="1" * 64,
        mrsigner="2" * 64,
        report_data=("1" * 64) + "::payload",
    )
    att = report.to_dict()
    att["report_hash"] = report.report_hash

    db_path = _fresh_market_db()
    market = ComputeMarketV3(db_path=db_path)
    try:
        order = _make_valid_tee_order(market, node_a, att)
        order.status = OrderStatus.FINISHED
        order.started_at = 1.0
        order.finished_at = 2.0

        # 1) 过期
        manager.attestation_reports[report.report_id].expiry = 1.0
        market._update_order(order)
        ok1, msg1 = market.request_validation(order.order_id, ValidationType.TEE_ATTESTATION)
        assert ok1 is False
        assert "过期" in msg1

        # 恢复有效期
        manager.attestation_reports[report.report_id].expiry = 10**10

        # 2) 节点不匹配
        order.tee_node_id = node_b
        market._update_order(order)
        ok2, msg2 = market.request_validation(order.order_id, ValidationType.TEE_ATTESTATION)
        assert ok2 is False
        assert ("不绑定" in msg2) or ("不一致" in msg2)

        # 3) 缺失报告ID
        order.tee_node_id = node_a
        order.tee_attestation = dict(att)
        order.tee_attestation.pop("report_id", None)
        market._update_order(order)
        ok3, msg3 = market.request_validation(order.order_id, ValidationType.TEE_ATTESTATION)
        assert ok3 is False
        assert "不存在" in msg3
    finally:
        market.close()


def test_submit_result_enforces_tee_validation_before_settlement():
    system = get_tee_system()
    manager = system["tee_manager"]

    node_id = "tee_submit_node"
    manager.register_tee_node(node_id=node_id, tee_type=TEEType.INTEL_SGX)
    report = manager.submit_attestation(
        node_id=node_id,
        mrenclave="3" * 64,
        mrsigner="4" * 64,
        report_data=("3" * 64) + "::payload",
    )
    att = report.to_dict()
    att["report_hash"] = report.report_hash

    db_path = _fresh_market_db()
    market = ComputeMarketV3(db_path=db_path)
    try:
        order = _make_valid_tee_order(market, node_id, att)
        # 创建后篡改订单中的证明，验证提交阶段仍会被拦截。
        order.tee_attestation = dict(att)
        order.tee_attestation["report_hash"] = "f" * 64
        order.status = OrderStatus.EXECUTING
        order.assigned_miners = [node_id]
        order.assigned_gpus = {node_id: 1}
        market._update_order(order)

        ok, msg = market.submit_result(
            order_id=order.order_id,
            miner_id=node_id,
            result_hash="a" * 64,
            result_encrypted="",
        )
        assert ok is False
        assert "TEE 证明验证失败" in msg

        reloaded = market.get_order(order.order_id)
        assert reloaded is not None
        assert reloaded.status == OrderStatus.FAILED
        assert "tee_validation_failed" in reloaded.settlement_error
    finally:
        market.close()


def test_tee_order_forces_validation_policy():
    system = get_tee_system()
    manager = system["tee_manager"]

    node_id = "tee_policy_node"
    manager.register_tee_node(node_id=node_id, tee_type=TEEType.INTEL_SGX)
    report = manager.submit_attestation(
        node_id=node_id,
        mrenclave="5" * 64,
        mrsigner="6" * 64,
        report_data=("5" * 64) + "::payload",
    )
    att = report.to_dict()
    att["report_hash"] = report.report_hash

    db_path = _fresh_market_db()
    market = ComputeMarketV3(db_path=db_path)
    try:
        order, _ = market.create_order(
            buyer_address="buyer_t3",
            sector="RTX4090",
            gpu_count=1,
            duration_hours=1,
            max_price=1.0,
            task_hash="task_hash_t3",
            execution_mode=TaskExecutionMode.TEE,
            allow_validation=False,  # 应被系统强制改回 True
            tee_node_id=node_id,
            tee_attestation=att,
        )
        assert order is not None
        assert order.allow_validation is True
        assert order.validation_type == ValidationType.TEE_ATTESTATION
    finally:
        market.close()


def test_tee_submit_result_rejects_miner_node_mismatch():
    system = get_tee_system()
    manager = system["tee_manager"]

    node_id = "tee_bind_node"
    manager.register_tee_node(node_id=node_id, tee_type=TEEType.INTEL_SGX)
    report = manager.submit_attestation(
        node_id=node_id,
        mrenclave="7" * 64,
        mrsigner="8" * 64,
        report_data=("7" * 64) + "::payload",
    )
    att = report.to_dict()
    att["report_hash"] = report.report_hash

    db_path = _fresh_market_db()
    market = ComputeMarketV3(db_path=db_path)
    try:
        order = _make_valid_tee_order(market, node_id, att)
        order.status = OrderStatus.EXECUTING
        order.assigned_miners = ["another_miner"]
        order.assigned_gpus = {"another_miner": 1}
        market._update_order(order)

        ok, msg = market.submit_result(
            order_id=order.order_id,
            miner_id="another_miner",
            result_hash="b" * 64,
            result_encrypted="",
        )
        assert ok is False
        assert "不一致" in msg
    finally:
        market.close()


def test_attestation_extended_evidence_fields_are_persisted():
    system = get_tee_system()
    manager = system["tee_manager"]

    node_id = "tee_ext_fields_node"
    manager.register_tee_node(node_id=node_id, tee_type=TEEType.AMD_SEV_SNP)
    report = manager.submit_attestation(
        node_id=node_id,
        mrenclave="9" * 64,
        mrsigner="a" * 64,
        report_data=("9" * 64) + "::payload",
        provider="mock_vendor",
        evidence_type="quote",
        cert_chain_hash="c" * 64,
        tcb_status="up_to_date",
        measurement_ts=1234567890.0,
    )

    assert report.is_valid is True
    d = report.to_dict()
    assert d["provider"] == "mock_vendor"
    assert d["evidence_type"] == "quote"
    assert d["cert_chain_hash"] == "c" * 64
    assert d["tcb_status"] == "up_to_date"
    assert float(d["measurement_ts"]) == 1234567890.0


def test_tee_strict_policy_checks_evidence_age_and_measurement_whitelist():
    old_whitelist = os.environ.get("POUW_TEE_MRENCLAVE_WHITELIST")
    old_rollout = os.environ.get("POUW_TEE_STRICT_ROLLOUT_PERCENT")
    old_full = os.environ.get("POUW_TEE_FULL_ENFORCE")
    old_age = os.environ.get("POUW_TEE_MAX_EVIDENCE_AGE_SECONDS")

    os.environ["POUW_TEE_MRENCLAVE_WHITELIST"] = "f" * 64
    os.environ["POUW_TEE_STRICT_ROLLOUT_PERCENT"] = "100"
    os.environ["POUW_TEE_FULL_ENFORCE"] = "true"
    os.environ["POUW_TEE_MAX_EVIDENCE_AGE_SECONDS"] = "10"

    try:
        system = get_tee_system()
        manager = system["tee_manager"]

        node_id = "tee_policy_strict_node"
        manager.register_tee_node(node_id=node_id, tee_type=TEEType.INTEL_SGX)

        report = manager.submit_attestation(
            node_id=node_id,
            mrenclave="1" * 64,
            mrsigner="2" * 64,
            report_data=("1" * 64) + "::payload",
            measurement_ts=1.0,  # 极旧证据，且不在白名单
        )
        att = report.to_dict()
        att["report_hash"] = report.report_hash

        db_path = _fresh_market_db()
        market = ComputeMarketV3(db_path=db_path)
        try:
                order, msg = market.create_order(
                    buyer_address="buyer_strict",
                    sector="RTX4090",
                    gpu_count=1,
                    duration_hours=1,
                    max_price=1.0,
                    task_hash="task_hash_strict",
                    execution_mode=TaskExecutionMode.TEE,
                    tee_node_id=node_id,
                    tee_attestation=att,
                )
                assert order is None
                assert "tee_policy_reject" in msg
                assert ("过旧" in msg) or ("白名单" in msg)
        finally:
            market.close()
    finally:
        if old_whitelist is None:
            os.environ.pop("POUW_TEE_MRENCLAVE_WHITELIST", None)
        else:
            os.environ["POUW_TEE_MRENCLAVE_WHITELIST"] = old_whitelist
        if old_rollout is None:
            os.environ.pop("POUW_TEE_STRICT_ROLLOUT_PERCENT", None)
        else:
            os.environ["POUW_TEE_STRICT_ROLLOUT_PERCENT"] = old_rollout
        if old_full is None:
            os.environ.pop("POUW_TEE_FULL_ENFORCE", None)
        else:
            os.environ["POUW_TEE_FULL_ENFORCE"] = old_full
        if old_age is None:
            os.environ.pop("POUW_TEE_MAX_EVIDENCE_AGE_SECONDS", None)
        else:
            os.environ["POUW_TEE_MAX_EVIDENCE_AGE_SECONDS"] = old_age


def test_kms_gate_requires_policy_and_attestation():
    system = get_tee_system()
    manager = system["tee_manager"]

    node_id = "tee_kms_gate_node"
    manager.register_tee_node(node_id=node_id, tee_type=TEEType.INTEL_SGX)
    report = manager.submit_attestation(
        node_id=node_id,
        mrenclave="d" * 64,
        mrsigner="e" * 64,
        report_data=("d" * 64) + "::payload",
        tcb_status="up_to_date",
    )
    att = report.to_dict()
    att["report_hash"] = report.report_hash

    ok, key, reason = manager.request_session_key(
        node_id=node_id,
        attestation=att,
        policy={"required_tcb_status": "up_to_date"},
    )
    assert ok is True
    assert bool(key)
    assert reason == "ok"

    bad_att = dict(att)
    bad_att["report_hash"] = "0" * 64
    ok2, key2, reason2 = manager.request_session_key(
        node_id=node_id,
        attestation=bad_att,
        policy={"required_tcb_status": "up_to_date"},
    )
    assert ok2 is False
    assert key2 == ""
    assert "failed" in reason2 or "不一致" in reason2


def test_tee_order_creation_fails_fast_when_policy_rejects_attestation():
    old_whitelist = os.environ.get("POUW_TEE_MRENCLAVE_WHITELIST")
    old_rollout = os.environ.get("POUW_TEE_STRICT_ROLLOUT_PERCENT")
    old_full = os.environ.get("POUW_TEE_FULL_ENFORCE")

    os.environ["POUW_TEE_MRENCLAVE_WHITELIST"] = "f" * 64
    os.environ["POUW_TEE_STRICT_ROLLOUT_PERCENT"] = "100"
    os.environ["POUW_TEE_FULL_ENFORCE"] = "true"

    try:
        system = get_tee_system()
        manager = system["tee_manager"]

        node_id = "tee_create_reject_node"
        manager.register_tee_node(node_id=node_id, tee_type=TEEType.INTEL_SGX)
        report = manager.submit_attestation(
            node_id=node_id,
            mrenclave="1" * 64,
            mrsigner="2" * 64,
            report_data=("1" * 64) + "::payload",
        )
        att = report.to_dict()
        att["report_hash"] = report.report_hash

        db_path = _fresh_market_db()
        market = ComputeMarketV3(db_path=db_path)
        try:
            order, msg = market.create_order(
                buyer_address="buyer_reject",
                sector="RTX4090",
                gpu_count=1,
                duration_hours=1,
                max_price=1.0,
                task_hash="task_hash_reject",
                execution_mode=TaskExecutionMode.TEE,
                tee_node_id=node_id,
                tee_attestation=att,
            )
            assert order is None
            assert "tee_policy_reject" in msg
        finally:
            market.close()
    finally:
        if old_whitelist is None:
            os.environ.pop("POUW_TEE_MRENCLAVE_WHITELIST", None)
        else:
            os.environ["POUW_TEE_MRENCLAVE_WHITELIST"] = old_whitelist
        if old_rollout is None:
            os.environ.pop("POUW_TEE_STRICT_ROLLOUT_PERCENT", None)
        else:
            os.environ["POUW_TEE_STRICT_ROLLOUT_PERCENT"] = old_rollout
        if old_full is None:
            os.environ.pop("POUW_TEE_FULL_ENFORCE", None)
        else:
            os.environ["POUW_TEE_FULL_ENFORCE"] = old_full
