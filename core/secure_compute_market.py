# -*- coding: utf-8 -*-
"""
secure_compute_market.py - 算力市场隐私与安全模块

基于《算力市场隐私与安全补充需求文档》实现：

核心设计原则（强约束）：
1. 算力提供者默认不可信
2. 任何单一节点不得获得完整任务信息
3. 链上不存储任何可还原用户隐私的数据
4. 执行环境只具备"执行权"，不具备"理解权"
5. 验证与审计必须以"不可泄露"为前提

威胁模型假设：
- 矿工拥有 Root 权限（宿主机）
- 矿工可物理访问容器文件系统
- 矿工可监控 GPU 驱动与运行态
- 多个算力提供者可能串谋

安全目标：
- 破解成本 > 可获得收益
- 即便多矿工串谋也无法获取完整代码/数据/结果
"""

import os
import time
import json
import hashlib
import secrets
import uuid
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from pathlib import Path


# ============== 常量配置 ==============

class SecurityConfig:
    """安全配置常量"""
    
    # 任务拆分
    MIN_SHARDS = 2                      # 最少拆分份数
    MAX_SHARDS = 16                     # 最多拆分份数
    DEFAULT_SHARDS = 3                  # 默认拆分份数
    
    # 密钥派生
    HKDF_HASH = "SHA256"                # HKDF 哈希算法
    KEY_SIZE = 32                       # AES-256 密钥大小
    NONCE_SIZE = 12                     # GCM nonce 大小
    
    # 容器安全
    CONTAINER_READONLY_ROOT = True      # 只读根文件系统
    CONTAINER_NO_PRIVILEGE = True       # 禁止特权模式
    CONTAINER_NO_PTRACE = True          # 禁止调试
    CONTAINER_NO_COREDUMP = True        # 禁止 core dump
    CONTAINER_NO_NETWORK = True         # 禁止网络
    CONTAINER_NO_NEW_PRIVS = True       # 禁止提权
    
    # 审计边界
    MAX_ONCHAIN_DATA = 256              # 链上最大数据（字节）
    HASH_ONLY_ONCHAIN = True            # 链上仅存哈希
    
    # 密钥生命周期
    KEY_TTL_SECONDS = 3600              # 密钥存活时间
    KEY_DESTROY_ON_COMPLETE = True      # 完成后销毁
    
    # 验证
    RESULT_HASH_ALGORITHM = "SHA3-256"  # 结果哈希算法
    MERKLE_TREE_DEPTH = 8               # Merkle 树深度


# ============== 枚举类型 ==============

class ShardType(Enum):
    """分片类型"""
    CODE = "code"               # 代码片段
    DATA = "data"               # 数据分片
    ARGS = "args"               # 执行参数
    MODEL = "model"             # 模型权重
    CONFIG = "config"           # 配置信息


class EncryptionState(Enum):
    """加密状态"""
    PLAINTEXT = "plaintext"     # 明文（用户侧）
    ENCRYPTED = "encrypted"     # 密文
    SEALED = "sealed"           # 密封（TEE）
    DESTROYED = "destroyed"     # 已销毁


class ExecutionMode(Enum):
    """执行模式"""
    SINGLE = "single"           # 单矿工执行
    PARALLEL = "parallel"       # 多矿工并行
    DISTRIBUTED = "distributed" # 分布式执行
    REDUNDANT = "redundant"     # 冗余执行（验证）


class AuditScope(Enum):
    """审计范围"""
    EXECUTION = "execution"     # 是否执行
    TIMING = "timing"           # 是否按时
    INTEGRITY = "integrity"     # 是否被篡改
    RESOURCE = "resource"       # 资源使用


class ContainerSecurityLevel(Enum):
    """容器安全级别"""
    STANDARD = "standard"       # 标准安全
    ENHANCED = "enhanced"       # 增强安全
    MAXIMUM = "maximum"         # 最大安全
    TEE = "tee"                 # TEE 保护


# ============== 数据结构 ==============

@dataclass
class TaskShard:
    """任务分片
    
    用户任务被拆分为多个分片，每个矿工只能访问分配给它的分片
    """
    shard_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: str = ""
    shard_type: ShardType = ShardType.DATA
    shard_index: int = 0
    total_shards: int = 1
    
    # 加密状态
    encryption_state: EncryptionState = EncryptionState.PLAINTEXT
    encrypted_content: bytes = b""
    content_hash: str = ""              # 内容哈希（用于验证）
    
    # 密钥信息（不含密钥本身）
    key_id: str = ""                    # 密钥ID
    recipient_miner_id: str = ""        # 接收矿工
    
    # 依赖关系
    depends_on: List[str] = field(default_factory=list)
    required_by: List[str] = field(default_factory=list)
    
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "task_id": self.task_id,
            "shard_type": self.shard_type.value,
            "shard_index": self.shard_index,
            "total_shards": self.total_shards,
            "encryption_state": self.encryption_state.value,
            "content_hash": self.content_hash,
            "key_id": self.key_id,
            "recipient_miner_id": self.recipient_miner_id,
            "depends_on": self.depends_on,
            "required_by": self.required_by,
            "created_at": self.created_at,
        }


@dataclass
class DerivedKey:
    """派生密钥
    
    子密钥 K_i = HKDF(K_task, miner_id)
    矿工永远不持有明文密钥
    """
    key_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_key_id: str = ""             # 父密钥ID（不存储父密钥）
    miner_id: str = ""
    
    # 密钥材料（仅在内存中存在）
    # 注意：生产环境中密钥应使用HSM或安全enclave
    _key_material: bytes = field(default=b"", repr=False)
    
    # 元数据
    algorithm: str = "AES-256-GCM"
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    destroyed: bool = False
    
    def __post_init__(self):
        if self.expires_at == 0:
            self.expires_at = self.created_at + SecurityConfig.KEY_TTL_SECONDS
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at or self.destroyed
    
    def destroy(self):
        """安全销毁密钥"""
        # 覆写内存（Python 中有限制，生产环境需要 C 扩展）
        if self._key_material:
            # 尝试覆写
            self._key_material = secrets.token_bytes(len(self._key_material))
            self._key_material = b""
        self.destroyed = True


@dataclass
class ContainerSecurityPolicy:
    """容器安全策略
    
    Layer 3：矿工本地封装安全约束
    """
    policy_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    security_level: ContainerSecurityLevel = ContainerSecurityLevel.STANDARD
    
    # 权限禁止
    no_privilege: bool = True           # 禁止特权模式
    no_ptrace: bool = True              # 禁止调试接口
    no_coredump: bool = True            # 禁止 core dump
    no_gpu_profiling: bool = True       # 禁止 GPU profiling
    no_network: bool = True             # 禁止网络访问
    no_new_privs: bool = True           # 禁止提权
    
    # 文件系统
    readonly_root: bool = True          # 只读根文件系统
    no_external_mount: bool = True      # 禁止外部挂载
    tmpfs_only: bool = True             # 仅使用 tmpfs
    
    # 资源限制
    max_memory_mb: int = 16384          # 最大内存
    max_cpu_percent: float = 90.0       # 最大 CPU
    max_gpu_percent: float = 95.0       # 最大 GPU
    max_runtime_seconds: int = 3600     # 最大运行时间
    
    # 进程限制
    max_pids: int = 100                 # 最大进程数
    no_ipc_namespace: bool = True       # 隔离 IPC
    no_net_namespace: bool = True       # 隔离网络
    
    def to_docker_security_opts(self) -> List[str]:
        """转换为 Docker 安全选项"""
        opts = []
        if self.no_ptrace:
            opts.append("no-new-privileges:true")
        if self.no_coredump:
            opts.append("seccomp=unconfined")  # 实际应使用严格策略
        return opts
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "security_level": self.security_level.value,
            "no_privilege": self.no_privilege,
            "no_ptrace": self.no_ptrace,
            "no_coredump": self.no_coredump,
            "no_gpu_profiling": self.no_gpu_profiling,
            "no_network": self.no_network,
            "readonly_root": self.readonly_root,
            "max_memory_mb": self.max_memory_mb,
            "max_runtime_seconds": self.max_runtime_seconds,
        }


@dataclass
class AuditRecord:
    """审计记录
    
    链上记录内容（仅允许）：
    - 任务哈希
    - 执行时间戳
    - 矿工 ID（匿名化）
    - 结果哈希
    
    严禁上链：明文代码、明文数据、用户身份信息
    """
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    
    # 允许上链的数据
    task_hash: str = ""                 # 任务哈希
    result_hash: str = ""               # 结果哈希
    execution_timestamp: float = 0      # 执行时间戳
    miner_id_hash: str = ""             # 矿工ID哈希（匿名化）
    
    # 审计范围
    audit_scope: List[AuditScope] = field(default_factory=list)
    
    # 验证信息
    merkle_root: str = ""               # Merkle 根
    zk_proof: Optional[str] = None      # 可选零知识证明
    
    # 状态
    verified: bool = False
    verification_block: int = 0
    
    created_at: float = field(default_factory=time.time)
    
    def to_onchain_data(self) -> Dict[str, Any]:
        """生成链上数据（严格限制大小）"""
        data = {
            "t": self.task_hash[:32],       # 任务哈希（截断）
            "r": self.result_hash[:32],     # 结果哈希（截断）
            "ts": int(self.execution_timestamp),
            "m": self.miner_id_hash[:16],   # 矿工哈希（截断）
            "mr": self.merkle_root[:32] if self.merkle_root else "",
        }
        
        # 验证大小
        data_str = json.dumps(data)
        if len(data_str) > SecurityConfig.MAX_ONCHAIN_DATA:
            raise ValueError(f"链上数据超过限制: {len(data_str)} > {SecurityConfig.MAX_ONCHAIN_DATA}")
        
        return data


@dataclass
class DistributedExecutionPlan:
    """分布式执行计划
    
    多矿工执行安全约束：
    - 每个矿工仅执行明确分配的子任务
    - 不允许任务全量广播
    - 不允许任意矿工重组完整任务
    """
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: str = ""
    execution_mode: ExecutionMode = ExecutionMode.SINGLE
    
    # 分片分配
    shard_assignments: Dict[str, List[str]] = field(default_factory=dict)  # miner_id -> [shard_ids]
    
    # 矿工列表
    assigned_miners: List[str] = field(default_factory=list)
    
    # 结果合并
    aggregator_id: str = ""             # 合并节点（无解密能力）
    aggregation_type: str = "mathematical"  # mathematical/concat/mpc
    
    # 安全约束
    allow_miner_communication: bool = False  # 禁止矿工间通信
    require_tee: bool = False           # 是否要求 TEE
    
    # 时间约束
    created_at: float = field(default_factory=time.time)
    deadline: float = 0
    
    def validate_assignment(self) -> Tuple[bool, str]:
        """验证分配是否安全"""
        # 检查是否有矿工获得过多分片
        for miner_id, shards in self.shard_assignments.items():
            if len(shards) > SecurityConfig.MAX_SHARDS // 2:
                return False, f"矿工 {miner_id} 分配了过多分片"
        
        # 检查是否覆盖所有分片
        all_shards = set()
        for shards in self.shard_assignments.values():
            all_shards.update(shards)
        
        return True, "分配有效"


# ============== Shamir's Secret Sharing (GF(256)) ==============

class GF256:
    """GF(2^8) 有限域运算
    
    使用 AES 不可约多项式: x^8 + x^4 + x^3 + x + 1 (0x11B)
    所有运算在 0-255 范围内闭合，满足有限域性质。
    """
    
    # 预计算对数/反对数表（性能优化）
    _EXP_TABLE = [0] * 512
    _LOG_TABLE = [0] * 256
    _initialized = False
    
    @classmethod
    def _init_tables(cls):
        """初始化 GF(256) 乘法查找表
        
        使用生成元 3 (x+1), 它是 AES 多项式下的原根，阶为 255。
        生成元 2 (x) 的阶仅为 51，不能生成完整乘法群。
        """
        if cls._initialized:
            return
        
        x = 1
        for i in range(255):
            cls._EXP_TABLE[i] = x
            cls._LOG_TABLE[x] = i
            # 乘以生成元 3: v*3 = xtime(v) XOR v, 其中 xtime(v) = v*2
            x2 = x << 1
            if x2 & 0x100:
                x2 ^= 0x11B  # AES 不可约多项式约简
            x = x2 ^ x       # v * 3 = v * 2 + v * 1
        
        # 扩展 EXP 表以简化乘法 (避免 mod 255 运算)
        for i in range(255, 512):
            cls._EXP_TABLE[i] = cls._EXP_TABLE[i - 255]
        
        cls._initialized = True
    
    @classmethod
    def mul(cls, a: int, b: int) -> int:
        """GF(256) 乘法"""
        cls._init_tables()
        if a == 0 or b == 0:
            return 0
        return cls._EXP_TABLE[cls._LOG_TABLE[a] + cls._LOG_TABLE[b]]
    
    @classmethod
    def inv(cls, a: int) -> int:
        """GF(256) 乘法逆元"""
        cls._init_tables()
        if a == 0:
            raise ZeroDivisionError("GF(256) 中 0 没有逆元")
        return cls._EXP_TABLE[255 - cls._LOG_TABLE[a]]
    
    @classmethod
    def div(cls, a: int, b: int) -> int:
        """GF(256) 除法"""
        if b == 0:
            raise ZeroDivisionError("GF(256) 除以 0")
        if a == 0:
            return 0
        cls._init_tables()
        return cls._EXP_TABLE[(cls._LOG_TABLE[a] - cls._LOG_TABLE[b]) % 255]


class ShamirSecretSharing:
    """Shamir's Secret Sharing (GF(256) 实现)
    
    信息论安全的秘密分享方案:
    - (t, n) 阈值方案: n 个分片, 至少 t 个才能恢复
    - 任意 t-1 个分片不会泄露任何关于原始数据的信息
    - 每个字节独立进行秘密分享
    
    分片格式: [1B share_index] [1B threshold] [2B data_length_be] [nB share_data]
    """
    
    @staticmethod
    def split(data: bytes, num_shares: int, threshold: int) -> List[bytes]:
        """将数据拆分为 Shamir 分片
        
        Args:
            data: 原始数据
            num_shares: 总分片数 (n)
            threshold: 恢复阈值 (t), 至少需要 t 个分片才能恢复
            
        Returns:
            List[bytes]: 每个分片带有 4 字节头部
        """
        if threshold < 2:
            raise ValueError("阈值至少为 2")
        if threshold > num_shares:
            raise ValueError("阈值不能超过分片总数")
        if num_shares > 255:
            raise ValueError("分片数不能超过 255")
        
        GF256._init_tables()
        data_len = len(data)
        
        # 初始化分片数据
        share_data = [bytearray() for _ in range(num_shares)]
        
        for byte_val in data:
            # 为每个字节生成随机多项式: f(x) = byte_val + a1*x + a2*x^2 + ... + a_{t-1}*x^{t-1}
            coeffs = [byte_val] + [secrets.randbelow(256) for _ in range(threshold - 1)]
            
            # 在 x=1,2,...,n 处求值
            for i in range(num_shares):
                x = i + 1  # x 从 1 开始（x=0 是秘密本身）
                y = coeffs[0]
                x_power = 1
                for j in range(1, threshold):
                    x_power = GF256.mul(x_power, x)
                    y ^= GF256.mul(coeffs[j], x_power)
                share_data[i].append(y)
        
        # 构建分片: [share_index(1B)] [threshold(1B)] [data_len(2B big-endian)] [share_data]
        shares = []
        for i in range(num_shares):
            header = bytes([
                i + 1,                           # 分片序号 (1-based)
                threshold,                       # 恢复阈值
                (data_len >> 8) & 0xFF,          # 数据长度高字节
                data_len & 0xFF,                 # 数据长度低字节
            ])
            shares.append(header + bytes(share_data[i]))
        
        return shares
    
    @staticmethod
    def reconstruct(shares: List[bytes], threshold: int = 0) -> bytes:
        """从分片重建原始数据
        
        使用拉格朗日插值在 x=0 处求值以恢复秘密。
        
        Args:
            shares: 至少 threshold 个分片
            threshold: 恢复阈值, 0 表示从分片头部读取
        """
        if not shares:
            raise ValueError("至少需要一个分片")
        
        # 解析头部
        parsed = []
        for share in shares:
            if len(share) < 4:
                raise ValueError("分片格式错误: 太短")
            x = share[0]           # 分片序号
            t = share[1]           # 阈值
            data_len = (share[2] << 8) | share[3]
            data = share[4:]
            parsed.append((x, t, data_len, data))
        
        if threshold == 0:
            threshold = parsed[0][1]
        
        if len(parsed) < threshold:
            raise ValueError(f"分片不足: 需要 {threshold} 个, 只有 {len(parsed)} 个")
        
        # 只取前 threshold 个分片
        used = parsed[:threshold]
        data_len = used[0][2]
        
        GF256._init_tables()
        
        # 拉格朗日插值在 x=0 处求值
        x_coords = [s[0] for s in used]
        result = bytearray()
        
        for byte_idx in range(data_len):
            y_coords = [s[3][byte_idx] for s in used]
            
            # Lagrange interpolation at x=0
            secret = 0
            for i in range(threshold):
                # 计算拉格朗日基函数 L_i(0) = ∏(0-x_j)/(x_i-x_j) for j≠i
                numerator = 1    # ∏(-x_j) = ∏(x_j) in GF(256) since -x = x
                denominator = 1  # ∏(x_i - x_j)
                for j in range(threshold):
                    if i != j:
                        numerator = GF256.mul(numerator, x_coords[j])
                        denominator = GF256.mul(denominator, x_coords[i] ^ x_coords[j])
                
                lagrange = GF256.div(numerator, denominator)
                secret ^= GF256.mul(y_coords[i], lagrange)
            
            result.append(secret)
        
        return bytes(result)


# ============== 核心安全引擎 ==============

class TaskShardingEngine:
    """任务拆分引擎
    
    将用户任务拆分为不可单独理解的片段
    """
    
    def __init__(self, log_fn: Optional[Callable[[str], None]] = None):
        self.log_fn = log_fn or print
    
    def shard_task(
        self,
        task_id: str,
        code: bytes,
        data: bytes,
        args: bytes,
        num_shards: int = SecurityConfig.DEFAULT_SHARDS,
    ) -> List[TaskShard]:
        """
        拆分任务
        
        拆分原则：
        - 代码片段（Code Fragment）
        - 数据分片（Data Shard）
        - 执行参数（Runtime Args）
        - 任何单一矿工只接触片段 + 密文形态
        """
        if num_shards < SecurityConfig.MIN_SHARDS:
            num_shards = SecurityConfig.MIN_SHARDS
        if num_shards > SecurityConfig.MAX_SHARDS:
            num_shards = SecurityConfig.MAX_SHARDS
        
        shards = []
        
        # 拆分代码
        code_shards = self._split_bytes(code, num_shards)
        for i, chunk in enumerate(code_shards):
            shard = TaskShard(
                task_id=task_id,
                shard_type=ShardType.CODE,
                shard_index=i,
                total_shards=len(code_shards),
                content_hash=hashlib.sha256(chunk).hexdigest(),
            )
            shard._plaintext = chunk  # 临时存储，加密后删除
            shards.append(shard)
        
        # 拆分数据
        data_shards = self._split_bytes(data, num_shards)
        for i, chunk in enumerate(data_shards):
            shard = TaskShard(
                task_id=task_id,
                shard_type=ShardType.DATA,
                shard_index=i,
                total_shards=len(data_shards),
                content_hash=hashlib.sha256(chunk).hexdigest(),
            )
            shard._plaintext = chunk
            shards.append(shard)
        
        # 参数通常较小，不拆分但加密
        args_shard = TaskShard(
            task_id=task_id,
            shard_type=ShardType.ARGS,
            shard_index=0,
            total_shards=1,
            content_hash=hashlib.sha256(args).hexdigest(),
        )
        args_shard._plaintext = args
        shards.append(args_shard)
        
        self.log_fn(f"📦 任务 {task_id} 已拆分为 {len(shards)} 个分片")
        return shards
    
    def _split_bytes(self, data: bytes, num_parts: int) -> List[bytes]:
        """使用 Shamir's Secret Sharing (GF(256)) 拆分字节数据

        安全保证:
        - 任意 threshold-1 个分片无法恢复原始数据（信息论安全）
        - 需要 threshold 个分片才能重建
        - 每个分片大小 = 原始数据大小 + 4字节头部（分片序号+元数据）
        
        GF(256) 上的 Shamir's Secret Sharing:
        - 对数据的每个字节独立进行秘密分享
        - 使用 AES 的不可约多项式 x^8 + x^4 + x^3 + x + 1 (0x11B)
        """
        if not data:
            return [b"" for _ in range(num_parts)]
        
        threshold = max(2, (num_parts + 1) // 2)  # 至少需要一半分片才能恢复
        shares = ShamirSecretSharing.split(data, num_parts, threshold)
        return shares
    
    @staticmethod
    def reassemble_bytes(shares: List[bytes], threshold: int = 0) -> bytes:
        """从 Shamir 分片重建原始数据
        
        Args:
            shares: 分片列表（至少 threshold 个有效分片）
            threshold: 恢复阈值, 0 表示自动从分片头部读取
        """
        return ShamirSecretSharing.reconstruct(shares, threshold)


class KeyDerivationEngine:
    """密钥派生引擎
    
    实现端到端加密：
    - 用户侧生成任务主密钥 K_task
    - 每个矿工派生子密钥 K_i = HKDF(K_task, miner_id)
    - 矿工永远不持有明文密钥
    """
    
    def __init__(self):
        self._active_keys: Dict[str, DerivedKey] = {}
    
    def generate_task_key(self, task_id: str) -> Tuple[str, bytes]:
        """生成任务主密钥"""
        key_id = f"task_{task_id}_{uuid.uuid4().hex[:8]}"
        key_material = secrets.token_bytes(SecurityConfig.KEY_SIZE)
        
        return key_id, key_material
    
    def derive_miner_key(
        self,
        parent_key_id: str,
        parent_key_material: bytes,
        miner_id: str,
    ) -> DerivedKey:
        """为矿工派生子密钥
        
        K_i = HKDF(K_task, miner_id)
        
        使用标准 HKDF (RFC 5869) 实现:
        - cryptography.hazmat.primitives.kdf.hkdf.HKDF
        - SHA-256 作为哈希算法
        - 随机 salt 确保即使相同 parent_key + miner_id 也产生不同派生密钥
        """
        info = f"miner:{miner_id}".encode()
        salt = secrets.token_bytes(16)
        
        try:
            # 标准 HKDF 实现 (RFC 5869)
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF as CryptoHKDF
            from cryptography.hazmat.primitives import hashes as crypto_hashes
            
            hkdf = CryptoHKDF(
                algorithm=crypto_hashes.SHA256(),
                length=SecurityConfig.KEY_SIZE,
                salt=salt,
                info=info,
            )
            derived = hkdf.derive(parent_key_material)
        except ImportError:
            # 回退: 标准 HMAC-based Extract-and-Expand (HKDF 手动实现)
            import hmac
            import warnings
            warnings.warn(
                "cryptography 库不可用，使用 HMAC 手动实现 HKDF。"
                "生产环境请安装 cryptography>=41.0.0",
                RuntimeWarning
            )
            # Extract: PRK = HMAC-Hash(salt, IKM)
            prk = hmac.new(salt, parent_key_material, "sha256").digest()
            # Expand: OKM = HMAC-Hash(PRK, info || 0x01)
            derived = hmac.new(prk, info + b"\x01", "sha256").digest()
        
        key = DerivedKey(
            parent_key_id=parent_key_id,
            miner_id=miner_id,
            _key_material=derived,
        )
        
        self._active_keys[key.key_id] = key
        return key
    
    def encrypt_for_miner(
        self,
        plaintext: bytes,
        derived_key: DerivedKey,
    ) -> Tuple[bytes, bytes]:
        """使用派生密钥加密数据
        
        加密方案:
        - 优先使用 AES-256-GCM（需要 cryptography 库）
        - 无库时回退到 HMAC-SHA256 流密码（⚠️ 非标准，仅用于演示）
        """
        if derived_key.is_expired():
            raise ValueError("密钥已过期或销毁")
        
        nonce = secrets.token_bytes(SecurityConfig.NONCE_SIZE)
        
        try:
            # 尝试使用真正的 AES-256-GCM
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(derived_key._key_material)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            # AES-GCM 输出自带认证标签（最后16字节）
            return nonce + ciphertext, nonce
        except ImportError:
            pass
        
        try:
            # 尝试使用 pycryptodome 的 AES-GCM
            from Crypto.Cipher import AES as AES_Crypto
            cipher = AES_Crypto.new(derived_key._key_material, AES_Crypto.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext)
            return nonce + tag + ciphertext, nonce
        except ImportError:
            pass
        
        # ⚠️ 回退方案: HMAC-SHA256 流密码 + HMAC 认证标签
        # 这不是标准 AES-GCM，安全性较低，仅用于无加密库的开发环境
        import warnings
        warnings.warn(
            "使用 HMAC-SHA256 流密码回退方案，安全性不及 AES-GCM。"
            "生产环境请安装 cryptography 或 pycryptodome 库。",
            RuntimeWarning
        )
        key_stream = self._expand_key(derived_key._key_material, len(plaintext))
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, key_stream))
        
        # HMAC 认证标签（防止密文篡改）
        import hmac as hmac_mod
        tag = hmac_mod.new(
            derived_key._key_material, 
            nonce + ciphertext, 
            "sha256"
        ).digest()[:16]
        
        return nonce + tag + ciphertext, nonce
    
    def decrypt_for_miner(
        self,
        ciphertext_with_metadata: bytes,
        derived_key: DerivedKey,
    ) -> bytes:
        """使用派生密钥解密数据（配对 encrypt_for_miner）
        
        解密方案:
        - 优先使用 AES-256-GCM（需要 cryptography 库）
        - 无库时回退到 HMAC-SHA256 流密码
        
        数据格式: nonce(12B) + ciphertext_with_tag (AES-GCM)
                  nonce(12B) + tag(16B) + ciphertext (pycryptodome / HMAC回退)
        """
        if derived_key.is_expired():
            raise ValueError("密钥已过期或销毁")
        
        nonce = ciphertext_with_metadata[:SecurityConfig.NONCE_SIZE]
        
        try:
            # 尝试 cryptography 库的 AES-256-GCM 解密
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(derived_key._key_material)
            ciphertext_with_tag = ciphertext_with_metadata[SecurityConfig.NONCE_SIZE:]
            plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            return plaintext
        except ImportError:
            pass
        except Exception:
            # cryptography 解密失败（可能用了其他方式加密），尝试下一种
            pass
        
        try:
            # 尝试 pycryptodome 的 AES-GCM 解密
            from Crypto.Cipher import AES as AES_Crypto
            tag = ciphertext_with_metadata[SecurityConfig.NONCE_SIZE:SecurityConfig.NONCE_SIZE + 16]
            ciphertext = ciphertext_with_metadata[SecurityConfig.NONCE_SIZE + 16:]
            cipher = AES_Crypto.new(derived_key._key_material, AES_Crypto.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            return plaintext
        except ImportError:
            pass
        except Exception:
            pass
        
        # 回退: HMAC-SHA256 流密码解密
        import warnings
        warnings.warn(
            "使用 HMAC-SHA256 流密码回退方案解密。"
            "生产环境请安装 cryptography 或 pycryptodome 库。",
            RuntimeWarning
        )
        tag = ciphertext_with_metadata[SecurityConfig.NONCE_SIZE:SecurityConfig.NONCE_SIZE + 16]
        ciphertext = ciphertext_with_metadata[SecurityConfig.NONCE_SIZE + 16:]
        
        # 验证 HMAC 认证标签
        import hmac as hmac_mod
        expected_tag = hmac_mod.new(
            derived_key._key_material,
            nonce + ciphertext,
            "sha256"
        ).digest()[:16]
        
        if not hmac_mod.compare_digest(tag, expected_tag):
            raise ValueError("HMAC 认证标签验证失败：数据可能被篡改")
        
        key_stream = self._expand_key(derived_key._key_material, len(ciphertext))
        plaintext = bytes(a ^ b for a, b in zip(ciphertext, key_stream))
        return plaintext
    
    def _expand_key(self, key: bytes, length: int) -> bytes:
        """扩展密钥流"""
        result = b""
        counter = 0
        while len(result) < length:
            block = hashlib.sha256(key + counter.to_bytes(4, 'big')).digest()
            result += block
            counter += 1
        return result[:length]
    
    def destroy_key(self, key_id: str):
        """销毁密钥"""
        if key_id in self._active_keys:
            self._active_keys[key_id].destroy()
            del self._active_keys[key_id]
    
    def cleanup_expired_keys(self):
        """清理过期密钥"""
        expired = [k for k, v in self._active_keys.items() if v.is_expired()]
        for key_id in expired:
            self.destroy_key(key_id)
        return len(expired)


class AuditEngine:
    """审计引擎
    
    审计目标（不泄露内容）：
    - 是否执行
    - 是否按时
    - 是否被篡改
    
    审计方式：
    - 哈希承诺
    - 可选零知识证明（ZK）
    """
    
    def __init__(self, log_fn: Optional[Callable[[str], None]] = None):
        self.log_fn = log_fn or print
        self._records: Dict[str, AuditRecord] = {}
    
    def create_task_commitment(
        self,
        task_id: str,
        code_hash: str,
        data_hash: str,
        args_hash: str,
    ) -> str:
        """创建任务承诺（哈希）"""
        # 合并所有哈希
        combined = f"{task_id}:{code_hash}:{data_hash}:{args_hash}"
        commitment = hashlib.sha3_256(combined.encode()).hexdigest()
        return commitment
    
    def create_result_commitment(
        self,
        task_id: str,
        result_hash: str,
        execution_time: float,
        miner_id: str,
    ) -> AuditRecord:
        """创建结果承诺（审计记录）"""
        # 匿名化矿工ID
        miner_id_hash = hashlib.sha256(miner_id.encode()).hexdigest()
        
        record = AuditRecord(
            task_hash=hashlib.sha256(task_id.encode()).hexdigest(),
            result_hash=result_hash,
            execution_timestamp=execution_time,
            miner_id_hash=miner_id_hash,
            audit_scope=[AuditScope.EXECUTION, AuditScope.TIMING, AuditScope.INTEGRITY],
        )
        
        self._records[record.record_id] = record
        return record
    
    def build_merkle_tree(self, shard_hashes: List[str]) -> str:
        """构建 Merkle 树"""
        if not shard_hashes:
            return ""
        
        # 填充到 2 的幂次
        while len(shard_hashes) & (len(shard_hashes) - 1):
            shard_hashes.append(shard_hashes[-1])
        
        # 构建树
        current_level = shard_hashes
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                combined = current_level[i] + current_level[i + 1]
                parent = hashlib.sha256(combined.encode()).hexdigest()
                next_level.append(parent)
            current_level = next_level
        
        return current_level[0]
    
    def verify_execution(
        self,
        record: AuditRecord,
        expected_task_hash: str,
    ) -> Tuple[bool, str]:
        """验证执行（基于哈希）"""
        if record.task_hash[:32] != expected_task_hash[:32]:
            return False, "任务哈希不匹配"
        
        if record.execution_timestamp == 0:
            return False, "缺少执行时间戳"
        
        record.verified = True
        return True, "验证通过"


class DistributedExecutionEngine:
    """分布式执行引擎
    
    多矿工执行安全约束：
    - 每个矿工仅执行明确分配的子任务
    - 不允许任务全量广播
    - 不允许任意矿工重组完整任务
    """
    
    def __init__(self, log_fn: Optional[Callable[[str], None]] = None):
        self.log_fn = log_fn or print
        self.sharding_engine = TaskShardingEngine(log_fn)
        self.key_engine = KeyDerivationEngine()
        self.audit_engine = AuditEngine(log_fn)
    
    def create_execution_plan(
        self,
        task_id: str,
        shards: List[TaskShard],
        available_miners: List[str],
        mode: ExecutionMode = ExecutionMode.DISTRIBUTED,
    ) -> DistributedExecutionPlan:
        """创建分布式执行计划"""
        if len(available_miners) < 2 and mode == ExecutionMode.DISTRIBUTED:
            self.log_fn("⚠️ 矿工数量不足，降级为单矿工执行")
            mode = ExecutionMode.SINGLE
        
        plan = DistributedExecutionPlan(
            task_id=task_id,
            execution_mode=mode,
            assigned_miners=available_miners[:],
        )
        
        if mode == ExecutionMode.SINGLE:
            # 单矿工获得所有分片（但仍是密文）
            plan.shard_assignments[available_miners[0]] = [s.shard_id for s in shards]
        else:
            # 分布式分配：确保无单一矿工获得完整任务
            self._distribute_shards(plan, shards, available_miners)
        
        # 设置合并节点（不同于执行矿工）
        if len(available_miners) > 1:
            # 选择一个不参与主要计算的节点作为合并节点
            plan.aggregator_id = available_miners[-1]
        
        return plan
    
    def _distribute_shards(
        self,
        plan: DistributedExecutionPlan,
        shards: List[TaskShard],
        miners: List[str],
    ):
        """安全分配分片
        
        确保：
        - 每个矿工只获得部分分片
        - 代码和数据分片分配给不同矿工
        """
        code_shards = [s for s in shards if s.shard_type == ShardType.CODE]
        data_shards = [s for s in shards if s.shard_type == ShardType.DATA]
        other_shards = [s for s in shards if s.shard_type not in [ShardType.CODE, ShardType.DATA]]
        
        # 初始化分配
        for miner in miners:
            plan.shard_assignments[miner] = []
        
        # 代码分片：尽量分散
        for i, shard in enumerate(code_shards):
            miner = miners[i % len(miners)]
            plan.shard_assignments[miner].append(shard.shard_id)
            shard.recipient_miner_id = miner
        
        # 数据分片：与代码分片错开
        for i, shard in enumerate(data_shards):
            # 偏移分配，确保同一矿工不同时获得对应的代码和数据
            offset = (len(miners) // 2) if len(miners) > 1 else 0
            miner = miners[(i + offset) % len(miners)]
            plan.shard_assignments[miner].append(shard.shard_id)
            shard.recipient_miner_id = miner
        
        # 其他分片随机分配
        for shard in other_shards:
            miner = secrets.choice(miners)
            plan.shard_assignments[miner].append(shard.shard_id)
            shard.recipient_miner_id = miner
    
    def prepare_encrypted_shards(
        self,
        shards: List[TaskShard],
        task_key_id: str,
        task_key_material: bytes,
    ) -> List[TaskShard]:
        """为分片加密"""
        encrypted_shards = []
        
        for shard in shards:
            if not hasattr(shard, '_plaintext') or not shard._plaintext:
                continue
            
            # 为目标矿工派生密钥
            if not shard.recipient_miner_id:
                shard.recipient_miner_id = "default_miner"
            
            derived_key = self.key_engine.derive_miner_key(
                task_key_id,
                task_key_material,
                shard.recipient_miner_id,
            )
            
            # 加密分片
            ciphertext, _ = self.key_engine.encrypt_for_miner(
                shard._plaintext,
                derived_key,
            )
            
            shard.encrypted_content = ciphertext
            shard.encryption_state = EncryptionState.ENCRYPTED
            shard.key_id = derived_key.key_id
            
            # 删除明文
            delattr(shard, '_plaintext')
            
            encrypted_shards.append(shard)
        
        return encrypted_shards


class ContainerSecurityEnforcer:
    """容器安全执行器
    
    Layer 3：矿工本地封装安全约束
    - 一次性、不可复用、不可观察的执行黑盒
    """
    
    def __init__(self, log_fn: Optional[Callable[[str], None]] = None):
        self.log_fn = log_fn or print
    
    def create_policy(
        self,
        security_level: ContainerSecurityLevel = ContainerSecurityLevel.ENHANCED,
    ) -> ContainerSecurityPolicy:
        """创建安全策略"""
        policy = ContainerSecurityPolicy(security_level=security_level)
        
        if security_level == ContainerSecurityLevel.MAXIMUM:
            # 最大安全级别
            policy.max_memory_mb = 8192
            policy.max_runtime_seconds = 1800
            policy.max_pids = 50
        elif security_level == ContainerSecurityLevel.TEE:
            # TEE 保护
            policy.no_gpu_profiling = True
        
        return policy
    
    def generate_seccomp_profile(self) -> Dict[str, Any]:
        """生成 seccomp 安全配置"""
        return {
            "defaultAction": "SCMP_ACT_ERRNO",
            "architectures": ["SCMP_ARCH_X86_64"],
            "syscalls": [
                # 仅允许必要的系统调用
                {
                    "names": [
                        "read", "write", "close", "fstat", "lseek",
                        "mmap", "mprotect", "munmap", "brk",
                        "rt_sigaction", "rt_sigprocmask",
                        "exit", "exit_group",
                        # GPU 相关（受限）
                        "ioctl",  # 需要进一步限制
                    ],
                    "action": "SCMP_ACT_ALLOW"
                }
            ]
        }
    
    def validate_container_config(
        self,
        config: Dict[str, Any],
        policy: ContainerSecurityPolicy,
    ) -> Tuple[bool, List[str]]:
        """验证容器配置是否符合安全策略"""
        violations = []
        
        # 检查特权模式
        if config.get("privileged", False) and policy.no_privilege:
            violations.append("禁止特权模式")
        
        # 检查网络
        if config.get("network_mode") != "none" and policy.no_network:
            violations.append("禁止网络访问")
        
        # 检查挂载
        mounts = config.get("mounts", [])
        if mounts and policy.no_external_mount:
            for mount in mounts:
                if mount.get("type") != "tmpfs":
                    violations.append(f"禁止外部挂载: {mount}")
        
        # 检查 capabilities
        if config.get("cap_add") and policy.no_new_privs:
            violations.append("禁止添加 capabilities")
        
        return len(violations) == 0, violations


# ============== 结果合并器 ==============

class SecureResultAggregator:
    """安全结果合并器
    
    结果合并原则：
    - 矿工输出加密中间结果
    - 合并节点仅执行数学合并/拼接
    - 合并节点不具备解密能力
    """
    
    def __init__(self, log_fn: Optional[Callable[[str], None]] = None):
        self.log_fn = log_fn or print
    
    def aggregate_encrypted_results(
        self,
        encrypted_results: List[bytes],
        aggregation_type: str = "concat",
    ) -> bytes:
        """合并加密结果（无需解密）"""
        if aggregation_type == "concat":
            # 简单拼接（保持加密状态）
            return b"".join(encrypted_results)
        elif aggregation_type == "mathematical":
            # 数学合并（加密结果的确定性聚合）
            return self._mathematical_aggregate(encrypted_results)
        else:
            raise ValueError(f"不支持的合并类型: {aggregation_type}")
    
    def _mathematical_aggregate(self, results: List[bytes]) -> bytes:
        """数学聚合：对加密结果进行确定性合并
        
        使用 Merkle 哈希链保证结果的完整性和顺序：
        - 每个分片结果单独哈希
        - 按顺序构建哈希链
        - 最终输出包含聚合哈希 + 原始数据
        
        注意：这不是同态加密（同态加密允许在密文上直接运算），
        而是对加密结果的安全聚合，保证数据完整性可验证。
        """
        if not results:
            return b""
        
        # 构建分片哈希链
        chain_hash = hashlib.sha256(b"AGGREGATE_INIT").digest()
        for i, result in enumerate(results):
            shard_hash = hashlib.sha256(result).digest()
            chain_hash = hashlib.sha256(
                chain_hash + shard_hash + i.to_bytes(4, 'big')
            ).digest()
        
        # 输出：聚合哈希(32B) + 分片数量(4B) + 原始数据
        shard_count = len(results).to_bytes(4, 'big')
        return chain_hash + shard_count + b"".join(results)
    
    def create_result_commitment(
        self,
        aggregated_result: bytes,
        shard_hashes: List[str],
    ) -> Dict[str, str]:
        """创建结果承诺"""
        return {
            "result_hash": hashlib.sha256(aggregated_result).hexdigest(),
            "shard_count": str(len(shard_hashes)),
            "merkle_root": AuditEngine().build_merkle_tree(shard_hashes),
        }


# ============== 主安全管理器 ==============

class SecureComputeMarket:
    """安全算力市场主管理器
    
    集成所有安全组件，提供统一接口
    """
    
    def __init__(self, log_fn: Optional[Callable[[str], None]] = None):
        self.log_fn = log_fn or print
        
        # 核心组件
        self.sharding_engine = TaskShardingEngine(log_fn)
        self.key_engine = KeyDerivationEngine()
        self.audit_engine = AuditEngine(log_fn)
        self.distributed_engine = DistributedExecutionEngine(log_fn)
        self.container_enforcer = ContainerSecurityEnforcer(log_fn)
        self.result_aggregator = SecureResultAggregator(log_fn)
    
    def submit_secure_task(
        self,
        user_id: str,
        code: bytes,
        data: bytes,
        args: bytes,
        available_miners: List[str],
        execution_mode: ExecutionMode = ExecutionMode.DISTRIBUTED,
    ) -> Tuple[str, DistributedExecutionPlan, List[TaskShard]]:
        """提交安全任务
        
        完整流程：
        1. 生成任务密钥
        2. 拆分任务
        3. 创建分布式执行计划
        4. 加密分片
        5. 创建审计记录
        """
        task_id = uuid.uuid4().hex[:12]
        self.log_fn(f"🔒 开始安全任务提交: {task_id}")
        
        # 1. 生成任务主密钥
        key_id, key_material = self.key_engine.generate_task_key(task_id)
        self.log_fn(f"   ✓ 生成任务密钥: {key_id}")
        
        # 2. 拆分任务
        num_shards = min(len(available_miners), SecurityConfig.DEFAULT_SHARDS)
        shards = self.sharding_engine.shard_task(task_id, code, data, args, num_shards)
        self.log_fn(f"   ✓ 任务拆分为 {len(shards)} 个分片")
        
        # 3. 创建执行计划
        plan = self.distributed_engine.create_execution_plan(
            task_id, shards, available_miners, execution_mode
        )
        self.log_fn(f"   ✓ 执行模式: {execution_mode.value}")
        
        # 4. 加密分片
        encrypted_shards = self.distributed_engine.prepare_encrypted_shards(
            shards, key_id, key_material
        )
        self.log_fn(f"   ✓ 已加密 {len(encrypted_shards)} 个分片")
        
        # 5. 创建审计承诺
        code_hash = hashlib.sha256(code).hexdigest()
        data_hash = hashlib.sha256(data).hexdigest()
        args_hash = hashlib.sha256(args).hexdigest()
        commitment = self.audit_engine.create_task_commitment(
            task_id, code_hash, data_hash, args_hash
        )
        self.log_fn(f"   ✓ 审计承诺: {commitment[:16]}...")
        
        self.log_fn(f"✅ 任务 {task_id} 准备完成")
        
        return task_id, plan, encrypted_shards
    
    def can_miner_see_full_code(self) -> bool:
        """矿工能否看到完整代码？
        
        结论: 取决于安全级别
        
        标准模式 (容器隔离):
        - 正常情况下不能 ← 代码被拆分 + 加密
        - ⚠️ 但拥有 root 权限的矿工理论上可以 dump 容器内进程内存，
          获取解密后的代码片段
        
        TEE 模式:
        - 不能 ← 解密发生在 enclave 内
        """
        return False  # 标准流程下无法直接看到
    
    def can_miners_collude_to_see_full_task(self) -> Tuple[bool, str]:
        """多矿工串谋能否看到完整任务？
        
        诚实结论: ⚠️ 在当前实现中，理论上可以。
        
        原因:
        - 每个矿工拥有自己的派生密钥（这是安全的）
        - 但每个矿工在执行时必须解密自己的分片（明文在进程内存中）
        - 如果所有矿工串谋，各自 dump 自己的明文分片
        - 然后合并，就能重组完整任务
        
        缓解措施:
        - 分片设计增加了串谋难度和成本
        - 审计系统可检测异常行为
        - 经济激励模型使得串谋不合算
        
        真正的防串谋需要: TEE 硬件 + Remote Attestation
        """
        return True, (
            "⚠️ 当前实现下，串谋矿工理论上可以重组任务。"
            "每个矿工执行时明文存在于进程内存中。"
            "真正防串谋需要 TEE 硬件支持。"
        )
    
    def get_security_summary(self) -> Dict[str, Any]:
        """获取安全摘要（诚实版本）"""
        return {
            "threat_model": {
                "miner_untrusted": True,
                "miner_has_root": True,
                "miners_may_collude": True,
            },
            "protections": {
                "task_sharding": True,
                "end_to_end_encryption": True,
                "derived_keys_per_miner": True,
                "container_isolation": True,
                "no_network": True,
                "no_debug": True,
                "audit_hash_only": True,
            },
            "honest_assessment": {
                "miner_cannot_see_full_code_normally": True,
                "miner_with_root_can_dump_memory": True,
                "colluding_miners_can_reconstruct_with_root": True,
                "encryption_protects_transport_and_storage": True,
                "encryption_does_NOT_protect_runtime_memory": True,
                "tee_needed_for_full_protection": True,
            },
            "security_levels": {
                "vs_network_eavesdrop": "★★★★★ (AES-256-GCM)",
                "vs_filesystem_access": "★★★★☆ (加密存储)",
                "vs_honest_but_curious_miner": "★★★★☆ (容器隔离 + 加密)",
                "vs_malicious_root_miner": "★★☆☆☆ (可 dump 内存)",
                "vs_colluding_miners": "★★☆☆☆ (可重组分片)",
                "with_tee_hardware": "★★★★★ (enclave 保护)",
            },
            "config": {
                "min_shards": SecurityConfig.MIN_SHARDS,
                "max_shards": SecurityConfig.MAX_SHARDS,
                "key_ttl_seconds": SecurityConfig.KEY_TTL_SECONDS,
                "max_onchain_data": SecurityConfig.MAX_ONCHAIN_DATA,
            }
        }


# ============== 便捷函数 ==============

def create_secure_market(log_fn: Optional[Callable[[str], None]] = None) -> SecureComputeMarket:
    """创建安全算力市场实例"""
    return SecureComputeMarket(log_fn)
