"""
治理与去中心化决策增强 v2.0
=========================

改进要点：
1. 增强治理模型 - 多层级提案、委托投票、阶梯式权重
2. 社区驱动功能 - 贡献积分、社区基金、激励机制
3. 智能合约自动治理 - 提案自动执行、合规规则引擎
4. 紧急治理机制 - 快速响应、多签应急、熔断保护

本模块补充和增强现有 contribution_governance.py 和 governance_v2.py 的功能。
"""

import time
import uuid
import json
import sqlite3
import hashlib
import threading
import logging
import math
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class ProposalCategory(Enum):
    """提案类别"""
    PARAMETER = "parameter"           # 参数调整（费率/区块大小等）
    PROTOCOL = "protocol"             # 协议升级
    TREASURY = "treasury"             # 国库资金使用
    COMMUNITY = "community"           # 社区活动/建设
    EMERGENCY = "emergency"           # 紧急修复
    GRANT = "grant"                   # 开发者资助
    SECTOR = "sector"                 # 扇区管理
    POLICY = "policy"                 # 政策变更
    FEATURE = "feature"               # 新功能提案
    CONSTITUTIONAL = "constitutional" # 宪法级修改


class ProposalStage(Enum):
    """提案阶段"""
    DRAFT = "draft"                   # 草案
    DISCUSSION = "discussion"         # 讨论期
    VOTING = "voting"                 # 投票期
    TIMELOCK = "timelock"             # 时间锁执行等待
    EXECUTION = "execution"           # 执行中
    EXECUTED = "executed"             # 已执行
    REJECTED = "rejected"             # 已否决
    EXPIRED = "expired"               # 已过期
    VETOED = "vetoed"                 # 已否决（紧急）
    CANCELLED = "cancelled"           # 已取消


class VoteType(Enum):
    """投票类型"""
    FOR = "for"                       # 赞成
    AGAINST = "against"               # 反对
    ABSTAIN = "abstain"               # 弃权


class GovernanceRole(Enum):
    """治理角色"""
    COMMUNITY = "community"           # 普通社区成员
    CONTRIBUTOR = "contributor"       # 核心贡献者
    VALIDATOR = "validator"           # 验证者/矿工
    DELEGATE = "delegate"             # 委托代表
    COUNCIL = "council"               # 理事会成员
    GUARDIAN = "guardian"             # 紧急守护者


class DelegationType(Enum):
    """委托类型"""
    FULL = "full"                     # 完全委托
    CATEGORY = "category"             # 按类别委托
    CONDITIONAL = "conditional"       # 条件委托
    TEMPORARY = "temporary"           # 临时委托


# ============================================================
# 数据模型
# ============================================================

@dataclass
class GovernanceProposal:
    """治理提案"""
    proposal_id: str
    category: ProposalCategory
    stage: ProposalStage = ProposalStage.DRAFT

    # 提案内容
    title: str = ""
    description: str = ""
    proposer_id: str = ""
    specification: Dict = field(default_factory=dict)
    impact_analysis: Dict = field(default_factory=dict)

    # 投票配置
    quorum_threshold: float = 0.15      # 法定人数(15%)
    pass_threshold: float = 0.66        # 通过阈值(66%)
    veto_threshold: float = 0.33        # 否决阈值(33%)

    # 时间配置
    discussion_days: int = 7
    voting_days: int = 5
    timelock_days: int = 2
    created_at: float = 0.0
    stage_changed_at: float = 0.0
    executed_at: float = 0.0

    # 投票统计
    votes_for: float = 0.0
    votes_against: float = 0.0
    votes_abstain: float = 0.0
    total_eligible_weight: float = 0.0
    voter_count: int = 0

    # 执行
    execution_actions: List[Dict] = field(default_factory=list)
    execution_result: Dict = field(default_factory=dict)

    # 元数据
    deposit_amount: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class VoteRecord:
    """投票记录"""
    vote_id: str
    proposal_id: str
    voter_id: str
    vote_type: VoteType
    weight: float = 1.0
    reason: str = ""
    delegated_from: str = ""    # 若是委托投票
    timestamp: float = 0.0


@dataclass
class VoteDelegation:
    """投票委托"""
    delegation_id: str
    delegator_id: str           # 委托人
    delegate_id: str            # 受托人
    delegation_type: DelegationType = DelegationType.FULL
    categories: List[ProposalCategory] = field(default_factory=list)
    conditions: Dict = field(default_factory=dict)
    weight_ratio: float = 1.0   # 委托权重比例
    expires_at: float = 0.0
    created_at: float = 0.0
    active: bool = True


@dataclass
class CommunityContribution:
    """社区贡献记录"""
    contribution_id: str
    contributor_id: str
    contribution_type: str      # code/testing/docs/community/review
    description: str = ""
    points: float = 0.0
    verified: bool = False
    verifier_id: str = ""
    created_at: float = 0.0


@dataclass
class CommunityFund:
    """社区基金"""
    fund_id: str
    name: str
    total_amount: float = 0.0
    distributed_amount: float = 0.0
    purpose: str = ""
    governance_proposal_id: str = ""
    created_at: float = 0.0


# ============================================================
# 增强治理引擎
# ============================================================

class EnhancedGovernanceEngine:
    """
    增强治理引擎

    功能：
    1. 多层级提案与分类治理
    2. 委托投票与阶梯权重
    3. 贡献积分与社区基金
    4. 自动执行与合规审查
    5. 紧急治理快速通道
    """

    # 安全等级声明
    SECURITY_LEVEL = "HIGH"

    # 不同类别提案的配置
    CATEGORY_CONFIG = {
        ProposalCategory.PARAMETER: {
            "quorum": 0.10, "pass": 0.60, "timelock_days": 1,
            "min_deposit": 100, "discussion_days": 3, "voting_days": 3,
        },
        ProposalCategory.PROTOCOL: {
            "quorum": 0.20, "pass": 0.75, "timelock_days": 7,
            "min_deposit": 1000, "discussion_days": 14, "voting_days": 7,
        },
        ProposalCategory.TREASURY: {
            "quorum": 0.15, "pass": 0.66, "timelock_days": 3,
            "min_deposit": 500, "discussion_days": 7, "voting_days": 5,
        },
        ProposalCategory.COMMUNITY: {
            "quorum": 0.10, "pass": 0.55, "timelock_days": 1,
            "min_deposit": 50, "discussion_days": 5, "voting_days": 3,
        },
        ProposalCategory.EMERGENCY: {
            "quorum": 0.05, "pass": 0.80, "timelock_days": 0,
            "min_deposit": 0, "discussion_days": 0, "voting_days": 1,
        },
        ProposalCategory.GRANT: {
            "quorum": 0.12, "pass": 0.60, "timelock_days": 2,
            "min_deposit": 200, "discussion_days": 7, "voting_days": 5,
        },
        ProposalCategory.SECTOR: {
            "quorum": 0.15, "pass": 0.66, "timelock_days": 3,
            "min_deposit": 500, "discussion_days": 7, "voting_days": 5,
        },
        ProposalCategory.POLICY: {
            "quorum": 0.15, "pass": 0.66, "timelock_days": 3,
            "min_deposit": 300, "discussion_days": 10, "voting_days": 5,
        },
        ProposalCategory.FEATURE: {
            "quorum": 0.10, "pass": 0.60, "timelock_days": 2,
            "min_deposit": 200, "discussion_days": 7, "voting_days": 5,
        },
        ProposalCategory.CONSTITUTIONAL: {
            "quorum": 0.30, "pass": 0.85, "timelock_days": 14,
            "min_deposit": 5000, "discussion_days": 30, "voting_days": 14,
        },
    }

    # 治理角色的投票权重倍数
    ROLE_WEIGHT_MULTIPLIER = {
        GovernanceRole.COMMUNITY: 1.0,
        GovernanceRole.CONTRIBUTOR: 1.5,
        GovernanceRole.VALIDATOR: 2.0,
        GovernanceRole.DELEGATE: 1.0,   # 委托权重独立计算
        GovernanceRole.COUNCIL: 3.0,
        GovernanceRole.GUARDIAN: 2.5,
    }

    def __init__(self, db_path: str = "data/governance_enhanced.db"):
        self.db_path = db_path
        self.lock = threading.Lock()

        # 内存缓存
        self.proposals: Dict[str, GovernanceProposal] = {}
        self.votes: Dict[str, List[VoteRecord]] = {}        # proposal_id -> votes
        self.delegations: Dict[str, VoteDelegation] = {}     # delegation_id -> delegation
        self.contributions: Dict[str, List[CommunityContribution]] = {}
        self.community_funds: Dict[str, CommunityFund] = {}

        # 用户角色与权重
        self.user_roles: Dict[str, GovernanceRole] = {}      # user_id -> role
        self.user_stake_weight: Dict[str, float] = {}        # user_id -> staked weight
        self.user_contribution_points: Dict[str, float] = {} # user_id -> total points

        # 紧急治理
        self.guardians: Set[str] = set()                     # 紧急守护者列表
        self.guardian_pubkeys: Dict[str, str] = {}           # guardian_id -> public_key (hex)
        self.emergency_multisig_threshold: int = 3           # 紧急多签阈值

        # 自动执行引擎
        self.execution_handlers: Dict[str, Callable] = {}

        self._init_db()
        logger.info("[治理引擎] 增强治理系统已初始化")

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    category TEXT,
                    stage TEXT,
                    title TEXT,
                    description TEXT,
                    proposer_id TEXT,
                    specification_json TEXT,
                    impact_json TEXT,
                    quorum_threshold REAL,
                    pass_threshold REAL,
                    veto_threshold REAL,
                    discussion_days INTEGER,
                    voting_days INTEGER,
                    timelock_days INTEGER,
                    created_at REAL,
                    stage_changed_at REAL,
                    executed_at REAL,
                    votes_for REAL DEFAULT 0,
                    votes_against REAL DEFAULT 0,
                    votes_abstain REAL DEFAULT 0,
                    total_eligible_weight REAL DEFAULT 0,
                    voter_count INTEGER DEFAULT 0,
                    execution_actions_json TEXT,
                    execution_result_json TEXT,
                    deposit_amount REAL DEFAULT 0,
                    tags_json TEXT
                );

                CREATE TABLE IF NOT EXISTS vote_records (
                    vote_id TEXT PRIMARY KEY,
                    proposal_id TEXT,
                    voter_id TEXT,
                    vote_type TEXT,
                    weight REAL,
                    reason TEXT,
                    delegated_from TEXT,
                    timestamp REAL
                );

                CREATE TABLE IF NOT EXISTS delegations (
                    delegation_id TEXT PRIMARY KEY,
                    delegator_id TEXT,
                    delegate_id TEXT,
                    delegation_type TEXT,
                    categories_json TEXT,
                    conditions_json TEXT,
                    weight_ratio REAL,
                    expires_at REAL,
                    created_at REAL,
                    active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS contributions (
                    contribution_id TEXT PRIMARY KEY,
                    contributor_id TEXT,
                    contribution_type TEXT,
                    description TEXT,
                    points REAL,
                    verified INTEGER DEFAULT 0,
                    verifier_id TEXT,
                    created_at REAL
                );

                CREATE TABLE IF NOT EXISTS community_funds (
                    fund_id TEXT PRIMARY KEY,
                    name TEXT,
                    total_amount REAL,
                    distributed_amount REAL,
                    purpose TEXT,
                    governance_proposal_id TEXT,
                    created_at REAL
                );

                CREATE INDEX IF NOT EXISTS idx_prop_stage ON proposals(stage);
                CREATE INDEX IF NOT EXISTS idx_vote_proposal ON vote_records(proposal_id);
                CREATE INDEX IF NOT EXISTS idx_vote_voter ON vote_records(voter_id);
                CREATE INDEX IF NOT EXISTS idx_deleg_delegator ON delegations(delegator_id);
                CREATE INDEX IF NOT EXISTS idx_contrib_user ON contributions(contributor_id);
            """)

    # ============================================================
    # 提案管理
    # ============================================================

    def create_proposal(self, proposer_id: str,
                        category: ProposalCategory,
                        title: str, description: str,
                        specification: Dict,
                        execution_actions: Optional[List[Dict]] = None,
                        deposit: float = 0.0) -> Optional[str]:
        """创建治理提案"""
        config = self.CATEGORY_CONFIG.get(category)
        if not config:
            logger.error(f"[治理引擎] 不支持的提案类别: {category}")
            return None

        # 检查保证金
        min_deposit = config["min_deposit"]
        if deposit < min_deposit:
            logger.warning(
                f"[治理引擎] 保证金不足: {deposit} < {min_deposit}")
            return None

        proposal_id = f"PROP-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        now = time.time()

        proposal = GovernanceProposal(
            proposal_id=proposal_id,
            category=category,
            stage=ProposalStage.DRAFT,
            title=title,
            description=description,
            proposer_id=proposer_id,
            specification=specification,
            quorum_threshold=config["quorum"],
            pass_threshold=config["pass"],
            discussion_days=config["discussion_days"],
            voting_days=config["voting_days"],
            timelock_days=config["timelock_days"],
            created_at=now,
            stage_changed_at=now,
            execution_actions=execution_actions or [],
            deposit_amount=deposit,
        )

        with self.lock:
            self.proposals[proposal_id] = proposal
            self.votes[proposal_id] = []

        self._save_proposal(proposal)
        logger.info(f"[治理引擎] 新提案已创建: {proposal_id} [{category.value}] {title}")

        return proposal_id

    def advance_proposal_stage(self, proposal_id: str) -> bool:
        """推进提案阶段"""
        with self.lock:
            proposal = self.proposals.get(proposal_id)
            if not proposal:
                return False

            now = time.time()
            stage_transitions = {
                ProposalStage.DRAFT: ProposalStage.DISCUSSION,
                ProposalStage.DISCUSSION: ProposalStage.VOTING,
                ProposalStage.VOTING: None,  # 由投票结果决定
                ProposalStage.TIMELOCK: ProposalStage.EXECUTION,
                ProposalStage.EXECUTION: ProposalStage.EXECUTED,
            }

            if proposal.stage == ProposalStage.VOTING:
                # 检查投票是否结束
                voting_end = proposal.stage_changed_at + \
                    proposal.voting_days * 86400
                if now < voting_end:
                    return False

                # 计算结果
                return self._finalize_vote(proposal)

            next_stage = stage_transitions.get(proposal.stage)
            if next_stage is None:
                return False

            # 检查时间要求
            if proposal.stage == ProposalStage.DISCUSSION:
                required = proposal.discussion_days * 86400
                if now - proposal.stage_changed_at < required:
                    return False

            if proposal.stage == ProposalStage.TIMELOCK:
                required = proposal.timelock_days * 86400
                if now - proposal.stage_changed_at < required:
                    return False

            proposal.stage = next_stage
            proposal.stage_changed_at = now

            # 进入投票阶段时，计算 total_eligible_weight
            if next_stage == ProposalStage.VOTING:
                total_weight = 0.0
                for voter_id in self.user_stake_weight:
                    weight = self._calculate_vote_weight(voter_id, proposal.category)
                    total_weight += weight
                # 确保至少有一个有效权重，避免除零
                proposal.total_eligible_weight = max(total_weight, 1.0)
                logger.info(
                    f"[治理引擎] 提案 {proposal.proposal_id} 进入投票阶段, "
                    f"total_eligible_weight={proposal.total_eligible_weight:.2f}"
                )

            if next_stage == ProposalStage.EXECUTION:
                self._execute_proposal(proposal)

            self._save_proposal(proposal)
            return True

    def _finalize_vote(self, proposal: GovernanceProposal) -> bool:
        """结算投票结果"""
        total_voted = proposal.votes_for + proposal.votes_against + proposal.votes_abstain

        if proposal.total_eligible_weight == 0:
            proposal.stage = ProposalStage.REJECTED
            proposal.stage_changed_at = time.time()
            self._save_proposal(proposal)
            return True

        participation_rate = total_voted / proposal.total_eligible_weight

        # 法定人数检查
        if participation_rate < proposal.quorum_threshold:
            proposal.stage = ProposalStage.REJECTED
            logger.info(
                f"[治理引擎] 提案 {proposal.proposal_id} 未达法定人数: "
                f"{participation_rate:.2%} < {proposal.quorum_threshold:.2%}")
            proposal.stage_changed_at = time.time()
            self._save_proposal(proposal)
            return True

        # 否决检查
        total_non_abstain = proposal.votes_for + proposal.votes_against
        if total_non_abstain > 0:
            against_ratio = proposal.votes_against / total_non_abstain
            if against_ratio >= proposal.veto_threshold:
                proposal.stage = ProposalStage.VETOED
                logger.info(
                    f"[治理引擎] 提案 {proposal.proposal_id} 被否决: "
                    f"反对率 {against_ratio:.2%}")
                proposal.stage_changed_at = time.time()
                self._save_proposal(proposal)
                return True

        # 通过检查
        if total_non_abstain > 0:
            approval_rate = proposal.votes_for / total_non_abstain
            if approval_rate >= proposal.pass_threshold:
                proposal.stage = ProposalStage.TIMELOCK
                logger.info(
                    f"[治理引擎] 提案 {proposal.proposal_id} 已通过: "
                    f"赞成率 {approval_rate:.2%}")
            else:
                proposal.stage = ProposalStage.REJECTED
                logger.info(
                    f"[治理引擎] 提案 {proposal.proposal_id} 未通过: "
                    f"赞成率 {approval_rate:.2%} < {proposal.pass_threshold:.2%}")
        else:
            proposal.stage = ProposalStage.REJECTED

        proposal.stage_changed_at = time.time()
        self._save_proposal(proposal)
        return True

    # ============================================================
    # 投票系统
    # ============================================================

    def cast_vote(self, proposal_id: str, voter_id: str,
                   vote_type: VoteType,
                   reason: str = "") -> Optional[str]:
        """投票"""
        with self.lock:
            proposal = self.proposals.get(proposal_id)
            if not proposal or proposal.stage != ProposalStage.VOTING:
                logger.warning(f"[治理引擎] 无效投票: 提案不存在或非投票阶段")
                return None

            # 检查是否已投票
            existing_votes = self.votes.get(proposal_id, [])
            if any(v.voter_id == voter_id for v in existing_votes):
                logger.warning(f"[治理引擎] 重复投票: {voter_id}")
                return None

            # 计算投票权重
            weight = self._calculate_vote_weight(voter_id, proposal.category)

            vote = VoteRecord(
                vote_id=str(uuid.uuid4()),
                proposal_id=proposal_id,
                voter_id=voter_id,
                vote_type=vote_type,
                weight=weight,
                reason=reason,
                timestamp=time.time()
            )

            existing_votes.append(vote)
            self.votes[proposal_id] = existing_votes

            # 更新计数
            if vote_type == VoteType.FOR:
                proposal.votes_for += weight
            elif vote_type == VoteType.AGAINST:
                proposal.votes_against += weight
            else:
                proposal.votes_abstain += weight
            proposal.voter_count += 1

            self._save_vote(vote)
            self._save_proposal(proposal)

            # 处理委托投票
            self._process_delegated_votes(proposal, voter_id, vote_type, reason)

            return vote.vote_id

    def _calculate_vote_weight(self, voter_id: str,
                                 category: ProposalCategory) -> float:
        """
        计算投票权重（阶梯式）

        权重 = 基础权重 × 角色倍数 × 贡献加成 × 质押加成

        阶梯式质押：
        - 0-1000:  ×1.0
        - 1000-10000: ×0.8（边际递减）
        - 10000+:  ×0.5
        """
        # 基础权重
        base_weight = 1.0

        # 角色倍数
        role = self.user_roles.get(voter_id, GovernanceRole.COMMUNITY)
        role_mult = self.ROLE_WEIGHT_MULTIPLIER.get(role, 1.0)

        # 贡献加成（最多50%加成）
        contribution_points = self.user_contribution_points.get(voter_id, 0)
        contribution_bonus = min(0.5, contribution_points / 10000)

        # 质押加成（阶梯式）
        staked = self.user_stake_weight.get(voter_id, 0)
        if staked <= 1000:
            stake_weight = staked * 1.0
        elif staked <= 10000:
            stake_weight = 1000 + (staked - 1000) * 0.8
        else:
            stake_weight = 1000 + 9000 * 0.8 + (staked - 10000) * 0.5

        # 标准化质押权重
        stake_bonus = min(3.0, stake_weight / 1000)

        weight = base_weight * role_mult * (1 + contribution_bonus) * (1 + stake_bonus)
        return round(weight, 4)

    def _process_delegated_votes(self, proposal: GovernanceProposal,
                                   delegate_id: str,
                                   vote_type: VoteType,
                                   reason: str):
        """处理委托投票"""
        for delegation in self.delegations.values():
            if not delegation.active:
                continue
            if delegation.delegate_id != delegate_id:
                continue
            if delegation.expires_at > 0 and delegation.expires_at < time.time():
                delegation.active = False
                continue

            # 类别检查
            if delegation.delegation_type == DelegationType.CATEGORY:
                if proposal.category not in delegation.categories:
                    continue

            # 条件检查
            if delegation.delegation_type == DelegationType.CONDITIONAL:
                if not self._check_delegation_conditions(
                     delegation, proposal, vote_type):
                    continue

            # 检查委托人是否已自行投票
            delegator_id = delegation.delegator_id
            existing = self.votes.get(proposal.proposal_id, [])
            if any(v.voter_id == delegator_id for v in existing):
                continue  # 委托人已自行投票，跳过

            # 计算委托权重
            delegated_weight = self._calculate_vote_weight(
                delegator_id, proposal.category) * delegation.weight_ratio

            delegated_vote = VoteRecord(
                vote_id=str(uuid.uuid4()),
                proposal_id=proposal.proposal_id,
                voter_id=delegator_id,
                vote_type=vote_type,
                weight=delegated_weight,
                reason=f"[委托投票] 受托人: {delegate_id} - {reason}",
                delegated_from=delegate_id,
                timestamp=time.time()
            )

            existing.append(delegated_vote)
            self.votes[proposal.proposal_id] = existing

            if vote_type == VoteType.FOR:
                proposal.votes_for += delegated_weight
            elif vote_type == VoteType.AGAINST:
                proposal.votes_against += delegated_weight
            else:
                proposal.votes_abstain += delegated_weight
            proposal.voter_count += 1

            self._save_vote(delegated_vote)

    def _check_delegation_conditions(self, delegation: VoteDelegation,
                                       proposal: GovernanceProposal,
                                       vote_type: VoteType) -> bool:
        """检查委托条件"""
        conditions = delegation.conditions

        # 金额限制
        if "max_treasury_amount" in conditions:
            if proposal.category == ProposalCategory.TREASURY:
                amount = proposal.specification.get("amount", 0)
                if amount > conditions["max_treasury_amount"]:
                    return False

        # 类别限制
        if "excluded_categories" in conditions:
            if proposal.category.value in conditions["excluded_categories"]:
                return False

        # 投票方向限制
        if "only_vote_for" in conditions and conditions["only_vote_for"]:
            if vote_type != VoteType.FOR:
                return False

        return True

    # ============================================================
    # 委托管理
    # ============================================================

    def create_delegation(self, delegator_id: str, delegate_id: str,
                           delegation_type: DelegationType = DelegationType.FULL,
                           categories: Optional[List[ProposalCategory]] = None,
                           conditions: Optional[Dict] = None,
                           weight_ratio: float = 1.0,
                           duration_days: float = 90) -> str:
        """创建投票委托"""
        delegation_id = str(uuid.uuid4())

        delegation = VoteDelegation(
            delegation_id=delegation_id,
            delegator_id=delegator_id,
            delegate_id=delegate_id,
            delegation_type=delegation_type,
            categories=categories or [],
            conditions=conditions or {},
            weight_ratio=min(1.0, weight_ratio),
            expires_at=time.time() + duration_days * 86400,
            created_at=time.time(),
            active=True,
        )

        with self.lock:
            # 取消同一委托人的旧委托
            for d in self.delegations.values():
                if d.delegator_id == delegator_id and d.active:
                    d.active = False

            self.delegations[delegation_id] = delegation

        self._save_delegation(delegation)
        logger.info(
            f"[治理引擎] 新委托: {delegator_id} -> {delegate_id} "
            f"[{delegation_type.value}]")

        return delegation_id

    def revoke_delegation(self, delegation_id: str) -> bool:
        """撤销委托"""
        with self.lock:
            delegation = self.delegations.get(delegation_id)
            if not delegation:
                return False
            delegation.active = False
            self._save_delegation(delegation)
            return True

    def get_delegate_info(self, delegate_id: str) -> Dict:
        """获取受托人信息"""
        delegators = []
        total_weight = 0.0

        for d in self.delegations.values():
            if d.delegate_id == delegate_id and d.active:
                if d.expires_at > 0 and d.expires_at < time.time():
                    continue
                w = self.user_stake_weight.get(d.delegator_id, 0) * d.weight_ratio
                delegators.append({
                    "delegator_id": d.delegator_id,
                    "type": d.delegation_type.value,
                    "weight": w,
                })
                total_weight += w

        return {
            "delegate_id": delegate_id,
            "delegator_count": len(delegators),
            "total_delegated_weight": total_weight,
            "delegators": delegators,
        }

    # ============================================================
    # 贡献积分系统
    # ============================================================

    def record_contribution(self, contributor_id: str,
                              contribution_type: str,
                              description: str,
                              points: float) -> str:
        """记录社区贡献"""
        # 积分倍数
        type_multiplier = {
            "code": 2.0,          # 代码贡献
            "review": 1.5,        # 代码审查
            "testing": 1.2,       # 测试
            "docs": 1.0,          # 文档
            "community": 0.8,     # 社区活动
            "bug_report": 1.5,    # 缺陷报告
            "security": 3.0,      # 安全漏洞
            "governance": 1.0,    # 治理参与
        }

        multiplier = type_multiplier.get(contribution_type, 1.0)
        actual_points = points * multiplier

        contribution = CommunityContribution(
            contribution_id=str(uuid.uuid4()),
            contributor_id=contributor_id,
            contribution_type=contribution_type,
            description=description,
            points=actual_points,
            created_at=time.time(),
        )

        with self.lock:
            if contributor_id not in self.contributions:
                self.contributions[contributor_id] = []
            self.contributions[contributor_id].append(contribution)

            current = self.user_contribution_points.get(contributor_id, 0)
            self.user_contribution_points[contributor_id] = current + actual_points

        self._save_contribution(contribution)
        return contribution.contribution_id

    def get_contribution_leaderboard(self, top_n: int = 20) -> List[Dict]:
        """获取贡献排行榜"""
        sorted_users = sorted(
            self.user_contribution_points.items(),
            key=lambda x: x[1], reverse=True
        )[:top_n]

        leaderboard = []
        for rank, (user_id, points) in enumerate(sorted_users, 1):
            contributions = self.contributions.get(user_id, [])
            leaderboard.append({
                "rank": rank,
                "user_id": user_id,
                "total_points": round(points, 2),
                "contribution_count": len(contributions),
                "role": self.user_roles.get(user_id, GovernanceRole.COMMUNITY).value,
            })

        return leaderboard

    # ============================================================
    # 紧急治理机制
    # ============================================================

    def create_emergency_proposal(self, guardian_id: str,
                                    title: str, description: str,
                                    actions: List[Dict]) -> Optional[str]:
        """创建紧急提案（仅守护者可创建）"""
        if guardian_id not in self.guardians:
            logger.warning(f"[治理引擎] 非守护者尝试创建紧急提案: {guardian_id}")
            return None

        proposal_id = self.create_proposal(
            proposer_id=guardian_id,
            category=ProposalCategory.EMERGENCY,
            title=f"[紧急] {title}",
            description=description,
            specification={"emergency": True, "actions": actions},
            execution_actions=actions,
            deposit=0
        )

        if proposal_id:
            proposal = self.proposals[proposal_id]
            # 紧急提案跳过讨论期
            proposal.stage = ProposalStage.VOTING
            proposal.stage_changed_at = time.time()
            self._save_proposal(proposal)

        return proposal_id

    def emergency_multisig_execute(self, proposal_id: str,
                                     signer_entries: List[Dict[str, str]]) -> bool:
        """紧急多签执行（密码学验证）
        
        Args:
            signer_entries: [{"signer_id": str, "signature": hex_str}, ...]
                           签名对象为 f"emergency:{proposal_id}" 的 SHA256 摘要
        """
        import hashlib
        message = f"emergency:{proposal_id}".encode()
        msg_hash = hashlib.sha256(message).digest()
        
        valid_signers = []
        seen = set()
        
        for entry in signer_entries:
            if not isinstance(entry, dict):
                continue
            signer_id = entry.get("signer_id", "")
            sig_hex = entry.get("signature", "")
            
            if signer_id not in self.guardians or signer_id in seen:
                continue
            
            pubkey_hex = self.guardian_pubkeys.get(signer_id)
            if not pubkey_hex:
                continue
            
            try:
                from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
                from ecdsa.util import sigdecode_der
                vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
                vk.verify(bytes.fromhex(sig_hex), msg_hash, sigdecode=sigdecode_der)
                valid_signers.append(signer_id)
                seen.add(signer_id)
            except ImportError:
                logger.error("[治理引擎] ecdsa library required for multisig")
                return False
            except Exception:
                continue
        
        if len(valid_signers) < self.emergency_multisig_threshold:
            logger.warning(
                f"[治理引擎] 紧急签名不足: {len(valid_signers)} < "
                f"{self.emergency_multisig_threshold}")
            return False

        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal.category != ProposalCategory.EMERGENCY:
            return False

        proposal.stage = ProposalStage.EXECUTION
        proposal.stage_changed_at = time.time()
        self._execute_proposal(proposal)
        return True

    # ============================================================
    # 自动执行引擎
    # ============================================================

    def register_execution_handler(self, action_type: str,
                                     handler: Callable):
        """注册提案执行处理器"""
        self.execution_handlers[action_type] = handler

    def _execute_proposal(self, proposal: GovernanceProposal):
        """执行通过的提案"""
        results = []

        for action in proposal.execution_actions:
            action_type = action.get("type", "")
            handler = self.execution_handlers.get(action_type)

            if handler:
                try:
                    result = handler(action)
                    results.append({
                        "action": action_type,
                        "status": "success",
                        "result": result,
                    })
                except Exception as e:
                    results.append({
                        "action": action_type,
                        "status": "failed",
                        "error": "execution_failed",
                    })
                    logger.error(f"[治理引擎] 执行失败: {action_type} - {e}")
            else:
                results.append({
                    "action": action_type,
                    "status": "no_handler",
                })

        proposal.execution_result = {"actions": results}
        proposal.executed_at = time.time()
        proposal.stage = ProposalStage.EXECUTED
        self._save_proposal(proposal)

        logger.info(
            f"[治理引擎] 提案 {proposal.proposal_id} 执行完成: "
            f"{len(results)} 个操作")

    # ============================================================
    # 查询接口
    # ============================================================

    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """获取提案详情"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return None

        votes = self.votes.get(proposal_id, [])
        total_voted = proposal.votes_for + proposal.votes_against + proposal.votes_abstain

        return {
            "proposal_id": proposal.proposal_id,
            "category": proposal.category.value,
            "stage": proposal.stage.value,
            "title": proposal.title,
            "description": proposal.description,
            "proposer_id": proposal.proposer_id,
            "specification": proposal.specification,
            # 投票状态
            "votes": {
                "for": round(proposal.votes_for, 2),
                "against": round(proposal.votes_against, 2),
                "abstain": round(proposal.votes_abstain, 2),
                "total": round(total_voted, 2),
                "voter_count": proposal.voter_count,
                "quorum": proposal.quorum_threshold,
                "pass_threshold": proposal.pass_threshold,
                "participation_rate": round(
                    total_voted / proposal.total_eligible_weight, 4)
                    if proposal.total_eligible_weight > 0 else 0,
            },
            # 时间
            "created_at": proposal.created_at,
            "stage_changed_at": proposal.stage_changed_at,
            "voting_ends_at": (
                proposal.stage_changed_at + proposal.voting_days * 86400
                if proposal.stage == ProposalStage.VOTING else None),
            "timelock_ends_at": (
                proposal.stage_changed_at + proposal.timelock_days * 86400
                if proposal.stage == ProposalStage.TIMELOCK else None),
            # 执行
            "execution_result": proposal.execution_result,
            "deposit_amount": proposal.deposit_amount,
        }

    def list_proposals(self, stage: Optional[ProposalStage] = None,
                        category: Optional[ProposalCategory] = None,
                        limit: int = 50) -> List[Dict]:
        """列出提案"""
        proposals = list(self.proposals.values())

        if stage:
            proposals = [p for p in proposals if p.stage == stage]
        if category:
            proposals = [p for p in proposals if p.category == category]

        proposals.sort(key=lambda p: p.created_at, reverse=True)

        return [self.get_proposal(p.proposal_id) for p in proposals[:limit]]

    def get_governance_stats(self) -> Dict:
        """获取治理统计"""
        all_proposals = list(self.proposals.values())

        return {
            "total_proposals": len(all_proposals),
            "by_stage": {
                s.value: sum(1 for p in all_proposals if p.stage == s)
                for s in ProposalStage
            },
            "by_category": {
                c.value: sum(1 for p in all_proposals if p.category == c)
                for c in ProposalCategory
            },
            "total_voters": len(set(
                v.voter_id for votes in self.votes.values()
                for v in votes)),
            "total_delegations": sum(
                1 for d in self.delegations.values() if d.active),
            "total_contribution_points": sum(
                self.user_contribution_points.values()),
            "guardian_count": len(self.guardians),
        }

    # ============================================================
    # 持久化
    # ============================================================

    def _save_proposal(self, p: GovernanceProposal):
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO proposals
                (proposal_id, category, stage, title, description,
                 proposer_id, specification_json, impact_json,
                 quorum_threshold, pass_threshold, veto_threshold,
                 discussion_days, voting_days, timelock_days,
                 created_at, stage_changed_at, executed_at,
                 votes_for, votes_against, votes_abstain,
                 total_eligible_weight, voter_count,
                 execution_actions_json, execution_result_json,
                 deposit_amount, tags_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                p.proposal_id, p.category.value, p.stage.value,
                p.title, p.description, p.proposer_id,
                json.dumps(p.specification), json.dumps(p.impact_analysis),
                p.quorum_threshold, p.pass_threshold, p.veto_threshold,
                p.discussion_days, p.voting_days, p.timelock_days,
                p.created_at, p.stage_changed_at, p.executed_at,
                p.votes_for, p.votes_against, p.votes_abstain,
                p.total_eligible_weight, p.voter_count,
                json.dumps(p.execution_actions), json.dumps(p.execution_result),
                p.deposit_amount, json.dumps(p.tags),
            ))

    def _save_vote(self, v: VoteRecord):
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO vote_records
                (vote_id, proposal_id, voter_id, vote_type, weight,
                 reason, delegated_from, timestamp)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                v.vote_id, v.proposal_id, v.voter_id,
                v.vote_type.value, v.weight, v.reason,
                v.delegated_from, v.timestamp,
            ))

    def _save_delegation(self, d: VoteDelegation):
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO delegations
                (delegation_id, delegator_id, delegate_id,
                 delegation_type, categories_json, conditions_json,
                 weight_ratio, expires_at, created_at, active)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                d.delegation_id, d.delegator_id, d.delegate_id,
                d.delegation_type.value,
                json.dumps([c.value for c in d.categories]),
                json.dumps(d.conditions),
                d.weight_ratio, d.expires_at, d.created_at,
                1 if d.active else 0,
            ))

    def _save_contribution(self, c: CommunityContribution):
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO contributions
                (contribution_id, contributor_id, contribution_type,
                 description, points, verified, verifier_id, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                c.contribution_id, c.contributor_id, c.contribution_type,
                c.description, c.points, 1 if c.verified else 0,
                c.verifier_id, c.created_at,
            ))
