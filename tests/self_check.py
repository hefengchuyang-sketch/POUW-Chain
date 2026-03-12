# -*- coding: utf-8 -*-
"""
POUW Chain 模块串联自检

测试所有核心模块是否可正常导入和初始化。
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 清理测试数据
print('=' * 70)
print('清理测试数据...')
print('=' * 70)
data_dir = Path("data")
if data_dir.exists():
    for db_file in data_dir.glob("test_*.db"):
        try:
            db_file.unlink()
            print(f'   删除: {db_file.name}')
        except:
            pass
print('清理完成')

print('=' * 70)
print('POUW Chain 模块串联自检')
print('=' * 70)

results = []

# 1. 核心模块导入测试
print('\n[1] 核心模块导入测试')
print('-' * 70)
try:
    from core import (
        Block, Account,
        Transaction, TxType,
        PoUWExecutor, RealTaskType, RealPoUWTask, RealPoUWResult,
        MinerRegistry,
        POUWScoringEngine, SandboxExecutor,
        DynamicExchangeRate, ComputeWitnessSystem,
        UnifiedConsensus,
    )
    print('OK 所有核心模块导入成功')
    results.append(('核心模块导入', True))
except Exception as e:
    print(f'FAIL 模块导入失败: {e}')
    results.append(('核心模块导入', False))

# 2. 设备检测
print('\n[2] 硬件设备检测')
print('-' * 70)
try:
    from core.device_detector import DeviceDetector
    detector = DeviceDetector(log_fn=lambda x: None)
    profile = detector.detect_all()
    gpu_name = profile.gpu_list[0].name if profile.gpu_list else "无"
    print(f'OK 设备ID: {profile.device_id}')
    print(f'   GPU: {gpu_name}')
    print(f'   推荐板块: {profile.primary_sector}')
    results.append(('硬件设备检测', True))
except Exception as e:
    print(f'FAIL 设备检测失败: {e}')
    results.append(('硬件设备检测', False))

# 3. 钱包系统
print('\n[3] 钱包/密钥系统')
print('-' * 70)
try:
    from core.wallet import WalletGenerator
    gen = WalletGenerator()
    wallet = gen.generate_wallet()
    addr = wallet.addresses.get('MAIN', 'N/A')
    print(f'OK 生成钱包: {addr[:40]}...')
    print(f'   支持地址类型: {list(wallet.addresses.keys())}')
    results.append(('钱包/密钥系统', True))
except Exception as e:
    print(f'FAIL 钱包生成失败: {e}')
    results.append(('钱包/密钥系统', False))

test_addr = 'TEST_' + 'A' * 40

# 4. 板块币账本
print('\n[4] 板块币账本')
print('-' * 70)
try:
    from core.sector_coin import SectorCoinLedger, SectorCoinType
    ledger = SectorCoinLedger('data/test_sector.db')
    ok, reward, msg = ledger.mint_block_reward('H100', test_addr, block_height=1)
    bal = ledger.get_balance(test_addr, SectorCoinType.H100_COIN)
    print(f'OK 铸造 {reward} H100_COIN 给测试地址')
    print(f'   余额: {bal.balance} H100_COIN')
    results.append(('板块币账本', True))
except Exception as e:
    print(f'FAIL 板块币账本失败: {e}')
    results.append(('板块币账本', False))

# 5. 双见证兑换
print('\n[5] 双见证兑换系统')
print('-' * 70)
try:
    from core.dual_witness_exchange import DualWitnessExchange
    exchange = DualWitnessExchange('data/test_exchange.db')
    print('OK 双见证兑换引擎初始化成功')
    print(f'   支持板块: {exchange.WITNESS_SECTORS}')
    results.append(('双见证兑换系统', True))
except Exception as e:
    print(f'FAIL 兑换系统失败: {e}')
    results.append(('双见证兑换系统', False))

# 6. RPC 服务
print('\n[6] RPC 服务')
print('-' * 70)
try:
    from core.rpc_service import NodeRPCService, RPCRequest, RPCResponse
    rpc = NodeRPCService()
    methods = rpc.registry.list_methods()
    print(f'OK RPC 服务初始化成功')
    print(f'   注册方法数: {len(methods)}')
    results.append(('RPC 服务', True))
except Exception as e:
    print(f'FAIL RPC 服务失败: {e}')
    results.append(('RPC 服务', False))

# 7. 算力调度器
print('\n[7] 算力调度器')
print('-' * 70)
try:
    from core.compute_scheduler import ComputeScheduler, MinerNode, MinerMode
    cs = ComputeScheduler('data/test_compute_scheduler.db')
    print('OK 算力调度器初始化成功')
    results.append(('算力调度器', True))
except Exception as e:
    print(f'FAIL 算力调度器失败: {e}')
    results.append(('算力调度器', False))

# 8. 共识引擎
print('\n[8] 共识引擎')
print('-' * 70)
try:
    from core.consensus import ConsensusEngine
    engine = ConsensusEngine()
    print(f'OK 共识引擎初始化成功')
    print(f'   目标出块时间: {engine.TARGET_BLOCK_TIME}s')
    results.append(('共识引擎', True))
except Exception as e:
    print(f'FAIL 共识引擎失败: {e}')
    results.append(('共识引擎', False))

# 9. UTXO 存储
print('\n[9] UTXO 存储')
print('-' * 70)
try:
    from core.utxo_store import UTXOStore
    store = UTXOStore('data/test_utxo.db')
    print('OK UTXO 存储初始化成功')
    results.append(('UTXO 存储', True))
except Exception as e:
    print(f'FAIL UTXO 存储失败: {e}')
    results.append(('UTXO 存储', False))

# 10. 治理系统
print('\n[10] 增强治理系统')
print('-' * 70)
try:
    from core.governance_enhanced import EnhancedGovernanceEngine
    gov = EnhancedGovernanceEngine()
    print('OK 增强治理引擎初始化成功')
    results.append(('增强治理系统', True))
except Exception as e:
    print(f'FAIL 增强治理失败: {e}')
    results.append(('增强治理系统', False))

# 11. 贡献权重治理
print('\n[11] 贡献权重治理')
print('-' * 70)
try:
    from core.contribution_governance import ContributionGovernance
    cg = ContributionGovernance()
    print('OK 贡献权重治理初始化成功')
    results.append(('贡献权重治理', True))
except Exception as e:
    print(f'FAIL 贡献权重治理失败: {e}')
    results.append(('贡献权重治理', False))

# 12. 安全模块
print('\n[12] 安全模块 (TLS/认证/限流)')
print('-' * 70)
try:
    from core.security import SecurityManager, RateLimiter
    rl = RateLimiter()
    print('OK 安全模块加载成功')
    print(f'   RateLimiter 最大追踪IP: {rl.MAX_TRACKED_IPS}')
    results.append(('安全模块', True))
except Exception as e:
    print(f'FAIL 安全模块失败: {e}')
    results.append(('安全模块', False))

# 汇总
print('\n' + '=' * 70)
print('自检结果汇总')
print('=' * 70)

passed = sum(1 for _, ok in results if ok)
total = len(results)

for name, ok in results:
    status = 'PASS' if ok else 'FAIL'
    icon = '✅' if ok else '❌'
    print(f'  {icon} {name}: {status}')

print()
print(f'总计: {passed}/{total} 通过')

if passed == total:
    print('\n🎉 所有模块自检通过！')
else:
    print(f'\n⚠️ {total - passed} 个模块存在问题')

print('=' * 70)
