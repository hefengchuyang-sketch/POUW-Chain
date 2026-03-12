"""
did_identity.py - 去中心化身份与反女巫攻击

Phase 9 功能：
1. 去中心化身份 (DID)
2. 防止刷信誉 / 女巫攻击
3. DID 与历史算力行为绑定
4. 信誉不可转移
5. 高信誉节点特权
"""

import time
import uuid
import hashlib
import secrets
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from collections import defaultdict
import json

try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
    from ecdsa.util import sigencode_der, sigdecode_der
    _HAS_ECDSA = True
except ImportError:
    _HAS_ECDSA = False


# ============== 枚举类型 ==============

class DIDMethod(Enum):
    """DID 方法"""
    POUW = "did:pouw"                  # POUW Chain DID
    KEY = "did:key"                    # Key-based DID
    WEB = "did:web"                    # Web DID


class VerificationMethod(Enum):
    """验证方法"""
    ED25519 = "Ed25519VerificationKey2020"
    SECP256K1 = "EcdsaSecp256k1VerificationKey2019"
    RSA = "RsaVerificationKey2018"


class CredentialType(Enum):
    """凭证类型"""
    IDENTITY = "identity"              # 身份凭证
    REPUTATION = "reputation"          # 信誉凭证
    COMPUTE_HISTORY = "compute_history" # 算力历史凭证
    KYC = "kyc"                        # KYC 凭证
    STAKE = "stake"                    # 质押凭证


class SybilRiskLevel(Enum):
    """女巫攻击风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReputationTier(Enum):
    """信誉等级"""
    NEWCOMER = "newcomer"              # 新人
    BRONZE = "bronze"                  # 青铜
    SILVER = "silver"                  # 白银
    GOLD = "gold"                      # 黄金
    PLATINUM = "platinum"              # 白金
    DIAMOND = "diamond"                # 钻石


# ============== 数据结构 ==============

@dataclass
class DIDDocument:
    """DID 文档"""
    did: str                           # DID 标识符
    controller: str = ""               # 控制者
    
    # 验证方法
    verification_methods: List[Dict] = field(default_factory=list)
    authentication: List[str] = field(default_factory=list)
    assertion_method: List[str] = field(default_factory=list)
    
    # 服务端点
    service_endpoints: List[Dict] = field(default_factory=list)
    
    # 时间
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    
    # 元数据
    version: int = 1
    deactivated: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": self.did,
            "controller": self.controller or self.did,
            "verificationMethod": self.verification_methods,
            "authentication": self.authentication,
            "service": self.service_endpoints,
            "created": self.created,
            "updated": self.updated,
        }


@dataclass
class VerifiableCredential:
    """可验证凭证"""
    credential_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    credential_type: CredentialType = CredentialType.IDENTITY
    
    # 发行者和持有者
    issuer: str = ""                   # 发行者 DID
    holder: str = ""                   # 持有者 DID
    
    # 凭证内容
    claims: Dict = field(default_factory=dict)
    
    # 有效期
    issuance_date: float = field(default_factory=time.time)
    expiration_date: float = 0
    
    # 签名
    proof: Dict = field(default_factory=dict)
    
    # 状态
    revoked: bool = False
    revoked_at: float = 0
    
    def is_valid(self) -> bool:
        """检查凭证是否有效"""
        if self.revoked:
            return False
        if self.expiration_date > 0 and time.time() > self.expiration_date:
            return False
        return True
    
    def to_dict(self) -> Dict:
        return {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "id": self.credential_id,
            "type": ["VerifiableCredential", self.credential_type.value],
            "issuer": self.issuer,
            "holder": self.holder,
            "issuanceDate": self.issuance_date,
            "expirationDate": self.expiration_date,
            "credentialSubject": self.claims,
            "proof": self.proof,
        }


@dataclass
class IdentityBinding:
    """身份绑定"""
    did: str
    
    # 绑定的地址
    wallet_addresses: List[str] = field(default_factory=list)
    miner_ids: List[str] = field(default_factory=list)
    
    # 历史
    compute_history: List[Dict] = field(default_factory=list)
    total_compute_hours: float = 0
    total_tasks_completed: int = 0
    
    # 信誉
    reputation_score: float = 0
    reputation_tier: ReputationTier = ReputationTier.NEWCOMER
    reputation_locked: bool = True     # 信誉不可转移
    
    # 质押
    staked_amount: float = 0
    stake_locked_until: float = 0
    
    # 注册时间
    registered_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


@dataclass
class SybilAnalysis:
    """女巫攻击分析"""
    subject_did: str
    analysis_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 风险评估
    risk_level: SybilRiskLevel = SybilRiskLevel.LOW
    risk_score: float = 0              # 0-100
    
    # 检测因素
    factors: List[Dict] = field(default_factory=list)
    
    # 关联分析
    related_dids: List[str] = field(default_factory=list)
    ip_clusters: List[str] = field(default_factory=list)
    behavior_similarity: float = 0
    
    # 时间
    analyzed_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "analysis_id": self.analysis_id,
            "subject_did": self.subject_did,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "factors": self.factors,
            "related_dids": self.related_dids,
            "analyzed_at": self.analyzed_at,
        }


# ============== DID 管理器 ==============

class DIDManager:
    """DID 管理器"""
    
    def __init__(self):
        self.did_documents: Dict[str, DIDDocument] = {}
        self.credentials: Dict[str, VerifiableCredential] = {}
        self.bindings: Dict[str, IdentityBinding] = {}
        self._lock = threading.RLock()
        
        # 索引
        self.wallet_to_did: Dict[str, str] = {}
        self.miner_to_did: Dict[str, str] = {}
    
    def create_did(
        self,
        public_key: str,
        verification_method: VerificationMethod = VerificationMethod.ED25519,
    ) -> DIDDocument:
        """创建 DID"""
        with self._lock:
            # 生成 DID
            did_suffix = hashlib.sha256(public_key.encode()).hexdigest()[:32]
            did = f"did:pouw:{did_suffix}"
            
            # 创建验证方法
            vm_id = f"{did}#keys-1"
            vm = {
                "id": vm_id,
                "type": verification_method.value,
                "controller": did,
                "publicKeyHex": public_key,
            }
            
            # 创建 DID 文档
            doc = DIDDocument(
                did=did,
                controller=did,
                verification_methods=[vm],
                authentication=[vm_id],
                assertion_method=[vm_id],
            )
            
            self.did_documents[did] = doc
            
            # 创建身份绑定
            binding = IdentityBinding(did=did)
            self.bindings[did] = binding
            
            return doc
    
    def resolve_did(self, did: str) -> Optional[DIDDocument]:
        """解析 DID"""
        with self._lock:
            return self.did_documents.get(did)
    
    def bind_wallet(self, did: str, wallet_address: str) -> bool:
        """绑定钱包地址"""
        with self._lock:
            # 检查钱包是否已绑定
            if wallet_address in self.wallet_to_did:
                return False
            
            binding = self.bindings.get(did)
            if not binding:
                return False
            
            binding.wallet_addresses.append(wallet_address)
            self.wallet_to_did[wallet_address] = did
            
            return True
    
    def bind_miner(self, did: str, miner_id: str) -> bool:
        """绑定矿工 ID"""
        with self._lock:
            # 检查矿工是否已绑定
            if miner_id in self.miner_to_did:
                return False
            
            binding = self.bindings.get(did)
            if not binding:
                return False
            
            binding.miner_ids.append(miner_id)
            self.miner_to_did[miner_id] = did
            
            return True
    
    def get_did_by_wallet(self, wallet_address: str) -> Optional[str]:
        """通过钱包获取 DID"""
        with self._lock:
            return self.wallet_to_did.get(wallet_address)
    
    def get_did_by_miner(self, miner_id: str) -> Optional[str]:
        """通过矿工 ID 获取 DID"""
        with self._lock:
            return self.miner_to_did.get(miner_id)
    
    def issue_credential(
        self,
        issuer_did: str,
        holder_did: str,
        credential_type: CredentialType,
        claims: Dict,
        expiry_days: int = 365,
        signing_key_hex: str = None,
    ) -> VerifiableCredential:
        """发行凭证
        
        Args:
            signing_key_hex: 发行者 ECDSA 私钥(hex)。提供时用真正的数字签名，
                             否则退化为 SHA-256 哈希（仅向后兼容）。
        """
        with self._lock:
            credential = VerifiableCredential(
                credential_type=credential_type,
                issuer=issuer_did,
                holder=holder_did,
                claims=claims,
                expiration_date=time.time() + expiry_days * 86400 if expiry_days > 0 else 0,
            )
            
            # 创建证明
            proof_data = f"{issuer_did}{holder_did}{json.dumps(claims, sort_keys=True)}"
            proof_bytes = proof_data.encode()
            
            if signing_key_hex and _HAS_ECDSA:
                # 真正的 ECDSA 签名
                try:
                    sk = SigningKey.from_string(bytes.fromhex(signing_key_hex), curve=SECP256k1)
                    signature = sk.sign(proof_bytes, sigencode=sigencode_der)
                    credential.proof = {
                        "type": "EcdsaSecp256k1Signature2019",
                        "created": time.time(),
                        "proofPurpose": "assertionMethod",
                        "verificationMethod": f"{issuer_did}#keys-1",
                        "proofValue": signature.hex(),
                    }
                except Exception:
                    # 签名失败，退化为哈希
                    credential.proof = {
                        "type": "Sha256Hash2023",
                        "created": time.time(),
                        "proofPurpose": "assertionMethod",
                        "verificationMethod": f"{issuer_did}#keys-1",
                        "proofValue": hashlib.sha256(proof_bytes).hexdigest(),
                    }
            else:
                # 无私钥时退化为哈希（向后兼容，安全性降低）
                credential.proof = {
                    "type": "Sha256Hash2023",
                    "created": time.time(),
                    "proofPurpose": "assertionMethod",
                    "verificationMethod": f"{issuer_did}#keys-1",
                    "proofValue": hashlib.sha256(proof_bytes).hexdigest(),
                }
            
            self.credentials[credential.credential_id] = credential
            return credential
    
    def verify_credential(self, credential_id: str) -> Dict:
        """验证凭证（包括密码学签名验证）"""
        with self._lock:
            credential = self.credentials.get(credential_id)
            if not credential:
                return {"valid": False, "reason": "Credential not found"}
            
            if credential.revoked:
                return {"valid": False, "reason": "Credential revoked"}
            
            if not credential.is_valid():
                return {"valid": False, "reason": "Credential expired"}
            
            # 验证签名
            proof = credential.proof or {}
            proof_type = proof.get("type", "")
            
            if proof_type == "EcdsaSecp256k1Signature2019" and _HAS_ECDSA:
                # 完整的密码学签名验证
                vm_id = proof.get("verificationMethod", "")
                issuer_did = credential.issuer
                did_doc = self.did_documents.get(issuer_did)
                
                if not did_doc:
                    return {"valid": False, "reason": "Issuer DID document not found"}
                
                # 从 DID 文档获取公钥
                pubkey_hex = None
                for vm in did_doc.verification_methods:
                    if isinstance(vm, dict) and vm.get("id") == vm_id:
                        pubkey_hex = vm.get("publicKeyHex")
                        break
                
                if not pubkey_hex:
                    return {"valid": False, "reason": "Verification method not found in DID document"}
                
                try:
                    vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
                    proof_data = f"{credential.issuer}{credential.holder}{json.dumps(credential.claims, sort_keys=True)}"
                    signature = bytes.fromhex(proof.get("proofValue", ""))
                    vk.verify(signature, proof_data.encode(), sigdecode=sigdecode_der)
                except (BadSignatureError, Exception):
                    return {"valid": False, "reason": "Signature verification failed"}
            elif proof_type == "Sha256Hash2023":
                # SHA256 哈希验证（向后兼容，安全性低于 ECDSA）
                # 必须重新计算哈希并比对，防止 claims 被篡改
                proof_data = f"{credential.issuer}{credential.holder}{json.dumps(credential.claims, sort_keys=True)}"
                expected_hash = hashlib.sha256(proof_data.encode()).hexdigest()
                actual_hash = proof.get("proofValue", "")
                if expected_hash != actual_hash:
                    return {"valid": False, "reason": "SHA256 proof hash mismatch — credential may have been tampered with"}
            else:
                # 未知的证明类型，拒绝验证
                return {"valid": False, "reason": f"Unknown proof type: {proof_type}"}
            
            return {
                "valid": True,
                "credential_type": credential.credential_type.value,
                "issuer": credential.issuer,
                "holder": credential.holder,
                "signature_type": proof_type,
            }
    
    def get_binding(self, did: str) -> Optional[Dict]:
        """获取身份绑定"""
        with self._lock:
            binding = self.bindings.get(did)
            if binding:
                return {
                    "did": binding.did,
                    "wallet_addresses": binding.wallet_addresses,
                    "miner_ids": binding.miner_ids,
                    "total_compute_hours": binding.total_compute_hours,
                    "total_tasks_completed": binding.total_tasks_completed,
                    "reputation_score": binding.reputation_score,
                    "reputation_tier": binding.reputation_tier.value,
                    "staked_amount": binding.staked_amount,
                    "registered_at": binding.registered_at,
                }
            return None


# ============== 信誉系统 ==============

class ReputationSystem:
    """信誉系统"""
    
    # 信誉等级阈值
    TIER_THRESHOLDS = {
        ReputationTier.NEWCOMER: 0,
        ReputationTier.BRONZE: 100,
        ReputationTier.SILVER: 500,
        ReputationTier.GOLD: 2000,
        ReputationTier.PLATINUM: 5000,
        ReputationTier.DIAMOND: 10000,
    }
    
    # 高信誉特权
    TIER_BENEFITS = {
        ReputationTier.NEWCOMER: {"margin_rate": 0.3, "priority": 1, "fee_discount": 0},
        ReputationTier.BRONZE: {"margin_rate": 0.25, "priority": 2, "fee_discount": 0.02},
        ReputationTier.SILVER: {"margin_rate": 0.20, "priority": 3, "fee_discount": 0.05},
        ReputationTier.GOLD: {"margin_rate": 0.15, "priority": 4, "fee_discount": 0.10},
        ReputationTier.PLATINUM: {"margin_rate": 0.10, "priority": 5, "fee_discount": 0.15},
        ReputationTier.DIAMOND: {"margin_rate": 0.05, "priority": 6, "fee_discount": 0.20},
    }
    
    def __init__(self, did_manager: DIDManager):
        self.did_manager = did_manager
        self._lock = threading.RLock()
        
        # 信誉历史
        self.reputation_history: Dict[str, List[Dict]] = defaultdict(list)
    
    def get_tier(self, score: float) -> ReputationTier:
        """获取信誉等级"""
        tier = ReputationTier.NEWCOMER
        for t, threshold in sorted(self.TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if score >= threshold:
                tier = t
                break
        return tier
    
    def add_reputation(
        self,
        did: str,
        amount: float,
        reason: str,
        source: str = "",
    ) -> Dict:
        """增加信誉"""
        with self._lock:
            binding = self.did_manager.bindings.get(did)
            if not binding:
                return {"error": "DID not found"}
            
            old_score = binding.reputation_score
            old_tier = binding.reputation_tier
            
            binding.reputation_score += amount
            binding.reputation_tier = self.get_tier(binding.reputation_score)
            
            # 记录历史
            self.reputation_history[did].append({
                "amount": amount,
                "reason": reason,
                "source": source,
                "old_score": old_score,
                "new_score": binding.reputation_score,
                "time": time.time(),
            })
            
            tier_changed = old_tier != binding.reputation_tier
            
            return {
                "did": did,
                "old_score": old_score,
                "new_score": binding.reputation_score,
                "amount_added": amount,
                "tier": binding.reputation_tier.value,
                "tier_changed": tier_changed,
            }
    
    def deduct_reputation(
        self,
        did: str,
        amount: float,
        reason: str,
    ) -> Dict:
        """扣除信誉"""
        return self.add_reputation(did, -amount, reason)
    
    def get_benefits(self, did: str) -> Dict:
        """获取信誉特权"""
        with self._lock:
            binding = self.did_manager.bindings.get(did)
            if not binding:
                return {"error": "DID not found"}
            
            return {
                "did": did,
                "reputation_score": binding.reputation_score,
                "tier": binding.reputation_tier.value,
                "benefits": self.TIER_BENEFITS.get(binding.reputation_tier, {}),
            }
    
    def record_compute_activity(
        self,
        did: str,
        compute_hours: float,
        tasks_completed: int,
        success_rate: float = 1.0,
    ) -> Dict:
        """记录计算活动"""
        with self._lock:
            binding = self.did_manager.bindings.get(did)
            if not binding:
                return {"error": "DID not found"}
            
            binding.total_compute_hours += compute_hours
            binding.total_tasks_completed += tasks_completed
            binding.last_active = time.time()
            
            # 根据活动计算信誉奖励
            base_reward = compute_hours * 0.5 + tasks_completed * 2
            adjusted_reward = base_reward * success_rate
            
            if adjusted_reward > 0:
                self.add_reputation(did, adjusted_reward, "compute_activity")
            
            binding.compute_history.append({
                "compute_hours": compute_hours,
                "tasks_completed": tasks_completed,
                "success_rate": success_rate,
                "time": time.time(),
            })
            
            return {
                "did": did,
                "total_compute_hours": binding.total_compute_hours,
                "total_tasks_completed": binding.total_tasks_completed,
                "reputation_earned": adjusted_reward,
            }


# ============== 女巫攻击检测 ==============

class SybilDetector:
    """女巫攻击检测器"""
    
    # 风险因素权重
    RISK_WEIGHTS = {
        "ip_sharing": 25,              # IP 共享
        "similar_behavior": 20,        # 行为相似
        "rapid_creation": 15,          # 快速创建
        "no_stake": 15,                # 无质押
        "suspicious_pattern": 15,      # 可疑模式
        "low_reputation": 10,          # 低信誉
    }
    
    def __init__(self, did_manager: DIDManager):
        self.did_manager = did_manager
        self._lock = threading.RLock()
        
        # IP 到 DID 映射
        self.ip_to_dids: Dict[str, Set[str]] = defaultdict(set)
        
        # 行为指纹
        self.behavior_fingerprints: Dict[str, Dict] = {}
    
    def register_ip(self, did: str, ip_address: str):
        """注册 IP 地址"""
        with self._lock:
            self.ip_to_dids[ip_address].add(did)
    
    def analyze_sybil_risk(self, did: str) -> SybilAnalysis:
        """分析女巫攻击风险"""
        with self._lock:
            analysis = SybilAnalysis(subject_did=did)
            risk_score = 0
            factors = []
            
            binding = self.did_manager.bindings.get(did)
            if not binding:
                analysis.risk_level = SybilRiskLevel.HIGH
                analysis.risk_score = 80
                analysis.factors.append({"factor": "unknown_did", "weight": 80})
                return analysis
            
            # 1. 检查 IP 共享
            related_dids = set()
            for ip, dids in self.ip_to_dids.items():
                if did in dids and len(dids) > 1:
                    related_dids.update(dids - {did})
                    analysis.ip_clusters.append(ip)
            
            if related_dids:
                ip_risk = min(len(related_dids) * 10, self.RISK_WEIGHTS["ip_sharing"])
                risk_score += ip_risk
                factors.append({
                    "factor": "ip_sharing",
                    "description": f"Shares IP with {len(related_dids)} other DIDs",
                    "weight": ip_risk,
                })
                analysis.related_dids = list(related_dids)
            
            # 2. 检查质押
            if binding.staked_amount == 0:
                risk_score += self.RISK_WEIGHTS["no_stake"]
                factors.append({
                    "factor": "no_stake",
                    "description": "No stake deposited",
                    "weight": self.RISK_WEIGHTS["no_stake"],
                })
            
            # 3. 检查信誉
            if binding.reputation_score < 100:
                risk_score += self.RISK_WEIGHTS["low_reputation"]
                factors.append({
                    "factor": "low_reputation",
                    "description": f"Low reputation score: {binding.reputation_score}",
                    "weight": self.RISK_WEIGHTS["low_reputation"],
                })
            
            # 4. 检查账户年龄
            account_age_days = (time.time() - binding.registered_at) / 86400
            if account_age_days < 7:
                risk_score += self.RISK_WEIGHTS["rapid_creation"]
                factors.append({
                    "factor": "rapid_creation",
                    "description": f"Account age: {account_age_days:.1f} days",
                    "weight": self.RISK_WEIGHTS["rapid_creation"],
                })
            
            # 5. 行为相似性检测
            if did in self.behavior_fingerprints:
                fingerprint = self.behavior_fingerprints[did]
                similar_count = self._find_similar_behavior(did, fingerprint)
                if similar_count > 0:
                    behavior_risk = min(similar_count * 10, self.RISK_WEIGHTS["similar_behavior"])
                    risk_score += behavior_risk
                    factors.append({
                        "factor": "similar_behavior",
                        "description": f"Similar behavior to {similar_count} other DIDs",
                        "weight": behavior_risk,
                    })
                    analysis.behavior_similarity = similar_count * 10
            
            # 确定风险等级
            analysis.risk_score = min(risk_score, 100)
            if risk_score >= 70:
                analysis.risk_level = SybilRiskLevel.CRITICAL
            elif risk_score >= 50:
                analysis.risk_level = SybilRiskLevel.HIGH
            elif risk_score >= 30:
                analysis.risk_level = SybilRiskLevel.MEDIUM
            else:
                analysis.risk_level = SybilRiskLevel.LOW
            
            analysis.factors = factors
            return analysis
    
    def _find_similar_behavior(
        self,
        did: str,
        fingerprint: Dict,
    ) -> int:
        """查找相似行为"""
        similar_count = 0
        for other_did, other_fp in self.behavior_fingerprints.items():
            if other_did == did:
                continue
            
            # 简单相似性计算
            similarity = self._calculate_similarity(fingerprint, other_fp)
            if similarity > 0.8:
                similar_count += 1
        
        return similar_count
    
    def _calculate_similarity(self, fp1: Dict, fp2: Dict) -> float:
        """计算相似度"""
        common_keys = set(fp1.keys()) & set(fp2.keys())
        if not common_keys:
            return 0
        
        matches = sum(1 for k in common_keys if fp1.get(k) == fp2.get(k))
        return matches / len(common_keys)
    
    def update_behavior_fingerprint(
        self,
        did: str,
        activity_pattern: Dict,
    ):
        """更新行为指纹"""
        with self._lock:
            if did not in self.behavior_fingerprints:
                self.behavior_fingerprints[did] = {}
            
            self.behavior_fingerprints[did].update(activity_pattern)
    
    def get_safe_dids(self, min_reputation: float = 100) -> List[str]:
        """获取安全的 DID 列表"""
        with self._lock:
            safe_dids = []
            
            for did, binding in self.did_manager.bindings.items():
                if binding.reputation_score < min_reputation:
                    continue
                
                analysis = self.analyze_sybil_risk(did)
                if analysis.risk_level in [SybilRiskLevel.LOW, SybilRiskLevel.MEDIUM]:
                    safe_dids.append(did)
            
            return safe_dids


# ============== 完整身份服务 ==============

class IdentityService:
    """身份服务"""
    
    def __init__(self):
        self.did_manager = DIDManager()
        self.reputation = ReputationSystem(self.did_manager)
        self.sybil_detector = SybilDetector(self.did_manager)
    
    def create_identity(
        self,
        public_key: str,
        wallet_address: str = None,
        miner_id: str = None,
        ip_address: str = None,
    ) -> Dict:
        """创建身份"""
        # 创建 DID
        did_doc = self.did_manager.create_did(public_key)
        
        # 绑定钱包
        if wallet_address:
            self.did_manager.bind_wallet(did_doc.did, wallet_address)
        
        # 绑定矿工
        if miner_id:
            self.did_manager.bind_miner(did_doc.did, miner_id)
        
        # 注册 IP
        if ip_address:
            self.sybil_detector.register_ip(did_doc.did, ip_address)
        
        return {
            "did": did_doc.did,
            "did_document": did_doc.to_dict(),
            "binding": self.did_manager.get_binding(did_doc.did),
        }
    
    def verify_identity(self, did: str) -> Dict:
        """验证身份"""
        doc = self.did_manager.resolve_did(did)
        if not doc:
            return {"valid": False, "reason": "DID not found"}
        
        if doc.deactivated:
            return {"valid": False, "reason": "DID deactivated"}
        
        binding = self.did_manager.get_binding(did)
        sybil_analysis = self.sybil_detector.analyze_sybil_risk(did)
        
        return {
            "valid": True,
            "did": did,
            "binding": binding,
            "sybil_risk": sybil_analysis.to_dict(),
            "reputation": self.reputation.get_benefits(did),
        }
    
    def get_identity_for_task(self, did: str) -> Dict:
        """获取用于任务的身份信息"""
        verification = self.verify_identity(did)
        
        if not verification.get("valid"):
            return verification
        
        # 获取特权
        benefits = self.reputation.get_benefits(did)
        
        return {
            "did": did,
            "verified": True,
            "reputation_tier": benefits.get("tier"),
            "margin_rate": benefits.get("benefits", {}).get("margin_rate", 0.3),
            "priority": benefits.get("benefits", {}).get("priority", 1),
            "fee_discount": benefits.get("benefits", {}).get("fee_discount", 0),
            "sybil_risk_level": verification.get("sybil_risk", {}).get("risk_level"),
        }


# ============== 全局实例 ==============

_identity_service: Optional[IdentityService] = None


def get_identity_service() -> IdentityService:
    """获取身份服务"""
    global _identity_service
    
    if _identity_service is None:
        _identity_service = IdentityService()
    
    return _identity_service
