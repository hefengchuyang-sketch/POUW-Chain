# -*- coding: utf-8 -*-
"""
矿工行为评分 - 报价-履约一致性评分

协议层边界声明：
├── 模块：miner_behavior
├── 层级：SERVICE (服务层)
├── 类别：MARKET_OPTIONAL (市场可选)
├── 共识影响：✗ 不影响
└── 确定性要求：✗ 不要求

设计目标：
1. 市场自由，但不是无成本套利
2. 防止只吃高价订单的隐性垄断
3. 保留矿工定价自由

核心规则：
- 长期只接高价任务的矿工不处罚
- 但在「低价订单拥堵时」调度权下降
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import statistics


# ========== 行为类型定义 ==========

class OrderPriceLevel(Enum):
    """订单价格等级"""
    LOW = "low"             # 低价（< 市场均价的 70%）
    MEDIUM = "medium"       # 中等（70% - 130%）
    HIGH = "high"           # 高价（> 130%）
    PREMIUM = "premium"     # 溢价（> 200%）


class FulfillmentStatus(Enum):
    """履约状态"""
    ACCEPTED = "accepted"           # 接受并完成
    REJECTED = "rejected"           # 拒绝
    TIMEOUT = "timeout"             # 超时
    CANCELLED = "cancelled"         # 取消


# ========== 配置常量 ==========

class BehaviorConfig:
    """行为评分配置"""
    
    # 价格分级阈值（相对于市场均价）
    LOW_PRICE_THRESHOLD = 0.70      # < 70% 为低价
    HIGH_PRICE_THRESHOLD = 1.30     # > 130% 为高价
    PREMIUM_PRICE_THRESHOLD = 2.00  # > 200% 为溢价
    
    # 一致性评分权重
    ACCEPTANCE_RATE_WEIGHT = 0.40   # 接受率权重
    PRICE_DIVERSITY_WEIGHT = 0.30   # 价格多样性权重
    CONGESTION_HELP_WEIGHT = 0.30   # 拥堵时帮助权重
    
    # 惩罚阈值
    LOW_SCORE_THRESHOLD = 0.30      # 低于此分数触发调度降权
    SCHEDULING_PENALTY = 0.50       # 调度概率降低 50%
    
    # 统计窗口
    STAT_WINDOW_DAYS = 30           # 30 天统计窗口
    MIN_ORDERS_FOR_SCORE = 10       # 最少订单数才计算分数


# ========== 行为记录 ==========

@dataclass
class OrderRecord:
    """订单记录"""
    order_id: str
    miner_id: str
    
    # 价格信息
    quoted_price: float             # 报价
    market_avg_price: float         # 当时市场均价
    price_level: OrderPriceLevel    # 价格等级
    
    # 履约信息
    status: FulfillmentStatus
    response_time_seconds: float    # 响应时间
    
    # 时间信息
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    # 拥堵信息
    was_congested: bool = False     # 下单时是否拥堵
    congestion_level: float = 0.0   # 拥堵程度 0-1


@dataclass
class MinerBehaviorScore:
    """矿工行为评分"""
    miner_id: str
    calculated_at: datetime
    
    # 基础统计
    total_orders: int = 0
    accepted_orders: int = 0
    rejected_orders: int = 0
    
    # 价格分布
    low_price_accepted: int = 0
    medium_price_accepted: int = 0
    high_price_accepted: int = 0
    premium_price_accepted: int = 0
    
    # 拥堵时表现
    congestion_orders_received: int = 0
    congestion_orders_accepted: int = 0
    
    # 分数组件
    acceptance_rate: float = 0.0        # 总体接受率
    price_diversity_score: float = 0.0  # 价格多样性（0-1）
    congestion_help_score: float = 0.0  # 拥堵帮助分（0-1）
    
    # 最终分数
    final_score: float = 0.0            # 0-1
    scheduling_multiplier: float = 1.0  # 调度权重乘数
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "miner_id": self.miner_id,
            "calculated_at": self.calculated_at.isoformat(),
            "statistics": {
                "total_orders": self.total_orders,
                "accepted": self.accepted_orders,
                "rejected": self.rejected_orders,
                "acceptance_rate": f"{self.acceptance_rate:.1%}"
            },
            "price_distribution": {
                "low": self.low_price_accepted,
                "medium": self.medium_price_accepted,
                "high": self.high_price_accepted,
                "premium": self.premium_price_accepted
            },
            "congestion_behavior": {
                "received": self.congestion_orders_received,
                "accepted": self.congestion_orders_accepted,
                "help_score": f"{self.congestion_help_score:.1%}"
            },
            "scores": {
                "price_diversity": f"{self.price_diversity_score:.2f}",
                "congestion_help": f"{self.congestion_help_score:.2f}",
                "final_score": f"{self.final_score:.2f}",
                "scheduling_multiplier": f"{self.scheduling_multiplier:.2f}"
            }
        }


# ========== 行为分析服务 ==========

class MinerBehaviorAnalyzer:
    """
    矿工行为分析器
    
    分析矿工的报价-履约一致性
    """
    
    def __init__(self):
        self.records: Dict[str, List[OrderRecord]] = {}  # miner_id -> records
        self.scores: Dict[str, MinerBehaviorScore] = {}  # miner_id -> score
        self.market_stats: Dict[str, float] = {}         # sector -> avg_price
    
    def classify_price_level(
        self,
        price: float,
        market_avg: float
    ) -> OrderPriceLevel:
        """分类价格等级"""
        if market_avg <= 0:
            return OrderPriceLevel.MEDIUM
        
        ratio = price / market_avg
        
        if ratio >= BehaviorConfig.PREMIUM_PRICE_THRESHOLD:
            return OrderPriceLevel.PREMIUM
        elif ratio >= BehaviorConfig.HIGH_PRICE_THRESHOLD:
            return OrderPriceLevel.HIGH
        elif ratio >= BehaviorConfig.LOW_PRICE_THRESHOLD:
            return OrderPriceLevel.MEDIUM
        else:
            return OrderPriceLevel.LOW
    
    def record_order(
        self,
        order_id: str,
        miner_id: str,
        quoted_price: float,
        market_avg_price: float,
        status: FulfillmentStatus,
        response_time: float,
        was_congested: bool = False,
        congestion_level: float = 0.0
    ) -> OrderRecord:
        """记录订单"""
        record = OrderRecord(
            order_id=order_id,
            miner_id=miner_id,
            quoted_price=quoted_price,
            market_avg_price=market_avg_price,
            price_level=self.classify_price_level(quoted_price, market_avg_price),
            status=status,
            response_time_seconds=response_time,
            created_at=datetime.now(),
            completed_at=datetime.now() if status == FulfillmentStatus.ACCEPTED else None,
            was_congested=was_congested,
            congestion_level=congestion_level
        )
        
        if miner_id not in self.records:
            self.records[miner_id] = []
        self.records[miner_id].append(record)
        # 每个矿工最多保留最近 500 条记录，防止无界增长
        if len(self.records[miner_id]) > 500:
            self.records[miner_id] = self.records[miner_id][-500:]
        
        return record
    
    def calculate_score(self, miner_id: str) -> MinerBehaviorScore:
        """
        计算矿工行为评分
        
        评分维度：
        1. 价格多样性：是否接受各种价位的订单
        2. 拥堵时帮助：在网络拥堵时是否愿意帮忙
        """
        if miner_id not in self.records:
            return self._empty_score(miner_id)
        
        # 获取统计窗口内的记录
        cutoff = datetime.now() - timedelta(days=BehaviorConfig.STAT_WINDOW_DAYS)
        records = [r for r in self.records[miner_id] if r.created_at >= cutoff]
        
        if len(records) < BehaviorConfig.MIN_ORDERS_FOR_SCORE:
            return self._empty_score(miner_id)
        
        score = MinerBehaviorScore(
            miner_id=miner_id,
            calculated_at=datetime.now(),
            total_orders=len(records)
        )
        
        # 统计各类订单
        for record in records:
            if record.status == FulfillmentStatus.ACCEPTED:
                score.accepted_orders += 1
                
                if record.price_level == OrderPriceLevel.LOW:
                    score.low_price_accepted += 1
                elif record.price_level == OrderPriceLevel.MEDIUM:
                    score.medium_price_accepted += 1
                elif record.price_level == OrderPriceLevel.HIGH:
                    score.high_price_accepted += 1
                else:
                    score.premium_price_accepted += 1
            else:
                score.rejected_orders += 1
            
            if record.was_congested:
                score.congestion_orders_received += 1
                if record.status == FulfillmentStatus.ACCEPTED:
                    score.congestion_orders_accepted += 1
        
        # 计算接受率
        score.acceptance_rate = score.accepted_orders / score.total_orders
        
        # 计算价格多样性分数
        score.price_diversity_score = self._calculate_diversity(
            score.low_price_accepted,
            score.medium_price_accepted,
            score.high_price_accepted,
            score.premium_price_accepted
        )
        
        # 计算拥堵帮助分数
        if score.congestion_orders_received > 0:
            score.congestion_help_score = (
                score.congestion_orders_accepted / score.congestion_orders_received
            )
        else:
            score.congestion_help_score = 0.5  # 无数据给中等分
        
        # 计算最终分数
        score.final_score = (
            score.acceptance_rate * BehaviorConfig.ACCEPTANCE_RATE_WEIGHT +
            score.price_diversity_score * BehaviorConfig.PRICE_DIVERSITY_WEIGHT +
            score.congestion_help_score * BehaviorConfig.CONGESTION_HELP_WEIGHT
        )
        
        # 计算调度乘数
        if score.final_score < BehaviorConfig.LOW_SCORE_THRESHOLD:
            score.scheduling_multiplier = BehaviorConfig.SCHEDULING_PENALTY
        else:
            # 线性映射：0.3-1.0 -> 0.5-1.0
            score.scheduling_multiplier = 0.5 + (score.final_score - 0.3) * (0.5 / 0.7)
        
        score.scheduling_multiplier = max(0.1, min(1.0, score.scheduling_multiplier))
        
        self.scores[miner_id] = score
        return score
    
    def _calculate_diversity(
        self,
        low: int,
        medium: int,
        high: int,
        premium: int
    ) -> float:
        """
        计算价格多样性分数
        
        使用改良的香农熵：接受各价位订单得分高
        """
        total = low + medium + high + premium
        if total == 0:
            return 0.0
        
        # 计算各价位占比
        proportions = [
            low / total,
            medium / total,
            high / total,
            premium / total
        ]
        
        # 理想分布是均匀分布 (0.25, 0.25, 0.25, 0.25)
        # 但我们更希望接受低价订单，所以调整权重
        ideal = [0.30, 0.40, 0.20, 0.10]  # 期望更多中低价
        
        # 计算与理想分布的接近程度
        deviation = sum(abs(p - i) for p, i in zip(proportions, ideal))
        max_deviation = 2.0  # 最大偏差
        
        diversity = 1.0 - (deviation / max_deviation)
        return max(0.0, min(1.0, diversity))
    
    def _empty_score(self, miner_id: str) -> MinerBehaviorScore:
        """返回空分数"""
        return MinerBehaviorScore(
            miner_id=miner_id,
            calculated_at=datetime.now(),
            final_score=0.5,          # 新矿工给中等分
            scheduling_multiplier=1.0  # 不惩罚
        )
    
    def get_scheduling_weight(self, miner_id: str) -> float:
        """
        获取调度权重
        
        在低价订单拥堵时调用，对只吃高价的矿工降权
        """
        if miner_id in self.scores:
            return self.scores[miner_id].scheduling_multiplier
        
        # 尝试重新计算
        score = self.calculate_score(miner_id)
        return score.scheduling_multiplier
    
    def should_penalize_in_congestion(
        self,
        miner_id: str,
        current_congestion_level: float
    ) -> tuple[bool, str]:
        """
        判断在拥堵时是否应该降权
        
        Returns:
            (should_penalize, reason)
        """
        if miner_id not in self.scores:
            return False, "无历史数据"
        
        score = self.scores[miner_id]
        
        # 只有在高拥堵且历史表现差时才降权
        if current_congestion_level < 0.5:
            return False, "拥堵程度不足，无需降权"
        
        if score.congestion_help_score < 0.3:
            return True, f"历史拥堵帮助分仅 {score.congestion_help_score:.1%}"
        
        if score.low_price_accepted == 0 and score.total_orders > 20:
            return True, "从未接受低价订单"
        
        return False, "行为正常"
    
    def get_miner_report(self, miner_id: str) -> Dict[str, Any]:
        """获取矿工行为报告"""
        score = self.calculate_score(miner_id)
        
        # 生成建议
        suggestions = []
        if score.low_price_accepted == 0:
            suggestions.append("考虑偶尔接受低价订单，提升社区贡献评分")
        if score.congestion_help_score < 0.3:
            suggestions.append("在网络拥堵时接单可提升优先调度权")
        if score.final_score >= 0.8:
            suggestions.append("表现优秀！继续保持")
        
        return {
            "score": score.to_dict(),
            "suggestions": suggestions,
            "note": "矿工有完全的定价自由，此评分仅影响拥堵时的调度优先级"
        }


# ========== 单例 ==========

_behavior_analyzer: Optional[MinerBehaviorAnalyzer] = None

def get_behavior_analyzer() -> MinerBehaviorAnalyzer:
    """获取行为分析器实例"""
    global _behavior_analyzer
    if _behavior_analyzer is None:
        _behavior_analyzer = MinerBehaviorAnalyzer()
    return _behavior_analyzer
