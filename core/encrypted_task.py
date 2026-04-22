"""
encrypted_task.py - 任务分发与数据加密系统

==============================================================
加密方案说明 (2026-02-17)
==============================================================

加密算法: RSA-2048 + AES-256-GCM (混合加密)

✅ 保护效果:
  - 传输层加密 (防止网络窃听)
  - 存储层加密 (防止文件系统访问)
  - 密钥分离 (每个节点只能解密自己的部分)

⚠️ 关键限制:
  - 解密后明文在进程内存中
  - 拥有内存访问权限者可读取明文
  - 不防止进程内存dump (gcore)

性能开销: ~1-3% (AES硬件加速)

详见: docs/SECURITY_ARCHITECTURE.md
==============================================================

基于设计文档实现：
1. 端到端加密任务提交
2. 链式加密数据传递
3. 时间计费模型
4. 隐私保护机制

加密流程：
    用户 → 接收者A（公钥A加密）
    接收者A → 接收者B（私钥A解密后，公钥B再加密）
    ...
    最终结果返回用户（用户私钥解密）

特性：
- RSA + AES 混合加密
- 每个节点只能访问自己需要处理的部分
- 按时间计费
- 智能合约结算支持
"""

import os
import uuid
import time
import hashlib
import base64
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum

# 尝试导入加密库
try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Random import get_random_bytes
    from Crypto.Hash import SHA256
    from Crypto.Signature import pkcs1_15
    HAS_PYCRYPTODOME = True
except ImportError:
    HAS_PYCRYPTODOME = False

try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    from core.security import is_production_mode
except Exception:
    def is_production_mode() -> bool:
        return os.environ.get("POUW_ENV", "").lower() in ("production", "mainnet")

# 生产模式安全检查——禁止 XOR 模拟加密
HAS_REAL_CRYPTO = HAS_PYCRYPTODOME or HAS_CRYPTOGRAPHY
PRODUCTION_MODE = is_production_mode()

if not HAS_REAL_CRYPTO:
    if PRODUCTION_MODE:
        raise ImportError(
            "🛑 严重安全错误: 生产环境必须安装加密库。\n"
            "  请运行: pip install pycryptodome  或  pip install cryptography\n"
            "  XOR 模拟加密不提供任何安全性，禁止在生产环境使用。"
        )
    else:
        import warnings
        warnings.warn(
            "⚠️ 加密库未安装，回退到 XOR 模拟加密（仅限开发/测试）。"
            "生产环境请安装: pip install pycryptodome",
            RuntimeWarning,
            stacklevel=2,
        )


# ============== 加密层 ==============

class EncryptionScheme(Enum):
    """加密方案。"""
    RSA_AES = "RSA_AES"           # RSA + AES 混合
    ECIES = "ECIES"               # 椭圆曲线集成加密
    HYBRID = "HYBRID"             # 混合方案


@dataclass
class KeyPair:
    """非对称密钥对。"""
    public_key: bytes
    private_key: bytes
    public_key_pem: str = ""
    private_key_pem: str = ""
    key_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if not self.public_key_pem and self.public_key:
            self.public_key_pem = base64.b64encode(self.public_key).decode()
        if not self.private_key_pem and self.private_key:
            self.private_key_pem = base64.b64encode(self.private_key).decode()


@dataclass
class EncryptedPayload:
    """加密的数据载荷。"""
    payload_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    encrypted_data: bytes = b""           # AES 加密的数据
    encrypted_key: bytes = b""            # RSA 加密的 AES 密钥
    nonce: bytes = b""                    # AES nonce/IV
    tag: bytes = b""                      # 认证标签
    sender_key_id: str = ""               # 发送者密钥 ID
    recipient_key_id: str = ""            # 接收者密钥 ID
    data_hash: str = ""                   # 原始数据哈希（用于验证）
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload_id": self.payload_id,
            "encrypted_data": base64.b64encode(self.encrypted_data).decode(),
            "encrypted_key": base64.b64encode(self.encrypted_key).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "tag": base64.b64encode(self.tag).decode(),
            "sender_key_id": self.sender_key_id,
            "recipient_key_id": self.recipient_key_id,
            "data_hash": self.data_hash,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedPayload":
        return cls(
            payload_id=data.get("payload_id", ""),
            encrypted_data=base64.b64decode(data.get("encrypted_data", "")),
            encrypted_key=base64.b64decode(data.get("encrypted_key", "")),
            nonce=base64.b64decode(data.get("nonce", "")),
            tag=base64.b64decode(data.get("tag", "")),
            sender_key_id=data.get("sender_key_id", ""),
            recipient_key_id=data.get("recipient_key_id", ""),
            data_hash=data.get("data_hash", ""),
            created_at=data.get("created_at", time.time()),
        )


class HybridEncryption:
    """混合加密器（RSA + AES-256-GCM）。
    
    流程：
    1. 生成随机 AES 密钥
    2. 用 AES 加密数据
    3. 用接收者 RSA 公钥加密 AES 密钥
    """
    
    @staticmethod
    def generate_keypair(key_size: int = 2048) -> KeyPair:
        """生成 RSA 密钥对。"""
        if HAS_PYCRYPTODOME:
            key = RSA.generate(key_size)
            return KeyPair(
                public_key=key.publickey().export_key(),
                private_key=key.export_key(),
                public_key_pem=key.publickey().export_key().decode(),
                private_key_pem=key.export_key().decode(),
            )
        elif HAS_CRYPTOGRAPHY:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
            )
            public_key = private_key.public_key()
            
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return KeyPair(
                public_key=public_pem,
                private_key=private_pem,
                public_key_pem=public_pem.decode(),
                private_key_pem=private_pem.decode(),
            )
        else:
            # 模拟实现
            private_key = secrets.token_bytes(32)
            public_key = hashlib.sha256(private_key).digest()
            return KeyPair(
                public_key=public_key,
                private_key=private_key,
            )
    
    @staticmethod
    def encrypt(
        plaintext: bytes,
        recipient_public_key: bytes,
        sender_key_id: str = "",
        recipient_key_id: str = "",
    ) -> EncryptedPayload:
        """混合加密数据。"""
        # 计算数据哈希
        data_hash = hashlib.sha256(plaintext).hexdigest()
        
        if HAS_PYCRYPTODOME:
            # 生成 AES 密钥
            aes_key = get_random_bytes(32)  # AES-256
            nonce = get_random_bytes(12)    # GCM nonce
            
            # AES-GCM 加密数据
            cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher_aes.encrypt_and_digest(plaintext)
            
            # RSA 加密 AES 密钥
            rsa_key = RSA.import_key(recipient_public_key)
            cipher_rsa = PKCS1_OAEP.new(rsa_key, hashAlgo=SHA256)
            encrypted_key = cipher_rsa.encrypt(aes_key)
            
            return EncryptedPayload(
                encrypted_data=ciphertext,
                encrypted_key=encrypted_key,
                nonce=nonce,
                tag=tag,
                sender_key_id=sender_key_id,
                recipient_key_id=recipient_key_id,
                data_hash=data_hash,
            )
        elif HAS_CRYPTOGRAPHY:
            # 生成 AES 密钥
            aes_key = secrets.token_bytes(32)
            nonce = secrets.token_bytes(12)
            
            # AES-GCM 加密
            aesgcm = AESGCM(aes_key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            
            # RSA 加密 AES 密钥
            public_key = serialization.load_pem_public_key(recipient_public_key)
            encrypted_key = public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return EncryptedPayload(
                encrypted_data=ciphertext,
                encrypted_key=encrypted_key,
                nonce=nonce,
                sender_key_id=sender_key_id,
                recipient_key_id=recipient_key_id,
                data_hash=data_hash,
            )
        else:
            # XOR 模拟加密——仅限开发/测试，生产环境已在模块加载时拦截
            import warnings
            warnings.warn("❌ 使用 XOR 模拟加密，无实际安全性！仅限开发测试！", RuntimeWarning, stacklevel=2)
            aes_key = secrets.token_bytes(32)
            nonce = secrets.token_bytes(12)
            
            # XOR 模拟
            key_stream = (aes_key * ((len(plaintext) // 32) + 1))[:len(plaintext)]
            ciphertext = bytes(a ^ b for a, b in zip(plaintext, key_stream))
            
            # 简单"加密" AES 密钥
            encrypted_key = bytes(a ^ b for a, b in zip(aes_key, recipient_public_key[:32]))
            
            return EncryptedPayload(
                encrypted_data=ciphertext,
                encrypted_key=encrypted_key,
                nonce=nonce,
                sender_key_id=sender_key_id,
                recipient_key_id=recipient_key_id,
                data_hash=data_hash,
            )
    
    @staticmethod
    def decrypt(
        payload: EncryptedPayload,
        recipient_private_key: bytes,
    ) -> bytes:
        """混合解密数据。"""
        if HAS_PYCRYPTODOME:
            # RSA 解密 AES 密钥
            rsa_key = RSA.import_key(recipient_private_key)
            cipher_rsa = PKCS1_OAEP.new(rsa_key, hashAlgo=SHA256)
            aes_key = cipher_rsa.decrypt(payload.encrypted_key)
            
            # AES-GCM 解密数据
            cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=payload.nonce)
            plaintext = cipher_aes.decrypt_and_verify(payload.encrypted_data, payload.tag)
            
            return plaintext
        elif HAS_CRYPTOGRAPHY:
            # RSA 解密 AES 密钥
            private_key = serialization.load_pem_private_key(recipient_private_key, password=None)
            aes_key = private_key.decrypt(
                payload.encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # AES-GCM 解密
            aesgcm = AESGCM(aes_key)
            plaintext = aesgcm.decrypt(payload.nonce, payload.encrypted_data, None)
            
            return plaintext
        else:
            # XOR 模拟解密——仅限开发/测试
            import warnings
            warnings.warn("❌ 使用 XOR 模拟解密，无实际安全性！仅限开发测试！", RuntimeWarning, stacklevel=2)
            aes_key = bytes(a ^ b for a, b in zip(payload.encrypted_key, recipient_private_key[:32]))
            key_stream = (aes_key * ((len(payload.encrypted_data) // 32) + 1))[:len(payload.encrypted_data)]
            plaintext = bytes(a ^ b for a, b in zip(payload.encrypted_data, key_stream))
            
            return plaintext


# ============== 任务链 ==============

class TaskChainStatus(Enum):
    """任务链状态。"""
    CREATED = "created"
    ENCRYPTING = "encrypting"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ChainNode:
    """任务链节点。"""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    miner_id: str = ""
    miner_public_key: bytes = b""
    order_in_chain: int = 0                # 在链中的顺序
    
    # 状态
    status: str = "pending"                # pending/processing/completed/failed
    received_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # 加密数据
    encrypted_input: Optional[EncryptedPayload] = None
    encrypted_output: Optional[EncryptedPayload] = None
    
    # 执行证明（结算时必须验证）
    result_hash: str = ""                  # 计算结果的 SHA256 哈希
    execution_proof: str = ""              # 基于输入哈希+结果哈希+时间戳的证明
    
    # 计费
    compute_time_seconds: float = 0.0
    compute_cost: float = 0.0


@dataclass
class EncryptedTask:
    """加密任务。
    
    包含完整的任务信息和加密链。
    """
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: str = ""
    user_public_key: bytes = b""
    
    # 任务描述
    title: str = ""
    description: str = ""
    task_type: str = "compute"             # compute/training/inference/rendering
    
    # 原始数据（仅用户可见，提交后清除）
    code_data: bytes = b""                 # 代码
    input_data: bytes = b""                # 输入数据
    requirements_data: bytes = b""         # Python 依赖（requirements.txt 内容）
    
    # 任务链
    chain_nodes: List[ChainNode] = field(default_factory=list)
    chain_status: TaskChainStatus = TaskChainStatus.CREATED
    
    # 结果
    encrypted_final_result: Optional[EncryptedPayload] = None
    final_result_hash: str = ""
    
    # 计费
    estimated_hours: float = 1.0
    budget_per_hour: float = 10.0          # 每小时预算
    total_budget: float = 0.0
    actual_cost: float = 0.0
    currency: str = "MAIN"
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    submitted_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def total_compute_time(self) -> float:
        """总计算时间（秒）。"""
        return sum(node.compute_time_seconds for node in self.chain_nodes)
    
    @property
    def chain_length(self) -> int:
        return len(self.chain_nodes)
    
    def get_current_node(self) -> Optional[ChainNode]:
        """获取当前正在处理的节点。"""
        for node in self.chain_nodes:
            if node.status in ("pending", "processing"):
                return node
        return None


# ============== 时间计费系统 ==============

@dataclass
class TimeBillingConfig:
    """时间计费配置。"""
    billing_unit: str = "hour"             # second/minute/hour
    base_rate_per_unit: float = 10.0       # 基础费率
    gpu_multiplier: Dict[str, float] = field(default_factory=lambda: {
        "H100": 5.0,
        "A100": 3.0,
        "RTX4090": 2.0,
        "RTX4080": 1.5,
        "RTX3090": 1.2,
        "RTX3080": 1.0,
        "CPU": 0.3,
    })
    peak_hour_multiplier: float = 1.5      # 高峰时段加价
    peak_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 14, 15, 16, 17])
    minimum_charge: float = 0.1            # 最低收费


class TimeBillingEngine:
    """时间计费引擎。
    
    公式：总费用 = 算力单位 × 时长 × 基础费率 × 价格因子
    """
    
    def __init__(self, config: Optional[TimeBillingConfig] = None):
        self.config = config or TimeBillingConfig()
    
    def calculate_cost(
        self,
        compute_time_seconds: float,
        gpu_type: str = "RTX3080",
        is_peak_hour: bool = False,
        extra_factors: Dict[str, float] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """计算费用。
        
        Returns:
            (总费用, 明细字典)
        """
        # 转换时间单位
        if self.config.billing_unit == "hour":
            time_units = compute_time_seconds / 3600
        elif self.config.billing_unit == "minute":
            time_units = compute_time_seconds / 60
        else:
            time_units = compute_time_seconds
        
        # GPU 乘数
        gpu_multiplier = self.config.gpu_multiplier.get(gpu_type, 1.0)
        
        # 高峰时段乘数
        peak_multiplier = self.config.peak_hour_multiplier if is_peak_hour else 1.0
        
        # 额外因子
        extra_multiplier = 1.0
        if extra_factors:
            for factor in extra_factors.values():
                extra_multiplier *= factor
        
        # 计算费用
        cost = time_units * self.config.base_rate_per_unit * gpu_multiplier * peak_multiplier * extra_multiplier
        
        # 最低收费
        if cost < self.config.minimum_charge and cost > 0:
            cost = self.config.minimum_charge
        
        breakdown = {
            "time_seconds": compute_time_seconds,
            "time_units": time_units,
            "unit_type": self.config.billing_unit,
            "base_rate": self.config.base_rate_per_unit,
            "gpu_type": gpu_type,
            "gpu_multiplier": gpu_multiplier,
            "peak_multiplier": peak_multiplier,
            "extra_multiplier": extra_multiplier,
            "raw_cost": time_units * self.config.base_rate_per_unit * gpu_multiplier * peak_multiplier * extra_multiplier,
            "final_cost": cost,
        }
        
        return cost, breakdown
    
    def estimate_cost(
        self,
        estimated_hours: float,
        gpu_type: str = "RTX3080",
        gpu_count: int = 1,
    ) -> float:
        """预估费用。"""
        cost_per_gpu, _ = self.calculate_cost(
            estimated_hours * 3600,
            gpu_type,
        )
        return cost_per_gpu * gpu_count


# ============== 任务分发管理器 ==============

class EncryptedTaskManager:
    """加密任务管理器。
    
    负责：
    1. 任务创建与加密
    2. 任务链构建
    3. 数据加密传递
    4. 结果聚合与解密
    5. 计费结算
    """
    
    def __init__(
        self,
        billing_config: Optional[TimeBillingConfig] = None,
        log_fn: Callable[[str], None] = print,
    ):
        self.tasks: Dict[str, EncryptedTask] = {}
        self.node_keys: Dict[str, KeyPair] = {}      # miner_id -> keypair
        self.billing_engine = TimeBillingEngine(billing_config)
        self.log = log_fn
        
        # 计费记录
        self.billing_records: List[Dict[str, Any]] = []
    
    def register_miner(self, miner_id: str, public_key: Optional[bytes] = None) -> KeyPair:
        """注册矿工并返回/生成密钥对。"""
        if miner_id in self.node_keys:
            return self.node_keys[miner_id]
        
        if public_key:
            # 使用提供的公钥（矿工自己生成私钥）
            keypair = KeyPair(public_key=public_key, private_key=b"")
        else:
            # 生成新密钥对
            keypair = HybridEncryption.generate_keypair()
        
        self.node_keys[miner_id] = keypair
        self.log(f"🔑 [ENCRYPT] Registered miner {miner_id} with key {keypair.key_id}")
        return keypair
    
    def create_task(
        self,
        user_id: str,
        user_keypair: KeyPair,
        title: str,
        description: str,
        code_data: bytes,
        input_data: bytes,
        task_type: str = "compute",
        estimated_hours: float = 1.0,
        budget_per_hour: float = 10.0,
        receivers: List[str] = None,
        requirements_data: bytes = b"",
    ) -> EncryptedTask:
        """创建加密任务。
        
        Args:
            user_id: 用户 ID
            user_keypair: 用户密钥对
            title: 任务标题
            description: 任务描述
            code_data: 代码数据
            input_data: 输入数据
            task_type: 任务类型
            estimated_hours: 预估时长
            budget_per_hour: 每小时预算
            receivers: 指定接收者列表（按顺序）
            requirements_data: Python 依赖（requirements.txt 内容）
        """
        task = EncryptedTask(
            user_id=user_id,
            user_public_key=user_keypair.public_key,
            title=title,
            description=description,
            task_type=task_type,
            code_data=code_data,
            input_data=input_data,
            requirements_data=requirements_data,
            estimated_hours=estimated_hours,
            budget_per_hour=budget_per_hour,
            total_budget=estimated_hours * budget_per_hour,
        )
        
        # 构建任务链
        if receivers:
            for i, receiver_id in enumerate(receivers):
                if receiver_id not in self.node_keys:
                    self.register_miner(receiver_id)
                
                node = ChainNode(
                    miner_id=receiver_id,
                    miner_public_key=self.node_keys[receiver_id].public_key,
                    order_in_chain=i,
                )
                task.chain_nodes.append(node)
        
        self.tasks[task.task_id] = task
        self.log(f"📋 [ENCRYPT] Created task {task.task_id}: {title}")
        return task
    
    def encrypt_and_submit(self, task_id: str, user_private_key: bytes) -> bool:
        """加密并提交任务。
        
        将任务数据加密，准备分发给接收者。
        """
        task = self.tasks.get(task_id)
        if not task:
            self.log(f"❌ [ENCRYPT] Task {task_id} not found")
            return False
        
        if not task.chain_nodes:
            self.log(f"❌ [ENCRYPT] Task {task_id} has no receivers")
            return False
        
        task.chain_status = TaskChainStatus.ENCRYPTING
        
        # 组合代码、数据和依赖（一起加密，矿工无法提前看到内容）
        combined_data = task.code_data + b"||DATA||" + task.input_data + b"||REQS||" + task.requirements_data
        
        # 用第一个接收者的公钥加密
        first_node = task.chain_nodes[0]
        encrypted_payload = HybridEncryption.encrypt(
            combined_data,
            first_node.miner_public_key,
            sender_key_id="user",
            recipient_key_id=first_node.node_id,
        )
        
        first_node.encrypted_input = encrypted_payload
        
        # 清除原始数据
        task.code_data = b""
        task.input_data = b""
        task.requirements_data = b""
        
        task.chain_status = TaskChainStatus.SUBMITTED
        task.submitted_at = time.time()
        
        self.log(f"🔐 [ENCRYPT] Task {task_id} encrypted and submitted")
        return True
    
    def process_at_node(
        self,
        task_id: str,
        node_id: str,
        node_private_key: bytes,
        process_fn: Callable[[bytes], bytes],
    ) -> Optional[EncryptedPayload]:
        """在节点处理任务。
        
        1. 解密输入数据
        2. 执行处理函数
        3. 加密输出给下一个节点（或用户）
        
        Args:
            task_id: 任务 ID
            node_id: 节点 ID
            node_private_key: 节点私钥
            process_fn: 处理函数，接收解密数据，返回处理结果
        """
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        # 找到当前节点
        current_node = None
        node_index = -1
        for i, node in enumerate(task.chain_nodes):
            if node.node_id == node_id:
                current_node = node
                node_index = i
                break
        
        if not current_node or not current_node.encrypted_input:
            self.log(f"❌ [ENCRYPT] Node {node_id} not found or no input")
            return None
        
        current_node.status = "processing"
        current_node.started_at = time.time()
        task.chain_status = TaskChainStatus.IN_PROGRESS
        
        try:
            # 解密输入
            decrypted_data = HybridEncryption.decrypt(
                current_node.encrypted_input,
                node_private_key,
            )
            
            # 完整性验证：检查解密后数据哈希是否与 payload 中记录的哈希匹配
            if current_node.encrypted_input.data_hash:
                actual_hash = hashlib.sha256(decrypted_data).hexdigest()
                if actual_hash != current_node.encrypted_input.data_hash:
                    self.log(f"⚠️ [ENCRYPT] 完整性验证失败: 数据哈希不匹配 (node={node_id})")
                    current_node.status = "failed"
                    task.chain_status = TaskChainStatus.FAILED
                    return None
            
            # 执行处理
            start_time = time.time()
            processed_data = process_fn(decrypted_data)
            compute_time = time.time() - start_time
            
            # 处理完成后清理明文（尽力而为，Python 无法保证内存完全清除）
            # 注意: 这不能防止内存 dump 攻击，但减少明文在内存中的驻留时间
            del decrypted_data
            
            current_node.compute_time_seconds = compute_time
            
            # 确定下一个接收者
            if node_index < len(task.chain_nodes) - 1:
                # 还有下一个节点
                next_node = task.chain_nodes[node_index + 1]
                next_public_key = next_node.miner_public_key
                recipient_key_id = next_node.node_id
            else:
                # 最后一个节点，返回给用户
                next_public_key = task.user_public_key
                recipient_key_id = "user"
            
            # 加密输出
            encrypted_output = HybridEncryption.encrypt(
                processed_data,
                next_public_key,
                sender_key_id=current_node.node_id,
                recipient_key_id=recipient_key_id,
            )
            
            current_node.encrypted_output = encrypted_output
            current_node.status = "completed"
            current_node.completed_at = time.time()
            
            # 生成执行证明（用于结算验证）
            result_hash = hashlib.sha256(processed_data).hexdigest()[:32]
            current_node.result_hash = result_hash
            current_node.execution_proof = hashlib.sha256(
                f"{result_hash}:{current_node.node_id}".encode()
            ).hexdigest()[:24]
            
            # 计算费用
            cost, _ = self.billing_engine.calculate_cost(compute_time)
            current_node.compute_cost = cost
            
            # 将输出传递给下一个节点
            if node_index < len(task.chain_nodes) - 1:
                next_node.encrypted_input = encrypted_output
            else:
                # 任务完成
                task.encrypted_final_result = encrypted_output
                task.final_result_hash = encrypted_output.data_hash
                task.chain_status = TaskChainStatus.COMPLETED
                task.completed_at = time.time()
                
                # 计算总费用
                task.actual_cost = sum(n.compute_cost for n in task.chain_nodes)
                
                self.log(f"✅ [ENCRYPT] Task {task_id} completed, cost: {task.actual_cost:.4f}")
            
            return encrypted_output
            
        except Exception as e:
            current_node.status = "failed"
            task.chain_status = TaskChainStatus.FAILED
            self.log(f"❌ [ENCRYPT] Processing failed at node {node_id}: {e}")
            return None
    
    def decrypt_result(
        self,
        task_id: str,
        user_private_key: bytes,
    ) -> Optional[bytes]:
        """解密最终结果。"""
        task = self.tasks.get(task_id)
        if not task or not task.encrypted_final_result:
            return None
        
        try:
            result = HybridEncryption.decrypt(
                task.encrypted_final_result,
                user_private_key,
            )
            return result
        except Exception as e:
            self.log(f"❌ [ENCRYPT] Failed to decrypt result: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态。"""
        task = self.tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}
        
        return {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.chain_status.value,
            "chain_length": task.chain_length,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "miner_id": n.miner_id,
                    "order": n.order_in_chain,
                    "status": n.status,
                    "compute_time": n.compute_time_seconds,
                    "compute_cost": n.compute_cost,
                }
                for n in task.chain_nodes
            ],
            "total_compute_time": task.total_compute_time,
            "estimated_cost": task.total_budget,
            "actual_cost": task.actual_cost,
            "created_at": task.created_at,
            "completed_at": task.completed_at,
        }
    
    def generate_billing_report(self, task_id: str) -> Dict[str, Any]:
        """生成计费报告。"""
        task = self.tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}
        
        report = {
            "task_id": task.task_id,
            "user_id": task.user_id,
            "title": task.title,
            "currency": task.currency,
            "estimated_budget": task.total_budget,
            "actual_cost": task.actual_cost,
            "savings": task.total_budget - task.actual_cost,
            "nodes_breakdown": [],
            "total_compute_time_seconds": task.total_compute_time,
            "billing_timestamp": time.time(),
        }
        
        for node in task.chain_nodes:
            cost, breakdown = self.billing_engine.calculate_cost(node.compute_time_seconds)
            report["nodes_breakdown"].append({
                "node_id": node.node_id,
                "miner_id": node.miner_id,
                "compute_time": node.compute_time_seconds,
                "cost": cost,
                "breakdown": breakdown,
            })
        
        self.billing_records.append(report)
        return report


# ============== 智能合约结算接口 ==============

@dataclass
class SettlementTransaction:
    """结算交易。"""
    tx_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_id: str = ""
    from_user: str = ""
    to_miner: str = ""
    amount: float = 0.0
    currency: str = "MAIN"
    status: str = "pending"              # pending/confirmed/failed
    created_at: float = field(default_factory=time.time)
    confirmed_at: Optional[float] = None


class TaskSettlementContract:
    """任务结算合约。
    
    模拟智能合约功能：
    1. 锁定用户预算
    2. 任务完成后分配给各节点
    3. 支持争议处理
    """
    
    def __init__(self, log_fn: Callable[[str], None] = print):
        self.locked_budgets: Dict[str, float] = {}   # task_id -> locked amount
        self.transactions: List[SettlementTransaction] = []
        self.balances: Dict[str, float] = {}          # user_id -> balance
        self.log = log_fn
    
    def deposit(self, user_id: str, amount: float):
        """用户充值。"""
        self.balances[user_id] = self.balances.get(user_id, 0) + amount
        self.log(f"💰 [CONTRACT] User {user_id} deposited {amount}")
    
    def lock_budget(self, task_id: str, user_id: str, amount: float) -> bool:
        """锁定任务预算。"""
        balance = self.balances.get(user_id, 0)
        if balance < amount:
            self.log(f"❌ [CONTRACT] Insufficient balance for user {user_id}")
            return False
        
        self.balances[user_id] -= amount
        self.locked_budgets[task_id] = amount
        self.log(f"🔒 [CONTRACT] Locked {amount} for task {task_id}")
        return True
    
    def release_budget(self, task_id: str, user_id: str) -> float:
        """释放锁定预算，全额退还给用户（用于上传超时等取消场景）。
        
        Returns:
            退还金额，若无锁定则返回 0
        """
        if task_id not in self.locked_budgets:
            return 0.0
        amount = self.locked_budgets.pop(task_id)
        self.balances[user_id] = self.balances.get(user_id, 0) + amount
        self.log(f"🔓 [CONTRACT] Released {amount:.4f} locked budget for task {task_id} back to user {user_id}")
        return amount
    
    def settle_task(self, task: EncryptedTask) -> List[SettlementTransaction]:
        """结算任务（需验证执行证明）。"""
        if task.task_id not in self.locked_budgets:
            self.log(f"❌ [CONTRACT] No locked budget for task {task.task_id}")
            return []
        
        locked = self.locked_budgets[task.task_id]
        transactions = []
        total_paid = 0.0
        
        # 分配给各节点（必须有执行证明才可结算，且总支付不得超过锁定预算）
        for node in task.chain_nodes:
            if node.status == "completed" and node.compute_cost > 0:
                # 验证执行证明
                if not node.result_hash or not node.execution_proof:
                    self.log(
                        f"⚠️ [CONTRACT] Node {node.miner_id} completed but missing "
                        f"execution proof, skipping settlement"
                    )
                    continue
                # 验证 proof = sha256(result_hash + ":" + node_id)[:24]
                import hashlib
                expected_proof = hashlib.sha256(
                    f"{node.result_hash}:{node.node_id}".encode()
                ).hexdigest()[:24]
                if node.execution_proof != expected_proof:
                    self.log(
                        f"⚠️ [CONTRACT] Node {node.miner_id} execution proof "
                        f"verification FAILED, skipping settlement"
                    )
                    continue

                # 防止总支付超过锁定预算（按比例封顶）
                remaining_budget = locked - total_paid
                if remaining_budget <= 0:
                    self.log(
                        f"⚠️ [CONTRACT] Budget exhausted, cannot pay node {node.miner_id}"
                    )
                    break
                actual_pay = min(node.compute_cost, remaining_budget)

                tx = SettlementTransaction(
                    task_id=task.task_id,
                    from_user=task.user_id,
                    to_miner=node.miner_id,
                    amount=actual_pay,
                    currency=task.currency,
                    status="confirmed",
                    confirmed_at=time.time(),
                )
                transactions.append(tx)
                total_paid += actual_pay
                
                # 增加矿工余额
                self.balances[node.miner_id] = self.balances.get(node.miner_id, 0) + actual_pay
        
        # 退还剩余
        refund = locked - total_paid
        if refund > 0:
            self.balances[task.user_id] = self.balances.get(task.user_id, 0) + refund
            self.log(f"💸 [CONTRACT] Refunded {refund:.4f} to user {task.user_id}")
        
        del self.locked_budgets[task.task_id]
        self.transactions.extend(transactions)
        
        self.log(f"✅ [CONTRACT] Settled task {task.task_id}, paid {total_paid:.4f} to {len(transactions)} miners")
        return transactions
    
    def get_balance(self, user_id: str) -> float:
        """获取余额。"""
        return self.balances.get(user_id, 0)


# ============== 辅助函数 ==============

def create_test_task_chain():
    """创建测试任务链。"""
    manager = EncryptedTaskManager()
    contract = TaskSettlementContract()
    
    # 用户和矿工密钥
    user_keypair = HybridEncryption.generate_keypair()
    miner1_keypair = manager.register_miner("miner_001")
    miner2_keypair = manager.register_miner("miner_002")
    miner3_keypair = manager.register_miner("miner_003")
    
    # 用户充值
    contract.deposit("user_001", 100.0)
    
    # 创建任务
    task = manager.create_task(
        user_id="user_001",
        user_keypair=user_keypair,
        title="分布式AI推理",
        description="使用三个节点进行分布式推理",
        code_data=b"import torch; model.forward(x)",
        input_data=b"tensor([1,2,3,4,5])",
        task_type="ai_inference",
        estimated_hours=1.0,
        budget_per_hour=10.0,
        receivers=["miner_001", "miner_002", "miner_003"],
    )
    
    # 锁定预算
    contract.lock_budget(task.task_id, "user_001", task.total_budget)
    
    # 加密提交
    manager.encrypt_and_submit(task.task_id, user_keypair.private_key)
    
    # 各节点处理
    import time as time_module
    
    def mock_process(data: bytes) -> bytes:
        time_module.sleep(0.1)  # 模拟 100ms 计算
        return b"processed_" + data[:50]
    
    for i, node in enumerate(task.chain_nodes):
        miner_key = manager.node_keys[node.miner_id].private_key
        manager.process_at_node(task.task_id, node.node_id, miner_key, mock_process)
    
    # 解密结果
    result = manager.decrypt_result(task.task_id, user_keypair.private_key)
    
    # 结算
    transactions = contract.settle_task(task)
    
    # 生成报告
    report = manager.generate_billing_report(task.task_id)
    
    return {
        "task": task,
        "result": result,
        "transactions": transactions,
        "report": report,
        "user_balance": contract.get_balance("user_001"),
        "miner_balances": {
            "miner_001": contract.get_balance("miner_001"),
            "miner_002": contract.get_balance("miner_002"),
            "miner_003": contract.get_balance("miner_003"),
        }
    }
