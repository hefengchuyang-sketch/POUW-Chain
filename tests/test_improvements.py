#!/usr/bin/env python3
"""
全面验证测试 - 验证所有改进是否正确集成

覆盖:
  P0: POUW 挖矿连接到共识循环
  P1: 死代码清理 (deprecated/)
  P2: 测试网单见证模式
  #1: POUW 区块类型 (task/idle/validation) + 奖励衰减
  #2: 评分系统 (ObjectiveMetricsCollector) 集成
  #3: 8 个扩展模块集成到 main.py
  #4: 算力市场 V3 集成
  #5: config.yaml network.type 生效
  #6: 优雅关闭
  #7: RPC 服务拆分
"""

import sys
import os
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0
results = []


def _run_test(name: str, func):
    global passed, failed
    try:
        func()
        passed += 1
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")


# ========================
# P0: POUW 挖矿连接
# ========================
def test_p0_pouw_connected():
    from core.consensus import ConsensusEngine, ConsensusType
    engine = ConsensusEngine(node_id="test_p0", sector="MAIN")
    ct = engine.select_consensus()
    assert ct == ConsensusType.POUW, f"Expected POUW, got {ct}"

_run_test("P0: POUW 挖矿已连接到共识循环", test_p0_pouw_connected)


# ========================
# P1: 死代码清理
# ========================
def test_p1_deprecated():
    # deprecated 目录已完全删除，确认废弃文件不存在
    removed = [
        "core/deprecated",
        "core/rpc.py",
        "core/p2p_network.py",
        "core/task_broadcast.py",
    ]
    for f in removed:
        assert not os.path.exists(f), f"Should be removed: {f}"

_run_test("P1: 死代码已清除", test_p1_deprecated)


# ========================
# P2: 测试网单见证
# ========================
def test_p2_testnet_witness():
    from core.dual_witness_exchange import DualWitnessExchange
    svc = DualWitnessExchange.__new__(DualWitnessExchange)
    # 检查类是否支持 testnet 参数
    import inspect
    sig = inspect.signature(DualWitnessExchange.__init__)
    params = list(sig.parameters.keys())
    assert 'testnet' in params, "DualWitnessExchange should accept testnet param"

_run_test("P2: 测试网单见证模式", test_p2_testnet_witness)


# ========================
# #1: POUW 区块类型
# ========================
def test_block_type_field():
    from core.consensus import Block
    b = Block()
    assert hasattr(b, 'block_type'), "Block should have block_type field"
    assert b.block_type == "task_block", f"Default block_type should be task_block, got {b.block_type}"

_run_test("#1a: Block 数据类包含 block_type 字段", test_block_type_field)


def test_block_type_selector():
    from core.pouw_block_types import BlockType, BlockTypeSelector
    bt, reason = BlockTypeSelector.select(
        has_pending_tasks=True, miner_is_online=True,
        miner_is_witness=False, consecutive_idle_blocks=0, consecutive_validation_blocks=0
    )
    assert bt == BlockType.TASK_BLOCK, f"With tasks, should select TASK_BLOCK, got {bt}"

    bt2, reason2 = BlockTypeSelector.select(
        has_pending_tasks=False, miner_is_online=True,
        miner_is_witness=False, consecutive_idle_blocks=0, consecutive_validation_blocks=0
    )
    assert bt2 == BlockType.IDLE_BLOCK, f"Without tasks, should select IDLE_BLOCK, got {bt2}"

_run_test("#1b: BlockTypeSelector 选择逻辑", test_block_type_selector)


def test_reward_decay():
    from core.pouw_block_types import BlockType, RewardDecayRules
    base = 50.0
    r1 = RewardDecayRules.calculate_reward(BlockType.IDLE_BLOCK, base, 1)
    r5 = RewardDecayRules.calculate_reward(BlockType.IDLE_BLOCK, base, 5)
    assert r1 < base, f"IDLE_BLOCK reward should be < base ({r1} vs {base})"
    assert r5 < r1, f"Consecutive decay: r5={r5} should be < r1={r1}"
    # task_block 不衰减
    rt = RewardDecayRules.calculate_reward(BlockType.TASK_BLOCK, base, 10)
    assert rt == base, f"TASK_BLOCK should not decay, got {rt}"

_run_test("#1c: 奖励衰减机制", test_reward_decay)


def test_liveness_constraint():
    from core.pouw_block_types import LivenessConstraints
    should_force, force_type = LivenessConstraints.should_force_block(500, 0)
    assert should_force, "Should force idle block after 500s with no tasks"
    should_force2, _ = LivenessConstraints.should_force_block(100, 5)
    assert not should_force2, "Should not force block at 100s with pending tasks"

_run_test("#1d: 活跃性约束 (超时强制出块)", test_liveness_constraint)


def test_block_type_in_serialization():
    from core.consensus import ConsensusEngine, Block
    engine = ConsensusEngine(node_id="test_ser", sector="MAIN")
    b = Block(height=1, block_type="idle_block")
    d = engine._block_to_dict(b)
    assert d.get('block_type') == 'idle_block', f"block_type not in serialized dict: {d.get('block_type')}"
    b2 = engine._dict_to_block(d)
    assert b2.block_type == 'idle_block', f"block_type not restored: {b2.block_type}"

_run_test("#1e: block_type 序列化/反序列化", test_block_type_in_serialization)


# ========================
# #2: 评分系统集成
# ========================
def test_scoring_collector():
    from core.pouw_scoring import ObjectiveMetricsCollector
    collector = ObjectiveMetricsCollector()
    collector.record_task("miner_1", success=True, response_time_ms=150)
    collector.record_block("miner_1")
    collector.record_uptime("miner_1", 0.5)
    metrics = collector.get_or_create("miner_1")
    assert metrics is not None, "Should return metrics"
    assert metrics.completed_tasks >= 1, f"completed_tasks should be >=1, got {metrics.completed_tasks}"
    assert metrics.blocks_mined >= 1, f"blocks_mined should be >=1, got {metrics.blocks_mined}"

_run_test("#2a: ObjectiveMetricsCollector 基础功能", test_scoring_collector)


def test_scoring_in_consensus():
    from core.consensus import ConsensusEngine
    engine = ConsensusEngine(node_id="test_score", sector="MAIN")
    assert hasattr(engine, 'metrics_collector'), "ConsensusEngine should have metrics_collector"
    assert hasattr(engine, '_consecutive_idle'), "ConsensusEngine should track consecutive_idle"
    assert hasattr(engine, '_last_block_time'), "ConsensusEngine should track last_block_time"

_run_test("#2b: 评分系统已集成到 ConsensusEngine", test_scoring_in_consensus)


# ========================
# #3: 8 个扩展模块
# ========================
def test_module_imports():
    modules = [
        ("core.audit_compliance", "AuditTrailEngine"),
        ("core.audit_compliance", "ComplianceEngine"),
        ("core.miner_security_manager", "MinerSecurityManager"),
        ("core.infrastructure", "MultiCloudManager"),
        ("core.infrastructure", "AutoScaler"),
        ("core.privacy_enhanced", "EncryptedComputeManager"),
        ("core.compute_economy", "ComputeEconomyEngine"),
        ("core.cross_region_scheduler", "CrossRegionScheduler"),
        ("core.governance_enhanced", "EnhancedGovernanceEngine"),
        ("core.user_experience", "I18nManager"),
        ("core.user_experience", "NotificationService"),
    ]
    for mod_name, cls_name in modules:
        mod = __import__(mod_name, fromlist=[cls_name])
        cls = getattr(mod, cls_name)
        assert cls is not None, f"{mod_name}.{cls_name} not found"

_run_test("#3a: 8 个扩展模块全部可导入", test_module_imports)


def test_main_has_extended_init():
    import ast
    with open("main.py", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            methods.add(node.name)
    assert "_init_extended_modules" in methods, "main.py should have _init_extended_modules"
    assert "_init_compute_market" in methods, "main.py should have _init_compute_market"

_run_test("#3b: main.py 包含扩展模块初始化方法", test_main_has_extended_init)


def test_main_node_attributes():
    import ast
    with open("main.py", encoding="utf-8") as f:
        source = f.read()
    # 检查 POUWNode.__init__ 中包含新模块属性
    required_attrs = [
        "audit_engine", "compliance_engine", "miner_security",
        "compute_economy", "privacy_manager", "cross_scheduler",
        "governance_engine", "compute_market", "cloud_manager",
    ]
    for attr in required_attrs:
        assert f"self.{attr}" in source, f"POUWNode should have self.{attr}"

_run_test("#3c: POUWNode 包含所有扩展模块属性", test_main_node_attributes)


# ========================
# #4: 算力市场 V3
# ========================
def test_compute_market_v3():
    from core.compute_market_v3 import ComputeMarketV3
    with tempfile.TemporaryDirectory() as tmpdir:
        db = os.path.join(tmpdir, "test_market.db")
        market = ComputeMarketV3(db_path=db)
        assert market is not None
        market.close()

_run_test("#4: ComputeMarketV3 可实例化", test_compute_market_v3)


# ========================
# #5: config.yaml network.type
# ========================
def test_config_network_type():
    import ast
    with open("main.py", encoding="utf-8") as f:
        source = f.read()
    assert 'network_type' in source, "main.py should pass network_type to consensus"
    assert 'consensus_engine.network_type' in source, "Should set consensus_engine.network_type"

_run_test("#5a: network.type 传递到共识引擎", test_config_network_type)


def test_config_consensus_params():
    import ast
    with open("main.py", encoding="utf-8") as f:
        source = f.read()
    assert "initial_difficulty" in source, "main.py should apply initial_difficulty from config"
    assert "base_reward" in source, "main.py should apply base_reward from config"

_run_test("#5b: 共识参数从 config.yaml 生效", test_config_consensus_params)


# ========================
# #6: 优雅关闭
# ========================
def test_graceful_shutdown():
    import ast
    with open("main.py", encoding="utf-8") as f:
        source = f.read()
    # 检查 stop() 方法关闭 RPC
    assert "rpc_server" in source.split("def stop(")[1].split("def ")[0], \
        "stop() should close rpc_server"
    # 检查关闭 P2P
    assert "p2p_node" in source.split("def stop(")[1].split("def ")[0], \
        "stop() should close p2p_node"

_run_test("#6: 优雅关闭 (RPC + P2P + 扩展模块)", test_graceful_shutdown)


# ========================
# #7: RPC 服务拆分
# ========================
def test_rpc_package_exists():
    assert os.path.isdir("core/rpc"), "core/rpc/ package should exist"
    assert os.path.isfile("core/rpc/__init__.py"), "__init__.py should exist"
    assert os.path.isfile("core/rpc/models.py"), "models.py should exist"
    assert os.path.isfile("core/rpc/server.py"), "server.py should exist"

_run_test("#7a: RPC 包结构存在", test_rpc_package_exists)


def test_rpc_backward_compat():
    from core.rpc_service import RPCServer, NodeRPCService, RPCClient
    assert RPCServer is not None
    assert NodeRPCService is not None
    assert RPCClient is not None

_run_test("#7b: RPC 向后兼容导入", test_rpc_backward_compat)


def test_rpc_new_import():
    from core.rpc import RPCServer, RPCClient, RPCRequest, RPCResponse, RPCErrorCode
    assert RPCServer is not None
    assert RPCClient is not None
    assert RPCRequest is not None

_run_test("#7c: RPC 新包导入路径", test_rpc_new_import)


def test_rpc_models_separation():
    from core.rpc.models import RPCErrorCode, RPCPermission, RPCMethodRegistry
    reg = RPCMethodRegistry()
    reg.register("test_method", lambda: None, "Test", RPCPermission.PUBLIC)
    assert reg.has("test_method")
    assert reg.count() == 1

_run_test("#7d: RPC 模型类独立工作", test_rpc_models_separation)


# ========================
# 集成: 挖矿流程
# ========================
def test_mining_integration():
    """测试完整挖矿流程: 区块类型选择 + 奖励衰减 + 评分记录"""
    from core.consensus import ConsensusEngine
    engine = ConsensusEngine(node_id="test_mining", sector="MAIN")

    # 挖一个区块
    block = engine.mine_block("test_address_001")
    assert block is not None, "Should mine a block"
    assert hasattr(block, 'block_type'), "Block should have block_type"
    assert block.block_type in ("task_block", "idle_block", "validation_block"), \
        f"Invalid block_type: {block.block_type}"
    assert block.block_reward > 0, "Block reward should be > 0"

    # 验证评分记录
    metrics = engine.metrics_collector.get_or_create("test_mining")
    assert metrics.blocks_mined >= 1, "Should have recorded the block"

_run_test("集成: 完整挖矿流程 (类型+衰减+评分)", test_mining_integration)


# ========================
# 总结
# ========================
print("\n" + "=" * 50)
print(f"测试结果: {passed} 通过, {failed} 失败 (共 {passed + failed} 项)")
print("=" * 50)

if failed > 0:
    print("\n失败项:")
    for r in results:
        if r[0] == "FAIL":
            print(f"  X {r[1]}: {r[2]}")
