# -*- coding: utf-8 -*-
"""
算力市场 V3 - 标准化 GPU 时间交易市场

核心设计原则（三条红线）:
1. 执行 ≠ 验证 - 任务只由用户租用的 GPU 执行，验证是轻量级的
2. 租用只用 MAIN - 只能使用 MAIN 主币支付
3. 板块 = 单一 GPU 型号 - 不允许跨板块混用

设计修正:
- ❌ 删除默认并行执行（冗余计算）
- ❌ 删除多数派共识
- ✅ 单次真实执行
- ✅ 验证是可选的轻量级操作
- ✅ FORCED 模式只作用于矿工事先声明的资源

商品定义:
- 在某一板块（GPU 型号）上
- 某一张 GPU
- 连续 T 小时的独占使用权
"""

import time
import json
import hashlib
import sqlite3
import logging
import os as _os
import warnings
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)
import secrets

from .crypto import ECDSASigner, HAS_ECDSA as _HAS_ECDSA

# 是否生产环境 — 生产环境强制要求 ResourceDeclaration 签名
_MARKET_PRODUCTION = _os.environ.get("POUW_ENV", "").lower() in ("production", "mainnet")


# ============== 硬规则定义 ==============

class HardRules:
    """
    硬规则 - 不可违反的协议级约束
    
    这些规则是链上强制执行的，任何违反都会导致交易无效
    """
    # C-09: 统一费率配置（从 fee_config.py 引用）
    from .fee_config import ProtocolFeeRates as _PFR
    PAYMENT_CURRENCY = "MAIN"           # 只能用 MAIN 支付
    
    # 费率规则 (总 1%)
    TOTAL_FEE_RATE = _PFR.TOTAL                 # 1% 总费率
    BURN_FEE_RATE = _PFR.BURN                   # 0.5% 销毁（通缩）
    MINER_FEE_RATE = _PFR.MINER                 # 0.3% 承载交易矿工
    FOUNDATION_FEE_RATE = _PFR.FOUNDATION       # 0.2% 基金会
    
    # 调度规则
    MAX_GPU_PER_ORDER = 8               # 单订单最大 GPU 数
    MAX_DURATION_HOURS = 720            # 最大租用时长（30天）
    MIN_DURATION_HOURS = 1              # 最小租用时长
    
    # 评价规则
    RATING_STAKE_RATIO = 0.001          # 评价需质押费用的 0.1%
    RATING_STAKE_BURN = 1.0             # 质押金 100% 销毁
    
    # 国库限制（不可违反）
    @staticmethod
    def treasury_restrictions() -> Dict[str, bool]:
        """国库硬性限制"""
        return {
            "can_intervene_scheduling": False,      # ❌ 不能干预调度
            "can_freeze_accounts": False,           # ❌ 不能冻结账户
            "can_modify_settlement": False,         # ❌ 不能修改结算结果
            "can_modify_parameters": True,          # ✅ 可以修改参数
            "can_modify_fee_ratio": True,           # ✅ 可以修改费率比例
            "can_approve_upgrades": True,           # ✅ 可以批准升级
        }


# ============== 枚举定义 ==============

class ExecutionMode(Enum):
    """执行模式 - 核心设计修正"""
    EXECUTION = "execution"             # 实际执行任务（默认）
    VALIDATION = "validation"           # 轻量验证（仅高风险任务）


class ScheduleMode(Enum):
    """调度模式"""
    VOLUNTARY = "voluntary"             # 🟢 自主模式：矿工主动接单
    FORCED = "forced"                   # 🔴 强制模式：使用矿工声明的可调度配额
    HYBRID = "hybrid"                   # 🟡 混合模式（默认）：优先自主，不足时使用声明配额


class OrderStatus(Enum):
    """订单状态机"""
    CREATED = "created"                 # 已创建，锁定预算
    MATCHED = "matched"                 # 已匹配卖家
    EXECUTING = "executing"             # 执行中
    SETTLEMENT_PENDING = "settlement_pending"  # 结果已提交，结算待处理
    FINISHED = "finished"               # 完成
    FAILED = "failed"                   # 失败
    CANCELLED = "cancelled"             # 取消


class TaskExecutionMode(Enum):
    """任务执行模式（用户声明）"""
    NORMAL = "normal"                   # 普通执行
    TEE = "tee"                         # 可信执行环境
    ZK = "zk"                           # 零知识证明


class MinerStatus(Enum):
    """矿工状态"""
    OFFLINE = "offline"
    AVAILABLE = "available"             # 可接单
    BUSY = "busy"                       # 执行中
    MINING = "mining"                   # PoUW 挖矿中


class ValidationType(Enum):
    """验证类型（非执行）"""
    HASH_CONSISTENCY = "hash"           # 哈希一致性
    RUNTIME_STATS = "stats"             # 运行时间/资源统计
    RANDOM_SAMPLING = "sampling"        # 随机抽样 slice
    TEE_ATTESTATION = "attestation"     # TEE 远程证明


# ============== 资源声明（核心修正）==============

@dataclass
class ResourceDeclaration:
    """
    矿工资源声明（链上存证）
    
    核心修正：FORCED 模式只能调用矿工事先声明的那部分资源
    系统不能越过矿工事先链上声明的资源边界
    """
    miner_id: str
    address: str                        # 钱包地址
    sector: str                         # GPU 型号（板块）
    
    # GPU 资源声明
    total_gpus: int                     # 总 GPU 数量
    allocatable_gpus: int               # 可被系统调度的 GPU 数量
    forced_ratio: float                 # 强制调度比例 (0.0 - 1.0)
    
    # 定价
    price_floor: float                  # 最低价格 (MAIN / GPU / h)
    
    # 支持的执行模式
    supports_tee: bool = False
    supports_zk: bool = False
    
    # 签名（矿工签署的资源切换合约）
    declaration_hash: str = ""
    signature: str = ""
    declared_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """验证声明合法性"""
        if self.allocatable_gpus > self.total_gpus:
            raise ValueError("allocatable_gpus 不能超过 total_gpus")
        if not 0.0 <= self.forced_ratio <= 1.0:
            raise ValueError("forced_ratio 必须在 0.0 - 1.0 之间")

    def compute_declaration_hash(self) -> str:
        """计算声明数据的规范哈希（用于签名 / 验证）"""
        import json as _json
        canonical = _json.dumps({
            "miner_id": self.miner_id,
            "address": self.address,
            "sector": self.sector,
            "total_gpus": self.total_gpus,
            "allocatable_gpus": self.allocatable_gpus,
            "forced_ratio": self.forced_ratio,
            "price_floor": self.price_floor,
            "supports_tee": self.supports_tee,
            "supports_zk": self.supports_zk,
        }, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_signature(self, miner_public_key: str = "") -> bool:
        """验证矿工对资源声明的 ECDSA 签名。

        Args:
            miner_public_key: 矿工公钥 (hex)。留空时从 address 推断不可行，
                              须由调用方（register_miner）传入。

        Returns:
            True 如果签名有效（或开发模式下降级通过）
        """
        if not self.signature or not miner_public_key:
            if _MARKET_PRODUCTION:
                return False
            # 开发模式：记录警告但仍拒绝未签名声明
            import logging as _logging
            _logging.getLogger('compute_market').warning(
                f"矿工 {self.miner_id} 资源声明缺少签名（非生产模式）"
            )
            return False

        try:
            expected_hash = self.compute_declaration_hash()
            msg = expected_hash.encode()
            sig = bytes.fromhex(self.signature)
            pub = bytes.fromhex(miner_public_key)
            return ECDSASigner.verify(pub, msg, sig)
        except Exception:
            return False
    
    @property
    def forced_gpus(self) -> int:
        """可被强制调度的 GPU 数量"""
        return int(self.allocatable_gpus * self.forced_ratio)
    
    @property
    def voluntary_gpus(self) -> int:
        """自主接单的 GPU 数量"""
        return self.allocatable_gpus - self.forced_gpus
    
    def to_dict(self) -> Dict:
        return {
            "miner_id": self.miner_id,
            "address": self.address,
            "sector": self.sector,
            "total_gpus": self.total_gpus,
            "allocatable_gpus": self.allocatable_gpus,
            "forced_ratio": self.forced_ratio,
            "forced_gpus": self.forced_gpus,
            "voluntary_gpus": self.voluntary_gpus,
            "price_floor": self.price_floor,
            "supports_tee": self.supports_tee,
            "supports_zk": self.supports_zk,
            "declaration_hash": self.declaration_hash,
            "signature": self.signature,
            "declared_at": self.declared_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ResourceDeclaration':
        return cls(
            miner_id=data['miner_id'],
            address=data['address'],
            sector=data['sector'],
            total_gpus=data['total_gpus'],
            allocatable_gpus=data['allocatable_gpus'],
            forced_ratio=data['forced_ratio'],
            price_floor=data['price_floor'],
            supports_tee=data.get('supports_tee', False),
            supports_zk=data.get('supports_zk', False),
            declaration_hash=data.get('declaration_hash', ''),
            signature=data.get('signature', ''),
            declared_at=data.get('declared_at', time.time()),
        )


# ============== 矿工节点 ==============

@dataclass
class MinerNode:
    """矿工节点（算力提供者）"""
    miner_id: str
    address: str
    sector: str                         # GPU 型号
    
    # 资源声明
    declaration: ResourceDeclaration = None
    
    # 当前状态
    status: MinerStatus = MinerStatus.OFFLINE
    available_gpus: int = 0             # 当前可用 GPU
    current_orders: List[str] = field(default_factory=list)
    
    # 评分（系统量化 + 用户评价）
    system_score: float = 1.0           # 系统量化分 (0-2)
    user_rating_weighted: float = 0.0   # 加权用户评分
    user_rating_count: int = 0
    total_stake_burned: float = 0.0     # 已销毁的评价质押金
    
    # 统计
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_earnings: float = 0.0
    
    # 时间
    last_heartbeat: float = field(default_factory=time.time)
    registered_at: float = field(default_factory=time.time)
    
    @property
    def combined_score(self) -> float:
        """综合评分 = 0.6 * 系统分 + 0.4 * 用户评分"""
        system_normalized = min(self.system_score, 2.0) / 2.0
        user_normalized = self.user_rating_weighted / 5.0 if self.user_rating_count > 0 else 0.5
        return 0.6 * system_normalized + 0.4 * user_normalized
    
    def to_dict(self) -> Dict:
        return {
            "miner_id": self.miner_id,
            "address": self.address,
            "sector": self.sector,
            "declaration": self.declaration.to_dict() if self.declaration else None,
            "status": self.status.value,
            "available_gpus": self.available_gpus,
            "current_orders": self.current_orders,
            "system_score": self.system_score,
            "user_rating_weighted": self.user_rating_weighted,
            "user_rating_count": self.user_rating_count,
            "total_stake_burned": self.total_stake_burned,
            "combined_score": self.combined_score,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "total_earnings": self.total_earnings,
            "last_heartbeat": self.last_heartbeat,
            "registered_at": self.registered_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MinerNode':
        declaration = None
        if data.get('declaration'):
            declaration = ResourceDeclaration.from_dict(data['declaration'])
        
        node = cls(
            miner_id=data['miner_id'],
            address=data['address'],
            sector=data['sector'],
            declaration=declaration,
            status=MinerStatus(data.get('status', 'offline')),
            available_gpus=data.get('available_gpus', 0),
            current_orders=data.get('current_orders', []),
            system_score=data.get('system_score', 1.0),
            user_rating_weighted=data.get('user_rating_weighted', 0.0),
            user_rating_count=data.get('user_rating_count', 0),
            total_stake_burned=data.get('total_stake_burned', 0.0),
            tasks_completed=data.get('tasks_completed', 0),
            tasks_failed=data.get('tasks_failed', 0),
            total_earnings=data.get('total_earnings', 0.0),
            last_heartbeat=data.get('last_heartbeat', time.time()),
            registered_at=data.get('registered_at', time.time()),
        )
        return node


# ============== 订单模型 ==============

@dataclass
class ComputeOrder:
    """
    算力订单
    
    商品 = 板块标准化 GPU 时间片
    """
    order_id: str
    buyer_address: str
    
    # 需求（不可变）
    sector: str                         # GPU 型号（板块）
    gpu_count: int                      # GPU 数量（整数）
    duration_hours: int                 # 时长（小时）
    max_price: float                    # 最高单价 (MAIN / GPU / h)
    execution_mode: TaskExecutionMode   # 执行模式
    
    # 任务
    task_hash: str                      # 任务哈希
    task_encrypted_blob: str            # 加密任务数据
    
    # 验证选项
    allow_validation: bool = True       # 是否允许验证
    validation_type: ValidationType = ValidationType.HASH_CONSISTENCY
    
    # 预算（MAIN only）
    total_budget: float = 0.0           # 总预算
    locked_budget: float = 0.0          # 锁定预算
    
    # 分配
    assigned_miners: List[str] = field(default_factory=list)
    assigned_gpus: Dict[str, int] = field(default_factory=dict)  # miner_id -> gpu_count
    
    # 状态
    status: OrderStatus = OrderStatus.CREATED
    
    # 结果
    result_hash: str = ""
    result_encrypted: str = ""

    # 结算状态
    settlement_status: str = "not_settled"    # not_settled / settled / pending
    settlement_error: str = ""
    settlement_attempts: int = 0
    settled_at: float = 0.0
    
    # 时间
    created_at: float = field(default_factory=time.time)
    matched_at: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0
    
    def __post_init__(self):
        """验证订单合法性"""
        if self.gpu_count > HardRules.MAX_GPU_PER_ORDER:
            raise ValueError(f"GPU 数量不能超过 {HardRules.MAX_GPU_PER_ORDER}")
        if self.duration_hours > HardRules.MAX_DURATION_HOURS:
            raise ValueError(f"时长不能超过 {HardRules.MAX_DURATION_HOURS} 小时")
        if self.duration_hours < HardRules.MIN_DURATION_HOURS:
            raise ValueError(f"时长不能少于 {HardRules.MIN_DURATION_HOURS} 小时")
        
        # 计算总预算
        self.total_budget = self.max_price * self.gpu_count * self.duration_hours
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "buyer_address": self.buyer_address,
            "sector": self.sector,
            "gpu_count": self.gpu_count,
            "duration_hours": self.duration_hours,
            "max_price": self.max_price,
            "execution_mode": self.execution_mode.value,
            "task_hash": self.task_hash,
            "task_encrypted_blob": self.task_encrypted_blob,
            "allow_validation": self.allow_validation,
            "validation_type": self.validation_type.value,
            "total_budget": self.total_budget,
            "locked_budget": self.locked_budget,
            "assigned_miners": self.assigned_miners,
            "assigned_gpus": self.assigned_gpus,
            "status": self.status.value,
            "result_hash": self.result_hash,
            "result_encrypted": self.result_encrypted,
            "settlement_status": self.settlement_status,
            "settlement_error": self.settlement_error,
            "settlement_attempts": self.settlement_attempts,
            "settled_at": self.settled_at,
            "created_at": self.created_at,
            "matched_at": self.matched_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ComputeOrder':
        order = cls(
            order_id=data['order_id'],
            buyer_address=data['buyer_address'],
            sector=data['sector'],
            gpu_count=data['gpu_count'],
            duration_hours=data['duration_hours'],
            max_price=data['max_price'],
            execution_mode=TaskExecutionMode(data.get('execution_mode', 'normal')),
            task_hash=data['task_hash'],
            task_encrypted_blob=data.get('task_encrypted_blob', ''),
            allow_validation=data.get('allow_validation', True),
            validation_type=ValidationType(data.get('validation_type', 'hash')),
        )
        order.total_budget = data.get('total_budget', 0.0)
        order.locked_budget = data.get('locked_budget', 0.0)
        order.assigned_miners = data.get('assigned_miners', [])
        order.assigned_gpus = data.get('assigned_gpus', {})
        order.status = OrderStatus(data.get('status', 'created'))
        order.result_hash = data.get('result_hash', '')
        order.result_encrypted = data.get('result_encrypted', '')
        order.settlement_status = data.get('settlement_status', 'not_settled')
        order.settlement_error = data.get('settlement_error', '')
        order.settlement_attempts = data.get('settlement_attempts', 0)
        order.settled_at = data.get('settled_at', 0.0)
        order.created_at = data.get('created_at', time.time())
        order.matched_at = data.get('matched_at', 0.0)
        order.started_at = data.get('started_at', 0.0)
        order.finished_at = data.get('finished_at', 0.0)
        return order


# ============== 用户评价（质押模式）==============

@dataclass
class StakedRating:
    """
    质押评价
    
    规则：
    - 必须质押费用的 0.1%
    - 质押金 100% 销毁
    - 权重与质押金额成正比
    - 无质押评价权重极低
    """
    rating_id: str
    order_id: str
    buyer_address: str
    miner_id: str
    
    # 评分
    rating: float                       # 0-5 星
    comment: str = ""
    
    # 质押
    stake_amount: float = 0.0           # 质押金额（MAIN）
    stake_burned: bool = False          # 是否已销毁
    
    # 权重
    weight: float = 0.0                 # 评价权重
    
    created_at: float = field(default_factory=time.time)
    
    def calculate_weight(self, order_total: float) -> float:
        """计算评价权重"""
        min_stake = order_total * HardRules.RATING_STAKE_RATIO
        if self.stake_amount >= min_stake:
            # 质押足够，权重与金额成正比
            self.weight = self.stake_amount / min_stake
        else:
            # 未质押或质押不足，权重极低
            self.weight = 0.01
        return self.weight


# ============== 算力市场 V3 ==============

class ComputeMarketV3:
    """
    算力市场 V3 - 标准化 GPU 时间交易市场
    
    核心原则：
    1. 执行 ≠ 验证
    2. 租用只用 MAIN
    3. 板块 = 单一 GPU 型号
    """
    
    # 配置
    HEARTBEAT_TIMEOUT = 60              # 心跳超时（秒）
    ORDER_TIMEOUT = 300                 # 订单匹配超时（5分钟）
    WATCHDOG_INTERVAL = 30              # 守护巡检间隔（秒）
    
    def __init__(self, 
                 db_path: str = "data/compute_market_v3.db",
                 schedule_mode: ScheduleMode = ScheduleMode.HYBRID):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schedule_mode = schedule_mode
        
        self._lock = threading.Lock()
        self._init_db()
        
        # 守护线程 — 巡检超时订单和离线矿工
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="market-watchdog"
        )
        self._watchdog_thread.start()
    
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        with self._conn() as conn:
            # 矿工表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS miners (
                    miner_id TEXT PRIMARY KEY,
                    miner_data TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    status TEXT NOT NULL,
                    available_gpus INTEGER DEFAULT 0,
                    combined_score REAL DEFAULT 1.0,
                    last_heartbeat REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            # 资源声明表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS declarations (
                    miner_id TEXT PRIMARY KEY,
                    declaration_data TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    allocatable_gpus INTEGER NOT NULL,
                    forced_ratio REAL NOT NULL,
                    declared_at REAL NOT NULL
                )
            """)
            
            # 订单表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    order_data TEXT NOT NULL,
                    buyer_address TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            # 评价表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ratings (
                    rating_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    miner_id TEXT NOT NULL,
                    rating REAL NOT NULL,
                    stake_amount REAL NOT NULL,
                    weight REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_miners_sector ON miners(sector)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_sector ON orders(sector)")
    
    # ============== 矿工管理 ==============
    
    def register_miner(self, 
                       miner_id: str,
                       address: str,
                       sector: str,
                       declaration: ResourceDeclaration,
                       miner_public_key: str = "") -> Tuple[bool, str]:
        """
        注册矿工（带资源声明）
        
        矿工必须声明可被系统调度的资源边界。
        生产环境要求提供 ECDSA 签名的资源声明。
        """
        # 验证声明
        if declaration.miner_id != miner_id:
            return False, "声明的 miner_id 不匹配"
        if declaration.sector != sector:
            return False, "声明的 sector 不匹配"

        # ---- 验证资源声明签名 ----
        if not declaration.verify_signature(miner_public_key):
            return False, "资源声明签名验证失败"
        # 自动填充 declaration_hash
        if not declaration.declaration_hash:
            declaration.declaration_hash = declaration.compute_declaration_hash()
        
        miner = MinerNode(
            miner_id=miner_id,
            address=address,
            sector=sector,
            declaration=declaration,
            available_gpus=declaration.allocatable_gpus,
        )
        
        with self._conn() as conn:
            # 保存矿工
            conn.execute("""
                INSERT OR REPLACE INTO miners
                (miner_id, miner_data, sector, status, available_gpus, combined_score, last_heartbeat, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                miner_id,
                json.dumps(miner.to_dict()),
                sector,
                MinerStatus.OFFLINE.value,
                miner.available_gpus,
                miner.combined_score,
                time.time(),
                time.time()
            ))
            
            # 保存声明
            conn.execute("""
                INSERT OR REPLACE INTO declarations
                (miner_id, declaration_data, sector, allocatable_gpus, forced_ratio, declared_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                miner_id,
                json.dumps(declaration.to_dict()),
                sector,
                declaration.allocatable_gpus,
                declaration.forced_ratio,
                time.time()
            ))
        
        return True, "矿工注册成功"
    
    def miner_online(self, miner_id: str) -> Tuple[bool, str]:
        """矿工上线"""
        miner = self.get_miner(miner_id)
        if not miner:
            return False, "矿工不存在"
        
        miner.status = MinerStatus.AVAILABLE
        miner.last_heartbeat = time.time()
        miner.available_gpus = miner.declaration.allocatable_gpus if miner.declaration else 0
        
        self._update_miner(miner)
        return True, "已上线"
    
    def miner_offline(self, miner_id: str) -> Tuple[bool, str]:
        """矿工下线"""
        miner = self.get_miner(miner_id)
        if not miner:
            return False, "矿工不存在"
        
        miner.status = MinerStatus.OFFLINE
        self._update_miner(miner)
        return True, "已下线"
    
    def miner_heartbeat(self, miner_id: str) -> Tuple[bool, Optional[ComputeOrder]]:
        """
        矿工心跳
        
        返回：是否有待执行的任务
        """
        miner = self.get_miner(miner_id)
        if not miner:
            return False, None
        
        miner.last_heartbeat = time.time()
        self._update_miner(miner)
        
        # 检查是否有已分配的订单
        if miner.current_orders:
            order = self.get_order(miner.current_orders[0])
            if order and order.status == OrderStatus.MATCHED:
                return True, order
        
        return True, None
    
    def get_miner(self, miner_id: str) -> Optional[MinerNode]:
        """获取矿工"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT miner_data FROM miners WHERE miner_id = ?",
                (miner_id,)
            ).fetchone()
            if row:
                return MinerNode.from_dict(json.loads(row['miner_data']))
        return None
    
    def _update_miner(self, miner: MinerNode):
        """更新矿工"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE miners SET
                    miner_data = ?,
                    status = ?,
                    available_gpus = ?,
                    combined_score = ?,
                    last_heartbeat = ?
                WHERE miner_id = ?
            """, (
                json.dumps(miner.to_dict()),
                miner.status.value,
                miner.available_gpus,
                miner.combined_score,
                miner.last_heartbeat,
                miner.miner_id
            ))
    
    # ============== 订单管理 ==============
    
    def create_order(self,
                     buyer_address: str,
                     sector: str,
                     gpu_count: int,
                     duration_hours: int,
                     max_price: float,
                     task_hash: str,
                     task_encrypted_blob: str = "",
                     execution_mode: TaskExecutionMode = TaskExecutionMode.NORMAL,
                     allow_validation: bool = True) -> Tuple[Optional[ComputeOrder], str]:
        """
        创建订单
        
        硬规则检查：
        1. 只能用 MAIN 支付
        2. 不允许跨板块混用
        3. GPU 数量限制
        """
        # 生成订单 ID
        order_id = hashlib.sha256(
            f"{buyer_address}{time.time()}{secrets.token_hex(8)}".encode()
        ).hexdigest()[:16]
        
        try:
            order = ComputeOrder(
                order_id=order_id,
                buyer_address=buyer_address,
                sector=sector,
                gpu_count=gpu_count,
                duration_hours=duration_hours,
                max_price=max_price,
                execution_mode=execution_mode,
                task_hash=task_hash,
                task_encrypted_blob=task_encrypted_blob,
                allow_validation=allow_validation,
            )
        except ValueError as e:
            logger.error(f"订单创建参数错误: {e}")
            return None, "invalid_order_parameters"
        
        # 锁定预算
        order.locked_budget = order.total_budget
        
        # 保存订单
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO orders
                (order_id, order_data, buyer_address, sector, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                json.dumps(order.to_dict()),
                buyer_address,
                sector,
                OrderStatus.CREATED.value,
                time.time()
            ))
        
        # 尝试匹配
        matched, msg = self._match_order(order)
        
        if matched:
            return order, "订单创建并匹配成功"
        else:
            return order, f"订单创建成功，等待匹配: {msg}"
    
    def _match_order(self, order: ComputeOrder) -> Tuple[bool, str]:
        """
        匹配订单到矿工
        
        调度规则：
        1. GPU 型号匹配
        2. GPU 空闲
        3. execution_mode 支持
        4. 价格 ≤ max_price
        """
        with self._lock:
            # 获取可用矿工
            available = self._get_available_miners_for_order(order)
            
            if not available:
                return False, "暂无可用矿工"
            
            # 按综合评分排序
            available.sort(key=lambda m: m.combined_score, reverse=True)
            
            # 分配 GPU
            remaining_gpus = order.gpu_count
            assigned = []
            assigned_gpus = {}
            
            for miner in available:
                if remaining_gpus <= 0:
                    break
                
                # 检查价格
                if miner.declaration and miner.declaration.price_floor > order.max_price:
                    continue
                
                # 分配
                gpus_to_assign = min(miner.available_gpus, remaining_gpus)
                if gpus_to_assign > 0:
                    assigned.append(miner.miner_id)
                    assigned_gpus[miner.miner_id] = gpus_to_assign
                    remaining_gpus -= gpus_to_assign
            
            if remaining_gpus > 0:
                return False, f"GPU 不足，还需 {remaining_gpus} 张"
            
            # 更新订单
            order.assigned_miners = assigned
            order.assigned_gpus = assigned_gpus
            order.status = OrderStatus.MATCHED
            order.matched_at = time.time()
            self._update_order(order)
            
            # 更新矿工状态
            for miner_id, gpus in assigned_gpus.items():
                miner = self.get_miner(miner_id)
                if miner:
                    miner.available_gpus -= gpus
                    miner.current_orders.append(order.order_id)
                    if miner.available_gpus == 0:
                        miner.status = MinerStatus.BUSY
                    self._update_miner(miner)
            
            return True, f"已匹配 {len(assigned)} 个矿工，共 {order.gpu_count} 张 GPU"
    
    def _get_available_miners_for_order(self, order: ComputeOrder) -> List[MinerNode]:
        """获取订单可用的矿工"""
        with self._conn() as conn:
            # 基础条件：板块匹配 + 在线 + 有可用 GPU
            rows = conn.execute("""
                SELECT miner_data FROM miners
                WHERE sector = ?
                AND status IN ('available', 'mining')
                AND available_gpus > 0
            """, (order.sector,)).fetchall()
            
            miners = []
            for row in rows:
                miner = MinerNode.from_dict(json.loads(row['miner_data']))
                
                # 检查心跳
                if time.time() - miner.last_heartbeat > self.HEARTBEAT_TIMEOUT:
                    continue
                
                # 检查执行模式支持
                if order.execution_mode == TaskExecutionMode.TEE:
                    if not miner.declaration or not miner.declaration.supports_tee:
                        continue
                if order.execution_mode == TaskExecutionMode.ZK:
                    if not miner.declaration or not miner.declaration.supports_zk:
                        continue
                
                # 根据调度模式过滤
                if self.schedule_mode == ScheduleMode.VOLUNTARY:
                    # 自主模式：只使用自愿上线的 GPU
                    if miner.declaration:
                        available = miner.declaration.voluntary_gpus
                        if available <= 0:
                            continue
                        miner.available_gpus = min(miner.available_gpus, available)
                
                elif self.schedule_mode == ScheduleMode.FORCED:
                    # 强制模式：使用声明的可调度 GPU
                    if miner.declaration:
                        available = miner.declaration.forced_gpus
                        if available <= 0:
                            continue
                        miner.available_gpus = min(miner.available_gpus, available)
                
                # HYBRID 模式使用全部可用 GPU
                
                miners.append(miner)
            
            return miners
    
    def get_order(self, order_id: str) -> Optional[ComputeOrder]:
        """获取订单"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT order_data FROM orders WHERE order_id = ?",
                (order_id,)
            ).fetchone()
            if row:
                return ComputeOrder.from_dict(json.loads(row['order_data']))
        return None
    
    def _update_order(self, order: ComputeOrder):
        """更新订单"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE orders SET
                    order_data = ?,
                    status = ?
                WHERE order_id = ?
            """, (
                json.dumps(order.to_dict()),
                order.status.value,
                order.order_id
            ))
    
    # ============== 任务执行（核心修正）==============
    
    def start_execution(self, order_id: str, miner_id: str) -> Tuple[bool, str]:
        """
        开始执行任务
        
        核心原则：
        - 任务只由用户租用的 GPU 执行
        - ❌ 不做冗余并行计算
        - ❌ 不做多数派共识
        """
        order = self.get_order(order_id)
        if not order:
            return False, "订单不存在"
        
        if miner_id not in order.assigned_miners:
            return False, "矿工未被分配到此订单"
        
        if order.status != OrderStatus.MATCHED:
            return False, f"订单状态不正确: {order.status.value}"
        
        order.status = OrderStatus.EXECUTING
        order.started_at = time.time()
        self._update_order(order)
        
        return True, "执行开始"
    
    def submit_result(self,
                      order_id: str,
                      miner_id: str,
                      result_hash: str,
                      result_encrypted: str = "") -> Tuple[bool, str]:
        """
        提交执行结果
        
        核心原则：
        - 单次真实执行
        - 结果直接接受（无多数派共识）
        - 验证是可选的轻量级操作
        """
        order = self.get_order(order_id)
        if not order:
            return False, "订单不存在"
        
        if miner_id not in order.assigned_miners:
            return False, "矿工未被分配到此订单"
        
        if order.status != OrderStatus.EXECUTING:
            return False, f"订单状态不正确: {order.status.value}"
        
        # 先写入执行结果，再尝试结算
        order.result_hash = result_hash
        order.result_encrypted = result_encrypted
        order.settlement_status = "not_settled"
        order.settlement_error = ""
        order.settlement_attempts += 1

        # 执行结算（强一致：结算失败不允许进入 FINISHED）
        settled, settle_msg = self._settle_order(order)

        if settled:
            order.status = OrderStatus.FINISHED
            order.finished_at = time.time()
            order.settlement_status = "settled"
            order.settlement_error = ""
            order.settled_at = time.time()
            self._update_order(order)
        else:
            order.status = OrderStatus.SETTLEMENT_PENDING
            order.finished_at = 0.0
            order.settlement_status = "pending"
            order.settlement_error = settle_msg
            self._update_order(order)
        
        # 执行阶段完成后释放矿工资源；若结算待处理，订单保留 pending 状态用于后续补偿。
        self._release_miners(order)

        if settled:
            return True, "结果已提交，订单完成"
        return False, f"结果已提交，但结算待处理: {settle_msg}"
    
    def _settle_order(self, order: ComputeOrder) -> Tuple[bool, str]:
        """
        结算订单
        
        费用流向（总 1%）：
        - 0.5% 销毁
        - 0.3% 承载交易矿工
        - 0.2% 基金会
        - 剩余 99% → 执行矿工
        """
        total = order.locked_budget
        
        # 扣除费用
        burn_amount = total * HardRules.BURN_FEE_RATE
        miner_fee = total * HardRules.MINER_FEE_RATE
        foundation_fee = total * HardRules.FOUNDATION_FEE_RATE
        
        # 矿工收益
        miner_payment = total * (1 - HardRules.TOTAL_FEE_RATE)

        miner_distribution = {
            mid: miner_payment * (gpus / order.gpu_count)
            for mid, gpus in order.assigned_gpus.items()
        } if order.gpu_count > 0 else {}

        if not miner_distribution:
            return False, "no_assigned_miners"
        
        # 链上结算
        if hasattr(self, '_settlement_fn') and self._settlement_fn:
            try:
                self._settlement_fn(
                    order_id=order.order_id,
                    buyer=order.buyer_address,
                    miners=miner_distribution,
                    burn=burn_amount,
                    foundation_fee=foundation_fee,
                )
            except Exception as settle_err:
                logger.error(f"结算失败: order={order.order_id}, err={settle_err}")
                return False, str(settle_err)
        else:
            logger.warning(
                f"结算待处理: order={order.order_id}, total={total:.4f}. "
                f"需配置 _settlement_fn 回调。"
            )
            return False, "settlement_fn_not_configured"

        # 链上结算成功后再入账矿工收益，避免账实不一致。
        for miner_id, payment in miner_distribution.items():
            miner = self.get_miner(miner_id)
            if miner:
                miner.total_earnings += payment
                miner.tasks_completed += 1
                self._update_miner(miner)

        return True, "ok"
    
    def _release_miners(self, order: ComputeOrder):
        """释放矿工资源"""
        for miner_id, gpus in order.assigned_gpus.items():
            miner = self.get_miner(miner_id)
            if miner:
                miner.available_gpus += gpus
                if order.order_id in miner.current_orders:
                    miner.current_orders.remove(order.order_id)
                if not miner.current_orders:
                    miner.status = MinerStatus.AVAILABLE
                self._update_miner(miner)
    
    # ============== 守护巡检 ==============
    
    def _watchdog_loop(self):
        """后台守护线程 — 定时巡检超时订单和离线矿工
        
        解决矿工断电/掉线后订单永久卡住的问题：
        1. MATCHED 状态超过 ORDER_TIMEOUT 未开始执行 → 释放矿工，重新匹配
        2. EXECUTING 状态中矿工全部心跳超时 → 标记失败，退还预算
        3. 心跳超时的矿工 → 标记离线
        """
        while self._watchdog_running:
            try:
                self._retry_pending_settlements()
                self._handle_expired_orders()
                self._handle_offline_miners_watchdog()
            except Exception as watchdog_err:
                logger.error(f"守护巡检异常: {watchdog_err}")
            
            for _ in range(self.WATCHDOG_INTERVAL):
                if not self._watchdog_running:
                    return
                time.sleep(1)
    
    def _handle_expired_orders(self):
        """扫描并处理超时订单"""
        now = time.time()
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT order_data FROM orders
                WHERE status IN ('matched', 'executing')
            """).fetchall()
        
        for row in rows:
            order = ComputeOrder.from_dict(json.loads(row['order_data']))
            
            if order.status == OrderStatus.MATCHED:
                # MATCHED 超过 ORDER_TIMEOUT 未开始执行
                if now - order.matched_at > self.ORDER_TIMEOUT:
                    self._timeout_order(order, "匹配后未在规定时间内开始执行")
            
            elif order.status == OrderStatus.EXECUTING:
                # EXECUTING 中检查所有分配矿工的心跳
                all_dead = True
                for miner_id in order.assigned_miners:
                    miner = self.get_miner(miner_id)
                    if miner and (now - miner.last_heartbeat) <= self.HEARTBEAT_TIMEOUT:
                        all_dead = False
                        break
                
                if all_dead and order.assigned_miners:
                    # 所有执行矿工都离线了
                    elapsed = now - order.started_at
                    # 给予宽限期（2 倍心跳超时）再判定失败
                    if elapsed > self.HEARTBEAT_TIMEOUT * 2:
                        self._timeout_order(order, "所有执行矿工离线，任务无法继续")
                
                # 额外检查：执行时间超过租用时长（duration_hours）
                if order.started_at > 0:
                    max_duration = order.duration_hours * 3600 + 300  # +5min 宽限
                    if now - order.started_at > max_duration:
                        self._timeout_order(order, "执行时间超过租用时长")

    def _retry_pending_settlements(self):
        """守护线程重试待结算订单。"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT order_data FROM orders
                WHERE status = 'settlement_pending'
            """).fetchall()

        for row in rows:
            order = ComputeOrder.from_dict(json.loads(row['order_data']))
            self._retry_settlement_order(order)

    def retry_settlement(self, order_id: str) -> Tuple[bool, str]:
        """手动重试某个订单的结算。"""
        order = self.get_order(order_id)
        if not order:
            return False, "订单不存在"
        if order.status != OrderStatus.SETTLEMENT_PENDING:
            return False, f"订单不在待结算状态: {order.status.value}"
        return self._retry_settlement_order(order)

    def _retry_settlement_order(self, order: ComputeOrder) -> Tuple[bool, str]:
        """重试结算并更新状态。"""
        order.settlement_attempts += 1
        settled, settle_msg = self._settle_order(order)

        if settled:
            order.status = OrderStatus.FINISHED
            order.finished_at = time.time()
            order.settlement_status = "settled"
            order.settlement_error = ""
            order.settled_at = time.time()
            self._update_order(order)
            return True, "结算重试成功"

        order.settlement_status = "pending"
        order.settlement_error = settle_msg
        self._update_order(order)
        return False, f"结算重试失败: {settle_msg}"
    
    def _timeout_order(self, order: ComputeOrder, reason: str):
        """将订单标记为失败并释放资源"""
        with self._lock:
            order.status = OrderStatus.FAILED
            order.finished_at = time.time()
            
            # 记录失败原因（附加到 order 的扩展字段）
            order_dict = order.to_dict()
            order_dict["failure_reason"] = reason
            order_dict["refund_eligible"] = True
            
            # 释放矿工资源
            self._release_miners(order)
            
            # 惩罚离线矿工（降低评分）
            now = time.time()
            for miner_id in order.assigned_miners:
                miner = self.get_miner(miner_id)
                if miner and (now - miner.last_heartbeat) > self.HEARTBEAT_TIMEOUT:
                    miner.tasks_failed += 1
                    miner.pouw_score = max(miner.pouw_score - 0.05, 0.1)
                    self._update_miner(miner)
            
            self._update_order(order)
    
    def _handle_offline_miners_watchdog(self):
        """扫描心跳超时的矿工，标记离线"""
        now = time.time()
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT miner_data FROM miners
                WHERE status IN ('available', 'busy', 'mining')
            """).fetchall()
        
        for row in rows:
            miner = MinerNode.from_dict(json.loads(row['miner_data']))
            if now - miner.last_heartbeat > self.HEARTBEAT_TIMEOUT:
                miner.status = MinerStatus.OFFLINE
                self._update_miner(miner)
    
    def close(self):
        """停止守护线程"""
        self._watchdog_running = False
        if self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=5)
    
    # ============== 验证机制（非执行）==============
    
    def request_validation(self,
                           order_id: str,
                           validation_type: ValidationType) -> Tuple[bool, str]:
        """
        请求验证（可选，非默认）
        
        验证 ≠ 重复计算
        
        验证方式：
        - 哈希一致性
        - 运行时间/资源统计
        - 随机抽样 slice
        - TEE 远程证明
        """
        order = self.get_order(order_id)
        if not order:
            return False, "订单不存在"
        
        if order.status != OrderStatus.FINISHED:
            return False, "订单未完成，无法验证"
        
        if not order.allow_validation:
            return False, "订单不允许验证"
        
        # 根据验证类型执行
        if validation_type == ValidationType.HASH_CONSISTENCY:
            # 验证结果哈希（最轻量）
            if order.result_hash:
                return True, f"哈希验证通过: {order.result_hash[:16]}..."
            return False, "无结果哈希"
        
        elif validation_type == ValidationType.RUNTIME_STATS:
            # 验证运行时统计
            duration = order.finished_at - order.started_at
            expected = order.duration_hours * 3600
            if duration <= expected * 1.1:  # 允许 10% 误差
                return True, f"运行时间验证通过: {duration:.1f}s"
            return False, f"运行时间异常: {duration:.1f}s"
        
        elif validation_type == ValidationType.TEE_ATTESTATION:
            # TEE 远程证明
            if order.execution_mode != TaskExecutionMode.TEE:
                return False, "订单未使用 TEE 模式"
            # 验证订单的 TEE 认证报告
            attestation = getattr(order, 'tee_attestation', None)
            if not attestation:
                return False, "订单缺少 TEE 认证报告"
            # 检查必要的认证字段
            if not isinstance(attestation, dict):
                return False, "TEE 认证报告格式无效"
            required_fields = ['mrenclave', 'mrsigner', 'report_id', 'is_valid']
            for f in required_fields:
                if f not in attestation:
                    return False, f"TEE 认证报告缺少字段: {f}"
            if not attestation.get('is_valid', False):
                return False, "TEE 认证报告验证未通过"
            # 检查认证是否过期
            expiry = attestation.get('expiry', 0)
            if expiry > 0 and expiry < time.time():
                return False, "TEE 认证报告已过期"
            return True, f"TEE 证明验证通过: {attestation.get('report_id', '')[:16]}"
        
        return False, f"不支持的验证类型: {validation_type.value}"
    
    # ============== 用户评价（质押模式）==============
    
    def submit_rating(self,
                      order_id: str,
                      buyer_address: str,
                      miner_id: str,
                      rating: float,
                      stake_amount: float = 0.0,
                      comment: str = "") -> Tuple[bool, str]:
        """
        提交评价（质押模式）
        
        规则：
        - 必须质押费用的 0.1%
        - 质押金 100% 销毁
        - 权重与质押金额成正比
        """
        order = self.get_order(order_id)
        if not order:
            return False, "订单不存在"
        
        if order.buyer_address != buyer_address:
            return False, "只有买家可以评价"
        
        if miner_id not in order.assigned_miners:
            return False, "矿工未参与此订单"
        
        if not 0 <= rating <= 5:
            return False, "评分必须在 0-5 之间"
        
        # 创建评价
        rating_id = hashlib.sha256(
            f"{order_id}{miner_id}{time.time()}".encode()
        ).hexdigest()[:12]
        
        staked_rating = StakedRating(
            rating_id=rating_id,
            order_id=order_id,
            buyer_address=buyer_address,
            miner_id=miner_id,
            rating=rating,
            comment=comment,
            stake_amount=stake_amount,
        )
        
        # 计算权重
        staked_rating.calculate_weight(order.total_budget)
        
        # 销毁质押金
        if stake_amount > 0:
            burn_executed = False
            if hasattr(self, '_burn_fn') and self._burn_fn:
                try:
                    burn_executed = self._burn_fn(buyer_address, stake_amount)
                except Exception as burn_err:
                    logger.error(f"质押销毁失败: {burn_err}")
            if not burn_executed:
                # 无销毁回调时，记录待处理的销毁操作
                logger.warning(
                    f"质押销毁待处理: buyer={buyer_address}, amount={stake_amount}, "
                    f"rating_id={rating_id}. 需配置 _burn_fn 回调。"
                )
            staked_rating.stake_burned = burn_executed
        
        # 保存评价
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO ratings
                (rating_id, order_id, miner_id, rating, stake_amount, weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                rating_id, order_id, miner_id, rating, stake_amount,
                staked_rating.weight, time.time()
            ))
        
        # 更新矿工评分
        miner = self.get_miner(miner_id)
        if miner:
            # 加权平均
            total_weight = miner.user_rating_count + staked_rating.weight
            if total_weight > 0:
                miner.user_rating_weighted = (
                    miner.user_rating_weighted * miner.user_rating_count +
                    rating * staked_rating.weight
                ) / total_weight
            miner.user_rating_count += 1
            miner.total_stake_burned += stake_amount
            self._update_miner(miner)
        
        return True, f"评价已提交，权重: {staked_rating.weight:.2f}"
    
    # ============== 市场统计 ==============
    
    def get_market_stats(self, sector: str = None) -> Dict:
        """获取市场统计"""
        with self._conn() as conn:
            query = "SELECT * FROM miners"
            if sector:
                query += f" WHERE sector = '{sector}'"
            
            rows = conn.execute(query).fetchall()
            
            total_miners = len(rows)
            online_miners = sum(1 for r in rows if r['status'] in ('available', 'mining'))
            total_gpus = sum(r['available_gpus'] for r in rows)
            
            return {
                "sector": sector or "ALL",
                "total_miners": total_miners,
                "online_miners": online_miners,
                "total_available_gpus": total_gpus,
                "schedule_mode": self.schedule_mode.value,
            }


# ============== 测试 ==============

if __name__ == "__main__":
    print("=" * 60)
    print("算力市场 V3 测试")
    print("核心原则: 执行≠验证 | 只用MAIN | 板块=单一GPU型号")
    print("=" * 60)
    
    # 创建市场
    market = ComputeMarketV3(db_path="data/test_market_v3.db")
    
    # 1. 注册矿工（带资源声明）
    print("\n[1] 注册矿工...")
    declaration = ResourceDeclaration(
        miner_id="miner_001",
        address="MAIN_wallet_001",
        sector="H100",
        total_gpus=8,
        allocatable_gpus=6,     # 6 张可被调度
        forced_ratio=0.3,       # 其中 30% 可被强制调度
        price_floor=1.2,
    )
    
    ok, msg = market.register_miner(
        miner_id="miner_001",
        address="MAIN_wallet_001",
        sector="H100",
        declaration=declaration
    )
    print(f"    注册: {msg}")
    print(f"    可强制调度 GPU: {declaration.forced_gpus}")
    print(f"    自主接单 GPU: {declaration.voluntary_gpus}")
    
    # 矿工上线
    ok, msg = market.miner_online("miner_001")
    print(f"    上线: {msg}")
    
    # 2. 创建订单
    print("\n[2] 创建订单...")
    order, msg = market.create_order(
        buyer_address="buyer_001",
        sector="H100",
        gpu_count=4,
        duration_hours=12,
        max_price=2.0,
        task_hash="0xabc123...",
        task_encrypted_blob="encrypted_task_data",
        execution_mode=TaskExecutionMode.NORMAL,
        allow_validation=True
    )
    
    if order:
        print(f"    订单ID: {order.order_id}")
        print(f"    状态: {order.status.value}")
        print(f"    总预算: {order.total_budget} MAIN")
        print(f"    分配矿工: {order.assigned_miners}")
        print(f"    分配GPU: {order.assigned_gpus}")
    else:
        print(f"    创建失败: {msg}")
    
    # 3. 执行任务
    if order and order.status == OrderStatus.MATCHED:
        print("\n[3] 执行任务...")
        ok, msg = market.start_execution(order.order_id, "miner_001")
        print(f"    开始执行: {msg}")
        
        # 提交结果
        ok, msg = market.submit_result(
            order.order_id,
            "miner_001",
            result_hash="0xresult_hash_123",
            result_encrypted="encrypted_result"
        )
        print(f"    提交结果: {msg}")
        
        # 验证（可选）
        print("\n[4] 验证结果（可选）...")
        ok, msg = market.request_validation(
            order.order_id,
            ValidationType.HASH_CONSISTENCY
        )
        print(f"    哈希验证: {msg}")
    
    # 5. 提交评价
    if order:
        print("\n[5] 提交评价（质押模式）...")
        ok, msg = market.submit_rating(
            order.order_id,
            "buyer_001",
            "miner_001",
            rating=4.5,
            stake_amount=0.01,  # 质押 0.01 MAIN
            comment="服务优秀"
        )
        print(f"    评价: {msg}")
    
    # 6. 市场统计
    print("\n[6] 市场统计...")
    stats = market.get_market_stats("H100")
    for k, v in stats.items():
        print(f"    {k}: {v}")
    
    print("\n" + "=" * 60)
    print("测试完成")
