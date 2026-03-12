"""
granular_billing.py - 细粒度资源计费

Phase 9 功能：
1. GPU 显存占用计费
2. GPU 利用率计费（SM occupancy）
3. 网络 IO 计费
4. 存储 IO 计费
5. 综合资源费用计算
6. 实时资源监控
"""

import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import defaultdict, deque
import statistics


# ============== 枚举类型 ==============

class ResourceType(Enum):
    """资源类型"""
    GPU_TIME = "gpu_time"              # GPU 时间
    GPU_MEMORY = "gpu_memory"          # GPU 显存
    GPU_UTILIZATION = "gpu_utilization"  # GPU 利用率
    NETWORK_INGRESS = "network_ingress"  # 网络入流量
    NETWORK_EGRESS = "network_egress"    # 网络出流量
    STORAGE_READ = "storage_read"        # 存储读
    STORAGE_WRITE = "storage_write"      # 存储写
    CPU_TIME = "cpu_time"                # CPU 时间
    MEMORY = "memory"                    # 内存


class BillingModel(Enum):
    """计费模型"""
    FLAT = "flat"                      # 固定费率
    TIERED = "tiered"                  # 阶梯计费
    USAGE_BASED = "usage_based"        # 按量计费
    HYBRID = "hybrid"                  # 混合模式


# ============== 数据结构 ==============

@dataclass
class ResourceRate:
    """资源费率"""
    resource_type: ResourceType
    unit: str                          # 计量单位 (GB, %, hours, GB/s)
    base_rate: float                   # 基础费率
    
    # 阶梯费率
    tiered_rates: List[Tuple[float, float]] = field(default_factory=list)  # [(threshold, rate), ...]
    
    # 市场乘数
    market_multiplier: float = 1.0
    
    # 时段乘数
    time_multiplier: float = 1.0
    
    def get_rate(self, usage: float = 0) -> float:
        """获取当前费率"""
        rate = self.base_rate
        
        # 应用阶梯费率
        if self.tiered_rates:
            for threshold, tier_rate in sorted(self.tiered_rates):
                if usage >= threshold:
                    rate = tier_rate
        
        return rate * self.market_multiplier * self.time_multiplier
    
    def to_dict(self) -> Dict:
        return {
            "resource_type": self.resource_type.value,
            "unit": self.unit,
            "base_rate": self.base_rate,
            "current_rate": self.get_rate(),
            "market_multiplier": self.market_multiplier,
        }


@dataclass
class ResourceUsage:
    """资源使用记录"""
    usage_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_id: str = ""
    miner_id: str = ""
    
    # 时间范围
    start_time: float = field(default_factory=time.time)
    end_time: float = 0
    duration_seconds: float = 0
    
    # GPU 资源
    gpu_type: str = ""
    gpu_memory_used_gb: float = 0          # 显存使用
    gpu_memory_total_gb: float = 0         # 显存总量
    gpu_utilization_percent: float = 0     # GPU 利用率
    sm_occupancy_percent: float = 0        # SM 占用率
    
    # 网络 IO
    network_ingress_gb: float = 0          # 入流量
    network_egress_gb: float = 0           # 出流量
    
    # 存储 IO
    storage_read_gb: float = 0             # 读取量
    storage_write_gb: float = 0            # 写入量
    
    # CPU & 内存
    cpu_cores_used: float = 0
    memory_used_gb: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "usage_id": self.usage_id,
            "task_id": self.task_id,
            "miner_id": self.miner_id,
            "duration_seconds": self.duration_seconds,
            "gpu_type": self.gpu_type,
            "gpu_memory_used_gb": self.gpu_memory_used_gb,
            "gpu_utilization_percent": self.gpu_utilization_percent,
            "network_ingress_gb": self.network_ingress_gb,
            "network_egress_gb": self.network_egress_gb,
            "storage_read_gb": self.storage_read_gb,
            "storage_write_gb": self.storage_write_gb,
        }


@dataclass
class GranularBill:
    """细粒度账单"""
    bill_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_id: str = ""
    user_id: str = ""
    miner_id: str = ""
    
    # 时间
    billing_period_start: float = 0
    billing_period_end: float = 0
    generated_at: float = field(default_factory=time.time)
    
    # 费用明细
    line_items: List[Dict] = field(default_factory=list)
    
    # 汇总
    gpu_time_cost: float = 0
    gpu_memory_cost: float = 0
    gpu_utilization_adjustment: float = 0
    network_cost: float = 0
    storage_cost: float = 0
    
    # 乘数
    market_multiplier: float = 1.0
    time_multiplier: float = 1.0
    quality_adjustment: float = 0          # 质量调整
    
    # 总计
    subtotal: float = 0
    adjustments: float = 0
    total: float = 0
    
    # 公式
    formula: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "bill_id": self.bill_id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "miner_id": self.miner_id,
            "billing_period": {
                "start": self.billing_period_start,
                "end": self.billing_period_end,
            },
            "line_items": self.line_items,
            "summary": {
                "gpu_time_cost": self.gpu_time_cost,
                "gpu_memory_cost": self.gpu_memory_cost,
                "gpu_utilization_adjustment": self.gpu_utilization_adjustment,
                "network_cost": self.network_cost,
                "storage_cost": self.storage_cost,
            },
            "multipliers": {
                "market": self.market_multiplier,
                "time": self.time_multiplier,
            },
            "subtotal": self.subtotal,
            "adjustments": self.adjustments,
            "total": self.total,
            "formula": self.formula,
        }


@dataclass
class ResourceSnapshot:
    """资源快照"""
    timestamp: float = field(default_factory=time.time)
    
    gpu_memory_gb: float = 0
    gpu_utilization: float = 0
    network_ingress_bps: float = 0
    network_egress_bps: float = 0
    storage_read_bps: float = 0
    storage_write_bps: float = 0


# ============== 细粒度计费引擎 ==============

class GranularBillingEngine:
    """细粒度计费引擎"""
    
    # 默认费率配置
    DEFAULT_RATES = {
        ResourceType.GPU_TIME: ResourceRate(
            resource_type=ResourceType.GPU_TIME,
            unit="GPU-hours",
            base_rate=1.0,
        ),
        ResourceType.GPU_MEMORY: ResourceRate(
            resource_type=ResourceType.GPU_MEMORY,
            unit="GB-hours",
            base_rate=0.05,
            tiered_rates=[(16, 0.04), (32, 0.03), (80, 0.02)],
        ),
        ResourceType.GPU_UTILIZATION: ResourceRate(
            resource_type=ResourceType.GPU_UTILIZATION,
            unit="percentage",
            base_rate=0.0,  # 利用率是调整因子
        ),
        ResourceType.NETWORK_INGRESS: ResourceRate(
            resource_type=ResourceType.NETWORK_INGRESS,
            unit="GB",
            base_rate=0.01,
        ),
        ResourceType.NETWORK_EGRESS: ResourceRate(
            resource_type=ResourceType.NETWORK_EGRESS,
            unit="GB",
            base_rate=0.02,
        ),
        ResourceType.STORAGE_READ: ResourceRate(
            resource_type=ResourceType.STORAGE_READ,
            unit="GB",
            base_rate=0.005,
        ),
        ResourceType.STORAGE_WRITE: ResourceRate(
            resource_type=ResourceType.STORAGE_WRITE,
            unit="GB",
            base_rate=0.01,
        ),
    }
    
    # GPU 基础价格
    GPU_BASE_PRICES = {
        "rtx_3060": 0.10,
        "rtx_3080": 0.25,
        "rtx_3090": 0.40,
        "rtx_4060": 0.20,
        "rtx_4080": 0.50,
        "rtx_4090": 0.80,
        "a100": 2.00,
        "h100": 4.00,
        "h200": 6.00,
    }
    
    # 利用率系数
    UTILIZATION_COEFFICIENTS = {
        (0, 20): 0.3,      # 0-20%: 只收30%
        (20, 40): 0.5,     # 20-40%: 收50%
        (40, 60): 0.7,     # 40-60%: 收70%
        (60, 80): 0.9,     # 60-80%: 收90%
        (80, 100): 1.0,    # 80-100%: 全价
    }
    
    # 显存系数
    MEMORY_COEFFICIENTS = {
        (0, 25): 0.7,      # 0-25%: 0.7x
        (25, 50): 0.85,    # 25-50%: 0.85x
        (50, 75): 1.0,     # 50-75%: 1.0x
        (75, 100): 1.15,   # 75-100%: 1.15x
    }
    
    def __init__(self):
        self.rates: Dict[ResourceType, ResourceRate] = dict(self.DEFAULT_RATES)
        self.usage_records: Dict[str, List[ResourceUsage]] = defaultdict(list)
        self.bills: Dict[str, GranularBill] = {}
        self._lock = threading.RLock()
        
        # 实时监控
        self.task_snapshots: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    def record_usage(
        self,
        task_id: str,
        miner_id: str,
        gpu_type: str,
        duration_seconds: float,
        gpu_memory_used_gb: float = 0,
        gpu_memory_total_gb: float = 0,
        gpu_utilization_percent: float = 100,
        network_ingress_gb: float = 0,
        network_egress_gb: float = 0,
        storage_read_gb: float = 0,
        storage_write_gb: float = 0,
    ) -> ResourceUsage:
        """记录资源使用"""
        with self._lock:
            usage = ResourceUsage(
                task_id=task_id,
                miner_id=miner_id,
                gpu_type=gpu_type.lower(),
                duration_seconds=duration_seconds,
                gpu_memory_used_gb=gpu_memory_used_gb,
                gpu_memory_total_gb=gpu_memory_total_gb,
                gpu_utilization_percent=gpu_utilization_percent,
                network_ingress_gb=network_ingress_gb,
                network_egress_gb=network_egress_gb,
                storage_read_gb=storage_read_gb,
                storage_write_gb=storage_write_gb,
            )
            usage.end_time = usage.start_time + duration_seconds
            
            self.usage_records[task_id].append(usage)
            return usage
    
    def record_snapshot(
        self,
        task_id: str,
        gpu_memory_gb: float,
        gpu_utilization: float,
        network_ingress_bps: float = 0,
        network_egress_bps: float = 0,
        storage_read_bps: float = 0,
        storage_write_bps: float = 0,
    ):
        """记录实时快照"""
        with self._lock:
            snapshot = ResourceSnapshot(
                gpu_memory_gb=gpu_memory_gb,
                gpu_utilization=gpu_utilization,
                network_ingress_bps=network_ingress_bps,
                network_egress_bps=network_egress_bps,
                storage_read_bps=storage_read_bps,
                storage_write_bps=storage_write_bps,
            )
            self.task_snapshots[task_id].append(snapshot)
    
    def get_utilization_coefficient(self, utilization_percent: float) -> float:
        """获取利用率系数"""
        for (low, high), coeff in self.UTILIZATION_COEFFICIENTS.items():
            if low <= utilization_percent < high:
                return coeff
        return 1.0
    
    def get_memory_coefficient(self, memory_percent: float) -> float:
        """获取显存系数"""
        for (low, high), coeff in self.MEMORY_COEFFICIENTS.items():
            if low <= memory_percent < high:
                return coeff
        return 1.0
    
    def get_rates(self, gpu_type: str = None) -> Dict:
        """获取计费费率"""
        with self._lock:
            gpu_rates = {}
            if gpu_type:
                gpu_type_lower = gpu_type.lower().replace("-", "_")
                if gpu_type_lower in self.GPU_BASE_PRICES:
                    gpu_rates[gpu_type] = self.GPU_BASE_PRICES[gpu_type_lower]
            else:
                # 返回所有GPU价格
                gpu_rates = {k.upper().replace("_", " "): v for k, v in self.GPU_BASE_PRICES.items()}
            
            # 将 tuple key 转换为字符串 key，以便 JSON 序列化
            utilization_coefficients = {
                f"{low}-{high}%": coeff 
                for (low, high), coeff in self.UTILIZATION_COEFFICIENTS.items()
            }
            memory_coefficients = {
                f"{low}-{high}%": coeff 
                for (low, high), coeff in self.MEMORY_COEFFICIENTS.items()
            }
            
            return {
                "gpu_rates": gpu_rates,
                "network_rate": {
                    "ingress": self.rates[ResourceType.NETWORK_INGRESS].base_rate,
                    "egress": self.rates[ResourceType.NETWORK_EGRESS].base_rate,
                },
                "storage_rate": {
                    "read": self.rates[ResourceType.STORAGE_READ].base_rate,
                    "write": self.rates[ResourceType.STORAGE_WRITE].base_rate,
                },
                "utilization_coefficients": utilization_coefficients,
                "memory_coefficients": memory_coefficients,
            }
    
    def get_task_billing(self, task_id: str) -> Dict:
        """获取任务计费详情"""
        with self._lock:
            bill = self.bills.get(task_id)
            if bill:
                return {
                    "records": [{
                        "type": "computed",
                        "amount": bill.total,
                        "timestamp": bill.billing_period_end,
                    }],
                    "total_cost": bill.total,
                    "breakdown": {
                        "gpu_time": bill.gpu_time_cost,
                        "gpu_memory": bill.gpu_memory_cost,
                        "network": bill.network_cost,
                        "storage": bill.storage_cost,
                    },
                    "period": {
                        "start": bill.billing_period_start,
                        "end": bill.billing_period_end,
                    }
                }
            return {
                "records": [],
                "total_cost": 0,
                "breakdown": {},
                "period": {}
            }

    def calculate_granular_cost(
        self,
        task_id: str,
        user_id: str,
        market_multiplier: float = 1.0,
        time_multiplier: float = 1.0,
    ) -> GranularBill:
        """计算细粒度费用"""
        with self._lock:
            usages = self.usage_records.get(task_id, [])
            if not usages:
                return GranularBill(task_id=task_id, user_id=user_id, total=0)
            
            bill = GranularBill(
                task_id=task_id,
                user_id=user_id,
                miner_id=usages[0].miner_id if usages else "",
                billing_period_start=min(u.start_time for u in usages),
                billing_period_end=max(u.end_time for u in usages),
                market_multiplier=market_multiplier,
                time_multiplier=time_multiplier,
            )
            
            total_gpu_time_cost = 0
            total_memory_cost = 0
            total_utilization_adjustment = 0
            total_network_cost = 0
            total_storage_cost = 0
            
            for usage in usages:
                duration_hours = usage.duration_seconds / 3600
                
                # 1. GPU 时间费用
                gpu_base_price = self.GPU_BASE_PRICES.get(usage.gpu_type, 1.0)
                gpu_time_cost = gpu_base_price * duration_hours
                
                # 2. 利用率调整
                util_coeff = self.get_utilization_coefficient(usage.gpu_utilization_percent)
                utilization_adjustment = gpu_time_cost * (util_coeff - 1)  # 负数表示折扣
                
                # 3. 显存费用
                memory_percent = 0
                if usage.gpu_memory_total_gb > 0:
                    memory_percent = (usage.gpu_memory_used_gb / usage.gpu_memory_total_gb) * 100
                
                memory_coeff = self.get_memory_coefficient(memory_percent)
                memory_rate = self.rates[ResourceType.GPU_MEMORY].get_rate(usage.gpu_memory_used_gb)
                memory_cost = usage.gpu_memory_used_gb * duration_hours * memory_rate * memory_coeff
                
                # 4. 网络费用
                network_ingress_cost = usage.network_ingress_gb * self.rates[ResourceType.NETWORK_INGRESS].get_rate()
                network_egress_cost = usage.network_egress_gb * self.rates[ResourceType.NETWORK_EGRESS].get_rate()
                network_cost = network_ingress_cost + network_egress_cost
                
                # 5. 存储 IO 费用
                storage_read_cost = usage.storage_read_gb * self.rates[ResourceType.STORAGE_READ].get_rate()
                storage_write_cost = usage.storage_write_gb * self.rates[ResourceType.STORAGE_WRITE].get_rate()
                storage_cost = storage_read_cost + storage_write_cost
                
                # 添加明细
                bill.line_items.append({
                    "usage_id": usage.usage_id,
                    "duration_hours": round(duration_hours, 4),
                    "gpu_type": usage.gpu_type,
                    "gpu_time_cost": round(gpu_time_cost, 4),
                    "gpu_utilization": usage.gpu_utilization_percent,
                    "utilization_coefficient": util_coeff,
                    "utilization_adjustment": round(utilization_adjustment, 4),
                    "gpu_memory_used_gb": usage.gpu_memory_used_gb,
                    "memory_coefficient": memory_coeff,
                    "memory_cost": round(memory_cost, 4),
                    "network_cost": round(network_cost, 4),
                    "storage_cost": round(storage_cost, 4),
                })
                
                total_gpu_time_cost += gpu_time_cost
                total_memory_cost += memory_cost
                total_utilization_adjustment += utilization_adjustment
                total_network_cost += network_cost
                total_storage_cost += storage_cost
            
            # 汇总
            bill.gpu_time_cost = round(total_gpu_time_cost, 4)
            bill.gpu_memory_cost = round(total_memory_cost, 4)
            bill.gpu_utilization_adjustment = round(total_utilization_adjustment, 4)
            bill.network_cost = round(total_network_cost, 4)
            bill.storage_cost = round(total_storage_cost, 4)
            
            # 小计
            bill.subtotal = (
                total_gpu_time_cost +
                total_memory_cost +
                total_utilization_adjustment +
                total_network_cost +
                total_storage_cost
            )
            
            # 应用市场和时段乘数
            bill.adjustments = bill.subtotal * (market_multiplier * time_multiplier - 1)
            bill.total = bill.subtotal * market_multiplier * time_multiplier
            
            # 生成公式
            bill.formula = (
                f"Total = (GPU_time × base_price × util_coeff + "
                f"GPU_memory × memory_rate × mem_coeff + "
                f"Network_IO × net_rate + Storage_IO × storage_rate) × "
                f"market_multiplier × time_multiplier"
            )
            
            bill.total = round(bill.total, 4)
            self.bills[bill.bill_id] = bill
            
            return bill
    
    def get_real_time_cost_rate(self, task_id: str) -> Dict:
        """获取实时费用率"""
        with self._lock:
            snapshots = list(self.task_snapshots.get(task_id, []))
            if not snapshots:
                return {"error": "No snapshots available"}
            
            # 取最近的快照
            recent = snapshots[-1] if snapshots else None
            if not recent:
                return {"error": "No recent snapshot"}
            
            # 计算平均值
            if len(snapshots) >= 10:
                recent_snapshots = snapshots[-10:]
                avg_utilization = statistics.mean(s.gpu_utilization for s in recent_snapshots)
                avg_memory = statistics.mean(s.gpu_memory_gb for s in recent_snapshots)
            else:
                avg_utilization = recent.gpu_utilization
                avg_memory = recent.gpu_memory_gb
            
            # 估算每小时费用
            util_coeff = self.get_utilization_coefficient(avg_utilization)
            
            # 假设 H100 GPU
            base_hourly = self.GPU_BASE_PRICES.get("h100", 4.0)
            adjusted_hourly = base_hourly * util_coeff
            
            # 网络费用（按当前速率估算）
            network_hourly = (
                (recent.network_ingress_bps * 3600 / 1e9) * self.rates[ResourceType.NETWORK_INGRESS].base_rate +
                (recent.network_egress_bps * 3600 / 1e9) * self.rates[ResourceType.NETWORK_EGRESS].base_rate
            )
            
            # 存储费用
            storage_hourly = (
                (recent.storage_read_bps * 3600 / 1e9) * self.rates[ResourceType.STORAGE_READ].base_rate +
                (recent.storage_write_bps * 3600 / 1e9) * self.rates[ResourceType.STORAGE_WRITE].base_rate
            )
            
            total_hourly = adjusted_hourly + network_hourly + storage_hourly
            
            return {
                "task_id": task_id,
                "timestamp": time.time(),
                "current_metrics": {
                    "gpu_utilization": recent.gpu_utilization,
                    "gpu_memory_gb": recent.gpu_memory_gb,
                    "network_ingress_mbps": recent.network_ingress_bps / 1e6,
                    "network_egress_mbps": recent.network_egress_bps / 1e6,
                },
                "estimated_hourly_cost": {
                    "gpu_compute": round(adjusted_hourly, 4),
                    "network": round(network_hourly, 4),
                    "storage": round(storage_hourly, 4),
                    "total": round(total_hourly, 4),
                },
                "estimated_per_minute": round(total_hourly / 60, 4),
                "utilization_coefficient": util_coeff,
            }
    
    def get_cost_breakdown(self, task_id: str) -> Dict:
        """获取费用细分"""
        with self._lock:
            usages = self.usage_records.get(task_id, [])
            if not usages:
                return {"error": "No usage records"}
            
            total_duration = sum(u.duration_seconds for u in usages)
            
            # 按资源类型汇总
            by_resource = defaultdict(float)
            
            for usage in usages:
                hours = usage.duration_seconds / 3600
                gpu_price = self.GPU_BASE_PRICES.get(usage.gpu_type, 1.0)
                
                by_resource["gpu_time"] += gpu_price * hours
                by_resource["gpu_memory"] += usage.gpu_memory_used_gb * 0.05 * hours
                by_resource["network_ingress"] += usage.network_ingress_gb * 0.01
                by_resource["network_egress"] += usage.network_egress_gb * 0.02
                by_resource["storage_read"] += usage.storage_read_gb * 0.005
                by_resource["storage_write"] += usage.storage_write_gb * 0.01
            
            total = sum(by_resource.values())
            
            return {
                "task_id": task_id,
                "total_duration_seconds": total_duration,
                "total_duration_hours": round(total_duration / 3600, 4),
                "breakdown": {
                    k: {"amount": round(v, 4), "percent": round(v / total * 100, 2) if total > 0 else 0}
                    for k, v in by_resource.items()
                },
                "total_cost": round(total, 4),
            }
    
    def update_rate(
        self,
        resource_type: ResourceType,
        base_rate: float = None,
        market_multiplier: float = None,
    ):
        """更新费率"""
        with self._lock:
            if resource_type in self.rates:
                if base_rate is not None:
                    self.rates[resource_type].base_rate = base_rate
                if market_multiplier is not None:
                    self.rates[resource_type].market_multiplier = market_multiplier
    
    def get_all_rates(self) -> List[Dict]:
        """获取所有费率"""
        with self._lock:
            return [rate.to_dict() for rate in self.rates.values()]
    
    def get_bill(self, bill_id: str) -> Optional[Dict]:
        """获取账单"""
        with self._lock:
            bill = self.bills.get(bill_id)
            if bill:
                return bill.to_dict()
            return None


# ============== 费用估算器 ==============

class CostEstimator:
    """费用估算器"""
    
    def __init__(self, billing_engine: GranularBillingEngine):
        self.engine = billing_engine
    
    def estimate_task_cost(
        self,
        gpu_type: str,
        duration_hours: float,
        expected_utilization: float = 80,
        expected_memory_gb: float = 16,
        expected_network_gb: float = 10,
        expected_storage_gb: float = 50,
        market_multiplier: float = 1.0,
    ) -> Dict:
        """估算任务费用"""
        gpu_price = self.engine.GPU_BASE_PRICES.get(gpu_type.lower(), 1.0)
        
        # GPU 时间
        util_coeff = self.engine.get_utilization_coefficient(expected_utilization)
        gpu_time_cost = gpu_price * duration_hours * util_coeff
        
        # 显存
        memory_cost = expected_memory_gb * 0.05 * duration_hours
        
        # 网络
        network_cost = expected_network_gb * 0.015  # 平均
        
        # 存储
        storage_cost = expected_storage_gb * 0.0075  # 平均
        
        subtotal = gpu_time_cost + memory_cost + network_cost + storage_cost
        total = subtotal * market_multiplier
        
        return {
            "gpu_type": gpu_type,
            "duration_hours": duration_hours,
            "estimates": {
                "gpu_time_cost": round(gpu_time_cost, 4),
                "memory_cost": round(memory_cost, 4),
                "network_cost": round(network_cost, 4),
                "storage_cost": round(storage_cost, 4),
            },
            "assumptions": {
                "expected_utilization": expected_utilization,
                "utilization_coefficient": util_coeff,
                "expected_memory_gb": expected_memory_gb,
            },
            "subtotal": round(subtotal, 4),
            "market_multiplier": market_multiplier,
            "total_estimated": round(total, 4),
            "confidence_range": {
                "low": round(total * 0.8, 4),
                "high": round(total * 1.3, 4),
            },
        }


# ============== 全局实例 ==============

_billing_engine: Optional[GranularBillingEngine] = None
_cost_estimator: Optional[CostEstimator] = None


def get_granular_billing() -> Tuple[GranularBillingEngine, CostEstimator]:
    """获取细粒度计费系统"""
    global _billing_engine, _cost_estimator
    
    if _billing_engine is None:
        _billing_engine = GranularBillingEngine()
        _cost_estimator = CostEstimator(_billing_engine)
    
    return _billing_engine, _cost_estimator
