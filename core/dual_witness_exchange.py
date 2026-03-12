# -*- coding: utf-8 -*-
"""
板块币 → MAIN 双见证兑换系统

设计约束:
- DR-5: MAIN 交易必须多板块承载
- DR-6: 双见证生效规则 - MAIN 交易需至少两个不同板块完成见证
- DR-9: 板块币 → MAIN 是受控兑换（销毁板块币 + 铸造 MAIN）
- DR-10: MAIN → 板块币为受限行为

兑换流程:
1. 用户请求兑换 X 板块币 → MAIN
2. 系统锁定用户的板块币
3. 系统选择 ≥2 个其他板块进行见证
4. 各见证板块在各自区块中记录见证信息
5. 双见证达成 → 销毁板块币 + 铸造 MAIN
6. 见证失败 → 解锁板块币，兑换取消
"""

import sqlite3
import time
import json
import hashlib
import threading
import logging

logger = logging.getLogger(__name__)
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Set
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

from core.sector_coin import SectorCoinType, SectorCoinLedger, get_sector_ledger


class ExchangeStatus(Enum):
    """兑换状态"""
    PENDING = "PENDING"          # 待见证
    WITNESSING = "WITNESSING"    # 见证中
    COMPLETED = "COMPLETED"      # 已完成
    FAILED = "FAILED"            # 失败
    CANCELLED = "CANCELLED"      # 已取消


@dataclass
class WitnessRecord:
    """见证记录"""
    witness_sector: str          # 见证板块
    witness_block_height: int    # 见证区块高度
    witness_block_hash: str      # 见证区块哈希
    witness_time: float          # 见证时间
    witness_signature: str       # 见证签名（板块验证者签名）


@dataclass
class ExchangeRequest:
    """兑换请求"""
    exchange_id: str
    requester_address: str       # 请求者地址
    source_sector: str           # 源板块
    source_coin_type: SectorCoinType
    source_amount: float         # 源板块币数量
    target_main_amount: float    # 目标 MAIN 数量
    exchange_rate: float         # 兑换比例
    
    status: ExchangeStatus = ExchangeStatus.PENDING
    created_at: float = 0.0
    completed_at: Optional[float] = None
    
    # 见证信息
    required_witnesses: int = 2  # 需要的见证数
    witness_sectors: List[str] = field(default_factory=list)  # 选中的见证板块
    witnesses: List[WitnessRecord] = field(default_factory=list)  # 已完成的见证
    
    def to_dict(self) -> Dict:
        return {
            "exchange_id": self.exchange_id,
            "requester_address": self.requester_address,
            "source_sector": self.source_sector,
            "source_coin_type": self.source_coin_type.value,
            "source_amount": self.source_amount,
            "target_main_amount": self.target_main_amount,
            "exchange_rate": self.exchange_rate,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "required_witnesses": self.required_witnesses,
            "witness_sectors": self.witness_sectors,
            "witnesses": [
                {
                    "witness_sector": w.witness_sector,
                    "witness_block_height": w.witness_block_height,
                    "witness_block_hash": w.witness_block_hash,
                    "witness_time": w.witness_time,
                }
                for w in self.witnesses
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ExchangeRequest":
        witnesses = [
            WitnessRecord(
                witness_sector=w['witness_sector'],
                witness_block_height=w['witness_block_height'],
                witness_block_hash=w['witness_block_hash'],
                witness_time=w['witness_time'],
                witness_signature=""
            )
            for w in data.get('witnesses', [])
        ]
        return cls(
            exchange_id=data['exchange_id'],
            requester_address=data['requester_address'],
            source_sector=data['source_sector'],
            source_coin_type=SectorCoinType(data['source_coin_type']),
            source_amount=data['source_amount'],
            target_main_amount=data['target_main_amount'],
            exchange_rate=data['exchange_rate'],
            status=ExchangeStatus(data['status']),
            created_at=data['created_at'],
            completed_at=data.get('completed_at'),
            required_witnesses=data.get('required_witnesses', 2),
            witness_sectors=data.get('witness_sectors', []),
            witnesses=witnesses
        )


class DualWitnessExchange:
    """
    双见证兑换系统
    
    核心规则:
    1. 板块币 → MAIN 必须经过双见证（主网）
    2. 见证板块必须与源板块不同
    3. 见证信息写入各见证板块的区块中
    4. 只有见证达成，MAIN 才会被铸造
    
    测试网模式:
    - required_witnesses=1: 单见证即可完成兑换（便于单节点测试）
    """
    
    # 所有可见证板块（初始内置，运行时从板块注册表动态获取）
    _INITIAL_WITNESS_SECTORS = ["H100", "RTX4090", "RTX3080", "CPU", "GENERAL"]
    
    # 兑换超时时间（秒）
    EXCHANGE_TIMEOUT = 3600 * 24  # 24 小时
    
    # 基础兑换比例（板块币 → MAIN）
    # 这个比例可以根据治理参数动态调整
    # 初始内置值；运行时通过 get_exchange_rate() 从 registry 获取
    _INITIAL_EXCHANGE_RATES: Dict[str, float] = {
        "H100": 0.5,        # 10 H100_COIN → 5 MAIN
        "RTX4090": 0.5,     # 5 RTX4090_COIN → 2.5 MAIN
        "RTX3080": 0.5,     # 2.5 RTX3080_COIN → 1.25 MAIN
        "CPU": 0.5,         # 1 CPU_COIN → 0.5 MAIN
        "GENERAL": 0.5,     # 1 GENERAL_COIN → 0.5 MAIN
    }
    
    @property
    def WITNESS_SECTORS(self) -> list:
        """动态获取活跃板块列表（兼容旧代码对 self.WITNESS_SECTORS 的引用）"""
        try:
            from core.sector_coin import get_sector_registry
            return get_sector_registry().get_active_sectors()
        except Exception:
            return list(self._INITIAL_WITNESS_SECTORS)
    
    @property
    def BASE_EXCHANGE_RATES(self) -> Dict[str, float]:
        """动态获取各板块兑换比率（兼容旧代码引用）"""
        try:
            from core.sector_coin import get_sector_registry
            registry = get_sector_registry()
            rates = {}
            for sector in registry.get_active_sectors():
                rates[sector] = registry.get_exchange_rate(sector)
            return rates
        except Exception:
            return dict(self._INITIAL_EXCHANGE_RATES)
    
    # === MAIN Supply Cap: Maximum total MAIN that can ever be minted ===
    MAIN_MAX_SUPPLY: float = 100_000_000.0  # 100 million MAIN
    
    def __init__(self, db_path: str = "data/exchange.db", testnet: bool = False,
                 dynamic_rate_engine=None):
        self.db_path = db_path
        self.testnet = testnet
        self.required_witnesses = 1 if testnet else 2  # 测试网单见证，主网双见证
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        
        # [H-06] 动态汇率引擎（可选）
        # 若注入 DynamicExchangeRate 实例，则 get_exchange_rate() 优先使用动态汇率
        self.dynamic_rate_engine = dynamic_rate_engine
        
        # 板块币账本
        self.sector_ledger = get_sector_ledger()
        
        # MAIN 余额（简化实现，实际应该有独立的 MAIN 账本）
        self._main_balances: Dict[str, float] = {}
        
        # D-04 fix: 见证板块公钥注册表
        # 生产环境应从配置文件或链上治理加载真实公钥
        self._witness_pubkeys: Dict[str, str] = {}  # sector -> public_key_hex
        self._init_witness_keys()
    
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_witness_keys(self):
        """S-1 fix: 从外部配置文件加载见证板块密钥，而非硬编码种子。
        
        优先级：
        1. 环境变量 WITNESS_KEYS_FILE 指定的文件路径
        2. data/witness_keys.json（默认持久化路径）
        3. 首次运行时生成真正的随机密钥并持久化
        
        密钥文件格式: {"SECTOR": {"private_key": "hex", "public_key": "hex"}, ...}
        """
        keys_path = os.environ.get(
            "WITNESS_KEYS_FILE",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "witness_keys.json")
        )
        
        # 尝试从配置文件加载
        loaded = self._load_witness_keys_from_file(keys_path)
        if loaded:
            return
        
        # 配置文件不存在：生成安全随机密钥并持久化
        try:
            from ecdsa import SigningKey, SECP256k1
            key_data = {}
            for sector in self.WITNESS_SECTORS:
                if sector not in self._witness_pubkeys:
                    # S-1 fix: 使用真正的随机密钥（os.urandom），不再用确定性种子
                    sk = SigningKey.generate(curve=SECP256k1, entropy=os.urandom)
                    vk = sk.get_verifying_key()
                    self._witness_pubkeys[sector] = vk.to_string().hex()
                    key_data[sector] = {
                        "private_key": sk.to_string().hex(),
                        "public_key": vk.to_string().hex(),
                    }
            # 持久化密钥到文件
            if key_data:
                self._save_witness_keys_to_file(keys_path, key_data)
        except ImportError:
            pass  # ecdsa 不可用时公钥注册表为空，签名验证将被跳过
    
    def _load_witness_keys_from_file(self, keys_path: str) -> bool:
        """从 JSON 文件加载见证密钥。返回 True 表示加载成功。"""
        try:
            if os.path.exists(keys_path):
                with open(keys_path, 'r') as f:
                    key_data = json.load(f)
                for sector, keys in key_data.items():
                    pub_hex = keys.get("public_key", "")
                    if pub_hex and len(pub_hex) >= 64:
                        self._witness_pubkeys[sector] = pub_hex
                if self._witness_pubkeys:
                    return True
        except Exception:
            pass
        return False
    
    def _save_witness_keys_to_file(self, keys_path: str, key_data: dict):
        """持久化见证密钥到 JSON 文件。"""
        try:
            os.makedirs(os.path.dirname(keys_path), exist_ok=True)
            with open(keys_path, 'w') as f:
                json.dump(key_data, f, indent=2)
            # 尝试限制文件权限（Linux/Mac）
            try:
                os.chmod(keys_path, 0o600)
            except (OSError, PermissionError):
                pass
        except Exception:
            pass  # 写入失败不影响运行，密钥仍在内存中
    
    def register_witness_pubkey(self, sector: str, pubkey_hex: str):
        """注册/更新见证板块的授权公钥。"""
        self._witness_pubkeys[sector] = pubkey_hex
    
    def _init_db(self):
        """初始化数据库"""
        with self._conn() as conn:
            # 兑换请求表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exchange_requests (
                    exchange_id TEXT PRIMARY KEY,
                    request_data TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            # MAIN 余额表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS main_balances (
                    address TEXT PRIMARY KEY,
                    balance REAL DEFAULT 0,
                    locked REAL DEFAULT 0,
                    updated_at REAL
                )
            """)
            
            # MAIN 交易记录（需要多板块见证）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS main_transactions (
                    tx_id TEXT PRIMARY KEY,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    tx_type TEXT NOT NULL,
                    witness_sectors TEXT,
                    witness_count INTEGER DEFAULT 0,
                    is_valid INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exchange_status ON exchange_requests(status)")
    
    # ==================== 兑换比例计算 ====================
    
    def get_exchange_rate(self, sector: str) -> float:
        """
        获取当前兑换比例
        
        [H-06] 优先使用 DynamicExchangeRate 动态汇率引擎（基于供需计算），
        若未注入则回退到静态 BASE_EXCHANGE_RATES。
        """
        # 优先使用动态汇率引擎
        if self.dynamic_rate_engine is not None:
            try:
                rate = self.dynamic_rate_engine.get_rate(sector)
                if rate and rate > 0:
                    return rate
            except Exception:
                pass  # 动态引擎异常时回退到静态汇率
        
        # 回退到静态基础比例
        return self.BASE_EXCHANGE_RATES.get(sector, 0.5)
    
    def calculate_main_amount(self, sector: str, sector_coin_amount: float) -> float:
        """计算可兑换的 MAIN 数量 [H-07: 精度安全]"""
        from .precision import safe_mul, to_display
        rate = self.get_exchange_rate(sector)
        return to_display(safe_mul(sector_coin_amount, rate))
    
    # ==================== 兑换流程 ====================
    
    def request_exchange(self, requester_address: str, sector: str, 
                         amount: float) -> Tuple[bool, str, Optional[ExchangeRequest]]:
        """
        Step 1: 请求兑换板块币 → MAIN
        
        Args:
            requester_address: 请求者钱包地址
            sector: 源板块
            amount: 板块币数量
            
        Returns:
            (成功, 消息, 兑换请求对象)
        """
        if sector == "MAIN":
            return False, "MAIN 不可兑换（DR-1）", None
        
        if amount <= 0:
            return False, "金额必须大于 0", None
        
        coin_type = SectorCoinType.from_sector(sector)
        
        # 检查 sector_ledger 余额（用于 lock/burn 管理）
        balance = self.sector_ledger.get_balance(requester_address, coin_type)
        if balance.available < amount:
            return False, f"可用余额不足: {balance.available:.4f} {coin_type.value}", None
        
        # 同时检查 UTXO 余额（create_exchange_transaction 实际消费 UTXO）
        try:
            from core.utxo_store import get_utxo_store
            utxo_store = get_utxo_store()
            utxo_spendable = utxo_store.get_spendable_utxos(requester_address, sector)
            utxo_total = sum(u.amount for u in utxo_spendable)
            if utxo_total < amount:
                return False, f"UTXO 可用余额不足: {utxo_total:.4f} {sector}, 需要 {amount:.4f}", None
        except Exception as e:
            logger.warning(f"UTXO 余额检查失败，仅依赖 sector_ledger: {e}")
        
        # 锁定板块币
        ok, msg = self.sector_ledger.lock_for_exchange(requester_address, coin_type, amount)
        if not ok:
            return False, msg, None
        
        # 计算可兑换的 MAIN
        rate = self.get_exchange_rate(sector)
        main_amount = amount * rate
        
        # 选择见证板块（排除源板块）— 使用密码学安全随机数
        import secrets
        secure_rng = secrets.SystemRandom()
        available_witnesses = [s for s in self.WITNESS_SECTORS if s != sector]
        witness_sectors = secure_rng.sample(available_witnesses, min(self.required_witnesses, len(available_witnesses)))
        
        # 创建兑换请求 (128-bit hash + random entropy to avoid collision)
        exchange_id = hashlib.sha256(
            f"EXCHANGE_{requester_address}_{sector}_{amount}_{time.time()}_{os.urandom(8).hex()}".encode()
        ).hexdigest()[:32]
        
        request = ExchangeRequest(
            exchange_id=exchange_id,
            requester_address=requester_address,
            source_sector=sector,
            source_coin_type=coin_type,
            source_amount=amount,
            target_main_amount=main_amount,
            exchange_rate=rate,
            status=ExchangeStatus.WITNESSING,
            created_at=time.time(),
            required_witnesses=self.required_witnesses,
            witness_sectors=witness_sectors
        )
        
        # 保存请求
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO exchange_requests (exchange_id, request_data, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (exchange_id, json.dumps(request.to_dict()), 
                  request.status.value, time.time(), time.time()))
        
        return True, f"兑换请求已创建，等待 {witness_sectors} 见证", request
    
    def add_witness(self, exchange_id: str, witness_sector: str,
                    block_height: int, block_hash: str,
                    signature: str = "") -> Tuple[bool, str]:
        """
        Step 2: 添加见证（由各板块的区块生成时调用）
        
        当见证板块产生新区块时，应检查是否有待见证的兑换请求，
        并将兑换信息写入区块，然后调用此方法记录见证。
        
        Security: signature MUST be cryptographically verified against
        the authorized validator key for the witness_sector.
        """
        # --- Security: Validate signature ---
        if not signature or len(signature) < 64:
            return False, "见证签名缺失或无效 (witness signature missing or invalid)"
        
        # D-04 fix: 使用公钥注册表进行真实 ECDSA 签名验证
        witness_payload = f"{exchange_id}:{witness_sector}:{block_height}:{block_hash}"
        try:
            from core.crypto import ECDSASigner
            sig_bytes = bytes.fromhex(signature)
            payload_hash = hashlib.sha256(witness_payload.encode()).digest()
            
            # 从公钥注册表获取该见证板块的授权公钥
            witness_pubkey_hex = self._witness_pubkeys.get(witness_sector)
            if witness_pubkey_hex:
                pub_bytes = bytes.fromhex(witness_pubkey_hex)
                if not ECDSASigner.verify(pub_bytes, payload_hash, sig_bytes):
                    return False, f"见证签名验证失败 (witness signature invalid for {witness_sector})"
            else:
                # 公钥未注册：仅在测试网允许跳过，主网拒绝
                if not self.testnet:
                    return False, f"见证板块 {witness_sector} 公钥未注册 (witness pubkey not registered)"
                # 测试网：至少验证签名结构（DER 格式至少 64 字节）
                if len(sig_bytes) < 64:
                    return False, f"见证签名长度无效 (witness signature too short for {witness_sector})"
        except (ValueError, Exception) as e:
            return False, f"见证签名验证异常: {e} (witness signature verification error)"
        
        with self._lock:
            with self._conn() as conn:
                # 获取请求
                row = conn.execute(
                    "SELECT request_data FROM exchange_requests WHERE exchange_id = ?",
                    (exchange_id,)
                ).fetchone()
                
                if not row:
                    return False, "兑换请求不存在"
                
                request = ExchangeRequest.from_dict(json.loads(row['request_data']))
                
                if request.status != ExchangeStatus.WITNESSING:
                    return False, f"请求状态不正确: {request.status.value}"
                
                if witness_sector not in request.witness_sectors:
                    return False, f"{witness_sector} 不是指定的见证板块"
                
                # 检查是否已见证
                for w in request.witnesses:
                    if w.witness_sector == witness_sector:
                        return False, f"{witness_sector} 已完成见证"
                
                # --- Security: Check exchange timeout (24h) ---
                if time.time() - request.created_at > 86400:
                    request.status = ExchangeStatus.FAILED
                    conn.execute("""
                        UPDATE exchange_requests SET request_data = ?, status = ?, updated_at = ?
                        WHERE exchange_id = ?
                    """, (json.dumps(request.to_dict()), request.status.value, 
                          time.time(), request.exchange_id))
                    # Unlock source coins
                    try:
                        self.sector_ledger.unlock_exchange(
                            request.requester_address, request.source_coin_type, request.source_amount
                        )
                    except Exception:
                        pass
                    return False, "兑换请求已超时 (exchange request expired after 24h)"
                
                # 添加见证
                witness = WitnessRecord(
                    witness_sector=witness_sector,
                    witness_block_height=block_height,
                    witness_block_hash=block_hash,
                    witness_time=time.time(),
                    witness_signature=signature
                )
                request.witnesses.append(witness)
                
                # 检查是否达到双见证
                if len(request.witnesses) >= request.required_witnesses:
                    # 双见证达成！执行兑换
                    ok, msg = self._complete_exchange(conn, request)
                    return ok, msg
                else:
                    # 更新请求
                    conn.execute("""
                        UPDATE exchange_requests SET request_data = ?, updated_at = ?
                        WHERE exchange_id = ?
                    """, (json.dumps(request.to_dict()), time.time(), exchange_id))
                    
                    remaining = request.required_witnesses - len(request.witnesses)
                    return True, f"见证已记录，还需 {remaining} 个见证"
    
    def _complete_exchange(self, conn, request: ExchangeRequest) -> Tuple[bool, str]:
        """
        Step 3: 完成兑换（双见证达成后）
        
        只解锁 sector_ledger 并标记完成。
        实际的 UTXO 消费和 sector_ledger 同步由调用方 (rpc_service) 处理，
        确保 UTXO 操作成功后才销毁 sector_ledger 余额。
        """
        # 解锁板块币（从 locked 恢复为 available，等 UTXO 操作成功后再 burn）
        ok, msg = self.sector_ledger.unlock_exchange(
            request.requester_address,
            request.source_coin_type,
            request.source_amount
        )
        
        if not ok:
            request.status = ExchangeStatus.FAILED
            conn.execute("""
                UPDATE exchange_requests SET request_data = ?, status = ?, updated_at = ?
                WHERE exchange_id = ?
            """, (json.dumps(request.to_dict()), request.status.value, 
                  time.time(), request.exchange_id))
            return False, f"解锁板块币失败: {msg}"
        
        # 铸造 MAIN（记录到 exchange.db，供余额展示和供应量追踪）
        self._mint_main(conn, request.requester_address, request.target_main_amount,
                        request.exchange_id, request.witness_sectors)
        
        # 更新状态
        request.status = ExchangeStatus.COMPLETED
        request.completed_at = time.time()
        
        conn.execute("""
            UPDATE exchange_requests SET request_data = ?, status = ?, updated_at = ?
            WHERE exchange_id = ?
        """, (json.dumps(request.to_dict()), request.status.value,
              time.time(), request.exchange_id))
        
        return True, f"兑换完成: {request.source_amount:.4f} {request.source_coin_type.value} → {request.target_main_amount:.4f} MAIN"
    
    def _mint_main(self, conn, address: str, amount: float, 
                   exchange_id: str, witness_sectors: List[str]):
        """铸造 MAIN（仅在双见证完成后调用）
        
        Security: Enforces MAIN_MAX_SUPPLY cap. Raises ValueError if cap exceeded.
        """
        # === Supply Cap Check ===
        total_minted = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM main_transactions WHERE tx_type = 'MINT'"
        ).fetchone()['total']
        
        if total_minted + amount > self.MAIN_MAX_SUPPLY:
            remaining = self.MAIN_MAX_SUPPLY - total_minted
            if remaining <= 0:
                raise ValueError(f"MAIN supply cap reached ({self.MAIN_MAX_SUPPLY}). Cannot mint more MAIN.")
            # Cap the mint to remaining supply
            amount = remaining
        
        # 更新余额
        row = conn.execute(
            "SELECT balance FROM main_balances WHERE address = ?", (address,)
        ).fetchone()
        
        if row:
            conn.execute("""
                UPDATE main_balances SET balance = balance + ?, updated_at = ?
                WHERE address = ?
            """, (amount, time.time(), address))
        else:
            conn.execute("""
                INSERT INTO main_balances (address, balance, locked, updated_at)
                VALUES (?, ?, 0, ?)
            """, (address, amount, time.time()))
        
        # 记录 MAIN 交易（带见证信息）
        # Security: Use full SHA-256 hash to avoid tx_id collisions
        import secrets
        entropy = secrets.token_hex(16)
        tx_id = hashlib.sha256(
            f"MINT_MAIN_{exchange_id}_{address}_{amount}_{time.time()}_{entropy}".encode()
        ).hexdigest()
        
        conn.execute("""
            INSERT INTO main_transactions 
            (tx_id, from_address, to_address, amount, tx_type, witness_sectors, witness_count, is_valid, created_at)
            VALUES (?, ?, ?, ?, 'MINT', ?, ?, 1, ?)
        """, (tx_id, "EXCHANGE_MINT", address, amount, 
              json.dumps(witness_sectors), len(witness_sectors), time.time()))
        # 注意: UTXO 由调用方 (rpc_service._sector_request_exchange → utxo_store.create_exchange_transaction) 创建
        # 此处不再重复创建，避免双重铸造
    
    # ==================== 取消兑换 ====================
    
    def cancel_exchange(self, exchange_id: str, 
                        requester_address: str) -> Tuple[bool, str]:
        """取消兑换请求（解锁板块币）"""
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT request_data FROM exchange_requests WHERE exchange_id = ?",
                    (exchange_id,)
                ).fetchone()
                
                if not row:
                    return False, "请求不存在"
                
                request = ExchangeRequest.from_dict(json.loads(row['request_data']))
                
                if request.requester_address != requester_address:
                    return False, "无权取消此请求"
                
                if request.status not in [ExchangeStatus.PENDING, ExchangeStatus.WITNESSING]:
                    return False, f"无法取消状态为 {request.status.value} 的请求"
                
                # 解锁板块币
                self.sector_ledger.unlock_exchange(
                    requester_address, request.source_coin_type, request.source_amount
                )
                
                # 更新状态
                request.status = ExchangeStatus.CANCELLED
                conn.execute("""
                    UPDATE exchange_requests SET request_data = ?, status = ?, updated_at = ?
                    WHERE exchange_id = ?
                """, (json.dumps(request.to_dict()), request.status.value,
                      time.time(), exchange_id))
        
        return True, "兑换已取消"
    
    # ==================== 查询 ====================
    
    def get_exchange_request(self, exchange_id: str) -> Optional[ExchangeRequest]:
        """获取兑换请求"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT request_data FROM exchange_requests WHERE exchange_id = ?",
                (exchange_id,)
            ).fetchone()
            
            if row:
                return ExchangeRequest.from_dict(json.loads(row['request_data']))
        return None
    
    def get_pending_exchanges_for_sector(self, sector: str) -> List[ExchangeRequest]:
        """获取需要该板块见证的待处理兑换请求"""
        result = []
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT request_data FROM exchange_requests 
                WHERE status = 'WITNESSING'
            """).fetchall()
            
            for row in rows:
                request = ExchangeRequest.from_dict(json.loads(row['request_data']))
                if sector in request.witness_sectors:
                    # 检查是否已见证
                    already_witnessed = any(
                        w.witness_sector == sector for w in request.witnesses
                    )
                    if not already_witnessed:
                        result.append(request)
        
        return result
    
    def get_main_balance(self, address: str) -> float:
        """获取 MAIN 余额"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT balance FROM main_balances WHERE address = ?", (address,)
            ).fetchone()
            return row['balance'] if row else 0.0
    
    def get_main_transactions(self, address: str, limit: int = 50) -> List[Dict]:
        """获取 MAIN 交易历史"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM main_transactions 
                WHERE from_address = ? OR to_address = ?
                ORDER BY created_at DESC LIMIT ?
            """, (address, address, limit)).fetchall()
            return [dict(r) for r in rows]


# ==================== 全局实例 ====================

_exchange_instance: Optional[DualWitnessExchange] = None


def get_exchange_service(testnet: bool = False) -> DualWitnessExchange:
    """获取全局兑换服务
    
    Args:
        testnet: 测试网模式（单见证即可完成兑换）
    """
    global _exchange_instance
    if _exchange_instance is None:
        _exchange_instance = DualWitnessExchange(testnet=testnet)
    return _exchange_instance
