"""
revenue_tracking.py - 收益跟踪系统

Phase 10 功能：
1. 矿工收益追踪
2. 实时收益统计
3. 收益分析报告
4. 收益预测
5. 收益通知
6. 多维度收益分析
"""

import time
import uuid
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import defaultdict
import statistics
import json


# ============== 枚举类型 ==============

class RevenueType(Enum):
    """收益类型"""
    MINING_REWARD = "mining_reward"
    TASK_PAYMENT = "task_payment"
    STAKING_REWARD = "staking_reward"
    REFERRAL_BONUS = "referral_bonus"
    GOVERNANCE_REWARD = "governance_reward"
    PENALTY_REFUND = "penalty_refund"


class RevenueStatus(Enum):
    """收益状态"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAID = "paid"
    CANCELLED = "cancelled"


class TimePeriod(Enum):
    """时间周期"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class NotificationType(Enum):
    """通知类型"""
    REVENUE_RECEIVED = "revenue_received"
    THRESHOLD_REACHED = "threshold_reached"
    DAILY_SUMMARY = "daily_summary"
    ABNORMAL_ACTIVITY = "abnormal_activity"


# ============== 数据结构 ==============

@dataclass
class RevenueRecord:
    """收益记录"""
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 参与者
    miner_id: str = ""
    
    # 收益信息
    revenue_type: RevenueType = RevenueType.MINING_REWARD
    amount: int = 0
    currency: str = "POUW"
    
    # 来源
    source_task_id: str = ""
    source_block_height: int = 0
    
    # 状态
    status: RevenueStatus = RevenueStatus.PENDING
    
    # 时间
    created_at: float = field(default_factory=time.time)
    confirmed_at: float = 0
    paid_at: float = 0
    
    # 交易
    tx_hash: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "miner_id": self.miner_id,
            "type": self.revenue_type.value,
            "amount": self.amount,
            "status": self.status.value,
            "created_at": self.created_at,
        }


@dataclass
class MinerStats:
    """矿工统计"""
    miner_id: str = ""
    
    # 累计
    total_revenue: int = 0
    total_tasks: int = 0
    total_blocks: int = 0
    
    # 按类型
    revenue_by_type: Dict[str, int] = field(default_factory=dict)
    
    # 时间序列
    hourly_revenue: Dict[str, int] = field(default_factory=dict)
    daily_revenue: Dict[str, int] = field(default_factory=dict)
    
    # 平均
    avg_revenue_per_task: float = 0
    avg_daily_revenue: float = 0
    
    # 效率
    efficiency_score: float = 0        # 0-100
    uptime_percent: float = 0
    
    # 排名
    rank: int = 0
    percentile: float = 0
    
    # 时间
    first_revenue_at: float = 0
    last_revenue_at: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "miner_id": self.miner_id,
            "total_revenue": self.total_revenue,
            "total_tasks": self.total_tasks,
            "avg_daily_revenue": round(self.avg_daily_revenue, 2),
            "efficiency_score": round(self.efficiency_score, 2),
            "rank": self.rank,
        }


@dataclass
class RevenueNotification:
    """收益通知"""
    notification_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 目标
    miner_id: str = ""
    
    # 内容
    notification_type: NotificationType = NotificationType.REVENUE_RECEIVED
    title: str = ""
    message: str = ""
    data: Dict = field(default_factory=dict)
    
    # 状态
    read: bool = False
    
    # 时间
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "notification_id": self.notification_id,
            "type": self.notification_type.value,
            "title": self.title,
            "message": self.message,
            "read": self.read,
            "created_at": self.created_at,
        }


@dataclass
class RevenueForecast:
    """收益预测"""
    miner_id: str = ""
    
    # 预测
    predicted_daily: float = 0
    predicted_weekly: float = 0
    predicted_monthly: float = 0
    
    # 置信区间
    confidence_low: float = 0
    confidence_high: float = 0
    
    # 趋势
    trend: str = "stable"              # up, down, stable
    trend_percent: float = 0
    
    # 影响因素
    factors: List[Dict] = field(default_factory=list)
    
    # 时间
    generated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "miner_id": self.miner_id,
            "predicted_daily": round(self.predicted_daily, 2),
            "predicted_weekly": round(self.predicted_weekly, 2),
            "predicted_monthly": round(self.predicted_monthly, 2),
            "trend": self.trend,
            "trend_percent": round(self.trend_percent, 2),
        }


# ============== 收益分析器 ==============

class RevenueAnalyzer:
    """收益分析器"""
    
    def __init__(self):
        pass
    
    def analyze_period(
        self,
        records: List[RevenueRecord],
        period: TimePeriod,
    ) -> Dict:
        """分析周期收益"""
        if not records:
            return {}
        
        # 按周期分组
        grouped = defaultdict(list)
        
        for record in records:
            key = self._get_period_key(record.created_at, period)
            grouped[key].append(record)
        
        # 计算每个周期的统计
        period_stats = {}
        for key, period_records in grouped.items():
            amounts = [r.amount for r in period_records]
            period_stats[key] = {
                "count": len(period_records),
                "total": sum(amounts),
                "avg": statistics.mean(amounts) if amounts else 0,
                "max": max(amounts) if amounts else 0,
                "min": min(amounts) if amounts else 0,
            }
        
        return period_stats
    
    def _get_period_key(self, timestamp: float, period: TimePeriod) -> str:
        """获取周期键"""
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp)
        
        if period == TimePeriod.HOURLY:
            return dt.strftime("%Y-%m-%d-%H")
        elif period == TimePeriod.DAILY:
            return dt.strftime("%Y-%m-%d")
        elif period == TimePeriod.WEEKLY:
            return f"{dt.year}-W{dt.isocalendar()[1]:02d}"
        elif period == TimePeriod.MONTHLY:
            return dt.strftime("%Y-%m")
        else:
            return str(dt.year)
    
    def calculate_trend(
        self,
        daily_revenues: Dict[str, int],
        days: int = 7,
    ) -> Tuple[str, float]:
        """计算趋势"""
        if len(daily_revenues) < 2:
            return "stable", 0
        
        # 获取最近的数据
        sorted_days = sorted(daily_revenues.keys())[-days:]
        values = [daily_revenues[d] for d in sorted_days]
        
        if len(values) < 2:
            return "stable", 0
        
        # 简单线性回归
        n = len(values)
        x = list(range(n))
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable", 0
        
        slope = numerator / denominator
        
        # 计算变化百分比
        if y_mean > 0:
            percent_change = (slope / y_mean) * 100
        else:
            percent_change = 0
        
        if percent_change > 5:
            trend = "up"
        elif percent_change < -5:
            trend = "down"
        else:
            trend = "stable"
        
        return trend, percent_change
    
    def forecast(
        self,
        miner_stats: MinerStats,
        days_ahead: int = 30,
    ) -> RevenueForecast:
        """预测收益"""
        forecast = RevenueForecast(miner_id=miner_stats.miner_id)
        
        # 基于历史平均预测
        if miner_stats.daily_revenue:
            recent_values = list(miner_stats.daily_revenue.values())[-30:]
            
            if recent_values:
                avg = statistics.mean(recent_values)
                std = statistics.stdev(recent_values) if len(recent_values) > 1 else 0
                
                forecast.predicted_daily = avg
                forecast.predicted_weekly = avg * 7
                forecast.predicted_monthly = avg * 30
                
                # 置信区间
                forecast.confidence_low = max(0, avg - 2 * std)
                forecast.confidence_high = avg + 2 * std
        
        # 计算趋势
        trend, percent = self.calculate_trend(miner_stats.daily_revenue)
        forecast.trend = trend
        forecast.trend_percent = percent
        
        # 影响因素
        forecast.factors = [
            {"factor": "historical_average", "impact": "base"},
            {"factor": "trend", "direction": trend, "impact": f"{percent:.1f}%"},
        ]
        
        return forecast


# ============== 收益跟踪管理器 ==============

class RevenueTrackingManager:
    """收益跟踪管理器"""
    
    def __init__(self):
        self.analyzer = RevenueAnalyzer()
        
        # 存储
        self.records: Dict[str, RevenueRecord] = {}
        self.miner_stats: Dict[str, MinerStats] = {}
        self.notifications: Dict[str, List[RevenueNotification]] = defaultdict(list)
        
        # 通知配置
        self.notification_thresholds: Dict[str, int] = {}
        
        # 全局统计
        self.global_stats = {
            "total_revenue_distributed": 0,
            "total_records": 0,
            "active_miners": 0,
            "avg_revenue_per_miner": 0,
        }
    
    def record_revenue(
        self,
        miner_id: str,
        amount: int,
        revenue_type: RevenueType,
        source_task_id: str = "",
        source_block_height: int = 0,
    ) -> RevenueRecord:
        """记录收益"""
        record = RevenueRecord(
            miner_id=miner_id,
            amount=amount,
            revenue_type=revenue_type,
            source_task_id=source_task_id,
            source_block_height=source_block_height,
        )
        
        self.records[record.record_id] = record
        
        # 更新矿工统计
        self._update_miner_stats(miner_id, record)
        
        # 更新全局统计
        self.global_stats["total_records"] += 1
        
        # 检查通知
        self._check_notifications(miner_id, record)
        
        return record
    
    def confirm_revenue(self, record_id: str, tx_hash: str = "") -> bool:
        """确认收益"""
        record = self.records.get(record_id)
        if not record:
            return False
        
        record.status = RevenueStatus.CONFIRMED
        record.confirmed_at = time.time()
        record.tx_hash = tx_hash
        
        # 更新全局统计
        self.global_stats["total_revenue_distributed"] += record.amount
        
        return True
    
    def _update_miner_stats(self, miner_id: str, record: RevenueRecord):
        """更新矿工统计"""
        if miner_id not in self.miner_stats:
            self.miner_stats[miner_id] = MinerStats(miner_id=miner_id)
            self.global_stats["active_miners"] += 1
        
        stats = self.miner_stats[miner_id]
        
        # 累计
        stats.total_revenue += record.amount
        stats.total_tasks += 1
        
        # 按类型
        type_key = record.revenue_type.value
        stats.revenue_by_type[type_key] = stats.revenue_by_type.get(type_key, 0) + record.amount
        
        # 时间序列
        import datetime
        dt = datetime.datetime.fromtimestamp(record.created_at)
        
        hour_key = dt.strftime("%Y-%m-%d-%H")
        day_key = dt.strftime("%Y-%m-%d")
        
        stats.hourly_revenue[hour_key] = stats.hourly_revenue.get(hour_key, 0) + record.amount
        stats.daily_revenue[day_key] = stats.daily_revenue.get(day_key, 0) + record.amount
        
        # 平均
        stats.avg_revenue_per_task = stats.total_revenue / stats.total_tasks
        
        if stats.daily_revenue:
            stats.avg_daily_revenue = statistics.mean(stats.daily_revenue.values())
        
        # 时间戳
        if stats.first_revenue_at == 0:
            stats.first_revenue_at = record.created_at
        stats.last_revenue_at = record.created_at
        
        # 更新全局平均
        if self.global_stats["active_miners"] > 0:
            total = sum(s.total_revenue for s in self.miner_stats.values())
            self.global_stats["avg_revenue_per_miner"] = total / self.global_stats["active_miners"]
    
    def _check_notifications(self, miner_id: str, record: RevenueRecord):
        """检查并发送通知"""
        # 收益通知
        notification = RevenueNotification(
            miner_id=miner_id,
            notification_type=NotificationType.REVENUE_RECEIVED,
            title="新收益",
            message=f"您收到 {record.amount} {record.currency} 收益",
            data={"record_id": record.record_id, "amount": record.amount},
        )
        self.notifications[miner_id].append(notification)
        
        # 阈值通知
        threshold = self.notification_thresholds.get(miner_id, 0)
        if threshold > 0:
            stats = self.miner_stats.get(miner_id)
            if stats and stats.total_revenue >= threshold:
                threshold_notification = RevenueNotification(
                    miner_id=miner_id,
                    notification_type=NotificationType.THRESHOLD_REACHED,
                    title="收益里程碑",
                    message=f"恭喜！您的总收益已达到 {stats.total_revenue}",
                    data={"total_revenue": stats.total_revenue},
                )
                self.notifications[miner_id].append(threshold_notification)
                # 清除阈值避免重复通知
                del self.notification_thresholds[miner_id]
        
        # 每个矿工最多保留 200 条通知，防止无界增长
        if len(self.notifications[miner_id]) > 200:
            self.notifications[miner_id] = self.notifications[miner_id][-200:]
    
    def set_notification_threshold(self, miner_id: str, threshold: int):
        """设置通知阈值"""
        self.notification_thresholds[miner_id] = threshold
    
    def get_miner_revenue(
        self,
        miner_id: str,
        start_time: float = 0,
        end_time: float = 0,
        revenue_type: RevenueType = None,
    ) -> List[RevenueRecord]:
        """获取矿工收益记录"""
        if end_time == 0:
            end_time = time.time()
        
        records = [
            r for r in self.records.values()
            if r.miner_id == miner_id
            and start_time <= r.created_at <= end_time
        ]
        
        if revenue_type:
            records = [r for r in records if r.revenue_type == revenue_type]
        
        return sorted(records, key=lambda r: r.created_at, reverse=True)
    
    def get_miner_stats(self, miner_id: str) -> Optional[MinerStats]:
        """获取矿工统计"""
        return self.miner_stats.get(miner_id)
    
    def get_revenue_analysis(
        self,
        miner_id: str,
        period: TimePeriod = TimePeriod.DAILY,
    ) -> Dict:
        """获取收益分析"""
        records = [r for r in self.records.values() if r.miner_id == miner_id]
        return self.analyzer.analyze_period(records, period)
    
    def get_revenue_forecast(self, miner_id: str) -> Optional[RevenueForecast]:
        """获取收益预测"""
        stats = self.miner_stats.get(miner_id)
        if not stats:
            return None
        
        return self.analyzer.forecast(stats)
    
    def get_notifications(self, miner_id: str, unread_only: bool = False) -> List[RevenueNotification]:
        """获取通知"""
        notifications = self.notifications.get(miner_id, [])
        
        if unread_only:
            notifications = [n for n in notifications if not n.read]
        
        return sorted(notifications, key=lambda n: n.created_at, reverse=True)
    
    def mark_notification_read(self, notification_id: str) -> bool:
        """标记通知已读"""
        for notifications in self.notifications.values():
            for n in notifications:
                if n.notification_id == notification_id:
                    n.read = True
                    return True
        return False
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """获取收益排行榜"""
        # 排序
        sorted_miners = sorted(
            self.miner_stats.values(),
            key=lambda s: s.total_revenue,
            reverse=True,
        )
        
        # 更新排名
        leaderboard = []
        for i, stats in enumerate(sorted_miners[:limit]):
            stats.rank = i + 1
            if len(sorted_miners) > 0:
                stats.percentile = ((len(sorted_miners) - stats.rank) / len(sorted_miners)) * 100
            leaderboard.append(stats.to_dict())
        
        return leaderboard
    
    def get_global_stats(self) -> Dict:
        """获取全局统计"""
        return {
            **self.global_stats,
            "revenue_by_type": self._get_revenue_by_type(),
        }
    
    def _get_revenue_by_type(self) -> Dict[str, int]:
        """按类型统计收益"""
        by_type = defaultdict(int)
        for record in self.records.values():
            by_type[record.revenue_type.value] += record.amount
        return dict(by_type)
    
    def generate_daily_summary(self, miner_id: str) -> RevenueNotification:
        """生成每日摘要"""
        import datetime
        
        today = datetime.date.today()
        day_key = today.strftime("%Y-%m-%d")
        
        stats = self.miner_stats.get(miner_id)
        today_revenue = 0
        if stats:
            today_revenue = stats.daily_revenue.get(day_key, 0)
        
        notification = RevenueNotification(
            miner_id=miner_id,
            notification_type=NotificationType.DAILY_SUMMARY,
            title="每日收益摘要",
            message=f"今日收益: {today_revenue} POUW",
            data={
                "date": day_key,
                "revenue": today_revenue,
                "total": stats.total_revenue if stats else 0,
            },
        )
        
        self.notifications[miner_id].append(notification)
        # 每个矿工最多保留 200 条通知
        if len(self.notifications[miner_id]) > 200:
            self.notifications[miner_id] = self.notifications[miner_id][-200:]
        return notification


# ============== 全局实例 ==============

_revenue_tracking_manager: Optional[RevenueTrackingManager] = None


def get_revenue_tracking_manager() -> RevenueTrackingManager:
    """获取收益跟踪管理器单例"""
    global _revenue_tracking_manager
    if _revenue_tracking_manager is None:
        _revenue_tracking_manager = RevenueTrackingManager()
    return _revenue_tracking_manager
