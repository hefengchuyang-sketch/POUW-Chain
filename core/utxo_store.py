"""
UTXO 存储模块 - 完整的未花费交易输出管理

功能：
1. UTXO 创建与消费
2. 余额计算（从 UTXO 集合）
3. 交易追溯（溯源到创世/coinbase）
4. 双花防护
5. 多板块支持

每一笔资金都可以追溯到源头（coinbase 挖矿奖励）
"""

import time
import json
import hashlib
import sqlite3
import threading
import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

from core import db
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from contextlib import contextmanager


class UTXOStatus(Enum):
    """UTXO 状态"""
    UNSPENT = "unspent"       # 未花费
    SPENT = "spent"           # 已花费
    PENDING = "pending"       # 待确认（在 mempool 中）
    LOCKED = "locked"         # 锁定（用于质押等）


@dataclass
class UTXO:
    """未花费交易输出"""
    txid: str                 # 所属交易ID
    output_index: int         # 输出索引
    address: str              # 拥有者地址
    amount: float             # 金额
    sector: str               # 板块/币种
    block_height: int         # 所在区块高度（-1 表示未确认）
    status: UTXOStatus        # 状态
    created_at: float         # 创建时间
    spent_txid: str = ""      # 花费此 UTXO 的交易ID（如果已花费）
    spent_at: float = 0       # 花费时间
    source_type: str = ""     # 来源类型：coinbase/transfer/exchange
    lock_until: float = 0     # 锁定截止时间（用于时间锁）
    script: str = ""          # 锁定脚本（可选）
    
    @property
    def utxo_id(self) -> str:
        """UTXO 唯一标识"""
        return f"{self.txid}:{self.output_index}"
    
    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "output_index": self.output_index,
            "address": self.address,
            "amount": self.amount,
            "sector": self.sector,
            "block_height": self.block_height,
            "status": self.status.value,
            "created_at": self.created_at,
            "spent_txid": self.spent_txid,
            "spent_at": self.spent_at,
            "source_type": self.source_type,
            "lock_until": self.lock_until,
            "script": self.script,
            "utxo_id": self.utxo_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UTXO':
        return cls(
            txid=data["txid"],
            output_index=data["output_index"],
            address=data["address"],
            amount=data["amount"],
            sector=data["sector"],
            block_height=data.get("block_height", -1),
            status=UTXOStatus(data.get("status", "unspent")),
            created_at=data.get("created_at", time.time()),
            spent_txid=data.get("spent_txid", ""),
            spent_at=data.get("spent_at", 0),
            source_type=data.get("source_type", ""),
            lock_until=data.get("lock_until", 0),
            script=data.get("script", ""),
        )


@dataclass
class TransactionRecord:
    """完整交易记录（用于追溯）"""
    txid: str
    tx_type: str              # coinbase/transfer/exchange
    inputs: List[Dict]        # 输入 UTXO 引用列表
    outputs: List[Dict]       # 输出列表
    from_address: str
    to_address: str
    amount: float
    fee: float
    sector: str
    block_height: int
    block_hash: str
    timestamp: float
    signature: str
    memo: str
    status: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TransactionRecord':
        return cls(**data)


class UTXOStore:
    """UTXO 存储管理器
    
    核心功能：
    - 管理所有 UTXO 的生命周期
    - 确保每笔资金可追溯
    - 防止双花
    """
    
    # Coinbase 成熟度：挖矿奖励需要 100 个区块确认后才能花费（与 consensus.ChainParams 一致）
    COINBASE_MATURITY = 100
    
    def __init__(self, db_path: str = "data/utxo.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.RLock()
        self._init_db()
    
    @contextmanager
    def _conn(self):
        """获取线程本地连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = db.connect(str(self.db_path))
        conn = self._local.conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    @contextmanager
    def _exclusive_conn(self):
        """获取排他事务连接（用于资金操作，防止并发双花）"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = db.connect(str(self.db_path))
        conn = self._local.conn
        try:
            conn.execute("BEGIN EXCLUSIVE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _init_db(self):
        """初始化数据库表"""
        with self._conn() as conn:
            # UTXO 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS utxos (
                    utxo_id TEXT PRIMARY KEY,
                    txid TEXT NOT NULL,
                    output_index INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    sector TEXT NOT NULL,
                    block_height INTEGER DEFAULT -1,
                    status TEXT DEFAULT 'unspent',
                    created_at REAL NOT NULL,
                    spent_txid TEXT DEFAULT '',
                    spent_at REAL DEFAULT 0,
                    source_type TEXT DEFAULT '',
                    lock_until REAL DEFAULT 0,
                    script TEXT DEFAULT ''
                )
            """)
            
            # 交易记录表（用于追溯）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    txid TEXT PRIMARY KEY,
                    tx_type TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    outputs TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    sector TEXT NOT NULL,
                    block_height INTEGER DEFAULT -1,
                    block_hash TEXT DEFAULT '',
                    timestamp REAL NOT NULL,
                    signature TEXT DEFAULT '',
                    memo TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_utxo_address ON utxos(address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_utxo_status ON utxos(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_utxo_sector ON utxos(sector)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_utxo_txid ON utxos(txid)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_height ON transactions(block_height)")
            
            # B-4: coinbase 唯一约束 — 每个区块每个板块只能有一个 coinbase UTXO
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_coinbase_unique
                ON utxos(block_height, sector)
                WHERE source_type = 'coinbase'
            """)
    
    # ============== UTXO 创建 ==============
    
    def create_coinbase_utxo(
        self,
        miner_address: str,
        amount: float,
        sector: str,
        block_height: int,
        block_hash: str = ""
    ) -> Tuple[str, UTXO]:
        """创建 Coinbase UTXO（挖矿奖励）
        
        这是所有资金的源头，不需要输入 UTXO
        """
        timestamp = time.time()
        
        # 生成确定性 coinbase 交易ID（同一区块+板块 → 同一 txid，保证幂等性）
        txid_data = f"coinbase:{miner_address}:{amount}:{sector}:{block_height}"
        txid = hashlib.sha256(txid_data.encode()).hexdigest()
        
        # 创建 UTXO
        utxo = UTXO(
            txid=txid,
            output_index=0,
            address=miner_address,
            amount=amount,
            sector=sector,
            block_height=block_height,
            status=UTXOStatus.UNSPENT,
            created_at=timestamp,
            source_type="coinbase"
        )
        
        # 保存 UTXO（INSERT OR IGNORE 配合唯一约束保证幂等性）
        with self._conn() as conn:
            result = conn.execute("""
                INSERT OR IGNORE INTO utxos 
                (utxo_id, txid, output_index, address, amount, sector, block_height, 
                 status, created_at, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                utxo.utxo_id, utxo.txid, utxo.output_index, utxo.address, 
                utxo.amount, utxo.sector, utxo.block_height, 
                utxo.status.value, utxo.created_at, utxo.source_type
            ))
            
            if result.rowcount == 0:
                # 唯一约束命中 — 此区块此板块已有 coinbase，跳过
                return txid, utxo
            
            # 记录交易
            conn.execute("""
                INSERT OR IGNORE INTO transactions
                (txid, tx_type, inputs, outputs, from_address, to_address, amount, 
                 fee, sector, block_height, block_hash, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                txid, "coinbase", "[]", 
                json.dumps([{"address": miner_address, "amount": amount, "sector": sector}]),
                "coinbase", miner_address, amount, 0, sector, block_height, 
                block_hash, timestamp, "confirmed"
            ))
        
        return txid, utxo
    
    def create_transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        sector: str,
        block_height: int = -1,
        block_hash: str = "",
        fee: float = 0.001,
        memo: str = "",
        signature: str = "",
        public_key: str = ""
    ) -> Dict:
        """创建转账交易
        
        1. 验证签名（如果提供了 public_key）
        2. 选择足够的 UTXO 作为输入
        3. 创建输出 UTXO（收款方 + 找零）
        4. 标记输入 UTXO 为已花费
        
        Args:
            signature: 交易签名（hex 编码）
            public_key: 发送方公钥（hex 编码），用于验证签名
        
        Returns:
            Dict with keys: success, txid, error, inputs_used, change_amount
        """
        # ===== 安全加固：签名验证（强制要求） =====
        # Signature verification is MANDATORY for all transfers.
        # Both public_key and signature must be provided.
        if not public_key or not signature:
            return {
                "success": False, 
                "error": "签名验证失败: 必须提供 public_key 和 signature / "
                         "Signature verification failed: public_key and signature are required"
            }
        
        try:
            from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
            from ecdsa.util import sigdecode_der
            vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
            tx_message = f"{from_address}{to_address}{amount}{fee}".encode()
            sig_bytes = bytes.fromhex(signature)
            vk.verify(sig_bytes, tx_message, sigdecode=sigdecode_der)
        except ImportError:
            return {"success": False, "error": "ecdsa library not installed, cannot verify signature"}
        except (BadSignatureError, ValueError, Exception) as e:
            logger.error(f"UTXO 签名验证异常: {e}")
            return {"success": False, "error": "签名验证失败 Signature verification failed"}
        
        # ===== 安全加固：验证公钥与发送地址匹配 =====
        # Verify that the provided public_key actually derives to from_address
        try:
            from .crypto import ECDSASigner
            # 尝试用所有可能的前缀派生地址
            pub_bytes = bytes.fromhex(public_key)
            derived_main = ECDSASigner.public_key_to_address(pub_bytes, "MAIN")
            # 提取地址前缀用于匹配
            addr_prefix = from_address.split('_')[0] if '_' in from_address else 'MAIN'
            derived_addr = ECDSASigner.public_key_to_address(pub_bytes, addr_prefix)
            if from_address != derived_main and from_address != derived_addr:
                return {
                    "success": False, 
                    "error": f"公钥与发送地址不匹配 / Public key does not match sender address"
                }
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"create_transfer: 公钥-地址验证异常 (non-fatal): {e}"
            )
        # 选择 UTXO
        available_utxos = self.get_spendable_utxos(from_address, sector)
        
        total_available = sum(u.amount for u in available_utxos)
        required = amount + fee
        
        if total_available < required:
            return {"success": False, "error": f"余额不足: 需要 {required} {sector}, 可用 {total_available}"}
        
        # 选择输入 UTXO（简单策略：从大到小选择）
        selected_utxos = []
        selected_total = 0.0
        for utxo in sorted(available_utxos, key=lambda u: -u.amount):
            selected_utxos.append(utxo)
            selected_total += utxo.amount
            if selected_total >= required:
                break
        
        timestamp = time.time()
        
        # 生成交易ID
        inputs_data = [{"txid": u.txid, "index": u.output_index, "amount": u.amount} for u in selected_utxos]
        txid_data = f"transfer:{from_address}:{to_address}:{amount}:{timestamp}:{json.dumps(inputs_data)}"
        txid = hashlib.sha256(txid_data.encode()).hexdigest()
        
        # 计算找零
        change = selected_total - amount - fee
        
        outputs = []
        new_utxos = []
        
        # 收款方 UTXO
        output_utxo = UTXO(
            txid=txid,
            output_index=0,
            address=to_address,
            amount=amount,
            sector=sector,
            block_height=block_height,
            status=UTXOStatus.UNSPENT if block_height >= 0 else UTXOStatus.PENDING,
            created_at=timestamp,
            source_type="transfer"
        )
        outputs.append({"address": to_address, "amount": amount, "sector": sector, "is_change": False})
        new_utxos.append(output_utxo)
        
        # 找零 UTXO
        if change > 0.00000001:
            change_utxo = UTXO(
                txid=txid,
                output_index=1,
                address=from_address,
                amount=change,
                sector=sector,
                block_height=block_height,
                status=UTXOStatus.UNSPENT if block_height >= 0 else UTXOStatus.PENDING,
                created_at=timestamp,
                source_type="transfer"
            )
            outputs.append({"address": from_address, "amount": change, "sector": sector, "is_change": True})
            new_utxos.append(change_utxo)
        
        # 原子操作：消费旧 UTXO，创建新 UTXO（排他事务防并发双花）
        with self._exclusive_conn() as conn:
            # 标记输入 UTXO 为已花费，并检查影响行数
            for utxo in selected_utxos:
                cursor = conn.execute("""
                    UPDATE utxos SET status = 'spent', spent_txid = ?, spent_at = ?
                    WHERE utxo_id = ? AND status = 'unspent'
                """, (txid, timestamp, utxo.utxo_id))
                if cursor.rowcount == 0:
                    raise ValueError(f"UTXO {utxo.utxo_id} 已被花费或不存在（双花防护触发）")
            
            # 创建新 UTXO
            for new_utxo in new_utxos:
                conn.execute("""
                    INSERT INTO utxos 
                    (utxo_id, txid, output_index, address, amount, sector, block_height, 
                     status, created_at, source_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_utxo.utxo_id, new_utxo.txid, new_utxo.output_index, 
                    new_utxo.address, new_utxo.amount, new_utxo.sector, 
                    new_utxo.block_height, new_utxo.status.value, 
                    new_utxo.created_at, new_utxo.source_type
                ))
            
            # 记录交易
            conn.execute("""
                INSERT INTO transactions
                (txid, tx_type, inputs, outputs, from_address, to_address, amount, 
                 fee, sector, block_height, block_hash, timestamp, memo, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                txid, "transfer", json.dumps(inputs_data), json.dumps(outputs),
                from_address, to_address, amount, fee, sector, block_height,
                block_hash, timestamp, memo, 
                "confirmed" if block_height >= 0 else "pending"
            ))
        
        return {
            "success": True,
            "txid": txid,
            "inputs_used": len(selected_utxos),
            "inputs": inputs_data,
            "change_amount": change,
            "fee": fee,
            "message": f"转账成功"
        }
    
    def replay_transfer_from_block(self, tx: Dict, block_height: int, block_hash: str = "") -> bool:
        """重放已确认区块中的转账交易到 UTXO 状态。
        
        与 create_transfer 的区别：
        - 不重新验证签名（区块已通过共识验证）
        - 幂等：如果交易已存在则跳过
        - 用于 P2P 收到区块后同步 UTXO 状态
        """
        txid = tx.get('tx_id', tx.get('txid', ''))
        tx_type = tx.get('tx_type', 'transfer')
        if tx_type == 'coinbase' or not txid:
            return False
        
        from_addr = tx.get('from', tx.get('from_address', ''))
        to_addr = tx.get('to', tx.get('to_address', ''))
        amount = tx.get('amount', 0)
        fee = tx.get('fee', 0)
        sector = tx.get('sector', 'MAIN')
        
        if not from_addr or not to_addr or amount <= 0:
            return False
        
        # 幂等检查：交易已存在则跳过
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT 1 FROM transactions WHERE txid = ?", (txid,)
            ).fetchone()
            if existing:
                return True  # 已处理过
        
        # 优先使用原始交易中记录的 inputs（保证所有节点消费相同 UTXO）
        original_inputs = tx.get('inputs', [])
        timestamp = tx.get('timestamp', time.time())
        
        if original_inputs:
            # 使用原始交易指定的 UTXO inputs
            selected_ids = []
            selected_total = 0.0
            for inp in original_inputs:
                inp_txid = inp.get('txid', '')
                inp_index = inp.get('index', 0)
                inp_amount = float(inp.get('amount', 0))
                utxo_id = f"{inp_txid}:{inp_index}"
                selected_ids.append((utxo_id, inp_amount))
                selected_total += inp_amount
            
            change = selected_total - amount - fee
            
            # 收款方 UTXO
            recv_utxo = UTXO(
                txid=txid, output_index=0, address=to_addr,
                amount=amount, sector=sector, block_height=block_height,
                status=UTXOStatus.UNSPENT, created_at=timestamp, source_type="transfer"
            )
            
            with self._exclusive_conn() as conn:
                # 幂等二次检查（持锁）
                if conn.execute("SELECT 1 FROM transactions WHERE txid = ?", (txid,)).fetchone():
                    return True
                
                for utxo_id, _ in selected_ids:
                    cursor = conn.execute("""
                        UPDATE utxos SET status = 'spent', spent_txid = ?, spent_at = ?
                        WHERE utxo_id = ? AND status = 'unspent'
                    """, (txid, timestamp, utxo_id))
                    if cursor.rowcount == 0:
                        logger.debug(f"重放 UTXO 冲突: {utxo_id}")
                        return False
                
                conn.execute("""
                    INSERT INTO utxos 
                    (utxo_id, txid, output_index, address, amount, sector, block_height,
                     status, created_at, source_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (recv_utxo.utxo_id, recv_utxo.txid, recv_utxo.output_index,
                      recv_utxo.address, recv_utxo.amount, recv_utxo.sector,
                      recv_utxo.block_height, recv_utxo.status.value,
                      recv_utxo.created_at, recv_utxo.source_type))
                
                if change > 0.00000001:
                    change_utxo = UTXO(
                        txid=txid, output_index=1, address=from_addr,
                        amount=change, sector=sector, block_height=block_height,
                        status=UTXOStatus.UNSPENT, created_at=timestamp, source_type="transfer"
                    )
                    conn.execute("""
                        INSERT INTO utxos 
                        (utxo_id, txid, output_index, address, amount, sector, block_height,
                         status, created_at, source_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (change_utxo.utxo_id, change_utxo.txid, change_utxo.output_index,
                          change_utxo.address, change_utxo.amount, change_utxo.sector,
                          change_utxo.block_height, change_utxo.status.value,
                          change_utxo.created_at, change_utxo.source_type))
                
                inputs_json = json.dumps(original_inputs)
                conn.execute("""
                    INSERT INTO transactions
                    (txid, tx_type, inputs, outputs, from_address, to_address, amount,
                     fee, sector, block_height, block_hash, timestamp, memo, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (txid, tx_type, inputs_json, json.dumps([]),
                      from_addr, to_addr, amount, fee, sector, block_height,
                      block_hash, timestamp, tx.get('memo', ''), "confirmed"))
            
            return True
        
        # 回退路径：无原始 inputs 时重新选择（兼容旧区块数据）
        logger.warning(f"重放 {txid[:12]}: 无原始inputs，回退到重新选择UTXO（可能导致状态差异）")
        available_utxos = self.get_spendable_utxos(from_addr, sector)
        total_available = sum(u.amount for u in available_utxos)
        required = amount + fee
        
        if total_available < required:
            logger.debug(f"重放跳过 {txid[:12]}: 余额不足 (需要 {required}, 可用 {total_available})")
            return False
        
        selected = []
        selected_total = 0.0
        for utxo in sorted(available_utxos, key=lambda u: -u.amount):
            selected.append(utxo)
            selected_total += utxo.amount
            if selected_total >= required:
                break
        
        change = selected_total - amount - fee
        timestamp = tx.get('timestamp', time.time())
        
        # 收款方 UTXO
        recv_utxo = UTXO(
            txid=txid, output_index=0, address=to_addr,
            amount=amount, sector=sector, block_height=block_height,
            status=UTXOStatus.UNSPENT, created_at=timestamp, source_type="transfer"
        )
        
        with self._exclusive_conn() as conn:
            # 幂等二次检查（持锁）
            if conn.execute("SELECT 1 FROM transactions WHERE txid = ?", (txid,)).fetchone():
                return True
            
            for utxo in selected:
                cursor = conn.execute("""
                    UPDATE utxos SET status = 'spent', spent_txid = ?, spent_at = ?
                    WHERE utxo_id = ? AND status = 'unspent'
                """, (txid, timestamp, utxo.utxo_id))
                if cursor.rowcount == 0:
                    logger.debug(f"重放 UTXO 冲突: {utxo.utxo_id}")
                    return False
            
            # 创建收款方 UTXO
            conn.execute("""
                INSERT INTO utxos 
                (utxo_id, txid, output_index, address, amount, sector, block_height,
                 status, created_at, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (recv_utxo.utxo_id, recv_utxo.txid, recv_utxo.output_index,
                  recv_utxo.address, recv_utxo.amount, recv_utxo.sector,
                  recv_utxo.block_height, recv_utxo.status.value,
                  recv_utxo.created_at, recv_utxo.source_type))
            
            # 找零 UTXO
            if change > 0.00000001:
                change_utxo = UTXO(
                    txid=txid, output_index=1, address=from_addr,
                    amount=change, sector=sector, block_height=block_height,
                    status=UTXOStatus.UNSPENT, created_at=timestamp, source_type="transfer"
                )
                conn.execute("""
                    INSERT INTO utxos 
                    (utxo_id, txid, output_index, address, amount, sector, block_height,
                     status, created_at, source_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (change_utxo.utxo_id, change_utxo.txid, change_utxo.output_index,
                      change_utxo.address, change_utxo.amount, change_utxo.sector,
                      change_utxo.block_height, change_utxo.status.value,
                      change_utxo.created_at, change_utxo.source_type))
            
            # 记录交易
            inputs_data = [{"txid": u.txid, "index": u.output_index, "amount": u.amount} for u in selected]
            conn.execute("""
                INSERT INTO transactions
                (txid, tx_type, inputs, outputs, from_address, to_address, amount,
                 fee, sector, block_height, block_hash, timestamp, memo, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (txid, tx_type, json.dumps(inputs_data), json.dumps([]),
                  from_addr, to_addr, amount, fee, sector, block_height,
                  block_hash, timestamp, tx.get('memo', ''), "confirmed"))
        
        return True
    
    # ============== UTXO 查询 ==============
    
    def get_utxo(self, txid: str, output_index: int) -> Optional[UTXO]:
        """获取指定 UTXO"""
        utxo_id = f"{txid}:{output_index}"
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM utxos WHERE utxo_id = ?", (utxo_id,)
            ).fetchone()
            if row:
                return UTXO.from_dict(dict(row))
        return None
    
    def get_utxos_by_address(
        self, 
        address: str, 
        sector: str = None,
        include_spent: bool = False
    ) -> List[UTXO]:
        """获取地址的所有 UTXO"""
        with self._conn() as conn:
            if sector:
                if include_spent:
                    rows = conn.execute(
                        "SELECT * FROM utxos WHERE address = ? AND sector = ? ORDER BY created_at DESC",
                        (address, sector)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM utxos WHERE address = ? AND sector = ? AND status = 'unspent' ORDER BY created_at DESC",
                        (address, sector)
                    ).fetchall()
            else:
                if include_spent:
                    rows = conn.execute(
                        "SELECT * FROM utxos WHERE address = ? ORDER BY created_at DESC",
                        (address,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM utxos WHERE address = ? AND status = 'unspent' ORDER BY created_at DESC",
                        (address,)
                    ).fetchall()
            
            return [UTXO.from_dict(dict(row)) for row in rows]
    
    def get_spendable_utxos(self, address: str, sector: str = None) -> List[UTXO]:
        """获取可花费的 UTXO（未花费且未锁定）"""
        now = time.time()
        with self._conn() as conn:
            if sector:
                rows = conn.execute("""
                    SELECT * FROM utxos 
                    WHERE address = ? AND sector = ? 
                    AND status = 'unspent' AND (lock_until = 0 OR lock_until < ?)
                    ORDER BY amount DESC
                """, (address, sector, now)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM utxos 
                    WHERE address = ? 
                    AND status = 'unspent' AND (lock_until = 0 OR lock_until < ?)
                    ORDER BY amount DESC
                """, (address, now)).fetchall()
            
            # 获取当前链高度，用于 coinbase 成熟度检查
            height_row = conn.execute(
                "SELECT MAX(block_height) FROM utxos"
            ).fetchone()
            current_height = (height_row[0] or 0) if height_row else 0
            
            result = []
            for row in rows:
                utxo = UTXO.from_dict(dict(row))
                # coinbase UTXO 需要 COINBASE_MATURITY 个确认才能花费
                if utxo.source_type == 'coinbase':
                    confirmations = current_height - utxo.block_height
                    if confirmations < self.COINBASE_MATURITY:
                        continue
                result.append(utxo)
            return result
    
    def get_balance(self, address: str, sector: str = None) -> float:
        """计算地址余额（从 UTXO 计算，仅可用余额）"""
        utxos = self.get_spendable_utxos(address, sector)
        return sum(u.amount for u in utxos)
    
    def get_total_balance(self, address: str, sector: str = None) -> float:
        """计算地址总余额（包括待成熟的coinbase UTXO）"""
        with self._conn() as conn:
            if sector:
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM utxos WHERE address = ? AND sector = ? AND status = 'unspent'",
                    (address, sector)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM utxos WHERE address = ? AND status = 'unspent'",
                    (address,)
                ).fetchone()
            return float(row[0]) if row else 0.0
    
    def get_all_balances(self, address: str) -> Dict[str, float]:
        """获取地址所有币种余额（仅可花费的，排除未成熟 coinbase）"""
        utxos = self.get_spendable_utxos(address)
        balances = {}
        for utxo in utxos:
            balances[utxo.sector] = balances.get(utxo.sector, 0) + utxo.amount
        return balances

    def get_all_total_balances(self, address: str) -> Dict[str, float]:
        """获取地址所有币种总余额（含未成熟 coinbase）"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT sector, COALESCE(SUM(amount), 0) as total FROM utxos "
                "WHERE address = ? AND status = 'unspent' GROUP BY sector",
                (address,)
            ).fetchall()
            return {row['sector']: float(row['total']) for row in rows}
    
    # ============== 交易追溯 ==============
    
    def get_transaction(self, txid: str) -> Optional[TransactionRecord]:
        """获取交易记录"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM transactions WHERE txid = ?", (txid,)
            ).fetchone()
            if row:
                data = dict(row)
                data['inputs'] = json.loads(data['inputs'])
                data['outputs'] = json.loads(data['outputs'])
                return TransactionRecord.from_dict(data)
        return None
    
    def trace_utxo_origin(self, txid: str, output_index: int) -> List[Dict]:
        """追溯 UTXO 的来源链，直到 coinbase
        
        返回完整的资金流转路径
        """
        trace = []
        current_txid = txid
        current_index = output_index
        
        max_depth = 1000  # 防止无限循环
        
        while current_txid and max_depth > 0:
            max_depth -= 1
            
            tx = self.get_transaction(current_txid)
            if not tx:
                break
            
            trace.append({
                "txid": tx.txid,
                "tx_type": tx.tx_type,
                "from": tx.from_address,
                "to": tx.to_address,
                "amount": tx.amount,
                "sector": tx.sector,
                "block_height": tx.block_height,
                "timestamp": tx.timestamp,
            })
            
            # 如果是 coinbase，追溯结束
            if tx.tx_type == "coinbase":
                break
            
            # 继续追溯第一个输入
            if tx.inputs and len(tx.inputs) > 0:
                first_input = tx.inputs[0]
                current_txid = first_input.get('txid', '')
                current_index = first_input.get('index', 0)
            else:
                break
        
        return trace
    
    def get_transaction_history(
        self, 
        address: str, 
        limit: int = 50,
        offset: int = 0
    ) -> List[TransactionRecord]:
        """获取地址的交易历史"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM transactions 
                WHERE from_address = ? OR to_address = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (address, address, limit, offset)).fetchall()
            
            result = []
            for row in rows:
                data = dict(row)
                data['inputs'] = json.loads(data['inputs'])
                data['outputs'] = json.loads(data['outputs'])
                result.append(TransactionRecord.from_dict(data))
            
            return result
    
    # ============== 兑换交易 ==============
    
    def create_exchange_transaction(
        self,
        address: str,
        from_sector: str,
        from_amount: float,
        to_sector: str,
        to_amount: float,
        exchange_id: str,
        witness_sectors: list,
        block_height: int = -1,
        block_hash: str = ""
    ) -> Dict:
        """创建板块币兑换交易（双见证完成后调用）
        
        安全验证 / Security checks:
        1. 验证 exchange_id 对应的兑换请求确实存在且已完成
        2. 验证请求者地址、金额与兑换请求一致
        3. 验证见证板块信息匹配
        4. 消费源板块的 UTXO（销毁）
        5. 创建目标板块的 UTXO（铸造）
        6. 记录带有见证信息的交易
        
        Returns:
            Dict with keys: success, txid, error
        """
        # ===== 安全加固：验证兑换请求合法性 =====
        # Security: verify the exchange was actually completed through dual-witness
        if not exchange_id or len(exchange_id) < 8:
            return {"success": False, "error": "无效的兑换ID / Invalid exchange_id"}
        
        if not witness_sectors or len(witness_sectors) < 2:
            return {"success": False, "error": "见证板块不足，至少需要2个 / Insufficient witnesses, need >= 2"}
        
        try:
            from core.dual_witness_exchange import get_exchange_service, ExchangeStatus
            exchange_svc = get_exchange_service()
            exchange_req = exchange_svc.get_exchange_request(exchange_id)
            
            if not exchange_req:
                return {"success": False, "error": f"兑换请求不存在: {exchange_id} / Exchange request not found"}
            
            if exchange_req.status != ExchangeStatus.COMPLETED:
                return {"success": False, "error": f"兑换未完成，状态: {exchange_req.status.value} / Exchange not completed"}
            
            # 验证请求者地址
            if exchange_req.requester_address != address:
                return {"success": False, "error": "地址与兑换请求不匹配 / Address mismatch"}
            
            # 验证金额一致
            if abs(exchange_req.source_amount - from_amount) > 0.00000001:
                return {"success": False, "error": f"源金额不匹配: 请求={exchange_req.source_amount}, 提交={from_amount} / Source amount mismatch"}
            
            if abs(exchange_req.target_main_amount - to_amount) > 0.00000001:
                return {"success": False, "error": f"目标金额不匹配: 请求={exchange_req.target_main_amount}, 提交={to_amount} / Target amount mismatch"}
            
            # 验证见证板块匹配
            if set(exchange_req.witness_sectors) != set(witness_sectors):
                return {"success": False, "error": "见证板块不匹配 / Witness sectors mismatch"}
            
            # 验证见证数量达标
            if len(exchange_req.witnesses) < exchange_req.required_witnesses:
                return {"success": False, "error": f"见证不足: {len(exchange_req.witnesses)}/{exchange_req.required_witnesses} / Insufficient witnesses"}
                
        except ImportError:
            return {"success": False, "error": "兑换服务不可用 / Exchange service unavailable"}
        except Exception as e:
            logger.error(f"UTXO 兑换验证异常: {e}")
            return {"success": False, "error": "兑换验证失败 / Exchange verification failed"}
        
        timestamp = time.time()
        
        # 生成交易ID
        txid_data = f"exchange:{address}:{from_sector}:{from_amount}:{to_sector}:{to_amount}:{exchange_id}:{timestamp}"
        txid = hashlib.sha256(txid_data.encode()).hexdigest()
        
        # 选择并消费源板块的 UTXO（真正销毁）
        source_utxos = self.get_spendable_utxos(address, from_sector)
        source_total = sum(u.amount for u in source_utxos)
        if source_total < from_amount:
            return {
                "success": False,
                "error": f"源板块余额不足: 需要 {from_amount} {from_sector}, 可用 {source_total}"
            }
        
        # 选择输入 UTXO
        selected_source = []
        selected_total = 0.0
        for utxo in sorted(source_utxos, key=lambda u: -u.amount):
            selected_source.append(utxo)
            selected_total += utxo.amount
            if selected_total >= from_amount:
                break
        
        # 构造输入
        inputs_data = [{
            "txid": u.txid,
            "index": u.output_index,
            "amount": u.amount,
            "sector": from_sector,
            "type": "burn",
        } for u in selected_source]
        inputs_data.append({
            "exchange_id": exchange_id,
            "verified_witnesses": [w.witness_sector for w in exchange_req.witnesses]
        })
        
        # 创建输出 UTXO（铸造的 MAIN）
        cur_height = block_height if block_height >= 0 else self._get_current_height()
        output_utxo = UTXO(
            txid=txid,
            output_index=0,
            address=address,
            amount=to_amount,
            sector=to_sector,
            block_height=cur_height,
            status=UTXOStatus.UNSPENT,
            created_at=timestamp,
            source_type="exchange"
        )
        
        outputs = [{
            "address": address,
            "amount": to_amount,
            "sector": to_sector,
            "is_mint": True
        }]
        
        # 找零（源板块币）
        source_change = selected_total - from_amount
        if source_change > 0.00000001:
            change_utxo = UTXO(
                txid=txid,
                output_index=1,
                address=address,
                amount=source_change,
                sector=from_sector,
                block_height=cur_height,
                status=UTXOStatus.UNSPENT,
                created_at=timestamp,
                source_type="exchange_change"
            )
            outputs.append({
                "address": address,
                "amount": source_change,
                "sector": from_sector,
                "is_change": True,
            })
        
        # 原子操作：消费源 UTXO + 创建新 UTXO（排他事务）
        with self._exclusive_conn() as conn:
            # 标记源板块 UTXO 为已花费（销毁）
            for utxo in selected_source:
                cursor = conn.execute("""
                    UPDATE utxos SET status = 'spent', spent_txid = ?, spent_at = ?
                    WHERE utxo_id = ? AND status = 'unspent'
                """, (txid, timestamp, utxo.utxo_id))
                if cursor.rowcount == 0:
                    raise ValueError(f"UTXO {utxo.utxo_id} 已被花费（兑换双花防护触发）")
            
            # 创建新 MAIN UTXO
            conn.execute("""
                INSERT INTO utxos 
                (utxo_id, txid, output_index, address, amount, sector, block_height, 
                 status, created_at, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                output_utxo.utxo_id, output_utxo.txid, output_utxo.output_index, 
                output_utxo.address, output_utxo.amount, output_utxo.sector, 
                output_utxo.block_height, output_utxo.status.value, 
                output_utxo.created_at, output_utxo.source_type
            ))
            
            # 找零 UTXO
            if source_change > 0.00000001:
                conn.execute("""
                    INSERT INTO utxos 
                    (utxo_id, txid, output_index, address, amount, sector, block_height, 
                     status, created_at, source_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    change_utxo.utxo_id, change_utxo.txid, change_utxo.output_index, 
                    change_utxo.address, change_utxo.amount, change_utxo.sector, 
                    change_utxo.block_height, change_utxo.status.value, 
                    change_utxo.created_at, change_utxo.source_type
                ))
            
            # 记录交易（带见证信息）
            memo = f"双见证兑换 {from_amount} {from_sector}_COIN → {to_amount} MAIN, 见证板块: {','.join(witness_sectors)}"
            conn.execute("""
                INSERT INTO transactions
                (txid, tx_type, inputs, outputs, from_address, to_address, amount, 
                 fee, sector, block_height, block_hash, timestamp, memo, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                txid, "exchange", json.dumps(inputs_data), json.dumps(outputs),
                f"{from_sector}_POOL", address, to_amount, 0, 
                f"{from_sector}->MAIN", 
                cur_height,
                block_hash or exchange_id, timestamp, memo, "confirmed"
            ))
        
        return {
            "success": True,
            "txid": txid,
            "from_sector": from_sector,
            "from_amount": from_amount,
            "to_sector": to_sector,
            "to_amount": to_amount,
            "message": f"兑换交易已记录到区块链"
        }
    
    def _get_current_height(self) -> int:
        """获取当前最高区块高度"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(block_height) FROM transactions"
            ).fetchone()
            return (row[0] or 0) + 1
    
    # ============== 确认管理 ==============
    
    def confirm_transaction(self, txid: str, block_height: int, block_hash: str):
        """确认交易（写入区块后调用）"""
        with self._conn() as conn:
            # 更新交易状态
            conn.execute("""
                UPDATE transactions 
                SET status = 'confirmed', block_height = ?, block_hash = ?
                WHERE txid = ?
            """, (block_height, block_hash, txid))
            
            # 更新相关 UTXO
            conn.execute("""
                UPDATE utxos 
                SET status = 'unspent', block_height = ?
                WHERE txid = ? AND status = 'pending'
            """, (block_height, txid))
    
    # ============== 统计 ==============
    
    def get_stats(self) -> Dict:
        """获取 UTXO 统计"""
        with self._conn() as conn:
            unspent_count = conn.execute(
                "SELECT COUNT(*) FROM utxos WHERE status = 'unspent'"
            ).fetchone()[0]
            
            spent_count = conn.execute(
                "SELECT COUNT(*) FROM utxos WHERE status = 'spent'"
            ).fetchone()[0]
            
            total_unspent = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM utxos WHERE status = 'unspent'"
            ).fetchone()[0]
            
            tx_count = conn.execute(
                "SELECT COUNT(*) FROM transactions"
            ).fetchone()[0]
            
            coinbase_count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE tx_type = 'coinbase'"
            ).fetchone()[0]
            
            return {
                "unspent_count": unspent_count,
                "spent_count": spent_count,
                "total_unspent_value": total_unspent,
                "transaction_count": tx_count,
                "coinbase_count": coinbase_count,
            }
    
    def rollback_to_height(self, height: int) -> int:
        """回滚 UTXO 状态到指定高度（含），删除 height 之后的交易和 UTXO。
        
        用于链重组(reorg)时保持 UTXO 状态与区块链一致。
        
        步骤：
        1. 恢复被 > height 交易花费的 UTXO 为 unspent
        2. 删除 block_height > height 的所有 UTXO
        3. 删除 block_height > height 的所有交易记录
        
        Returns:
            被回滚的记录数。
        """
        with self._lock:
            with self._exclusive_conn() as conn:
                # Step 1: 找出 > height 的交易，从 transactions 表的 inputs JSON 中
                # 提取被花费的 UTXO（transactions 表用 JSON 存储 inputs/outputs）
                high_txs = conn.execute(
                    "SELECT txid, inputs FROM transactions WHERE block_height > ?",
                    (height,)
                ).fetchall()
                
                # Step 2: 恢复被花费的 UTXO 状态
                restored = 0
                for row in high_txs:
                    inputs_json = row[1] if isinstance(row, (tuple, list)) else row['inputs']
                    try:
                        import json
                        inputs = json.loads(inputs_json) if isinstance(inputs_json, str) else inputs_json
                        if isinstance(inputs, list):
                            for inp in inputs:
                                # 正确构造 utxo_id: txid:output_index
                                inp_txid = inp.get('txid', '')
                                inp_index = inp.get('index', 0)
                                utxo_id = inp.get('utxo_id') or f"{inp_txid}:{inp_index}"
                                if utxo_id:
                                    conn.execute("""
                                        UPDATE utxos SET status = 'unspent', spent_txid = ''
                                        WHERE utxo_id = ? AND status = 'spent'
                                    """, (utxo_id,))
                                    restored += 1
                    except Exception:
                        pass  # inputs 格式不是 JSON 列表，跳过
                
                # Step 3: 删除 > height 产生的 UTXO（包括 coinbase 和交易输出）
                deleted_utxos = conn.execute(
                    "SELECT COUNT(*) FROM utxos WHERE block_height > ?", (height,)
                ).fetchone()[0]
                conn.execute("DELETE FROM utxos WHERE block_height > ?", (height,))
                
                # Step 4: 删除 > height 的交易记录
                deleted_txs = conn.execute(
                    "SELECT COUNT(*) FROM transactions WHERE block_height > ?", (height,)
                ).fetchone()[0]
                conn.execute("DELETE FROM transactions WHERE block_height > ?", (height,))
                
                return deleted_utxos + deleted_txs


# ============== 全局实例 ==============

_utxo_store: Optional[UTXOStore] = None


def get_utxo_store(db_path: str = "data/utxo.db") -> UTXOStore:
    """获取全局 UTXO 存储实例"""
    global _utxo_store
    if _utxo_store is None:
        _utxo_store = UTXOStore(db_path)
    return _utxo_store


# ============== 测试 ==============

if __name__ == "__main__":
    import os
    
    # 测试文件
    test_db = "data/test_utxo.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    store = UTXOStore(test_db)
    
    # 1. 创建 coinbase（挖矿奖励）
    print("=== 1. 创建挖矿奖励 ===")
    txid1, utxo1 = store.create_coinbase_utxo(
        miner_address="addr_miner_001",
        amount=50.0,
        sector="H100",
        block_height=1
    )
    print(f"Coinbase UTXO: {utxo1.utxo_id}, 金额: {utxo1.amount} {utxo1.sector}")
    
    # 2. 查询余额
    print("\n=== 2. 查询余额 ===")
    balance = store.get_balance("addr_miner_001", "H100")
    print(f"矿工余额: {balance} H100")
    
    # 3. 转账
    print("\n=== 3. 转账 ===")
    success, msg, txid2 = store.create_transfer(
        from_address="addr_miner_001",
        to_address="addr_user_001",
        amount=10.0,
        sector="H100",
        block_height=2,
        fee=0.01
    )
    print(f"转账结果: {success}, {msg}")
    
    # 4. 查询转账后余额
    print("\n=== 4. 查询转账后余额 ===")
    miner_balance = store.get_balance("addr_miner_001", "H100")
    user_balance = store.get_balance("addr_user_001", "H100")
    print(f"矿工余额: {miner_balance} H100")
    print(f"用户余额: {user_balance} H100")
    
    # 5. 查询 UTXO
    print("\n=== 5. 查询用户 UTXO ===")
    user_utxos = store.get_utxos_by_address("addr_user_001")
    for utxo in user_utxos:
        print(f"  {utxo.utxo_id}: {utxo.amount} {utxo.sector} ({utxo.source_type})")
    
    # 6. 追溯资金来源
    print("\n=== 6. 追溯资金来源 ===")
    if user_utxos:
        trace = store.trace_utxo_origin(user_utxos[0].txid, user_utxos[0].output_index)
        print(f"资金追溯链 (共 {len(trace)} 笔交易):")
        for i, tx in enumerate(trace):
            print(f"  {i+1}. [{tx['tx_type']}] {tx['from'][:15]}... -> {tx['to'][:15]}... : {tx['amount']} {tx['sector']}")
    
    # 7. 统计
    print("\n=== 7. UTXO 统计 ===")
    stats = store.get_stats()
    print(f"未花费 UTXO: {stats['unspent_count']}")
    print(f"已花费 UTXO: {stats['spent_count']}")
    print(f"总交易数: {stats['transaction_count']}")
    print(f"Coinbase 数: {stats['coinbase_count']}")
    
    # 清理
    os.remove(test_db)
    print("\n✅ 测试完成")
