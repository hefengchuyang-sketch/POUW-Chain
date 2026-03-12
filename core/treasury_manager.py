# -*- coding: utf-8 -*-
"""
财库与费用管理模块 - 透明度与自动化分配

协议层边界声明：
├── 模块：treasury_manager
├── 层级：APPLICATION (应用层)
├── 类别：NON_CONSENSUS (非共识)
├── 共识影响：❌ 无 - 不影响区块共识
├── 资金安全：需要多签和投票治理
└── 确定性要求：✓ 资金操作需要确定性

去中心化治理原则：
1. 任何资金使用都需要经过公开提案和投票
2. 超过阈值的资金需要多签审批
3. 所有资金流动可追溯，接受社区审计
4. 定期生成透明度报告
5. 紧急提案需要更高的通过门槛

透明度要求：
- 所有提案内容公开可查
- 投票记录上链存储
- 资金流向实时可查
- 定期发布审计报告

功能：
1. 费用透明展示：显示所有费用来源和去向
2. 自动化资金分配：根据规则自动分配资金
3. 国库提案系统：社区投票决定国库资金使用
4. 财务报告生成：定期生成财务透明度报告

资金池：
- Platform Fee Pool: 平台费用池
- Mining Reward Pool: 挖矿奖励池
- Development Fund: 开发基金
- Community Fund: 社区基金
- Reserve Fund: 储备金
"""

import time
import json
import hashlib
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from contextlib import contextmanager
from decimal import Decimal, ROUND_DOWN


class FundPool(Enum):
    """资金池类型"""
    PLATFORM_FEE = "platform_fee"       # 平台费用
    MINING_REWARD = "mining_reward"     # 挖矿奖励
    DEVELOPMENT = "development"         # 开发基金
    COMMUNITY = "community"             # 社区基金
    RESERVE = "reserve"                 # 储备金
    STAKING = "staking"                 # 质押池
    TREASURY = "treasury"               # 国库


class TransactionType(Enum):
    """交易类型"""
    DEPOSIT = "deposit"             # 存入
    WITHDRAWAL = "withdrawal"       # 提取
    TRANSFER = "transfer"           # 转账
    FEE = "fee"                     # 费用
    REWARD = "reward"               # 奖励
    REFUND = "refund"               # 退款
    DISTRIBUTION = "distribution"   # 分配
    BURN = "burn"                   # 销毁


class ProposalStatus(Enum):
    """提案状态"""
    DRAFT = "draft"                 # 草稿
    VOTING = "voting"               # 投票中
    PASSED = "passed"               # 已通过
    REJECTED = "rejected"           # 已否决
    EXECUTED = "executed"           # 已执行
    CANCELLED = "cancelled"         # 已取消
    EXPIRED = "expired"             # 已过期


class ProposalType(Enum):
    """提案类型"""
    FUNDING = "funding"             # 资金申请
    PARAMETER = "parameter"         # 参数调整
    EMERGENCY = "emergency"         # 紧急提案
    UPGRADE = "upgrade"             # 升级提案


# 资金分配比例
DEFAULT_DISTRIBUTION = {
    FundPool.DEVELOPMENT: 0.20,     # 20% 开发
    FundPool.COMMUNITY: 0.15,       # 15% 社区
    FundPool.RESERVE: 0.10,         # 10% 储备
    FundPool.TREASURY: 0.55         # 55% 国库
}


# ========== 去中心化治理配置 ==========

class GovernanceConfig:
    """
    治理配置
    
    定义提案和资金操作的门槛要求
    """
    
    # 提案通过门槛
    NORMAL_PROPOSAL_THRESHOLD = 0.50      # 普通提案需要 50% 同意
    EMERGENCY_PROPOSAL_THRESHOLD = 0.67   # 紧急提案需要 67% 同意
    PARAMETER_CHANGE_THRESHOLD = 0.60     # 参数变更需要 60% 同意
    
    # 投票参与率要求
    MIN_PARTICIPATION_RATE = 0.20         # 最低 20% 参与率
    
    # 资金审批门槛
    SMALL_AMOUNT_THRESHOLD = 100          # 小额（自动审批）
    MEDIUM_AMOUNT_THRESHOLD = 1000        # 中额（单签审批）
    LARGE_AMOUNT_THRESHOLD = 10000        # 大额（多签审批）
    
    # 多签要求
    MULTISIG_REQUIRED = 3                 # 大额需要 3 个签名
    MULTISIG_TOTAL = 5                    # 共 5 个签名者
    
    # 提案时间限制
    VOTING_PERIOD_DAYS = 7                # 投票期 7 天
    EXECUTION_DELAY_HOURS = 24            # 执行前等待 24 小时
    
    # 透明度要求
    AUDIT_REPORT_INTERVAL_DAYS = 30       # 每 30 天生成审计报告
    
    @classmethod
    def get_required_threshold(cls, proposal_type: 'ProposalType') -> float:
        """获取提案所需的通过门槛"""
        thresholds = {
            ProposalType.FUNDING: cls.NORMAL_PROPOSAL_THRESHOLD,
            ProposalType.PARAMETER: cls.PARAMETER_CHANGE_THRESHOLD,
            ProposalType.EMERGENCY: cls.EMERGENCY_PROPOSAL_THRESHOLD,
            ProposalType.UPGRADE: cls.PARAMETER_CHANGE_THRESHOLD,
        }
        return thresholds.get(proposal_type, cls.NORMAL_PROPOSAL_THRESHOLD)
    
    @classmethod
    def get_approval_requirement(cls, amount: float) -> Dict[str, Any]:
        """获取资金审批要求"""
        if amount <= cls.SMALL_AMOUNT_THRESHOLD:
            return {
                "level": "auto",
                "description": "自动审批",
                "signatures_required": 0
            }
        elif amount <= cls.MEDIUM_AMOUNT_THRESHOLD:
            return {
                "level": "single",
                "description": "单签审批",
                "signatures_required": 1
            }
        elif amount <= cls.LARGE_AMOUNT_THRESHOLD:
            return {
                "level": "multisig",
                "description": "多签审批",
                "signatures_required": 2
            }
        else:
            return {
                "level": "full_multisig",
                "description": "完整多签审批",
                "signatures_required": cls.MULTISIG_REQUIRED
            }


class AuditTrail:
    """
    审计追踪
    
    记录所有资金操作的完整审计轨迹
    """
    
    @staticmethod
    def create_audit_record(
        action: str,
        actor: str,
        target: str,
        amount: float,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建审计记录"""
        import time
        import hashlib
        
        record = {
            "action": action,
            "actor": actor,
            "target": target,
            "amount": amount,
            "details": details,
            "timestamp": time.time(),
        }
        
        # 计算记录哈希（用于防篡改）
        record_str = json.dumps(record, sort_keys=True)
        record["hash"] = hashlib.sha256(record_str.encode()).hexdigest()
        
        return record
    
    @staticmethod
    def verify_audit_record(record: Dict[str, Any]) -> bool:
        """验证审计记录完整性"""
        import hashlib
        
        stored_hash = record.pop("hash", None)
        if not stored_hash:
            return False
        
        record_str = json.dumps(record, sort_keys=True)
        computed_hash = hashlib.sha256(record_str.encode()).hexdigest()
        
        record["hash"] = stored_hash
        return stored_hash == computed_hash


@dataclass
class FundTransaction:
    """资金交易"""
    tx_id: str
    pool: FundPool
    tx_type: TransactionType
    amount: float
    currency: str = "MAIN"
    
    # 关联
    from_address: str = ""
    to_address: str = ""
    from_pool: Optional[FundPool] = None
    to_pool: Optional[FundPool] = None
    
    # 描述
    description: str = ""
    reference_id: str = ""          # 关联的订单/合约ID
    
    # 区块链
    block_height: int = 0
    tx_hash: str = ""
    
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "tx_id": self.tx_id,
            "pool": self.pool.value,
            "tx_type": self.tx_type.value,
            "amount": self.amount,
            "currency": self.currency,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "from_pool": self.from_pool.value if self.from_pool else None,
            "to_pool": self.to_pool.value if self.to_pool else None,
            "description": self.description,
            "reference_id": self.reference_id,
            "block_height": self.block_height,
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp
        }


@dataclass
class TreasuryProposal:
    """国库提案"""
    proposal_id: str
    title: str
    description: str
    proposal_type: ProposalType
    
    # 申请
    proposer_address: str
    requested_amount: float
    recipient_address: str = ""
    
    # 投票
    votes_for: float = 0            # 赞成票（权重）
    votes_against: float = 0        # 反对票（权重）
    voters: Dict[str, bool] = field(default_factory=dict)  # address -> vote
    
    # 状态
    status: ProposalStatus = ProposalStatus.DRAFT
    
    # 时间
    created_at: float = field(default_factory=time.time)
    voting_start: Optional[float] = None
    voting_end: Optional[float] = None
    executed_at: Optional[float] = None
    
    # 区块链
    block_height: int = 0
    tx_hash: str = ""
    
    def __post_init__(self):
        if not self.proposal_id:
            self.proposal_id = self._generate_id()
    
    def _generate_id(self) -> str:
        data = f"{self.title}{self.proposer_address}{self.created_at}"
        return f"PROP_{hashlib.sha256(data.encode()).hexdigest()[:12]}"
    
    def vote_result(self) -> Tuple[bool, float]:
        """
        投票结果
        返回 (是否通过, 支持率)
        """
        total = self.votes_for + self.votes_against
        if total == 0:
            return False, 0
        
        support_rate = self.votes_for / total
        return support_rate > 0.5, support_rate
    
    def to_dict(self) -> Dict:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "proposal_type": self.proposal_type.value,
            "proposer_address": self.proposer_address,
            "requested_amount": self.requested_amount,
            "recipient_address": self.recipient_address,
            "votes_for": self.votes_for,
            "votes_against": self.votes_against,
            "voter_count": len(self.voters),
            "status": self.status.value,
            "created_at": self.created_at,
            "voting_start": self.voting_start,
            "voting_end": self.voting_end,
            "executed_at": self.executed_at,
            "block_height": self.block_height,
            "tx_hash": self.tx_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TreasuryProposal':
        return cls(
            proposal_id=data["proposal_id"],
            title=data["title"],
            description=data["description"],
            proposal_type=ProposalType(data["proposal_type"]),
            proposer_address=data["proposer_address"],
            requested_amount=data["requested_amount"],
            recipient_address=data.get("recipient_address", ""),
            votes_for=data.get("votes_for", 0),
            votes_against=data.get("votes_against", 0),
            voters=data.get("voters", {}),
            status=ProposalStatus(data.get("status", "draft")),
            created_at=data.get("created_at", time.time()),
            voting_start=data.get("voting_start"),
            voting_end=data.get("voting_end"),
            executed_at=data.get("executed_at"),
            block_height=data.get("block_height", 0),
            tx_hash=data.get("tx_hash", "")
        )


@dataclass
class FeeBreakdown:
    """费用明细"""
    total_fee: float
    
    # 各项费用
    platform_fee: float = 0         # 平台费
    network_fee: float = 0          # 网络费
    miner_fee: float = 0            # 矿工费
    treasury_contribution: float = 0 # 国库贡献
    
    # 分配
    to_miners: float = 0
    to_treasury: float = 0
    to_development: float = 0
    to_community: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "total_fee": round(self.total_fee, 6),
            "breakdown": {
                "platform_fee": round(self.platform_fee, 6),
                "network_fee": round(self.network_fee, 6),
                "miner_fee": round(self.miner_fee, 6),
                "treasury_contribution": round(self.treasury_contribution, 6)
            },
            "distribution": {
                "to_miners": round(self.to_miners, 6),
                "to_treasury": round(self.to_treasury, 6),
                "to_development": round(self.to_development, 6),
                "to_community": round(self.to_community, 6)
            }
        }


class TreasuryManager:
    """
    财库管理器
    
    核心功能：
    1. 资金池管理
    2. 费用计算与分配
    3. 提案系统
    4. 透明度报告
    """
    
    # 费率设置
    PLATFORM_FEE_RATE = 0.05        # 5% 平台费
    NETWORK_FEE_RATE = 0.001        # 0.1% 网络费
    TREASURY_CONTRIBUTION = 0.02    # 2% 国库贡献
    
    # 投票参数
    VOTING_PERIOD = 7 * 24 * 3600   # 7 天投票期
    MIN_PROPOSAL_STAKE = 100        # 最低提案质押
    MIN_QUORUM = 0.1                # 最低参与率 10%
    
    # 最大单笔提案金额（国库的百分比）
    MAX_PROPOSAL_PERCENTAGE = 0.10  # 10%
    
    def __init__(self, db_path: str = "data/treasury.db"):
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
        """初始化数据库"""
        with self._conn() as conn:
            # 资金池余额表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pool_balances (
                    pool TEXT PRIMARY KEY,
                    balance REAL DEFAULT 0,
                    currency TEXT DEFAULT 'MAIN',
                    updated_at REAL
                )
            """)
            
            # 初始化资金池
            for pool in FundPool:
                conn.execute("""
                    INSERT OR IGNORE INTO pool_balances (pool, balance, updated_at)
                    VALUES (?, 0, ?)
                """, (pool.value, time.time()))
            
            # 交易记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fund_transactions (
                    tx_id TEXT PRIMARY KEY,
                    pool TEXT NOT NULL,
                    tx_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'MAIN',
                    from_address TEXT,
                    to_address TEXT,
                    from_pool TEXT,
                    to_pool TEXT,
                    description TEXT,
                    reference_id TEXT,
                    block_height INTEGER,
                    tx_hash TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            
            # 提案表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    proposal_data TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_amount REAL,
                    proposer_address TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL
                )
            """)
            
            # 投票记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposal_votes (
                    proposal_id TEXT NOT NULL,
                    voter_address TEXT NOT NULL,
                    vote INTEGER NOT NULL,
                    weight REAL DEFAULT 1,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (proposal_id, voter_address)
                )
            """)
            
            # 费用统计表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fee_statistics (
                    date TEXT PRIMARY KEY,
                    total_fees REAL DEFAULT 0,
                    platform_fees REAL DEFAULT 0,
                    network_fees REAL DEFAULT 0,
                    treasury_contributions REAL DEFAULT 0,
                    distributed_amount REAL DEFAULT 0
                )
            """)
            
            # 分配规则表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS distribution_rules (
                    pool TEXT PRIMARY KEY,
                    percentage REAL NOT NULL,
                    active INTEGER DEFAULT 1,
                    updated_at REAL
                )
            """)
            
            # 初始化分配规则
            for pool, pct in DEFAULT_DISTRIBUTION.items():
                conn.execute("""
                    INSERT OR IGNORE INTO distribution_rules (pool, percentage, updated_at)
                    VALUES (?, ?, ?)
                """, (pool.value, pct, time.time()))
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_pool ON fund_transactions(pool)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_time ON fund_transactions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_proposal_status ON proposals(status)")
    
    # ============== 资金池管理 ==============
    
    def get_pool_balance(self, pool: FundPool) -> float:
        """获取资金池余额"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT balance FROM pool_balances WHERE pool = ?",
                (pool.value,)
            ).fetchone()
            return row["balance"] if row else 0
    
    def get_all_balances(self) -> Dict[str, float]:
        """获取所有资金池余额"""
        with self._conn() as conn:
            rows = conn.execute("SELECT pool, balance FROM pool_balances").fetchall()
            return {row["pool"]: row["balance"] for row in rows}
    
    def deposit_to_pool(self, pool: FundPool, amount: float,
                         from_address: str = "", description: str = "",
                         reference_id: str = "") -> Tuple[bool, str]:
        """向资金池存入"""
        if amount <= 0:
            return False, "金额必须大于 0"
        
        tx_id = f"TX_{hashlib.sha256(f'{pool.value}{amount}{time.time()}'.encode()).hexdigest()[:12]}"
        
        with self._conn() as conn:
            # 更新余额
            conn.execute("""
                UPDATE pool_balances 
                SET balance = balance + ?, updated_at = ?
                WHERE pool = ?
            """, (amount, time.time(), pool.value))
            
            # 记录交易
            conn.execute("""
                INSERT INTO fund_transactions (
                    tx_id, pool, tx_type, amount, from_address,
                    description, reference_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_id, pool.value, TransactionType.DEPOSIT.value,
                amount, from_address, description, reference_id, time.time()
            ))
        
        return True, f"已存入 {amount} MAIN 到 {pool.value}"
    
    def withdraw_from_pool(self, pool: FundPool, amount: float,
                            to_address: str, description: str = "",
                            reference_id: str = "") -> Tuple[bool, str]:
        """从资金池提取"""
        if amount <= 0:
            return False, "金额必须大于 0"
        
        balance = self.get_pool_balance(pool)
        if amount > balance:
            return False, f"余额不足: {balance}"
        
        tx_id = f"TX_{hashlib.sha256(f'{pool.value}{amount}{time.time()}'.encode()).hexdigest()[:12]}"
        
        with self._conn() as conn:
            # 更新余额
            conn.execute("""
                UPDATE pool_balances 
                SET balance = balance - ?, updated_at = ?
                WHERE pool = ?
            """, (amount, time.time(), pool.value))
            
            # 记录交易
            conn.execute("""
                INSERT INTO fund_transactions (
                    tx_id, pool, tx_type, amount, to_address,
                    description, reference_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_id, pool.value, TransactionType.WITHDRAWAL.value,
                amount, to_address, description, reference_id, time.time()
            ))
        
        return True, f"已从 {pool.value} 提取 {amount} MAIN"
    
    def transfer_between_pools(self, from_pool: FundPool, to_pool: FundPool,
                                amount: float, description: str = "") -> Tuple[bool, str]:
        """资金池间转账"""
        if amount <= 0:
            return False, "金额必须大于 0"
        
        balance = self.get_pool_balance(from_pool)
        if amount > balance:
            return False, f"{from_pool.value} 余额不足: {balance}"
        
        tx_id = f"TX_{hashlib.sha256(f'{from_pool.value}{to_pool.value}{amount}{time.time()}'.encode()).hexdigest()[:12]}"
        
        with self._conn() as conn:
            # 扣减来源
            conn.execute("""
                UPDATE pool_balances 
                SET balance = balance - ?, updated_at = ?
                WHERE pool = ?
            """, (amount, time.time(), from_pool.value))
            
            # 增加目标
            conn.execute("""
                UPDATE pool_balances 
                SET balance = balance + ?, updated_at = ?
                WHERE pool = ?
            """, (amount, time.time(), to_pool.value))
            
            # 记录交易
            conn.execute("""
                INSERT INTO fund_transactions (
                    tx_id, pool, tx_type, amount, from_pool, to_pool,
                    description, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_id, from_pool.value, TransactionType.TRANSFER.value,
                amount, from_pool.value, to_pool.value, description, time.time()
            ))
        
        return True, f"已从 {from_pool.value} 转账 {amount} MAIN 到 {to_pool.value}"
    
    # ============== 费用计算与分配 ==============
    
    def calculate_fees(self, transaction_amount: float) -> FeeBreakdown:
        """
        计算交易费用
        """
        platform_fee = transaction_amount * self.PLATFORM_FEE_RATE
        network_fee = transaction_amount * self.NETWORK_FEE_RATE
        treasury_contribution = transaction_amount * self.TREASURY_CONTRIBUTION
        
        total_fee = platform_fee + network_fee + treasury_contribution
        
        # 获取分配规则
        rules = self._get_distribution_rules()
        
        # 计算分配
        distributable = platform_fee  # 只分配平台费
        to_treasury = distributable * rules.get(FundPool.TREASURY.value, 0.55)
        to_development = distributable * rules.get(FundPool.DEVELOPMENT.value, 0.20)
        to_community = distributable * rules.get(FundPool.COMMUNITY.value, 0.15)
        to_miners = network_fee  # 网络费给矿工
        
        return FeeBreakdown(
            total_fee=total_fee,
            platform_fee=platform_fee,
            network_fee=network_fee,
            miner_fee=0,
            treasury_contribution=treasury_contribution,
            to_miners=to_miners,
            to_treasury=to_treasury + treasury_contribution,
            to_development=to_development,
            to_community=to_community
        )
    
    def collect_and_distribute_fee(self, transaction_amount: float,
                                    reference_id: str = "") -> Tuple[bool, FeeBreakdown]:
        """
        收取并分配费用
        """
        breakdown = self.calculate_fees(transaction_amount)
        
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        
        with self._conn() as conn:
            # 分配到各资金池
            if breakdown.to_treasury > 0:
                conn.execute("""
                    UPDATE pool_balances 
                    SET balance = balance + ?, updated_at = ?
                    WHERE pool = ?
                """, (breakdown.to_treasury, now, FundPool.TREASURY.value))
            
            if breakdown.to_development > 0:
                conn.execute("""
                    UPDATE pool_balances 
                    SET balance = balance + ?, updated_at = ?
                    WHERE pool = ?
                """, (breakdown.to_development, now, FundPool.DEVELOPMENT.value))
            
            if breakdown.to_community > 0:
                conn.execute("""
                    UPDATE pool_balances 
                    SET balance = balance + ?, updated_at = ?
                    WHERE pool = ?
                """, (breakdown.to_community, now, FundPool.COMMUNITY.value))
            
            # 更新费用统计
            conn.execute("""
                INSERT INTO fee_statistics (date, total_fees, platform_fees, network_fees,
                    treasury_contributions, distributed_amount)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_fees = total_fees + ?,
                    platform_fees = platform_fees + ?,
                    network_fees = network_fees + ?,
                    treasury_contributions = treasury_contributions + ?,
                    distributed_amount = distributed_amount + ?
            """, (
                today, breakdown.total_fee, breakdown.platform_fee,
                breakdown.network_fee, breakdown.treasury_contribution,
                breakdown.platform_fee,
                breakdown.total_fee, breakdown.platform_fee,
                breakdown.network_fee, breakdown.treasury_contribution,
                breakdown.platform_fee
            ))
            
            # 记录分配交易
            tx_id = f"DIST_{hashlib.sha256(f'{reference_id}{now}'.encode()).hexdigest()[:12]}"
            conn.execute("""
                INSERT INTO fund_transactions (
                    tx_id, pool, tx_type, amount, description, reference_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_id, FundPool.PLATFORM_FEE.value,
                TransactionType.DISTRIBUTION.value,
                breakdown.total_fee,
                "自动费用分配",
                reference_id, now
            ))
        
        return True, breakdown
    
    def _get_distribution_rules(self) -> Dict[str, float]:
        """获取分配规则"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT pool, percentage FROM distribution_rules WHERE active = 1"
            ).fetchall()
            return {row["pool"]: row["percentage"] for row in rows}
    
    def update_distribution_rule(self, pool: FundPool,
                                  percentage: float) -> Tuple[bool, str]:
        """更新分配规则"""
        if not 0 <= percentage <= 1:
            return False, "百分比必须在 0-1 之间"
        
        # 验证总和不超过 1
        rules = self._get_distribution_rules()
        rules[pool.value] = percentage
        total = sum(rules.values())
        
        if total > 1.0:
            return False, f"总分配比例不能超过 100%，当前总计: {total * 100:.1f}%"
        
        with self._conn() as conn:
            conn.execute("""
                UPDATE distribution_rules 
                SET percentage = ?, updated_at = ?
                WHERE pool = ?
            """, (percentage, time.time(), pool.value))
        
        return True, f"已更新 {pool.value} 分配比例为 {percentage * 100:.1f}%"
    
    # ============== 提案系统 ==============
    
    def create_proposal(self, title: str, description: str,
                        proposer_address: str, requested_amount: float,
                        proposal_type: ProposalType = ProposalType.FUNDING,
                        recipient_address: str = "") -> Tuple[bool, str, Optional[TreasuryProposal]]:
        """创建提案"""
        # 验证金额
        treasury_balance = self.get_pool_balance(FundPool.TREASURY)
        max_amount = treasury_balance * self.MAX_PROPOSAL_PERCENTAGE
        
        if requested_amount > max_amount:
            return False, f"申请金额超过限制: 最大 {max_amount:.2f} MAIN", None
        
        if not recipient_address:
            recipient_address = proposer_address
        
        proposal = TreasuryProposal(
            proposal_id="",
            title=title,
            description=description,
            proposal_type=proposal_type,
            proposer_address=proposer_address,
            requested_amount=requested_amount,
            recipient_address=recipient_address,
            status=ProposalStatus.DRAFT
        )
        
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO proposals (
                    proposal_id, proposal_data, status, requested_amount,
                    proposer_address, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                proposal.proposal_id, json.dumps(proposal.to_dict()),
                proposal.status.value, proposal.requested_amount,
                proposal.proposer_address, proposal.created_at, time.time()
            ))
        
        return True, f"提案已创建: {proposal.proposal_id}", proposal
    
    def start_voting(self, proposal_id: str) -> Tuple[bool, str]:
        """开始投票"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "提案不存在"
        
        if proposal.status != ProposalStatus.DRAFT:
            return False, f"提案状态不允许开始投票: {proposal.status.value}"
        
        proposal.status = ProposalStatus.VOTING
        proposal.voting_start = time.time()
        proposal.voting_end = time.time() + self.VOTING_PERIOD
        
        self._update_proposal(proposal)
        
        return True, f"投票已开始，截止时间: {time.ctime(proposal.voting_end)}"
    
    def vote(self, proposal_id: str, voter_address: str,
             support: bool, weight: float = 1.0) -> Tuple[bool, str]:
        """投票"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "提案不存在"
        
        if proposal.status != ProposalStatus.VOTING:
            return False, "提案不在投票期"
        
        if time.time() > proposal.voting_end:
            self._finalize_proposal(proposal)
            return False, "投票已结束"
        
        # 检查是否已投票
        if voter_address in proposal.voters:
            return False, "您已投过票"
        
        # 记录投票
        proposal.voters[voter_address] = support
        if support:
            proposal.votes_for += weight
        else:
            proposal.votes_against += weight
        
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO proposal_votes (
                    proposal_id, voter_address, vote, weight, timestamp
                ) VALUES (?, ?, ?, ?, ?)
            """, (proposal_id, voter_address, 1 if support else 0, weight, time.time()))
        
        self._update_proposal(proposal)
        
        return True, f"投票成功: {'赞成' if support else '反对'}"
    
    def finalize_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        """结算提案"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "提案不存在"
        
        if proposal.status != ProposalStatus.VOTING:
            return False, "提案不在投票期"
        
        if time.time() < proposal.voting_end:
            return False, "投票尚未结束"
        
        return self._finalize_proposal(proposal)
    
    def _finalize_proposal(self, proposal: TreasuryProposal) -> Tuple[bool, str]:
        """内部结算提案"""
        passed, support_rate = proposal.vote_result()
        
        if passed:
            proposal.status = ProposalStatus.PASSED
            msg = f"提案通过，支持率: {support_rate * 100:.1f}%"
        else:
            proposal.status = ProposalStatus.REJECTED
            msg = f"提案未通过，支持率: {support_rate * 100:.1f}%"
        
        self._update_proposal(proposal)
        
        return True, msg
    
    def execute_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        """执行通过的提案"""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False, "提案不存在"
        
        if proposal.status != ProposalStatus.PASSED:
            return False, "只有通过的提案可以执行"
        
        # 检查余额
        balance = self.get_pool_balance(FundPool.TREASURY)
        if proposal.requested_amount > balance:
            return False, f"国库余额不足: {balance}"
        
        # 执行转账
        ok, msg = self.withdraw_from_pool(
            FundPool.TREASURY,
            proposal.requested_amount,
            proposal.recipient_address,
            f"提案执行: {proposal.title}",
            proposal.proposal_id
        )
        
        if ok:
            proposal.status = ProposalStatus.EXECUTED
            proposal.executed_at = time.time()
            self._update_proposal(proposal)
            return True, f"提案已执行，{proposal.requested_amount} MAIN 已转账"
        
        return False, msg
    
    def get_proposal(self, proposal_id: str) -> Optional[TreasuryProposal]:
        """获取提案"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT proposal_data FROM proposals WHERE proposal_id = ?",
                (proposal_id,)
            ).fetchone()
            
            if row:
                data = json.loads(row["proposal_data"])
                # 获取投票记录
                votes = conn.execute(
                    "SELECT voter_address, vote FROM proposal_votes WHERE proposal_id = ?",
                    (proposal_id,)
                ).fetchall()
                data["voters"] = {v["voter_address"]: bool(v["vote"]) for v in votes}
                return TreasuryProposal.from_dict(data)
        return None
    
    def _update_proposal(self, proposal: TreasuryProposal):
        """更新提案"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE proposals 
                SET proposal_data = ?, status = ?, updated_at = ?
                WHERE proposal_id = ?
            """, (
                json.dumps(proposal.to_dict()),
                proposal.status.value,
                time.time(),
                proposal.proposal_id
            ))
    
    def get_active_proposals(self) -> List[TreasuryProposal]:
        """获取活跃提案"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT proposal_data FROM proposals 
                WHERE status IN ('draft', 'voting', 'passed')
                ORDER BY created_at DESC
            """).fetchall()
        
        return [TreasuryProposal.from_dict(json.loads(r["proposal_data"])) for r in rows]
    
    # ============== 透明度报告 ==============
    
    def generate_report(self, period_days: int = 30) -> Dict:
        """生成财务透明度报告"""
        now = time.time()
        cutoff = now - period_days * 24 * 3600
        
        with self._conn() as conn:
            # 资金池余额
            balances = self.get_all_balances()
            
            # 期间交易统计
            tx_stats = conn.execute("""
                SELECT tx_type, SUM(amount) as total, COUNT(*) as count
                FROM fund_transactions
                WHERE timestamp > ?
                GROUP BY tx_type
            """, (cutoff,)).fetchall()
            
            # 费用统计
            fee_stats = conn.execute("""
                SELECT 
                    SUM(total_fees) as total_fees,
                    SUM(platform_fees) as platform_fees,
                    SUM(network_fees) as network_fees,
                    SUM(treasury_contributions) as treasury_contributions,
                    SUM(distributed_amount) as distributed_amount
                FROM fee_statistics
                WHERE date >= ?
            """, (time.strftime("%Y-%m-%d", time.localtime(cutoff)),)).fetchone()
            
            # 提案统计
            proposal_stats = conn.execute("""
                SELECT status, COUNT(*) as count, SUM(requested_amount) as total_amount
                FROM proposals
                WHERE created_at > ?
                GROUP BY status
            """, (cutoff,)).fetchall()
            
            # 最近交易
            recent_tx = conn.execute("""
                SELECT * FROM fund_transactions
                ORDER BY timestamp DESC LIMIT 20
            """).fetchall()
        
        return {
            "report_period": {
                "days": period_days,
                "from": time.ctime(cutoff),
                "to": time.ctime(now)
            },
            "pool_balances": balances,
            "total_treasury": sum(balances.values()),
            "transaction_summary": {
                row["tx_type"]: {
                    "total": row["total"],
                    "count": row["count"]
                }
                for row in tx_stats
            },
            "fee_summary": {
                "total_fees": fee_stats["total_fees"] or 0,
                "platform_fees": fee_stats["platform_fees"] or 0,
                "network_fees": fee_stats["network_fees"] or 0,
                "treasury_contributions": fee_stats["treasury_contributions"] or 0,
                "distributed_amount": fee_stats["distributed_amount"] or 0
            } if fee_stats else {},
            "proposal_summary": {
                row["status"]: {
                    "count": row["count"],
                    "total_requested": row["total_amount"] or 0
                }
                for row in proposal_stats
            },
            "recent_transactions": [dict(t) for t in recent_tx],
            "distribution_rules": self._get_distribution_rules(),
            "generated_at": time.ctime(now)
        }
    
    def get_transaction_history(self, pool: FundPool = None,
                                  limit: int = 100) -> List[Dict]:
        """获取交易历史"""
        with self._conn() as conn:
            if pool:
                rows = conn.execute("""
                    SELECT * FROM fund_transactions
                    WHERE pool = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (pool.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM fund_transactions
                    ORDER BY timestamp DESC LIMIT ?
                """, (limit,)).fetchall()
        
        return [dict(r) for r in rows]
    
    def get_fee_statistics(self, days: int = 30) -> List[Dict]:
        """获取费用统计"""
        cutoff_date = time.strftime("%Y-%m-%d", 
                                     time.localtime(time.time() - days * 24 * 3600))
        
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM fee_statistics
                WHERE date >= ?
                ORDER BY date ASC
            """, (cutoff_date,)).fetchall()
        
        return [dict(r) for r in rows]


# 全局实例
_treasury_manager: Optional[TreasuryManager] = None

def get_treasury_manager(db_path: str = "data/treasury.db") -> TreasuryManager:
    """获取财库管理器实例"""
    global _treasury_manager
    if _treasury_manager is None:
        _treasury_manager = TreasuryManager(db_path)
    return _treasury_manager
