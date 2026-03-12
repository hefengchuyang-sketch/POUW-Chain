"""
pouw_scoring.py - POUW 三层评分架构

Phase 6 实现：

Layer 1 - 客观指标层 (Objective Metrics Layer)
    - 自动采集，不可人为干预
    - 响应延迟、任务成功率、在线时长、出块稳定性
    - 只是"传感器数据"，不生成结论

Layer 2 - 混合反馈层 (Hybrid Feedback Layer)
    - 用户评分 1-5（需支付小额 MAIN）
    - 防刷分、防女巫
    - 只影响调度，不影响共识/治理

Layer 3 - 治理演进层 (Governance Layer)
    - 评分参数可由治理投票修改
    - 不写死，可演进

核心原则：
- 评分只是市场信号，不是共识本身
- 共识存在于链的安全与治理层
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import time
import math


# ============================================================
# Layer 1: 客观指标层
# ============================================================

@dataclass
class ObjectiveMetrics:
    """客观指标（自动采集，不可篡改）。"""
    miner_id: str
    
    # 响应性能
    avg_response_latency_ms: float = 0.0
    p95_response_latency_ms: float = 0.0
    
    # 任务完成
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    # 在线稳定性
    uptime_hours: float = 0.0
    downtime_events: int = 0
    
    # 出块参与
    blocks_mined: int = 0
    block_participation_rate: float = 0.0
    
    # 时间戳
    last_updated: float = field(default_factory=time.time)

    def completion_rate(self) -> float:
        if self.total_tasks == 0:
            return 1.0
        return self.completed_tasks / self.total_tasks

    def uptime_rate(self) -> float:
        """估算在线率。"""
        # 简化：假设每次 downtime 平均 1 小时
        if self.uptime_hours == 0:
            return 0.0
        total_time = self.uptime_hours + self.downtime_events
        return self.uptime_hours / total_time if total_time > 0 else 1.0


class ObjectiveMetricsCollector:
    """客观指标采集器（自动、不可干预）。"""

    def __init__(self):
        self.metrics: Dict[str, ObjectiveMetrics] = {}

    def get_or_create(self, miner_id: str) -> ObjectiveMetrics:
        if miner_id not in self.metrics:
            self.metrics[miner_id] = ObjectiveMetrics(miner_id=miner_id)
        return self.metrics[miner_id]

    def record_task(
        self,
        miner_id: str,
        success: bool,
        response_time_ms: float,
    ):
        """记录任务执行（自动采集）。"""
        m = self.get_or_create(miner_id)
        m.total_tasks += 1
        if success:
            m.completed_tasks += 1
        else:
            m.failed_tasks += 1

        # 更新平均延迟（滑动平均）
        if m.total_tasks == 1:
            m.avg_response_latency_ms = response_time_ms
            m.p95_response_latency_ms = response_time_ms
        else:
            alpha = 0.1  # 滑动平均系数
            m.avg_response_latency_ms = (
                (1 - alpha) * m.avg_response_latency_ms + alpha * response_time_ms
            )
            # P95 估算（简化）
            if response_time_ms > m.p95_response_latency_ms:
                m.p95_response_latency_ms = (
                    (1 - alpha) * m.p95_response_latency_ms + alpha * response_time_ms
                )

        m.last_updated = time.time()

    def record_uptime(self, miner_id: str, hours: float):
        """记录在线时长。"""
        m = self.get_or_create(miner_id)
        m.uptime_hours += hours
        m.last_updated = time.time()

    def record_downtime(self, miner_id: str):
        """记录下线事件。"""
        m = self.get_or_create(miner_id)
        m.downtime_events += 1
        m.last_updated = time.time()

    def record_block(self, miner_id: str):
        """记录出块。"""
        m = self.get_or_create(miner_id)
        m.blocks_mined += 1
        m.last_updated = time.time()


# ============================================================
# Layer 2: 混合反馈层
# ============================================================

@dataclass
class UserFeedback:
    """用户评分（需支付小费/质押金才能打分）。
    
    PRD v0.9 规范：
    - 评分范围: 0-5 星（支持 0.5 步进）
    - 必须支付小费才能评分（不给小费 = 不打分）
    - 小费金额由用户决定（最低阈值可配置）
    - 小费直接奖励给被评价的矿工
    """
    feedback_id: str
    job_id: str
    miner_id: str
    user_id: str
    rating: float                   # 0-5 星（0.5 步进：0, 0.5, 1.0, ... 5.0）
    tip_amount: float               # 用户给的小费金额（质押金）
    comment: str = ""
    timestamp: float = field(default_factory=time.time)
    
    # 有效评分值
    VALID_RATINGS = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    
    def __post_init__(self):
        """验证评分值。"""
        if self.rating not in self.VALID_RATINGS:
            raise ValueError(f"Invalid rating {self.rating}. Must be one of {self.VALID_RATINGS}")


class UserFeedbackSystem:
    """用户反馈系统（PRD v0.9 规范）。

    规则：
    - 必须支付小费（质押金）才能评分 - 不给小费 = 不打分
    - 评分范围 0-5 星（0.5 步进）
    - 小费直接奖励给被评价的矿工
    - 评分只影响调度，不影响共识/治理
    - 最低小费阈值可配置（防刷分）
    """

    # 有效评分值
    VALID_RATINGS = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]

    def __init__(
        self,
        min_tip_amount: float = 0.001,  # 最低小费阈值（防刷分）
        treasury: Any = None,
        treasury_tip_ratio: float = 0.002,  # 0.2% 基金会运维（去中心化多签）
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.min_tip_amount = min_tip_amount
        self.treasury = treasury
        self.treasury_tip_ratio = treasury_tip_ratio  # 基金会抽成比例
        self.feedbacks: List[UserFeedback] = []
        self.miner_ratings: Dict[str, List[float]] = {}  # miner_id -> [ratings]
        self.miner_tips: Dict[str, float] = {}  # miner_id -> total tips
        self._log_fn = log_fn or (lambda x: None)

    def _log(self, msg: str):
        self._log_fn(f"[FEEDBACK] {msg}")

    def submit_feedback(
        self,
        job_id: str,
        miner_id: str,
        user_id: str,
        rating: float,
        tip_amount: float,
        account: Any,
        miner_account: Any = None,
        comment: str = "",
    ) -> Optional[UserFeedback]:
        """提交用户反馈（必须支付小费才能评分）。

        PRD v0.9 规范：
        - 不给小费就是不打分
        - 评分范围 0-5 星（0.5 步进）
        - 小费直接奖励给矿工（扣除财政抽成）

        Args:
            job_id: 任务 ID
            miner_id: 矿工 ID
            user_id: 用户 ID
            rating: 评分 0-5（0.5 步进）
            tip_amount: 小费金额（质押金）
            account: 用户账户（用于扣费）
            miner_account: 矿工账户（用于收取小费）
            comment: 评论

        Returns:
            反馈记录（失败返回 None）
        """
        # 验证小费金额 - 不给小费就是不打分
        if tip_amount < self.min_tip_amount:
            self._log(f"Tip amount {tip_amount} below minimum {self.min_tip_amount} - cannot rate")
            return None

        # 验证评分范围（0-5，0.5 步进）
        if rating not in self.VALID_RATINGS:
            self._log(f"Invalid rating: {rating}. Must be one of {self.VALID_RATINGS}")
            return None

        # 扣除小费金额
        if hasattr(account, 'available_main'):
            if account.available_main() < tip_amount:
                self._log(f"Insufficient balance for tip: need {tip_amount}, have {account.available_main()}")
                return None
            account.debit_main(tip_amount)

        # 计算分成
        treasury_share = tip_amount * self.treasury_tip_ratio
        miner_share = tip_amount - treasury_share

        # 财政收取抽成
        if self.treasury:
            self.treasury.balance += treasury_share
            self.treasury.total_collected += treasury_share

        # 小费直接奖励给矿工
        if miner_account and hasattr(miner_account, 'credit_main'):
            miner_account.credit_main(miner_share)
        
        # 记录矿工累计小费
        if miner_id not in self.miner_tips:
            self.miner_tips[miner_id] = 0.0
        self.miner_tips[miner_id] += miner_share

        import uuid
        feedback = UserFeedback(
            feedback_id=uuid.uuid4().hex[:8],
            job_id=job_id,
            miner_id=miner_id,
            user_id=user_id,
            rating=rating,
            tip_amount=tip_amount,
            comment=comment,
        )

        self.feedbacks.append(feedback)

        # 更新矿工评分
        if miner_id not in self.miner_ratings:
            self.miner_ratings[miner_id] = []
        self.miner_ratings[miner_id].append(rating)

        self._log(f"{user_id} rated {miner_id}: {rating}/5 stars (tip: {tip_amount} MAIN, miner gets: {miner_share})")

        return feedback

    def get_miner_rating(self, miner_id: str) -> float:
        """获取矿工平均评分。"""
        ratings = self.miner_ratings.get(miner_id, [])
        if not ratings:
            return 2.5  # 默认中等（0-5 范围的中间值）
        return sum(ratings) / len(ratings)

    def get_miner_rating_count(self, miner_id: str) -> int:
        """获取矿工评分数量。"""
        return len(self.miner_ratings.get(miner_id, []))

    def get_miner_total_tips(self, miner_id: str) -> float:
        """获取矿工累计收到的小费。"""
        return self.miner_tips.get(miner_id, 0.0)


# ============================================================
# Layer 3: 治理演进层 - 评分参数
# ============================================================

@dataclass
class ScoringParameters:
    """评分参数（可由治理修改）。"""
    # 客观指标权重
    weight_latency: float = 0.25
    weight_completion: float = 0.30
    weight_uptime: float = 0.25
    weight_block_participation: float = 0.20

    # 混合反馈权重
    alpha_objective: float = 0.7     # 客观指标占比
    beta_feedback: float = 0.3       # 用户反馈占比

    # 延迟评分参数（ms）
    latency_optimal: float = 100.0   # 最优延迟
    latency_max: float = 5000.0      # 最大可接受延迟

    # 最低评分数量（用户反馈才生效）
    min_feedback_count: int = 5

    def normalize_weights(self):
        """归一化权重。"""
        total = (self.weight_latency + self.weight_completion +
                 self.weight_uptime + self.weight_block_participation)
        if total > 0:
            self.weight_latency /= total
            self.weight_completion /= total
            self.weight_uptime /= total
            self.weight_block_participation /= total


# ============================================================
# 综合评分引擎
# ============================================================

class POUWScoringEngine:
    """POUW 评分引擎（三层架构）。

    Layer 1: 客观指标（自动采集）
    Layer 2: 用户反馈（付费评分）
    Layer 3: 治理参数（可演进）

    输出：调度优先级分数（不是共识权重）
    """

    def __init__(
        self,
        metrics_collector: Optional[ObjectiveMetricsCollector] = None,
        feedback_system: Optional[UserFeedbackSystem] = None,
        parameters: Optional[ScoringParameters] = None,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.metrics = metrics_collector or ObjectiveMetricsCollector()
        self.feedback = feedback_system or UserFeedbackSystem()
        self.params = parameters or ScoringParameters()
        self._log_fn = log_fn or (lambda x: None)

    def _log(self, msg: str):
        self._log_fn(f"[SCORING] {msg}")

    def _score_latency(self, latency_ms: float) -> float:
        """延迟评分 (0-1)。"""
        if latency_ms <= self.params.latency_optimal:
            return 1.0
        if latency_ms >= self.params.latency_max:
            return 0.0
        # 线性衰减
        return 1.0 - (latency_ms - self.params.latency_optimal) / (
            self.params.latency_max - self.params.latency_optimal
        )

    def _score_completion(self, rate: float) -> float:
        """完成率评分 (0-1)。"""
        return rate

    def _score_uptime(self, rate: float) -> float:
        """在线率评分 (0-1)。"""
        return rate

    def _score_block_participation(self, rate: float) -> float:
        """出块参与评分 (0-1)。"""
        return min(1.0, rate)

    def calculate_objective_score(self, miner_id: str) -> float:
        """计算客观指标分数 (0-1)。"""
        m = self.metrics.metrics.get(miner_id)
        if not m:
            return 0.5  # 新矿工默认中等

        p = self.params

        latency_score = self._score_latency(m.avg_response_latency_ms)
        completion_score = self._score_completion(m.completion_rate())
        uptime_score = self._score_uptime(m.uptime_rate())
        block_score = self._score_block_participation(m.block_participation_rate)

        objective_score = (
            p.weight_latency * latency_score +
            p.weight_completion * completion_score +
            p.weight_uptime * uptime_score +
            p.weight_block_participation * block_score
        )

        return objective_score

    def calculate_feedback_score(self, miner_id: str) -> float:
        """计算用户反馈分数 (0-1)。"""
        rating = self.feedback.get_miner_rating(miner_id)
        count = self.feedback.get_miner_rating_count(miner_id)

        # 如果评分数量不足，不使用反馈分数
        if count < self.params.min_feedback_count:
            return 0.5  # 默认中等

        # 1-5 分映射到 0-1
        return (rating - 1) / 4.0

    def calculate_priority_score(self, miner_id: str) -> float:
        """计算调度优先级分数 (0-1)。

        FinalScore = α * ObjectiveScore + β * UserFeedbackScore
        """
        objective = self.calculate_objective_score(miner_id)
        feedback = self.calculate_feedback_score(miner_id)

        p = self.params
        
        # 如果反馈数量不足，只用客观分数
        count = self.feedback.get_miner_rating_count(miner_id)
        if count < p.min_feedback_count:
            return objective

        priority = p.alpha_objective * objective + p.beta_feedback * feedback

        return priority

    def rank_miners(self, miner_ids: List[str]) -> List[tuple]:
        """对矿工进行优先级排序。

        Returns:
            [(miner_id, score), ...] 按分数降序
        """
        scored = [(mid, self.calculate_priority_score(mid)) for mid in miner_ids]
        scored.sort(key=lambda x: -x[1])
        return scored

    def get_score_breakdown(self, miner_id: str) -> dict:
        """获取分数详情。"""
        m = self.metrics.metrics.get(miner_id)
        
        return {
            "miner_id": miner_id,
            "objective_score": self.calculate_objective_score(miner_id),
            "feedback_score": self.calculate_feedback_score(miner_id),
            "priority_score": self.calculate_priority_score(miner_id),
            "metrics": {
                "avg_latency_ms": m.avg_response_latency_ms if m else 0,
                "completion_rate": m.completion_rate() if m else 0,
                "uptime_rate": m.uptime_rate() if m else 0,
                "total_tasks": m.total_tasks if m else 0,
            } if m else {},
            "feedback": {
                "rating": self.feedback.get_miner_rating(miner_id),
                "count": self.feedback.get_miner_rating_count(miner_id),
            },
            "parameters": {
                "alpha": self.params.alpha_objective,
                "beta": self.params.beta_feedback,
            },
        }

    def update_parameters(self, new_params: ScoringParameters):
        """更新评分参数（治理层调用）。"""
        self.params = new_params
        self._log(f"Parameters updated: α={new_params.alpha_objective}, β={new_params.beta_feedback}")

    def __repr__(self) -> str:
        return f"POUWScoringEngine(miners={len(self.metrics.metrics)}, feedbacks={len(self.feedback.feedbacks)})"
