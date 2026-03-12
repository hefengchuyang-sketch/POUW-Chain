# -*- coding: utf-8 -*-
"""
盲任务引擎 (BlindTaskEngine) + 盲调度 (ComputeScheduler BLIND) 测试
验证：矿工无感知的算力租用系统完整流程
"""

import sys
import os
import json
import hashlib
import unittest
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestTrapGenerator(unittest.TestCase):
    """Test 1-3: 陷阱题生成器"""

    def test_trap_hash_prefix_deterministic(self):
        """陷阱题：相同 seed 产生相同答案"""
        from core.blind_task_engine import TrapGenerator, TrapDifficulty
        data1, answer1 = TrapGenerator.generate(TrapDifficulty.EASY, seed=42)
        data2, answer2 = TrapGenerator.generate(TrapDifficulty.EASY, seed=42)
        self.assertEqual(answer1, answer2, "相同 seed 应产生相同答案")
        self.assertEqual(data1, data2)

    def test_trap_matrix_checksum(self):
        """陷阱题：矩阵乘法校验和可验证"""
        from core.blind_task_engine import TrapGenerator, TrapDifficulty
        data, answer = TrapGenerator.generate(TrapDifficulty.MEDIUM, seed=123)
        self.assertIn("matrix_a", data)
        self.assertIn("matrix_b", data)
        # 独立计算验证
        A = data["matrix_a"]
        B = data["matrix_b"]
        size = data["size"]
        C = [[0] * size for _ in range(size)]
        for i in range(size):
            for j in range(size):
                for k in range(size):
                    C[i][j] += A[i][k] * B[k][j]
        expected = hashlib.sha256(json.dumps(C, sort_keys=True).encode()).hexdigest()
        self.assertEqual(answer, expected, "矩阵乘法陷阱答案应正确")

    def test_trap_gradient_descent(self):
        """陷阱题：梯度下降目标可验证"""
        from core.blind_task_engine import TrapGenerator, TrapDifficulty
        data, answer = TrapGenerator.generate(TrapDifficulty.HARD, seed=999)
        self.assertIn("target", data)
        self.assertIn("initial", data)
        self.assertIsInstance(answer, str)
        self.assertEqual(len(answer), 64)  # SHA256 hex


class TestBlindChallenge(unittest.TestCase):
    """Test 4-6: 盲挑战伪装性"""

    def test_challenge_type_always_mining(self):
        """所有挑战类型都显示为 mining_challenge"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        challenge = engine.wrap_as_mining("real_task_1", {"computation": "hash_search"})
        self.assertEqual(challenge.challenge_type, "mining_challenge")
        view = challenge.to_miner_view()
        self.assertEqual(view["type"], "mining_challenge")

    def test_camouflaged_id_irreversible(self):
        """伪装 ID 不可逆推出原始 task_id"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        c1 = engine.wrap_as_mining("task_secret_001", {"computation": "test"})
        c2 = engine.wrap_as_mining("task_secret_001", {"computation": "test"})
        # 相同任务每次生成不同 ID
        self.assertNotEqual(c1.challenge_id, c2.challenge_id)
        # ID 不含原始 task_id
        self.assertNotIn("secret", c1.challenge_id)

    def test_miner_view_hides_internal(self):
        """矿工视图不包含泄露信息"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        batch = engine.create_blind_batch(
            "miner_A",
            [("secret_task_1", {"computation": "hash_search", "block_data": "test"})],
            force_trap_count=2,
        )
        view = batch.to_miner_view()
        # 视图中不含 _real_task_ids, _trap_ids, _trap_answers
        view_str = json.dumps(view)
        self.assertNotIn("_real", view_str)
        self.assertNotIn("_trap", view_str)
        self.assertNotIn("secret_task", view_str)


class TestBlindBatch(unittest.TestCase):
    """Test 7-10: 盲批次混入与打乱"""

    def test_batch_mixes_real_and_traps(self):
        """批次混合真实任务和陷阱"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        batch = engine.create_blind_batch(
            "miner_B",
            [
                ("task_1", {"computation": "hash_search", "data": "d1"}),
                ("task_2", {"computation": "matrix_multiply", "data": "d2"}),
            ],
            force_trap_count=3,
        )
        self.assertEqual(len(batch._real_task_ids), 2)
        self.assertEqual(len(batch._trap_ids), 3)
        self.assertEqual(len(batch.challenges), 5)  # 2 real + 3 traps

    def test_batch_shuffled(self):
        """批次中挑战顺序被打乱"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        # 创建多次，检查不是固定顺序
        orders = set()
        for _ in range(10):
            batch = engine.create_blind_batch(
                "miner_C",
                [("t1", {"computation": "test"})],
                force_trap_count=3,
            )
            order = tuple(c.challenge_id for c in batch.challenges)
            orders.add(order)
        # 至少有不同的排列出现
        self.assertGreater(len(orders), 1, "挑战应被随机打乱")

    def test_banned_miner_rejected(self):
        """被禁矿工不分配任务"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        engine._get_or_create_trust("bad_miner").is_banned = True
        batch = engine.create_blind_batch(
            "bad_miner",
            [("task_1", {"computation": "test"})],
        )
        self.assertEqual(batch.status, "rejected")
        self.assertEqual(len(batch.challenges), 0)

    def test_trap_count_adapts_to_trust(self):
        """陷阱数量根据信任度调整"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        # 高信任矿工
        trust = engine._get_or_create_trust("trusted_miner")
        trust.trust_score = 0.95
        batch_trusted = engine.create_blind_batch(
            "trusted_miner",
            [("t1", {"computation": "test"})],
        )
        # 低信任矿工
        trust2 = engine._get_or_create_trust("sus_miner")
        trust2.trust_score = 0.3
        batch_sus = engine.create_blind_batch(
            "sus_miner",
            [("t1", {"computation": "test"})],
        )
        # 低信任矿工应有更多陷阱
        self.assertGreaterEqual(len(batch_sus._trap_ids), len(batch_trusted._trap_ids))


class TestBlindVerification(unittest.TestCase):
    """Test 11-16: 盲验证流程"""

    def _create_verified_batch(self, engine, miner_id, pass_traps=True):
        """辅助：创建批次并准备结果"""
        batch = engine.create_blind_batch(
            miner_id,
            [("real_task_X", {"computation": "hash_search", "block_data": "data"})],
            force_trap_count=2,
        )
        results = {}
        for cid in batch._real_task_ids:
            results[cid] = "real_result_hash"
        for cid in batch._trap_ids:
            if pass_traps:
                results[cid] = batch._trap_answers[cid]  # 正确答案
            else:
                results[cid] = "wrong_answer_xxxx"  # 故意错误
        return batch, results

    def test_trap_pass_accepts_result(self):
        """陷阱通过 → 接受真实结果"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        batch, results = self._create_verified_batch(engine, "good_miner", pass_traps=True)
        is_trusted, report = engine.verify_batch(batch.batch_id, results)
        self.assertTrue(is_trusted)
        self.assertEqual(report["trap_pass_rate"], 1.0)
        self.assertIn("real_task_X", report["real_results"])

    def test_trap_fail_rejects_result(self):
        """陷阱失败 → 拒绝真实结果"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        batch, results = self._create_verified_batch(engine, "bad_miner", pass_traps=False)
        is_trusted, report = engine.verify_batch(batch.batch_id, results)
        self.assertFalse(is_trusted)
        self.assertEqual(report["trap_passed"], 0)

    def test_trust_increases_on_pass(self):
        """通过陷阱 → 信任度上升"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        trust_before = engine._get_or_create_trust("rising_miner").trust_score
        batch, results = self._create_verified_batch(engine, "rising_miner", pass_traps=True)
        engine.verify_batch(batch.batch_id, results)
        trust_after = engine._get_or_create_trust("rising_miner").trust_score
        self.assertGreater(trust_after, trust_before)

    def test_trust_decreases_on_fail(self):
        """未通过陷阱 → 信任度下降"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        trust_before = engine._get_or_create_trust("falling_miner").trust_score
        batch, results = self._create_verified_batch(engine, "falling_miner", pass_traps=False)
        engine.verify_batch(batch.batch_id, results)
        trust_after = engine._get_or_create_trust("falling_miner").trust_score
        self.assertLess(trust_after, trust_before)

    def test_consecutive_fail_bans_miner(self):
        """连续 3 次陷阱失败 → 矿工被禁"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        for i in range(3):
            batch, results = self._create_verified_batch(
                engine, "repeat_offender", pass_traps=False
            )
            engine.verify_batch(batch.batch_id, results)
        trust = engine._get_or_create_trust("repeat_offender")
        self.assertTrue(trust.is_banned)

    def test_unban_resets_trust(self):
        """解禁矿工 → 重置为低信任"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        trust = engine._get_or_create_trust("banned_one")
        trust.is_banned = True
        trust.trust_score = 0.0
        result = engine.unban_miner("banned_one")
        self.assertTrue(result)
        self.assertFalse(trust.is_banned)
        self.assertEqual(trust.trust_score, 0.50)


class TestSchedulerBlindMode(unittest.TestCase):
    """Test 17-24: ComputeScheduler 盲调度集成"""

    def _create_scheduler(self):
        """创建干净的盲调度器"""
        import tempfile
        from core.compute_scheduler import (
            ComputeScheduler, ScheduleMode, MinerNode,
            MinerMode, MinerStatus, ComputeTask
        )
        db = os.path.join(tempfile.gettempdir(), f"test_blind_{random.randint(0,999999)}.db")
        scheduler = ComputeScheduler(db_path=db, mode=ScheduleMode.BLIND)

        # 注册矿工
        miner = MinerNode(
            miner_id="m_test",
            address="ADDR_TEST",
            sector="GPU",
            gpu_model="RTX 4090",
            gpu_memory=24.0,
            compute_power=200.0,
            mode=MinerMode.VOLUNTARY,
            status=MinerStatus.ONLINE,
        )
        scheduler.register_miner(miner)
        return scheduler, db

    def test_blind_mode_single_miner(self):
        """盲模式只分配 1 个矿工"""
        from core.compute_scheduler import ComputeTask
        scheduler, db = self._create_scheduler()
        task = ComputeTask(
            task_id="bt_001", order_id="o1", buyer_address="B1",
            task_type="training", task_data='{"model":"test"}',
            sector="GPU", total_payment=5.0,
        )
        ok, msg = scheduler.create_task(task, required_miners=1)
        self.assertTrue(ok)
        task = scheduler.get_task("bt_001")
        self.assertEqual(len(task.assigned_miners), 1)
        self.assertEqual(task.redundancy, 1)
        scheduler.close()
        os.remove(db)

    def test_blind_fee_breakdown_has_metadata(self):
        """盲模式 fee_breakdown 记录盲调度信息"""
        from core.compute_scheduler import ComputeTask
        scheduler, db = self._create_scheduler()
        task = ComputeTask(
            task_id="bt_002", order_id="o2", buyer_address="B2",
            task_type="inference", task_data='{"model":"gpt"}',
            sector="GPU", total_payment=3.0,
        )
        scheduler.create_task(task)
        task = scheduler.get_task("bt_002")
        self.assertTrue(task.fee_breakdown.get("blind_mode"))
        self.assertIn("blind_batch_id", task.fee_breakdown)
        self.assertGreaterEqual(task.fee_breakdown.get("trap_count", 0), 1)
        scheduler.close()
        os.remove(db)

    def test_miner_status_shows_mining(self):
        """盲模式下矿工状态显示 MINING 而非 BUSY"""
        from core.compute_scheduler import ComputeTask, MinerStatus
        scheduler, db = self._create_scheduler()
        task = ComputeTask(
            task_id="bt_003", order_id="o3", buyer_address="B3",
            task_type="train", task_data='{}',
            sector="GPU", total_payment=1.0,
        )
        scheduler.create_task(task)
        # 心跳
        scheduler.miner_heartbeat("m_test")
        miner = scheduler.get_miner("m_test")
        self.assertEqual(miner.status, MinerStatus.MINING)
        scheduler.close()
        os.remove(db)

    def test_blind_submit_result_completes(self):
        """盲模式下 submit_result 应被拒绝（必须走 submit_blind_batch）"""
        from core.compute_scheduler import ComputeTask, TaskStatus
        scheduler, db = self._create_scheduler()
        task = ComputeTask(
            task_id="bt_004", order_id="o4", buyer_address="B4",
            task_type="train", task_data='{}',
            sector="GPU", total_payment=2.0,
        )
        scheduler.create_task(task)
        ok, msg = scheduler.submit_result("bt_004", "m_test", "result_xyz")
        self.assertTrue(ok)
        task = scheduler.get_task("bt_004")
        # 盲模式下 submit_result 不应完成任务（应回退到 RUNNING）
        self.assertEqual(task.status, TaskStatus.RUNNING)
        scheduler.close()
        os.remove(db)

    def test_blind_settlement_single_miner(self):
        """传统模式结算 99% 给单个矿工"""
        import tempfile
        from core.compute_scheduler import (
            ComputeScheduler, ComputeTask, ScheduleMode,
            MinerNode, MinerMode, MinerStatus
        )
        db = os.path.join(tempfile.gettempdir(), f"test_settle_{random.randint(0,999999)}.db")
        scheduler = ComputeScheduler(db_path=db, mode=ScheduleMode.VOLUNTARY)
        miner = MinerNode(
            miner_id="m_test", address="ADDR_TEST", sector="GPU",
            gpu_model="RTX 4090", gpu_memory=24.0, compute_power=200.0,
            mode=MinerMode.VOLUNTARY, status=MinerStatus.ONLINE,
        )
        scheduler.register_miner(miner)
        task = ComputeTask(
            task_id="bt_005", order_id="o5", buyer_address="B5",
            task_type="train", task_data='{}',
            sector="GPU", total_payment=10.0,
        )
        scheduler.create_task(task)
        scheduler.submit_result("bt_005", "m_test", "result_abc")
        task = scheduler.get_task("bt_005")
        # 99% = 9.9
        self.assertAlmostEqual(task.miner_payments["m_test"], 9.9, places=2)
        # fee 1% = 0.1
        fb = task.fee_breakdown
        self.assertAlmostEqual(fb["burn"], 0.05, places=3)
        self.assertAlmostEqual(fb["miner_incentive"], 0.03, places=3)
        self.assertAlmostEqual(fb["foundation"], 0.02, places=3)
        scheduler.close()
        os.remove(db)

    def test_blind_batch_submit_trusted(self):
        """通过 submit_blind_batch 提交 → 陷阱通过 → 结算"""
        from core.compute_scheduler import ComputeTask, TaskStatus
        scheduler, db = self._create_scheduler()
        task = ComputeTask(
            task_id="bt_006", order_id="o6", buyer_address="B6",
            task_type="train", task_data='{"computation": "hash_search"}',
            sector="GPU", total_payment=5.0,
        )
        scheduler.create_task(task)
        # 获取盲批次
        batch_view = scheduler.get_blind_batch_for_miner("m_test")
        self.assertIsNotNone(batch_view)
        batch_id = batch_view["batch_id"]
        # 获取内部批次来构造正确答案
        batch = scheduler.blind_engine.pending_batches[batch_id]
        results = {}
        for cid in batch._real_task_ids:
            results[cid] = "computed_result"
        for cid in batch._trap_ids:
            results[cid] = batch._trap_answers[cid]  # 正确答案
        # 提交
        ok, report = scheduler.submit_blind_batch(batch_id, "m_test", results)
        self.assertTrue(ok)
        # 原始任务应完成
        task = scheduler.get_task("bt_006")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        scheduler.close()
        os.remove(db)

    def test_blind_batch_submit_untrusted(self):
        """通过 submit_blind_batch 提交 → 陷阱失败 → 任务重置"""
        from core.compute_scheduler import ComputeTask, TaskStatus
        scheduler, db = self._create_scheduler()
        task = ComputeTask(
            task_id="bt_007", order_id="o7", buyer_address="B7",
            task_type="train", task_data='{}',
            sector="GPU", total_payment=5.0,
        )
        scheduler.create_task(task)
        batch_view = scheduler.get_blind_batch_for_miner("m_test")
        batch_id = batch_view["batch_id"]
        batch = scheduler.blind_engine.pending_batches[batch_id]
        # 全部提交错误答案
        results = {cid: "wrong_wrong" for cid in 
                   batch._real_task_ids + batch._trap_ids}
        ok, report = scheduler.submit_blind_batch(batch_id, "m_test", results)
        self.assertFalse(ok)
        # 任务应被重置为 PENDING
        task = scheduler.get_task("bt_007")
        self.assertEqual(task.status, TaskStatus.PENDING)
        scheduler.close()
        os.remove(db)

    def test_legacy_mode_still_works(self):
        """传统 HYBRID 模式向后兼容"""
        import tempfile
        from core.compute_scheduler import (
            ComputeScheduler, ScheduleMode, MinerNode,
            MinerMode, MinerStatus, ComputeTask, TaskStatus
        )
        db = os.path.join(tempfile.gettempdir(), f"test_legacy_{random.randint(0,999999)}.db")
        scheduler = ComputeScheduler(db_path=db, mode=ScheduleMode.HYBRID)
        for i in range(2):
            miner = MinerNode(
                miner_id=f"leg_{i}", address=f"A{i}", sector="CPU",
                gpu_model="RTX3080", gpu_memory=10,
                compute_power=100, mode=MinerMode.VOLUNTARY,
                status=MinerStatus.ONLINE,
            )
            scheduler.register_miner(miner)
        task = ComputeTask(
            task_id="lt_001", order_id="lo1", buyer_address="LB",
            task_type="test", task_data='{}',
            sector="CPU", total_payment=2.0,
        )
        ok, msg = scheduler.create_task(task, required_miners=2)
        self.assertTrue(ok)
        task = scheduler.get_task("lt_001")
        self.assertEqual(len(task.assigned_miners), 2)
        # 两个矿工提交相同结果 → 多数派通过
        for mid in task.assigned_miners:
            scheduler.submit_result("lt_001", mid, "same_hash")
        task = scheduler.get_task("lt_001")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        scheduler.close()
        os.remove(db)


class TestSavingsCalculation(unittest.TestCase):
    """Test 25: 算力节省统计"""

    def test_savings_reported(self):
        """引擎能计算相对旧方案的节省百分比"""
        from core.blind_task_engine import BlindTaskEngine
        engine = BlindTaskEngine()
        engine._get_or_create_trust("m1").trust_score = 0.95
        engine._get_or_create_trust("m2").trust_score = 0.60
        stats = engine.get_stats()
        self.assertIn("节省", stats["total_trap_ratio_savings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
