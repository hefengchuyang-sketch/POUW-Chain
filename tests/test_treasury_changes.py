# -*- coding: utf-8 -*-
"""验证财库税率改动"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

passed = 0
failed = 0

def _run_test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  [PASS] {name}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        failed += 1

print("=" * 50)
print("财库税率改动验证")
print("=" * 50)

# 1. ChainParams 常量
def t1():
    from core.consensus import ChainParams
    assert ChainParams.TREASURY_RATE == 0.03
_run_test("ChainParams.TREASURY_RATE == 0.03", t1)

# 2. RewardCalculator 默认值
def t2():
    from core.consensus import RewardCalculator
    rc = RewardCalculator()
    assert rc.treasury_rate == 0.03
_run_test("RewardCalculator 默认 treasury_rate == 0.03", t2)

# 3. 奖励分配比例正确
def t3():
    from core.consensus import RewardCalculator
    rc = RewardCalculator()
    dist = rc.calculate_distribution(height=0, miner_pouw_score=0, total_pouw_score=0)
    assert abs(dist["treasury"] - 1.5) < 0.001, f"treasury={dist['treasury']}"
    assert abs(dist["miner"] - 48.5) < 0.001, f"miner={dist['miner']}"
_run_test("区块奖励: 矿工=48.5, 财库=1.5 (总50)", t3)

# 4. 税率可动态修改
def t4():
    from core.consensus import RewardCalculator
    rc = RewardCalculator()
    rc.treasury_rate = 0.05
    dist = rc.calculate_distribution(height=0, miner_pouw_score=0, total_pouw_score=0)
    assert abs(dist["treasury"] - 2.5) < 0.001
    assert abs(dist["miner"] - 47.5) < 0.001
_run_test("动态修改税率为5%", t4)

# 5. config.yaml 包含 treasury_rate
def t5():
    import yaml
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tr = cfg.get("consensus", {}).get("treasury_rate")
    assert tr == 0.03, f"got {tr}"
_run_test("config.yaml treasury_rate == 0.03", t5)

# 6. RPC 方法存在
def t6():
    from core.rpc_service import NodeRPCService
    methods = [
        "_dao_get_treasury_config",
        "_dao_set_treasury_rate",
        "_dao_get_treasury_report",
        "_dao_create_treasury_proposal",
        "_dao_treasury_withdraw",
    ]
    for m in methods:
        assert hasattr(NodeRPCService, m), f"Missing {m}"
_run_test("5个新 RPC 方法存在", t6)

# 7. _dao_get_treasury_config 返回正确结构
def t7():
    from core.rpc_service import NodeRPCService
    service = NodeRPCService.__new__(NodeRPCService)
    service.consensus_engine = None
    result = service._dao_get_treasury_config()
    assert "blockReward" in result
    assert result["blockReward"]["treasuryRate"] == 0.03
    assert result["blockReward"]["minerRate"] == 0.97
_run_test("_dao_get_treasury_config 返回正确数据", t7)

# 8. _dao_set_treasury_rate 范围检查
def t8():
    from core.rpc_service import NodeRPCService
    service = NodeRPCService.__new__(NodeRPCService)
    service.consensus_engine = None
    # 无参数
    r1 = service._dao_set_treasury_rate()
    assert r1["success"] == False
    # 超出范围
    r2 = service._dao_set_treasury_rate(rate=0.50)
    assert r2["success"] == False
    # 太低
    r3 = service._dao_set_treasury_rate(rate=0.001)
    assert r3["success"] == False
_run_test("_dao_set_treasury_rate 范围校验", t8)

# 9. _dao_get_treasury_report 基础返回
def t9():
    from core.rpc_service import NodeRPCService
    service = NodeRPCService.__new__(NodeRPCService)
    service.consensus_engine = None
    result = service._dao_get_treasury_report()
    assert result.get("success") == True, f"result={result}"
    report = result.get("report", {})
    # 可能返回 TreasuryManager 的报告，或 fallback
    has_control = "controlMechanism" in report
    has_pool = "pool_balances" in report
    assert has_control or has_pool, f"report missing expected keys"
_run_test("_dao_get_treasury_report 返回报告", t9)

# 10. _dao_create_treasury_proposal 参数校验
def t10():
    from core.rpc_service import NodeRPCService
    service = NodeRPCService.__new__(NodeRPCService)
    r = service._dao_create_treasury_proposal()
    assert r["success"] == False
_run_test("_dao_create_treasury_proposal 参数校验", t10)

# 11. _dao_treasury_withdraw 参数校验
def t11():
    from core.rpc_service import NodeRPCService
    service = NodeRPCService.__new__(NodeRPCService)
    r = service._dao_treasury_withdraw()
    assert r["success"] == False
    assert "hint" in r
_run_test("_dao_treasury_withdraw 需要 proposalId", t11)

# 12. 减半后奖励+税率仍正确
def t12():
    from core.consensus import RewardCalculator
    rc = RewardCalculator()
    # 一次减半后 base_reward = 25
    dist = rc.calculate_distribution(height=210000, miner_pouw_score=0, total_pouw_score=0)
    assert abs(dist["treasury"] - 0.75) < 0.001  # 25 * 0.03
    assert abs(dist["miner"] - 24.25) < 0.001    # 25 * 0.97
_run_test("减半后财库税率仍为 3%", t12)

print()
print(f"结果: {passed} 通过, {failed} 失败 / 共 {passed + failed}")
if failed == 0:
    print("=== 全部通过! ===")
