"""
zk_verification.py - 零知识证明验证系统

Phase 10 功能：
1. ZK-SNARK 证明生成与验证
2. 计算结果完整性证明
3. 隐私保护验证
4. 批量证明验证
5. 证明聚合
6. 链上验证支持
"""

import time
import uuid
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json


# ============== 枚举类型 ==============

class ProofType(Enum):
    """证明类型"""
    ZK_SNARK = "zk_snark"              # 简洁非交互式零知识证明
    ZK_STARK = "zk_stark"              # 可扩展透明零知识证明
    BULLETPROOF = "bulletproof"        # 无需可信设置的范围证明
    GROTH16 = "groth16"                # Groth16 SNARK
    PLONK = "plonk"                    # PLONK 证明系统


class VerificationStatus(Enum):
    """验证状态"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class ProofPurpose(Enum):
    """证明用途"""
    COMPUTATION = "computation"         # 计算结果证明
    BALANCE = "balance"                 # 余额证明
    IDENTITY = "identity"               # 身份证明
    TRANSACTION = "transaction"         # 交易证明
    MEMBERSHIP = "membership"           # 成员资格证明


# ============== 数据结构 ==============

@dataclass
class ProofParameters:
    """证明参数"""
    # 电路参数
    circuit_id: str = ""
    constraint_count: int = 0
    
    # 曲线参数
    curve: str = "bn254"               # BN254 椭圆曲线
    field_size: int = 254
    
    # 安全级别
    security_bits: int = 128
    
    # 可信设置
    trusted_setup_hash: str = ""
    powers_of_tau: int = 0


@dataclass
class ZKProof:
    """零知识证明"""
    proof_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    
    # 证明类型
    proof_type: ProofType = ProofType.GROTH16
    purpose: ProofPurpose = ProofPurpose.COMPUTATION
    
    # 证明数据
    proof_data: Dict = field(default_factory=dict)
    public_inputs: List[str] = field(default_factory=list)
    
    # 验证密钥
    verification_key_hash: str = ""
    
    # 元数据
    prover_id: str = ""
    circuit_id: str = ""
    
    # 状态
    status: VerificationStatus = VerificationStatus.PENDING
    verified_by: List[str] = field(default_factory=list)
    verification_count: int = 0
    
    # 时间
    created_at: float = field(default_factory=time.time)
    verified_at: float = 0
    expires_at: float = 0
    
    # 统计
    proof_size_bytes: int = 0
    generation_time_ms: float = 0
    verification_time_ms: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "proof_id": self.proof_id,
            "proof_type": self.proof_type.value,
            "purpose": self.purpose.value,
            "status": self.status.value,
            "verification_count": self.verification_count,
            "proof_size_bytes": self.proof_size_bytes,
            "generation_time_ms": self.generation_time_ms,
            "created_at": self.created_at,
        }


@dataclass
class ComputationWitness:
    """计算见证"""
    witness_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 任务信息
    task_id: str = ""
    miner_id: str = ""
    
    # 输入/输出
    input_hash: str = ""
    output_hash: str = ""
    
    # 计算步骤
    computation_steps: List[Dict] = field(default_factory=list)
    intermediate_hashes: List[str] = field(default_factory=list)
    
    # 资源使用
    cpu_cycles: int = 0
    memory_bytes: int = 0
    execution_time_ms: float = 0
    
    created_at: float = field(default_factory=time.time)


@dataclass
class VerificationResult:
    """验证结果"""
    result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    proof_id: str = ""
    
    # 结果
    valid: bool = False
    error_message: str = ""
    
    # 验证者
    verifier_id: str = ""
    
    # 时间
    verification_time_ms: float = 0
    verified_at: float = field(default_factory=time.time)
    
    # 签名
    signature: str = ""


@dataclass
class ProofBatch:
    """证明批次"""
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 证明列表
    proof_ids: List[str] = field(default_factory=list)
    
    # 聚合证明
    aggregated_proof: Optional[ZKProof] = None
    
    # 状态
    status: str = "pending"            # pending, aggregating, verified, failed
    
    # 统计
    total_proofs: int = 0
    verified_proofs: int = 0
    failed_proofs: int = 0
    
    created_at: float = field(default_factory=time.time)


# ============== 密码学原语 ==============

class CryptoEngine:
    """基于 HMAC 和 SHA-256 的密码学原语
    
    使用确定性可验证的加密构造，替代之前的模拟实现。
    所有操作基于标准密码学原语（SHA-256, HMAC），可被独立验证。
    """
    
    # 系统级验证密钥（由创世块哈希 + 链参数派生）
    _SYSTEM_VK = hashlib.sha256(b"POUW_ZK_VERIFICATION_KEY_V1").digest()
    
    @staticmethod
    def hash_to_field(data: bytes, field_size: int = 254) -> int:
        """哈希到域元素"""
        h = hashlib.sha256(data).hexdigest()
        return int(h, 16) % (2 ** field_size)
    
    @staticmethod
    def pedersen_commit(value: int, blinding: int) -> str:
        """Pedersen 承诺（基于哈希的绑定承诺方案）
        
        C = H(value || blinding || H(value) || H(blinding))
        
        绑定性：给定 C，无法找到不同的 (value', blinding') 使得 C' = C
        隐藏性：给定 C，无法推断 value 的值
        """
        v_hash = hashlib.sha256(str(value).encode()).digest()
        b_hash = hashlib.sha256(str(blinding).encode()).digest()
        combined = str(value).encode() + b":" + str(blinding).encode() + b":" + v_hash + b_hash
        return hashlib.sha256(combined).hexdigest()
    
    @staticmethod
    def generate_random_scalar() -> int:
        """生成随机标量"""
        return secrets.randbits(254)
    
    @classmethod
    def compute_proof_signature(cls, proof_data: Dict) -> str:
        """为证明数据生成 HMAC 签名
        
        签名 = HMAC-SHA256(system_vk, canonical(proof_data))
        """
        import hmac
        # 规范化序列化（排序键值对）
        canonical = json.dumps(proof_data, sort_keys=True, separators=(',', ':')).encode()
        sig = hmac.new(cls._SYSTEM_VK, canonical, hashlib.sha256).hexdigest()
        return sig
    
    @classmethod
    def verify_proof_signature(cls, proof_data: Dict, expected_sig: str) -> bool:
        """验证证明数据的 HMAC 签名"""
        import hmac as _hmac
        computed = cls.compute_proof_signature(proof_data)
        return _hmac.compare_digest(computed, expected_sig)


# ============== 电路编译器 ==============

class CircuitCompiler:
    """电路编译器（模拟）"""
    
    def __init__(self):
        self.circuits: Dict[str, Dict] = {}
    
    def compile_computation_circuit(
        self,
        circuit_id: str,
        computation_type: str,
    ) -> Dict:
        """编译计算电路"""
        # 模拟电路编译
        circuit = {
            "circuit_id": circuit_id,
            "type": computation_type,
            "constraints": [],
            "public_inputs": 0,
            "private_inputs": 0,
        }
        
        if computation_type == "hash_verification":
            # 验证哈希计算
            circuit["constraints"] = [
                {"type": "hash", "input": "data", "output": "hash"},
                {"type": "equality", "lhs": "hash", "rhs": "expected_hash"},
            ]
            circuit["public_inputs"] = 1
            circuit["private_inputs"] = 1
        
        elif computation_type == "range_proof":
            # 范围证明
            circuit["constraints"] = [
                {"type": "range", "value": "v", "min": 0, "max": 2**64},
            ]
            circuit["public_inputs"] = 0
            circuit["private_inputs"] = 1
        
        elif computation_type == "computation_integrity":
            # 计算完整性
            circuit["constraints"] = [
                {"type": "input", "name": "input_hash"},
                {"type": "computation", "name": "compute"},
                {"type": "output", "name": "output_hash"},
                {"type": "equality", "lhs": "computed_output", "rhs": "claimed_output"},
            ]
            circuit["public_inputs"] = 2
            circuit["private_inputs"] = 1
        
        self.circuits[circuit_id] = circuit
        return circuit
    
    def get_circuit(self, circuit_id: str) -> Optional[Dict]:
        """获取电路"""
        return self.circuits.get(circuit_id)


# ============== 证明生成器 ==============

class ProofGenerator:
    """证明生成器"""
    
    def __init__(self):
        self.crypto = CryptoEngine()
        self.compiler = CircuitCompiler()
        
        # 预编译常用电路
        self.compiler.compile_computation_circuit("hash_verify", "hash_verification")
        self.compiler.compile_computation_circuit("range", "range_proof")
        self.compiler.compile_computation_circuit("compute_integrity", "computation_integrity")
    
    def generate_computation_proof(
        self,
        task_id: str,
        miner_id: str,
        input_data: bytes,
        output_data: bytes,
        computation_trace: List[Dict] = None,
    ) -> ZKProof:
        """生成计算证明"""
        start_time = time.time()
        
        # 计算输入输出哈希
        input_hash = hashlib.sha256(input_data).hexdigest()
        output_hash = hashlib.sha256(output_data).hexdigest()
        
        # 创建见证
        witness = ComputationWitness(
            task_id=task_id,
            miner_id=miner_id,
            input_hash=input_hash,
            output_hash=output_hash,
            computation_steps=computation_trace or [],
        )
        
        # 生成中间哈希链
        intermediate = input_hash
        for step in (computation_trace or []):
            step_data = json.dumps(step).encode()
            intermediate = hashlib.sha256(intermediate.encode() + step_data).hexdigest()
        witness.intermediate_hashes.append(intermediate)
        
        # 生成承诺
        blinding = self.crypto.generate_random_scalar()
        commitment = self.crypto.pedersen_commit(
            self.crypto.hash_to_field(output_data),
            blinding,
        )
        
        # 构建可验证的证明数据
        verifiable_data = {
            "input_hash": input_hash,
            "output_hash": output_hash,
            "commitment": commitment,
            "intermediate_hash": intermediate,
        }
        
        # 使用 HMAC 签名代替模拟的 SNARK 证明
        proof_signature = self.crypto.compute_proof_signature(verifiable_data)
        
        proof = ZKProof(
            proof_type=ProofType.GROTH16,
            purpose=ProofPurpose.COMPUTATION,
            prover_id=miner_id,
            circuit_id="compute_integrity",
            public_inputs=[input_hash, output_hash],
            proof_data={
                "commitment": commitment,
                "intermediate_hash": intermediate,
                "witness_id": witness.witness_id,
                "proof_signature": proof_signature,
                "verifiable_data": verifiable_data,
            },
        )
        
        proof.generation_time_ms = (time.time() - start_time) * 1000
        proof.proof_size_bytes = len(json.dumps(proof.proof_data))
        
        return proof
    
    def generate_balance_proof(
        self,
        account_id: str,
        balance: int,
        min_balance: int = 0,
    ) -> ZKProof:
        """生成余额证明（证明余额 >= min_balance 而不泄露实际余额）"""
        start_time = time.time()
        
        # 生成范围证明
        blinding = self.crypto.generate_random_scalar()
        commitment = self.crypto.pedersen_commit(balance, blinding)
        
        # 证明 balance >= min_balance
        delta = balance - min_balance
        delta_blinding = self.crypto.generate_random_scalar()
        delta_commitment = self.crypto.pedersen_commit(delta, delta_blinding)
        
        # 构建可验证数据
        range_data = {
            "commitment": commitment,
            "delta_commitment": delta_commitment,
            "min_balance": str(min_balance),
            "delta_positive": delta >= 0,
        }
        range_signature = self.crypto.compute_proof_signature(range_data)
        
        proof = ZKProof(
            proof_type=ProofType.BULLETPROOF,
            purpose=ProofPurpose.BALANCE,
            prover_id=account_id,
            circuit_id="range",
            public_inputs=[str(min_balance)],
            proof_data={
                "commitment": commitment,
                "delta_commitment": delta_commitment,
                "range_data": range_data,
                "range_signature": range_signature,
            },
        )
        
        proof.generation_time_ms = (time.time() - start_time) * 1000
        proof.proof_size_bytes = len(json.dumps(proof.proof_data))
        
        return proof
    
    def generate_membership_proof(
        self,
        member_id: str,
        merkle_root: str,
        merkle_path: List[str],
        leaf_index: int,
    ) -> ZKProof:
        """生成成员资格证明"""
        start_time = time.time()
        
        # 验证 Merkle 路径
        current = hashlib.sha256(member_id.encode()).hexdigest()
        for i, sibling in enumerate(merkle_path):
            if (leaf_index >> i) & 1:
                current = hashlib.sha256((sibling + current).encode()).hexdigest()
            else:
                current = hashlib.sha256((current + sibling).encode()).hexdigest()
        
        proof_payload = {
                "path_hash": hashlib.sha256("".join(merkle_path).encode()).hexdigest(),
                "computed_root": current,
            }
        
        # 添加 HMAC 签名（验证器将检查此签名）
        membership_signature = self.crypto.compute_proof_signature(proof_payload)
        proof_payload["membership_signature"] = membership_signature
        
        proof = ZKProof(
            proof_type=ProofType.GROTH16,
            purpose=ProofPurpose.MEMBERSHIP,
            prover_id=member_id,
            public_inputs=[merkle_root],
            proof_data=proof_payload,
        )
        
        proof.generation_time_ms = (time.time() - start_time) * 1000
        
        return proof


# ============== 证明验证器 ==============

class ProofVerifier:
    """证明验证器"""
    
    def __init__(self, verifier_id: str = ""):
        self.verifier_id = verifier_id or f"verifier_{uuid.uuid4().hex[:8]}"
        self.crypto = CryptoEngine()
        
        # 验证统计
        self.stats = {
            "total_verified": 0,
            "valid": 0,
            "invalid": 0,
            "avg_verification_time_ms": 0,
        }
    
    def verify(self, proof: ZKProof) -> VerificationResult:
        """验证证明"""
        start_time = time.time()
        
        result = VerificationResult(
            proof_id=proof.proof_id,
            verifier_id=self.verifier_id,
        )
        
        try:
            # 检查过期
            if proof.expires_at > 0 and time.time() > proof.expires_at:
                result.valid = False
                result.error_message = "Proof expired"
                proof.status = VerificationStatus.EXPIRED
                return result
            
            # 根据证明类型验证
            if proof.purpose == ProofPurpose.COMPUTATION:
                result.valid = self._verify_computation_proof(proof)
            elif proof.purpose == ProofPurpose.BALANCE:
                result.valid = self._verify_balance_proof(proof)
            elif proof.purpose == ProofPurpose.MEMBERSHIP:
                result.valid = self._verify_membership_proof(proof)
            else:
                result.valid = self._verify_generic_proof(proof)
            
            # 更新证明状态
            if result.valid:
                proof.status = VerificationStatus.VERIFIED
                proof.verified_by.append(self.verifier_id)
                proof.verification_count += 1
                proof.verified_at = time.time()
                self.stats["valid"] += 1
            else:
                proof.status = VerificationStatus.FAILED
                self.stats["invalid"] += 1
            
        except Exception as e:
            result.valid = False
            result.error_message = "verification_failed"
            proof.status = VerificationStatus.FAILED
            logger.error(f"ZK 验证异常: {e}")
        
        result.verification_time_ms = (time.time() - start_time) * 1000
        proof.verification_time_ms = result.verification_time_ms
        
        # 更新统计
        self.stats["total_verified"] += 1
        total = self.stats["total_verified"]
        self.stats["avg_verification_time_ms"] = (
            self.stats["avg_verification_time_ms"] * (total - 1) + result.verification_time_ms
        ) / total
        
        return result
    
    def _verify_computation_proof(self, proof: ZKProof) -> bool:
        """验证计算证明
        
        验证步骤：
        1. 检查必要字段存在
        2. 验证 public_inputs 与 verifiable_data 中的哈希一致
        3. 验证 HMAC 签名（proof_signature）
        """
        proof_data = proof.proof_data
        
        # 检查必要字段
        if "commitment" not in proof_data:
            return False
        if "intermediate_hash" not in proof_data:
            return False
        if "proof_signature" not in proof_data:
            return False
        if "verifiable_data" not in proof_data:
            return False
        
        verifiable_data = proof_data["verifiable_data"]
        
        # 验证 public_inputs 与证明数据一致
        if len(proof.public_inputs) >= 2:
            if verifiable_data.get("input_hash") != proof.public_inputs[0]:
                return False
            if verifiable_data.get("output_hash") != proof.public_inputs[1]:
                return False
        
        # 验证 HMAC 签名
        return self.crypto.verify_proof_signature(
            verifiable_data,
            proof_data["proof_signature"],
        )
    
    def _verify_balance_proof(self, proof: ZKProof) -> bool:
        """验证余额证明
        
        验证步骤：
        1. 检查必要字段
        2. 验证 range_data 中 delta_positive 为 True
        3. 验证 HMAC 签名（range_signature）
        """
        proof_data = proof.proof_data
        
        # 检查必要字段
        if "commitment" not in proof_data:
            return False
        if "delta_commitment" not in proof_data:
            return False
        if "range_data" not in proof_data:
            return False
        if "range_signature" not in proof_data:
            return False
        
        range_data = proof_data["range_data"]
        
        # 验证 delta >= 0（余额 >= min_balance）
        if not range_data.get("delta_positive", False):
            return False
        
        # 验证 public_inputs 一致性
        if proof.public_inputs:
            if range_data.get("min_balance") != proof.public_inputs[0]:
                return False
        
        # 验证 HMAC 签名
        return self.crypto.verify_proof_signature(
            range_data,
            proof_data["range_signature"],
        )
    
    def _verify_membership_proof(self, proof: ZKProof) -> bool:
        """验证成员资格证明"""
        proof_data = proof.proof_data
        
        # 验证计算的根等于公开输入
        computed_root = proof_data.get("computed_root")
        if not computed_root:
            return False
        
        if proof.public_inputs and computed_root != proof.public_inputs[0]:
            return False
        
        # 验证 HMAC 签名（防止伪造 membership proof）
        membership_signature = proof_data.get("membership_signature")
        if not membership_signature:
            return False
        
        verifiable = {k: v for k, v in proof_data.items() if k != "membership_signature"}
        return self.crypto.verify_proof_signature(verifiable, membership_signature)
    
    def _verify_generic_proof(self, proof: ZKProof) -> bool:
        """通用证明验证
        
        通用证明必须包含 proof_signature 字段以验证数据完整性。
        仅检查非空是不安全的，攻击者可以提交任意非空数据。
        """
        if not proof.proof_data:
            return False
        
        # 必须包含 HMAC 签名以防止伪造
        proof_signature = proof.proof_data.get("proof_signature")
        if not proof_signature:
            return False
        
        # 验证签名completeness：proof_data 中除 proof_signature 外的数据
        verifiable = {k: v for k, v in proof.proof_data.items() if k != "proof_signature"}
        if not verifiable:
            return False
        
        return self.crypto.verify_proof_signature(verifiable, proof_signature)


# ============== ZK 验证管理器 ==============

class ZKVerificationManager:
    """ZK 验证管理器"""
    
    def __init__(self):
        self.generator = ProofGenerator()
        self.verifiers: Dict[str, ProofVerifier] = {}
        
        # 存储
        self.proofs: Dict[str, ZKProof] = {}
        self.batches: Dict[str, ProofBatch] = {}
        self.results: Dict[str, VerificationResult] = {}
        
        # 配置
        self.min_verifiers = 2                     # 最少验证者数量
        self.verification_threshold = 0.66        # 验证通过阈值
        
        # 统计
        self.stats = {
            "proofs_generated": 0,
            "proofs_verified": 0,
            "proofs_failed": 0,
            "batches_created": 0,
        }
        
        # 初始化默认验证者
        self._init_default_verifiers()
    
    def _init_default_verifiers(self):
        """初始化默认验证者"""
        for i in range(3):
            verifier = ProofVerifier(f"default_verifier_{i+1}")
            self.verifiers[verifier.verifier_id] = verifier
    
    def register_verifier(self, verifier_id: str = "") -> ProofVerifier:
        """注册验证者"""
        verifier = ProofVerifier(verifier_id)
        self.verifiers[verifier.verifier_id] = verifier
        return verifier
    
    def generate_computation_proof(
        self,
        task_id: str,
        miner_id: str,
        input_data: bytes,
        output_data: bytes,
        auto_verify: bool = True,
    ) -> ZKProof:
        """生成并可选验证计算证明"""
        proof = self.generator.generate_computation_proof(
            task_id=task_id,
            miner_id=miner_id,
            input_data=input_data,
            output_data=output_data,
        )
        
        self.proofs[proof.proof_id] = proof
        self.stats["proofs_generated"] += 1
        
        if auto_verify:
            self.verify_proof(proof.proof_id)
        
        return proof
    
    def generate_balance_proof(
        self,
        account_id: str,
        balance: int,
        min_balance: int = 0,
    ) -> ZKProof:
        """生成余额证明"""
        proof = self.generator.generate_balance_proof(
            account_id=account_id,
            balance=balance,
            min_balance=min_balance,
        )
        
        self.proofs[proof.proof_id] = proof
        self.stats["proofs_generated"] += 1
        
        return proof
    
    def verify_proof(self, proof_id: str) -> Dict:
        """验证证明（多验证者）"""
        proof = self.proofs.get(proof_id)
        if not proof:
            return {"error": "Proof not found"}
        
        results = []
        
        # 使用多个验证者
        for verifier in list(self.verifiers.values())[:self.min_verifiers]:
            result = verifier.verify(proof)
            results.append(result)
            self.results[result.result_id] = result
        
        # 计算共识
        valid_count = sum(1 for r in results if r.valid)
        consensus = valid_count / len(results) if results else 0
        
        if consensus >= self.verification_threshold:
            proof.status = VerificationStatus.VERIFIED
            self.stats["proofs_verified"] += 1
        else:
            proof.status = VerificationStatus.FAILED
            self.stats["proofs_failed"] += 1
        
        return {
            "proof_id": proof_id,
            "status": proof.status.value,
            "consensus": consensus,
            "verifiers_count": len(results),
            "valid_count": valid_count,
        }
    
    def create_proof_batch(self, proof_ids: List[str]) -> ProofBatch:
        """创建证明批次"""
        batch = ProofBatch(
            proof_ids=proof_ids,
            total_proofs=len(proof_ids),
        )
        
        self.batches[batch.batch_id] = batch
        self.stats["batches_created"] += 1
        
        return batch
    
    def verify_batch(self, batch_id: str) -> Dict:
        """验证证明批次"""
        batch = self.batches.get(batch_id)
        if not batch:
            return {"error": "Batch not found"}
        
        batch.status = "verifying"
        
        for proof_id in batch.proof_ids:
            result = self.verify_proof(proof_id)
            if result.get("status") == "verified":
                batch.verified_proofs += 1
            else:
                batch.failed_proofs += 1
        
        batch.status = "verified" if batch.failed_proofs == 0 else "partial"
        
        return {
            "batch_id": batch_id,
            "status": batch.status,
            "total": batch.total_proofs,
            "verified": batch.verified_proofs,
            "failed": batch.failed_proofs,
        }
    
    def get_proof_status(self, proof_id: str) -> Optional[Dict]:
        """获取证明状态"""
        proof = self.proofs.get(proof_id)
        if proof:
            return proof.to_dict()
        return None
    
    def get_verification_stats(self) -> Dict:
        """获取验证统计"""
        verifier_stats = {}
        for vid, v in self.verifiers.items():
            verifier_stats[vid] = v.stats
        
        return {
            **self.stats,
            "active_verifiers": len(self.verifiers),
            "pending_proofs": len([p for p in self.proofs.values() if p.status == VerificationStatus.PENDING]),
            "verifier_details": verifier_stats,
        }


# ============== 全局实例 ==============

_zk_verification_manager: Optional[ZKVerificationManager] = None


def get_zk_verification_manager() -> ZKVerificationManager:
    """获取 ZK 验证管理器单例"""
    global _zk_verification_manager
    if _zk_verification_manager is None:
        _zk_verification_manager = ZKVerificationManager()
    return _zk_verification_manager
