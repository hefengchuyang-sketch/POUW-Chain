# -*- coding: utf-8 -*-
"""
协议费用池模块 - 重新定位国库

设计原则：
1. 国库 = "协议级公共费用池"，不是中心化控制机构
2. 明确国库的能力边界（什么能做，什么不能做）
3. 费用分配完全透明、不可篡改

费用结构（硬编码）：
- 总手续费: 1%
  - 0.5% → 销毁（通缩）
  - 0.3% → 矿工奖励池
  - 0.2% → 协议费用池（原国库）

协议费用池用途（白名单）：
✓ 网络基础设施维护（节点运营、DNS、IPFS 网关）
✓ 安全审计基金
✓ 漏洞赏金计划
✓ 生态激励（需 DAO 投票）

协议费用池禁止事项（硬规则）：
✗ 不能干预任务调度
✗ 不能冻结用户账户
✗ 不能修改结算结果
✗ 不能单方面改变费用分配比例
✗ 不能直接支配用户资金
"""

import time
import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# ============== 硬规则（不可更改）==============

class ProtocolHardRules:
    """协议硬规则 - 国库权限边界"""
    
    # C-09: 统一费率配置（从 fee_config.py 引用）
    from .fee_config import ProtocolFeeRates as _PFR
    TOTAL_FEE_RATE = _PFR.TOTAL                 # 1% 总手续费
    BURN_RATE = _PFR.BURN                       # 0.5% 销毁
    MINER_REWARD_RATE = _PFR.MINER              # 0.3% 矿工奖励
    PROTOCOL_POOL_RATE = _PFR.FOUNDATION         # 0.2% 协议费用池
    
    @classmethod
    def validate_fee_split(cls) -> bool:
        """验证费用分配总和"""
        total = cls.BURN_RATE + cls.MINER_REWARD_RATE + cls.PROTOCOL_POOL_RATE
        return abs(total - cls.TOTAL_FEE_RATE) < 1e-10
    
    @classmethod
    def treasury_cannot_do(cls) -> List[str]:
        """国库不能做的事（硬规则）"""
        return [
            "CANNOT_INTERVENE_SCHEDULING",       # 不能干预任务调度
            "CANNOT_FREEZE_ACCOUNTS",            # 不能冻结用户账户
            "CANNOT_MODIFY_SETTLEMENT",          # 不能修改结算结果
            "CANNOT_CHANGE_FEE_UNILATERALLY",    # 不能单方面改变费用
            "CANNOT_ACCESS_USER_FUNDS",          # 不能直接支配用户资金
            "CANNOT_PAUSE_PROTOCOL",             # 不能暂停协议（除非安全漏洞）
            "CANNOT_BLACKLIST_MINERS",           # 不能黑名单矿工（只有算法评分）
        ]
    
    @classmethod
    def treasury_can_do(cls) -> List[str]:
        """国库可以做的事（白名单）"""
        return [
            "CAN_FUND_INFRASTRUCTURE",           # 资助基础设施
            "CAN_FUND_SECURITY_AUDIT",           # 资助安全审计
            "CAN_FUND_BUG_BOUNTY",               # 资助漏洞赏金
            "CAN_FUND_ECOSYSTEM_GRANT",          # 资助生态激励（需投票）
            "CAN_BURN_TOKENS",                   # 销毁代币（通缩）
            "CAN_DISTRIBUTE_REWARDS",            # 分发矿工奖励
        ]


# ============== 枚举定义 ==============

class SpendingCategory(Enum):
    """支出类别"""
    INFRASTRUCTURE = "infrastructure"       # 基础设施
    SECURITY_AUDIT = "security_audit"       # 安全审计
    BUG_BOUNTY = "bug_bounty"               # 漏洞赏金
    ECOSYSTEM_GRANT = "ecosystem_grant"     # 生态激励
    EMERGENCY = "emergency"                 # 紧急（安全漏洞）


class SpendingStatus(Enum):
    """支出状态"""
    PROPOSED = "proposed"                   # 已提议
    VOTING = "voting"                       # 投票中
    APPROVED = "approved"                   # 已批准
    EXECUTED = "executed"                   # 已执行
    REJECTED = "rejected"                   # 已拒绝


# ============== 数据结构 ==============

@dataclass
class FeeDistribution:
    """费用分配记录"""
    tx_id: str
    total_amount: float
    
    burn_amount: float = 0                  # 销毁金额
    miner_reward_amount: float = 0          # 矿工奖励
    protocol_pool_amount: float = 0         # 协议费用池
    
    timestamp: float = field(default_factory=time.time)
    block_height: int = 0
    
    def validate(self) -> Tuple[bool, str]:
        """验证分配是否符合硬规则"""
        expected_burn = self.total_amount * ProtocolHardRules.BURN_RATE / ProtocolHardRules.TOTAL_FEE_RATE
        expected_miner = self.total_amount * ProtocolHardRules.MINER_REWARD_RATE / ProtocolHardRules.TOTAL_FEE_RATE
        expected_pool = self.total_amount * ProtocolHardRules.PROTOCOL_POOL_RATE / ProtocolHardRules.TOTAL_FEE_RATE
        
        tolerance = 0.0001  # 允许的误差
        
        if abs(self.burn_amount - expected_burn) > tolerance:
            return False, f"销毁金额不正确: 预期 {expected_burn}, 实际 {self.burn_amount}"
        
        if abs(self.miner_reward_amount - expected_miner) > tolerance:
            return False, f"矿工奖励不正确: 预期 {expected_miner}, 实际 {self.miner_reward_amount}"
        
        if abs(self.protocol_pool_amount - expected_pool) > tolerance:
            return False, f"协议费用池不正确: 预期 {expected_pool}, 实际 {self.protocol_pool_amount}"
        
        return True, "分配验证通过"


@dataclass
class ProtocolFeePool:
    """协议费用池（原国库）"""
    pool_id: str = "protocol_fee_pool"
    
    # 余额
    balance: float = 0
    locked_balance: float = 0               # 已批准但未执行的支出
    
    # 收入统计
    total_income: float = 0
    
    # 支出统计
    total_spent: float = 0
    spent_by_category: Dict[str, float] = field(default_factory=dict)
    
    # 销毁统计
    total_burned: float = 0
    
    # 时间
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    
    def available_balance(self) -> float:
        """可用余额"""
        return self.balance - self.locked_balance
    
    def to_dict(self) -> Dict:
        return {
            "pool_id": self.pool_id,
            "balance": self.balance,
            "locked_balance": self.locked_balance,
            "available_balance": self.available_balance(),
            "total_income": self.total_income,
            "total_spent": self.total_spent,
            "total_burned": self.total_burned,
            "spent_by_category": self.spent_by_category,
        }


@dataclass
class SpendingProposal:
    """支出提案"""
    proposal_id: str = field(default_factory=lambda: f"spend_{uuid.uuid4().hex[:8]}")
    
    category: SpendingCategory = SpendingCategory.INFRASTRUCTURE
    amount: float = 0
    recipient: str = ""
    description: str = ""
    
    # 投票
    votes_for: float = 0
    votes_against: float = 0
    voter_count: int = 0
    voters: set = field(default_factory=set)  # 已投票地址集合，防重复
    
    # 状态
    status: SpendingStatus = SpendingStatus.PROPOSED
    
    # 时间
    created_at: float = field(default_factory=time.time)
    voting_ends: float = 0
    executed_at: float = 0
    
    # 执行者（多签）
    executed_by: List[str] = field(default_factory=list)
    
    def approval_rate(self) -> float:
        total = self.votes_for + self.votes_against
        if total == 0:
            return 0
        return self.votes_for / total * 100
    
    def is_approved(self, quorum: float, threshold: float, total_voting_power: float) -> bool:
        """检查是否通过"""
        # 检查法定人数
        total_votes = self.votes_for + self.votes_against
        if total_votes < total_voting_power * quorum / 100:
            return False
        
        # 检查通过阈值
        return self.approval_rate() >= threshold


# ============== 协议费用池管理器 ==============

class ProtocolFeePoolManager:
    """
    协议费用池管理器
    
    关键特性：
    1. 费用分配完全透明
    2. 支出必须经过 DAO 投票
    3. 禁止事项由硬规则约束
    """
    
    # 治理参数
    QUORUM_PERCENT = 10                     # 法定人数 10%
    APPROVAL_THRESHOLD = 51                 # 通过阈值 51%
    VOTING_PERIOD_DAYS = 7                  # 投票期 7 天
    MIN_STAKE_TO_VOTE = 100                 # 最低投票质押
    MIN_STAKE_TO_PROPOSE = 1000             # 最低提案质押
    
    # 紧急提案参数（安全漏洞）
    EMERGENCY_QUORUM = 5                    # 紧急法定人数 5%
    EMERGENCY_THRESHOLD = 66                # 紧急通过阈值 66%
    EMERGENCY_VOTING_HOURS = 24             # 紧急投票 24 小时
    
    def __init__(self):
        self.pool = ProtocolFeePool()
        self.proposals: Dict[str, SpendingProposal] = {}
        self.fee_distributions: List[FeeDistribution] = []
        self.burn_records: List[Dict] = []
        self.miner_reward_pool: float = 0   # 矿工奖励池
        
        # 投票权（模拟）
        self.voting_power: Dict[str, float] = {}
        self.total_voting_power: float = 0
    
    def process_fee(self, tx_id: str, fee_amount: float, block_height: int = 0) -> FeeDistribution:
        """
        处理交易手续费（自动分配）
        
        分配比例（硬编码）：
        - 0.5% 销毁
        - 0.3% 矿工奖励
        - 0.2% 协议费用池
        """
        # 计算分配
        burn_amount = fee_amount * (ProtocolHardRules.BURN_RATE / ProtocolHardRules.TOTAL_FEE_RATE)
        miner_reward = fee_amount * (ProtocolHardRules.MINER_REWARD_RATE / ProtocolHardRules.TOTAL_FEE_RATE)
        pool_amount = fee_amount * (ProtocolHardRules.PROTOCOL_POOL_RATE / ProtocolHardRules.TOTAL_FEE_RATE)
        
        # 创建分配记录
        distribution = FeeDistribution(
            tx_id=tx_id,
            total_amount=fee_amount,
            burn_amount=burn_amount,
            miner_reward_amount=miner_reward,
            protocol_pool_amount=pool_amount,
            block_height=block_height,
        )
        
        # 验证分配
        ok, msg = distribution.validate()
        if not ok:
            raise ValueError(f"费用分配验证失败: {msg}")
        
        # 执行分配
        self._execute_burn(burn_amount, tx_id)
        self._add_miner_reward(miner_reward, tx_id)
        self._add_to_pool(pool_amount, tx_id)
        
        self.fee_distributions.append(distribution)
        # 防止 fee_distributions 无限增长
        if len(self.fee_distributions) > 10000:
            self.fee_distributions = self.fee_distributions[-5000:]
        
        return distribution
    
    def _execute_burn(self, amount: float, tx_id: str):
        """执行销毁"""
        self.pool.total_burned += amount
        self.burn_records.append({
            "tx_id": tx_id,
            "amount": amount,
            "timestamp": time.time(),
        })
        # 防止 burn_records 无限增长
        if len(self.burn_records) > 10000:
            self.burn_records = self.burn_records[-5000:]
    
    def _add_miner_reward(self, amount: float, tx_id: str):
        """添加到矿工奖励池"""
        self.miner_reward_pool += amount
    
    def _add_to_pool(self, amount: float, tx_id: str):
        """添加到协议费用池"""
        self.pool.balance += amount
        self.pool.total_income += amount
        self.pool.last_updated = time.time()
    
    def create_spending_proposal(
        self,
        proposer: str,
        proposer_stake: float,
        category: SpendingCategory,
        amount: float,
        recipient: str,
        description: str,
    ) -> Tuple[Optional[SpendingProposal], str]:
        """创建支出提案"""
        # 检查质押
        if proposer_stake < self.MIN_STAKE_TO_PROPOSE:
            return None, f"质押不足: 需要 {self.MIN_STAKE_TO_PROPOSE}, 实际 {proposer_stake}"
        
        # 检查余额
        if amount > self.pool.available_balance():
            return None, f"余额不足: 可用 {self.pool.available_balance()}, 请求 {amount}"
        
        # 检查类别是否允许
        allowed_categories = [
            SpendingCategory.INFRASTRUCTURE,
            SpendingCategory.SECURITY_AUDIT,
            SpendingCategory.BUG_BOUNTY,
            SpendingCategory.ECOSYSTEM_GRANT,
            SpendingCategory.EMERGENCY,
        ]
        if category not in allowed_categories:
            return None, f"不允许的支出类别: {category.value}"
        
        # 创建提案
        proposal = SpendingProposal(
            category=category,
            amount=amount,
            recipient=recipient,
            description=description,
            status=SpendingStatus.VOTING,
        )
        
        # 设置投票截止时间
        if category == SpendingCategory.EMERGENCY:
            proposal.voting_ends = time.time() + self.EMERGENCY_VOTING_HOURS * 3600
        else:
            proposal.voting_ends = time.time() + self.VOTING_PERIOD_DAYS * 86400
        
        # 锁定金额
        self.pool.locked_balance += amount
        
        self.proposals[proposal.proposal_id] = proposal
        
        return proposal, "提案创建成功"
    
    def vote_on_proposal(
        self,
        proposal_id: str,
        voter: str,
        voter_stake: float,
        vote_for: bool,
    ) -> Tuple[bool, str]:
        """投票"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, "提案不存在"
        
        if proposal.status != SpendingStatus.VOTING:
            return False, f"提案状态不是投票中: {proposal.status.value}"
        
        if time.time() > proposal.voting_ends:
            return False, "投票已结束"
        
        if voter_stake < self.MIN_STAKE_TO_VOTE:
            return False, f"质押不足: 需要 {self.MIN_STAKE_TO_VOTE}"
        
        # 防止重复投票
        if voter in proposal.voters:
            return False, "您已对此提案投过票"
        
        # 记录投票
        voting_power = voter_stake  # 简化：投票权 = 质押
        if vote_for:
            proposal.votes_for += voting_power
        else:
            proposal.votes_against += voting_power
        
        proposal.voter_count += 1
        proposal.voters.add(voter)
        
        return True, "投票成功"
    
    def finalize_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        """结算提案"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, "提案不存在"
        
        if proposal.status != SpendingStatus.VOTING:
            return False, f"提案状态不是投票中"
        
        if time.time() < proposal.voting_ends:
            return False, "投票尚未结束"
        
        # 确定阈值
        if proposal.category == SpendingCategory.EMERGENCY:
            quorum = self.EMERGENCY_QUORUM
            threshold = self.EMERGENCY_THRESHOLD
        else:
            quorum = self.QUORUM_PERCENT
            threshold = self.APPROVAL_THRESHOLD
        
        # 检查是否通过
        if proposal.is_approved(quorum, threshold, self.total_voting_power):
            proposal.status = SpendingStatus.APPROVED
            return True, "提案通过"
        else:
            proposal.status = SpendingStatus.REJECTED
            # 解锁金额
            self.pool.locked_balance -= proposal.amount
            return False, "提案未通过"
    
    def execute_spending(
        self,
        proposal_id: str,
        executors: List[str],
    ) -> Tuple[bool, str]:
        """执行支出"""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, "提案不存在"
        
        if proposal.status != SpendingStatus.APPROVED:
            return False, f"提案未批准: {proposal.status.value}"
        
        # 验证执行者（多签）
        # 这里简化处理，实际应该验证多签
        if len(executors) < 2:
            return False, "需要至少 2 个签名"
        
        # 执行转账
        self.pool.balance -= proposal.amount
        self.pool.locked_balance -= proposal.amount
        self.pool.total_spent += proposal.amount
        
        # 按类别统计
        category_key = proposal.category.value
        self.pool.spent_by_category[category_key] = \
            self.pool.spent_by_category.get(category_key, 0) + proposal.amount
        
        proposal.status = SpendingStatus.EXECUTED
        proposal.executed_at = time.time()
        proposal.executed_by = executors
        
        return True, f"支出执行成功: {proposal.amount} -> {proposal.recipient}"
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "pool": self.pool.to_dict(),
            "miner_reward_pool": self.miner_reward_pool,
            "total_burned": self.pool.total_burned,
            "fee_distribution_count": len(self.fee_distributions),
            "proposal_count": len(self.proposals),
            "hard_rules": {
                "cannot_do": ProtocolHardRules.treasury_cannot_do(),
                "can_do": ProtocolHardRules.treasury_can_do(),
            },
        }
    
    def verify_action_allowed(self, action: str) -> Tuple[bool, str]:
        """验证操作是否允许"""
        forbidden = ProtocolHardRules.treasury_cannot_do()
        
        # 检查禁止操作
        action_map = {
            "freeze_account": "CANNOT_FREEZE_ACCOUNTS",
            "modify_settlement": "CANNOT_MODIFY_SETTLEMENT",
            "intervene_scheduling": "CANNOT_INTERVENE_SCHEDULING",
            "change_fee": "CANNOT_CHANGE_FEE_UNILATERALLY",
            "access_user_funds": "CANNOT_ACCESS_USER_FUNDS",
            "pause_protocol": "CANNOT_PAUSE_PROTOCOL",
            "blacklist_miner": "CANNOT_BLACKLIST_MINERS",
        }
        
        if action in action_map:
            rule = action_map[action]
            if rule in forbidden:
                return False, f"操作被硬规则禁止: {rule}"
        
        return True, "操作允许"


# ============== 测试 ==============

if __name__ == "__main__":
    print("=" * 60)
    print("协议费用池模块测试")
    print("=" * 60)
    
    # 验证硬规则
    print("\n[1] 验证硬规则...")
    print(f"    费用分配验证: {ProtocolHardRules.validate_fee_split()}")
    print(f"    总费率: {ProtocolHardRules.TOTAL_FEE_RATE * 100}%")
    print(f"    销毁: {ProtocolHardRules.BURN_RATE * 100}%")
    print(f"    矿工: {ProtocolHardRules.MINER_REWARD_RATE * 100}%")
    print(f"    费用池: {ProtocolHardRules.PROTOCOL_POOL_RATE * 100}%")
    
    print("\n[2] 国库禁止事项...")
    for rule in ProtocolHardRules.treasury_cannot_do():
        print(f"    ✗ {rule}")
    
    print("\n[3] 国库允许事项...")
    for rule in ProtocolHardRules.treasury_can_do():
        print(f"    ✓ {rule}")
    
    # 初始化管理器
    manager = ProtocolFeePoolManager()
    manager.total_voting_power = 10000  # 模拟总投票权
    
    # 4. 处理交易费用
    print("\n[4] 处理交易费用...")
    fee_amount = 100  # 假设 100 MAIN 的 1% = 1 MAIN 手续费
    distribution = manager.process_fee("tx_001", fee_amount)
    print(f"    总费用: {distribution.total_amount}")
    print(f"    销毁: {distribution.burn_amount}")
    print(f"    矿工奖励: {distribution.miner_reward_amount}")
    print(f"    费用池: {distribution.protocol_pool_amount}")
    
    # 5. 创建支出提案
    print("\n[5] 创建支出提案...")
    proposal, msg = manager.create_spending_proposal(
        proposer="user_001",
        proposer_stake=2000,
        category=SpendingCategory.SECURITY_AUDIT,
        amount=10,
        recipient="auditor_001",
        description="安全审计合约代码",
    )
    if proposal:
        print(f"    提案ID: {proposal.proposal_id}")
        print(f"    金额: {proposal.amount}")
        print(f"    状态: {proposal.status.value}")
    
    # 6. 投票
    print("\n[6] 投票...")
    ok, msg = manager.vote_on_proposal(
        proposal.proposal_id, "voter_001", 5000, True
    )
    print(f"    投票结果: {msg}")
    ok, msg = manager.vote_on_proposal(
        proposal.proposal_id, "voter_002", 3000, True
    )
    print(f"    投票结果: {msg}")
    
    # 7. 验证禁止操作
    print("\n[7] 验证禁止操作...")
    for action in ["freeze_account", "modify_settlement", "intervene_scheduling"]:
        ok, msg = manager.verify_action_allowed(action)
        print(f"    {action}: {'✓ 允许' if ok else '✗ 禁止'}")
    
    # 8. 统计
    print("\n[8] 统计信息...")
    stats = manager.get_statistics()
    print(f"    费用池余额: {stats['pool']['balance']}")
    print(f"    矿工奖励池: {stats['miner_reward_pool']}")
    print(f"    总销毁: {stats['total_burned']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
