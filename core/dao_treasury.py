"""
dao_treasury.py - DAO 国库与去中心化治理

Phase 9 功能：
1. 国库多签 / DAO 治理
2. 费用分配参数链上治理
3. 重大参数变更需投票
4. 提案系统
5. 投票机制
"""

import time
import uuid
import hashlib
import threading
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from collections import defaultdict
import json
import sqlite3
import os


# ============== 枚举类型 ==============

class ProposalType(Enum):
    """提案类型"""
    PARAMETER_CHANGE = "parameter_change"      # 参数变更
    FEE_ADJUSTMENT = "fee_adjustment"          # 费用调整
    TREASURY_SPEND = "treasury_spend"          # 国库支出
    UPGRADE = "upgrade"                        # 系统升级
    EMERGENCY = "emergency"                    # 紧急提案
    GOVERNANCE = "governance"                  # 治理规则变更
    SIGNER_ROTATION = "signer_rotation"        # 多签签名者轮换（去中心化治理）
    SECTOR_ADD = "sector_add"                  # 新增板块（需社区投票）
    SECTOR_DEACTIVATE = "sector_deactivate"    # 废除板块（需社区投票）


class ProposalStatus(Enum):
    """提案状态"""
    DRAFT = "draft"                    # 草稿
    ACTIVE = "active"                  # 投票中
    PASSED = "passed"                  # 已通过
    REJECTED = "rejected"              # 已否决
    EXECUTED = "executed"              # 已执行
    EXPIRED = "expired"                # 已过期
    CANCELLED = "cancelled"            # 已取消


class VoteType(Enum):
    """投票类型"""
    FOR = "for"                        # 赞成
    AGAINST = "against"                # 反对
    ABSTAIN = "abstain"                # 弃权


class GovernanceParameter(Enum):
    """治理参数"""
    PLATFORM_FEE_RATE = "platform_fee_rate"            # 平台费率
    MINER_REWARD_RATE = "miner_reward_rate"            # 矿工奖励率
    MIN_STAKE = "min_stake"                            # 最低质押
    PROPOSAL_THRESHOLD = "proposal_threshold"          # 提案门槛
    QUORUM = "quorum"                                  # 法定人数
    VOTING_PERIOD = "voting_period"                    # 投票期
    EXECUTION_DELAY = "execution_delay"                # 执行延迟


# ============== 数据结构 ==============

@dataclass
class TreasuryAccount:
    """国库账户"""
    account_id: str = "treasury_main"
    
    # 余额
    balance: float = 0
    locked_balance: float = 0          # 锁定余额（待执行的支出）
    
    # 收入统计
    total_income: float = 0
    fee_income: float = 0
    penalty_income: float = 0
    
    # 支出统计
    total_spent: float = 0
    
    # 多签
    multisig_threshold: int = 3        # 需要 3/5 签名
    multisig_signers: List[str] = field(default_factory=list)  # signer_id 列表
    multisig_pubkeys: Dict[str, str] = field(default_factory=dict)  # signer_id -> public_key (hex)
    
    # 时间
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "account_id": self.account_id,
            "balance": self.balance,
            "locked_balance": self.locked_balance,
            "available_balance": self.balance - self.locked_balance,
            "total_income": self.total_income,
            "total_spent": self.total_spent,
            "multisig_threshold": self.multisig_threshold,
            "signers_count": len(self.multisig_signers),
        }


@dataclass
class Proposal:
    """提案"""
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    proposal_type: ProposalType = ProposalType.PARAMETER_CHANGE
    
    # 提案者
    proposer: str = ""
    proposer_stake: float = 0          # 提案者质押
    
    # 内容
    title: str = ""
    description: str = ""
    
    # 变更详情
    changes: List[Dict] = field(default_factory=list)  # 参数变更列表
    execution_payload: Dict = field(default_factory=dict)  # 执行数据
    
    # 时间
    created_at: float = field(default_factory=time.time)
    voting_starts: float = 0
    voting_ends: float = 0
    execution_time: float = 0          # 通过后的执行时间
    
    # 投票统计
    votes_for: float = 0               # 赞成票（权重）
    votes_against: float = 0           # 反对票
    votes_abstain: float = 0           # 弃权票
    voter_count: int = 0
    
    # 状态
    status: ProposalStatus = ProposalStatus.DRAFT
    executed: bool = False
    executed_at: float = 0
    execution_tx: str = ""
    
    # 链上
    on_chain: bool = False
    tx_hash: str = ""
    
    # H-10: 投票快照 — 提案创建时冻结质押状态，防止投票期间质押操纵
    stake_snapshot: Dict = field(default_factory=dict)  # {address: stake_amount}
    
    def total_votes(self) -> float:
        """总投票权重"""
        return self.votes_for + self.votes_against + self.votes_abstain
    
    def approval_rate(self) -> float:
        """通过率"""
        total = self.votes_for + self.votes_against
        if total == 0:
            return 0
        return self.votes_for / total * 100
    
    def to_dict(self) -> Dict:
        return {
            "proposal_id": self.proposal_id,
            "type": self.proposal_type.value,
            "proposer": self.proposer,
            "title": self.title,
            "description": self.description,
            "changes": self.changes,
            "status": self.status.value,
            "votes": {
                "for": self.votes_for,
                "against": self.votes_against,
                "abstain": self.votes_abstain,
                "total": self.total_votes(),
                "approval_rate": self.approval_rate(),
            },
            "voter_count": self.voter_count,
            "voting_starts": self.voting_starts,
            "voting_ends": self.voting_ends,
            "created_at": self.created_at,
        }


@dataclass
class Vote:
    """投票记录"""
    vote_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    proposal_id: str = ""
    voter: str = ""                    # 投票者 DID 或地址
    
    vote_type: VoteType = VoteType.FOR
    voting_power: float = 0            # 投票权重（基于质押）
    
    reason: str = ""                   # 投票理由
    
    voted_at: float = field(default_factory=time.time)
    
    # 链上
    tx_hash: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "vote_id": self.vote_id,
            "proposal_id": self.proposal_id,
            "voter": self.voter,
            "vote_type": self.vote_type.value,
            "voting_power": self.voting_power,
            "voted_at": self.voted_at,
        }


@dataclass
class GovernanceConfig:
    """治理配置"""
    # C-09: 算力市场费率参数（可由 DAO 投票修改）
    # 注意区分：这是算力订单结算的分配比例，不是协议级交易手续费
    from .fee_config import ComputeMarketFeeRates as _CMF
    platform_fee_rate: float = _CMF.PLATFORM      # 5% 平台费
    miner_reward_rate: float = _CMF.MINER          # 90% 给矿工
    treasury_rate: float = _CMF.TREASURY           # 5% 进国库
    
    # 质押参数
    min_stake_to_vote: float = 100         # 最低投票质押
    min_stake_to_propose: float = 1000     # 最低提案质押
    
    # 投票参数
    voting_period_days: int = 7            # 投票期
    execution_delay_days: int = 2          # 执行延迟
    quorum_percent: float = 10             # 法定人数 (10%)
    approval_threshold: float = 50         # 通过阈值 (50%)
    min_unique_voters: int = 3             # D-17 fix: 最少独立投票人数（防止单人通过提案）
    
    # 紧急提案
    emergency_quorum: float = 20           # 紧急提案法定人数
    emergency_threshold: float = 66        # 紧急提案通过阈值
    emergency_voting_hours: int = 24       # 紧急投票时长
    emergency_min_voters: int = 5          # D-17 fix: 紧急提案最少投票人数


# ============== 国库管理器 ==============

class TreasuryManager:
    """国库管理器"""
    
    # 创世预拨：网络启动时国库的种子资金，用于早期补偿等场景
    GENESIS_SEED_FUND = 1000.0
    
    # 防滥用：自动补偿的频率和总量限制
    DAILY_COMPENSATE_CAP = 100.0         # 每日自动补偿总上限（MAIN）
    PER_MINER_DAILY_CAP = 20.0           # 每个矿工每日最多获得的自动补偿（MAIN）
    PER_MINER_DAILY_COUNT = 5            # 每个矿工每日最多触发补偿次数
    
    def __init__(self):
        self.treasury = TreasuryAccount()
        self.transactions: List[Dict] = []
        self._lock = threading.RLock()
        
        # 补偿欠条：国库余额不足时记录待补发的债务
        self.pending_debts: List[Dict] = []
        
        # 防滥用：每日补偿跟踪
        self._daily_compensate_total: float = 0.0
        self._daily_compensate_date: str = ""
        self._per_miner_daily: Dict[str, Dict] = {}  # {miner: {"amount": float, "count": int}}
        
        # 创世预拨种子资金（通过 deposit 记录交易，确保可追溯）
        self.deposit(
            amount=self.GENESIS_SEED_FUND,
            source="genesis_seed",
            category="genesis",
        )
        
        # 初始化签名者
        self._init_signers()
    
    def _init_signers(self):
        """初始化多签签名者及其公钥"""
        # 默认 5 个签名者
        self.treasury.multisig_signers = [
            "signer_foundation",
            "signer_dev_team",
            "signer_community_1",
            "signer_community_2",
            "signer_community_3",
        ]
        self.treasury.multisig_threshold = 3
        
        # 自动生成临时密钥对（生产环境应从配置/链上加载真实公钥）
        # Auto-generate keypairs for initial setup; production should load real pubkeys
        try:
            from ecdsa import SigningKey, SECP256k1
            for signer_id in self.treasury.multisig_signers:
                if signer_id not in self.treasury.multisig_pubkeys:
                    sk = SigningKey.generate(curve=SECP256k1)
                    vk = sk.get_verifying_key()
                    self.treasury.multisig_pubkeys[signer_id] = vk.to_string().hex()
        except ImportError:
            pass  # ecdsa not available; pubkeys must be set manually
    
    def deposit(
        self,
        amount: float,
        source: str,
        category: str = "fee",
    ) -> Dict:
        """存入国库"""
        with self._lock:
            self.treasury.balance += amount
            self.treasury.total_income += amount
            
            if category == "fee":
                self.treasury.fee_income += amount
            elif category == "penalty":
                self.treasury.penalty_income += amount
            
            self.treasury.last_updated = time.time()
            
            tx = {
                "tx_id": uuid.uuid4().hex[:12],
                "type": "deposit",
                "amount": amount,
                "source": source,
                "category": category,
                "time": time.time(),
                "balance_after": self.treasury.balance,
            }
            self.transactions.append(tx)
            
            # 每次入账后尝试清偿欠条
            self._settle_pending_debts()
            
            return tx
    
    def request_withdrawal(
        self,
        amount: float,
        recipient: str,
        purpose: str,
        proposal_id: str = None,
    ) -> Dict:
        """请求提款"""
        with self._lock:
            available = self.treasury.balance - self.treasury.locked_balance
            if amount > available:
                return {"error": f"Insufficient balance. Available: {available}"}
            
            # 锁定金额
            self.treasury.locked_balance += amount
            
            return {
                "request_id": uuid.uuid4().hex[:12],
                "amount": amount,
                "recipient": recipient,
                "purpose": purpose,
                "proposal_id": proposal_id,
                "status": "pending_signatures",
                "required_signatures": self.treasury.multisig_threshold,
                "signatures": [],
            }
    
    def execute_withdrawal(
        self,
        request_id: str,
        amount: float,
        recipient: str,
        signatures: List[Dict[str, str]],
    ) -> Dict:
        """执行提款（需要多签 + ECDSA 密码学验证）
        
        Args:
            signatures: 签名列表，每项为 {"signer_id": str, "signature": hex_str}
                        签名对象为 f"{request_id}{amount}{recipient}" 的 SHA256 摘要
        """
        with self._lock:
            # 构造待验证消息
            message = f"{request_id}{amount}{recipient}".encode()
            msg_hash = hashlib.sha256(message).digest()
            
            # 密码学验证每个签名
            valid_signers: List[str] = []
            seen_signers: Set[str] = set()  # 防止同一签名者重复签名
            
            for sig_entry in signatures:
                if not isinstance(sig_entry, dict):
                    continue
                signer_id = sig_entry.get("signer_id", "")
                sig_hex = sig_entry.get("signature", "")
                
                # 检查签名者是否为合法多签成员
                if signer_id not in self.treasury.multisig_signers:
                    continue
                
                # 防止同一签名者重复签名
                if signer_id in seen_signers:
                    continue
                
                # 获取签名者公钥
                pubkey_hex = self.treasury.multisig_pubkeys.get(signer_id)
                if not pubkey_hex:
                    continue
                
                # ECDSA 签名验证（DER 编码，与 ECDSASigner 一致）
                try:
                    from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
                    from ecdsa.util import sigdecode_der
                    vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
                    vk.verify(bytes.fromhex(sig_hex), msg_hash, sigdecode=sigdecode_der)
                    valid_signers.append(signer_id)
                    seen_signers.add(signer_id)
                except ImportError:
                    return {"error": "ecdsa library required for multisig verification"}
                except (BadSignatureError, ValueError, Exception):
                    # 签名无效，跳过此签名
                    continue
            
            if len(valid_signers) < self.treasury.multisig_threshold:
                return {
                    "error": f"Insufficient valid signatures. Required: {self.treasury.multisig_threshold}, Got: {len(valid_signers)}"
                }
            
            # 验证余额
            if amount > self.treasury.locked_balance:
                return {"error": "Amount not locked"}
            
            # 执行转账
            self.treasury.balance -= amount
            self.treasury.locked_balance -= amount
            self.treasury.total_spent += amount
            self.treasury.last_updated = time.time()
            
            tx = {
                "tx_id": uuid.uuid4().hex[:12],
                "type": "withdrawal",
                "amount": amount,
                "recipient": recipient,
                "signatures": valid_signers,
                "time": time.time(),
                "balance_after": self.treasury.balance,
            }
            self.transactions.append(tx)
            
            return tx
    
    def get_balance(self) -> Dict:
        """获取余额"""
        with self._lock:
            return self.treasury.to_dict()
    
    # 系统自动补偿单笔上限（MAIN），防止滥用
    AUTO_COMPENSATE_MAX = 10.0
    
    def _reset_daily_if_needed(self):
        """如果日期变更，重置每日补偿计数器（在 _lock 内调用）"""
        today = time.strftime("%Y-%m-%d")
        if today != self._daily_compensate_date:
            self._daily_compensate_date = today
            self._daily_compensate_total = 0.0
            self._per_miner_daily = {}
    
    def _check_compensate_limits(self, recipient: str, amount: float) -> Optional[str]:
        """检查防滥用限制，返回 None 表示通过，否则返回错误信息（在 _lock 内调用）"""
        self._reset_daily_if_needed()
        
        # 单笔上限
        if amount > self.AUTO_COMPENSATE_MAX:
            return f"Auto-compensate capped at {self.AUTO_COMPENSATE_MAX} MAIN per tx"
        
        # 每日总量上限
        if self._daily_compensate_total + amount > self.DAILY_COMPENSATE_CAP:
            return f"Daily auto-compensate cap reached ({self.DAILY_COMPENSATE_CAP} MAIN/day)"
        
        # 每矿工每日限额
        miner_stats = self._per_miner_daily.get(recipient, {"amount": 0.0, "count": 0})
        if miner_stats["amount"] + amount > self.PER_MINER_DAILY_CAP:
            return f"Miner daily compensate cap reached ({self.PER_MINER_DAILY_CAP} MAIN/day)"
        if miner_stats["count"] >= self.PER_MINER_DAILY_COUNT:
            return f"Miner daily compensate count limit reached ({self.PER_MINER_DAILY_COUNT}/day)"
        
        return None
    
    def _record_compensate_usage(self, recipient: str, amount: float):
        """记录补偿使用量（在 _lock 内调用）"""
        self._daily_compensate_total += amount
        if recipient not in self._per_miner_daily:
            self._per_miner_daily[recipient] = {"amount": 0.0, "count": 0}
        self._per_miner_daily[recipient]["amount"] += amount
        self._per_miner_daily[recipient]["count"] += 1
    
    def auto_compensate(
        self,
        recipient: str,
        amount: float,
        reason: str,
        task_id: str = "",
    ) -> Dict:
        """系统自动补偿（无需多签，限小额）。
        
        用于上传超时等场景下自动补偿矿工带宽成本。
        防滥用限制：单笔上限、每日总量上限、每矿工每日上限及次数限制。
        借贷周期限制：矿工必须偿还已有欠条后才能获得下一笔补偿。
        超限需通过正常多签提案。
        """
        with self._lock:
            if amount <= 0:
                return {"error": "Amount must be positive"}
            
            # 借贷周期检查：矿工存在未偿还欠条时不可再借
            existing_debts = [
                d for d in self.pending_debts if d["recipient"] == recipient
            ]
            if existing_debts:
                return {
                    "error": f"Miner has {len(existing_debts)} outstanding debt(s) "
                             f"totaling {sum(d['amount'] for d in existing_debts):.4f} MAIN. "
                             f"Must repay before next compensation.",
                    "outstanding_debts": len(existing_debts),
                }
            
            # 防滥用检查
            limit_error = self._check_compensate_limits(recipient, amount)
            if limit_error:
                return {"error": limit_error}
            
            available = self.treasury.balance - self.treasury.locked_balance
            if amount > available:
                # 余额不足：记录欠条，后续国库收入时自动补发
                debt = {
                    "debt_id": uuid.uuid4().hex[:12],
                    "recipient": recipient,
                    "amount": amount,
                    "reason": reason,
                    "task_id": task_id,
                    "created_at": time.time(),
                }
                self.pending_debts.append(debt)
                self._record_compensate_usage(recipient, amount)
                return {
                    "deferred": True,
                    "debt_id": debt["debt_id"],
                    "amount": amount,
                    "reason": f"Treasury insufficient ({available:.4f}), compensation deferred",
                }
            
            self.treasury.balance -= amount
            self.treasury.total_spent += amount
            self.treasury.last_updated = time.time()
            self._record_compensate_usage(recipient, amount)
            
            tx = {
                "tx_id": uuid.uuid4().hex[:12],
                "type": "auto_compensate",
                "amount": amount,
                "recipient": recipient,
                "reason": reason,
                "task_id": task_id,
                "time": time.time(),
                "balance_after": self.treasury.balance,
            }
            self.transactions.append(tx)
            return tx
    
    def get_transactions(self, limit: int = 50) -> List[Dict]:
        """获取交易记录"""
        with self._lock:
            return self.transactions[-limit:]
    
    def _settle_pending_debts(self):
        """尝试清偿待补发的欠条（在 _lock 内调用）"""
        if not self.pending_debts:
            return
        
        settled = []
        for debt in self.pending_debts:
            available = self.treasury.balance - self.treasury.locked_balance
            if debt["amount"] > available:
                break  # 余额不够，后面的也别试了
            
            self.treasury.balance -= debt["amount"]
            self.treasury.total_spent += debt["amount"]
            self.treasury.last_updated = time.time()
            
            tx = {
                "tx_id": uuid.uuid4().hex[:12],
                "type": "debt_settlement",
                "amount": debt["amount"],
                "recipient": debt["recipient"],
                "reason": debt["reason"],
                "task_id": debt.get("task_id", ""),
                "debt_id": debt["debt_id"],
                "original_time": debt["created_at"],
                "time": time.time(),
                "balance_after": self.treasury.balance,
            }
            self.transactions.append(tx)
            settled.append(debt)
        
        for d in settled:
            self.pending_debts.remove(d)


# ============== DAO 治理系统 ==============

class DAOGovernance:
    """DAO 治理系统"""
    
    def __init__(self, treasury: TreasuryManager = None, data_dir: str = "./data"):
        self.treasury = treasury or TreasuryManager()
        self.config = GovernanceConfig()
        self.proposals: Dict[str, Proposal] = {}
        self.votes: Dict[str, List[Vote]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # 质押记录
        self.stakes: Dict[str, float] = {}
        
        # 投票历史
        self.voter_history: Dict[str, List[str]] = defaultdict(list)
        
        # SQLite 持久化
        self._db_path = os.path.join(data_dir, "dao_governance.db")
        os.makedirs(data_dir, exist_ok=True)
        self._init_db()
        self._load_state()
    
    # ============== 持久化层 ==============
    
    def _get_db(self) -> sqlite3.Connection:
        """获取线程本地数据库连接"""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    
    def _init_db(self):
        """初始化 DAO 持久化表"""
        conn = self._get_db()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS dao_stakes (
                    address TEXT PRIMARY KEY,
                    amount REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dao_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dao_votes (
                    vote_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    voter TEXT NOT NULL,
                    data TEXT NOT NULL,
                    voted_at REAL NOT NULL,
                    UNIQUE(proposal_id, voter)
                );
                CREATE TABLE IF NOT EXISTS dao_treasury_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()
    
    def _load_state(self):
        """从 SQLite 加载所有 DAO 状态"""
        conn = self._get_db()
        try:
            # 加载质押
            for row in conn.execute("SELECT address, amount FROM dao_stakes WHERE amount > 0"):
                self.stakes[row[0]] = row[1]
            
            # 加载提案
            for row in conn.execute("SELECT proposal_id, data FROM dao_proposals"):
                try:
                    data = json.loads(row[1])
                    proposal = Proposal(
                        proposal_id=data["proposal_id"],
                        proposal_type=ProposalType(data["proposal_type"]),
                        proposer=data["proposer"],
                        title=data["title"],
                        description=data.get("description", ""),
                        changes=data.get("changes", {}),
                        status=ProposalStatus(data["status"]),
                        votes_for=data.get("votes_for", 0),
                        votes_against=data.get("votes_against", 0),
                        votes_abstain=data.get("votes_abstain", 0),
                        voter_count=data.get("voter_count", 0),
                        voting_starts=data.get("voting_starts", 0),
                        voting_ends=data.get("voting_ends", 0),
                        executed=data.get("executed", False),
                    )
                    if data.get("voters"):
                        proposal.voters = set(data["voters"])
                    self.proposals[row[0]] = proposal
                except Exception:
                    pass
            
            # 加载投票
            for row in conn.execute("SELECT proposal_id, data FROM dao_votes"):
                try:
                    data = json.loads(row[1])
                    vote = Vote(
                        vote_id=data["vote_id"],
                        proposal_id=data["proposal_id"],
                        voter=data["voter"],
                        vote_type=VoteType(data["vote_type"]),
                        voting_power=data.get("voting_power", 0),
                        reason=data.get("reason", ""),
                        voted_at=data.get("voted_at", 0),
                    )
                    self.votes[row[0]].append(vote)
                except Exception:
                    pass
            
            # 加载国库余额
            row = conn.execute("SELECT value FROM dao_treasury_state WHERE key='balance'").fetchone()
            if row:
                self.treasury.treasury.balance = float(row[0])
        finally:
            conn.close()
    
    def _save_stake(self, address: str):
        """持久化单个质押记录"""
        conn = self._get_db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO dao_stakes (address, amount, updated_at) VALUES (?, ?, ?)",
                (address, self.stakes.get(address, 0), time.time())
            )
            conn.commit()
        finally:
            conn.close()
    
    def _save_proposal(self, proposal: 'Proposal'):
        """持久化单个提案"""
        conn = self._get_db()
        try:
            data = {
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type.value,
                "proposer": proposal.proposer,
                "title": proposal.title,
                "description": proposal.description,
                "changes": proposal.changes,
                "status": proposal.status.value,
                "votes_for": proposal.votes_for,
                "votes_against": proposal.votes_against,
                "votes_abstain": proposal.votes_abstain,
                "voter_count": proposal.voter_count,
                "voting_starts": proposal.voting_starts,
                "voting_ends": proposal.voting_ends,
                "executed": proposal.executed,
                "voters": list(getattr(proposal, 'voters', set())),
            }
            conn.execute(
                "INSERT OR REPLACE INTO dao_proposals (proposal_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (proposal.proposal_id, json.dumps(data), proposal.voting_starts, time.time())
            )
            conn.commit()
        finally:
            conn.close()
    
    def _save_vote(self, vote: 'Vote'):
        """持久化投票记录"""
        conn = self._get_db()
        try:
            data = {
                "vote_id": vote.vote_id,
                "proposal_id": vote.proposal_id,
                "voter": vote.voter,
                "vote_type": vote.vote_type.value,
                "voting_power": vote.voting_power,
                "reason": vote.reason,
                "voted_at": vote.voted_at,
            }
            conn.execute(
                "INSERT OR REPLACE INTO dao_votes (vote_id, proposal_id, voter, data, voted_at) VALUES (?, ?, ?, ?, ?)",
                (vote.vote_id, vote.proposal_id, vote.voter, json.dumps(data), vote.voted_at)
            )
            conn.commit()
        finally:
            conn.close()
    
    def _save_treasury_balance(self):
        """持久化国库余额"""
        conn = self._get_db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO dao_treasury_state (key, value) VALUES ('balance', ?)",
                (str(self.treasury.treasury.balance),)
            )
            conn.commit()
        finally:
            conn.close()
    
    def stake(self, address: str, amount: float) -> Dict:
        """质押代币"""
        if amount <= 0:
            return {"error": "Stake amount must be positive"}
        if amount > 1_000_000_000:
            return {"error": "Stake amount exceeds maximum allowed"}
        with self._lock:
            current = self.stakes.get(address, 0)
            self.stakes[address] = current + amount
            self._save_stake(address)
            
            return {
                "address": address,
                "staked": amount,
                "total_stake": self.stakes[address],
                "voting_power": self.stakes[address],
            }
    
    def unstake(self, address: str, amount: float) -> Dict:
        """解除质押"""
        with self._lock:
            current = self.stakes.get(address, 0)
            if amount > current:
                return {"error": "Insufficient stake"}
            
            self.stakes[address] = current - amount
            self._save_stake(address)
            
            return {
                "address": address,
                "unstaked": amount,
                "remaining_stake": self.stakes[address],
            }
    
    def get_voting_power(self, address: str) -> float:
        """获取投票权重"""
        with self._lock:
            return self.stakes.get(address, 0)
    
    def create_proposal(
        self,
        proposer: str,
        proposal_type: ProposalType,
        title: str,
        description: str,
        changes: List[Dict] = None,
        execution_payload: Dict = None,
    ) -> Proposal:
        """创建提案"""
        with self._lock:
            # 检查质押
            stake = self.get_voting_power(proposer)
            if stake < self.config.min_stake_to_propose:
                raise ValueError(
                    f"Insufficient stake. Required: {self.config.min_stake_to_propose}, Got: {stake}"
                )
            
            # 确定投票期
            if proposal_type == ProposalType.EMERGENCY:
                voting_period = self.config.emergency_voting_hours * 3600
            else:
                voting_period = self.config.voting_period_days * 86400
            
            now = time.time()
            
            proposal = Proposal(
                proposal_type=proposal_type,
                proposer=proposer,
                proposer_stake=stake,
                title=title,
                description=description,
                changes=changes or [],
                execution_payload=execution_payload or {},
                voting_starts=now,
                voting_ends=now + voting_period,
                stake_snapshot=dict(self.stakes),  # H-10: 冻结当前质押状态
            )
            
            proposal.status = ProposalStatus.ACTIVE
            self.proposals[proposal.proposal_id] = proposal
            self._save_proposal(proposal)
            
            return proposal
    
    def vote(
        self,
        proposal_id: str,
        voter: str,
        vote_type: VoteType,
        reason: str = "",
    ) -> Vote:
        """投票"""
        with self._lock:
            proposal = self.proposals.get(proposal_id)
            if not proposal:
                raise ValueError("Proposal not found")
            
            if proposal.status != ProposalStatus.ACTIVE:
                raise ValueError(f"Proposal not active: {proposal.status.value}")
            
            if time.time() > proposal.voting_ends:
                raise ValueError("Voting period ended")
            
            # 检查是否已投票
            existing_votes = self.votes.get(proposal_id, [])
            for v in existing_votes:
                if v.voter == voter:
                    raise ValueError("Already voted")
            
            # 获取投票权重 — H-10: 使用提案创建时的快照，防止投票期间质押操纵
            if proposal.stake_snapshot:
                voting_power = proposal.stake_snapshot.get(voter, 0)
            else:
                voting_power = self.get_voting_power(voter)  # 向后兼容旧提案
            if voting_power < self.config.min_stake_to_vote:
                raise ValueError(
                    f"Insufficient stake to vote. Required: {self.config.min_stake_to_vote}"
                )
            
            # 创建投票
            vote = Vote(
                proposal_id=proposal_id,
                voter=voter,
                vote_type=vote_type,
                voting_power=voting_power,
                reason=reason,
            )
            
            self.votes[proposal_id].append(vote)
            self.voter_history[voter].append(proposal_id)
            
            # 更新提案统计
            proposal.voter_count += 1
            if vote_type == VoteType.FOR:
                proposal.votes_for += voting_power
            elif vote_type == VoteType.AGAINST:
                proposal.votes_against += voting_power
            else:
                proposal.votes_abstain += voting_power
            
            # 持久化
            self._save_vote(vote)
            self._save_proposal(proposal)
            
            return vote
    
    def finalize_proposal(self, proposal_id: str) -> Dict:
        """结束提案投票"""
        with self._lock:
            proposal = self.proposals.get(proposal_id)
            if not proposal:
                return {"error": "Proposal not found"}
            
            if proposal.status != ProposalStatus.ACTIVE:
                return {"error": f"Proposal not active: {proposal.status.value}"}
            
            # 检查投票期是否结束
            if time.time() < proposal.voting_ends:
                return {"error": "Voting period not ended"}
            
            # 计算法定人数
            total_stake = sum(self.stakes.values())
            if total_stake == 0:
                return {"error": "No stakes in system"}
            
            participation_rate = proposal.total_votes() / total_stake * 100
            
            # 确定阈值
            if proposal.proposal_type == ProposalType.EMERGENCY:
                quorum = self.config.emergency_quorum
                threshold = self.config.emergency_threshold
            else:
                quorum = self.config.quorum_percent
                threshold = self.config.approval_threshold
            
            # 检查法定人数
            if participation_rate < quorum:
                proposal.status = ProposalStatus.REJECTED
                self._save_proposal(proposal)
                return {
                    "proposal_id": proposal_id,
                    "status": "rejected",
                    "reason": f"Quorum not met. Required: {quorum}%, Got: {participation_rate:.2f}%",
                }
            
            # D-17 fix: 检查最少独立投票人数（防止单人鲸鱼通过提案）
            unique_voters = len(set(
                v.voter for votes_list in self.votes.values()
                for v in votes_list
                if v.proposal_id == proposal_id
            ))
            min_voters = (self.config.emergency_min_voters 
                         if proposal.proposal_type == ProposalType.EMERGENCY 
                         else self.config.min_unique_voters)
            if unique_voters < min_voters:
                proposal.status = ProposalStatus.REJECTED
                self._save_proposal(proposal)
                return {
                    "proposal_id": proposal_id,
                    "status": "rejected",
                    "reason": f"Minimum voters not met. Required: {min_voters}, Got: {unique_voters}",
                }
            
            # 检查通过率
            approval_rate = proposal.approval_rate()
            if approval_rate >= threshold:
                proposal.status = ProposalStatus.PASSED
                proposal.execution_time = time.time() + self.config.execution_delay_days * 86400
                self._save_proposal(proposal)
                
                return {
                    "proposal_id": proposal_id,
                    "status": "passed",
                    "approval_rate": approval_rate,
                    "execution_time": proposal.execution_time,
                }
            else:
                proposal.status = ProposalStatus.REJECTED
                self._save_proposal(proposal)
                
                return {
                    "proposal_id": proposal_id,
                    "status": "rejected",
                    "reason": f"Approval threshold not met. Required: {threshold}%, Got: {approval_rate:.2f}%",
                }
    
    def auto_execute_ready_proposals(self) -> List[Dict]:
        """M-07: 自动执行所有已到执行时间的已通过提案。
        
        可由定时任务周期性调用（如每个区块回调中）。
        
        Returns:
            执行结果列表
        """
        results = []
        now = time.time()
        ready_ids = []
        with self._lock:
            for pid, proposal in self.proposals.items():
                if (proposal.status == ProposalStatus.PASSED
                        and not proposal.executed
                        and now >= proposal.execution_time):
                    ready_ids.append(pid)
        
        # 逐个执行（execute_proposal 内部会加锁）
        for pid in ready_ids:
            result = self.execute_proposal(pid)
            results.append(result)
        
        return results
    
    def execute_proposal(self, proposal_id: str) -> Dict:
        """执行提案"""
        with self._lock:
            proposal = self.proposals.get(proposal_id)
            if not proposal:
                return {"error": "Proposal not found"}
            
            if proposal.status != ProposalStatus.PASSED:
                return {"error": f"Proposal not passed: {proposal.status.value}"}
            
            if proposal.executed:
                return {"error": "Proposal already executed"}
            
            # 检查执行延迟
            if time.time() < proposal.execution_time:
                return {
                    "error": f"Execution delay not passed. Can execute at: {proposal.execution_time}"
                }
            
            # 执行变更
            execution_results = []
            
            for change in proposal.changes:
                param = change.get("parameter")
                new_value = change.get("new_value")
                
                if param and new_value is not None:
                    result = self._apply_parameter_change(param, new_value)
                    execution_results.append(result)
            
            # 如果是国库支出
            if proposal.proposal_type == ProposalType.TREASURY_SPEND:
                payload = proposal.execution_payload
                amount = payload.get("amount", 0)
                recipient = payload.get("recipient", "")
                
                if amount > 0 and recipient:
                    # 需要多签执行
                    spend_result = self.treasury.request_withdrawal(
                        amount=amount,
                        recipient=recipient,
                        purpose=proposal.title,
                        proposal_id=proposal_id,
                    )
                    execution_results.append(spend_result)
            
            # 去中心化修复：多签签名者轮换
            if proposal.proposal_type == ProposalType.SIGNER_ROTATION:
                rotate_result = self._execute_signer_rotation(proposal)
                execution_results.append(rotate_result)
            
            # 板块新增（社区投票通过后执行）
            if proposal.proposal_type == ProposalType.SECTOR_ADD:
                sector_result = self._execute_sector_add(proposal)
                execution_results.append(sector_result)
            
            # 板块废除（社区投票通过后执行）
            if proposal.proposal_type == ProposalType.SECTOR_DEACTIVATE:
                sector_result = self._execute_sector_deactivate(proposal)
                execution_results.append(sector_result)
            
            proposal.executed = True
            proposal.executed_at = time.time()
            proposal.status = ProposalStatus.EXECUTED
            self._save_proposal(proposal)
            
            return {
                "proposal_id": proposal_id,
                "status": "executed",
                "results": execution_results,
                "executed_at": proposal.executed_at,
            }
    
    # Allowed parameter bounds for governance changes
    PARAMETER_BOUNDS: Dict[str, Tuple] = {
        "platform_fee_rate": (0.0, 0.1),      # 0% - 10%
        "miner_reward_rate": (0.0, 1.0),      # 0% - 100%
        "min_stake": (0.0, 1_000_000.0),      # max 1M
        "proposal_threshold": (0.0, 1_000_000.0),
        "quorum": (0.0, 1.0),                  # 0% - 100%
        "voting_period": (3600, 2592000),       # 1 hour - 30 days
        "execution_delay": (0, 604800),         # 0 - 7 days
    }
    
    def _execute_signer_rotation(self, proposal) -> Dict:
        """去中心化修复：通过 DAO 投票执行多签签名者轮换。
        
        execution_payload 格式:
        {
            "action": "add" | "remove" | "replace",
            "signer_id": "new_signer_id",           # add/replace 时必填
            "public_key": "hex_pubkey",              # add/replace 时必填
            "remove_signer_id": "old_signer_id",     # remove/replace 时必填
            "new_threshold": 3,                       # 可选：更新阈值
        }
        
        安全约束：
        - 签名者总数不得少于 3
        - 签名者总数不得超过 9
        - 阈值不得低于 ceil(总数/2)（即始终要求过半数）
        - 不能移除所有签名者
        """
        payload = proposal.execution_payload or {}
        action = payload.get("action", "")
        signer_id = payload.get("signer_id", "")
        pubkey_hex = payload.get("public_key", "")
        remove_id = payload.get("remove_signer_id", "")
        new_threshold = payload.get("new_threshold")
        
        import math
        
        signers = self.treasury.multisig_signers
        pubkeys = self.treasury.multisig_pubkeys
        
        if action == "add":
            if not signer_id or not pubkey_hex:
                return {"success": False, "error": "add 操作需要 signer_id 和 public_key"}
            if signer_id in signers:
                return {"success": False, "error": f"签名者 {signer_id} 已存在"}
            if len(signers) >= 9:
                return {"success": False, "error": "签名者总数不能超过 9"}
            signers.append(signer_id)
            pubkeys[signer_id] = pubkey_hex
            
        elif action == "remove":
            if not remove_id:
                return {"success": False, "error": "remove 操作需要 remove_signer_id"}
            if remove_id not in signers:
                return {"success": False, "error": f"签名者 {remove_id} 不存在"}
            if len(signers) <= 3:
                return {"success": False, "error": "签名者总数不能少于 3"}
            signers.remove(remove_id)
            pubkeys.pop(remove_id, None)
            
        elif action == "replace":
            if not remove_id or not signer_id or not pubkey_hex:
                return {"success": False, "error": "replace 操作需要 remove_signer_id、signer_id 和 public_key"}
            if remove_id not in signers:
                return {"success": False, "error": f"被替换签名者 {remove_id} 不存在"}
            if signer_id in signers:
                return {"success": False, "error": f"新签名者 {signer_id} 已存在"}
            idx = signers.index(remove_id)
            signers[idx] = signer_id
            pubkeys.pop(remove_id, None)
            pubkeys[signer_id] = pubkey_hex
        else:
            return {"success": False, "error": f"未知操作: {action}，支持 add/remove/replace"}
        
        # 更新阈值（如果指定）
        if new_threshold is not None:
            min_threshold = math.ceil(len(signers) / 2)
            if new_threshold < min_threshold:
                new_threshold = min_threshold
            if new_threshold > len(signers):
                new_threshold = len(signers)
            self.treasury.multisig_threshold = int(new_threshold)
        else:
            # 自动调整：确保阈值 >= ceil(总数/2)
            min_threshold = math.ceil(len(signers) / 2)
            if self.treasury.multisig_threshold < min_threshold:
                self.treasury.multisig_threshold = min_threshold
        
        return {
            "success": True,
            "action": action,
            "signers": list(signers),
            "threshold": self.treasury.multisig_threshold,
        }
    
    def _execute_sector_add(self, proposal) -> Dict:
        """通过 DAO 投票执行板块新增。
        
        execution_payload 格式:
        {
            "sector_name": "RTX5090",
            "base_reward": 50.0,
            "exchange_rate": 1.0,
            "max_supply": 21000000,
            "gpu_models": ["RTX 5090", "RTX5090"]
        }
        """
        payload = proposal.execution_payload or {}
        sector_name = payload.get("sector_name", "")
        if not sector_name:
            return {"success": False, "error": "缺少 sector_name"}
        
        import re
        if not re.match(r'^[A-Za-z0-9_]+$', sector_name):
            return {"success": False, "error": "板块名称只允许字母、数字和下划线"}
        
        try:
            from core.sector_coin import get_sector_registry
            registry = get_sector_registry()
            ok, msg = registry.add_sector(
                name=sector_name.upper(),
                base_reward=payload.get("base_reward"),
                exchange_rate=payload.get("exchange_rate"),
                max_supply=payload.get("max_supply"),
                gpu_models=payload.get("gpu_models"),
            )
            return {"success": ok, "message": msg, "sector": sector_name.upper()}
        except Exception as e:
            logger.error(f"DAO 板块创建执行失败: {e}")
            return {"success": False, "error": "sector_creation_failed"}
    
    def _execute_sector_deactivate(self, proposal) -> Dict:
        """通过 DAO 投票执行板块废除。
        
        execution_payload 格式:
        {
            "sector_name": "RTX5090"
        }
        """
        payload = proposal.execution_payload or {}
        sector_name = payload.get("sector_name", "")
        if not sector_name:
            return {"success": False, "error": "缺少 sector_name"}
        
        try:
            from core.sector_coin import get_sector_registry, SectorCoinType, SectorCoinLedger
            registry = get_sector_registry()
            
            # 前置检查：板块币必须全部挖完才能执行停用
            sector_upper = sector_name.upper()
            info = registry.get_sector_info(sector_upper)
            if info:
                coin_type = SectorCoinType.from_sector(sector_upper)
                ledger = SectorCoinLedger()
                total_minted = ledger._get_total_minted(coin_type)
                max_supply = info.get("max_supply", 21_000_000.0)
                if total_minted < max_supply:
                    return {
                        "success": False,
                        "error": (f"板块 {sector_upper} 的币尚未挖完 "
                                  f"(已铸造 {total_minted:.2f}/{max_supply:.2f})，"
                                  f"必须全部挖完后才能触发停用"),
                        "sector": sector_upper,
                    }
            
            ok, msg = registry.deactivate_sector(sector_upper)
            return {"success": ok, "message": msg, "sector": sector_upper}
        except Exception as e:
            logger.error(f"DAO 板块废除执行失败: {e}")
            return {"success": False, "error": "sector_deactivation_failed"}
    
    def _apply_parameter_change(self, parameter: str, new_value: Any) -> Dict:
        """应用参数变更 (with bounds validation)"""
        try:
            param = GovernanceParameter(parameter)
            
            # Security: Validate parameter bounds
            bounds = self.PARAMETER_BOUNDS.get(parameter)
            if bounds:
                min_val, max_val = bounds
                try:
                    numeric_val = float(new_value)
                    if numeric_val < min_val or numeric_val > max_val:
                        return {
                            "parameter": parameter,
                            "error": f"Value {new_value} out of bounds [{min_val}, {max_val}]",
                            "success": False,
                        }
                except (ValueError, TypeError):
                    return {
                        "parameter": parameter,
                        "error": f"Value must be numeric, got {type(new_value).__name__}",
                        "success": False,
                    }
            
            old_value = getattr(self.config, parameter, None)
            setattr(self.config, parameter, new_value)
            
            return {
                "parameter": parameter,
                "old_value": old_value,
                "new_value": new_value,
                "success": True,
            }
        except Exception as e:
            return {
                "parameter": parameter,
                "error": "parameter_change_failed",
                "success": False,
            }
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """获取提案"""
        with self._lock:
            proposal = self.proposals.get(proposal_id)
            if proposal:
                return proposal.to_dict()
            return None
    
    def get_active_proposals(self) -> List[Dict]:
        """获取活跃提案"""
        with self._lock:
            active = [
                p.to_dict() for p in self.proposals.values()
                if p.status == ProposalStatus.ACTIVE
            ]
            return sorted(active, key=lambda x: x["voting_ends"])
    
    def get_proposal_votes(self, proposal_id: str) -> List[Dict]:
        """获取提案投票"""
        with self._lock:
            votes = self.votes.get(proposal_id, [])
            return [v.to_dict() for v in votes]
    
    def get_governance_config(self) -> Dict:
        """获取治理配置"""
        return {
            "platform_fee_rate": self.config.platform_fee_rate,
            "miner_reward_rate": self.config.miner_reward_rate,
            "treasury_rate": self.config.treasury_rate,
            "min_stake_to_vote": self.config.min_stake_to_vote,
            "min_stake_to_propose": self.config.min_stake_to_propose,
            "voting_period_days": self.config.voting_period_days,
            "execution_delay_days": self.config.execution_delay_days,
            "quorum_percent": self.config.quorum_percent,
            "approval_threshold": self.config.approval_threshold,
        }
    
    def get_governance_stats(self) -> Dict:
        """获取治理统计"""
        with self._lock:
            total_proposals = len(self.proposals)
            passed = sum(1 for p in self.proposals.values() if p.status == ProposalStatus.PASSED)
            executed = sum(1 for p in self.proposals.values() if p.status == ProposalStatus.EXECUTED)
            
            return {
                "total_proposals": total_proposals,
                "passed": passed,
                "executed": executed,
                "rejected": total_proposals - passed - sum(1 for p in self.proposals.values() if p.status == ProposalStatus.ACTIVE),
                "total_stakers": len(self.stakes),
                "total_stake": sum(self.stakes.values()),
                "treasury_balance": self.treasury.get_balance(),
            }


# ============== 费用分配器 ==============

class FeeDistributor:
    """费用分配器"""
    
    def __init__(self, governance: DAOGovernance):
        self.governance = governance
    
    def distribute_fee(
        self,
        total_fee: float,
        miner_id: str,
    ) -> Dict:
        """分配费用"""
        config = self.governance.config
        
        # 计算分配
        miner_share = total_fee * config.miner_reward_rate
        platform_share = total_fee * config.platform_fee_rate
        treasury_share = total_fee * config.treasury_rate
        
        # 存入国库
        if treasury_share > 0:
            self.governance.treasury.deposit(
                amount=treasury_share,
                source=f"fee_from_task",
                category="fee",
            )
        
        return {
            "total_fee": total_fee,
            "distribution": {
                "miner": {
                    "id": miner_id,
                    "amount": miner_share,
                    "rate": config.miner_reward_rate,
                },
                "platform": {
                    "amount": platform_share,
                    "rate": config.platform_fee_rate,
                },
                "treasury": {
                    "amount": treasury_share,
                    "rate": config.treasury_rate,
                },
            },
        }


# ============== 全局实例 ==============

_dao_governance: Optional[DAOGovernance] = None
_fee_distributor: Optional[FeeDistributor] = None


def get_dao_system() -> Tuple[DAOGovernance, FeeDistributor]:
    """获取 DAO 系统"""
    global _dao_governance, _fee_distributor
    
    if _dao_governance is None:
        _dao_governance = DAOGovernance()
        _fee_distributor = FeeDistributor(_dao_governance)
    
    return _dao_governance, _fee_distributor
