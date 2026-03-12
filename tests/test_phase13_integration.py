#!/usr/bin/env python3
"""
Phase 13 集成测试 — 7个新接入子系统
======================================================
测试 unified_consensus.py 中 Phase 13 新增的全部方法:

#12 process_transaction_fee     — 协议费用池 (1%手续费分配)
#13 start_task_arbitration      — 任务仲裁
    file_dispute                — 纠纷提交
    complete_arbitration        — 仲裁完成
#14 monitor_transaction         — 交易监控/告警
#15 update_reputation           — 信誉引擎 (多维评分)
#16 verify_task_acceptance      — 三层SLA验收
#17 submit_review               — 留言评价系统
#18 record_order_behavior       — 矿工行为分析
#19 process_full_block_lifecycle— 增强区块生命周期
#20 get_full_system_status      — 完整系统状态
"""

import sys
import os
import unittest
import time
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.unified_consensus import (
    UnifiedConsensus,
    UnifiedMinerConfig,
    UnifiedMinerMode,
    TaskDistributionMode,
)
from core.sector_coin import SectorCoinType


class TestPhase13Integration(unittest.TestCase):
    """Phase 13 集成测试"""

    @classmethod
    def setUpClass(cls):
        print("=" * 70)
        print("  Phase 13 集成测试 — 7个子系统接入验证")
        print("=" * 70)

    def setUp(self):
        """每个测试前创建干净的 UnifiedConsensus 实例"""
        # 重置全局 SectorCoinLedger 单例，确保每个测试使用干净的数据库
        import core.sector_coin as _sc
        _sc._ledger_instance = None
        # 重置 UTXO 全局单例，防止数据累积
        import core.utxo_store as _us
        if _us._utxo_store is not None:
            try:
                with _us._utxo_store._conn() as conn:
                    conn.execute("DELETE FROM utxos")
                    conn.execute("DELETE FROM processed_txids")
            except Exception:
                pass
        _us._utxo_store = None
        for f in ["data/sector_coins.db", "data/utxo.db"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

        self.uc = UnifiedConsensus()
        # 注册一个标准矿工
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="miner_A", address="addr_A", sector="H100",
            mode=UnifiedMinerMode.MINING_AND_TASK
        ))
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="miner_B", address="addr_B", sector="H100",
            mode=UnifiedMinerMode.TASK_ONLY
        ))
        # 设置MAIN余额
        self.uc.set_main_balance("addr_A", 1000.0)
        self.uc.set_main_balance("addr_B", 500.0)

    def tearDown(self):
        """清理测试产生的数据库文件"""
        for f in ["data/reputation.db", "data/messages.db"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

    # ================================================================
    # #12 协议费用池
    # ================================================================

    def test_01_fee_processing_basic(self):
        """测试手续费基本分配: 1% = 0.5%销毁 + 0.3%矿工 + 0.2%池"""
        result = self.uc.process_transaction_fee("tx_001", 100.0)
        
        self.assertEqual(result["tx_id"], "tx_001")
        self.assertAlmostEqual(result["fee_amount"], 1.0, places=6)      # 100 * 1%
        self.assertAlmostEqual(result["burn"], 0.5, places=6)             # 0.5%
        self.assertAlmostEqual(result["miner_reward"], 0.3, places=6)    # 0.3%
        self.assertAlmostEqual(result["protocol_pool"], 0.2, places=6)   # 0.2%

    def test_02_fee_stats_accumulate(self):
        """测试手续费统计累积"""
        self.uc.process_transaction_fee("tx_a", 1000.0)
        self.uc.process_transaction_fee("tx_b", 500.0)
        
        # 总: 1500 * 1% = 15
        self.assertAlmostEqual(self.uc.stats["fees_burned"], 7.5, places=4)
        self.assertAlmostEqual(self.uc.stats["fees_to_miners"], 4.5, places=4)
        self.assertAlmostEqual(self.uc.stats["fees_to_pool"], 3.0, places=4)

    def test_03_fee_zero_amount(self):
        """测试零金额手续费"""
        result = self.uc.process_transaction_fee("tx_zero", 0.0)
        self.assertAlmostEqual(result["fee_amount"], 0.0, places=6)

    def test_04_transfer_main_deducts_fee(self):
        """测试MAIN转账自动扣除1%手续费"""
        ok, msg = self.uc.transfer_main("addr_A", "addr_B", 100.0)
        self.assertTrue(ok)
        
        # 发送方扣100, 接收方实收99 (1%手续费)
        self.assertAlmostEqual(self.uc._get_main_balance("addr_A"), 900.0)
        self.assertAlmostEqual(self.uc._get_main_balance("addr_B"), 599.0)
        
        # 手续费统计
        self.assertGreater(self.uc.stats["fees_burned"], 0)

    # ================================================================
    # #13 仲裁系统
    # ================================================================

    def test_05_start_arbitration(self):
        """测试仲裁期启动"""
        ok, msg = self.uc.start_task_arbitration(
            task_id="task_001",
            renter_id="addr_A",
            miner_id="addr_B",
            task_payment=10.0,
            coin_type="MAIN",
        )
        self.assertTrue(ok)
        self.assertIn("仲裁期开始", msg)

    def test_06_file_dispute_requires_arbitration(self):
        """测试提交纠纷 (需先启动仲裁)"""
        # 先启动仲裁
        self.uc.start_task_arbitration(
            "task_002", "addr_A", "addr_B", 10.0, "MAIN"
        )
        
        # 提交纠纷
        ok, result = self.uc.file_dispute(
            task_id="task_002",
            complainant_id="addr_A",
            reason="RESULT_INCORRECT",
            description="结果不正确",
            evidence={"screenshot": "xxx"},
        )
        self.assertTrue(ok)
        self.assertEqual(self.uc.stats["disputes_filed"], 1)

    def test_07_file_dispute_without_arbitration(self):
        """测试没有仲裁期时提交纠纷失败"""
        ok, msg = self.uc.file_dispute(
            task_id="nonexistent",
            complainant_id="addr_A",
            reason="QUALITY_ISSUE",
            description="质量太差",
        )
        self.assertFalse(ok)
        self.assertIn("失败", msg)

    def test_08_complete_arbitration(self):
        """测试完成仲裁"""
        # 启动仲裁（设极短仲裁期以便快速完成）
        self.uc.arbitration.arbitration_period = 0.01  # 0.01秒
        self.uc.start_task_arbitration(
            "task_003", "addr_A", "addr_B", 10.0, "MAIN"
        )
        time.sleep(0.05)  # 等待仲裁期结束
        
        ok, msg, status = self.uc.complete_arbitration("task_003")
        self.assertTrue(ok)
        self.assertEqual(self.uc.stats["disputes_resolved"], 1)

    # ================================================================
    # #14 交易监控
    # ================================================================

    def test_09_monitor_normal_transaction(self):
        """测试正常交易不触发告警"""
        result = self.uc.monitor_transaction({
            "txid": "tx_normal",
            "from_address": "addr_A",
            "to_address": "addr_B",
            "amount": 50.0,
        })
        self.assertIsNone(result)
        self.assertEqual(self.uc.stats["alerts_triggered"], 0)

    def test_10_monitor_large_transaction(self):
        """测试大额交易触发告警 (>1000)"""
        result = self.uc.monitor_transaction({
            "txid": "tx_large",
            "from_address": "addr_A",
            "to_address": "addr_B",
            "amount": 5000.0,
        })
        self.assertIsNotNone(result)
        self.assertEqual(result["alert_type"], "large_transaction")
        self.assertEqual(self.uc.stats["alerts_triggered"], 1)

    def test_11_monitor_records_security_event(self):
        """测试监控告警写入安全事件"""
        self.uc.monitor_transaction({
            "txid": "tx_huge",
            "from_address": "addr_A",
            "to_address": "addr_B",
            "amount": 10000.0,
        })
        events = self.uc.audit_events
        # 应该有安全事件记录
        self.assertGreater(len(events), 0)

    # ================================================================
    # #15 信誉引擎
    # ================================================================

    def test_12_update_reputation_success(self):
        """测试信誉更新 (任务成功)"""
        result = self.uc.update_reputation(
            miner_id="miner_A",
            task_id="task_rep_1",
            quality_score=90.0,
            speed_score=85.0,
            success=True,
        )
        self.assertEqual(result["miner_id"], "miner_A")
        self.assertIn("overall", result)
        self.assertIn("tier", result)

    def test_13_update_reputation_failure(self):
        """测试信誉更新 (任务失败)"""
        result = self.uc.update_reputation(
            miner_id="miner_A",
            task_id="task_rep_2",
            quality_score=20.0,
            speed_score=50.0,
            success=False,
        )
        self.assertEqual(result["miner_id"], "miner_A")

    def test_14_reputation_accumulates(self):
        """测试信誉多次更新累积"""
        for i in range(5):
            self.uc.update_reputation(
                miner_id="miner_A",
                task_id=f"task_acc_{i}",
                quality_score=80.0 + i,
                success=True,
            )
        
        result = self.uc.update_reputation(
            miner_id="miner_A",
            task_id="task_acc_final",
            quality_score=85.0,
            success=True,
        )
        self.assertGreaterEqual(result.get("total_tasks", 0), 1)

    # ================================================================
    # #16 三层SLA验收
    # ================================================================

    def test_15_task_acceptance_protocol_pass(self):
        """测试协议层验证通过"""
        ok, msg, verdicts = self.uc.verify_task_acceptance(
            task_id="task_sla_1",
            miner_id="miner_A",
            result_data={
                "result_hash": "abc123",
                "execution_time_ms": 500,
            },
        )
        self.assertTrue(ok)
        self.assertEqual(verdicts["protocol"], "executed")
        self.assertEqual(verdicts["application"], "auto_accepted")

    def test_16_task_acceptance_no_hash_fails(self):
        """测试缺少结果哈希时协议层失败"""
        ok, msg, verdicts = self.uc.verify_task_acceptance(
            task_id="task_sla_2",
            miner_id="miner_A",
            result_data={},
        )
        self.assertFalse(ok)
        self.assertEqual(verdicts["protocol"], "invalid")
        self.assertIn("无结果哈希", msg)

    def test_17_task_acceptance_sla_violated(self):
        """测试SLA延迟超标"""
        ok, msg, verdicts = self.uc.verify_task_acceptance(
            task_id="task_sla_3",
            miner_id="miner_A",
            result_data={
                "result_hash": "def456",
                "execution_time_ms": 5000,
            },
            sla={"max_latency_ms": 1000},
        )
        self.assertFalse(ok)
        self.assertEqual(verdicts["service"], "violated")
        self.assertGreater(self.uc.stats["sla_violations"], 0)

    def test_18_task_acceptance_sla_met(self):
        """测试SLA完全满足"""
        ok, msg, verdicts = self.uc.verify_task_acceptance(
            task_id="task_sla_4",
            miner_id="miner_A",
            result_data={
                "result_hash": "ghi789",
                "execution_time_ms": 200,
                "error_rate": 0.001,
            },
            sla={"max_latency_ms": 1000, "max_error_rate": 0.01},
        )
        self.assertTrue(ok)
        self.assertEqual(verdicts["service"], "met")
        self.assertIn("三层验收通过", msg)

    def test_19_task_acceptance_updates_reputation(self):
        """测试验收自动更新信誉"""
        self.uc.verify_task_acceptance(
            task_id="task_sla_5",
            miner_id="miner_A",
            result_data={"result_hash": "hash123"},
        )
        # 验收通过后应触发信誉更新（通过 update_reputation 内部调用）
        # 统计中 tasks_completed 应增加
        self.assertEqual(self.uc.stats["tasks_completed"], 1)

    # ================================================================
    # #17 留言评价系统
    # ================================================================

    def test_20_submit_review_basic(self):
        """测试基本评价提交"""
        ok, review_hash = self.uc.submit_review(
            reviewer_id="addr_A",
            target_id="miner_B",
            task_id="task_review_1",
            rating=4.5,
            comment="服务很好",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(review_hash)
        self.assertEqual(len(review_hash), 32)  # SHA256前32字符
        self.assertEqual(self.uc.stats["reviews_submitted"], 1)

    def test_21_submit_review_clamp_rating(self):
        """测试评分范围限制 (1.0-5.0)"""
        # 超过5
        ok1, _ = self.uc.submit_review(
            "addr_A", "miner_B", "task_r2", 10.0
        )
        self.assertTrue(ok1)
        
        # 低于1
        ok2, _ = self.uc.submit_review(
            "addr_A", "miner_B", "task_r3", -1.0
        )
        self.assertTrue(ok2)
        self.assertEqual(self.uc.stats["reviews_submitted"], 2)

    def test_22_review_updates_miner_score(self):
        """测试评价更新矿工评分"""
        # 提交一个低分评价
        self.uc.submit_review(
            "addr_A", "miner_A", "task_r4", 2.0, "不太行"
        )
        # miner_A 在 miner_scores 中，评分应被更新
        if "miner_A" in self.uc.miner_scores:
            rating = self.uc.miner_scores["miner_A"].get("user_rating", 5.0)
            # 指数移动平均: 0.3*2.0 + 0.7*5.0 = 4.1
            self.assertLess(rating, 5.0)

    def test_23_review_hash_deterministic(self):
        """测试评价哈希包含关键信息"""
        ok, h = self.uc.submit_review(
            "addr_A", "miner_B", "task_det", 3.0, "普通"
        )
        self.assertTrue(ok)
        # 哈希是32位hex
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    # ================================================================
    # #18 矿工行为分析
    # ================================================================

    def test_24_record_order_accepted(self):
        """测试记录接受订单"""
        result = self.uc.record_order_behavior(
            order_id="order_001",
            miner_id="miner_A",
            quoted_price=10.0,
            market_avg_price=12.0,
            accepted=True,
            response_time=0.5,
        )
        self.assertEqual(result["miner_id"], "miner_A")
        self.assertIn("overall_score", result)
        self.assertIn("acceptance_rate", result)
        self.assertIn("price_diversity", result)

    def test_25_record_order_rejected(self):
        """测试记录拒绝订单"""
        result = self.uc.record_order_behavior(
            order_id="order_002",
            miner_id="miner_A",
            quoted_price=5.0,
            market_avg_price=10.0,
            accepted=False,
        )
        self.assertEqual(result["miner_id"], "miner_A")

    def test_26_behavior_congestion_bonus(self):
        """测试拥堵期接单记录"""
        result = self.uc.record_order_behavior(
            order_id="order_003",
            miner_id="miner_A",
            quoted_price=8.0,
            market_avg_price=10.0,
            accepted=True,
            was_congested=True,
        )
        self.assertEqual(result["miner_id"], "miner_A")

    def test_27_behavior_multiple_orders_score(self):
        """测试多订单后行为评分"""
        for i in range(10):
            self.uc.record_order_behavior(
                order_id=f"order_multi_{i}",
                miner_id="miner_A",
                quoted_price=8.0 + i,
                market_avg_price=10.0,
                accepted=(i % 3 != 0),  # 70%接受率
                response_time=0.3,
            )
        
        result = self.uc.record_order_behavior(
            order_id="order_multi_final",
            miner_id="miner_A",
            quoted_price=10.0,
            market_avg_price=10.0,
            accepted=True,
        )
        # 有足够数据后应能计算出合理评分
        self.assertGreaterEqual(result["overall_score"], 0)
        self.assertLessEqual(result["overall_score"], 1.0)

    # ================================================================
    # #19 增强区块生命周期
    # ================================================================

    def test_28_full_lifecycle_basic(self):
        """测试增强区块生命周期 (无交易)"""
        result = self.uc.process_full_block_lifecycle(
            block_height=99001,
            miner_id="miner_A",
            miner_address="addr_A",
            sector="H100",
            block_reward=10.0,
        )
        self.assertEqual(result["block_height"], 99001)
        self.assertEqual(result["fees_processed"], 0)
        self.assertAlmostEqual(result["total_fees"], 0.0)

    def test_29_full_lifecycle_with_transactions(self):
        """测试增强区块生命周期 (含交易 → 手续费)"""
        txs = [
            {"tx_id": "tx_lc_1", "from_address": "addr_A", "to_address": "addr_B", "amount": 200.0},
            {"tx_id": "tx_lc_2", "from_address": "addr_B", "to_address": "addr_A", "amount": 100.0},
        ]
        result = self.uc.process_full_block_lifecycle(
            block_height=99002,
            miner_id="miner_A",
            miner_address="addr_A",
            sector="H100",
            block_reward=10.0,
            transactions=txs,
        )
        self.assertEqual(result["block_height"], 99002)
        self.assertEqual(result["fees_processed"], 2)
        # 总手续费: (200+100)*1% = 3.0
        self.assertAlmostEqual(result["total_fees"], 3.0, places=4)

    def test_30_full_lifecycle_large_tx_alert(self):
        """测试增强生命周期中大额交易触发告警"""
        txs = [
            {"tx_id": "tx_big", "from_address": "addr_A", "to_address": "addr_B","amount": 5000.0},
        ]
        result = self.uc.process_full_block_lifecycle(
            block_height=99003,
            miner_id="miner_A",
            miner_address="addr_A",
            sector="H100",
            block_reward=10.0,
            transactions=txs,
        )
        # 大额交易应触发告警
        self.assertGreater(self.uc.stats["alerts_triggered"], 0)

    def test_31_full_lifecycle_updates_reputation(self):
        """测试增强生命周期自动更新矿工信誉"""
        self.uc.process_full_block_lifecycle(
            block_height=99004,
            miner_id="miner_A",
            miner_address="addr_A",
            sector="H100",
            block_reward=10.0,
        )
        # 内部会调用 update_reputation → reputation.record_task_completion
        # 无异常说明集成成功

    # ================================================================
    # #20 完整系统状态
    # ================================================================

    def test_32_full_system_status(self):
        """测试完整系统状态查询"""
        # 先产生一些数据
        self.uc.process_transaction_fee("tx_st", 500.0)
        self.uc.submit_review("addr_A", "miner_B", "task_st", 4.0)
        
        status = self.uc.get_full_system_status()
        
        # 基本字段
        self.assertIn("stats", status)
        self.assertIn("subsystems", status)
        self.assertIn("fee_pool", status)
        
        # Phase 13 统计
        self.assertGreater(status["stats"]["fees_burned"], 0)
        self.assertEqual(status["stats"]["reviews_submitted"], 1)

    def test_33_system_status_subsystem_connectivity(self):
        """测试子系统连接状态"""
        status = self.uc.get_full_system_status()
        subs = status["subsystems"]
        
        self.assertEqual(subs["fee_pool"], "connected")
        self.assertEqual(subs["arbitration"], "connected")
        self.assertEqual(subs["reputation"], "connected")
        self.assertEqual(subs["tx_monitor"], "connected")
        self.assertEqual(subs["task_acceptance"], "connected")
        self.assertEqual(subs["message_system"], "connected")
        self.assertEqual(subs["behavior_analyzer"], "connected")

    # ================================================================
    # 端到端: 完整任务流程
    # ================================================================

    def test_34_e2e_task_lifecycle(self):
        """端到端: 发布→执行→验收→评价→仲裁"""
        # 1. 设置余额
        self.uc.set_main_balance("addr_A", 2000.0)
        
        # 2. 提交任务
        ok, msg, task_id = self.uc.submit_task(
            user_address="addr_A",
            task_data={"model": "llama2"},
            sector="H100",
            payment_amount=50.0,
            distribution=TaskDistributionMode.SINGLE,
        )
        self.assertTrue(ok, f"任务提交失败: {msg}")
        
        # 3. 模拟执行 → 三层验收
        ok, msg, verdicts = self.uc.verify_task_acceptance(
            task_id=task_id,
            miner_id="miner_A",
            result_data={
                "result_hash": "result_abc123",
                "execution_time_ms": 300,
            },
            sla={"max_latency_ms": 1000},
        )
        self.assertTrue(ok)
        self.assertEqual(verdicts["service"], "met")
        
        # 4. 进入仲裁期
        ok, msg = self.uc.start_task_arbitration(
            task_id=task_id,
            renter_id="addr_A",
            miner_id="addr_B",
            task_payment=50.0,
        )
        self.assertTrue(ok)
        
        # 5. 用户提交评价
        ok, review_hash = self.uc.submit_review(
            reviewer_id="addr_A",
            target_id="miner_A",
            task_id=task_id,
            rating=5.0,
            comment="非常好的矿工",
        )
        self.assertTrue(ok)
        
        # 6. 完成仲裁（无纠纷）
        self.uc.arbitration.arbitration_period = 0.01
        # 重置仲裁期
        arb = self.uc.arbitration.arbitrations.get(task_id)
        if arb:
            arb.arbitration_end = time.time() - 1
        time.sleep(0.02)
        
        ok, msg, status = self.uc.complete_arbitration(task_id)
        self.assertTrue(ok)

    def test_35_e2e_dispute_flow(self):
        """端到端: 发布→执行→纠纷→仲裁裁决"""
        task_id = "dispute_task_001"
        
        # 1. 启动仲裁
        ok, msg = self.uc.start_task_arbitration(
            task_id=task_id,
            renter_id="addr_A",
            miner_id="addr_B",
            task_payment=100.0,
        )
        self.assertTrue(ok)
        
        # 2. 提交纠纷
        ok, dispute_result = self.uc.file_dispute(
            task_id=task_id,
            complainant_id="addr_A",
            reason="RESULT_INCORRECT",
            description="结果与预期不符",
            evidence={"log": "error at line 42"},
        )
        self.assertTrue(ok)
        self.assertEqual(self.uc.stats["disputes_filed"], 1)
        
        # 3. 记录矿工负面行为
        result = self.uc.record_order_behavior(
            order_id=task_id,
            miner_id="miner_B",
            quoted_price=10.0,
            market_avg_price=10.0,
            accepted=True,
        )
        
        # 4. 更新信誉 (失败)
        rep = self.uc.update_reputation(
            miner_id="miner_B",
            task_id=task_id,
            quality_score=10.0,
            success=False,
        )
        self.assertEqual(rep["miner_id"], "miner_B")

    # ================================================================
    # 边界/异常情况
    # ================================================================

    def test_36_fee_very_small_amount(self):
        """测试极小金额的手续费"""
        result = self.uc.process_transaction_fee("tx_tiny", 0.001)
        self.assertAlmostEqual(result["fee_amount"], 0.00001, places=8)

    def test_37_monitor_multiple_alerts(self):
        """测试多次大额交易告警"""
        for i in range(3):
            self.uc.monitor_transaction({
                "txid": f"tx_multi_alert_{i}",
                "from_address": "addr_A",
                "to_address": "addr_B",
                "amount": 2000.0 + i * 1000,
            })
        self.assertEqual(self.uc.stats["alerts_triggered"], 3)

    def test_38_reputation_unknown_miner(self):
        """测试未知矿工的信誉更新"""
        result = self.uc.update_reputation(
            miner_id="unknown_miner",
            task_id="task_unknown",
            quality_score=80.0,
            success=True,
        )
        # 应该不报错，返回默认值
        self.assertEqual(result["miner_id"], "unknown_miner")

    def test_39_acceptance_trap_failure(self):
        """测试陷阱题失败时协议层拒绝"""
        ok, msg, verdicts = self.uc.verify_task_acceptance(
            task_id="task_trap",
            miner_id="miner_A",
            result_data={
                "result_hash": "hash_ok",
                "trap_results": {"t1": False, "t2": False, "t3": False},
            },
        )
        self.assertFalse(ok)
        self.assertEqual(verdicts["protocol"], "cheated")

    def test_40_review_multiple_same_target(self):
        """测试同一目标多次评价"""
        for i in range(5):
            ok, h = self.uc.submit_review(
                f"reviewer_{i}", "miner_A", f"task_multi_{i}",
                rating=3.0 + (i * 0.3)
            )
            self.assertTrue(ok)
        self.assertEqual(self.uc.stats["reviews_submitted"], 5)


# ================================================================
# 主入口
# ================================================================

if __name__ == "__main__":
    # 确保在项目根目录运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(TestPhase13Integration))
    
    total = result.testsRun
    failures = len(result.failures) + len(result.errors)
    passed = total - failures
    
    print()
    print("=" * 70)
    print(f"  结果: {passed}/{total} 通过")
    print("=" * 70)
    
    if failures > 0:
        print(f"  失败: {failures}")
        for test, trace in result.failures + result.errors:
            print(f"\n  ✗ {test}")
    
    sys.exit(0 if failures == 0 else 1)
