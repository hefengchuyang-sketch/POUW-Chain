"""
测试上传超时自动取消 + 国库补偿矿工带宽
"""
import os
import sys
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_release_budget():
    """测试 TaskSettlementContract.release_budget 全额退还"""
    from core.encrypted_task import TaskSettlementContract

    contract = TaskSettlementContract(log_fn=lambda x: None)
    contract.deposit("user1", 100.0)
    assert contract.get_balance("user1") == 100.0

    # 锁定 50
    ok = contract.lock_budget("task_abc", "user1", 50.0)
    assert ok
    assert contract.get_balance("user1") == 50.0
    assert contract.locked_budgets["task_abc"] == 50.0

    # 释放
    refunded = contract.release_budget("task_abc", "user1")
    assert refunded == 50.0
    assert contract.get_balance("user1") == 100.0
    assert "task_abc" not in contract.locked_budgets


def test_release_budget_nonexistent():
    """释放不存在的任务应返回 0"""
    from core.encrypted_task import TaskSettlementContract

    contract = TaskSettlementContract(log_fn=lambda x: None)
    refunded = contract.release_budget("no_such_task", "user1")
    assert refunded == 0.0


def test_upload_timeout_detection():
    """测试上传超时任务能被自动检测"""
    from core.encrypted_task import (
        EncryptedTaskManager, TaskSettlementContract,
        TaskChainStatus, HybridEncryption,
    )

    manager = EncryptedTaskManager(log_fn=lambda x: None)
    contract = TaskSettlementContract(log_fn=lambda x: None)
    contract.deposit("user_test", 200.0)

    keypair = HybridEncryption.generate_keypair()
    manager.register_miner("miner_a")

    task = manager.create_task(
        user_id="user_test",
        user_keypair=keypair,
        title="timeout test",
        description="",
        code_data=b"print('hi')",
        input_data=b"",
        task_type="compute",
        estimated_hours=1.0,
        budget_per_hour=10.0,
        receivers=["miner_a"],
    )
    task._extra_meta = {}

    # 锁定预算
    contract.lock_budget(task.task_id, "user_test", task.total_budget)

    # 任务刚创建，状态应该是 CREATED
    assert task.chain_status == TaskChainStatus.CREATED

    # 模拟超时：把创建时间推早 3 小时
    task.created_at = time.time() - 3 * 3600

    # 手动调用取消逻辑
    import logging
    logger = logging.getLogger("test")

    # 导入并调用取消函数（模拟 rpc_service 的逻辑）
    from core.rpc_service import NodeRPCService
    service = NodeRPCService()
    service._cancel_upload_timeout_task(task, contract, logger)

    # 验证
    assert task.chain_status == TaskChainStatus.CANCELLED
    assert task.completed_at is not None
    assert task._extra_meta["cancel_reason"] == "upload_timeout"
    # 预算已退还
    assert contract.get_balance("user_test") == 200.0


def test_upload_timeout_with_miner_compensation():
    """测试上传超时时矿工有部分数据会获得国库补偿"""
    from core.encrypted_task import (
        EncryptedTaskManager, TaskSettlementContract,
        TaskChainStatus, HybridEncryption,
    )

    manager = EncryptedTaskManager(log_fn=lambda x: None)
    contract = TaskSettlementContract(log_fn=lambda x: None)
    contract.deposit("user_comp", 100.0)

    keypair = HybridEncryption.generate_keypair()
    manager.register_miner("miner_b")

    task = manager.create_task(
        user_id="user_comp",
        user_keypair=keypair,
        title="compensation test",
        description="",
        code_data=b"x=1",
        input_data=b"",
        task_type="compute",
        estimated_hours=2.0,
        budget_per_hour=10.0,
        receivers=["miner_b"],
    )
    task._extra_meta = {}
    contract.lock_budget(task.task_id, "user_comp", task.total_budget)

    # 模拟矿工已经接收了部分数据：创建 P2P 接收目录并写入假文件
    data_dir = os.path.join("data", "p2p_recv", task.task_id)
    os.makedirs(data_dir, exist_ok=True)
    try:
        # 写入 500MB 的假文件（只写元数据，不实际分配磁盘空间）
        fake_file = os.path.join(data_dir, "dataset.bin")
        with open(fake_file, "wb") as f:
            # 写 1MB 实际数据来测试补偿计算
            f.write(b"\x00" * (1024 * 1024))

        task.created_at = time.time() - 3 * 3600

        import logging
        logger = logging.getLogger("test_comp")

        from core.rpc_service import NodeRPCService
        service = NodeRPCService()
        
        # 确保国库有余额用于补偿
        dao_system = service._get_dao_system()
        dao_system["governance"].treasury.treasury.balance = 1000.0
        
        service._cancel_upload_timeout_task(task, contract, logger)

        assert task.chain_status == TaskChainStatus.CANCELLED
        # 用户预算全额退还
        assert contract.get_balance("user_comp") == 100.0
        # 矿工获得了国库补偿
        miner_balance = contract.balances.get("miner_b", 0)
        assert miner_balance > 0, "矿工应该获得国库补偿"
        assert task._extra_meta["miner_compensation"] > 0
        assert task._extra_meta["bytes_received_by_miner"] == 1024 * 1024
    finally:
        # 清理测试文件
        shutil.rmtree(data_dir, ignore_errors=True)


def test_cancel_rpc_method():
    """测试手动取消 RPC 接口"""
    from core.encrypted_task import (
        TaskChainStatus, HybridEncryption,
    )
    from core.rpc_service import NodeRPCService

    service = NodeRPCService()
    manager, contract = service._get_encrypted_task_manager()
    contract.deposit("user_cancel", 50.0)

    keypair = HybridEncryption.generate_keypair()
    manager.register_miner("miner_c")

    task = manager.create_task(
        user_id="user_cancel",
        user_keypair=keypair,
        title="cancel test",
        description="",
        code_data=b"pass",
        input_data=b"",
        task_type="compute",
        estimated_hours=1.0,
        budget_per_hour=10.0,
        receivers=["miner_c"],
    )
    task._extra_meta = {}
    contract.lock_budget(task.task_id, "user_cancel", task.total_budget)

    # 调用 RPC 取消
    result = service._encrypted_task_cancel(taskId=task.task_id)
    assert result["status"] == "cancelled"
    assert result["refunded"] == 10.0
    assert "cancelReason" in result

    # 用户余额恢复
    assert contract.get_balance("user_cancel") == 50.0


def test_cancel_already_running_rejected():
    """测试已在执行中的任务不允许取消"""
    from core.encrypted_task import TaskChainStatus, HybridEncryption
    from core.rpc_service import NodeRPCService
    from core.rpc.models import RPCError

    service = NodeRPCService()
    manager, contract = service._get_encrypted_task_manager()
    contract.deposit("user_run", 50.0)

    keypair = HybridEncryption.generate_keypair()
    manager.register_miner("miner_d")

    task = manager.create_task(
        user_id="user_run",
        user_keypair=keypair,
        title="running test",
        description="",
        code_data=b"pass",
        input_data=b"",
        task_type="compute",
        estimated_hours=1.0,
        budget_per_hour=10.0,
        receivers=["miner_d"],
    )
    task._extra_meta = {}
    contract.lock_budget(task.task_id, "user_run", task.total_budget)

    # 强制设为 IN_PROGRESS
    task.chain_status = TaskChainStatus.IN_PROGRESS

    try:
        service._encrypted_task_cancel(taskId=task.task_id)
        assert False, "应该抛出 RPCError"
    except RPCError as e:
        assert "不允许取消" in str(e)


def test_treasury_genesis_fund():
    """测试国库创世预拨种子资金"""
    from core.dao_treasury import TreasuryManager

    mgr = TreasuryManager()
    assert mgr.treasury.balance == 1000.0, "国库应有 1000 MAIN 创世预拨"
    assert mgr.treasury.total_income == 1000.0


def test_treasury_debt_and_auto_settle():
    """测试国库余额不足时记录欠条，入账后自动清偿"""
    from core.dao_treasury import TreasuryManager

    mgr = TreasuryManager()
    # 先花光国库
    mgr.treasury.balance = 0.0

    # 补偿请求 → 应产生欠条
    result = mgr.auto_compensate(
        recipient="miner_x", amount=2.0,
        reason="bandwidth", task_id="task_001",
    )
    assert result.get("deferred") is True
    assert len(mgr.pending_debts) == 1
    assert mgr.pending_debts[0]["recipient"] == "miner_x"
    assert mgr.pending_debts[0]["amount"] == 2.0

    # 国库收到一笔入账 → 自动清偿
    mgr.deposit(amount=5.0, source="fee_from_task", category="fee")
    assert len(mgr.pending_debts) == 0, "欠条应已自动清偿"
    assert mgr.treasury.balance == 3.0  # 5 - 2 = 3
    # 确认清偿交易已记录
    debt_txs = [t for t in mgr.transactions if t["type"] == "debt_settlement"]
    assert len(debt_txs) == 1
    assert debt_txs[0]["recipient"] == "miner_x"
    assert debt_txs[0]["amount"] == 2.0


def test_treasury_debt_partial_settle():
    """测试多笔欠条按顺序清偿，余额不足时保留剩余欠条"""
    from core.dao_treasury import TreasuryManager

    mgr = TreasuryManager()
    mgr.treasury.balance = 0.0

    # 产生 3 笔欠条
    mgr.auto_compensate(recipient="m1", amount=1.0, reason="bw", task_id="t1")
    mgr.auto_compensate(recipient="m2", amount=3.0, reason="bw", task_id="t2")
    mgr.auto_compensate(recipient="m3", amount=2.0, reason="bw", task_id="t3")
    assert len(mgr.pending_debts) == 3

    # 入账 2.5 → 只够清偿第一笔（1.0），第二笔需要 3.0 不够
    mgr.deposit(amount=2.5, source="block_reward", category="fee")
    assert len(mgr.pending_debts) == 2  # m2, m3 仍然未清
    assert mgr.treasury.balance == 1.5  # 2.5 - 1.0 = 1.5

    # 再入账 5.0 → 清偿剩余（3.0 + 2.0 = 5.0）
    mgr.deposit(amount=5.0, source="block_reward", category="fee")
    assert len(mgr.pending_debts) == 0
    assert mgr.treasury.balance == 1.5  # 1.5 + 5.0 - 3.0 - 2.0 = 1.5


def test_treasury_daily_compensate_cap():
    """测试每日自动补偿总量上限（防止国库被耗尽）"""
    from core.dao_treasury import TreasuryManager

    mgr = TreasuryManager()
    mgr.treasury.balance = 50000.0  # 给足够余额

    # 连续补偿直到触碰日限额（DAILY_COMPENSATE_CAP = 100 MAIN）
    paid = 0.0
    for i in range(20):
        result = mgr.auto_compensate(
            recipient=f"miner_{i}", amount=8.0, reason="bw", task_id=f"t{i}"
        )
        if "error" in result:
            break
        paid += 8.0

    # 应在 12 次后（96 MAIN）还能成功，第 13 次（104 > 100）被拒绝
    assert paid == 96.0  # 12 × 8 = 96
    assert "Daily auto-compensate cap" in result["error"]


def test_treasury_per_miner_daily_cap():
    """测试单个矿工每日补偿上限"""
    from core.dao_treasury import TreasuryManager

    mgr = TreasuryManager()
    mgr.treasury.balance = 50000.0

    # 同一矿工连续领取（PER_MINER_DAILY_CAP = 20 MAIN）
    paid = 0.0
    for i in range(10):
        result = mgr.auto_compensate(
            recipient="greedy_miner", amount=5.0, reason="bw", task_id=f"t{i}"
        )
        if "error" in result:
            break
        paid += 5.0

    # 应在 4 次后（20 MAIN）停止：第 5 次超出 per-miner 限额
    assert paid == 20.0  # 4 × 5 = 20
    assert "Miner daily compensate cap" in result["error"]


def test_treasury_per_miner_count_limit():
    """测试单个矿工每日补偿次数上限"""
    from core.dao_treasury import TreasuryManager

    mgr = TreasuryManager()
    mgr.treasury.balance = 50000.0

    # 同一矿工小额多次（PER_MINER_DAILY_COUNT = 5）
    count = 0
    for i in range(10):
        result = mgr.auto_compensate(
            recipient="spammer", amount=0.01, reason="bw", task_id=f"t{i}"
        )
        if "error" in result:
            break
        count += 1

    assert count == 5  # 5 次后拒绝
    assert "count limit" in result["error"]


def test_treasury_daily_cap_resets():
    """测试日限额在日期变化后重置"""
    from core.dao_treasury import TreasuryManager

    mgr = TreasuryManager()
    mgr.treasury.balance = 50000.0

    # 先消耗掉日限额
    for i in range(12):
        mgr.auto_compensate(recipient=f"m_{i}", amount=8.0, reason="bw", task_id=f"t{i}")

    # 此时日限额已用 96，再次应被拒
    r = mgr.auto_compensate(recipient="m_x", amount=8.0, reason="bw", task_id="tx")
    assert "error" in r

    # 模拟日期变更 → 重置
    mgr._daily_compensate_date = "1970-01-01"

    # 应当再次允许
    r2 = mgr.auto_compensate(recipient="m_y", amount=8.0, reason="bw", task_id="ty")
    assert "error" not in r2
    assert r2.get("tx_id") or r2.get("deferred")


if __name__ == "__main__":
    test_release_budget()
    test_release_budget_nonexistent()
    test_upload_timeout_detection()
    test_upload_timeout_with_miner_compensation()
    test_cancel_rpc_method()
    test_cancel_already_running_rejected()
    test_treasury_genesis_fund()
    test_treasury_debt_and_auto_settle()
    test_treasury_debt_partial_settle()
    print("✅ 全部 9 个上传超时测试通过")
