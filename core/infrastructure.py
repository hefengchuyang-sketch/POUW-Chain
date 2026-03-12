"""
技术基础设施增强 v2.0
=====================

改进要点：
1. 云服务集成 - AWS/Azure/GCP 多云接入, 混合部署
2. 弹性伸缩 - 自动扩缩容、负载均衡、资源池化
3. 全球节点协调 - 跨区域同步、智能路由、CDN加速
4. 性能优化 - 连接池、缓存策略、批处理管道

本模块补充现有 p2p_network.py 和 tcp_network.py,
提供生产级基础设施能力。
"""

import time
import uuid
import json
import sqlite3
import threading
import logging
import math
import hashlib
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from contextlib import contextmanager
from collections import deque

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class CloudProvider(Enum):
    """云服务提供商"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ALIBABA = "alibaba"
    HUAWEI = "huawei"
    TENCENT = "tencent"
    BARE_METAL = "bare_metal"       # 裸金属
    HYBRID = "hybrid"               # 混合


class ScalingPolicy(Enum):
    """伸缩策略"""
    CPU_BASED = "cpu_based"           # CPU利用率
    GPU_BASED = "gpu_based"           # GPU利用率
    MEMORY_BASED = "memory_based"     # 内存利用率
    QUEUE_BASED = "queue_based"       # 队列深度
    PREDICTIVE = "predictive"         # 预测性伸缩
    SCHEDULE = "schedule"             # 定时伸缩
    CUSTOM = "custom"                 # 自定义


class NodeRegion(Enum):
    """节点区域"""
    CN_EAST = "cn-east"
    CN_SOUTH = "cn-south"
    CN_NORTH = "cn-north"
    ASIA_SOUTHEAST = "asia-southeast"
    ASIA_NORTHEAST = "asia-northeast"
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    ME_SOUTH = "me-south"
    SA_EAST = "sa-east"
    AF_SOUTH = "af-south"
    AU_EAST = "au-east"


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"                       # 最近最少使用
    LFU = "lfu"                       # 最不经常使用
    TTL = "ttl"                       # 基于过期时间
    WRITE_THROUGH = "write_through"   # 写穿透
    WRITE_BACK = "write_back"         # 写回
    ADAPTIVE = "adaptive"             # 自适应


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class CloudInstance:
    """云实例"""
    instance_id: str
    provider: CloudProvider
    region: NodeRegion
    instance_type: str = ""           # e.g. p4d.24xlarge
    gpu_type: str = ""
    gpu_count: int = 0
    cpu_cores: int = 0
    memory_gb: float = 0.0
    storage_gb: float = 0.0
    bandwidth_gbps: float = 0.0
    status: str = "running"
    ip_address: str = ""
    cost_per_hour: float = 0.0
    launched_at: float = 0.0
    tags: Dict = field(default_factory=dict)


@dataclass
class ScalingRule:
    """伸缩规则"""
    rule_id: str
    policy: ScalingPolicy
    # 阈值
    scale_up_threshold: float = 80.0    # 扩容阈值 (%)
    scale_down_threshold: float = 30.0  # 缩容阈值 (%)
    # 限制
    min_instances: int = 1
    max_instances: int = 100
    # 冷却
    cooldown_seconds: int = 300
    # 步进
    scale_up_step: int = 2              # 每次扩容数量
    scale_down_step: int = 1            # 每次缩容数量
    # 状态
    last_scale_action: float = 0.0
    enabled: bool = True


@dataclass
class ConnectionPoolConfig:
    """连接池配置"""
    pool_name: str
    min_connections: int = 5
    max_connections: int = 50
    idle_timeout_s: int = 300
    max_lifetime_s: int = 3600
    validation_interval_s: int = 30
    retry_count: int = 3
    retry_delay_s: float = 1.0


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: float = 0.0
    # CPU
    cpu_usage_percent: float = 0.0
    cpu_cores_used: float = 0.0
    # GPU
    gpu_usage_percent: float = 0.0
    gpu_memory_used_gb: float = 0.0
    gpu_temperature_c: float = 0.0
    # 内存
    memory_usage_percent: float = 0.0
    memory_used_gb: float = 0.0
    # 网络
    network_in_mbps: float = 0.0
    network_out_mbps: float = 0.0
    # 存储
    disk_usage_percent: float = 0.0
    disk_iops: float = 0.0
    # 应用
    request_rate: float = 0.0         # 请求/秒
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0           # 错误率
    active_connections: int = 0
    queue_depth: int = 0


# ============================================================
# 多云集成管理器
# ============================================================

class MultiCloudManager:
    """
    多云集成管理器

    功能：
    1. 统一多云资源管理（AWS/Azure/GCP/阿里云/华为云/腾讯云）
    2. 跨云实例编排
    3. 成本优化
    4. 灾备切换
    """

    SECURITY_LEVEL = "HIGH"

    # 各区域推荐的云提供商
    REGION_PROVIDERS = {
        NodeRegion.CN_EAST: [CloudProvider.ALIBABA, CloudProvider.TENCENT,
                             CloudProvider.HUAWEI],
        NodeRegion.CN_SOUTH: [CloudProvider.ALIBABA, CloudProvider.TENCENT],
        NodeRegion.CN_NORTH: [CloudProvider.HUAWEI, CloudProvider.ALIBABA],
        NodeRegion.ASIA_SOUTHEAST: [CloudProvider.AWS, CloudProvider.GCP,
                                     CloudProvider.ALIBABA],
        NodeRegion.ASIA_NORTHEAST: [CloudProvider.AWS, CloudProvider.GCP],
        NodeRegion.US_EAST: [CloudProvider.AWS, CloudProvider.AZURE,
                             CloudProvider.GCP],
        NodeRegion.US_WEST: [CloudProvider.AWS, CloudProvider.GCP],
        NodeRegion.EU_WEST: [CloudProvider.AWS, CloudProvider.AZURE],
        NodeRegion.EU_CENTRAL: [CloudProvider.AZURE, CloudProvider.AWS],
    }

    # GPU 实例类型映射
    GPU_INSTANCE_TYPES = {
        CloudProvider.AWS: {
            "H100": "p5.48xlarge",
            "A100": "p4d.24xlarge",
            "V100": "p3.2xlarge",
            "T4": "g4dn.xlarge",
            "L4": "g6.xlarge",
        },
        CloudProvider.AZURE: {
            "H100": "Standard_ND96isr_H100_v5",
            "A100": "Standard_ND96asr_v4",
            "V100": "Standard_NC6s_v3",
            "T4": "Standard_NC4as_T4_v3",
        },
        CloudProvider.GCP: {
            "H100": "a3-highgpu-8g",
            "A100": "a2-highgpu-1g",
            "V100": "n1-standard-8 + V100",
            "T4": "n1-standard-4 + T4",
            "L4": "g2-standard-4",
        },
        CloudProvider.ALIBABA: {
            "A100": "ecs.gn7.xlarge",
            "V100": "ecs.gn6v.xlarge",
            "T4": "ecs.gn6i.xlarge",
        },
    }

    # 每小时参考价格（USD）
    GPU_PRICING = {
        "H100": {"aws": 32.77, "azure": 33.0, "gcp": 30.0},
        "A100": {"aws": 12.58, "azure": 13.0, "gcp": 11.0,
                 "alibaba": 9.0},
        "V100": {"aws": 3.06, "azure": 3.2, "gcp": 2.48,
                 "alibaba": 2.5},
        "T4": {"aws": 0.526, "azure": 0.55, "gcp": 0.35,
                "alibaba": 0.4},
        "L4": {"aws": 0.81, "gcp": 0.70},
    }

    def __init__(self, db_path: str = "data/cloud_infra.db"):
        self.db_path = db_path
        self.lock = threading.Lock()

        self.instances: Dict[str, CloudInstance] = {}
        self.credentials: Dict[CloudProvider, Dict] = {}
        self.region_health: Dict[NodeRegion, HealthStatus] = {
            r: HealthStatus.UNKNOWN for r in NodeRegion}

        self._init_db()
        logger.info("[多云管理] 多云集成管理器已初始化")

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
                CREATE TABLE IF NOT EXISTS cloud_instances (
                    instance_id TEXT PRIMARY KEY,
                    provider TEXT,
                    region TEXT,
                    instance_type TEXT,
                    gpu_type TEXT,
                    gpu_count INTEGER,
                    cpu_cores INTEGER,
                    memory_gb REAL,
                    storage_gb REAL,
                    bandwidth_gbps REAL,
                    status TEXT,
                    ip_address TEXT,
                    cost_per_hour REAL,
                    launched_at REAL,
                    tags_json TEXT
                );

                CREATE TABLE IF NOT EXISTS cloud_costs (
                    cost_id TEXT PRIMARY KEY,
                    instance_id TEXT,
                    provider TEXT,
                    region TEXT,
                    amount REAL,
                    currency TEXT DEFAULT 'USD',
                    period_start REAL,
                    period_end REAL
                );

                CREATE TABLE IF NOT EXISTS region_routing (
                    route_id TEXT PRIMARY KEY,
                    from_region TEXT,
                    to_region TEXT,
                    latency_ms REAL,
                    bandwidth_mbps REAL,
                    cost_per_gb REAL,
                    updated_at REAL
                );
            """)

    def configure_provider(self, provider: CloudProvider,
                             credentials: Dict):
        """配置云提供商凭证"""
        # 仅保存凭证引用，不保存明文
        self.credentials[provider] = {
            "configured": True,
            "provider": provider.value,
            "configured_at": time.time(),
        }
        logger.info(f"[多云管理] 配置提供商: {provider.value}")

    def find_optimal_provider(self, gpu_type: str,
                                region: Optional[NodeRegion] = None,
                                max_cost: float = 0) -> List[Dict]:
        """查找最优云提供商"""
        options = []

        for provider, types in self.GPU_INSTANCE_TYPES.items():
            if gpu_type not in types:
                continue

            instance_type = types[gpu_type]
            pricing = self.GPU_PRICING.get(gpu_type, {})
            price = pricing.get(provider.value, 0)

            if price == 0:
                continue
            if max_cost > 0 and price > max_cost:
                continue

            # 检查区域支持
            if region:
                supported_providers = self.REGION_PROVIDERS.get(region, [])
                if provider not in supported_providers:
                    continue

            options.append({
                "provider": provider.value,
                "instance_type": instance_type,
                "gpu_type": gpu_type,
                "cost_per_hour": price,
                "region": region.value if region else "any",
            })

        # 按价格排序
        options.sort(key=lambda x: x["cost_per_hour"])
        return options

    def provision_instance(self, provider: CloudProvider,
                             region: NodeRegion,
                             gpu_type: str,
                             gpu_count: int = 1,
                             tags: Optional[Dict] = None) -> Optional[str]:
        """创建云实例"""
        instance_types = self.GPU_INSTANCE_TYPES.get(provider, {})
        instance_type = instance_types.get(gpu_type)
        if not instance_type:
            logger.error(
                f"[多云管理] 不支持的配置: {provider.value}/{gpu_type}")
            return None

        pricing = self.GPU_PRICING.get(gpu_type, {})
        cost = pricing.get(provider.value, 0) * gpu_count

        instance_id = f"i-{provider.value[:3]}-{uuid.uuid4().hex[:12]}"

        instance = CloudInstance(
            instance_id=instance_id,
            provider=provider,
            region=region,
            instance_type=instance_type,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            cost_per_hour=cost,
            launched_at=time.time(),
            status="provisioning",
            tags=tags or {},
        )

        with self.lock:
            self.instances[instance_id] = instance

        self._save_instance(instance)
        logger.info(
            f"[多云管理] 创建实例: {instance_id} "
            f"[{provider.value}/{region.value}] "
            f"{gpu_count}x{gpu_type} ${cost}/h")

        return instance_id

    def terminate_instance(self, instance_id: str) -> bool:
        """终止云实例"""
        with self.lock:
            instance = self.instances.get(instance_id)
            if not instance:
                return False

            instance.status = "terminated"
            runtime_hours = (time.time() - instance.launched_at) / 3600
            total_cost = runtime_hours * instance.cost_per_hour

            logger.info(
                f"[多云管理] 终止实例: {instance_id} "
                f"运行 {runtime_hours:.1f}h, 费用 ${total_cost:.2f}")

        self._save_instance(instance)
        return True

    def get_fleet_summary(self) -> Dict:
        """获取实例集群概览"""
        active = [i for i in self.instances.values()
                  if i.status in ("running", "provisioning")]

        by_provider = {}
        by_region = {}
        total_cost = 0.0
        total_gpus = 0

        for inst in active:
            p = inst.provider.value
            r = inst.region.value

            by_provider[p] = by_provider.get(p, 0) + 1
            by_region[r] = by_region.get(r, 0) + 1
            total_cost += inst.cost_per_hour
            total_gpus += inst.gpu_count

        return {
            "total_instances": len(active),
            "total_gpus": total_gpus,
            "hourly_cost_usd": round(total_cost, 2),
            "daily_cost_usd": round(total_cost * 24, 2),
            "monthly_cost_usd": round(total_cost * 24 * 30, 2),
            "by_provider": by_provider,
            "by_region": by_region,
        }

    def _save_instance(self, inst: CloudInstance):
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cloud_instances
                (instance_id, provider, region, instance_type,
                 gpu_type, gpu_count, cpu_cores, memory_gb,
                 storage_gb, bandwidth_gbps, status, ip_address,
                 cost_per_hour, launched_at, tags_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                inst.instance_id, inst.provider.value, inst.region.value,
                inst.instance_type, inst.gpu_type, inst.gpu_count,
                inst.cpu_cores, inst.memory_gb, inst.storage_gb,
                inst.bandwidth_gbps, inst.status, inst.ip_address,
                inst.cost_per_hour, inst.launched_at,
                json.dumps(inst.tags),
            ))


# ============================================================
# 弹性伸缩引擎
# ============================================================

class AutoScaler:
    """
    弹性伸缩引擎

    功能：
    1. 多维度伸缩策略（CPU/GPU/内存/队列/预测）
    2. 冷却期保护
    3. 预测性伸缩（基于历史模式）
    4. 成本感知伸缩
    """

    SECURITY_LEVEL = "MEDIUM"

    def __init__(self, cloud_manager: MultiCloudManager):
        self.cloud_manager = cloud_manager
        self.lock = threading.Lock()

        self.rules: Dict[str, ScalingRule] = {}
        self.metrics_history: deque = deque(maxlen=1440)  # 24h * 60 = 1440分钟
        self.current_metrics: Optional[PerformanceMetrics] = None

        # 预测模型数据
        self.hourly_patterns: Dict[int, float] = {}     # hour -> avg load
        self.daily_patterns: Dict[int, float] = {}       # day_of_week -> avg load

        logger.info("[弹性伸缩] 自动伸缩引擎已初始化")

    def add_rule(self, rule: ScalingRule):
        """添加伸缩规则"""
        self.rules[rule.rule_id] = rule
        logger.info(
            f"[弹性伸缩] 添加规则: {rule.rule_id} [{rule.policy.value}] "
            f"up>{rule.scale_up_threshold}% down<{rule.scale_down_threshold}%")

    def update_metrics(self, metrics: PerformanceMetrics):
        """更新性能指标"""
        metrics.timestamp = time.time()
        self.current_metrics = metrics
        self.metrics_history.append(metrics)

        # 更新时间模式
        import datetime
        dt = datetime.datetime.fromtimestamp(metrics.timestamp)
        hour = dt.hour
        day = dt.weekday()

        # 指数移动平均
        alpha = 0.1
        current_load = metrics.cpu_usage_percent

        prev_hourly = self.hourly_patterns.get(hour, current_load)
        self.hourly_patterns[hour] = prev_hourly * (1 - alpha) + current_load * alpha

        prev_daily = self.daily_patterns.get(day, current_load)
        self.daily_patterns[day] = prev_daily * (1 - alpha) + current_load * alpha

    def evaluate_scaling(self) -> List[Dict]:
        """评估伸缩需求"""
        if not self.current_metrics:
            return []

        actions = []

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            # 冷却期检查
            if time.time() - rule.last_scale_action < rule.cooldown_seconds:
                continue

            action = self._evaluate_rule(rule, self.current_metrics)
            if action:
                actions.append(action)

        return actions

    def _evaluate_rule(self, rule: ScalingRule,
                        metrics: PerformanceMetrics) -> Optional[Dict]:
        """评估单条规则"""
        current_value = 0.0

        if rule.policy == ScalingPolicy.CPU_BASED:
            current_value = metrics.cpu_usage_percent
        elif rule.policy == ScalingPolicy.GPU_BASED:
            current_value = metrics.gpu_usage_percent
        elif rule.policy == ScalingPolicy.MEMORY_BASED:
            current_value = metrics.memory_usage_percent
        elif rule.policy == ScalingPolicy.QUEUE_BASED:
            # 队列深度转化为利用率百分比
            current_value = min(100, metrics.queue_depth / 100 * 100)
        elif rule.policy == ScalingPolicy.PREDICTIVE:
            return self._evaluate_predictive(rule, metrics)
        else:
            return None

        active_instances = len([
            i for i in self.cloud_manager.instances.values()
            if i.status == "running"
        ])

        if current_value > rule.scale_up_threshold:
            if active_instances < rule.max_instances:
                return {
                    "action": "scale_up",
                    "rule_id": rule.rule_id,
                    "policy": rule.policy.value,
                    "current_value": current_value,
                    "threshold": rule.scale_up_threshold,
                    "instances_to_add": rule.scale_up_step,
                    "current_instances": active_instances,
                }

        elif current_value < rule.scale_down_threshold:
            if active_instances > rule.min_instances:
                return {
                    "action": "scale_down",
                    "rule_id": rule.rule_id,
                    "policy": rule.policy.value,
                    "current_value": current_value,
                    "threshold": rule.scale_down_threshold,
                    "instances_to_remove": rule.scale_down_step,
                    "current_instances": active_instances,
                }

        return None

    def _evaluate_predictive(self, rule: ScalingRule,
                               metrics: PerformanceMetrics) -> Optional[Dict]:
        """预测性伸缩评估"""
        import datetime
        dt = datetime.datetime.fromtimestamp(time.time())
        next_hour = (dt.hour + 1) % 24

        predicted_load = self.hourly_patterns.get(next_hour, 50)
        day_factor = self.daily_patterns.get(dt.weekday(), 50) / 50

        predicted = predicted_load * day_factor

        active_instances = len([
            i for i in self.cloud_manager.instances.values()
            if i.status == "running"
        ])

        if predicted > rule.scale_up_threshold:
            return {
                "action": "scale_up",
                "rule_id": rule.rule_id,
                "policy": "predictive",
                "predicted_load": round(predicted, 1),
                "instances_to_add": rule.scale_up_step,
                "current_instances": active_instances,
                "reason": f"预测下一小时负载 {predicted:.1f}%",
            }
        elif predicted < rule.scale_down_threshold and \
                metrics.cpu_usage_percent < rule.scale_down_threshold:
            return {
                "action": "scale_down",
                "rule_id": rule.rule_id,
                "policy": "predictive",
                "predicted_load": round(predicted, 1),
                "instances_to_remove": rule.scale_down_step,
                "current_instances": active_instances,
                "reason": f"预测下一小时负载 {predicted:.1f}%",
            }

        return None

    def execute_scaling(self, action: Dict) -> bool:
        """执行伸缩动作"""
        rule = self.rules.get(action.get("rule_id"))
        if not rule:
            return False

        if action["action"] == "scale_up":
            count = action.get("instances_to_add", 1)
            for _ in range(count):
                instance_id = self.cloud_manager.provision_instance(
                    provider=CloudProvider.AWS,
                    region=NodeRegion.US_EAST,
                    gpu_type="T4",
                    gpu_count=1,
                    tags={"auto_scaled": True, "rule_id": rule.rule_id},
                )
                if instance_id:
                    logger.info(
                        f"[弹性伸缩] 扩容: 新实例 {instance_id}")

        elif action["action"] == "scale_down":
            count = action.get("instances_to_remove", 1)
            # 选择最近启动的自动伸缩实例
            auto_instances = sorted(
                [i for i in self.cloud_manager.instances.values()
                 if i.status == "running"
                 and i.tags.get("auto_scaled")],
                key=lambda x: x.launched_at, reverse=True
            )

            for inst in auto_instances[:count]:
                self.cloud_manager.terminate_instance(inst.instance_id)
                logger.info(
                    f"[弹性伸缩] 缩容: 终止实例 {inst.instance_id}")

        rule.last_scale_action = time.time()
        return True

    def get_scaling_stats(self) -> Dict:
        """获取伸缩统计"""
        active = [i for i in self.cloud_manager.instances.values()
                  if i.status == "running"]
        auto_scaled = [i for i in active if i.tags.get("auto_scaled")]

        return {
            "total_instances": len(active),
            "auto_scaled_instances": len(auto_scaled),
            "active_rules": sum(1 for r in self.rules.values() if r.enabled),
            "current_metrics": {
                "cpu": self.current_metrics.cpu_usage_percent
                    if self.current_metrics else 0,
                "gpu": self.current_metrics.gpu_usage_percent
                    if self.current_metrics else 0,
                "memory": self.current_metrics.memory_usage_percent
                    if self.current_metrics else 0,
            },
            "hourly_pattern": dict(self.hourly_patterns),
        }


# ============================================================
# 高性能缓存系统
# ============================================================

class PerformanceCache:
    """
    高性能多级缓存系统

    功能：
    1. L1 内存缓存（热数据）
    2. L2 本地磁盘缓存
    3. 自适应缓存策略（LRU/LFU/TTL）
    4. 缓存预热与失效
    """

    def __init__(self, max_l1_size: int = 10000,
                  strategy: CacheStrategy = CacheStrategy.LRU):
        self.strategy = strategy
        self.max_l1_size = max_l1_size
        self.lock = threading.Lock()

        # L1 缓存
        self.l1_cache: Dict[str, Any] = {}
        self.l1_ttl: Dict[str, float] = {}       # key -> expire_time
        self.l1_access_count: Dict[str, int] = {} # key -> access count
        self.l1_access_time: Dict[str, float] = {} # key -> last access time
        self.l1_order: List[str] = []              # LRU 顺序

        # 统计
        self.stats = {
            "hits": 0, "misses": 0,
            "l1_hits": 0, "evictions": 0,
        }

        logger.info(
            f"[缓存系统] 初始化: 策略={strategy.value}, "
            f"L1容量={max_l1_size}")

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self.lock:
            # L1 查找
            if key in self.l1_cache:
                # 检查TTL
                if key in self.l1_ttl:
                    if time.time() > self.l1_ttl[key]:
                        self._evict_key(key)
                        self.stats["misses"] += 1
                        return None

                # 更新访问信息
                self.l1_access_count[key] = \
                    self.l1_access_count.get(key, 0) + 1
                self.l1_access_time[key] = time.time()

                # LRU 顺序更新
                if key in self.l1_order:
                    self.l1_order.remove(key)
                self.l1_order.append(key)

                self.stats["hits"] += 1
                self.stats["l1_hits"] += 1
                return self.l1_cache[key]

            self.stats["misses"] += 1
            return None

    def set(self, key: str, value: Any,
            ttl_seconds: float = 0) -> bool:
        """设置缓存"""
        with self.lock:
            # 容量检查
            if len(self.l1_cache) >= self.max_l1_size and \
                    key not in self.l1_cache:
                self._evict()

            self.l1_cache[key] = value
            self.l1_access_count[key] = 0
            self.l1_access_time[key] = time.time()

            if ttl_seconds > 0:
                self.l1_ttl[key] = time.time() + ttl_seconds

            if key in self.l1_order:
                self.l1_order.remove(key)
            self.l1_order.append(key)

            return True

    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self.lock:
            return self._evict_key(key)

    def _evict(self):
        """淘汰缓存项"""
        if not self.l1_cache:
            return

        if self.strategy == CacheStrategy.LRU:
            # 最近最少使用
            if self.l1_order:
                key = self.l1_order[0]
                self._evict_key(key)
        elif self.strategy == CacheStrategy.LFU:
            # 最不经常使用
            if self.l1_access_count:
                key = min(self.l1_access_count,
                          key=lambda k: self.l1_access_count.get(k, 0))
                self._evict_key(key)
        elif self.strategy == CacheStrategy.TTL:
            # 最早过期
            expired = [k for k, t in self.l1_ttl.items()
                       if time.time() > t]
            for key in expired:
                self._evict_key(key)
            if not expired and self.l1_order:
                self._evict_key(self.l1_order[0])
        elif self.strategy == CacheStrategy.ADAPTIVE:
            # 自适应：结合 LRU 和 LFU
            now = time.time()
            scores = {}
            for key in self.l1_cache:
                freq = self.l1_access_count.get(key, 0)
                recency = now - self.l1_access_time.get(key, 0)
                # 分数 = 频率 / (时间衰减 + 1)
                scores[key] = freq / (recency / 60 + 1)

            if scores:
                key = min(scores, key=lambda k: scores[k])
                self._evict_key(key)

        self.stats["evictions"] += 1

    def _evict_key(self, key: str) -> bool:
        """移除指定缓存项"""
        if key not in self.l1_cache:
            return False

        del self.l1_cache[key]
        self.l1_access_count.pop(key, None)
        self.l1_access_time.pop(key, None)
        self.l1_ttl.pop(key, None)
        if key in self.l1_order:
            self.l1_order.remove(key)
        return True

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.l1_cache.clear()
            self.l1_ttl.clear()
            self.l1_access_count.clear()
            self.l1_access_time.clear()
            self.l1_order.clear()

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / max(1, total)

        return {
            "strategy": self.strategy.value,
            "l1_size": len(self.l1_cache),
            "l1_max_size": self.max_l1_size,
            "total_requests": total,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": round(hit_rate, 4),
            "evictions": self.stats["evictions"],
        }


# ============================================================
# 批处理管道
# ============================================================

class BatchProcessor:
    """
    批处理管道

    功能：
    1. 请求聚合与批处理
    2. 流水线并行执行
    3. 背压控制
    4. 失败重试
    """

    def __init__(self, batch_size: int = 100,
                  flush_interval_s: float = 1.0,
                  max_retries: int = 3):
        self.batch_size = batch_size
        self.flush_interval_s = flush_interval_s
        self.max_retries = max_retries
        self.lock = threading.Lock()

        self.buffer: List[Dict] = []
        self.processors: Dict[str, Callable] = {}
        self.last_flush = time.time()

        # 统计
        self.stats = {
            "total_items": 0,
            "total_batches": 0,
            "total_errors": 0,
            "total_retries": 0,
            "avg_batch_size": 0,
        }

        logger.info(
            f"[批处理] 初始化: batch_size={batch_size}, "
            f"flush_interval={flush_interval_s}s")

    def register_processor(self, item_type: str, processor: Callable):
        """注册处理器"""
        self.processors[item_type] = processor

    def add_item(self, item_type: str, data: Dict) -> str:
        """添加待处理项"""
        item_id = str(uuid.uuid4())[:12]

        with self.lock:
            self.buffer.append({
                "id": item_id,
                "type": item_type,
                "data": data,
                "added_at": time.time(),
                "retries": 0,
            })
            self.stats["total_items"] += 1

            # 自动刷新
            if len(self.buffer) >= self.batch_size:
                self._flush_batch()
            elif time.time() - self.last_flush >= self.flush_interval_s:
                self._flush_batch()

        return item_id

    def _flush_batch(self):
        """刷新批处理"""
        if not self.buffer:
            return

        batch = self.buffer[:self.batch_size]
        self.buffer = self.buffer[self.batch_size:]

        # 按类型分组
        by_type: Dict[str, List] = {}
        for item in batch:
            t = item["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(item)

        # 批量处理
        for item_type, items in by_type.items():
            processor = self.processors.get(item_type)
            if not processor:
                logger.warning(f"[批处理] 未注册处理器: {item_type}")
                continue

            try:
                processor([i["data"] for i in items])
            except Exception as e:
                logger.error(f"[批处理] 处理失败: {item_type} - {e}")
                self.stats["total_errors"] += 1

                # 重试
                for item in items:
                    if item["retries"] < self.max_retries:
                        item["retries"] += 1
                        self.buffer.append(item)
                        self.stats["total_retries"] += 1

        self.stats["total_batches"] += 1
        self.stats["avg_batch_size"] = (
            self.stats["total_items"] / max(1, self.stats["total_batches"]))
        self.last_flush = time.time()

    def flush(self):
        """手动刷新"""
        with self.lock:
            while self.buffer:
                self._flush_batch()

    def get_stats(self) -> Dict:
        """获取批处理统计"""
        return {
            **self.stats,
            "buffer_size": len(self.buffer),
            "registered_processors": list(self.processors.keys()),
        }


# ============================================================
# 全局节点协调器
# ============================================================

class GlobalNodeCoordinator:
    """
    全球节点协调器

    功能：
    1. 跨区域节点发现与注册
    2. 智能路由（延迟最优/成本最优/可用性最优）
    3. 区域健康监控
    4. 流量调度
    """

    # 区域间延迟矩阵（ms）
    REGION_LATENCY = {
        (NodeRegion.CN_EAST, NodeRegion.CN_SOUTH): 15,
        (NodeRegion.CN_EAST, NodeRegion.CN_NORTH): 20,
        (NodeRegion.CN_EAST, NodeRegion.ASIA_SOUTHEAST): 40,
        (NodeRegion.CN_EAST, NodeRegion.ASIA_NORTHEAST): 30,
        (NodeRegion.CN_EAST, NodeRegion.US_WEST): 150,
        (NodeRegion.CN_EAST, NodeRegion.US_EAST): 200,
        (NodeRegion.CN_EAST, NodeRegion.EU_WEST): 250,
        (NodeRegion.US_EAST, NodeRegion.US_WEST): 60,
        (NodeRegion.US_EAST, NodeRegion.EU_WEST): 80,
        (NodeRegion.US_EAST, NodeRegion.EU_CENTRAL): 90,
        (NodeRegion.EU_WEST, NodeRegion.EU_CENTRAL): 10,
        (NodeRegion.ASIA_SOUTHEAST, NodeRegion.AU_EAST): 60,
    }

    def __init__(self):
        self.lock = threading.Lock()
        self.nodes: Dict[str, Dict] = {}           # node_id -> info
        self.region_stats: Dict[NodeRegion, Dict] = {}

        logger.info("[全球协调] 全球节点协调器已初始化")

    def register_node(self, node_id: str, region: NodeRegion,
                       capabilities: Dict) -> bool:
        """注册全球节点"""
        with self.lock:
            self.nodes[node_id] = {
                "node_id": node_id,
                "region": region,
                "capabilities": capabilities,
                "registered_at": time.time(),
                "last_heartbeat": time.time(),
                "health": HealthStatus.HEALTHY.value,
                "load": 0.0,
            }

            # 更新区域统计
            if region not in self.region_stats:
                self.region_stats[region] = {
                    "node_count": 0,
                    "total_gpu": 0,
                    "avg_load": 0.0,
                }
            self.region_stats[region]["node_count"] += 1
            self.region_stats[region]["total_gpu"] += \
                capabilities.get("gpu_count", 0)

        return True

    def get_latency(self, from_region: NodeRegion,
                     to_region: NodeRegion) -> float:
        """获取区域间延迟"""
        if from_region == to_region:
            return 1.0  # 同区域

        key1 = (from_region, to_region)
        key2 = (to_region, from_region)

        return self.REGION_LATENCY.get(
            key1, self.REGION_LATENCY.get(key2, 300))

    def find_optimal_route(self, source_region: NodeRegion,
                            task_requirements: Dict) -> List[Dict]:
        """查找最优任务路由"""
        candidates = []

        for node_id, info in self.nodes.items():
            if info["health"] != HealthStatus.HEALTHY.value:
                continue
            if info["load"] > 0.9:
                continue

            region = info["region"]
            latency = self.get_latency(source_region, region)

            # 检查能力匹配
            caps = info["capabilities"]
            min_gpu = task_requirements.get("min_gpu", 0)
            if caps.get("gpu_count", 0) < min_gpu:
                continue

            gpu_type = task_requirements.get("gpu_type")
            if gpu_type and caps.get("gpu_type") != gpu_type:
                continue

            # 计算路由评分
            score = self._calculate_route_score(
                latency, info["load"], caps, task_requirements)

            candidates.append({
                "node_id": node_id,
                "region": region.value,
                "latency_ms": latency,
                "load": info["load"],
                "score": round(score, 3),
                "capabilities": caps,
            })

        candidates.sort(key=lambda x: -x["score"])
        return candidates[:10]

    def _calculate_route_score(self, latency: float, load: float,
                                 capabilities: Dict,
                                 requirements: Dict) -> float:
        """计算路由评分"""
        # 延迟评分 (40%) - 延迟越低越好
        latency_score = max(0, 1 - latency / 500)

        # 负载评分 (25%) - 负载越低越好
        load_score = 1 - load

        # 能力匹配评分 (25%)
        gpu_match = 1.0 if capabilities.get("gpu_type") == \
            requirements.get("gpu_type") else 0.5
        gpu_count = capabilities.get("gpu_count", 0)
        min_gpu = requirements.get("min_gpu", 1)
        gpu_score = min(1, gpu_count / max(1, min_gpu))
        capability_score = (gpu_match + gpu_score) / 2

        # 可用性评分 (10%)
        uptime = capabilities.get("uptime_ratio", 0.95)
        availability_score = uptime

        return (latency_score * 0.40 +
                load_score * 0.25 +
                capability_score * 0.25 +
                availability_score * 0.10)

    def get_global_status(self) -> Dict:
        """获取全球节点状态"""
        total_nodes = len(self.nodes)
        healthy = sum(1 for n in self.nodes.values()
                      if n["health"] == HealthStatus.HEALTHY.value)

        return {
            "total_nodes": total_nodes,
            "healthy_nodes": healthy,
            "unhealthy_nodes": total_nodes - healthy,
            "regions": {
                r.value: {
                    **stats,
                    "health": (HealthStatus.HEALTHY.value
                               if stats["node_count"] > 0
                               else HealthStatus.UNKNOWN.value),
                }
                for r, stats in self.region_stats.items()
            },
        }
