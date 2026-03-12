"""
贡献权重治理投票模块 (Contribution-Based Governance)

核心设计原则：
1. 投票 = 制度级开关，不参与日常调度
2. 治理权重 = 算力贡献 + 使用贡献 + 锁仓权重
3. 单地址权重上限 5%（防鲸鱼）
4. 提案需押金，通过返还，恶意销毁
5. 投票三选项：支持/反对/弃权
6. 双门槛：参与率 15% + 支持率 66%
7. Timelock 延迟执行

适用范围（制度级）：
✅ 熔断参数调整
✅ 板块启停
✅ 协议费比例调整
✅ 基金会资金方向
✅ 安全策略

不适用（运营级）：
❌ 单个任务分配
❌ 即时处罚
❌ 临时调度
"""

import time
import json
import hashlib
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path
from contextlib import contextmanager
import math


# ============== 常量配置 ==============

class GovernanceConfig:
    """治理配置常量"""
    
    # 权重上限（防鲸鱼）
    MAX_WEIGHT_PERCENT = 5.0           # 单地址最大 5%
    
    # 权重衰减
    DECAY_HALF_LIFE_DAYS = 90          # 90天衰减一半
    
    # 提案押金（MAIN）
    BOND_PARAM = 100                   # 🟢 参数类提案
    BOND_FEATURE = 500                 # 🟡 功能开关提案
    BOND_STRUCTURAL = 2000             # 🔴 结构性提案
    
    # 提案人权重门槛（必须达到此权重才能提交提案）
    MIN_PROPOSER_WEIGHT = 100.0        # 提案人最低权重要求
    MIN_PROPOSER_WEIGHT_PERCENT = 0.1  # 或占全网权重的 0.1%（取较大值）
    
    # 提案通过的最低支持权重（绝对值）
    MIN_SUPPORT_WEIGHT = 1000.0        # 🟢 参数类提案最低支持权重
    MIN_SUPPORT_WEIGHT_FEATURE = 5000.0   # 🟡 功能开关最低支持权重
    MIN_SUPPORT_WEIGHT_STRUCTURAL = 10000.0  # 🔴 结构性提案最低支持权重
    
    # 冷静期
    COOLDOWN_HOURS = 24                # 提案发布后 24 小时冷静期
    
    # 投票期
    VOTING_PERIOD_DAYS = 7             # 标准投票期
    EMERGENCY_VOTING_HOURS = 24        # 紧急投票期
    
    # 提案过期时间（超时未达到门槛自动失效）
    PROPOSAL_EXPIRE_DAYS = 30          # 提案 30 天内未通过则过期
    
    # 通过门槛
    QUORUM_PERCENT = 15.0              # 参与率门槛
    APPROVAL_THRESHOLD = 66.0          # 支持率门槛（普通）
    STRUCTURAL_THRESHOLD = 75.0        # 支持率门槛（结构性）
    
    # Timelock
    TIMELOCK_HOURS = 48                # 延迟执行时间
    
    # 锁仓权重系数
    LOCK_FACTORS = {
        30: 1.0,       # 30天锁仓：1x
        90: 1.5,       # 90天锁仓：1.5x
        180: 2.0,      # 180天锁仓：2x
        365: 3.0,      # 1年锁仓：3x
    }


# ============== 枚举类型 ==============

class ProposalRisk(Enum):
    """提案风险等级"""
    LOW = "low"           # 🟢 参数类
    MEDIUM = "medium"     # 🟡 功能开关
    HIGH = "high"         # 🔴 结构性


class ProposalType(Enum):
    """提案类型"""
    PARAM_CHANGE = "param_change"         # 参数修改
    CIRCUIT_BREAKER = "circuit_breaker"   # 熔断机制
    SECTOR_TOGGLE = "sector_toggle"       # 板块启停
    FEE_ADJUSTMENT = "fee_adjustment"     # 费率调整
    FUND_DIRECTION = "fund_direction"     # 基金会方向
    SECURITY_POLICY = "security_policy"   # 安全策略
    EMERGENCY = "emergency"               # 紧急提案


class ProposalStatus(Enum):
    """提案状态"""
    PENDING = "pending"         # 冷静期
    ACTIVE = "active"           # 投票中
    PASSED = "passed"           # 通过
    REJECTED = "rejected"       # 拒绝
    QUEUED = "queued"           # 等待执行（Timelock）
    EXECUTED = "executed"       # 已执行
    CANCELLED = "cancelled"     # 已取消
    EXPIRED = "expired"         # 已过期


class VoteChoice(Enum):
    """投票选项"""
    SUPPORT = "support"       # 👍 支持
    OPPOSE = "oppose"         # 👎 反对
    ABSTAIN = "abstain"       # 🤍 弃权


class ContributorRole(Enum):
    """贡献者角色"""
    USER = "user"             # 普通用户（租用算力）
    MINER = "miner"           # 矿工（提供 GPU）
    FOUNDATION = "foundation"  # 基金会（无投票权，仅执行）


# ============== 数据结构 ==============

@dataclass
class ContributionRecord:
    """贡献记录"""
    record_id: str
    address: str
    role: ContributorRole
    contribution_type: str     # gpu_hours / main_paid / stake
    amount: float
    sector: str = "MAIN"
    success: bool = True       # 是否成功（失败不计）
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "address": self.address,
            "role": self.role.value,
            "contribution_type": self.contribution_type,
            "amount": self.amount,
            "sector": self.sector,
            "success": self.success,
            "timestamp": self.timestamp
        }


@dataclass
class GovernanceWeight:
    """治理权重"""
    address: str
    power_weight: float = 0.0    # 算力贡献权重
    usage_weight: float = 0.0    # 使用贡献权重
    stake_weight: float = 0.0    # 锁仓权重
    total_weight: float = 0.0    # 总权重
    capped_weight: float = 0.0   # 截断后权重
    cap_applied: bool = False    # 是否被截断
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "power_weight": self.power_weight,
            "usage_weight": self.usage_weight,
            "stake_weight": self.stake_weight,
            "total_weight": self.total_weight,
            "capped_weight": self.capped_weight,
            "cap_applied": self.cap_applied
        }


@dataclass
class ProposalBond:
    """提案押金"""
    bond_id: str
    proposal_id: str
    depositor: str
    amount: float
    status: str = "locked"       # locked / returned / burned
    created_at: float = field(default_factory=time.time)
    settled_at: float = 0.0


@dataclass
class Vote:
    """投票记录"""
    vote_id: str
    proposal_id: str
    voter: str
    choice: VoteChoice
    weight: float               # 投票权重
    block_height: int
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "vote_id": self.vote_id,
            "proposal_id": self.proposal_id,
            "voter": self.voter,
            "choice": self.choice.value,
            "weight": self.weight,
            "block_height": self.block_height,
            "timestamp": self.timestamp
        }


@dataclass
class Proposal:
    """治理提案"""
    proposal_id: str
    proposer: str
    proposal_type: ProposalType
    risk_level: ProposalRisk
    title: str
    description: str
    
    # 变更内容
    target_param: str = ""
    old_value: Any = None
    new_value: Any = None
    changes: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    status: ProposalStatus = ProposalStatus.PENDING
    
    # 时间节点
    created_at: float = field(default_factory=time.time)
    cooldown_ends: float = 0.0
    voting_ends: float = 0.0
    timelock_ends: float = 0.0
    executed_at: float = 0.0
    
    # 投票统计
    votes_support: float = 0.0
    votes_oppose: float = 0.0
    votes_abstain: float = 0.0
    total_voting_power: float = 0.0
    voter_count: int = 0
    
    # 押金
    bond_amount: float = 0.0
    bond_status: str = "locked"   # locked / returned / burned
    
    # 快照块高度
    snapshot_block: int = 0
    
    def __post_init__(self):
        if isinstance(self.proposal_type, str):
            self.proposal_type = ProposalType(self.proposal_type)
        if isinstance(self.risk_level, str):
            self.risk_level = ProposalRisk(self.risk_level)
        if isinstance(self.status, str):
            self.status = ProposalStatus(self.status)
    
    @property
    def participation_rate(self) -> float:
        """参与率"""
        if self.total_voting_power == 0:
            return 0.0
        voted = self.votes_support + self.votes_oppose + self.votes_abstain
        return (voted / self.total_voting_power) * 100
    
    @property
    def approval_rate(self) -> float:
        """支持率（弃权不计）"""
        total = self.votes_support + self.votes_oppose
        if total == 0:
            return 0.0
        return (self.votes_support / total) * 100
    
    def is_quorum_reached(self) -> bool:
        """是否达到法定人数"""
        return self.participation_rate >= GovernanceConfig.QUORUM_PERCENT
    
    def get_threshold(self) -> float:
        """获取通过阈值"""
        if self.risk_level == ProposalRisk.HIGH:
            return GovernanceConfig.STRUCTURAL_THRESHOLD
        return GovernanceConfig.APPROVAL_THRESHOLD
    
    def get_min_support_weight(self) -> float:
        """获取最低支持权重门槛（根据风险等级）"""
        if self.risk_level == ProposalRisk.HIGH:
            return GovernanceConfig.MIN_SUPPORT_WEIGHT_STRUCTURAL
        elif self.risk_level == ProposalRisk.MEDIUM:
            return GovernanceConfig.MIN_SUPPORT_WEIGHT_FEATURE
        return GovernanceConfig.MIN_SUPPORT_WEIGHT
    
    def is_support_weight_sufficient(self) -> bool:
        """支持权重是否达到最低门槛"""
        return self.votes_support >= self.get_min_support_weight()
    
    def is_support_greater_than_oppose(self) -> bool:
        """支持权重是否大于反对权重"""
        return self.votes_support > self.votes_oppose
    
    def is_passed(self) -> bool:
        """是否通过
        
        通过条件（全部满足）：
        1. 参与率达到法定门槛
        2. 支持率达到通过阈值
        3. 支持权重大于反对权重
        4. 支持权重达到最低门槛
        """
        return (
            self.is_quorum_reached() and 
            self.approval_rate >= self.get_threshold() and
            self.is_support_greater_than_oppose() and
            self.is_support_weight_sufficient()
        )
    
    def get_pass_status(self) -> Dict[str, Any]:
        """获取详细通过状态"""
        return {
            "quorum_reached": self.is_quorum_reached(),
            "quorum_required": GovernanceConfig.QUORUM_PERCENT,
            "participation_rate": self.participation_rate,
            "approval_rate": self.approval_rate,
            "threshold_required": self.get_threshold(),
            "support_greater_than_oppose": self.is_support_greater_than_oppose(),
            "votes_support": self.votes_support,
            "votes_oppose": self.votes_oppose,
            "support_weight_sufficient": self.is_support_weight_sufficient(),
            "min_support_required": self.get_min_support_weight(),
            "is_passed": self.is_passed()
        }
    
    def to_dict(self) -> Dict:
        return {
            "proposal_id": self.proposal_id,
            "proposer": self.proposer,
            "proposal_type": self.proposal_type.value,
            "risk_level": self.risk_level.value,
            "title": self.title,
            "description": self.description,
            "target_param": self.target_param,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changes": self.changes,
            "status": self.status.value,
            "created_at": self.created_at,
            "cooldown_ends": self.cooldown_ends,
            "voting_ends": self.voting_ends,
            "timelock_ends": self.timelock_ends,
            "executed_at": self.executed_at,
            "votes_support": self.votes_support,
            "votes_oppose": self.votes_oppose,
            "votes_abstain": self.votes_abstain,
            "total_voting_power": self.total_voting_power,
            "voter_count": self.voter_count,
            "bond_amount": self.bond_amount,
            "bond_status": self.bond_status,
            "snapshot_block": self.snapshot_block,
            # 通过条件统计
            "participation_rate": self.participation_rate,
            "approval_rate": self.approval_rate,
            "threshold": self.get_threshold(),
            "min_support_weight": self.get_min_support_weight(),
            "support_greater_than_oppose": self.is_support_greater_than_oppose(),
            "support_weight_sufficient": self.is_support_weight_sufficient(),
            "quorum_reached": self.is_quorum_reached(),
            "is_passed": self.is_passed(),
            "pass_status": self.get_pass_status()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Proposal':
        return cls(
            proposal_id=data["proposal_id"],
            proposer=data["proposer"],
            proposal_type=ProposalType(data["proposal_type"]),
            risk_level=ProposalRisk(data["risk_level"]),
            title=data["title"],
            description=data["description"],
            target_param=data.get("target_param", ""),
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            changes=data.get("changes", {}),
            status=ProposalStatus(data["status"]),
            created_at=data.get("created_at", time.time()),
            cooldown_ends=data.get("cooldown_ends", 0),
            voting_ends=data.get("voting_ends", 0),
            timelock_ends=data.get("timelock_ends", 0),
            executed_at=data.get("executed_at", 0),
            votes_support=data.get("votes_support", 0),
            votes_oppose=data.get("votes_oppose", 0),
            votes_abstain=data.get("votes_abstain", 0),
            total_voting_power=data.get("total_voting_power", 0),
            voter_count=data.get("voter_count", 0),
            bond_amount=data.get("bond_amount", 0),
            bond_status=data.get("bond_status", "locked"),
            snapshot_block=data.get("snapshot_block", 0)
        )


# ============== 贡献权重计算器 ==============

class ContributionWeightCalculator:
    """
    贡献权重计算器
    
    治理权重 = 算力贡献权重 + 使用贡献权重 + 锁仓权重
    """
    
    def __init__(self, db_path: str = "data/contribution.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
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
            # 贡献记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS contributions (
                    record_id TEXT PRIMARY KEY,
                    address TEXT NOT NULL,
                    role TEXT NOT NULL,
                    contribution_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    sector TEXT DEFAULT 'MAIN',
                    success INTEGER DEFAULT 1,
                    timestamp REAL NOT NULL
                )
            """)
            
            # 锁仓记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stakes (
                    stake_id TEXT PRIMARY KEY,
                    address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    lock_days INTEGER NOT NULL,
                    locked_until REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            # 权重快照表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weight_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    block_height INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    weight_data TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contrib_addr ON contributions(address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contrib_type ON contributions(contribution_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stakes_addr ON stakes(address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_block ON weight_snapshots(block_height)")
    
    def _calculate_decay(self, timestamp: float) -> float:
        """计算时间衰减因子"""
        days_ago = (time.time() - timestamp) / 86400
        half_life = GovernanceConfig.DECAY_HALF_LIFE_DAYS
        return math.pow(0.5, days_ago / half_life)
    
    def record_contribution(self, address: str, role: ContributorRole,
                          contribution_type: str, amount: float,
                          sector: str = "MAIN", success: bool = True) -> str:
        """记录贡献"""
        if not success:
            return ""  # 失败不计
        
        import secrets as _secrets
        # S-3 fix: 使用密码学安全的随机数生成记录 ID
        record_id = hashlib.sha256(
            f"{address}{contribution_type}{amount}{time.time()}{_secrets.token_hex(8)}".encode()
        ).hexdigest()[:16]
        
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO contributions 
                (record_id, address, role, contribution_type, amount, sector, success, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (record_id, address, role.value, contribution_type, 
                  amount, sector, 1 if success else 0, time.time()))
        
        return record_id
    
    def record_gpu_hours(self, miner_address: str, gpu_hours: float,
                        sector: str = "MAIN", success: bool = True) -> str:
        """记录矿工算力贡献（GPU·小时）"""
        return self.record_contribution(
            miner_address, ContributorRole.MINER,
            "gpu_hours", gpu_hours, sector, success
        )
    
    def record_main_paid(self, user_address: str, main_amount: float,
                        sector: str = "MAIN", success: bool = True) -> str:
        """记录用户使用贡献（支付 MAIN）"""
        return self.record_contribution(
            user_address, ContributorRole.USER,
            "main_paid", main_amount, sector, success
        )
    
    def stake(self, address: str, amount: float, lock_days: int) -> Tuple[bool, str]:
        """锁仓质押"""
        if amount <= 0:
            return False, "Amount must be positive"
        if lock_days not in GovernanceConfig.LOCK_FACTORS:
            valid_days = list(GovernanceConfig.LOCK_FACTORS.keys())
            return False, f"Lock days must be one of: {valid_days}"
        
        stake_id = hashlib.sha256(
            f"{address}{amount}{lock_days}{time.time()}".encode()
        ).hexdigest()[:16]
        
        locked_until = time.time() + (lock_days * 86400)
        
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO stakes (stake_id, address, amount, lock_days, locked_until, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (stake_id, address, amount, lock_days, locked_until, time.time()))
        
        return True, stake_id
    
    def unstake(self, stake_id: str, address: str) -> Tuple[bool, str, float]:
        """解除锁仓"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM stakes WHERE stake_id = ? AND address = ?",
                (stake_id, address)
            ).fetchone()
            
            if not row:
                return False, "Stake not found", 0
            
            if row['locked_until'] > time.time():
                remaining = (row['locked_until'] - time.time()) / 86400
                return False, f"Still locked for {remaining:.1f} days", 0
            
            amount = row['amount']
            conn.execute("DELETE FROM stakes WHERE stake_id = ?", (stake_id,))
            return True, "Unstaked successfully", amount
    
    def get_power_weight(self, address: str, days: int = 90) -> float:
        """
        计算算力贡献权重（矿工）
        Power_miner = Σ (GPU_hours × decay(t))
        """
        cutoff = time.time() - (days * 86400)
        
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT amount, timestamp FROM contributions
                WHERE address = ? AND contribution_type = 'gpu_hours'
                AND success = 1 AND timestamp > ?
            """, (address, cutoff)).fetchall()
        
        total = 0.0
        for row in rows:
            decay = self._calculate_decay(row['timestamp'])
            total += row['amount'] * decay
        
        return total
    
    def get_usage_weight(self, address: str, days: int = 90) -> float:
        """
        计算使用贡献权重（用户）
        Power_user = Σ (MAIN_paid × decay(t))
        """
        cutoff = time.time() - (days * 86400)
        
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT amount, timestamp FROM contributions
                WHERE address = ? AND contribution_type = 'main_paid'
                AND success = 1 AND timestamp > ?
            """, (address, cutoff)).fetchall()
        
        total = 0.0
        for row in rows:
            decay = self._calculate_decay(row['timestamp'])
            total += row['amount'] * decay
        
        return total
    
    def get_stake_weight(self, address: str) -> float:
        """
        计算锁仓权重
        Power_stake = Σ (locked_MAIN × lock_factor)
        """
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT amount, lock_days FROM stakes
                WHERE address = ? AND locked_until > ?
            """, (address, time.time())).fetchall()
        
        total = 0.0
        for row in rows:
            factor = GovernanceConfig.LOCK_FACTORS.get(row['lock_days'], 1.0)
            total += row['amount'] * factor
        
        return total
    
    def get_total_weight(self, address: str) -> GovernanceWeight:
        """计算总治理权重"""
        power = self.get_power_weight(address)
        usage = self.get_usage_weight(address)
        stake = self.get_stake_weight(address)
        total = power + usage + stake
        
        return GovernanceWeight(
            address=address,
            power_weight=power,
            usage_weight=usage,
            stake_weight=stake,
            total_weight=total,
            capped_weight=total,  # 稍后在 apply_cap 中处理
            cap_applied=False
        )
    
    def get_network_total_weight(self) -> float:
        """获取全网总权重"""
        with self._conn() as conn:
            # 获取所有有贡献的地址
            addresses = conn.execute("""
                SELECT DISTINCT address FROM contributions WHERE success = 1
                UNION
                SELECT DISTINCT address FROM stakes WHERE locked_until > ?
            """, (time.time(),)).fetchall()
        
        total = 0.0
        for row in addresses:
            weight = self.get_total_weight(row['address'])
            total += weight.total_weight
        
        return total
    
    def apply_cap(self, weight: GovernanceWeight, network_total: float) -> GovernanceWeight:
        """应用权重上限（5%）"""
        if network_total == 0:
            return weight
        
        max_weight = network_total * (GovernanceConfig.MAX_WEIGHT_PERCENT / 100)
        
        if weight.total_weight > max_weight:
            weight.capped_weight = max_weight
            weight.cap_applied = True
        else:
            weight.capped_weight = weight.total_weight
        
        return weight
    
    def create_snapshot(self, block_height: int) -> Dict[str, GovernanceWeight]:
        """创建权重快照（用于投票）"""
        network_total = self.get_network_total_weight()
        
        with self._conn() as conn:
            addresses = conn.execute("""
                SELECT DISTINCT address FROM contributions WHERE success = 1
                UNION
                SELECT DISTINCT address FROM stakes WHERE locked_until > ?
            """, (time.time(),)).fetchall()
        
        snapshots = {}
        snapshot_id_base = hashlib.sha256(
            f"snapshot_{block_height}_{time.time()}".encode()
        ).hexdigest()[:12]
        
        for i, row in enumerate(addresses):
            addr = row['address']
            weight = self.get_total_weight(addr)
            weight = self.apply_cap(weight, network_total)
            snapshots[addr] = weight
            
            # 存储快照
            snap_id = f"{snapshot_id_base}_{i}"
            with self._conn() as conn2:
                conn2.execute("""
                    INSERT INTO weight_snapshots (snapshot_id, block_height, address, weight_data, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (snap_id, block_height, addr, json.dumps(weight.to_dict()), time.time()))
        
        return snapshots
    
    def get_snapshot_weight(self, block_height: int, address: str) -> Optional[GovernanceWeight]:
        """获取快照中的权重"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT weight_data FROM weight_snapshots
                WHERE block_height = ? AND address = ?
            """, (block_height, address)).fetchone()
            
            if row:
                data = json.loads(row['weight_data'])
                return GovernanceWeight(**data)
            return None
    
    def get_snapshot_total(self, block_height: int) -> float:
        """获取快照总权重"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT weight_data FROM weight_snapshots WHERE block_height = ?
            """, (block_height,)).fetchall()
        
        total = 0.0
        for row in rows:
            data = json.loads(row['weight_data'])
            total += data.get('capped_weight', 0)
        
        return total


# ============== 治理引擎 ==============

class ContributionGovernance:
    """
    贡献权重治理引擎
    
    核心特性：
    1. 基于真实贡献的投票权重
    2. 提案押金机制
    3. 冷静期 + 投票期 + Timelock
    4. 双门槛通过机制
    5. 链上规则自动生效
    """
    
    def __init__(self, db_path: str = "data/governance_v3.db",
                 contribution_db: str = "data/contribution.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        self.weight_calc = ContributionWeightCalculator(contribution_db)
        self._executors: Dict[str, Callable] = {}
        self._param_store: Dict[str, Any] = {}
    
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
            # 提案表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    proposal_data TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            # 投票表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    vote_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    voter TEXT NOT NULL,
                    vote_data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE (proposal_id, voter)
                )
            """)
            
            # 押金表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bonds (
                    bond_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    depositor TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'locked',
                    created_at REAL NOT NULL,
                    settled_at REAL DEFAULT 0
                )
            """)
            
            # 执行日志表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT,
                    executed_at REAL NOT NULL
                )
            """)
            
            # 治理参数表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS params (
                    param_key TEXT PRIMARY KEY,
                    param_value TEXT NOT NULL,
                    updated_by TEXT,
                    updated_at REAL NOT NULL
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prop_status ON proposals(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_votes_prop ON votes(proposal_id)")
    
    def _get_bond_amount(self, risk_level: ProposalRisk) -> float:
        """获取押金金额"""
        return {
            ProposalRisk.LOW: GovernanceConfig.BOND_PARAM,
            ProposalRisk.MEDIUM: GovernanceConfig.BOND_FEATURE,
            ProposalRisk.HIGH: GovernanceConfig.BOND_STRUCTURAL,
        }.get(risk_level, GovernanceConfig.BOND_PARAM)
    
    def _get_risk_level(self, proposal_type: ProposalType) -> ProposalRisk:
        """获取提案风险等级"""
        low_risk = [ProposalType.PARAM_CHANGE, ProposalType.FEE_ADJUSTMENT]
        high_risk = [ProposalType.SECURITY_POLICY, ProposalType.SECTOR_TOGGLE]
        
        if proposal_type in low_risk:
            return ProposalRisk.LOW
        elif proposal_type in high_risk:
            return ProposalRisk.HIGH
        else:
            return ProposalRisk.MEDIUM
    
    def is_foundation(self, address: str) -> bool:
        """检查是否为基金会地址（无投票权）"""
        # 基金会地址列表（可配置）
        foundation_addresses = self.get_param("foundation_addresses", [])
        return address in foundation_addresses
    
    def register_executor(self, param_key: str, executor: Callable):
        """注册参数执行器"""
        self._executors[param_key] = executor
    
    # ============== 提案管理 ==============
    
    def get_min_proposer_weight(self) -> float:
        """获取提案人最低权重要求"""
        network_total = self.weight_calc.get_network_total_weight()
        # 取固定值和百分比中的较大值
        fixed_min = GovernanceConfig.MIN_PROPOSER_WEIGHT
        percent_min = network_total * (GovernanceConfig.MIN_PROPOSER_WEIGHT_PERCENT / 100)
        return max(fixed_min, percent_min)
    
    def check_proposer_eligibility(self, proposer: str) -> Tuple[bool, str, float, float]:
        """
        检查提案人是否有资格提交提案
        
        返回: (eligible, reason, proposer_weight, min_required)
        """
        # 基金会无法创建提案
        if self.is_foundation(proposer):
            return False, "Foundation cannot create proposals", 0, 0
        
        # 获取提案人权重
        weight = self.weight_calc.get_total_weight(proposer)
        network_total = self.weight_calc.get_network_total_weight()
        weight = self.weight_calc.apply_cap(weight, network_total)
        
        proposer_weight = weight.capped_weight
        min_required = self.get_min_proposer_weight()
        
        if proposer_weight <= 0:
            return False, "No governance weight (need contribution or stake)", proposer_weight, min_required
        
        if proposer_weight < min_required:
            return False, f"Insufficient weight: {proposer_weight:.2f} < {min_required:.2f} required", proposer_weight, min_required
        
        return True, "Eligible to propose", proposer_weight, min_required
    
    def create_proposal(
        self,
        proposer: str,
        proposal_type: ProposalType,
        title: str,
        description: str,
        target_param: str = "",
        old_value: Any = None,
        new_value: Any = None,
        changes: Dict[str, Any] = None,
        current_block: int = 0
    ) -> Tuple[Optional[Proposal], str]:
        """
        创建提案
        
        提案人资格要求：
        1. 非基金会地址
        2. 权重 >= MIN_PROPOSER_WEIGHT (100)
        3. 或权重 >= 全网权重的 0.1%
        """
        
        # 检查提案人资格
        eligible, reason, proposer_weight, min_required = self.check_proposer_eligibility(proposer)
        if not eligible:
            return None, reason
        
        # 确定风险等级和押金
        risk_level = self._get_risk_level(proposal_type)
        bond_amount = self._get_bond_amount(risk_level)
        
        # 生成提案 ID
        proposal_id = f"P-{int(time.time())}-{hashlib.sha256(title.encode()).hexdigest()[:6]}"
        
        # 计算时间节点
        now = time.time()
        if proposal_type == ProposalType.EMERGENCY:
            cooldown_ends = now  # 无冷静期
            voting_period = GovernanceConfig.EMERGENCY_VOTING_HOURS * 3600
            timelock_delay = 0   # 无延迟
        else:
            cooldown_ends = now + (GovernanceConfig.COOLDOWN_HOURS * 3600)
            voting_period = GovernanceConfig.VOTING_PERIOD_DAYS * 86400
            timelock_delay = GovernanceConfig.TIMELOCK_HOURS * 3600
        
        voting_ends = cooldown_ends + voting_period
        
        # 创建提案
        proposal = Proposal(
            proposal_id=proposal_id,
            proposer=proposer,
            proposal_type=proposal_type,
            risk_level=risk_level,
            title=title,
            description=description,
            target_param=target_param,
            old_value=old_value,
            new_value=new_value,
            changes=changes or {},
            status=ProposalStatus.PENDING,
            created_at=now,
            cooldown_ends=cooldown_ends,
            voting_ends=voting_ends,
            bond_amount=bond_amount,
            snapshot_block=current_block
        )
        
        # 创建权重快照
        self.weight_calc.create_snapshot(current_block)
        proposal.total_voting_power = self.weight_calc.get_snapshot_total(current_block)
        
        try:
            with self._conn() as conn:
                # 保存提案
                conn.execute("""
                    INSERT INTO proposals (proposal_id, proposal_data, status, created_at)
                    VALUES (?, ?, ?, ?)
                """, (proposal.proposal_id, json.dumps(proposal.to_dict()),
                      proposal.status.value, now))
                
                # 记录押金
                bond_id = hashlib.sha256(f"{proposal_id}_bond".encode()).hexdigest()[:16]
                conn.execute("""
                    INSERT INTO bonds (bond_id, proposal_id, depositor, amount, status, created_at)
                    VALUES (?, ?, ?, ?, 'locked', ?)
                """, (bond_id, proposal_id, proposer, bond_amount, now))
            
            return proposal, f"Proposal created. Bond: {bond_amount} MAIN. Cooldown ends: {cooldown_ends}"
        
        except Exception as e:
            return None, str(e)
    
    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """获取提案"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT proposal_data FROM proposals WHERE proposal_id = ?",
                (proposal_id,)
            ).fetchone()
            return Proposal.from_dict(json.loads(row['proposal_data'])) if row else None
    
    def _update_proposal(self, proposal: Proposal):
        """更新提案"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE proposals SET proposal_data = ?, status = ?
                WHERE proposal_id = ?
            """, (json.dumps(proposal.to_dict()), proposal.status.value, proposal.proposal_id))
    
    def activate_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        """激活提案（冷静期结束后）"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "Proposal not found"
        
        if proposal.status != ProposalStatus.PENDING:
            return False, f"Invalid status: {proposal.status.value}"
        
        if time.time() < proposal.cooldown_ends:
            remaining = (proposal.cooldown_ends - time.time()) / 3600
            return False, f"Cooldown not ended: {remaining:.1f} hours remaining"
        
        proposal.status = ProposalStatus.ACTIVE
        self._update_proposal(proposal)
        
        return True, f"Proposal activated. Voting ends at {proposal.voting_ends}"
    
    def get_proposals(self, status: ProposalStatus = None, limit: int = 50) -> List[Proposal]:
        """获取提案列表"""
        with self._conn() as conn:
            if status:
                rows = conn.execute("""
                    SELECT proposal_data FROM proposals WHERE status = ?
                    ORDER BY created_at DESC LIMIT ?
                """, (status.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT proposal_data FROM proposals
                    ORDER BY created_at DESC LIMIT ?
                """, (limit,)).fetchall()
            
            return [Proposal.from_dict(json.loads(r['proposal_data'])) for r in rows]
    
    def check_and_expire_proposals(self) -> List[str]:
        """
        检查并标记过期的提案
        
        过期条件：
        - 状态为 PENDING 或 ACTIVE
        - 创建时间超过 PROPOSAL_EXPIRE_DAYS
        """
        expired_ids = []
        expire_threshold = time.time() - (GovernanceConfig.PROPOSAL_EXPIRE_DAYS * 86400)
        
        # 查找需要过期的提案
        proposals = self.get_proposals()
        for proposal in proposals:
            if proposal.status in [ProposalStatus.PENDING, ProposalStatus.ACTIVE]:
                if proposal.created_at < expire_threshold:
                    proposal.status = ProposalStatus.EXPIRED
                    self._update_proposal(proposal)
                    
                    # 返还部分押金（过期返还 25%）
                    self._return_bond(proposal.proposal_id, 0.25)
                    proposal.bond_status = "expired_partial_return"
                    self._update_proposal(proposal)
                    
                    expired_ids.append(proposal.proposal_id)
        
        return expired_ids
    
    def get_proposal_time_remaining(self, proposal_id: str) -> Dict[str, Any]:
        """
        获取提案剩余时间信息
        """
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return {"error": "Proposal not found"}
        
        now = time.time()
        expire_at = proposal.created_at + (GovernanceConfig.PROPOSAL_EXPIRE_DAYS * 86400)
        
        result = {
            "proposal_id": proposal_id,
            "status": proposal.status.value,
            "created_at": proposal.created_at,
            "expire_at": expire_at,
            "is_expired": now > expire_at,
        }
        
        if proposal.status == ProposalStatus.PENDING:
            result["cooldown_remaining_hours"] = max(0, (proposal.cooldown_ends - now) / 3600)
            result["cooldown_ends"] = proposal.cooldown_ends
        
        if proposal.status == ProposalStatus.ACTIVE:
            result["voting_remaining_hours"] = max(0, (proposal.voting_ends - now) / 3600)
            result["voting_ends"] = proposal.voting_ends
        
        if proposal.status == ProposalStatus.QUEUED:
            result["timelock_remaining_hours"] = max(0, (proposal.timelock_ends - now) / 3600)
            result["timelock_ends"] = proposal.timelock_ends
        
        result["total_remaining_days"] = max(0, (expire_at - now) / 86400)
        
        return result

    # ============== 投票 ==============
    
    def vote(
        self,
        proposal_id: str,
        voter: str,
        choice: VoteChoice,
        current_block: int
    ) -> Tuple[bool, str]:
        """投票"""
        # 基金会无投票权
        if self.is_foundation(voter):
            return False, "Foundation cannot vote (execution only)"
        
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "Proposal not found"
        
        # 检查状态
        if proposal.status != ProposalStatus.ACTIVE:
            # 自动激活（如果冷静期结束）
            if proposal.status == ProposalStatus.PENDING:
                if time.time() >= proposal.cooldown_ends:
                    proposal.status = ProposalStatus.ACTIVE
                    self._update_proposal(proposal)
                else:
                    return False, "Proposal still in cooldown period"
            else:
                return False, f"Proposal not active: {proposal.status.value}"
        
        # 检查投票期
        if time.time() > proposal.voting_ends:
            return False, "Voting period ended"
        
        # 获取快照权重
        weight_obj = self.weight_calc.get_snapshot_weight(proposal.snapshot_block, voter)
        if not weight_obj:
            # 快照不存在，实时计算
            weight_obj = self.weight_calc.get_total_weight(voter)
            network_total = self.weight_calc.get_network_total_weight()
            weight_obj = self.weight_calc.apply_cap(weight_obj, network_total)
        
        if weight_obj.capped_weight <= 0:
            return False, "No voting power"
        
        weight = weight_obj.capped_weight
        
        vote_id = hashlib.sha256(
            f"{proposal_id}{voter}{time.time()}".encode()
        ).hexdigest()[:16]
        
        vote = Vote(
            vote_id=vote_id,
            proposal_id=proposal_id,
            voter=voter,
            choice=choice,
            weight=weight,
            block_height=current_block
        )
        
        try:
            with self._conn() as conn:
                # 检查是否已投票
                existing = conn.execute("""
                    SELECT vote_data FROM votes WHERE proposal_id = ? AND voter = ?
                """, (proposal_id, voter)).fetchone()
                
                if existing:
                    # 撤销之前的投票
                    old_vote = json.loads(existing['vote_data'])
                    old_choice = VoteChoice(old_vote['choice'])
                    old_weight = old_vote['weight']
                    
                    if old_choice == VoteChoice.SUPPORT:
                        proposal.votes_support -= old_weight
                    elif old_choice == VoteChoice.OPPOSE:
                        proposal.votes_oppose -= old_weight
                    else:
                        proposal.votes_abstain -= old_weight
                    
                    # 更新投票
                    conn.execute("""
                        UPDATE votes SET vote_data = ?, created_at = ?
                        WHERE proposal_id = ? AND voter = ?
                    """, (json.dumps(vote.to_dict()), time.time(), proposal_id, voter))
                else:
                    # 新投票
                    conn.execute("""
                        INSERT INTO votes (vote_id, proposal_id, voter, vote_data, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (vote_id, proposal_id, voter, json.dumps(vote.to_dict()), time.time()))
                    proposal.voter_count += 1
                
                # 更新统计
                if choice == VoteChoice.SUPPORT:
                    proposal.votes_support += weight
                elif choice == VoteChoice.OPPOSE:
                    proposal.votes_oppose += weight
                else:
                    proposal.votes_abstain += weight
                
                # 同一事务更新提案
                conn.execute("""
                    UPDATE proposals SET proposal_data = ?, status = ?
                    WHERE proposal_id = ?
                """, (json.dumps(proposal.to_dict()), proposal.status.value, proposal.proposal_id))
            
            return True, f"Voted {choice.value} with weight {weight:.2f}"
        
        except Exception as e:
            return False, str(e)
    
    def get_vote(self, proposal_id: str, voter: str) -> Optional[Vote]:
        """获取投票"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT vote_data FROM votes WHERE proposal_id = ? AND voter = ?
            """, (proposal_id, voter)).fetchone()
            
            if row:
                data = json.loads(row['vote_data'])
                return Vote(
                    vote_id=data['vote_id'],
                    proposal_id=data['proposal_id'],
                    voter=data['voter'],
                    choice=VoteChoice(data['choice']),
                    weight=data['weight'],
                    block_height=data['block_height'],
                    timestamp=data.get('timestamp', 0)
                )
            return None
    
    def get_votes(self, proposal_id: str) -> List[Vote]:
        """获取提案所有投票"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT vote_data FROM votes WHERE proposal_id = ?
            """, (proposal_id,)).fetchall()
            
            votes = []
            for row in rows:
                data = json.loads(row['vote_data'])
                votes.append(Vote(
                    vote_id=data['vote_id'],
                    proposal_id=data['proposal_id'],
                    voter=data['voter'],
                    choice=VoteChoice(data['choice']),
                    weight=data['weight'],
                    block_height=data['block_height'],
                    timestamp=data.get('timestamp', 0)
                ))
            return votes
    
    # ============== 结算与执行 ==============
    
    def finalize_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        """结算提案"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "Proposal not found"
        
        if proposal.status != ProposalStatus.ACTIVE:
            return False, f"Proposal not active: {proposal.status.value}"
        
        if time.time() < proposal.voting_ends:
            remaining = (proposal.voting_ends - time.time()) / 3600
            return False, f"Voting not ended: {remaining:.1f} hours remaining"
        
        # 判断是否通过
        if proposal.is_passed():
            # 需要 Timelock
            if proposal.proposal_type != ProposalType.EMERGENCY:
                proposal.status = ProposalStatus.QUEUED
                proposal.timelock_ends = time.time() + (GovernanceConfig.TIMELOCK_HOURS * 3600)
                msg = f"Passed! Queued for execution. Timelock ends: {proposal.timelock_ends}"
            else:
                proposal.status = ProposalStatus.PASSED
                msg = "Passed! Ready for immediate execution."
            
            # 返还押金
            self._return_bond(proposal.proposal_id)
            proposal.bond_status = "returned"
        else:
            proposal.status = ProposalStatus.REJECTED
            
            # 销毁 50% 押金
            self._burn_bond(proposal.proposal_id, 0.5)
            proposal.bond_status = "partially_burned"
            
            # 构建详细拒绝原因
            reasons = []
            if not proposal.is_quorum_reached():
                reasons.append(f"参与率不足({proposal.participation_rate:.1f}% < {GovernanceConfig.QUORUM_PERCENT}%)")
            if proposal.approval_rate < proposal.get_threshold():
                reasons.append(f"支持率不足({proposal.approval_rate:.1f}% < {proposal.get_threshold()}%)")
            if not proposal.is_support_greater_than_oppose():
                reasons.append(f"支持未超过反对(支持:{proposal.votes_support:.1f} <= 反对:{proposal.votes_oppose:.1f})")
            if not proposal.is_support_weight_sufficient():
                reasons.append(f"支持权重不足({proposal.votes_support:.1f} < {proposal.get_min_support_weight():.1f})")
            
            reason_str = ", ".join(reasons) if reasons else "未满足通过条件"
            msg = f"Rejected: {reason_str}"
        
        self._update_proposal(proposal)
        return True, msg
    
    def execute_proposal(self, proposal_id: str, executor: str = None) -> Tuple[bool, str]:
        """执行提案"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "Proposal not found"
        
        # 检查状态
        if proposal.status == ProposalStatus.QUEUED:
            if time.time() < proposal.timelock_ends:
                remaining = (proposal.timelock_ends - time.time()) / 3600
                return False, f"Timelock not expired: {remaining:.1f} hours remaining"
        elif proposal.status != ProposalStatus.PASSED:
            return False, f"Cannot execute: status is {proposal.status.value}"
        
        # 执行变更
        results = []
        
        # 单一参数变更
        if proposal.target_param and proposal.new_value is not None:
            executor_fn = self._executors.get(proposal.target_param)
            if executor_fn:
                try:
                    result = executor_fn(proposal.target_param, proposal.new_value)
                    results.append(f"{proposal.target_param}: {result}")
                except Exception as e:
                    results.append(f"{proposal.target_param}: ERROR - {e}")
            else:
                self.set_param(proposal.target_param, proposal.new_value, proposal.proposer)
                results.append(f"{proposal.target_param} = {proposal.new_value}")
        
        # 多参数变更
        for key, value in proposal.changes.items():
            executor_fn = self._executors.get(key)
            if executor_fn:
                try:
                    result = executor_fn(key, value)
                    results.append(f"{key}: {result}")
                except Exception as e:
                    results.append(f"{key}: ERROR - {e}")
            else:
                self.set_param(key, value, proposal.proposer)
                results.append(f"{key} = {value}")
        
        # 更新状态
        proposal.status = ProposalStatus.EXECUTED
        proposal.executed_at = time.time()
        self._update_proposal(proposal)
        
        # 记录执行日志
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO execution_log (proposal_id, action, result, executed_at)
                VALUES (?, 'execute', ?, ?)
            """, (proposal_id, json.dumps(results), time.time()))
        
        return True, f"Executed: {'; '.join(results)}"
    
    def cancel_proposal(self, proposal_id: str, canceller: str) -> Tuple[bool, str]:
        """取消提案（仅提案人，且在 PENDING/QUEUED 状态）"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "Proposal not found"
        
        if proposal.proposer != canceller:
            return False, "Only proposer can cancel"
        
        if proposal.status not in [ProposalStatus.PENDING, ProposalStatus.QUEUED]:
            return False, f"Cannot cancel: status is {proposal.status.value}"
        
        proposal.status = ProposalStatus.CANCELLED
        
        # 销毁 100% 押金（主动取消）
        self._burn_bond(proposal.proposal_id, 1.0)
        proposal.bond_status = "burned"
        
        self._update_proposal(proposal)
        return True, "Proposal cancelled. Bond burned."
    
    # ============== 押金管理 ==============
    
    def _return_bond(self, proposal_id: str, return_ratio: float = 1.0):
        """
        返还押金
        
        Args:
            proposal_id: 提案ID
            return_ratio: 返还比例 (1.0 = 全额返还, 0.25 = 返还25%)
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT amount FROM bonds WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            
            if row:
                returned_amount = row['amount'] * return_ratio
                if return_ratio >= 1.0:
                    status = 'returned'
                else:
                    status = f'partial_returned_{return_ratio:.0%}'
                
                conn.execute("""
                    UPDATE bonds SET status = ?, settled_at = ?
                    WHERE proposal_id = ?
                """, (status, time.time(), proposal_id))
    
    def _burn_bond(self, proposal_id: str, burn_ratio: float):
        """销毁押金"""
        with self._conn() as conn:
            # 获取押金
            row = conn.execute(
                "SELECT amount FROM bonds WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            
            if row:
                burned = row['amount'] * burn_ratio
                conn.execute("""
                    UPDATE bonds SET status = ?, settled_at = ?
                    WHERE proposal_id = ?
                """, (f"burned_{burn_ratio:.0%}", time.time(), proposal_id))
    
    # ============== 参数管理 ==============
    
    def set_param(self, key: str, value: Any, updated_by: str = None):
        """设置治理参数"""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO params (param_key, param_value, updated_by, updated_at)
                VALUES (?, ?, ?, ?)
            """, (key, json.dumps(value), updated_by, time.time()))
        self._param_store[key] = value
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取治理参数"""
        if key in self._param_store:
            return self._param_store[key]
        
        with self._conn() as conn:
            row = conn.execute(
                "SELECT param_value FROM params WHERE param_key = ?", (key,)
            ).fetchone()
            
            if row:
                value = json.loads(row['param_value'])
                self._param_store[key] = value
                return value
            return default
    
    def get_all_params(self) -> Dict[str, Any]:
        """获取所有治理参数"""
        with self._conn() as conn:
            rows = conn.execute("SELECT param_key, param_value FROM params").fetchall()
            return {r['param_key']: json.loads(r['param_value']) for r in rows}
    
    # ============== 统计 ==============
    
    def get_stats(self) -> Dict:
        """获取治理统计"""
        with self._conn() as conn:
            proposals = conn.execute("""
                SELECT status, COUNT(*) as count FROM proposals GROUP BY status
            """).fetchall()
            
            total_votes = conn.execute("SELECT COUNT(*) as c FROM votes").fetchone()['c']
            unique_voters = conn.execute(
                "SELECT COUNT(DISTINCT voter) as c FROM votes"
            ).fetchone()['c']
            
            bonds = conn.execute("""
                SELECT status, SUM(amount) as total FROM bonds GROUP BY status
            """).fetchall()
        
        return {
            "proposals_by_status": {r['status']: r['count'] for r in proposals},
            "total_proposals": sum(r['count'] for r in proposals),
            "total_votes": total_votes,
            "unique_voters": unique_voters,
            "bonds_by_status": {r['status']: r['total'] for r in bonds},
            "network_weight": self.weight_calc.get_network_total_weight()
        }
    
    def get_voter_power(self, address: str) -> Dict:
        """获取用户投票权详情"""
        weight = self.weight_calc.get_total_weight(address)
        network_total = self.weight_calc.get_network_total_weight()
        weight = self.weight_calc.apply_cap(weight, network_total)
        
        return {
            "address": address,
            "power_weight": weight.power_weight,
            "usage_weight": weight.usage_weight,
            "stake_weight": weight.stake_weight,
            "total_weight": weight.total_weight,
            "capped_weight": weight.capped_weight,
            "cap_applied": weight.cap_applied,
            "network_percent": (weight.capped_weight / network_total * 100) if network_total > 0 else 0,
            "is_foundation": self.is_foundation(address)
        }
    
    def simulate_vote_impact(self, proposal_id: str, voter: str, choice: VoteChoice) -> Dict:
        """模拟投票影响"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return {"error": "Proposal not found"}
        
        weight = self.weight_calc.get_total_weight(voter)
        network_total = self.weight_calc.get_network_total_weight()
        weight = self.weight_calc.apply_cap(weight, network_total)
        
        # 模拟投票后的结果
        new_support = proposal.votes_support
        new_oppose = proposal.votes_oppose
        new_abstain = proposal.votes_abstain
        
        if choice == VoteChoice.SUPPORT:
            new_support += weight.capped_weight
        elif choice == VoteChoice.OPPOSE:
            new_oppose += weight.capped_weight
        else:
            new_abstain += weight.capped_weight
        
        new_total = new_support + new_oppose + new_abstain
        new_participation = (new_total / proposal.total_voting_power * 100) if proposal.total_voting_power > 0 else 0
        new_approval = (new_support / (new_support + new_oppose) * 100) if (new_support + new_oppose) > 0 else 0
        
        return {
            "your_weight": weight.capped_weight,
            "weight_percent": (weight.capped_weight / proposal.total_voting_power * 100) if proposal.total_voting_power > 0 else 0,
            "before": {
                "participation": proposal.participation_rate,
                "approval": proposal.approval_rate,
                "would_pass": proposal.is_passed()
            },
            "after": {
                "participation": new_participation,
                "approval": new_approval,
                "would_pass": new_participation >= GovernanceConfig.QUORUM_PERCENT and new_approval >= proposal.get_threshold()
            }
        }


# ============== 测试 ==============

if __name__ == "__main__":
    import os
    
    # 清理测试数据
    test_files = [
        "data/test_governance_v3.db",
        "data/test_contribution.db"
    ]
    for f in test_files:
        if os.path.exists(f):
            os.remove(f)
    
    print("=" * 70)
    print("贡献权重治理投票模块测试")
    print("=" * 70)
    
    gov = ContributionGovernance(
        "data/test_governance_v3.db",
        "data/test_contribution.db"
    )
    
    # 1. 模拟贡献记录
    print("\n[1] 模拟贡献记录...")
    
    # Alice: 矿工，大量 GPU 贡献
    for _ in range(50):
        gov.weight_calc.record_gpu_hours("addr_alice", 100.0)
    
    # Bob: 用户，大量使用贡献
    for _ in range(30):
        gov.weight_calc.record_main_paid("addr_bob", 500.0)
    
    # Charlie: 锁仓
    gov.weight_calc.stake("addr_charlie", 10000, 180)  # 180天锁仓
    
    # 显示权重
    for addr in ["addr_alice", "addr_bob", "addr_charlie"]:
        power = gov.get_voter_power(addr)
        print(f"  {addr}:")
        print(f"    算力权重: {power['power_weight']:.2f}")
        print(f"    使用权重: {power['usage_weight']:.2f}")
        print(f"    锁仓权重: {power['stake_weight']:.2f}")
        print(f"    总权重: {power['capped_weight']:.2f} ({power['network_percent']:.1f}%)")
    
    # 2. 创建提案
    print("\n[2] 创建提案...")
    
    proposal, msg = gov.create_proposal(
        proposer="addr_alice",
        proposal_type=ProposalType.CIRCUIT_BREAKER,
        title="调整熔断阈值从 85% 到 92%",
        description="当前熔断阈值过于敏感，建议放宽到 92%",
        target_param="CIRCUIT_BREAKER_THRESHOLD",
        old_value=0.85,
        new_value=0.92,
        current_block=1000
    )
    
    if proposal:
        print(f"  ✅ 提案创建成功")
        print(f"  ID: {proposal.proposal_id}")
        print(f"  风险等级: {proposal.risk_level.value}")
        print(f"  押金: {proposal.bond_amount} MAIN")
        print(f"  冷静期结束: {proposal.cooldown_ends}")
    else:
        print(f"  ❌ 创建失败: {msg}")
    
    # 3. 模拟冷静期结束，激活提案
    print("\n[3] 激活提案...")
    
    # 手动设置冷静期已过（测试用）
    proposal.cooldown_ends = time.time() - 1
    gov._update_proposal(proposal)
    
    ok, msg = gov.activate_proposal(proposal.proposal_id)
    print(f"  {'✅' if ok else '❌'} {msg}")
    
    # 4. 投票
    print("\n[4] 投票...")
    
    # Alice 支持
    ok, msg = gov.vote(proposal.proposal_id, "addr_alice", VoteChoice.SUPPORT, 1001)
    print(f"  Alice 支持: {'✅' if ok else '❌'} {msg}")
    
    # Bob 支持
    ok, msg = gov.vote(proposal.proposal_id, "addr_bob", VoteChoice.SUPPORT, 1002)
    print(f"  Bob 支持: {'✅' if ok else '❌'} {msg}")
    
    # Charlie 反对
    ok, msg = gov.vote(proposal.proposal_id, "addr_charlie", VoteChoice.OPPOSE, 1003)
    print(f"  Charlie 反对: {'✅' if ok else '❌'} {msg}")
    
    # 查看结果
    proposal = gov.get_proposal(proposal.proposal_id)
    print(f"\n  投票统计:")
    print(f"    支持: {proposal.votes_support:.2f}")
    print(f"    反对: {proposal.votes_oppose:.2f}")
    print(f"    弃权: {proposal.votes_abstain:.2f}")
    print(f"    参与率: {proposal.participation_rate:.1f}% (门槛: {GovernanceConfig.QUORUM_PERCENT}%)")
    print(f"    支持率: {proposal.approval_rate:.1f}% (门槛: {proposal.get_threshold()}%)")
    print(f"    会通过: {'是' if proposal.is_passed() else '否'}")
    
    # 5. 模拟投票影响
    print("\n[5] 模拟投票影响...")
    
    # 假设有新用户投反对票
    gov.weight_calc.record_main_paid("addr_dave", 5000.0)
    impact = gov.simulate_vote_impact(proposal.proposal_id, "addr_dave", VoteChoice.OPPOSE)
    print(f"  Dave 如果投反对:")
    print(f"    权重: {impact['your_weight']:.2f} ({impact['weight_percent']:.1f}%)")
    print(f"    投票前通过: {impact['before']['would_pass']}")
    print(f"    投票后通过: {impact['after']['would_pass']}")
    
    # 6. 结算提案
    print("\n[6] 结算提案...")
    
    # 手动设置投票期结束
    proposal.voting_ends = time.time() - 1
    gov._update_proposal(proposal)
    
    ok, msg = gov.finalize_proposal(proposal.proposal_id)
    print(f"  {'✅' if ok else '❌'} {msg}")
    
    proposal = gov.get_proposal(proposal.proposal_id)
    print(f"  状态: {proposal.status.value}")
    print(f"  押金: {proposal.bond_status}")
    
    # 7. 执行提案
    if proposal.status in [ProposalStatus.QUEUED, ProposalStatus.PASSED]:
        print("\n[7] 执行提案...")
        
        # 手动设置 Timelock 结束
        if proposal.status == ProposalStatus.QUEUED:
            proposal.timelock_ends = time.time() - 1
            gov._update_proposal(proposal)
        
        ok, msg = gov.execute_proposal(proposal.proposal_id)
        print(f"  {'✅' if ok else '❌'} {msg}")
        
        # 查看参数
        param = gov.get_param("CIRCUIT_BREAKER_THRESHOLD")
        print(f"  CIRCUIT_BREAKER_THRESHOLD = {param}")
    
    # 8. 统计
    print("\n[8] 治理统计...")
    stats = gov.get_stats()
    print(f"  总提案: {stats['total_proposals']}")
    print(f"  总投票: {stats['total_votes']}")
    print(f"  独立投票者: {stats['unique_voters']}")
    print(f"  全网权重: {stats['network_weight']:.2f}")
    print(f"  状态分布: {stats['proposals_by_status']}")
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
