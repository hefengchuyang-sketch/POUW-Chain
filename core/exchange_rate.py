"""
exchange_rate.py - 动态汇率系统

实现市场化汇率机制：
1. 基于供需的动态汇率
2. 各板块独立汇率
3. 交易量加权
4. 防止剧烈波动的平滑机制

汇率决定因素：
- 板块算力总量（供给）
- 板块任务需求量（需求）
- 近期交易量
- 板块币流通量
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import time
import math


class RateUpdateTrigger(Enum):
    """汇率更新触发条件。"""
    TIME_INTERVAL = "time_interval"     # 定时更新
    VOLUME_THRESHOLD = "volume_threshold"  # 交易量触发
    PRICE_DEVIATION = "price_deviation"    # 价格偏离触发
    GOVERNANCE = "governance"              # 治理投票


@dataclass
class SectorMetrics:
    """板块指标（用于汇率计算）。"""
    sector_type: str
    total_compute_power: float = 0.0    # 总算力（供给）
    active_miners: int = 0              # 活跃矿工数
    pending_jobs: int = 0               # 待处理任务（需求）
    completed_jobs_24h: int = 0         # 24h 完成任务
    total_volume_24h: float = 0.0       # 24h 交易量（板块币）
    circulating_supply: float = 0.0     # 流通量
    burned_amount: float = 0.0          # 销毁量
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExchangeRateRecord:
    """汇率记录。"""
    sector_type: str
    rate: float                         # 板块币 → MAIN 汇率
    inverse_rate: float                 # MAIN → 板块币 汇率
    timestamp: float = field(default_factory=time.time)
    trigger: RateUpdateTrigger = RateUpdateTrigger.TIME_INTERVAL
    metrics_snapshot: Optional[SectorMetrics] = None


@dataclass
class ExchangeOrder:
    """兑换订单。"""
    order_id: str
    account_id: str
    from_currency: str                  # 源币种
    to_currency: str                    # 目标币种
    amount: float                       # 兑换数量（源币）
    rate_at_order: float                # 下单时汇率
    expected_amount: float              # 预期获得量
    actual_amount: float = 0.0          # 实际获得量
    status: str = "pending"             # pending/confirmed/completed/cancelled
    witnesses: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class DynamicExchangeRate:
    """动态汇率引擎。
    
    汇率计算公式：
        rate = base_rate × demand_factor × supply_factor × volume_factor
    
    其中：
        demand_factor = 1 + (pending_jobs / avg_jobs) × sensitivity
        supply_factor = 1 - (excess_supply / total_supply) × sensitivity
        volume_factor = 移动平均平滑
    """

    # 基础汇率（可通过治理调整）— 板块名与 sector_coin.py/dual_witness_exchange.py 一致
    DEFAULT_BASE_RATES = {
        "H100": 1.0,            # 1 H100_COIN = 1 MAIN（数据中心算力最值钱）
        "RTX4090": 0.6,         # 1 RTX4090_COIN = 0.6 MAIN
        "RTX3080": 0.4,         # 1 RTX3080_COIN = 0.4 MAIN
        "CPU": 0.3,             # 1 CPU_COIN = 0.3 MAIN
        "GENERAL": 0.1,         # 1 GENERAL_COIN = 0.1 MAIN
    }

    def __init__(
        self,
        base_rates: Dict[str, float] = None,
        demand_sensitivity: float = 0.2,    # 需求敏感度
        supply_sensitivity: float = 0.15,   # 供给敏感度
        smoothing_factor: float = 0.1,      # 平滑系数（EMA）
        max_rate_change: float = 0.1,       # 单次最大变化 10%
        update_interval_seconds: float = 3600,  # 更新间隔
        log_fn=None,
    ):
        self.base_rates = base_rates or self.DEFAULT_BASE_RATES.copy()
        self.demand_sensitivity = demand_sensitivity
        self.supply_sensitivity = supply_sensitivity
        self.smoothing_factor = smoothing_factor
        self.max_rate_change = max_rate_change
        self.update_interval = update_interval_seconds
        
        # 当前汇率
        self.current_rates: Dict[str, float] = self.base_rates.copy()
        # 汇率历史
        self.rate_history: Dict[str, List[ExchangeRateRecord]] = {
            sector: [] for sector in self.base_rates
        }
        # 板块指标
        self.sector_metrics: Dict[str, SectorMetrics] = {}
        # 兑换订单
        self.orders: Dict[str, ExchangeOrder] = {}
        
        self._log_fn = log_fn or (lambda x: None)
        self.last_update_time = time.time()

    def _log(self, msg: str):
        self._log_fn(f"[EXCHANGE] {msg}")

    def update_sector_metrics(
        self,
        sector_type: str,
        compute_power: float = None,
        active_miners: int = None,
        pending_jobs: int = None,
        completed_jobs: int = None,
        volume: float = None,
        circulating: float = None,
    ):
        """更新板块指标。"""
        if sector_type not in self.sector_metrics:
            self.sector_metrics[sector_type] = SectorMetrics(sector_type=sector_type)
        
        m = self.sector_metrics[sector_type]
        if compute_power is not None:
            m.total_compute_power = compute_power
        if active_miners is not None:
            m.active_miners = active_miners
        if pending_jobs is not None:
            m.pending_jobs = pending_jobs
        if completed_jobs is not None:
            m.completed_jobs_24h = completed_jobs
        if volume is not None:
            m.total_volume_24h = volume
        if circulating is not None:
            m.circulating_supply = circulating
        m.timestamp = time.time()

    def _calculate_demand_factor(self, metrics: SectorMetrics) -> float:
        """计算需求因子。
        
        待处理任务越多 → 需求越高 → 汇率越高
        """
        if metrics.completed_jobs_24h == 0:
            return 1.0
        
        # 需求比 = 待处理 / 日均完成
        demand_ratio = metrics.pending_jobs / max(1, metrics.completed_jobs_24h)
        
        # 因子 = 1 + ratio × sensitivity（上限 1.5，下限 0.7）
        factor = 1.0 + demand_ratio * self.demand_sensitivity
        return max(0.7, min(1.5, factor))

    def _calculate_supply_factor(self, metrics: SectorMetrics) -> float:
        """计算供给因子。
        
        算力越充裕 → 供给过剩 → 汇率略降
        """
        if metrics.total_compute_power == 0:
            return 1.0
        
        # 简化：矿工越多，供给因子略降
        # 实际应该计算 供给/需求 比
        avg_power_per_miner = metrics.total_compute_power / max(1, metrics.active_miners)
        
        # 算力利用率估计
        if metrics.completed_jobs_24h > 0:
            utilization = min(1.0, metrics.completed_jobs_24h / (metrics.active_miners * 10))
        else:
            utilization = 0.5
        
        # 利用率低 → 供给过剩 → 因子降低
        factor = 0.8 + 0.4 * utilization
        return max(0.7, min(1.3, factor))

    def _calculate_volume_factor(self, metrics: SectorMetrics) -> float:
        """计算交易量因子。
        
        交易量大 → 流动性好 → 汇率稳定
        """
        if metrics.circulating_supply == 0:
            return 1.0
        
        # 换手率 = 24h 交易量 / 流通量
        turnover = metrics.total_volume_24h / metrics.circulating_supply
        
        # 换手率高 → 流动性好 → 因子接近 1
        # 换手率低 → 流动性差 → 可能有小幅折价
        if turnover > 0.1:  # 高换手
            return 1.0
        elif turnover > 0.01:
            return 0.98
        else:
            return 0.95

    def calculate_rate(self, sector_type: str) -> float:
        """计算板块当前汇率。"""
        if sector_type not in self.base_rates:
            self._log(f"Unknown sector: {sector_type}, using 0.5")
            return 0.5
        
        base = self.base_rates[sector_type]
        
        if sector_type not in self.sector_metrics:
            return base
        
        metrics = self.sector_metrics[sector_type]
        
        demand_f = self._calculate_demand_factor(metrics)
        supply_f = self._calculate_supply_factor(metrics)
        volume_f = self._calculate_volume_factor(metrics)
        
        # 计算新汇率
        new_rate = base * demand_f * supply_f * volume_f
        
        # 限制单次变化幅度
        current = self.current_rates.get(sector_type, base)
        max_change = current * self.max_rate_change
        
        if new_rate > current + max_change:
            new_rate = current + max_change
        elif new_rate < current - max_change:
            new_rate = current - max_change
        
        # EMA 平滑
        smoothed = self.smoothing_factor * new_rate + (1 - self.smoothing_factor) * current
        
        return round(smoothed, 6)

    def update_rates(self, trigger: RateUpdateTrigger = RateUpdateTrigger.TIME_INTERVAL):
        """更新所有板块汇率。"""
        self._log(f"Updating rates (trigger: {trigger.value})")
        
        for sector in self.base_rates:
            old_rate = self.current_rates.get(sector, self.base_rates[sector])
            new_rate = self.calculate_rate(sector)
            self.current_rates[sector] = new_rate
            
            # 记录历史
            record = ExchangeRateRecord(
                sector_type=sector,
                rate=new_rate,
                inverse_rate=1.0 / new_rate if new_rate > 0 else 0,
                trigger=trigger,
                metrics_snapshot=self.sector_metrics.get(sector),
            )
            self.rate_history[sector].append(record)
            
            # 只保留最近 1000 条
            if len(self.rate_history[sector]) > 1000:
                self.rate_history[sector] = self.rate_history[sector][-1000:]
            
            change_pct = (new_rate - old_rate) / old_rate * 100 if old_rate > 0 else 0
            self._log(f"  {sector}: {old_rate:.6f} -> {new_rate:.6f} ({change_pct:+.2f}%)")
        
        self.last_update_time = time.time()

    def get_rate(self, sector_type: str) -> float:
        """获取板块当前汇率（板块币 → MAIN）。"""
        # 检查是否需要更新
        if time.time() - self.last_update_time > self.update_interval:
            self.update_rates()
        
        return self.current_rates.get(sector_type, self.base_rates.get(sector_type, 0.5))

    def get_inverse_rate(self, sector_type: str) -> float:
        """获取 MAIN → 板块币 汇率。"""
        rate = self.get_rate(sector_type)
        return 1.0 / rate if rate > 0 else 0

    def convert_to_main(self, sector_type: str, amount: float) -> Tuple[float, float]:
        """计算板块币兑换 MAIN。
        
        Returns:
            (MAIN 数量, 使用的汇率)
        """
        rate = self.get_rate(sector_type)
        main_amount = amount * rate
        return main_amount, rate

    def convert_from_main(self, sector_type: str, main_amount: float) -> Tuple[float, float]:
        """计算 MAIN 兑换板块币。
        
        Returns:
            (板块币数量, 使用的汇率)
        """
        rate = self.get_rate(sector_type)
        sector_amount = main_amount / rate if rate > 0 else 0
        return sector_amount, rate

    def get_rate_history(
        self,
        sector_type: str,
        limit: int = 100,
    ) -> List[ExchangeRateRecord]:
        """获取汇率历史。"""
        history = self.rate_history.get(sector_type, [])
        return history[-limit:]

    def get_all_rates(self) -> Dict[str, float]:
        """获取所有板块当前汇率。"""
        return self.current_rates.copy()

    def set_base_rate(self, sector_type: str, rate: float):
        """设置基础汇率（通过治理调整）。"""
        old = self.base_rates.get(sector_type)
        self.base_rates[sector_type] = rate
        if sector_type not in self.current_rates:
            self.current_rates[sector_type] = rate
        self._log(f"Base rate updated: {sector_type} {old} -> {rate} (governance)")

    def print_rates(self):
        """打印当前汇率。"""
        print("\n" + "=" * 50)
        print("EXCHANGE RATES (Sector Coin → MAIN)")
        print("=" * 50)
        for sector, rate in sorted(self.current_rates.items()):
            inverse = 1.0 / rate if rate > 0 else 0
            print(f"  {sector}: {rate:.6f} (1 MAIN = {inverse:.4f} {sector})")
        print()

    def __repr__(self) -> str:
        return f"DynamicExchangeRate(sectors={len(self.current_rates)})"
