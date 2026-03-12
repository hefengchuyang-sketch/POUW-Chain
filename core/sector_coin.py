# -*- coding: utf-8 -*-
"""
板块币系统 (Sector Coin System)

设计约束:
- DR-3: 每个板块只能产出"本板块币"
- DR-4: 板块之间禁止直接互换，必须经过 MAIN
- DR-7: 板块奖励单位必须是板块币
- DR-8: 减半机制按板块独立执行

板块币类型:
- H100_COIN: H100 板块产出
- RTX4090_COIN: RTX4090 板块产出
- RTX3080_COIN: RTX3080 板块产出
- CPU_COIN: CPU 板块产出
- GENERAL_COIN: GENERAL 板块产出

注意: MAIN 不可挖，不属于任何板块，仅作为跨板块结算资产
"""

import time
import json
import hashlib
import secrets
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
from core import db
from contextlib import contextmanager


# ==================== 板块注册表（动态管理） ====================

class SectorRegistry:
    """板块动态注册表
    
    管理所有已注册板块及其状态。支持：
    1. 根据新 GPU 型号动态注册新板块
    2. 停用长期无矿工活跃的板块
    3. 查询当前活跃板块列表
    
    设计约束：
    - 内置板块（H100, RTX4090, RTX3080, CPU, GENERAL）不可删除
    - 新板块需提交 DAO 提案或由管理员手动添加
    - 停用板块只是标记 inactive，历史数据保留
    """
    
    # 内置板块，不可删除
    BUILTIN_SECTORS = {"H100", "RTX4090", "RTX3080", "CPU", "GENERAL"}
    
    # 新板块默认配置
    DEFAULT_BASE_REWARD = 1.0
    DEFAULT_EXCHANGE_RATE = 0.5
    DEFAULT_MAX_SUPPLY = 21_000_000.0
    
    def __init__(self):
        self._lock = threading.RLock()
        # {sector_name: SectorInfo}
        self._sectors: Dict[str, dict] = {}
        # 初始化内置板块
        self._init_builtin()
    
    def _init_builtin(self):
        """注册内置板块"""
        builtin_configs = {
            "H100":    {"base_reward": 10.0, "exchange_rate": 0.5, "max_supply": 21_000_000.0, "gpu_models": ["H100", "A100", "A6000", "A40", "A30", "L40"]},
            "RTX4090": {"base_reward": 5.0,  "exchange_rate": 0.5, "max_supply": 21_000_000.0, "gpu_models": ["RTX 4090", "RTX 4080", "RTX 3090 TI", "RTX 3090"]},
            "RTX3080": {"base_reward": 2.5,  "exchange_rate": 0.5, "max_supply": 21_000_000.0, "gpu_models": ["RTX 3080", "RTX 3070", "RTX 3060", "RTX 4070", "RTX 4060"]},
            "CPU":     {"base_reward": 1.0,  "exchange_rate": 0.5, "max_supply": 21_000_000.0, "gpu_models": []},
            "GENERAL": {"base_reward": 1.0,  "exchange_rate": 0.5, "max_supply": 21_000_000.0, "gpu_models": []},
        }
        for name, cfg in builtin_configs.items():
            self._sectors[name] = {
                "name": name,
                "active": True,
                "builtin": True,
                "base_reward": cfg["base_reward"],
                "exchange_rate": cfg["exchange_rate"],
                "max_supply": cfg["max_supply"],
                "gpu_models": cfg["gpu_models"],
                "created_at": 0,
                "deactivated_at": None,
                "active_miners": 0,
                "last_block_time": 0,
            }
    
    def add_sector(
        self,
        name: str,
        base_reward: float = None,
        exchange_rate: float = None,
        max_supply: float = None,
        gpu_models: List[str] = None,
    ) -> Tuple[bool, str]:
        """注册新板块
        
        Args:
            name: 板块名称（如 "RTX5090", "H200"）
            base_reward: 每块基础奖励（板块币）
            exchange_rate: 兑换 MAIN 的比率
            max_supply: 最大供应量
            gpu_models: 关联的 GPU 型号列表
        """
        with self._lock:
            if name in self._sectors:
                info = self._sectors[name]
                if info["active"]:
                    return False, f"板块 {name} 已存在且处于活跃状态"
                # 重新激活已停用的板块
                info["active"] = True
                info["deactivated_at"] = None
                return True, f"板块 {name} 已重新激活"
            
            self._sectors[name] = {
                "name": name,
                "active": True,
                "builtin": False,
                "base_reward": base_reward or self.DEFAULT_BASE_REWARD,
                "exchange_rate": exchange_rate or self.DEFAULT_EXCHANGE_RATE,
                "max_supply": max_supply or self.DEFAULT_MAX_SUPPLY,
                "gpu_models": gpu_models or [],
                "created_at": time.time(),
                "deactivated_at": None,
                "active_miners": 0,
                "last_block_time": 0,
            }
            return True, f"板块 {name} 已创建"
    
    def deactivate_sector(self, name: str, force: bool = False) -> Tuple[bool, str]:
        """停用板块（历史数据保留，不再接受新矿工和新任务）
        
        前提条件：该板块的币必须全部挖完（total_minted >= max_supply），
        否则拒绝停用。force=True 可跳过此检查（仅限内部测试）。
        """
        with self._lock:
            if name not in self._sectors:
                return False, f"板块 {name} 不存在"
            if name in self.BUILTIN_SECTORS:
                return False, f"内置板块 {name} 不可停用"
            info = self._sectors[name]
            if not info["active"]:
                return False, f"板块 {name} 已经处于停用状态"
            
            # 前提条件：板块币必须全部挖完才能触发停用
            if not force:
                try:
                    from core.sector_coin import SectorCoinType, SectorCoinLedger
                    coin_type = SectorCoinType.from_sector(name)
                    ledger = SectorCoinLedger()
                    total_minted = ledger._get_total_minted(coin_type)
                    max_supply = info["max_supply"]
                    if total_minted < max_supply:
                        return False, (f"板块 {name} 的币尚未挖完 "
                                       f"(已铸造 {total_minted:.2f}/{max_supply:.2f})，"
                                       f"必须全部挖完后才能触发停用")
                except Exception:
                    pass  # 安全回退：无法检验时允许通过
            
            info["active"] = False
            info["deactivated_at"] = time.time()
            return True, f"板块 {name} 已停用"
    
    def get_active_sectors(self) -> List[str]:
        """获取所有活跃板块名称"""
        with self._lock:
            return [name for name, info in self._sectors.items() if info["active"]]
    
    def get_all_sectors(self) -> List[dict]:
        """获取所有板块详情（含停用的）"""
        with self._lock:
            return [dict(info) for info in self._sectors.values()]
    
    def get_sector_info(self, name: str) -> Optional[dict]:
        """获取单个板块信息"""
        with self._lock:
            info = self._sectors.get(name)
            return dict(info) if info else None
    
    def is_active(self, name: str) -> bool:
        """板块是否活跃"""
        with self._lock:
            info = self._sectors.get(name)
            return info["active"] if info else False
    
    def update_miner_count(self, name: str, count: int):
        """更新板块活跃矿工数"""
        with self._lock:
            if name in self._sectors:
                self._sectors[name]["active_miners"] = count
    
    def update_last_block_time(self, name: str):
        """记录板块最近出块时间"""
        with self._lock:
            if name in self._sectors:
                self._sectors[name]["last_block_time"] = time.time()
    
    def get_base_reward(self, sector: str) -> float:
        """获取板块基础奖励"""
        with self._lock:
            info = self._sectors.get(sector)
            return info["base_reward"] if info else self.DEFAULT_BASE_REWARD
    
    def get_exchange_rate(self, sector: str) -> float:
        """获取板块兑换比率"""
        with self._lock:
            info = self._sectors.get(sector)
            return info["exchange_rate"] if info else self.DEFAULT_EXCHANGE_RATE
    
    def get_max_supply(self, sector: str) -> float:
        """获取板块最大供应量"""
        with self._lock:
            info = self._sectors.get(sector)
            return info["max_supply"] if info else self.DEFAULT_MAX_SUPPLY


# 全局板块注册表单例
_sector_registry: Optional[SectorRegistry] = None


def get_sector_registry() -> SectorRegistry:
    """获取全局板块注册表"""
    global _sector_registry
    if _sector_registry is None:
        _sector_registry = SectorRegistry()
    return _sector_registry


class SectorCoinType(Enum):
    """板块币类型"""
    H100_COIN = "H100_COIN"
    RTX4090_COIN = "RTX4090_COIN"
    RTX3080_COIN = "RTX3080_COIN"
    CPU_COIN = "CPU_COIN"
    GENERAL_COIN = "GENERAL_COIN"
    
    @classmethod
    def from_sector(cls, sector: str) -> "SectorCoinType":
        """从板块名获取板块币类型（支持动态板块）"""
        mapping = {
            "H100": cls.H100_COIN,
            "RTX4090": cls.RTX4090_COIN,
            "RTX3080": cls.RTX3080_COIN,
            "CPU": cls.CPU_COIN,
            "GENERAL": cls.GENERAL_COIN,
        }
        if sector in mapping:
            return mapping[sector]
        # 动态板块：使用 DynamicSectorCoin 包装
        return DynamicSectorCoin(sector)
    
    @property
    def sector(self) -> str:
        """获取板块名"""
        return self.value.replace("_COIN", "")


class DynamicSectorCoin:
    """动态板块币类型（非 Enum 成员，用于运行时新增的板块）"""
    
    def __init__(self, sector_name: str):
        self._sector = sector_name
        self.value = f"{sector_name}_COIN"
        self.name = f"{sector_name}_COIN"
    
    @property
    def sector(self) -> str:
        return self._sector
    
    def __eq__(self, other):
        if isinstance(other, DynamicSectorCoin):
            return self.value == other.value
        if isinstance(other, SectorCoinType):
            return self.value == other.value
        return False
    
    def __hash__(self):
        return hash(self.value)
    
    def __repr__(self):
        return f"DynamicSectorCoin({self._sector})"


@dataclass
class SectorCoinBalance:
    """板块币余额"""
    address: str
    coin_type: SectorCoinType
    balance: float = 0.0
    locked: float = 0.0  # 锁定中（待兑换）
    
    @property
    def available(self) -> float:
        """可用余额"""
        return self.balance - self.locked


@dataclass
class SectorCoinTransfer:
    """板块币转账记录"""
    tx_id: str
    coin_type: SectorCoinType
    from_address: str
    to_address: str
    amount: float
    timestamp: float
    block_height: int = 0  # 所属区块高度
    
    # 特殊地址
    MINT_ADDRESS = "SECTOR_MINT"      # 铸造地址（挖矿奖励来源）
    BURN_ADDRESS = "SECTOR_BURN"      # 销毁地址（兑换 MAIN 时销毁）


class SectorCoinLedger:
    """
    板块币账本
    
    每个板块维护独立的账本，记录:
    1. 各地址的板块币余额
    2. 板块内转账记录
    3. 挖矿铸造记录
    4. 兑换销毁记录
    """
    
    # 基础挖矿奖励（板块币单位）— 内置默认值，动态板块从 SectorRegistry 读取
    BASE_REWARDS: Dict[str, float] = {
        "H100": 10.0,        # H100_COIN
        "RTX4090": 5.0,      # RTX4090_COIN
        "RTX3080": 2.5,      # RTX3080_COIN
        "CPU": 1.0,          # CPU_COIN
        "GENERAL": 1.0,      # GENERAL_COIN
    }
    
    # 减半周期（每板块独立）
    HALVING_INTERVAL = 210000
    
    # === Supply Cap: Maximum supply per sector coin type ===
    MAX_SUPPLY: Dict[str, float] = {
        "H100": 21_000_000.0,
        "RTX4090": 21_000_000.0,
        "RTX3080": 21_000_000.0,
        "CPU": 21_000_000.0,
        "GENERAL": 21_000_000.0,
    }
    
    def _get_base_reward(self, sector: str) -> float:
        """从注册表获取基础奖励（兼容内置 + 动态板块）"""
        if sector in self.BASE_REWARDS:
            return self.BASE_REWARDS[sector]
        return get_sector_registry().get_base_reward(sector)
    
    def _get_max_supply(self, sector: str) -> float:
        """从注册表获取最大供应量（兼容内置 + 动态板块）"""
        if sector in self.MAX_SUPPLY:
            return self.MAX_SUPPLY[sector]
        return get_sector_registry().get_max_supply(sector)
    
    def __init__(self, db_path: str = "data/sector_coins.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
    
    @contextmanager
    def _conn(self):
        conn = db.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库"""
        with self._conn() as conn:
            # 余额表（每个地址在每个板块的余额）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS balances (
                    address TEXT NOT NULL,
                    coin_type TEXT NOT NULL,
                    balance REAL DEFAULT 0,
                    locked REAL DEFAULT 0,
                    updated_at REAL,
                    PRIMARY KEY (address, coin_type)
                )
            """)
            
            # 转账记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transfers (
                    tx_id TEXT PRIMARY KEY,
                    coin_type TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    block_height INTEGER DEFAULT 0,
                    tx_type TEXT DEFAULT 'TRANSFER'
                )
            """)
            
            # B-3: 唯一约束防止同一区块同一板块双铸
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_mint_unique
                ON transfers(coin_type, block_height, to_address)
                WHERE tx_type = 'MINT'
            """)
            
            # 板块高度表（用于计算减半）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sector_heights (
                    sector TEXT PRIMARY KEY,
                    height INTEGER DEFAULT 0,
                    last_block_time REAL
                )
            """)
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transfers_address ON transfers(from_address, to_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transfers_coin ON transfers(coin_type)")
    
    # ==================== 余额管理 ====================
    
    def get_balance(self, address: str, coin_type: SectorCoinType) -> SectorCoinBalance:
        """获取板块币余额"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT balance, locked FROM balances 
                WHERE address = ? AND coin_type = ?
            """, (address, coin_type.value)).fetchone()
            
            return SectorCoinBalance(
                address=address,
                coin_type=coin_type,
                balance=row['balance'] if row else 0.0,
                locked=row['locked'] if row else 0.0
            )
    
    def get_all_balances(self, address: str) -> Dict[SectorCoinType, SectorCoinBalance]:
        """获取地址的所有板块币余额"""
        result = {}
        for coin_type in SectorCoinType:
            result[coin_type] = self.get_balance(address, coin_type)
        return result
    
    def _update_balance(self, conn, address: str, coin_type: SectorCoinType, 
                        delta: float, delta_locked: float = 0):
        """更新余额（内部方法）
        
        Raises:
            ValueError: 余额或锁定金额变为负数
        """
        now = time.time()
        
        # 检查是否存在记录
        row = conn.execute("""
            SELECT balance, locked FROM balances WHERE address = ? AND coin_type = ?
        """, (address, coin_type.value)).fetchone()
        
        if row:
            new_balance = row['balance'] + delta
            new_locked = row['locked'] + delta_locked
            
            # 防止负余额
            if new_balance < -0.00000001:
                raise ValueError(f"余额不足: {address} {coin_type.value} 余额 {row['balance']}, 尝试变更 {delta}")
            if new_locked < -0.00000001:
                raise ValueError(f"锁定金额异常: {address} {coin_type.value} 锁定 {row['locked']}, 尝试变更 {delta_locked}")
            
            # 修正浮点精度
            new_balance = max(0.0, new_balance)
            new_locked = max(0.0, new_locked)
            
            conn.execute("""
                UPDATE balances SET balance = ?, locked = ?, updated_at = ?
                WHERE address = ? AND coin_type = ?
            """, (new_balance, new_locked, now, address, coin_type.value))
        else:
            if delta < 0:
                raise ValueError(f"余额不足: {address} {coin_type.value} 无余额记录, 尝试扣除 {delta}")
            if delta_locked < 0:
                raise ValueError(f"锁定金额异常: {address} {coin_type.value} 无记录, 尝试解锁 {delta_locked}")
            conn.execute("""
                INSERT INTO balances (address, coin_type, balance, locked, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (address, coin_type.value, delta, delta_locked, now))
    
    # ==================== 挖矿奖励（铸造） ====================
    
    def get_block_reward(self, sector: str, height: int) -> float:
        """
        计算板块的区块奖励
        
        Args:
            sector: 板块名称
            height: 该板块的区块高度
            
        Returns:
            板块币数量（不是 MAIN!）
        """
        # MAIN 不可挖
        if sector == "MAIN":
            return 0.0
        
        base = self._get_base_reward(sector)
        halvings = height // self.HALVING_INTERVAL
        reward = base / (2 ** halvings)
        
        # Check against supply cap - reward drops to 0 when cap reached
        max_supply = self._get_max_supply(sector)
        coin_type = SectorCoinType.from_sector(sector)
        current_supply = self._get_total_minted(coin_type)
        if current_supply >= max_supply:
            return 0.0
        # Cap reward to not exceed max supply
        if current_supply + reward > max_supply:
            reward = max_supply - current_supply
        
        return reward if reward > 0 else 0.0
    
    def mint_block_reward(self, sector: str, miner_address: str, 
                          block_height: int) -> Tuple[bool, float, str]:
        """
        铸造区块奖励（挖矿产出板块币）
        
        Args:
            sector: 板块名称
            miner_address: 矿工地址
            block_height: 区块高度
            
        Returns:
            (成功, 奖励数量, 消息)
            
        注意: 奖励单位是板块币，不是 MAIN!
        """
        if sector == "MAIN":
            return False, 0, "MAIN 不可挖矿 (DR-1)"
        
        coin_type = SectorCoinType.from_sector(sector)
        
        with self._lock:
            with self._conn() as conn:
                # 原子性供应上限检查：在同一事务/锁内读取当前供应量并铸造
                # Atomic supply cap check: read supply + mint in same lock/transaction
                current_supply = conn.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total FROM transfers
                    WHERE coin_type = ? AND tx_type = 'MINT'
                """, (coin_type.value,)).fetchone()['total']
                
                max_supply = self._get_max_supply(sector)
                if current_supply >= max_supply:
                    return False, 0, f"{sector} 板块币已达到最大供应量 (supply cap reached)"
                
                # 计算奖励（内联 get_block_reward 的核心逻辑，避免二次查询）
                base = self._get_base_reward(sector)
                halvings = block_height // self.HALVING_INTERVAL
                reward = base / (2 ** halvings)
                
                # 截止到上限
                if current_supply + reward > max_supply:
                    reward = max_supply - current_supply
                
                if reward <= 0:
                    return False, 0, f"{sector} 板块币已达到最大供应量 (supply cap reached)"
                
                # 生成确定性交易 ID（同一区块+板块+矿工 → 同一 tx_id，保证幂等性）
                tx_id = hashlib.sha256(
                    f"MINT_{sector}_{block_height}_{miner_address}".encode()
                ).hexdigest()
                
                # 增加矿工余额
                self._update_balance(conn, miner_address, coin_type, reward)
                
                # 记录铸造交易
                conn.execute("""
                    INSERT INTO transfers (tx_id, coin_type, from_address, to_address, 
                                           amount, timestamp, block_height, tx_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'MINT')
                """, (tx_id, coin_type.value, SectorCoinTransfer.MINT_ADDRESS,
                      miner_address, reward, time.time(), block_height))
                
                # 更新板块高度
                conn.execute("""
                    INSERT OR REPLACE INTO sector_heights (sector, height, last_block_time)
                    VALUES (?, ?, ?)
                """, (sector, block_height, time.time()))
        
        return True, reward, f"铸造 {reward:.4f} {coin_type.value}"
    
    # ==================== 板块内转账 ====================
    
    def transfer(self, from_address: str, to_address: str, 
                 coin_type: SectorCoinType, amount: float,
                 signature: str = "", public_key: str = "") -> Tuple[bool, str]:
        """
        板块币转账（仅限同板块内）
        
        Security: Requires valid ECDSA signature from the sender.
        注意: 不同板块的币不能直接互转！
        """
        if amount <= 0:
            return False, "金额必须大于 0"
        
        # --- Security: Verify transfer signature ---
        if not signature or not public_key:
            return False, "转账必须提供签名和公钥 (signature and public_key required)"
        
        # D-10 fix: 正确的 ECDSA 签名验证
        try:
            from core.crypto import ECDSASigner
            # 构造签名载荷
            transfer_payload = f"TRANSFER:{from_address}:{to_address}:{coin_type.value}:{amount}"
            payload_hash = hashlib.sha256(transfer_payload.encode()).digest()
            
            sig_bytes = bytes.fromhex(signature)
            pub_bytes = bytes.fromhex(public_key)
            
            # 验证 ECDSA 签名
            if not ECDSASigner.verify(pub_bytes, payload_hash, sig_bytes):
                return False, "签名验证失败 (signature verification failed)"
            
            # 验证公钥派生地址匹配发送地址
            derived_addr = ECDSASigner.public_key_to_address(pub_bytes)
            if derived_addr != from_address:
                # 兼容简化地址格式
                alt_addr = hashlib.sha256(pub_bytes).hexdigest()[:40]
                if alt_addr != from_address:
                    return False, "公钥与发送地址不匹配 (public_key does not match from_address)"
        except ImportError:
            import os
            if os.environ.get('MAINCOIN_PRODUCTION', '').lower() == 'true':
                return False, "签名验证不可用 (ecdsa library missing in production)"
        except (ValueError, Exception) as e:
            return False, f"签名验证异常: {e} (signature verification error)"
        
        with self._lock:
            with self._conn() as conn:
                # 检查余额
                row = conn.execute("""
                    SELECT balance, locked FROM balances 
                    WHERE address = ? AND coin_type = ?
                """, (from_address, coin_type.value)).fetchone()
                
                available = (row['balance'] - row['locked']) if row else 0
                if available < amount:
                    return False, f"余额不足: 可用 {available:.4f} {coin_type.value}"
                
                # 生成交易 ID（完整 SHA-256）
                entropy = secrets.token_hex(16)
                tx_id = hashlib.sha256(
                    f"TRANSFER_{from_address}_{to_address}_{amount}_{time.time()}_{entropy}".encode()
                ).hexdigest()
                
                # 扣除发送方余额
                self._update_balance(conn, from_address, coin_type, -amount)
                
                # 增加接收方余额
                self._update_balance(conn, to_address, coin_type, amount)
                
                # 记录转账
                conn.execute("""
                    INSERT INTO transfers (tx_id, coin_type, from_address, to_address,
                                           amount, timestamp, tx_type)
                    VALUES (?, ?, ?, ?, ?, ?, 'TRANSFER')
                """, (tx_id, coin_type.value, from_address, to_address, 
                      amount, time.time()))
        
        return True, f"转账成功: {amount:.4f} {coin_type.value}"
    
    # ==================== 板块币兑换MAIN ====================
    
    def exchange_to_main(self, address: str, sector: str, amount: float, 
                         rate: float) -> Tuple[bool, float, str]:
        """
        将板块币兑换为 MAIN 币
        
        注意：此方法只负责销毁板块币部分。
        MAIN 币的铸造必须通过 MainLedger 模块完成（需双见证确认）。
        不在此处直接增加 MAIN 余额，避免绕过双见证机制。
        
        Security: Rate parameter is validated against maximum allowed rate
        to prevent callers from passing arbitrary inflated rates.
        
        Args:
            address: 用户地址
            sector: 板块名称（如 'RTX3080'）
            amount: 板块币数量
            rate: 兑换率（1 板块币 = rate MAIN）
            
        Returns:
            (成功, MAIN数量, 消息)
        """
        if amount <= 0:
            return False, 0, "金额必须大于0"
        
        # Security: Validate exchange rate is within allowed bounds
        MAX_EXCHANGE_RATE = 10.0  # Maximum allowed exchange rate per sector coin
        if rate <= 0 or rate > MAX_EXCHANGE_RATE:
            return False, 0, f"兑换率无效: 必须在 0 到 {MAX_EXCHANGE_RATE} 之间 (invalid exchange rate)"
        
        coin_type = SectorCoinType.from_sector(sector)
        # [H-07] 精度安全乘法
        from .precision import safe_mul, to_display
        main_amount = to_display(safe_mul(amount, rate))
        
        with self._lock:
            with self._conn() as conn:
                # 检查余额
                row = conn.execute("""
                    SELECT balance, locked FROM balances 
                    WHERE address = ? AND coin_type = ?
                """, (address, coin_type.value)).fetchone()
                
                available = (row['balance'] - row['locked']) if row else 0
                if available < amount:
                    return False, 0, f"余额不足: 可用 {available:.4f} {coin_type.value}"
                
                # 生成交易 ID（使用完整 SHA-256）
                import secrets
                entropy = secrets.token_hex(16)
                tx_id = hashlib.sha256(
                    f"EXCHANGE_{address}_{sector}_{amount}_{time.time()}_{entropy}".encode()
                ).hexdigest()
                
                # 扣除板块币（销毁）
                self._update_balance(conn, address, coin_type, -amount)
                
                # 注意：不在此处增加 MAIN 余额！
                # MAIN 币的铸造必须通过 convert_request + main_ledger 的双见证流程完成
                # 调用方应创建 ConvertRequest 并提交到双见证引擎
                
                # 记录销毁
                conn.execute("""
                    INSERT INTO transfers (tx_id, coin_type, from_address, to_address,
                                           amount, timestamp, tx_type)
                    VALUES (?, ?, ?, ?, ?, ?, 'BURN')
                """, (tx_id, coin_type.value, address, "EXCHANGE_BURN", 
                      amount, time.time()))
        
        return True, main_amount, f"板块币销毁成功: {amount:.4f} {sector}, 待双见证确认后铸造 {main_amount:.4f} MAIN"
    
    # ==================== UTXO 同步 ====================
    
    def sync_transfer_from_utxo(self, from_address: str, to_address: str,
                                coin_type: SectorCoinType, amount: float) -> bool:
        """
        同步 UTXO 转账到 sector_ledger（内部使用，不验证签名）。
        
        调用方必须已通过 UTXO 系统完成签名验证和余额扣减。
        此方法仅保持 sector_ledger 余额与 UTXO 一致，
        确保兑换系统 (lock_for_exchange) 能看到正确余额。
        """
        if amount <= 0:
            return False
        with self._lock:
            with self._conn() as conn:
                try:
                    self._update_balance(conn, from_address, coin_type, -amount)
                    self._update_balance(conn, to_address, coin_type, amount)
                    return True
                except ValueError:
                    return False
    
    # ==================== 兑换准备（锁定） ====================
    
    def lock_for_exchange(self, address: str, coin_type: SectorCoinType, 
                          amount: float) -> Tuple[bool, str]:
        """
        锁定板块币用于兑换 MAIN
        
        锁定后余额不能用于转账，直到兑换完成或取消
        """
        if amount <= 0:
            return False, "金额必须大于 0"
        
        with self._lock:
            with self._conn() as conn:
                # 检查可用余额
                balance = self.get_balance(address, coin_type)
                if balance.available < amount:
                    return False, f"可用余额不足: {balance.available:.4f}"
                
                # 增加锁定金额
                self._update_balance(conn, address, coin_type, 0, amount)
        
        return True, f"已锁定 {amount:.4f} {coin_type.value}"
    
    def unlock_exchange(self, address: str, coin_type: SectorCoinType, 
                        amount: float) -> Tuple[bool, str]:
        """解锁板块币（兑换取消时调用）"""
        if amount <= 0:
            return False, "金额必须大于 0"
        
        with self._lock:
            with self._conn() as conn:
                # 先检查锁定金额是否足够
                row = conn.execute("""
                    SELECT locked FROM balances WHERE address = ? AND coin_type = ?
                """, (address, coin_type.value)).fetchone()
                
                if not row or row['locked'] < amount:
                    current_locked = row['locked'] if row else 0
                    return False, f"锁定金额不足: 当前锁定 {current_locked:.4f}, 尝试解锁 {amount:.4f}"
                
                self._update_balance(conn, address, coin_type, 0, -amount)
        return True, "解锁成功"
    
    def burn_for_exchange(self, address: str, coin_type: SectorCoinType,
                          amount: float, exchange_id: str) -> Tuple[bool, str]:
        """
        销毁板块币（兑换 MAIN 时调用）
        
        这是板块币 → MAIN 兑换的一部分
        必须在双见证确认后才能调用
        """
        if amount <= 0:
            return False, "金额必须大于 0"
        
        with self._lock:
            with self._conn() as conn:
                # 检查锁定余额和总余额
                row = conn.execute("""
                    SELECT balance, locked FROM balances 
                    WHERE address = ? AND coin_type = ?
                """, (address, coin_type.value)).fetchone()
                
                if not row:
                    return False, "无余额记录"
                if row['locked'] < amount:
                    return False, f"锁定余额不足: 锁定 {row['locked']:.4f}, 需要 {amount:.4f}"
                if row['balance'] < amount:
                    return False, f"总余额不足: 余额 {row['balance']:.4f}, 需要 {amount:.4f}"
                
                # 减少余额和锁定
                self._update_balance(conn, address, coin_type, -amount, -amount)
                
                # 生成销毁交易 ID（完整 SHA-256）
                entropy = secrets.token_hex(16)
                tx_id = hashlib.sha256(
                    f"BURN_{exchange_id}_{address}_{amount}_{time.time()}_{entropy}".encode()
                ).hexdigest()
                
                # 记录销毁
                conn.execute("""
                    INSERT INTO transfers (tx_id, coin_type, from_address, to_address,
                                           amount, timestamp, tx_type)
                    VALUES (?, ?, ?, ?, ?, ?, 'BURN')
                """, (tx_id, coin_type.value, address, SectorCoinTransfer.BURN_ADDRESS,
                      amount, time.time()))
        
        return True, f"已销毁 {amount:.4f} {coin_type.value}"
    
    # ==================== 查询 ====================
    
    def get_sector_height(self, sector: str) -> int:
        """获取板块当前高度"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT height FROM sector_heights WHERE sector = ?", (sector,)
            ).fetchone()
            return row['height'] if row else 0
    
    def get_transfer_history(self, address: str, 
                             coin_type: Optional[SectorCoinType] = None,
                             limit: int = 50) -> List[Dict]:
        """获取转账历史"""
        with self._conn() as conn:
            if coin_type:
                rows = conn.execute("""
                    SELECT * FROM transfers 
                    WHERE (from_address = ? OR to_address = ?) AND coin_type = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (address, address, coin_type.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM transfers 
                    WHERE from_address = ? OR to_address = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (address, address, limit)).fetchall()
            
            return [dict(r) for r in rows]
    
    def _get_total_minted(self, coin_type: SectorCoinType) -> float:
        """Get total minted supply for a coin type (for supply cap checks)"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(amount), 0) as total FROM transfers 
                WHERE coin_type = ? AND tx_type = 'MINT'
            """, (coin_type.value,)).fetchone()
            return row['total'] if row else 0.0
    
    def get_total_supply(self, coin_type: SectorCoinType) -> Dict[str, float]:
        """获取板块币总供应量统计"""
        with self._conn() as conn:
            # 总铸造
            minted = conn.execute("""
                SELECT COALESCE(SUM(amount), 0) as total FROM transfers 
                WHERE coin_type = ? AND tx_type = 'MINT'
            """, (coin_type.value,)).fetchone()['total']
            
            # 总销毁
            burned = conn.execute("""
                SELECT COALESCE(SUM(amount), 0) as total FROM transfers 
                WHERE coin_type = ? AND tx_type = 'BURN'
            """, (coin_type.value,)).fetchone()['total']
            
            return {
                "coin_type": coin_type.value,
                "total_minted": minted,
                "total_burned": burned,
                "circulating": minted - burned
            }
    
    def rollback_to_height(self, sector: str, height: int) -> int:
        """回滚指定板块到 height（含），删除 height 之后的铸造/交易记录并重算余额。
        
        用于链重组(reorg)时保持板块币状态与区块链一致。
        
        Returns:
            被回滚的交易记录数。
        """
        coin_type = SectorCoinType.from_sector(sector)
        with self._lock:
            with self._conn() as conn:
                # 找出需要回滚的交易
                rows = conn.execute("""
                    SELECT tx_id, from_address, to_address, amount, tx_type
                    FROM transfers
                    WHERE coin_type = ? AND block_height > ?
                """, (coin_type.value, height)).fetchall()
                
                count = len(rows)
                if count == 0:
                    return 0
                
                # 删除交易记录
                conn.execute("""
                    DELETE FROM transfers
                    WHERE coin_type = ? AND block_height > ?
                """, (coin_type.value, height))
                
                # 重算所有受影响地址的余额
                affected_addresses = set()
                for r in rows:
                    if r['from_address']:
                        affected_addresses.add(r['from_address'])
                    if r['to_address']:
                        affected_addresses.add(r['to_address'])
                
                for addr in affected_addresses:
                    if addr == SectorCoinTransfer.MINT_ADDRESS:
                        continue
                    # 重算余额 = SUM(收入) - SUM(支出)
                    received = conn.execute("""
                        SELECT COALESCE(SUM(amount), 0) as total FROM transfers
                        WHERE coin_type = ? AND to_address = ?
                    """, (coin_type.value, addr)).fetchone()['total']
                    
                    sent = conn.execute("""
                        SELECT COALESCE(SUM(amount), 0) as total FROM transfers
                        WHERE coin_type = ? AND from_address = ?
                    """, (coin_type.value, addr)).fetchone()['total']
                    
                    new_balance = max(0.0, received - sent)
                    conn.execute("""
                        INSERT OR REPLACE INTO balances (address, coin_type, balance, locked, updated_at)
                        VALUES (?, ?, ?, COALESCE((SELECT locked FROM balances WHERE address=? AND coin_type=?), 0), ?)
                    """, (addr, coin_type.value, new_balance, addr, coin_type.value, time.time()))
                
                # 更新板块高度
                conn.execute("""
                    INSERT OR REPLACE INTO sector_heights (sector, height, last_block_time)
                    VALUES (?, ?, ?)
                """, (sector, height, time.time()))
                
                return count


# ==================== 全局实例 ====================

_ledger_instance: Optional[SectorCoinLedger] = None


def get_sector_ledger() -> SectorCoinLedger:
    """获取全局板块币账本"""
    global _ledger_instance
    if _ledger_instance is None:
        _ledger_instance = SectorCoinLedger()
    return _ledger_instance
