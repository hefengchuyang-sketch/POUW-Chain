"""
data_lifecycle.py - 数据生命周期与自毁机制

Phase 9 功能：
1. 数据生命周期管理
2. 自动擦除中间数据
3. 延迟销毁 / 立即销毁
4. 销毁证明哈希
5. 临时会话密钥
6. 密钥过期自动失效
"""

import time
import uuid
import hashlib
import secrets
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from collections import defaultdict
import base64


# ============== 枚举类型 ==============

class DataType(Enum):
    """数据类型"""
    INPUT = "input"                    # 输入数据
    OUTPUT = "output"                  # 输出数据
    INTERMEDIATE = "intermediate"      # 中间数据
    MODEL = "model"                    # 模型数据
    CHECKPOINT = "checkpoint"          # 检查点
    LOG = "log"                        # 日志
    TEMP = "temp"                      # 临时数据


class RetentionPolicy(Enum):
    """保留策略"""
    IMMEDIATE_DELETE = "immediate"     # 立即删除
    DELAYED_DELETE = "delayed"         # 延迟删除
    KEEP_UNTIL_EXPIRY = "until_expiry" # 保留到过期
    PERMANENT = "permanent"            # 永久保留
    USER_CONTROLLED = "user_controlled" # 用户控制


class DestructionMethod(Enum):
    """销毁方式"""
    SECURE_OVERWRITE = "secure_overwrite"   # 安全覆写
    CRYPTO_ERASE = "crypto_erase"           # 加密擦除
    PHYSICAL_DESTROY = "physical_destroy"    # 物理销毁
    SIMPLE_DELETE = "simple_delete"          # 简单删除


class KeyType(Enum):
    """密钥类型"""
    SESSION = "session"                # 会话密钥
    EPHEMERAL = "ephemeral"           # 临时密钥
    STAGE = "stage"                    # 阶段密钥
    MASTER = "master"                  # 主密钥


class KeyStatus(Enum):
    """密钥状态"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ROTATED = "rotated"


# ============== 数据结构 ==============

@dataclass
class DataAsset:
    """数据资产"""
    asset_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_id: str = ""
    user_id: str = ""
    miner_id: str = ""
    
    # 数据信息
    data_type: DataType = DataType.INTERMEDIATE
    data_hash: str = ""                    # 数据哈希
    size_bytes: int = 0
    location: str = ""                     # 存储位置
    
    # 加密
    encrypted: bool = True
    encryption_key_id: str = ""
    
    # 生命周期
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    retention_policy: RetentionPolicy = RetentionPolicy.DELAYED_DELETE
    retention_days: int = 7                # 保留天数
    
    # 销毁
    destruction_method: DestructionMethod = DestructionMethod.CRYPTO_ERASE
    destroyed: bool = False
    destroyed_at: float = 0
    destruction_proof: str = ""            # 销毁证明哈希
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict:
        return {
            "asset_id": self.asset_id,
            "task_id": self.task_id,
            "data_type": self.data_type.value,
            "data_hash": self.data_hash,
            "size_bytes": self.size_bytes,
            "encrypted": self.encrypted,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "retention_policy": self.retention_policy.value,
            "destroyed": self.destroyed,
            "destruction_proof": self.destruction_proof,
        }


@dataclass
class DestructionCertificate:
    """销毁证书"""
    certificate_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_id: str = ""
    task_id: str = ""
    
    # 销毁详情
    destruction_method: DestructionMethod = DestructionMethod.CRYPTO_ERASE
    destroyed_at: float = field(default_factory=time.time)
    destroyed_by: str = ""                 # 执行者
    
    # 证明
    data_hash_before: str = ""             # 销毁前数据哈希
    proof_hash: str = ""                   # 销毁证明哈希
    witness_signatures: List[str] = field(default_factory=list)
    
    # 链上记录
    on_chain: bool = False
    tx_hash: str = ""
    block_number: int = 0
    
    def compute_proof(self) -> str:
        """计算销毁证明"""
        data = f"{self.asset_id}{self.data_hash_before}{self.destroyed_at}"
        data += f"{self.destruction_method.value}{self.destroyed_by}"
        self.proof_hash = hashlib.sha256(data.encode()).hexdigest()
        return self.proof_hash
    
    def to_dict(self) -> Dict:
        return {
            "certificate_id": self.certificate_id,
            "asset_id": self.asset_id,
            "task_id": self.task_id,
            "destruction_method": self.destruction_method.value,
            "destroyed_at": self.destroyed_at,
            "proof_hash": self.proof_hash,
            "on_chain": self.on_chain,
            "tx_hash": self.tx_hash,
        }


@dataclass
class EphemeralKey:
    """临时密钥"""
    key_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    key_type: KeyType = KeyType.EPHEMERAL
    
    # 关联
    task_id: str = ""
    stage_id: str = ""                     # 阶段 ID
    session_id: str = ""
    
    # 密钥数据
    key_material: bytes = b""              # 密钥材料（加密存储）
    key_hash: str = ""                     # 密钥哈希（用于验证）
    algorithm: str = "AES-256-GCM"
    
    # 生命周期
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    max_uses: int = 0                      # 最大使用次数 (0=无限)
    use_count: int = 0
    
    # 状态
    status: KeyStatus = KeyStatus.ACTIVE
    revoked_at: float = 0
    revoked_reason: str = ""
    
    # 派生
    parent_key_id: str = ""                # 父密钥
    derived_from: str = ""                 # 派生来源
    
    def is_valid(self) -> bool:
        """检查密钥是否有效"""
        if self.status != KeyStatus.ACTIVE:
            return False
        if self.expires_at > 0 and time.time() > self.expires_at:
            return False
        if self.max_uses > 0 and self.use_count >= self.max_uses:
            return False
        return True
    
    def use(self) -> bool:
        """使用密钥"""
        if not self.is_valid():
            return False
        self.use_count += 1
        return True
    
    def to_dict(self) -> Dict:
        return {
            "key_id": self.key_id,
            "key_type": self.key_type.value,
            "task_id": self.task_id,
            "stage_id": self.stage_id,
            "algorithm": self.algorithm,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status.value,
            "use_count": self.use_count,
            "max_uses": self.max_uses,
        }


@dataclass
class KeyRotationPolicy:
    """密钥轮换策略"""
    rotation_interval_seconds: int = 3600      # 轮换间隔
    max_key_age_seconds: int = 86400           # 最大密钥年龄
    auto_rotate: bool = True
    notify_on_rotation: bool = True


# ============== 数据生命周期管理器 ==============

class DataLifecycleManager:
    """数据生命周期管理器"""
    
    # 默认保留配置
    DEFAULT_RETENTION = {
        DataType.INPUT: 7,           # 7 天
        DataType.OUTPUT: 30,         # 30 天
        DataType.INTERMEDIATE: 1,    # 1 天
        DataType.MODEL: 90,          # 90 天
        DataType.CHECKPOINT: 14,     # 14 天
        DataType.LOG: 30,            # 30 天
        DataType.TEMP: 0,            # 立即
    }
    
    def __init__(self):
        self.assets: Dict[str, DataAsset] = {}
        self.certificates: Dict[str, DestructionCertificate] = {}
        self._lock = threading.RLock()
        
        # 任务数据索引
        self.task_assets: Dict[str, List[str]] = defaultdict(list)
        
        # 清理回调
        self.cleanup_callbacks: List[Callable] = []
    
    def register_asset(
        self,
        task_id: str,
        user_id: str,
        miner_id: str,
        data_type: DataType,
        data_hash: str,
        size_bytes: int = 0,
        retention_policy: RetentionPolicy = None,
        retention_days: int = None,
        destruction_method: DestructionMethod = DestructionMethod.CRYPTO_ERASE,
    ) -> DataAsset:
        """注册数据资产"""
        with self._lock:
            if retention_days is None:
                retention_days = self.DEFAULT_RETENTION.get(data_type, 7)
            
            if retention_policy is None:
                if retention_days == 0:
                    retention_policy = RetentionPolicy.IMMEDIATE_DELETE
                else:
                    retention_policy = RetentionPolicy.DELAYED_DELETE
            
            asset = DataAsset(
                task_id=task_id,
                user_id=user_id,
                miner_id=miner_id,
                data_type=data_type,
                data_hash=data_hash,
                size_bytes=size_bytes,
                retention_policy=retention_policy,
                retention_days=retention_days,
                destruction_method=destruction_method,
            )
            
            if retention_days > 0:
                asset.expires_at = asset.created_at + retention_days * 86400
            
            self.assets[asset.asset_id] = asset
            self.task_assets[task_id].append(asset.asset_id)
            
            return asset
    
    def request_destruction(
        self,
        asset_id: str,
        immediate: bool = True,
        destroyed_by: str = "system",
    ) -> DestructionCertificate:
        """请求销毁数据"""
        with self._lock:
            asset = self.assets.get(asset_id)
            if not asset:
                raise ValueError("Asset not found")
            
            if asset.destroyed:
                raise ValueError("Asset already destroyed")
            
            # 创建销毁证书
            cert = DestructionCertificate(
                asset_id=asset_id,
                task_id=asset.task_id,
                destruction_method=asset.destruction_method,
                destroyed_by=destroyed_by,
                data_hash_before=asset.data_hash,
            )
            
            # 执行销毁
            if immediate:
                self._perform_destruction(asset, cert)
            else:
                # 延迟销毁 - 设置过期时间
                asset.expires_at = time.time() + 3600  # 1小时后
            
            self.certificates[cert.certificate_id] = cert
            return cert
    
    def _perform_destruction(
        self,
        asset: DataAsset,
        cert: DestructionCertificate,
    ):
        """执行销毁"""
        # 模拟销毁过程
        if asset.destruction_method == DestructionMethod.CRYPTO_ERASE:
            # 删除加密密钥即可使数据不可读
            asset.encryption_key_id = ""
        
        # 更新资产状态
        asset.destroyed = True
        asset.destroyed_at = time.time()
        
        # 计算销毁证明
        cert.compute_proof()
        asset.destruction_proof = cert.proof_hash
        
        # 执行回调
        for callback in self.cleanup_callbacks:
            try:
                callback(asset.asset_id, cert.proof_hash)
            except Exception:
                pass
    
    def destroy_task_data(
        self,
        task_id: str,
        data_types: List[DataType] = None,
        immediate: bool = True,
    ) -> List[DestructionCertificate]:
        """销毁任务数据"""
        with self._lock:
            certificates = []
            
            asset_ids = self.task_assets.get(task_id, [])
            for asset_id in asset_ids:
                asset = self.assets.get(asset_id)
                if not asset or asset.destroyed:
                    continue
                
                # 过滤数据类型
                if data_types and asset.data_type not in data_types:
                    continue
                
                try:
                    cert = self.request_destruction(
                        asset_id,
                        immediate=immediate,
                        destroyed_by="task_cleanup"
                    )
                    certificates.append(cert)
                except Exception:
                    pass
            
            return certificates
    
    def cleanup_expired(self) -> List[DestructionCertificate]:
        """清理过期数据"""
        with self._lock:
            certificates = []
            
            for asset in list(self.assets.values()):
                if asset.destroyed:
                    continue
                if not asset.is_expired():
                    continue
                
                try:
                    cert = self.request_destruction(
                        asset.asset_id,
                        immediate=True,
                        destroyed_by="expiry_cleanup"
                    )
                    certificates.append(cert)
                except Exception:
                    pass
            
            return certificates
    
    def get_asset_status(self, asset_id: str) -> Optional[Dict]:
        """获取资产状态"""
        with self._lock:
            asset = self.assets.get(asset_id)
            if asset:
                return asset.to_dict()
            return None
    
    def get_task_assets(self, task_id: str) -> List[Dict]:
        """获取任务资产"""
        with self._lock:
            asset_ids = self.task_assets.get(task_id, [])
            return [
                self.assets[aid].to_dict()
                for aid in asset_ids
                if aid in self.assets
            ]
    
    def get_destruction_proof(self, asset_id: str) -> Optional[Dict]:
        """获取销毁证明"""
        with self._lock:
            for cert in self.certificates.values():
                if cert.asset_id == asset_id:
                    return cert.to_dict()
            return None
    
    def verify_destruction(self, proof_hash: str) -> bool:
        """验证销毁证明"""
        with self._lock:
            for cert in self.certificates.values():
                if cert.proof_hash == proof_hash:
                    return True
            return False


# ============== 临时密钥管理器 ==============

class EphemeralKeyManager:
    """临时密钥管理器"""
    
    def __init__(self):
        self.keys: Dict[str, EphemeralKey] = {}
        self._lock = threading.RLock()
        
        # 索引
        self.task_keys: Dict[str, List[str]] = defaultdict(list)
        self.stage_keys: Dict[str, List[str]] = defaultdict(list)
        self.session_keys: Dict[str, List[str]] = defaultdict(list)
        
        # 轮换策略
        self.rotation_policy = KeyRotationPolicy()
    
    def generate_session_key(
        self,
        task_id: str,
        session_id: str,
        ttl_seconds: int = 3600,
    ) -> EphemeralKey:
        """生成会话密钥"""
        with self._lock:
            key_material = secrets.token_bytes(32)  # 256-bit
            
            key = EphemeralKey(
                key_type=KeyType.SESSION,
                task_id=task_id,
                session_id=session_id,
                key_material=key_material,
                key_hash=hashlib.sha256(key_material).hexdigest(),
                expires_at=time.time() + ttl_seconds,
            )
            
            self.keys[key.key_id] = key
            self.task_keys[task_id].append(key.key_id)
            self.session_keys[session_id].append(key.key_id)
            
            return key
    
    def generate_stage_key(
        self,
        task_id: str,
        stage_id: str,
        parent_key_id: str = None,
        max_uses: int = 1,
        ttl_seconds: int = 600,
    ) -> EphemeralKey:
        """生成阶段密钥"""
        with self._lock:
            # 可从父密钥派生
            if parent_key_id and parent_key_id in self.keys:
                parent = self.keys[parent_key_id]
                derived_material = hashlib.sha256(
                    parent.key_material + stage_id.encode()
                ).digest()
            else:
                derived_material = secrets.token_bytes(32)
            
            key = EphemeralKey(
                key_type=KeyType.STAGE,
                task_id=task_id,
                stage_id=stage_id,
                key_material=derived_material,
                key_hash=hashlib.sha256(derived_material).hexdigest(),
                expires_at=time.time() + ttl_seconds,
                max_uses=max_uses,
                parent_key_id=parent_key_id or "",
            )
            
            self.keys[key.key_id] = key
            self.task_keys[task_id].append(key.key_id)
            self.stage_keys[stage_id].append(key.key_id)
            
            return key
    
    def generate_ephemeral_key(
        self,
        purpose: str,
        ttl_seconds: int = 300,
    ) -> EphemeralKey:
        """生成临时密钥"""
        with self._lock:
            key_material = secrets.token_bytes(32)
            
            key = EphemeralKey(
                key_type=KeyType.EPHEMERAL,
                key_material=key_material,
                key_hash=hashlib.sha256(key_material).hexdigest(),
                expires_at=time.time() + ttl_seconds,
                derived_from=purpose,
            )
            
            self.keys[key.key_id] = key
            return key
    
    def get_key(self, key_id: str) -> Optional[EphemeralKey]:
        """获取密钥"""
        with self._lock:
            key = self.keys.get(key_id)
            if key and key.is_valid():
                return key
            return None
    
    def use_key(self, key_id: str) -> Optional[bytes]:
        """使用密钥（返回密钥材料）"""
        with self._lock:
            key = self.keys.get(key_id)
            if not key:
                return None
            
            if not key.use():
                return None
            
            return key.key_material
    
    def revoke_key(self, key_id: str, reason: str = "") -> bool:
        """撤销密钥"""
        with self._lock:
            key = self.keys.get(key_id)
            if not key:
                return False
            
            key.status = KeyStatus.REVOKED
            key.revoked_at = time.time()
            key.revoked_reason = reason
            
            # 清除密钥材料
            key.key_material = b""
            
            return True
    
    def revoke_task_keys(self, task_id: str) -> int:
        """撤销任务所有密钥"""
        with self._lock:
            key_ids = self.task_keys.get(task_id, [])
            count = 0
            
            for key_id in key_ids:
                if self.revoke_key(key_id, "task_completed"):
                    count += 1
            
            return count
    
    def rotate_key(self, old_key_id: str) -> Optional[EphemeralKey]:
        """轮换密钥"""
        with self._lock:
            old_key = self.keys.get(old_key_id)
            if not old_key:
                return None
            
            # 创建新密钥
            new_key = EphemeralKey(
                key_type=old_key.key_type,
                task_id=old_key.task_id,
                stage_id=old_key.stage_id,
                session_id=old_key.session_id,
                key_material=secrets.token_bytes(32),
                expires_at=time.time() + (old_key.expires_at - old_key.created_at),
                max_uses=old_key.max_uses,
                parent_key_id=old_key_id,
            )
            new_key.key_hash = hashlib.sha256(new_key.key_material).hexdigest()
            
            self.keys[new_key.key_id] = new_key
            
            # 标记旧密钥
            old_key.status = KeyStatus.ROTATED
            
            # 更新索引
            if old_key.task_id:
                self.task_keys[old_key.task_id].append(new_key.key_id)
            
            return new_key
    
    def cleanup_expired_keys(self) -> int:
        """清理过期密钥"""
        with self._lock:
            count = 0
            current_time = time.time()
            
            for key in list(self.keys.values()):
                if key.status == KeyStatus.ACTIVE:
                    if key.expires_at > 0 and current_time > key.expires_at:
                        key.status = KeyStatus.EXPIRED
                        key.key_material = b""  # 清除密钥材料
                        count += 1
            
            return count
    
    def get_key_info(self, key_id: str) -> Optional[Dict]:
        """获取密钥信息（不包含密钥材料）"""
        with self._lock:
            key = self.keys.get(key_id)
            if key:
                return key.to_dict()
            return None
    
    def get_task_keys(self, task_id: str) -> List[Dict]:
        """获取任务密钥"""
        with self._lock:
            key_ids = self.task_keys.get(task_id, [])
            return [
                self.keys[kid].to_dict()
                for kid in key_ids
                if kid in self.keys
            ]


# ============== 会话密钥协议 ==============

class SessionKeyProtocol:
    """会话密钥协议"""
    
    def __init__(self, key_manager: EphemeralKeyManager):
        self.key_manager = key_manager
        self.sessions: Dict[str, Dict] = {}
        self._lock = threading.RLock()
    
    def initiate_session(
        self,
        task_id: str,
        user_id: str,
        miner_id: str,
        stages: List[str],
    ) -> Dict:
        """初始化会话"""
        with self._lock:
            session_id = uuid.uuid4().hex[:16]
            
            # 生成主会话密钥
            session_key = self.key_manager.generate_session_key(
                task_id=task_id,
                session_id=session_id,
                ttl_seconds=7200,  # 2小时
            )
            
            # 为每个阶段生成密钥
            stage_keys = {}
            for stage in stages:
                stage_key = self.key_manager.generate_stage_key(
                    task_id=task_id,
                    stage_id=stage,
                    parent_key_id=session_key.key_id,
                    max_uses=1,
                    ttl_seconds=1800,  # 30分钟
                )
                stage_keys[stage] = stage_key.key_id
            
            session = {
                "session_id": session_id,
                "task_id": task_id,
                "user_id": user_id,
                "miner_id": miner_id,
                "session_key_id": session_key.key_id,
                "stage_keys": stage_keys,
                "created_at": time.time(),
                "status": "active",
            }
            
            self.sessions[session_id] = session
            
            return {
                "session_id": session_id,
                "session_key_id": session_key.key_id,
                "session_key_hash": session_key.key_hash,
                "stage_keys": {
                    stage: self.key_manager.get_key_info(key_id)
                    for stage, key_id in stage_keys.items()
                },
                "expires_at": session_key.expires_at,
            }
    
    def get_stage_key(
        self,
        session_id: str,
        stage_id: str,
    ) -> Optional[Dict]:
        """获取阶段密钥"""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return None
            
            key_id = session.get("stage_keys", {}).get(stage_id)
            if not key_id:
                return None
            
            key = self.key_manager.get_key(key_id)
            if not key:
                return None
            
            return {
                "key_id": key.key_id,
                "key_hash": key.key_hash,
                "expires_at": key.expires_at,
                "remaining_uses": key.max_uses - key.use_count if key.max_uses > 0 else -1,
            }
    
    def complete_stage(
        self,
        session_id: str,
        stage_id: str,
    ) -> bool:
        """完成阶段（使密钥失效）"""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            key_id = session.get("stage_keys", {}).get(stage_id)
            if not key_id:
                return False
            
            return self.key_manager.revoke_key(key_id, "stage_completed")
    
    def terminate_session(self, session_id: str) -> bool:
        """终止会话"""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            # 撤销所有密钥
            self.key_manager.revoke_task_keys(session["task_id"])
            
            session["status"] = "terminated"
            session["terminated_at"] = time.time()
            
            return True


# ============== 全局实例 ==============

_lifecycle_manager: Optional[DataLifecycleManager] = None
_key_manager: Optional[EphemeralKeyManager] = None
_session_protocol: Optional[SessionKeyProtocol] = None


def get_data_lifecycle_system() -> Tuple[DataLifecycleManager, EphemeralKeyManager, SessionKeyProtocol]:
    """获取数据生命周期系统"""
    global _lifecycle_manager, _key_manager, _session_protocol
    
    if _lifecycle_manager is None:
        _lifecycle_manager = DataLifecycleManager()
        _key_manager = EphemeralKeyManager()
        _session_protocol = SessionKeyProtocol(_key_manager)
    
    return _lifecycle_manager, _key_manager, _session_protocol
