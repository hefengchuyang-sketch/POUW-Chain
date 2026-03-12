"""
MAIN 主币交易双见证机制

主币交易比板块内交易更关键，需要更高安全级别：
1. 跨板块结算交易（板块币→MAIN）
2. 主币直接转账（MAIN→MAIN）
3. 大额交易（超过阈值）

双见证流程：
1. 交易发起方签名提交
2. 随机选择 ≥2 个见证节点
3. 各见证节点独立验证：
   - 发送方余额
   - 签名有效性
   - 交易不重复（防双花）
   - 时间戳合理性
4. 收集足够见证签名后，交易生效
5. 写入主链，广播确认

设计原则：
- 见证节点从活跃节点池随机选择
- 见证节点不能是交易双方
- 见证超时自动重选
- 见证奖励从手续费分配
"""

import time
import hashlib
import random
import secrets
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
    from ecdsa.util import sigdecode_der, sigencode_der
    HAS_ECDSA = True
except ImportError:
    HAS_ECDSA = False

logger = logging.getLogger(__name__)


class WitnessStatus(Enum):
    """见证状态"""
    PENDING = "pending"          # 等待见证
    PARTIAL = "partial"          # 部分见证
    CONFIRMED = "confirmed"      # 见证完成
    REJECTED = "rejected"        # 被拒绝
    EXPIRED = "expired"          # 已过期


class TransactionType(Enum):
    """交易类型"""
    TRANSFER = "transfer"        # 普通转账
    EXCHANGE = "exchange"        # 板块币兑换
    REWARD = "reward"            # 挖矿奖励
    FEE = "fee"                  # 手续费
    GOVERNANCE = "governance"    # 治理操作


@dataclass
class WitnessRecord:
    """见证记录"""
    witness_id: str              # 见证节点 ID
    witness_address: str         # 见证节点地址
    timestamp: float             # 见证时间
    signature: str               # 见证签名
    verified: bool = True        # 验证结果
    reason: str = ""             # 拒绝原因（如有）


@dataclass
class MainTransaction:
    """主币交易"""
    tx_id: str                           # 交易 ID
    tx_type: TransactionType             # 交易类型
    from_address: str                    # 发送方地址
    to_address: str                      # 接收方地址
    amount: float                        # 金额
    fee: float                           # 手续费
    timestamp: float                     # 时间戳
    signature: str                       # 发送方签名
    public_key: str = ""                 # 发送方公钥（用于签名验证）
    
    # 见证相关
    witnesses_required: int = 2          # 需要的见证数
    witnesses: List[WitnessRecord] = field(default_factory=list)
    status: WitnessStatus = WitnessStatus.PENDING
    
    # 元数据
    memo: str = ""                       # 备注
    source_sector: str = ""              # 源板块（兑换时）
    block_height: int = 0                # 确认区块高度
    confirmed_at: float = 0              # 确认时间
    
    def __post_init__(self):
        if not self.tx_id:
            self.tx_id = self._generate_tx_id()
    
    def _generate_tx_id(self) -> str:
        """生成交易 ID（使用密码学安全随机数，完整 SHA-256）"""
        entropy = secrets.token_hex(32)
        data = f"{self.from_address}{self.to_address}{self.amount}{self.timestamp}{entropy}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def add_witness(self, record: WitnessRecord) -> bool:
        """添加见证记录
        
        Returns:
            True 如果见证被接受
        """
        # 检查是否已被此节点见证
        if any(w.witness_id == record.witness_id for w in self.witnesses):
            return False
        
        self.witnesses.append(record)
        
        # 更新状态
        confirmed_count = sum(1 for w in self.witnesses if w.verified)
        rejected_count = sum(1 for w in self.witnesses if not w.verified)
        
        if confirmed_count >= self.witnesses_required:
            self.status = WitnessStatus.CONFIRMED
            self.confirmed_at = time.time()
        elif rejected_count >= self.witnesses_required:
            self.status = WitnessStatus.REJECTED
        elif len(self.witnesses) > 0:
            self.status = WitnessStatus.PARTIAL
        
        return True
    
    def is_confirmed(self) -> bool:
        """是否已确认"""
        return self.status == WitnessStatus.CONFIRMED
    
    def witness_count(self) -> int:
        """有效见证数"""
        return sum(1 for w in self.witnesses if w.verified)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "tx_id": self.tx_id,
            "tx_type": self.tx_type.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "amount": self.amount,
            "fee": self.fee,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "status": self.status.value,
            "witnesses_required": self.witnesses_required,
            "witness_count": self.witness_count(),
            "witnesses": [
                {
                    "witness_id": w.witness_id,
                    "witness_address": w.witness_address,
                    "timestamp": w.timestamp,
                    "verified": w.verified,
                }
                for w in self.witnesses
            ],
            "memo": self.memo,
            "source_sector": self.source_sector,
            "block_height": self.block_height,
            "confirmed_at": self.confirmed_at,
        }


class WitnessNode:
    """见证节点
    
    每个全节点都可以作为见证节点参与交易验证。
    """
    
    def __init__(
        self,
        node_id: str,
        address: str,
        private_key: bytes = None,
    ):
        self.node_id = node_id
        self.address = address
        self.private_key = private_key or self._generate_key()
        
        # 状态
        self.is_active = True
        self.last_witness_time = 0
        self.witness_count = 0
        self.earned_fees = 0.0
    
    def _generate_key(self) -> bytes:
        """生成密钥（使用密码学安全随机数）"""
        if HAS_ECDSA:
            sk = SigningKey.generate(curve=SECP256k1)
            return sk.to_string()
        else:
            return secrets.token_bytes(32)
    
    def sign(self, data: bytes) -> str:
        """使用 ECDSA 签名数据（DER 编码，与项目统一格式一致）"""
        if not HAS_ECDSA:
            raise RuntimeError("ecdsa 库未安装，无法进行签名")
        sk = SigningKey.from_string(self.private_key, curve=SECP256k1)
        sig = sk.sign(data, sigencode=sigencode_der)
        return sig.hex()
    
    def get_public_key(self) -> str:
        """获取公钥的十六进制表示"""
        if not HAS_ECDSA:
            raise RuntimeError("ecdsa 库未安装")
        sk = SigningKey.from_string(self.private_key, curve=SECP256k1)
        return sk.get_verifying_key().to_string().hex()
    
    def verify_transaction(self, tx: MainTransaction, ledger: "MainLedger") -> Tuple[bool, str]:
        """验证交易
        
        Returns:
            (是否通过, 原因)
        """
        # 1. 检查基本字段
        if not tx.from_address or not tx.to_address:
            return False, "Invalid addresses"
        
        if tx.amount <= 0:
            return False, "Invalid amount"
        
        if tx.fee < 0:
            return False, "Invalid fee"
        
        # 2. 检查时间戳（不能太旧或太新）
        current_time = time.time()
        # 安全窗口：5分钟前到 30秒后
        if tx.timestamp < current_time - 300:  # 5分钟前
            return False, "Transaction too old (>5min)"
        if tx.timestamp > current_time + 30:   # 30秒后
            return False, "Transaction from future"
        
        # 3. 检查余额
        balance = ledger.get_balance(tx.from_address) if ledger else float('inf')
        if balance < tx.amount + tx.fee:
            return False, f"Insufficient balance: {balance} < {tx.amount + tx.fee}"
        
        # 4. 检查双花（交易 ID 是否已存在）
        if ledger and ledger.is_tx_processed(tx.tx_id):
            return False, "Transaction already processed (double spend attempt)"
        
        # 5. 检查签名（ECDSA 验证）
        if not tx.signature:
            return False, "Missing signature"
        
        if not tx.public_key:
            return False, "Missing public_key for signature verification"
        
        # 执行真实签名验证
        if HAS_ECDSA:
            try:
                vk = VerifyingKey.from_string(
                    bytes.fromhex(tx.public_key), curve=SECP256k1
                )
                tx_data = f"{tx.from_address}{tx.to_address}{tx.amount}{tx.fee}".encode()
                sig_bytes = bytes.fromhex(tx.signature)
                vk.verify(sig_bytes, tx_data, sigdecode=sigdecode_der)
            except (BadSignatureError, ValueError, Exception) as e:
                return False, f"Invalid signature: {e}"
        else:
            logger.warning("ecdsa 库未安装，无法验证交易签名")
            return False, "ecdsa library not available for signature verification"
        
        return True, "OK"
    
    def witness(self, tx: MainTransaction, ledger: "MainLedger" = None) -> WitnessRecord:
        """见证交易
        
        Returns:
            见证记录
        """
        # 验证交易
        verified, reason = self.verify_transaction(tx, ledger)
        
        # 生成签名（与 verify_transaction 使用一致的数据格式）
        tx_data = f"{tx.from_address}{tx.to_address}{tx.amount}{tx.fee}".encode()
        signature = self.sign(tx_data)
        
        # 创建记录
        record = WitnessRecord(
            witness_id=self.node_id,
            witness_address=self.address,
            timestamp=time.time(),
            signature=signature,
            verified=verified,
            reason="" if verified else reason,
        )
        
        # 更新统计
        self.last_witness_time = time.time()
        self.witness_count += 1
        
        return record


class DoubleWitnessEngine:
    """双见证引擎
    
    管理主币交易的双见证流程。
    """
    
    # 配置
    REQUIRED_WITNESSES = 2              # 默认需要 2 个见证
    LARGE_TX_THRESHOLD = 10000          # 大额交易阈值
    LARGE_TX_WITNESSES = 3              # 大额交易需要更多见证
    WITNESS_TIMEOUT = 30                # 见证超时（秒）
    WITNESS_FEE_RATIO = 0.1             # 见证者分得手续费比例（PRD v0.9：控制费率）
    
    def __init__(
        self,
        node_pool: List[WitnessNode] = None,
        ledger: "MainLedger" = None,
        log_fn = print,
    ):
        self.node_pool = node_pool or []
        self.ledger = ledger
        self.log = log_fn
        
        # 待处理交易
        self.pending_txs: Dict[str, MainTransaction] = {}
        
        # 已确认交易
        self.confirmed_txs: Dict[str, MainTransaction] = {}
        
        # 统计
        self.total_witnessed = 0
        self.total_rejected = 0
    
    def register_node(self, node: WitnessNode):
        """注册见证节点"""
        if node not in self.node_pool:
            self.node_pool.append(node)
            self.log(f"[WITNESS] 注册见证节点: {node.node_id}")
    
    def select_witnesses(
        self,
        tx: MainTransaction,
        exclude: List[str] = None,
    ) -> List[WitnessNode]:
        """选择见证节点
        
        Args:
            tx: 待见证交易
            exclude: 排除的地址（通常是交易双方）
        
        Returns:
            选中的见证节点列表
        """
        exclude = exclude or []
        exclude.extend([tx.from_address, tx.to_address])
        
        # 确定需要的见证数
        required = self.REQUIRED_WITNESSES
        if tx.amount >= self.LARGE_TX_THRESHOLD:
            required = self.LARGE_TX_WITNESSES
            self.log(f"[WITNESS] 大额交易，需要 {required} 个见证")
        
        tx.witnesses_required = required
        
        # 筛选可用节点
        available = [
            n for n in self.node_pool
            if n.is_active and n.address not in exclude
        ]
        
        if len(available) < required:
            self.log(f"[WITNESS] 警告: 可用节点不足 ({len(available)} < {required})")
            return available
        
        # 密码学安全随机选择
        secure_rng = secrets.SystemRandom()
        selected = secure_rng.sample(available, min(required, len(available)))
        
        self.log(f"[WITNESS] 选择见证节点: {[n.node_id for n in selected]}")
        return selected
    
    def submit_transaction(self, tx: MainTransaction) -> str:
        """提交交易进行见证
        
        Returns:
            交易 ID
        """
        self.log(f"[TX] 提交交易: {tx.tx_id}")
        self.log(f"  {tx.from_address} -> {tx.to_address}: {tx.amount} MAIN")
        
        # 选择见证者
        witnesses = self.select_witnesses(tx)
        
        if not witnesses:
            tx.status = WitnessStatus.REJECTED
            self.log(f"[TX] 交易被拒绝: 无可用见证节点")
            return tx.tx_id
        
        # 执行见证
        for node in witnesses:
            record = node.witness(tx, self.ledger)
            tx.add_witness(record)
            
            status = "✓ 通过" if record.verified else f"✗ 拒绝: {record.reason}"
            self.log(f"  [{node.node_id}] {status}")
        
        # 处理结果
        if tx.is_confirmed():
            self.confirmed_txs[tx.tx_id] = tx
            self.total_witnessed += 1
            
            # 分配手续费（仅分配给确认通过的见证节点）
            confirming_witnesses = [
                node for node in witnesses 
                if any(w.witness_id == node.node_id and w.verified for w in tx.witnesses)
            ]
            if confirming_witnesses:
                fee_per_witness = tx.fee * self.WITNESS_FEE_RATIO / len(confirming_witnesses)
                for node in confirming_witnesses:
                    node.earned_fees += fee_per_witness
            
            self.log(f"[TX] ✅ 交易确认: {tx.tx_id}")
        else:
            self.pending_txs[tx.tx_id] = tx
            if tx.status == WitnessStatus.REJECTED:
                self.total_rejected += 1
                self.log(f"[TX] ❌ 交易被拒绝: {tx.tx_id}")
        
        return tx.tx_id
    
    def get_transaction(self, tx_id: str) -> Optional[MainTransaction]:
        """获取交易"""
        return self.confirmed_txs.get(tx_id) or self.pending_txs.get(tx_id)
    
    def process_pending(self):
        """处理待见证交易（超时检查等）"""
        current_time = time.time()
        expired = []
        
        for tx_id, tx in self.pending_txs.items():
            if current_time - tx.timestamp > self.WITNESS_TIMEOUT:
                tx.status = WitnessStatus.EXPIRED
                expired.append(tx_id)
                self.log(f"[TX] 交易超时: {tx_id}")
        
        for tx_id in expired:
            del self.pending_txs[tx_id]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "active_nodes": len([n for n in self.node_pool if n.is_active]),
            "pending_txs": len(self.pending_txs),
            "confirmed_txs": len(self.confirmed_txs),
            "total_witnessed": self.total_witnessed,
            "total_rejected": self.total_rejected,
        }


class MainLedger:
    """主币账本（简化版）"""
    
    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.processed_txs: set = set()
    
    def get_balance(self, address: str) -> float:
        return self.balances.get(address, 0.0)
    
    def set_balance(self, address: str, amount: float):
        self.balances[address] = amount
    
    def is_tx_processed(self, tx_id: str) -> bool:
        return tx_id in self.processed_txs
    
    def record_tx(self, tx_id: str):
        self.processed_txs.add(tx_id)


# ============== 测试 ==============

if __name__ == "__main__":
    print("=" * 60)
    print("MAIN 主币交易双见证机制测试")
    print("=" * 60)
    
    # 创建账本
    ledger = MainLedger()
    ledger.set_balance("MAIN_ALICE", 10000.0)
    ledger.set_balance("MAIN_BOB", 500.0)
    
    # 创建见证节点
    nodes = [
        WitnessNode("node_1", "MAIN_NODE1"),
        WitnessNode("node_2", "MAIN_NODE2"),
        WitnessNode("node_3", "MAIN_NODE3"),
        WitnessNode("node_4", "MAIN_NODE4"),
    ]
    
    # 创建见证引擎
    engine = DoubleWitnessEngine(
        node_pool=nodes,
        ledger=ledger,
    )
    
    print("\n--- 测试 1: 普通转账 (双见证) ---")
    tx1 = MainTransaction(
        tx_id="",
        tx_type=TransactionType.TRANSFER,
        from_address="MAIN_ALICE",
        to_address="MAIN_BOB",
        amount=100.0,
        fee=0.1,
        timestamp=time.time(),
        signature="sig_alice_001",
    )
    engine.submit_transaction(tx1)
    print(f"交易状态: {tx1.status.value}")
    print(f"见证数: {tx1.witness_count()}/{tx1.witnesses_required}")
    
    print("\n--- 测试 2: 大额交易 (需要更多见证) ---")
    tx2 = MainTransaction(
        tx_id="",
        tx_type=TransactionType.TRANSFER,
        from_address="MAIN_ALICE",
        to_address="MAIN_BOB",
        amount=15000.0,  # 超过阈值
        fee=1.5,
        timestamp=time.time(),
        signature="sig_alice_002",
    )
    engine.submit_transaction(tx2)
    print(f"交易状态: {tx2.status.value}")
    print(f"见证数: {tx2.witness_count()}/{tx2.witnesses_required}")
    
    print("\n--- 测试 3: 余额不足 (应被拒绝) ---")
    tx3 = MainTransaction(
        tx_id="",
        tx_type=TransactionType.TRANSFER,
        from_address="MAIN_BOB",
        to_address="MAIN_ALICE",
        amount=999999.0,  # 余额不足
        fee=0.1,
        timestamp=time.time(),
        signature="sig_bob_001",
    )
    engine.submit_transaction(tx3)
    print(f"交易状态: {tx3.status.value}")
    
    print("\n--- 测试 4: 双花攻击 (应被拒绝) ---")
    ledger.record_tx("duplicate_tx")
    tx4 = MainTransaction(
        tx_id="duplicate_tx",  # 已存在的 ID
        tx_type=TransactionType.TRANSFER,
        from_address="MAIN_ALICE",
        to_address="MAIN_BOB",
        amount=50.0,
        fee=0.05,
        timestamp=time.time(),
        signature="sig_alice_003",
    )
    engine.submit_transaction(tx4)
    print(f"交易状态: {tx4.status.value}")
    
    print("\n--- 统计 ---")
    stats = engine.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n--- 见证节点收益 ---")
    for node in nodes:
        print(f"  {node.node_id}: 见证 {node.witness_count} 次, 收益 {node.earned_fees:.4f} MAIN")
    
    print("\n✅ 双见证机制测试完成")
