"""
dynamic_pricing.py - 市场波动定价系统

实现功能：
1. 基础算力参考价机制
2. 供需动态调节系数 (Market Multiplier)
3. 策略溢价系统
4. 时间片计费
5. 市场监控与反馈
"""

import time
import threading
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from collections import deque
import json


# ============== 枚举类型 ==============

class PricingStrategy(Enum):
    """用户定价策略"""
    IMMEDIATE = "immediate"      # 立即执行（溢价）
    STANDARD = "standard"        # 标准执行
    ECONOMY = "economy"          # 经济模式（排队）
    NIGHT_DISCOUNT = "night"     # 夜间低价
    FLEXIBLE = "flexible"        # 弹性模式


class TimeSlot(Enum):
    """时段类型"""
    PEAK = "peak"          # 高峰时段 (9:00-12:00, 14:00-18:00)
    NORMAL = "normal"      # 正常时段
    OFF_PEAK = "off_peak"  # 低谷时段 (0:00-6:00)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 1    # 最高优先级
    HIGH = 2        # 高优先级
    NORMAL = 3      # 正常优先级
    LOW = 4         # 低优先级
    BACKGROUND = 5  # 后台任务


# ============== 数据结构 ==============

@dataclass
class GPUBasePrice:
    """GPU 基础价格配置"""
    gpu_type: str
    base_price_per_hour: float      # 每小时基础价格
    compute_units: float            # 算力单位
    memory_gb: int                  # 显存大小
    power_consumption_w: int        # 功耗(瓦特)
    last_updated: float = field(default_factory=time.time)
    governance_approved: bool = True  # 是否经过治理批准


@dataclass
class MarketState:
    """市场状态"""
    timestamp: float
    total_supply: float           # 总供给算力
    total_demand: float           # 总需求算力
    active_miners: int            # 活跃矿工数
    pending_tasks: int            # 待处理任务数
    avg_queue_time: float         # 平均排队时间(秒)
    supply_demand_ratio: float    # 供需比
    market_multiplier: float      # 市场乘数


@dataclass
class TimeSlice:
    """时间片计费记录"""
    slice_id: str
    task_id: str
    start_time: float
    end_time: float
    duration_seconds: float
    gpu_type: str
    base_price: float
    market_multiplier: float
    time_slot_multiplier: float
    strategy_multiplier: float
    final_price: float
    
    def to_dict(self) -> Dict:
        return {
            "slice_id": self.slice_id,
            "task_id": self.task_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "gpu_type": self.gpu_type,
            "base_price": self.base_price,
            "market_multiplier": self.market_multiplier,
            "time_slot_multiplier": self.time_slot_multiplier,
            "strategy_multiplier": self.strategy_multiplier,
            "final_price": self.final_price,
        }


@dataclass
class PricingResult:
    """定价计算结果"""
    base_price: float
    market_multiplier: float
    time_slot_multiplier: float
    strategy_multiplier: float
    final_unit_price: float
    estimated_total: float
    price_breakdown: Dict[str, float]
    valid_until: float  # 价格有效期


@dataclass
class BudgetLock:
    """预算锁定记录"""
    lock_id: str
    task_id: str
    user_id: str
    locked_amount: float
    estimated_time_hours: float
    gpu_type: str
    pricing_strategy: PricingStrategy
    worst_case_price: float      # 最坏情况估算
    locked_at: float
    expires_at: float
    status: str = "active"       # active, released, consumed
    actual_consumed: float = 0.0
    refunded: float = 0.0


@dataclass 
class SettlementRecord:
    """结算记录"""
    settlement_id: str
    task_id: str
    user_id: str
    miner_id: str
    locked_budget: float
    actual_cost: float
    refund_amount: float
    time_slices: List[TimeSlice]
    settled_at: float
    settlement_hash: str  # 链上哈希


# ============== 基础价格管理器 ==============

class BasePriceManager:
    """基础算力价格管理器"""
    
    # 默认基础价格配置 (每小时，单位：MAIN)
    DEFAULT_PRICES = {
        "CPU": GPUBasePrice("CPU", 1.0, 1.0, 0, 65),
        "RTX3060": GPUBasePrice("RTX3060", 5.0, 10.0, 12, 170),
        "RTX3070": GPUBasePrice("RTX3070", 7.0, 15.0, 8, 220),
        "RTX3080": GPUBasePrice("RTX3080", 10.0, 20.0, 10, 320),
        "RTX3090": GPUBasePrice("RTX3090", 15.0, 25.0, 24, 350),
        "RTX4070": GPUBasePrice("RTX4070", 12.0, 22.0, 12, 200),
        "RTX4080": GPUBasePrice("RTX4080", 18.0, 35.0, 16, 320),
        "RTX4090": GPUBasePrice("RTX4090", 25.0, 50.0, 24, 450),
        "A100": GPUBasePrice("A100", 40.0, 80.0, 40, 400),
        "H100": GPUBasePrice("H100", 60.0, 120.0, 80, 700),
        "H200": GPUBasePrice("H200", 80.0, 160.0, 141, 700),
    }
    
    def __init__(self):
        self.prices: Dict[str, GPUBasePrice] = dict(self.DEFAULT_PRICES)
        self.price_history: Dict[str, List[Tuple[float, float]]] = {}
        self._lock = threading.RLock()
        self.governance_proposals: List[Dict] = []
    
    def get_base_price(self, gpu_type: str) -> float:
        """获取 GPU 基础价格"""
        with self._lock:
            if gpu_type in self.prices:
                return self.prices[gpu_type].base_price_per_hour
            # 未知类型使用 CPU 价格
            return self.prices["CPU"].base_price_per_hour
    
    def get_all_prices(self) -> Dict[str, Dict]:
        """获取所有 GPU 价格（公开透明）"""
        with self._lock:
            return {
                gpu_type: {
                    "base_price_per_hour": p.base_price_per_hour,
                    "compute_units": p.compute_units,
                    "memory_gb": p.memory_gb,
                    "power_consumption_w": p.power_consumption_w,
                    "last_updated": p.last_updated,
                    "governance_approved": p.governance_approved,
                }
                for gpu_type, p in self.prices.items()
            }
    
    def propose_price_change(
        self,
        gpu_type: str,
        new_price: float,
        proposer: str,
        reason: str,
    ) -> str:
        """提议价格变更（治理机制）"""
        proposal_id = hashlib.sha256(
            f"{gpu_type}{new_price}{time.time()}".encode()
        ).hexdigest()[:16]
        
        proposal = {
            "proposal_id": proposal_id,
            "gpu_type": gpu_type,
            "current_price": self.get_base_price(gpu_type),
            "proposed_price": new_price,
            "proposer": proposer,
            "reason": reason,
            "created_at": time.time(),
            "votes_for": 0,
            "votes_against": 0,
            "status": "pending",
            "expires_at": time.time() + 7 * 24 * 3600,  # 7天投票期
        }
        
        self.governance_proposals.append(proposal)
        return proposal_id
    
    def apply_price_change(self, gpu_type: str, new_price: float) -> bool:
        """应用价格变更（需要治理批准）"""
        with self._lock:
            if gpu_type not in self.prices:
                return False
            
            old_price = self.prices[gpu_type].base_price_per_hour
            self.prices[gpu_type].base_price_per_hour = new_price
            self.prices[gpu_type].last_updated = time.time()
            
            # 记录历史
            if gpu_type not in self.price_history:
                self.price_history[gpu_type] = []
            self.price_history[gpu_type].append((time.time(), new_price))
            
            return True


# ============== 供需系数计算器 ==============

class MarketMultiplierCalculator:
    """供需动态调节系数计算器"""
    
    def __init__(self):
        # 配置参数
        self.min_multiplier = 0.5    # 最低系数（供过于求）
        self.max_multiplier = 3.0    # 最高系数（供不应求）
        self.base_multiplier = 1.0   # 基准系数
        self.smoothing_factor = 0.3  # 平滑系数（防止剧烈波动）
        
        # 状态
        self._current_multiplier = 1.0
        self._history: deque = deque(maxlen=1000)
        self._lock = threading.RLock()
        
        # 市场数据
        self.total_supply = 0.0
        self.total_demand = 0.0
        self.active_miners = 0
        self.pending_tasks = 0
    
    def update_market_data(
        self,
        total_supply: float,
        total_demand: float,
        active_miners: int,
        pending_tasks: int,
    ):
        """更新市场数据"""
        with self._lock:
            self.total_supply = max(total_supply, 0.001)  # 防止除零
            self.total_demand = total_demand
            self.active_miners = active_miners
            self.pending_tasks = pending_tasks
            
            # 重新计算系数
            self._recalculate_multiplier()
    
    def _recalculate_multiplier(self):
        """重新计算供需系数"""
        # 供需比 = 需求 / 供给
        ratio = self.total_demand / self.total_supply
        
        # 使用 sigmoid 函数平滑映射到 [min, max] 范围
        # ratio = 1 时，multiplier = 1
        # ratio > 1 时，multiplier > 1 (供不应求)
        # ratio < 1 时，multiplier < 1 (供过于求)
        
        import math
        # 使用对数函数来计算系数
        if ratio <= 0:
            raw_multiplier = self.min_multiplier
        else:
            # ln(ratio) + 1，ratio=1 时为1
            raw_multiplier = math.log(ratio) * 0.5 + 1.0
        
        # 限制范围
        raw_multiplier = max(self.min_multiplier, min(self.max_multiplier, raw_multiplier))
        
        # 应用平滑（避免价格剧烈波动）
        self._current_multiplier = (
            self.smoothing_factor * raw_multiplier +
            (1 - self.smoothing_factor) * self._current_multiplier
        )
        
        # 记录历史
        state = MarketState(
            timestamp=time.time(),
            total_supply=self.total_supply,
            total_demand=self.total_demand,
            active_miners=self.active_miners,
            pending_tasks=self.pending_tasks,
            avg_queue_time=self._calculate_avg_queue_time(),
            supply_demand_ratio=ratio,
            market_multiplier=self._current_multiplier,
        )
        self._history.append(state)
    
    def _calculate_avg_queue_time(self) -> float:
        """计算平均排队时间"""
        if self.total_supply <= 0 or self.pending_tasks <= 0:
            return 0.0
        # 简单估算：待处理任务数 / 供给能力
        return self.pending_tasks / self.total_supply * 60  # 秒
    
    def get_current_multiplier(self) -> float:
        """获取当前供需系数"""
        with self._lock:
            return round(self._current_multiplier, 4)
    
    def get_market_state(self) -> Dict:
        """获取当前市场状态（链上公开）"""
        with self._lock:
            return {
                "timestamp": time.time(),
                "total_supply": self.total_supply,
                "total_demand": self.total_demand,
                "active_miners": self.active_miners,
                "pending_tasks": self.pending_tasks,
                "supply_demand_ratio": round(self.total_demand / self.total_supply, 4) if self.total_supply > 0 else 0,
                "market_multiplier": round(self._current_multiplier, 4),
                "avg_queue_time_seconds": round(self._calculate_avg_queue_time(), 1),
            }
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """获取历史记录"""
        with self._lock:
            return [
                {
                    "timestamp": s.timestamp,
                    "supply_demand_ratio": round(s.supply_demand_ratio, 4),
                    "market_multiplier": round(s.market_multiplier, 4),
                    "pending_tasks": s.pending_tasks,
                }
                for s in list(self._history)[-limit:]
            ]


# ============== 时段系数计算器 ==============

class TimeSlotCalculator:
    """时段系数计算器"""
    
    # 时段定义 (小时范围)
    PEAK_HOURS = [(9, 12), (14, 18)]    # 高峰时段
    OFF_PEAK_HOURS = [(0, 6)]            # 低谷时段
    
    # 时段系数
    MULTIPLIERS = {
        TimeSlot.PEAK: 1.3,       # 高峰加价 30%
        TimeSlot.NORMAL: 1.0,     # 正常
        TimeSlot.OFF_PEAK: 0.7,   # 低谷优惠 30%
    }
    
    @classmethod
    def get_current_time_slot(cls) -> TimeSlot:
        """获取当前时段"""
        hour = time.localtime().tm_hour
        
        for start, end in cls.PEAK_HOURS:
            if start <= hour < end:
                return TimeSlot.PEAK
        
        for start, end in cls.OFF_PEAK_HOURS:
            if start <= hour < end:
                return TimeSlot.OFF_PEAK
        
        return TimeSlot.NORMAL
    
    @classmethod
    def get_multiplier(cls, time_slot: Optional[TimeSlot] = None) -> float:
        """获取时段系数"""
        if time_slot is None:
            time_slot = cls.get_current_time_slot()
        return cls.MULTIPLIERS.get(time_slot, 1.0)
    
    @classmethod
    def get_schedule(cls) -> Dict:
        """获取完整时段表"""
        schedule = {}
        for hour in range(24):
            slot = TimeSlot.NORMAL
            for start, end in cls.PEAK_HOURS:
                if start <= hour < end:
                    slot = TimeSlot.PEAK
                    break
            for start, end in cls.OFF_PEAK_HOURS:
                if start <= hour < end:
                    slot = TimeSlot.OFF_PEAK
                    break
            schedule[hour] = {
                "slot": slot.value,
                "multiplier": cls.MULTIPLIERS[slot],
            }
        return schedule


# ============== 策略系数计算器 ==============

class StrategyCalculator:
    """用户策略系数计算器"""
    
    # 策略系数
    MULTIPLIERS = {
        PricingStrategy.IMMEDIATE: 1.5,    # 立即执行，溢价 50%
        PricingStrategy.STANDARD: 1.0,     # 标准
        PricingStrategy.ECONOMY: 0.8,      # 经济模式，优惠 20%（需排队）
        PricingStrategy.NIGHT_DISCOUNT: 0.6,  # 夜间模式，优惠 40%
        PricingStrategy.FLEXIBLE: 0.9,     # 弹性模式，系统自动调度
    }
    
    # 策略对应的优先级
    PRIORITIES = {
        PricingStrategy.IMMEDIATE: TaskPriority.CRITICAL,
        PricingStrategy.STANDARD: TaskPriority.NORMAL,
        PricingStrategy.ECONOMY: TaskPriority.LOW,
        PricingStrategy.NIGHT_DISCOUNT: TaskPriority.BACKGROUND,
        PricingStrategy.FLEXIBLE: TaskPriority.NORMAL,
    }
    
    # 策略对应的最大等待时间（秒）
    MAX_WAIT_TIMES = {
        PricingStrategy.IMMEDIATE: 60,       # 1分钟
        PricingStrategy.STANDARD: 600,       # 10分钟
        PricingStrategy.ECONOMY: 3600,       # 1小时
        PricingStrategy.NIGHT_DISCOUNT: 86400,  # 24小时
        PricingStrategy.FLEXIBLE: 7200,      # 2小时
    }
    
    @classmethod
    def get_multiplier(cls, strategy: PricingStrategy) -> float:
        """获取策略系数"""
        return cls.MULTIPLIERS.get(strategy, 1.0)
    
    @classmethod
    def get_priority(cls, strategy: PricingStrategy) -> TaskPriority:
        """获取任务优先级"""
        return cls.PRIORITIES.get(strategy, TaskPriority.NORMAL)
    
    @classmethod
    def get_max_wait_time(cls, strategy: PricingStrategy) -> int:
        """获取最大等待时间"""
        return cls.MAX_WAIT_TIMES.get(strategy, 600)
    
    @classmethod
    def get_all_strategies(cls) -> List[Dict]:
        """获取所有可用策略"""
        return [
            {
                "strategy": s.value,
                "multiplier": cls.MULTIPLIERS[s],
                "priority": cls.PRIORITIES[s].value,
                "max_wait_seconds": cls.MAX_WAIT_TIMES[s],
                "description": cls._get_description(s),
            }
            for s in PricingStrategy
        ]
    
    @classmethod
    def _get_description(cls, strategy: PricingStrategy) -> str:
        """获取策略描述"""
        descriptions = {
            PricingStrategy.IMMEDIATE: "立即执行，最高优先级，溢价50%",
            PricingStrategy.STANDARD: "标准执行，正常排队",
            PricingStrategy.ECONOMY: "经济模式，低优先级，优惠20%",
            PricingStrategy.NIGHT_DISCOUNT: "夜间模式，最低优先级，优惠40%",
            PricingStrategy.FLEXIBLE: "弹性模式，系统智能调度，优惠10%",
        }
        return descriptions.get(strategy, "")


# ============== 动态定价引擎 ==============

class DynamicPricingEngine:
    """动态定价引擎"""
    
    def __init__(self):
        self.base_price_manager = BasePriceManager()
        self.market_calculator = MarketMultiplierCalculator()
        self.time_slices: Dict[str, List[TimeSlice]] = {}  # task_id -> slices
        self._lock = threading.RLock()
        
        # 定价有效期（秒）
        self.price_validity_seconds = 300  # 5分钟
        
        # 时间片长度（秒）
        self.time_slice_duration = 60  # 1分钟
    
    def calculate_price(
        self,
        gpu_type: str,
        estimated_hours: float,
        strategy: PricingStrategy = PricingStrategy.STANDARD,
    ) -> PricingResult:
        """
        计算价格
        
        公式: 最终单价 = 基础价格 × 供需系数 × 时段系数 × 策略系数
        """
        base_price = self.base_price_manager.get_base_price(gpu_type)
        market_multiplier = self.market_calculator.get_current_multiplier()
        time_slot = TimeSlotCalculator.get_current_time_slot()
        time_slot_multiplier = TimeSlotCalculator.get_multiplier(time_slot)
        strategy_multiplier = StrategyCalculator.get_multiplier(strategy)
        
        # 计算最终单价（每小时）
        final_unit_price = (
            base_price *
            market_multiplier *
            time_slot_multiplier *
            strategy_multiplier
        )
        
        # 计算预估总价
        estimated_total = final_unit_price * estimated_hours
        
        return PricingResult(
            base_price=base_price,
            market_multiplier=market_multiplier,
            time_slot_multiplier=time_slot_multiplier,
            strategy_multiplier=strategy_multiplier,
            final_unit_price=round(final_unit_price, 4),
            estimated_total=round(estimated_total, 4),
            price_breakdown={
                "base_price": base_price,
                "market_multiplier": market_multiplier,
                "time_slot": time_slot.value,
                "time_slot_multiplier": time_slot_multiplier,
                "strategy": strategy.value,
                "strategy_multiplier": strategy_multiplier,
                "estimated_hours": estimated_hours,
            },
            valid_until=time.time() + self.price_validity_seconds,
        )
    
    def calculate_worst_case_price(
        self,
        gpu_type: str,
        estimated_hours: float,
        strategy: PricingStrategy = PricingStrategy.STANDARD,
    ) -> float:
        """
        计算最坏情况价格（用于预算锁定）
        使用最高可能的市场系数和高峰时段系数
        """
        base_price = self.base_price_manager.get_base_price(gpu_type)
        
        # 最坏情况：最高市场系数 + 高峰时段 + 策略系数
        worst_case_multiplier = (
            self.market_calculator.max_multiplier *
            TimeSlotCalculator.MULTIPLIERS[TimeSlot.PEAK] *
            StrategyCalculator.get_multiplier(strategy)
        )
        
        worst_case_price = base_price * worst_case_multiplier * estimated_hours
        
        # 增加 10% 安全边际
        return round(worst_case_price * 1.1, 4)
    
    def start_time_slice(
        self,
        task_id: str,
        gpu_type: str,
        strategy: PricingStrategy,
    ) -> TimeSlice:
        """开始新的时间片"""
        with self._lock:
            slice_id = str(uuid.uuid4())[:12]
            current_time = time.time()
            
            base_price = self.base_price_manager.get_base_price(gpu_type)
            market_multiplier = self.market_calculator.get_current_multiplier()
            time_slot_multiplier = TimeSlotCalculator.get_multiplier()
            strategy_multiplier = StrategyCalculator.get_multiplier(strategy)
            
            time_slice = TimeSlice(
                slice_id=slice_id,
                task_id=task_id,
                start_time=current_time,
                end_time=0,
                duration_seconds=0,
                gpu_type=gpu_type,
                base_price=base_price,
                market_multiplier=market_multiplier,
                time_slot_multiplier=time_slot_multiplier,
                strategy_multiplier=strategy_multiplier,
                final_price=0,
            )
            
            if task_id not in self.time_slices:
                self.time_slices[task_id] = []
            self.time_slices[task_id].append(time_slice)
            
            return time_slice
    
    def end_time_slice(self, task_id: str, slice_id: str) -> Optional[TimeSlice]:
        """结束时间片并计算费用"""
        with self._lock:
            if task_id not in self.time_slices:
                return None
            
            for ts in self.time_slices[task_id]:
                if ts.slice_id == slice_id and ts.end_time == 0:
                    ts.end_time = time.time()
                    ts.duration_seconds = ts.end_time - ts.start_time
                    
                    # 计算该时间片费用
                    hours = ts.duration_seconds / 3600
                    ts.final_price = round(
                        ts.base_price *
                        ts.market_multiplier *
                        ts.time_slot_multiplier *
                        ts.strategy_multiplier *
                        hours,
                        6
                    )
                    
                    return ts
            
            return None
    
    def get_task_time_slices(self, task_id: str) -> List[Dict]:
        """获取任务的所有时间片"""
        with self._lock:
            if task_id not in self.time_slices:
                return []
            return [ts.to_dict() for ts in self.time_slices[task_id]]
    
    def calculate_task_total_cost(self, task_id: str) -> float:
        """计算任务总费用（所有时间片之和）"""
        with self._lock:
            if task_id not in self.time_slices:
                return 0.0
            return sum(ts.final_price for ts in self.time_slices[task_id])
    
    def get_real_time_price(self, gpu_type: str) -> Dict:
        """获取实时价格（前端动态更新用）"""
        base_price = self.base_price_manager.get_base_price(gpu_type)
        market_multiplier = self.market_calculator.get_current_multiplier()
        time_slot = TimeSlotCalculator.get_current_time_slot()
        time_slot_multiplier = TimeSlotCalculator.get_multiplier(time_slot)
        
        current_price = base_price * market_multiplier * time_slot_multiplier
        
        return {
            "gpu_type": gpu_type,
            "base_price": base_price,
            "market_multiplier": market_multiplier,
            "time_slot": time_slot.value,
            "time_slot_multiplier": time_slot_multiplier,
            "current_price_per_hour": round(current_price, 4),
            "timestamp": time.time(),
            "valid_for_seconds": 60,  # 建议刷新间隔
        }


# ============== 预算锁定管理器 ==============

class BudgetLockManager:
    """预算锁定管理器"""
    
    def __init__(self, pricing_engine: DynamicPricingEngine):
        self.pricing_engine = pricing_engine
        self.locks: Dict[str, BudgetLock] = {}
        self.user_balances: Dict[str, float] = {}
        self._lock = threading.RLock()
    
    def deposit(self, user_id: str, amount: float) -> float:
        """用户充值"""
        with self._lock:
            self.user_balances[user_id] = self.user_balances.get(user_id, 0) + amount
            return self.user_balances[user_id]
    
    def get_balance(self, user_id: str) -> float:
        """获取余额"""
        with self._lock:
            return self.user_balances.get(user_id, 0)
    
    def lock_budget(
        self,
        task_id: str,
        user_id: str,
        gpu_type: str,
        estimated_hours: float,
        strategy: PricingStrategy = PricingStrategy.STANDARD,
    ) -> Optional[BudgetLock]:
        """
        锁定预算（按最坏情况估算）
        """
        with self._lock:
            # 计算最坏情况价格
            worst_case_price = self.pricing_engine.calculate_worst_case_price(
                gpu_type, estimated_hours, strategy
            )
            
            # 检查余额
            balance = self.user_balances.get(user_id, 0)
            if balance < worst_case_price:
                return None
            
            # 扣除余额
            self.user_balances[user_id] = balance - worst_case_price
            
            # 创建锁定记录
            lock_id = hashlib.sha256(
                f"{task_id}{user_id}{time.time()}".encode()
            ).hexdigest()[:16]
            
            lock = BudgetLock(
                lock_id=lock_id,
                task_id=task_id,
                user_id=user_id,
                locked_amount=worst_case_price,
                estimated_time_hours=estimated_hours,
                gpu_type=gpu_type,
                pricing_strategy=strategy,
                worst_case_price=worst_case_price,
                locked_at=time.time(),
                expires_at=time.time() + estimated_hours * 3600 * 2,  # 2倍预估时间
            )
            
            self.locks[task_id] = lock
            return lock
    
    def settle_and_refund(
        self,
        task_id: str,
        actual_cost: float,
    ) -> Optional[Tuple[float, float]]:
        """
        结算并退款
        返回: (实际消耗, 退款金额)
        """
        with self._lock:
            if task_id not in self.locks:
                return None
            
            lock = self.locks[task_id]
            
            # 计算退款
            refund = lock.locked_amount - actual_cost
            if refund < 0:
                # 实际消耗超出预算（理论上不应该发生）
                refund = 0
                actual_cost = lock.locked_amount
            
            # 退款到用户账户
            self.user_balances[lock.user_id] = (
                self.user_balances.get(lock.user_id, 0) + refund
            )
            
            # 更新锁定记录
            lock.status = "consumed"
            lock.actual_consumed = actual_cost
            lock.refunded = refund
            
            return (actual_cost, refund)
    
    def release_lock(self, task_id: str) -> bool:
        """释放锁定（任务取消时）"""
        with self._lock:
            if task_id not in self.locks:
                return False
            
            lock = self.locks[task_id]
            
            # 全额退款
            self.user_balances[lock.user_id] = (
                self.user_balances.get(lock.user_id, 0) + lock.locked_amount
            )
            
            lock.status = "released"
            lock.refunded = lock.locked_amount
            
            return True
    
    def get_lock_info(self, task_id: str) -> Optional[Dict]:
        """获取锁定信息"""
        with self._lock:
            if task_id not in self.locks:
                return None
            lock = self.locks[task_id]
            return {
                "lock_id": lock.lock_id,
                "task_id": lock.task_id,
                "user_id": lock.user_id,
                "locked_amount": lock.locked_amount,
                "status": lock.status,
                "actual_consumed": lock.actual_consumed,
                "refunded": lock.refunded,
                "locked_at": lock.locked_at,
            }


# ============== 结算引擎 ==============

class SettlementEngine:
    """结算引擎（智能合约模拟）"""
    
    def __init__(
        self,
        pricing_engine: DynamicPricingEngine,
        budget_manager: BudgetLockManager,
    ):
        self.pricing_engine = pricing_engine
        self.budget_manager = budget_manager
        self.settlements: Dict[str, SettlementRecord] = {}
        self.miner_earnings: Dict[str, float] = {}
        self._lock = threading.RLock()
    
    def settle_task(
        self,
        task_id: str,
        user_id: str,
        miner_id: str,
    ) -> Optional[SettlementRecord]:
        """
        结算任务
        """
        with self._lock:
            # 获取锁定信息
            lock_info = self.budget_manager.get_lock_info(task_id)
            if not lock_info:
                return None
            
            # 计算实际费用
            actual_cost = self.pricing_engine.calculate_task_total_cost(task_id)
            
            # 获取时间片
            time_slices = self.pricing_engine.get_task_time_slices(task_id)
            
            # 执行结算
            result = self.budget_manager.settle_and_refund(task_id, actual_cost)
            if not result:
                return None
            
            consumed, refund = result
            
            # 支付给矿工
            self.miner_earnings[miner_id] = (
                self.miner_earnings.get(miner_id, 0) + consumed
            )
            
            # 创建结算记录
            settlement_id = hashlib.sha256(
                f"{task_id}{time.time()}".encode()
            ).hexdigest()[:16]
            
            # 生成链上哈希
            settlement_hash = hashlib.sha256(
                json.dumps({
                    "settlement_id": settlement_id,
                    "task_id": task_id,
                    "user_id": user_id,
                    "miner_id": miner_id,
                    "actual_cost": consumed,
                    "refund": refund,
                    "time": time.time(),
                }).encode()
            ).hexdigest()
            
            record = SettlementRecord(
                settlement_id=settlement_id,
                task_id=task_id,
                user_id=user_id,
                miner_id=miner_id,
                locked_budget=lock_info["locked_amount"],
                actual_cost=consumed,
                refund_amount=refund,
                time_slices=[],  # 简化
                settled_at=time.time(),
                settlement_hash=settlement_hash,
            )
            
            self.settlements[task_id] = record
            return record
    
    def get_settlement_record(self, task_id: str) -> Optional[Dict]:
        """获取结算记录"""
        with self._lock:
            if task_id not in self.settlements:
                return None
            record = self.settlements[task_id]
            return {
                "settlement_id": record.settlement_id,
                "task_id": record.task_id,
                "user_id": record.user_id,
                "miner_id": record.miner_id,
                "locked_budget": record.locked_budget,
                "actual_cost": record.actual_cost,
                "refund_amount": record.refund_amount,
                "settled_at": record.settled_at,
                "settlement_hash": record.settlement_hash,
            }
    
    def get_miner_earnings(self, miner_id: str) -> float:
        """获取矿工收益"""
        with self._lock:
            return self.miner_earnings.get(miner_id, 0)
    
    def get_detailed_bill(self, task_id: str) -> Dict:
        """获取详细账单"""
        settlement = self.get_settlement_record(task_id)
        time_slices = self.pricing_engine.get_task_time_slices(task_id)
        lock_info = self.budget_manager.get_lock_info(task_id)
        
        return {
            "task_id": task_id,
            "settlement": settlement,
            "lock_info": lock_info,
            "time_slices": time_slices,
            "summary": {
                "total_time_slices": len(time_slices),
                "total_duration_seconds": sum(ts.get("duration_seconds", 0) for ts in time_slices),
                "total_cost": sum(ts.get("final_price", 0) for ts in time_slices),
            }
        }


# ============== 市场监控系统 ==============

class MarketMonitor:
    """市场监控系统"""
    
    def __init__(
        self,
        pricing_engine: DynamicPricingEngine,
        market_calculator: MarketMultiplierCalculator,
    ):
        self.pricing_engine = pricing_engine
        self.market_calculator = market_calculator
        self.task_queue: List[Dict] = []
        self.gpu_utilization: Dict[str, float] = {}
        self._lock = threading.RLock()
    
    def update_gpu_utilization(self, gpu_type: str, utilization: float):
        """更新 GPU 利用率"""
        with self._lock:
            self.gpu_utilization[gpu_type] = utilization
    
    def add_to_queue(self, task_info: Dict):
        """添加任务到队列"""
        with self._lock:
            self.task_queue.append({
                **task_info,
                "queued_at": time.time(),
            })
    
    def remove_from_queue(self, task_id: str):
        """从队列移除任务"""
        with self._lock:
            self.task_queue = [t for t in self.task_queue if t.get("task_id") != task_id]
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        with self._lock:
            now = time.time()
            queue_by_priority = {}
            for task in self.task_queue:
                priority = task.get("priority", TaskPriority.NORMAL.value)
                if priority not in queue_by_priority:
                    queue_by_priority[priority] = []
                queue_by_priority[priority].append({
                    "task_id": task.get("task_id"),
                    "wait_time": now - task.get("queued_at", now),
                })
            
            return {
                "total_pending": len(self.task_queue),
                "by_priority": queue_by_priority,
                "avg_wait_time": (
                    sum(now - t.get("queued_at", now) for t in self.task_queue) / len(self.task_queue)
                    if self.task_queue else 0
                ),
            }
    
    def get_supply_demand_curve(self, hours: int = 24) -> List[Dict]:
        """获取供需曲线数据"""
        return self.market_calculator.get_history(hours * 60)  # 每分钟一个点
    
    def get_dashboard_data(self) -> Dict:
        """获取监控面板数据"""
        market_state = self.market_calculator.get_market_state()
        queue_status = self.get_queue_status()
        
        # 获取各 GPU 实时价格
        gpu_prices = {}
        for gpu_type in self.pricing_engine.base_price_manager.prices.keys():
            gpu_prices[gpu_type] = self.pricing_engine.get_real_time_price(gpu_type)
        
        return {
            "market_state": market_state,
            "queue_status": queue_status,
            "gpu_utilization": self.gpu_utilization,
            "real_time_prices": gpu_prices,
            "time_slot": TimeSlotCalculator.get_current_time_slot().value,
            "time_slot_multiplier": TimeSlotCalculator.get_multiplier(),
            "timestamp": time.time(),
        }
    
    def get_price_forecast(self, gpu_type: str, hours_ahead: int = 24) -> List[Dict]:
        """预测未来价格趋势"""
        forecasts = []
        base_price = self.pricing_engine.base_price_manager.get_base_price(gpu_type)
        current_market = self.market_calculator.get_current_multiplier()
        
        for hour in range(hours_ahead):
            future_hour = (time.localtime().tm_hour + hour) % 24
            
            # 确定时段
            time_slot = TimeSlot.NORMAL
            for start, end in TimeSlotCalculator.PEAK_HOURS:
                if start <= future_hour < end:
                    time_slot = TimeSlot.PEAK
                    break
            for start, end in TimeSlotCalculator.OFF_PEAK_HOURS:
                if start <= future_hour < end:
                    time_slot = TimeSlot.OFF_PEAK
                    break
            
            time_multiplier = TimeSlotCalculator.MULTIPLIERS[time_slot]
            
            # 假设市场系数逐渐回归 1.0
            estimated_market = current_market + (1.0 - current_market) * (hour / 24)
            
            estimated_price = base_price * estimated_market * time_multiplier
            
            forecasts.append({
                "hours_ahead": hour,
                "hour_of_day": future_hour,
                "time_slot": time_slot.value,
                "estimated_price": round(estimated_price, 4),
                "confidence": max(0.5, 1.0 - hour * 0.02),  # 越远置信度越低
            })
        
        return forecasts


# ============== 弹性任务队列 ==============

class ElasticTaskQueue:
    """弹性任务队列"""
    
    def __init__(self, max_concurrent: int = 100):
        self.max_concurrent = max_concurrent
        self.queues: Dict[int, deque] = {p.value: deque() for p in TaskPriority}
        self.active_tasks: Dict[str, Dict] = {}
        self._lock = threading.RLock()
    
    def enqueue(
        self,
        task_id: str,
        priority: TaskPriority,
        task_info: Dict,
    ) -> int:
        """入队，返回队列位置"""
        with self._lock:
            self.queues[priority.value].append({
                "task_id": task_id,
                "priority": priority.value,
                "enqueued_at": time.time(),
                **task_info,
            })
            return len(self.queues[priority.value])
    
    def dequeue(self) -> Optional[Dict]:
        """出队（按优先级）"""
        with self._lock:
            if len(self.active_tasks) >= self.max_concurrent:
                return None
            
            for priority in sorted(self.queues.keys()):
                if self.queues[priority]:
                    task = self.queues[priority].popleft()
                    self.active_tasks[task["task_id"]] = task
                    return task
            
            return None
    
    def complete_task(self, task_id: str):
        """完成任务"""
        with self._lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    def get_position(self, task_id: str) -> Optional[int]:
        """获取队列位置"""
        with self._lock:
            position = 0
            for priority in sorted(self.queues.keys()):
                for i, task in enumerate(self.queues[priority]):
                    if task["task_id"] == task_id:
                        return position + i + 1
                position += len(self.queues[priority])
            return None
    
    def get_estimated_wait_time(self, task_id: str) -> float:
        """估算等待时间（秒）"""
        position = self.get_position(task_id)
        if position is None:
            return 0
        
        # 简单估算：每个任务平均 30 秒
        avg_task_time = 30
        available_slots = max(1, self.max_concurrent - len(self.active_tasks))
        
        return (position / available_slots) * avg_task_time
    
    def adjust_capacity(self, new_max: int):
        """调整容量（弹性伸缩）"""
        with self._lock:
            self.max_concurrent = new_max
    
    def get_stats(self) -> Dict:
        """获取队列统计"""
        with self._lock:
            return {
                "max_concurrent": self.max_concurrent,
                "active_tasks": len(self.active_tasks),
                "available_slots": self.max_concurrent - len(self.active_tasks),
                "queued_by_priority": {
                    priority: len(queue)
                    for priority, queue in self.queues.items()
                },
                "total_queued": sum(len(q) for q in self.queues.values()),
            }


# ============== 工厂函数 ==============

def create_pricing_system() -> Tuple[
    DynamicPricingEngine,
    BudgetLockManager,
    SettlementEngine,
    MarketMonitor,
    ElasticTaskQueue,
]:
    """创建完整的定价系统"""
    pricing_engine = DynamicPricingEngine()
    budget_manager = BudgetLockManager(pricing_engine)
    settlement_engine = SettlementEngine(pricing_engine, budget_manager)
    market_monitor = MarketMonitor(pricing_engine, pricing_engine.market_calculator)
    task_queue = ElasticTaskQueue()
    
    return (
        pricing_engine,
        budget_manager,
        settlement_engine,
        market_monitor,
        task_queue,
    )


# ============== 便捷接口 ==============

# 全局实例
_pricing_engine: Optional[DynamicPricingEngine] = None
_budget_manager: Optional[BudgetLockManager] = None
_settlement_engine: Optional[SettlementEngine] = None
_market_monitor: Optional[MarketMonitor] = None
_task_queue: Optional[ElasticTaskQueue] = None


def get_pricing_system():
    """获取或创建定价系统单例"""
    global _pricing_engine, _budget_manager, _settlement_engine, _market_monitor, _task_queue
    
    if _pricing_engine is None:
        (
            _pricing_engine,
            _budget_manager,
            _settlement_engine,
            _market_monitor,
            _task_queue,
        ) = create_pricing_system()
    
    return {
        "pricing_engine": _pricing_engine,
        "budget_manager": _budget_manager,
        "settlement_engine": _settlement_engine,
        "market_monitor": _market_monitor,
        "task_queue": _task_queue,
    }
