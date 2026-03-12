# -*- coding: utf-8 -*-
"""
安全模块测试 — 测试加密任务、安全算力市场、TEE 可信执行

已移除的模块测试:
- anti_leakage.py (已删除)
- container_security.py (已删除)
- security_level.py (已删除)
"""

import sys
import os
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

PASS = 0
FAIL = 0
WARN = 0

def _run_test(name, fn):
    global PASS, FAIL, WARN
    try:
        result = fn()
        if result == True or result is None:
            print(f"  ✅ {name}")
            PASS += 1
        elif isinstance(result, str) and result.startswith("WARN"):
            print(f"  ⚠️  {name}: {result}")
            WARN += 1
        else:
            print(f"  ❌ {name}: 返回 {result}")
            FAIL += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        traceback.print_exc()
        FAIL += 1


# ================================================================
# 1. 测试 encrypted_task.py (加密任务模块)
# ================================================================
print("\n" + "=" * 60)
print("1. 测试 encrypted_task.py (加密任务模块)")
print("=" * 60)

def test_hybrid_encryption_keypair():
    from core.encrypted_task import HybridEncryption
    kp = HybridEncryption.generate_keypair()
    assert kp.public_key
    assert kp.private_key
    assert kp.public_key != kp.private_key

def test_hybrid_encrypt_decrypt():
    from core.encrypted_task import HybridEncryption
    kp = HybridEncryption.generate_keypair()
    plaintext = b"Hello POUW Chain"
    encrypted = HybridEncryption.encrypt(plaintext, kp.public_key)
    assert encrypted.encrypted_data != plaintext
    decrypted = HybridEncryption.decrypt(encrypted, kp.private_key)
    assert decrypted == plaintext

def test_encrypted_task_create():
    from core.encrypted_task import EncryptedTaskManager, HybridEncryption
    mgr = EncryptedTaskManager()
    kp = HybridEncryption.generate_keypair()
    task = mgr.create_task(
        task_type="ML_TRAINING",
        user_id="buyer_001",
        title="Test Task",
        description="Test encrypted task creation",
        code_data=b"print('hello')",
        input_data=b"training_data_here",
        user_keypair=kp
    )
    assert task.task_id
    assert task.code_data
    assert task.input_data

_run_test("HybridEncryption 密钥对生成", test_hybrid_encryption_keypair)
_run_test("HybridEncryption 加密/解密", test_hybrid_encrypt_decrypt)
_run_test("EncryptedTask 创建", test_encrypted_task_create)


# ================================================================
# 2. 测试 secure_compute_market.py (安全算力市场)
# ================================================================
print("\n" + "=" * 60)
print("2. 测试 secure_compute_market.py (安全算力市场)")
print("=" * 60)

def test_secure_market_create():
    from core.secure_compute_market import create_secure_market
    market = create_secure_market()
    assert market is not None

def test_key_derivation():
    from core.secure_compute_market import KeyDerivationEngine
    engine = KeyDerivationEngine()
    key_id, key_material = engine.generate_task_key("task_001")
    assert key_id is not None
    derived = engine.derive_miner_key(key_id, key_material, "worker_001")
    assert derived is not None

def test_task_sharding():
    from core.secure_compute_market import TaskShardingEngine
    engine = TaskShardingEngine()
    shards = engine.shard_task(
        "task_shard_001",
        b"code_data_here",
        b"x" * 1000,
        b"args_here",
        num_shards=3
    )
    assert len(shards) >= 3  # 每种数据类型独立分片，总数 = code分片 + data分片 + args分片

_run_test("安全算力市场创建", test_secure_market_create)
_run_test("密钥派生引擎", test_key_derivation)
_run_test("任务分片引擎", test_task_sharding)


# ================================================================
# 3. 测试 tee_computing.py (TEE 可信执行环境)
# ================================================================
print("\n" + "=" * 60)
print("3. 测试 tee_computing.py (TEE 可信执行环境)")
print("=" * 60)

def test_tee_register():
    from core.tee_computing import TEEManager, TEEType
    mgr = TEEManager()
    result = mgr.register_tee_node("node_001", TEEType.INTEL_SGX)
    assert result is not None

def test_tee_attestation():
    from core.tee_computing import TEEManager, TEEType
    mgr = TEEManager()
    mgr.register_tee_node("node_att", TEEType.INTEL_SGX)
    ok = mgr.submit_attestation(
        "node_att",
        mrenclave="a" * 64,
        mrsigner="b" * 64
    )
    assert ok

def test_tee_hardware_detection():
    from core.tee_computing import get_tee_system, TEEManager
    system = get_tee_system()
    assert isinstance(system, dict)
    assert "tee_manager" in system
    result = TEEManager.detect_hardware_tee()
    assert "available" in result
    assert "detected_types" in result
    assert "platform" in result

_run_test("TEE 节点注册", test_tee_register)
_run_test("TEE 认证报告提交", test_tee_attestation)
_run_test("TEE 硬件检测", test_tee_hardware_detection)


# ================================================================
# 结果汇总
# ================================================================
print("\n" + "=" * 60)
print(f"测试结果汇总")
print("=" * 60)
print(f"  ✅ 通过: {PASS}")
print(f"  ⚠️  警告: {WARN}")
print(f"  ❌ 失败: {FAIL}")
print(f"  总计: {PASS + WARN + FAIL}")
print("=" * 60)

if FAIL > 0:
    print("⚠️ 有测试失败，需要修复！")
else:
    print("🎉 所有测试通过!")
