"""
完整 POUW 系统验证
验证整个系统改进后的运行状态：
1. POUW 挖矿闭环（不再 PoW 回退）
2. 板块币奖励 + UTXO 创建
3. 测试网单见证兑换
4. 废弃模块已清理
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0

def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}: {detail}")

def test_pouw_mining_closed_loop():
    """测试 1: POUW 挖矿闭环"""
    print("\n📦 测试 1: POUW 挖矿闭环")
    print("-" * 50)
    
    from core.consensus import ConsensusEngine, ConsensusType
    
    engine = ConsensusEngine(
        node_id="verify_node",
        sector="GENERAL",
        log_fn=lambda x: None,
        db_path="data/verify_chain.db"
    )
    
    # 测试自动 POUW 选择
    consensus = engine.select_consensus()
    check("共识类型为 POUW", consensus == ConsensusType.POUW, f"实际: {consensus.value}")
    check("自动生成了 POUW 证明", len(engine.pending_pouw) > 0, f"数量: {len(engine.pending_pouw)}")
    
    # 挖 5 个区块
    pouw_blocks = 0
    pow_blocks = 0
    for _ in range(5):
        block = engine.mine_block("test_wallet")
        if block:
            engine.add_block(block)
            if block.consensus_type == ConsensusType.POUW:
                pouw_blocks += 1
            else:
                pow_blocks += 1
    
    check("所有区块都是 POUW", pouw_blocks == 5, f"POUW={pouw_blocks}, PoW={pow_blocks}")
    check("区块包含真实证明", bool(engine.chain[-1].pouw_proofs), "没有 POUW 证明")
    
    # 检查证明细节
    last_proofs = engine.chain[-1].pouw_proofs
    has_task_id = all(p.get("task_id") for p in last_proofs)
    has_score = all(p.get("quality_score", 0) > 0 for p in last_proofs)
    check("证明包含 task_id", has_task_id)
    check("证明包含 quality_score", has_score)
    
    # 清理
    try:
        engine._db_conn.close()
        os.remove("data/verify_chain.db")
    except Exception:
        pass

def test_sector_coin_and_utxo():
    """测试 2: 板块币 + UTXO"""
    print("\n💰 测试 2: 板块币奖励 + UTXO")
    print("-" * 50)
    
    from core.sector_coin import SectorCoinLedger, SectorCoinType
    from core.utxo_store import UTXOStore
    
    ledger = SectorCoinLedger(db_path="data/verify_sector.db")
    utxo = UTXOStore(db_path="data/verify_utxo.db")
    
    # 铸造奖励
    success, reward, msg = ledger.mint_block_reward(
        sector="GENERAL",
        miner_address="test_miner_addr",
        block_height=1
    )
    check("板块币铸造成功", success, msg)
    
    # 查余额
    bal = ledger.get_balance("test_miner_addr", SectorCoinType.from_sector("GENERAL"))
    check("板块币余额正确", bal.balance > 0, f"余额: {bal.balance}")
    
    # 创建 Coinbase UTXO
    txid, utxo_obj = utxo.create_coinbase_utxo(
        miner_address="test_miner_addr",
        amount=50.0,
        sector="GENERAL",
        block_height=1,
        block_hash="abc123"
    )
    check("Coinbase UTXO 创建成功", bool(txid), f"txid: {txid[:12]}...")
    
    # 查 UTXO
    unspent = utxo.get_utxos_by_address("test_miner_addr")
    check("UTXO 可查询", len(unspent) > 0, f"UTXO 数量: {len(unspent)}")
    
    # 清理
    try:
        ledger.conn.close()
    except Exception:
        pass
    try:
        utxo.conn.close()
    except Exception:
        pass
    for f in ["data/verify_sector.db", "data/verify_utxo.db"]:
        try:
            os.remove(f)
        except Exception:
            pass

def test_testnet_witness():
    """测试 3: 测试网单见证"""
    print("\n🔍 测试 3: 测试网单见证模式")
    print("-" * 50)
    
    from core.dual_witness_exchange import DualWitnessExchange
    
    # 测试网模式
    ex_testnet = DualWitnessExchange(db_path="data/verify_exchange.db", testnet=True)
    check("测试网见证数=1", ex_testnet.required_witnesses == 1)
    
    # 主网模式
    ex_mainnet = DualWitnessExchange(db_path="data/verify_exchange2.db", testnet=False)
    check("主网见证数=2", ex_mainnet.required_witnesses == 2)
    
    # 清理
    for f in ["data/verify_exchange.db", "data/verify_exchange2.db"]:
        try:
            os.remove(f)
        except Exception:
            pass

def test_deprecated_cleanup():
    """测试 4: 废弃代码已完全清除"""
    print("\n🗑️  测试 4: 废弃代码清除验证")
    print("-" * 50)
    
    # deprecated 目录应已完全删除
    check("deprecated/ 目录已删除", not os.path.exists("core/deprecated"), "目录仍存在")
    
    # 废弃模块不应存在于任何位置
    should_not_exist = [
        "core/rpc.py",
        "core/p2p_network.py",
        "core/task_broadcast.py",
        "core/compute_market.py",
        "core/compute_market_v2.py",
        "core/exchange_treasury.py",
    ]
    
    for f in should_not_exist:
        check(f"已清除: {os.path.basename(f)}", not os.path.exists(f), "文件仍存在")

def test_pouw_executor():
    """测试 5: POUW 执行器任务类型"""
    print("\n🔬 测试 5: POUW 执行器多任务类型")
    print("-" * 50)
    
    from core.pouw_executor import PoUWExecutor, RealTaskType
    
    executor = PoUWExecutor(min_score_threshold=0.3)  # 与挖矿引擎一致
    
    for task_type in RealTaskType:
        task = executor.generate_task(task_type, difficulty=1)
        result = executor.execute_task(task, "test_miner")
        check(
            f"{task_type.value}: score={result.score:.3f}",
            result.score > 0,
            f"score={result.score}"
        )

def test_core_imports():
    """测试 6: 核心模块导入"""
    print("\n📚 测试 6: 核心模块导入完整性")
    print("-" * 50)
    
    modules = [
        ("core.consensus", "ConsensusEngine"),
        ("core.pouw_executor", "PoUWExecutor"),
        ("core.pouw", "PoUWVerifier"),
        ("core.pouw_scoring", "ObjectiveMetricsCollector"),
        ("core.sector_coin", "SectorCoinLedger"),
        ("core.utxo_store", "UTXOStore"),
        ("core.tcp_network", "P2PNode"),
        ("core.dual_witness_exchange", "DualWitnessExchange"),
        ("core.pouw_block_types", "BlockType"),
    ]
    
    for mod_name, class_name in modules:
        try:
            mod = __import__(mod_name, fromlist=[class_name])
            cls = getattr(mod, class_name)
            check(f"{mod_name}.{class_name}", True)
        except Exception as e:
            check(f"{mod_name}.{class_name}", False, str(e))

if __name__ == "__main__":
    print("=" * 60)
    print("POUW Multi-Sector Chain 系统验证")
    print("=" * 60)
    
    test_pouw_mining_closed_loop()
    test_sector_coin_and_utxo()
    test_testnet_witness()
    test_deprecated_cleanup()
    test_pouw_executor()
    test_core_imports()
    
    print("\n" + "=" * 60)
    total = PASS + FAIL
    if FAIL == 0:
        print(f"🎉 全部通过！{PASS}/{total} 测试")
    else:
        print(f"⚠️  {PASS}/{total} 通过, {FAIL} 失败")
    print("=" * 60)
    
    sys.exit(0 if FAIL == 0 else 1)
