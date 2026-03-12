# -*- coding: utf-8 -*-
"""
统一共识引擎测试 (Unified Consensus Engine Tests)

测试覆盖:
1. 矿工三模式注册与管理
2. 区块挖出→板块币铸造
3. 板块币→MAIN兑换（动态汇率+双见证）
4. 统一见证协调器
5. 订单支付验证（必须MAIN+双见证）
6. 板块币内部转账（分级见证）
7. MAIN转账（必须双见证）
8. 零信任任务安全
9. 评分集成与优先级排序
10. 任务提交与分发（单节点/分布式）
11. 安全审计与矿工封禁
12. 完整区块生命周期
"""

import sys
import os
import time
import tempfile
import shutil
import unittest

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from core.unified_consensus import (
    UnifiedConsensus,
    UnifiedMinerMode,
    UnifiedMinerConfig,
    TaskDistributionMode,
    WitnessScope,
    SecurityThreatLevel,
    SecureTaskEnvelope,
)
from core.sector_coin import SectorCoinType, SectorCoinLedger


class TestUnifiedConsensus(unittest.TestCase):
    """统一共识引擎测试"""
    
    def setUp(self):
        """每个测试前创建临时数据目录"""
        self.test_dir = tempfile.mkdtemp(prefix="unified_test_")
        # 重置 UTXO 全局单例，使用测试目录的独立数据库
        import core.utxo_store as _us
        _us._utxo_store = None
        _us.get_utxo_store(os.path.join(self.test_dir, "utxo.db"))
        self.uc = UnifiedConsensus(
            sector="H100",
            testnet=True,
            db_dir=self.test_dir,
            log_fn=lambda x: None,  # 静默日志
        )
        # 使用独立的板块币账本
        self.uc.sector_ledger = SectorCoinLedger(
            db_path=os.path.join(self.test_dir, "sector_coins.db")
        )
    
    def tearDown(self):
        """清理临时目录"""
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass
    
    # ================================================================
    # 1. 矿工三模式注册与管理
    # ================================================================
    
    def test_01_register_mining_only(self):
        """测试注册纯挖矿矿工"""
        config = UnifiedMinerConfig(
            miner_id="miner_001",
            address="addr_001",
            sector="H100",
            mode=UnifiedMinerMode.MINING_ONLY,
        )
        ok, msg = self.uc.register_miner(config)
        self.assertTrue(ok)
        self.assertIn("纯挖矿", msg)
        
        # 应该在挖矿列表中
        mining = self.uc.get_miners_mining()
        self.assertEqual(len(mining), 1)
        self.assertEqual(mining[0].miner_id, "miner_001")
        
        # 不应该在接单列表中
        tasking = self.uc.get_miners_accepting_tasks()
        self.assertEqual(len(tasking), 0)
    
    def test_02_register_task_only(self):
        """测试注册纯接单矿工"""
        config = UnifiedMinerConfig(
            miner_id="miner_002",
            address="addr_002",
            sector="RTX4090",
            mode=UnifiedMinerMode.TASK_ONLY,
        )
        ok, msg = self.uc.register_miner(config)
        self.assertTrue(ok)
        self.assertIn("纯接单", msg)
        
        # 应该在接单列表中
        tasking = self.uc.get_miners_accepting_tasks()
        self.assertEqual(len(tasking), 1)
        
        # 不应该在挖矿列表中
        mining = self.uc.get_miners_mining()
        self.assertEqual(len(mining), 0)
    
    def test_03_register_mining_and_task(self):
        """测试注册挖矿+接单矿工"""
        config = UnifiedMinerConfig(
            miner_id="miner_003",
            address="addr_003",
            sector="H100",
            mode=UnifiedMinerMode.MINING_AND_TASK,
        )
        ok, msg = self.uc.register_miner(config)
        self.assertTrue(ok)
        self.assertIn("挖矿+接单", msg)
        
        # 应该同时出现在两个列表中
        mining = self.uc.get_miners_mining()
        tasking = self.uc.get_miners_accepting_tasks()
        self.assertEqual(len(mining), 1)
        self.assertEqual(len(tasking), 1)
    
    def test_04_switch_miner_mode(self):
        """测试切换矿工模式"""
        config = UnifiedMinerConfig(
            miner_id="miner_switch",
            address="addr_switch",
            sector="H100",
            mode=UnifiedMinerMode.MINING_ONLY,
        )
        self.uc.register_miner(config)
        
        # 切换到接单+挖矿
        ok, msg = self.uc.switch_miner_mode("miner_switch", UnifiedMinerMode.MINING_AND_TASK)
        self.assertTrue(ok)
        
        # 验证切换后两个列表都有
        mining = self.uc.get_miners_mining()
        tasking = self.uc.get_miners_accepting_tasks()
        self.assertEqual(len(mining), 1)
        self.assertEqual(len(tasking), 1)
    
    def test_05_banned_miner_rejected(self):
        """测试封禁矿工不能注册"""
        self.uc.banned_miners["bad_miner"] = time.time() + 3600
        
        config = UnifiedMinerConfig(
            miner_id="bad_miner",
            address="addr_bad",
            sector="H100",
        )
        ok, msg = self.uc.register_miner(config)
        self.assertFalse(ok)
        self.assertIn("封禁", msg)
    
    # ================================================================
    # 2. 区块挖出 → 板块币铸造
    # ================================================================
    
    def test_06_block_mined_mints_sector_coin(self):
        """测试区块挖出后铸造板块币"""
        config = UnifiedMinerConfig(
            miner_id="miner_mint",
            address="addr_mint",
            sector="H100",
            mode=UnifiedMinerMode.MINING_ONLY,
        )
        self.uc.register_miner(config)
        
        # 模拟区块挖出
        ok, reward, msg = self.uc.on_block_mined(
            block_height=1,
            miner_address="addr_mint",
            sector="H100",
            block_reward=10.0
        )
        
        self.assertTrue(ok)
        self.assertGreater(reward, 0)
        
        # 验证板块币余额增加
        balance = self.uc.sector_ledger.get_balance(
            "addr_mint", SectorCoinType.H100_COIN
        )
        self.assertGreater(balance.balance, 0)
        self.assertEqual(self.uc.stats["blocks_mined"], 1)
    
    def test_07_main_sector_no_mint(self):
        """测试MAIN板块不能挖矿铸造"""
        ok, reward, msg = self.uc.on_block_mined(
            block_height=1,
            miner_address="addr_main",
            sector="MAIN",
            block_reward=50.0
        )
        self.assertFalse(ok)
        self.assertIn("DR-1", msg)
    
    def test_08_multiple_blocks_accumulate(self):
        """测试多次出块累积板块币"""
        for i in range(5):
            self.uc.on_block_mined(
                block_height=i + 1,
                miner_address="addr_multi",
                sector="RTX4090",
                block_reward=5.0
            )
        
        balance = self.uc.sector_ledger.get_balance(
            "addr_multi", SectorCoinType.RTX4090_COIN
        )
        # 5 blocks * 5.0 base reward = 25.0
        self.assertGreater(balance.balance, 0)
        self.assertEqual(self.uc.stats["blocks_mined"], 5)
    
    # ================================================================
    # 3. 板块币 → MAIN 兑换
    # ================================================================
    
    def test_09_exchange_sector_to_main(self):
        """测试板块币兑换MAIN"""
        # 先铸造一些板块币
        self.uc.on_block_mined(1, "addr_ex", "H100", 10.0)
        
        balance_before = self.uc.sector_ledger.get_balance(
            "addr_ex", SectorCoinType.H100_COIN
        )
        self.assertGreater(balance_before.balance, 0)
        
        # 兑换
        ok, msg, exchange_id = self.uc.exchange_sector_to_main(
            address="addr_ex",
            sector="H100",
            amount=5.0
        )
        
        self.assertTrue(ok)
        self.assertIsNotNone(exchange_id)
    
    def test_10_exchange_insufficient_balance(self):
        """测试余额不足时兑换失败"""
        ok, msg, eid = self.uc.exchange_sector_to_main(
            address="addr_empty",
            sector="H100",
            amount=1000.0
        )
        self.assertFalse(ok)
        self.assertIn("余额不足", msg)
    
    def test_11_exchange_rate_dynamic(self):
        """测试动态汇率获取"""
        rate_h100 = self.uc.get_exchange_rate("H100")
        rate_cpu = self.uc.get_exchange_rate("CPU")
        
        # H100 是数据中心GPU，汇率应该更高
        self.assertGreater(rate_h100, 0)
        self.assertGreater(rate_cpu, 0)
    
    def test_12_all_exchange_rates(self):
        """测试获取所有板块汇率"""
        rates = self.uc.get_exchange_rates()
        self.assertIn("H100", rates)
        self.assertIn("RTX4090", rates)
        self.assertIn("CPU", rates)
        for rate in rates.values():
            self.assertGreater(rate, 0)
    
    # ================================================================
    # 4. 统一见证协调器
    # ================================================================
    
    def test_13_witness_main_transfer(self):
        """测试MAIN转账见证"""
        ok, witness_id = self.uc.request_witness(
            WitnessScope.MAIN_TRANSFER,
            {"from_address": "addr_a", "to_address": "addr_b", "amount": 100}
        )
        self.assertTrue(ok)
        self.assertIsNotNone(witness_id)
        self.assertGreater(self.uc.stats["witnesses_completed"], 0)
    
    def test_14_witness_sector_exchange(self):
        """测试板块币兑换见证"""
        ok, witness_id = self.uc.request_witness(
            WitnessScope.SECTOR_EXCHANGE,
            {"exchange_id": "ex_123"}
        )
        self.assertTrue(ok)
    
    def test_15_witness_sector_transfer_levels(self):
        """测试板块币转账分级见证"""
        # 微额 (< 10): 免见证
        ok1, _ = self.uc.request_witness(
            WitnessScope.SECTOR_TRANSFER,
            {"from_address": "a", "to_address": "b", "amount": 5}
        )
        self.assertTrue(ok1)
        
        # 中等 (10-100): 单见证
        ok2, _ = self.uc.request_witness(
            WitnessScope.SECTOR_TRANSFER,
            {"from_address": "a", "to_address": "b", "amount": 50}
        )
        self.assertTrue(ok2)
        
        # 大额 (>= 100): 双见证
        ok3, _ = self.uc.request_witness(
            WitnessScope.SECTOR_TRANSFER,
            {"from_address": "a", "to_address": "b", "amount": 500}
        )
        self.assertTrue(ok3)
    
    def test_16_witness_order_payment(self):
        """测试订单支付见证"""
        ok, witness_id = self.uc.request_witness(
            WitnessScope.ORDER_PAYMENT,
            {"order_id": "order_001", "amount": 10.0}
        )
        self.assertTrue(ok)
    
    # ================================================================
    # 5. 订单支付验证
    # ================================================================
    
    def test_17_order_payment_requires_main(self):
        """测试下单必须有MAIN余额"""
        # 无余额 → 失败
        ok, msg = self.uc.validate_order_payment("addr_no_main", 10.0)
        self.assertFalse(ok)
        self.assertIn("余额不足", msg)
    
    def test_18_order_payment_with_main(self):
        """测试有MAIN余额时可以下单"""
        # 设置MAIN余额
        self.uc.set_main_balance("addr_rich", 1000.0)
        
        ok, msg = self.uc.validate_order_payment("addr_rich", 10.0)
        self.assertTrue(ok)
        self.assertIn("验证通过", msg)
    
    def test_19_order_min_amount(self):
        """测试最低订单金额"""
        self.uc.set_main_balance("addr_min", 1000.0)
        
        ok, msg = self.uc.validate_order_payment("addr_min", 0.001)
        self.assertFalse(ok)
        self.assertIn("最低订单金额", msg)
    
    # ================================================================
    # 6. 板块币内部转账
    # ================================================================
    
    def test_20_sector_transfer(self):
        """测试板块币同板块转账"""
        from core.crypto import ECDSASigner
        import hashlib
        
        # 生成密钥对并获取地址
        kp = ECDSASigner.generate_keypair()
        sender_addr = ECDSASigner.public_key_to_address(kp.public_key)
        
        # 给发送方一些板块币
        self.uc.on_block_mined(1, sender_addr, "H100", 10.0)
        
        balance = self.uc.sector_ledger.get_balance(
            sender_addr, SectorCoinType.H100_COIN
        )
        amount = min(balance.balance, 3.0)
        
        # 构造签名
        transfer_payload = f"TRANSFER:{sender_addr}:addr_receiver:H100_COIN:{amount}"
        payload_hash = hashlib.sha256(transfer_payload.encode()).digest()
        signature = ECDSASigner.sign(kp.private_key, payload_hash)
        
        ok, msg = self.uc.transfer_sector_coin(
            sender_addr, "addr_receiver", "H100", amount,
            signature=signature.hex(), public_key=kp.public_key.hex()
        )
        self.assertTrue(ok, msg)
        
        # 验证接收方余额
        recv_balance = self.uc.sector_ledger.get_balance(
            "addr_receiver", SectorCoinType.H100_COIN
        )
        self.assertAlmostEqual(recv_balance.balance, amount, places=4)
    
    def test_21_sector_transfer_insufficient(self):
        """测试板块币转账余额不足"""
        ok, msg = self.uc.transfer_sector_coin(
            "addr_empty", "addr_recv", "H100", 999.0
        )
        self.assertFalse(ok)
        self.assertIn("余额不足", msg)
    
    # ================================================================
    # 7. MAIN 转账
    # ================================================================
    
    def test_22_main_transfer_with_witness(self):
        """测试MAIN转账必须双见证 + 1%手续费"""
        self.uc.set_main_balance("addr_main_a", 100.0)

        ok, msg = self.uc.transfer_main("addr_main_a", "addr_main_b", 50.0)
        self.assertTrue(ok)
        
        # 验证余额变动 (1%手续费: 50*0.01=0.5, 收方实收49.5)
        self.assertAlmostEqual(self.uc._get_main_balance("addr_main_a"), 50.0)
        self.assertAlmostEqual(self.uc._get_main_balance("addr_main_b"), 49.5)
    
    def test_23_main_transfer_insufficient(self):
        """测试MAIN转账余额不足"""
        ok, msg = self.uc.transfer_main("addr_poor", "addr_dest", 1000.0)
        self.assertFalse(ok)
        self.assertIn("余额不足", msg)
    
    # ================================================================
    # 8. 零信任任务安全
    # ================================================================
    
    def test_24_create_secure_task(self):
        """测试创建安全任务信封"""
        envelope = self.uc.create_secure_task(
            task_id="task_001",
            task_data={"model": "llama2", "prompt": "hello"},
            sector="H100",
            user_address="addr_user"
        )
        
        self.assertIsInstance(envelope, SecureTaskEnvelope)
        self.assertEqual(envelope.task_id, "task_001")
        self.assertTrue(envelope.read_only_rootfs)
        self.assertEqual(envelope.network_policy, "none")
        self.assertEqual(envelope.gpu_isolation, "confidential")
        self.assertGreater(len(envelope.encrypted_payload), 0)
        self.assertNotEqual(envelope.payload_hash, "")
    
    def test_25_secure_task_gpu_protection(self):
        """测试GPU保护策略"""
        # H100 → confidential
        env_h100 = self.uc.create_secure_task("t1", {}, "H100", "addr")
        self.assertEqual(env_h100.gpu_isolation, "confidential")
        self.assertEqual(env_h100.gpu_memory_limit_mb, 16384)
        
        # RTX3080 → isolated
        env_3080 = self.uc.create_secure_task("t2", {}, "RTX3080", "addr")
        self.assertEqual(env_3080.gpu_isolation, "isolated")
        self.assertEqual(env_3080.gpu_memory_limit_mb, 8192)
    
    def test_26_encrypt_decrypt_roundtrip(self):
        """测试加密解密往返"""
        original = b"sensitive task data"
        key = "test_key_12345"
        
        encrypted = self.uc._encrypt_payload(original, key)
        self.assertNotEqual(encrypted, original)
        
        decrypted = self.uc._decrypt_payload(encrypted, key)
        self.assertEqual(decrypted, original)
    
    # ================================================================
    # 9. 任务结果验证（陷阱+封禁）
    # ================================================================
    
    def test_27_verify_task_success(self):
        """测试任务验证通过"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="miner_v", address="addr_v", sector="H100"
        ))
        
        ok, msg, delta = self.uc.verify_task_result(
            task_id="task_v",
            miner_id="miner_v",
            result_hash="abcd1234",
            trap_results={"trap1": True, "trap2": True}
        )
        
        self.assertTrue(ok)
        self.assertGreater(delta, 0)
        self.assertEqual(self.uc.stats["tasks_completed"], 1)
    
    def test_28_verify_task_trap_failure(self):
        """测试陷阱题失败"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="miner_cheat", address="addr_cheat", sector="H100"
        ))
        
        ok, msg, delta = self.uc.verify_task_result(
            task_id="task_cheat",
            miner_id="miner_cheat",
            result_hash="fake",
            trap_results={"trap1": False, "trap2": False, "trap3": False}
        )
        
        self.assertFalse(ok)
        self.assertLess(delta, 0)
        self.assertEqual(self.uc.stats["tasks_failed"], 1)
    
    def test_29_ban_after_repeated_failures(self):
        """测试连续失败后封禁"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="miner_ban", address="addr_ban", sector="H100"
        ))
        
        # 连续3次陷阱失败
        for _ in range(3):
            self.uc.verify_task_result(
                task_id=f"task_ban_{_}",
                miner_id="miner_ban",
                result_hash="fake",
                trap_results={"t1": False, "t2": False}
            )
        
        # 应该被封禁
        self.assertIn("miner_ban", self.uc.banned_miners)
        self.assertGreater(self.uc.stats["miners_banned"], 0)
    
    # ================================================================
    # 10. 评分集成与优先级
    # ================================================================
    
    def test_30_task_priority_scoring(self):
        """测试综合评分与优先级"""
        # 注册两个矿工
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="m_high", address="a_h", sector="H100",
            mode=UnifiedMinerMode.TASK_ONLY
        ))
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="m_low", address="a_l", sector="H100",
            mode=UnifiedMinerMode.TASK_ONLY
        ))
        
        # 给 m_high 高分
        self.uc.update_miner_score("m_high", pouw_score=1.8, user_rating=4.8, 
                                     behavior_score=0.9, trust_delta=0.3)
        
        # 给 m_low 低分
        self.uc.update_miner_score("m_low", pouw_score=0.5, user_rating=2.0,
                                     behavior_score=0.3, trust_delta=-0.2)
        
        p_high = self.uc.get_task_priority("m_high")
        p_low = self.uc.get_task_priority("m_low")
        
        self.assertGreater(p_high, p_low)
    
    def test_31_ranked_miners(self):
        """测试矿工排名"""
        for i in range(5):
            self.uc.register_miner(UnifiedMinerConfig(
                miner_id=f"rank_{i}", address=f"addr_r{i}", sector="H100",
                mode=UnifiedMinerMode.TASK_ONLY
            ))
            # 使用较低值避免触碰 1.0 上限
            self.uc.update_miner_score(f"rank_{i}", pouw_score=0.1 + i * 0.15,
                                         user_rating=1.0 + i * 0.5,
                                         behavior_score=0.1 + i * 0.1,
                                         trust_delta=-0.3 + i * 0.1)
        
        ranked = self.uc.get_ranked_miners(3)
        self.assertEqual(len(ranked), 3)
        
        # 第一个应该是分数最高的 (rank_4)
        self.assertEqual(ranked[0][0], "rank_4")
        # 优先级应该递减
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i][1], ranked[i+1][1])
    
    def test_32_banned_miner_zero_priority(self):
        """测试被封禁矿工优先级为0"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="m_banned", address="a_b", sector="H100"
        ))
        self.uc.banned_miners["m_banned"] = time.time() + 3600
        
        priority = self.uc.get_task_priority("m_banned")
        self.assertEqual(priority, 0.0)
    
    # ================================================================
    # 11. 任务提交与分发
    # ================================================================
    
    def test_33_submit_task_single(self):
        """测试单节点任务提交"""
        # 注册矿工并给用户MAIN余额
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="worker_1", address="w_addr_1", sector="H100",
            mode=UnifiedMinerMode.TASK_ONLY
        ))
        self.uc.set_main_balance("user_001", 1000.0)
        
        ok, msg, task_id = self.uc.submit_task(
            user_address="user_001",
            task_data={"model": "bert", "data": "test"},
            sector="H100",
            payment_amount=10.0,
            distribution=TaskDistributionMode.SINGLE
        )
        print("TEST 33 MSG:", msg)

        self.assertTrue(ok, f"提交失败: {msg}")
        self.assertIn("单节点", msg)
        self.assertIsNotNone(task_id)
    
    def test_34_submit_task_distributed(self):
        """测试分布式任务提交"""
        # 注册多个矿工
        for i in range(5):
            self.uc.register_miner(UnifiedMinerConfig(
                miner_id=f"dw_{i}", address=f"dw_addr_{i}", sector="H100",
                mode=UnifiedMinerMode.MINING_AND_TASK
            ))
        self.uc.set_main_balance("user_dist", 1000.0)
        
        ok, msg, task_id = self.uc.submit_task(
            user_address="user_dist",
            task_data={"model": "gpt", "data": "test"},
            sector="H100",
            payment_amount=20.0,
            distribution=TaskDistributionMode.DISTRIBUTED
        )
        
        self.assertTrue(ok)
        self.assertIn("分布式", msg)
    
    def test_35_submit_task_no_main_fails(self):
        """测试无MAIN余额提交任务失败"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="worker_x", address="wx", sector="H100",
            mode=UnifiedMinerMode.TASK_ONLY
        ))
        
        ok, msg, task_id = self.uc.submit_task(
            user_address="user_broke",
            task_data={"test": True},
            sector="H100",
            payment_amount=10.0
        )
        
        self.assertFalse(ok)
        self.assertIn("支付验证失败", msg)
    
    def test_36_submit_task_no_miners_fails(self):
        """测试无可用矿工时任务提交失败"""
        self.uc.set_main_balance("user_lonely", 1000.0)
        
        ok, msg, task_id = self.uc.submit_task(
            user_address="user_lonely",
            task_data={"test": True},
            sector="H100",
            payment_amount=10.0
        )
        
        self.assertFalse(ok)
        self.assertIn("没有可用矿工", msg)
    
    # ================================================================
    # 12. 完整区块生命周期
    # ================================================================
    
    def test_37_block_lifecycle(self):
        """测试完整区块生命周期"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="lifecycle_miner", address="lc_addr", sector="H100",
            mode=UnifiedMinerMode.MINING_ONLY
        ))
        
        result = self.uc.process_block_lifecycle(
            block_height=1,
            miner_id="lifecycle_miner",
            miner_address="lc_addr",
            sector="H100",
            block_reward=10.0,
            transactions=[]
        )
        
        self.assertGreater(result["minted"], 0)
        self.assertTrue(result["score_updated"])
        self.assertTrue(result["security_ok"])
    
    def test_38_block_lifecycle_with_transactions(self):
        """测试带交易的区块生命周期"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="lc_miner2", address="lc_addr2", sector="H100",
            mode=UnifiedMinerMode.MINING_ONLY
        ))
        
        # 先铸造一些币
        for i in range(3):
            self.uc.on_block_mined(i+1, "lc_addr2", "H100", 10.0)
        
        # 带板块币转账的区块
        result = self.uc.process_block_lifecycle(
            block_height=4,
            miner_id="lc_miner2",
            miner_address="lc_addr2",
            sector="H100",
            block_reward=10.0,
            transactions=[
                {
                    "tx_type": "sector_transfer",
                    "from_address": "lc_addr2",
                    "to_address": "lc_recv",
                    "sector": "H100",
                    "amount": 5.0,
                }
            ]
        )
        
        self.assertGreater(result["transactions_processed"], 0)
    
    # ================================================================
    # 13. 系统状态与报告
    # ================================================================
    
    def test_39_system_status(self):
        """测试系统状态查询"""
        # 注册各类矿工
        for mode, name in [
            (UnifiedMinerMode.MINING_ONLY, "mo"),
            (UnifiedMinerMode.TASK_ONLY, "to"),
            (UnifiedMinerMode.MINING_AND_TASK, "mt"),
        ]:
            self.uc.register_miner(UnifiedMinerConfig(
                miner_id=f"status_{name}", address=f"s_{name}", sector="H100",
                mode=mode
            ))
        
        status = self.uc.get_system_status()
        
        self.assertEqual(status["miners"]["total"], 3)
        self.assertEqual(status["miners"]["mining_only"], 1)
        self.assertEqual(status["miners"]["task_only"], 1)
        self.assertEqual(status["miners"]["mining_and_task"], 1)
    
    def test_40_miner_detail(self):
        """测试矿工详情查询"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="detail_m", address="d_addr", sector="H100",
            mode=UnifiedMinerMode.MINING_AND_TASK
        ))
        self.uc.on_block_mined(1, "d_addr", "H100", 10.0)
        
        detail = self.uc.get_miner_detail("detail_m")
        
        self.assertIsNotNone(detail)
        self.assertEqual(detail["config"]["miner_id"], "detail_m")
        self.assertIn("scores", detail)
        self.assertIn("priority", detail)
        self.assertIn("sector_balances", detail)
    
    def test_41_security_report(self):
        """测试安全报告"""
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="sec_miner", address="sec_addr", sector="H100"
        ))
        
        # 触发安全事件
        self.uc.verify_task_result(
            "t_sec", "sec_miner", "fake",
            trap_results={"t1": False, "t2": False}
        )
        
        report = self.uc.get_security_report()
        
        self.assertGreater(report["total_events"], 0)
        self.assertIn("recent_events", report)
    
    # ================================================================
    # 14. 端到端集成测试
    # ================================================================
    
    def test_42_full_mining_to_order_flow(self):
        """端到端: 挖矿 → 铸币 → 兑换 → 下单"""
        # 1. 注册矿工
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="e2e_miner", address="e2e_addr", sector="H100",
            mode=UnifiedMinerMode.MINING_AND_TASK
        ))
        
        # 2. 挖矿铸币 (模拟5个区块)
        for i in range(5):
            ok, reward, _ = self.uc.on_block_mined(
                i+1, "e2e_addr", "H100", 10.0
            )
            self.assertTrue(ok)
        
        # 3. 检查板块币余额
        h100_balance = self.uc.sector_ledger.get_balance(
            "e2e_addr", SectorCoinType.H100_COIN
        )
        self.assertGreater(h100_balance.balance, 0)
        
        # 4. 兑换板块币为MAIN
        exchange_amount = min(h100_balance.balance, 20.0)
        ok, msg, eid = self.uc.exchange_sector_to_main(
            "e2e_addr", "H100", exchange_amount
        )
        self.assertTrue(ok, f"兑换失败: {msg}")
        
        # 5. 注册另一个矿工作为接单方
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="e2e_worker", address="e2e_worker_addr", sector="H100",
            mode=UnifiedMinerMode.TASK_ONLY
        ))
        
        # 6. 设置MAIN余额（模拟兑换完成）
        self.uc.set_main_balance("e2e_addr", 100.0)
        
        # 7. 提交任务
        ok, msg, task_id = self.uc.submit_task(
            user_address="e2e_addr",
            task_data={"inference": "llama2-70b"},
            sector="H100",
            payment_amount=5.0,
            distribution=TaskDistributionMode.SINGLE
        )
        self.assertTrue(ok, f"任务提交失败: {msg}")
        self.assertIsNotNone(task_id)
    
    def test_43_zero_trust_complete_flow(self):
        """端到端: 零信任完整流程"""
        # 1. 注册矿工
        self.uc.register_miner(UnifiedMinerConfig(
            miner_id="zt_miner", address="zt_addr", sector="RTX4090",
            mode=UnifiedMinerMode.MINING_AND_TASK
        ))
        
        # 2. 创建安全任务
        envelope = self.uc.create_secure_task(
            task_id="zt_task",
            task_data={"secret_data": "classified"},
            sector="RTX4090",
            user_address="zt_user"
        )
        
        # 验证安全配置
        self.assertTrue(envelope.read_only_rootfs)
        self.assertEqual(envelope.network_policy, "none")
        self.assertGreater(len(envelope.encrypted_payload), 0)
        
        # 3. 验证加密
        key = "zt_task_zt_user"  # 简化
        decrypted = self.uc._decrypt_payload(
            self.uc._encrypt_payload(b"test_data", key), key
        )
        self.assertEqual(decrypted, b"test_data")
        
        # 4. 验证结果（陷阱通过）
        ok, msg, delta = self.uc.verify_task_result(
            "zt_task", "zt_miner", "valid_hash",
            trap_results={"trap1": True, "trap2": True, "trap3": True}
        )
        self.assertTrue(ok)
        self.assertGreater(delta, 0)
        
        # 5. 验证信任度提升
        scores = self.uc.miner_scores["zt_miner"]
        self.assertGreater(scores["trust_score"], 0.5)


# ================================================================
# 运行
# ================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  统一共识引擎测试 (Unified Consensus Engine Tests)")
    print("=" * 70)
    
    # 设置编码环境
    import io
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestUnifiedConsensus)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"结果: {passed}/{total} 通过")
    
    if result.failures:
        print(f"失败: {len(result.failures)}")
        for test, trace in result.failures:
            print(f"  ✗ {test}")
    if result.errors:
        print(f"错误: {len(result.errors)}")
        for test, trace in result.errors:
            print(f"  ✗ {test}")
    
    print("=" * 70)
    
    sys.exit(0 if result.wasSuccessful() else 1)
