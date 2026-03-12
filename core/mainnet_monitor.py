"""
mainnet_monitor.py - 主网监控系统

Phase 10 功能：
1. 系统健康监控
2. 性能指标收集
3. 告警系统
4. 仪表盘数据
5. 日志聚合
6. 异常检测
"""

import time
import uuid
import threading
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from collections import defaultdict, deque
import json


# ============== 枚举类型 ==============

class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """告警严重性"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """告警状态"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class MetricType(Enum):
    """指标类型"""
    GAUGE = "gauge"                    # 瞬时值
    COUNTER = "counter"                # 累计值
    HISTOGRAM = "histogram"            # 分布
    SUMMARY = "summary"                # 摘要


class ComponentType(Enum):
    """组件类型"""
    BLOCKCHAIN = "blockchain"
    NETWORK = "network"
    COMPUTE = "compute"
    STORAGE = "storage"
    API = "api"
    DATABASE = "database"


# ============== 数据结构 ==============

@dataclass
class Metric:
    """指标"""
    name: str
    value: float = 0
    metric_type: MetricType = MetricType.GAUGE
    
    # 标签
    labels: Dict[str, str] = field(default_factory=dict)
    
    # 时间
    timestamp: float = field(default_factory=time.time)
    
    # 描述
    description: str = ""
    unit: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "labels": self.labels,
            "timestamp": self.timestamp,
            "unit": self.unit,
        }


@dataclass
class HealthCheck:
    """健康检查"""
    component: str
    component_type: ComponentType = ComponentType.API
    
    # 状态
    status: HealthStatus = HealthStatus.UNKNOWN
    
    # 详情
    message: str = ""
    details: Dict = field(default_factory=dict)
    
    # 响应时间
    response_time_ms: float = 0
    
    # 时间
    checked_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "component": self.component,
            "type": self.component_type.value,
            "status": self.status.value,
            "message": self.message,
            "response_time_ms": round(self.response_time_ms, 2),
            "checked_at": self.checked_at,
        }


@dataclass
class Alert:
    """告警"""
    alert_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 告警信息
    name: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.ACTIVE
    
    # 内容
    message: str = ""
    description: str = ""
    
    # 来源
    component: str = ""
    metric_name: str = ""
    metric_value: float = 0
    threshold: float = 0
    
    # 时间
    fired_at: float = field(default_factory=time.time)
    acknowledged_at: float = 0
    resolved_at: float = 0
    
    # 通知
    notified: bool = False
    notification_channels: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "component": self.component,
            "fired_at": self.fired_at,
        }


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    
    # 规则
    name: str = ""
    metric_name: str = ""
    condition: str = ">"              # >, <, >=, <=, ==, !=
    threshold: float = 0
    
    # 告警配置
    severity: AlertSeverity = AlertSeverity.WARNING
    
    # 持续时间
    for_duration_seconds: int = 60     # 持续多久触发
    
    # 状态
    enabled: bool = True
    last_triggered: float = 0
    
    # 通知
    notification_channels: List[str] = field(default_factory=list)


@dataclass
class LogEntry:
    """日志条目"""
    log_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 日志信息
    level: str = "info"                # debug, info, warning, error, critical
    message: str = ""
    
    # 来源
    component: str = ""
    source: str = ""
    
    # 上下文
    context: Dict = field(default_factory=dict)
    
    # 时间
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "log_id": self.log_id,
            "level": self.level,
            "message": self.message,
            "component": self.component,
            "timestamp": self.timestamp,
        }


@dataclass
class DashboardData:
    """仪表盘数据"""
    # 概览
    total_nodes: int = 0
    active_nodes: int = 0
    total_tasks: int = 0
    pending_tasks: int = 0
    
    # 性能
    avg_block_time: float = 0
    tps: float = 0
    avg_latency_ms: float = 0
    
    # 健康
    system_health: HealthStatus = HealthStatus.UNKNOWN
    healthy_components: int = 0
    unhealthy_components: int = 0
    
    # 告警
    active_alerts: int = 0
    critical_alerts: int = 0
    
    # 资源
    cpu_usage: float = 0
    memory_usage: float = 0
    disk_usage: float = 0
    network_in_mbps: float = 0
    network_out_mbps: float = 0
    
    # 时间
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "overview": {
                "total_nodes": self.total_nodes,
                "active_nodes": self.active_nodes,
                "total_tasks": self.total_tasks,
                "pending_tasks": self.pending_tasks,
            },
            "performance": {
                "avg_block_time": round(self.avg_block_time, 2),
                "tps": round(self.tps, 2),
                "avg_latency_ms": round(self.avg_latency_ms, 2),
            },
            "health": {
                "status": self.system_health.value,
                "healthy": self.healthy_components,
                "unhealthy": self.unhealthy_components,
            },
            "alerts": {
                "active": self.active_alerts,
                "critical": self.critical_alerts,
            },
            "resources": {
                "cpu": round(self.cpu_usage, 2),
                "memory": round(self.memory_usage, 2),
                "disk": round(self.disk_usage, 2),
            },
            "updated_at": self.updated_at,
        }


# ============== 指标收集器 ==============

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 指标存储
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.current_values: Dict[str, float] = {}
        
        # 计数器
        self.counters: Dict[str, float] = defaultdict(float)
        
        # 直方图
        self.histograms: Dict[str, List[float]] = defaultdict(list)
    
    def gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """设置瞬时值"""
        with self._lock:
            metric = Metric(
                name=name,
                value=value,
                metric_type=MetricType.GAUGE,
                labels=labels or {},
            )
            self.metrics[name].append(metric)
            self.current_values[name] = value
    
    def counter(self, name: str, value: float = 1, labels: Dict[str, str] = None):
        """增加计数器"""
        with self._lock:
            key = name
            if labels:
                key = f"{name}:{json.dumps(labels, sort_keys=True)}"
            
            self.counters[key] += value
            
            metric = Metric(
                name=name,
                value=self.counters[key],
                metric_type=MetricType.COUNTER,
                labels=labels or {},
            )
            self.metrics[name].append(metric)
            self.current_values[name] = self.counters[key]
    
    def histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """记录直方图值"""
        with self._lock:
            self.histograms[name].append(value)
            
            # 保留最近 1000 个值
            if len(self.histograms[name]) > 1000:
                self.histograms[name] = self.histograms[name][-1000:]
            
            # 计算摘要
            values = self.histograms[name]
            summary = {
                "count": len(values),
                "sum": sum(values),
                "avg": statistics.mean(values) if values else 0,
                "p50": self._percentile(values, 50),
                "p95": self._percentile(values, 95),
                "p99": self._percentile(values, 99),
            }
            
            metric = Metric(
                name=name,
                value=summary["avg"],
                metric_type=MetricType.HISTOGRAM,
                labels={**(labels or {}), "summary": json.dumps(summary)},
            )
            self.metrics[name].append(metric)
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not data:
            return 0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)
    
    def get_metric(self, name: str, since: float = 0) -> List[Metric]:
        """获取指标历史"""
        with self._lock:
            metrics = list(self.metrics.get(name, []))
            if since > 0:
                metrics = [m for m in metrics if m.timestamp >= since]
            return metrics
    
    def get_current(self, name: str) -> Optional[float]:
        """获取当前值"""
        with self._lock:
            return self.current_values.get(name)
    
    def get_all_current(self) -> Dict[str, float]:
        """获取所有当前值"""
        with self._lock:
            return dict(self.current_values)


# ============== 健康检查器 ==============

class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 检查函数
        self.checks: Dict[str, Callable] = {}
        
        # 最近检查结果
        self.last_checks: Dict[str, HealthCheck] = {}
        
        # 历史
        self.check_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
    
    def register_check(
        self,
        component: str,
        check_func: Callable,
        component_type: ComponentType = ComponentType.API,
    ):
        """注册健康检查"""
        self.checks[component] = {
            "func": check_func,
            "type": component_type,
        }
    
    def run_check(self, component: str) -> HealthCheck:
        """运行健康检查"""
        with self._lock:
            if component not in self.checks:
                return HealthCheck(
                    component=component,
                    status=HealthStatus.UNKNOWN,
                    message="Component not registered",
                )
            
            check_info = self.checks[component]
            check = HealthCheck(
                component=component,
                component_type=check_info["type"],
            )
            
            start_time = time.time()
            
            try:
                result = check_info["func"]()
                check.response_time_ms = (time.time() - start_time) * 1000
                
                if isinstance(result, dict):
                    check.status = HealthStatus(result.get("status", "healthy"))
                    check.message = result.get("message", "OK")
                    check.details = result.get("details", {})
                elif isinstance(result, bool):
                    check.status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                    check.message = "OK" if result else "Failed"
                else:
                    check.status = HealthStatus.HEALTHY
                    check.message = "OK"
                    
            except Exception as e:
                check.response_time_ms = (time.time() - start_time) * 1000
                check.status = HealthStatus.UNHEALTHY
                check.message = str(e)
            
            self.last_checks[component] = check
            self.check_history[component].append(check)
            
            return check
    
    def run_all_checks(self) -> Dict[str, HealthCheck]:
        """运行所有健康检查"""
        results = {}
        for component in self.checks:
            results[component] = self.run_check(component)
        return results
    
    def get_overall_health(self) -> HealthStatus:
        """获取整体健康状态"""
        with self._lock:
            if not self.last_checks:
                return HealthStatus.UNKNOWN
            
            statuses = [c.status for c in self.last_checks.values()]
            
            if any(s == HealthStatus.CRITICAL for s in statuses):
                return HealthStatus.CRITICAL
            if any(s == HealthStatus.UNHEALTHY for s in statuses):
                return HealthStatus.UNHEALTHY
            if any(s == HealthStatus.DEGRADED for s in statuses):
                return HealthStatus.DEGRADED
            if all(s == HealthStatus.HEALTHY for s in statuses):
                return HealthStatus.HEALTHY
            
            return HealthStatus.UNKNOWN


# ============== 告警管理器 ==============

class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 告警
        self.alerts: Dict[str, Alert] = {}
        self.rules: Dict[str, AlertRule] = {}
        
        # 告警历史
        self.alert_history: deque = deque(maxlen=10000)
        
        # 通知渠道
        self.notification_handlers: Dict[str, Callable] = {}
        
        # 静默规则
        self.silences: Dict[str, Dict] = {}
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        with self._lock:
            self.rules[rule.rule_id] = rule
    
    def evaluate_rules(self, metrics: Dict[str, float]) -> List[Alert]:
        """评估告警规则"""
        with self._lock:
            new_alerts = []
            
            for rule in self.rules.values():
                if not rule.enabled:
                    continue
                
                if rule.metric_name not in metrics:
                    continue
                
                value = metrics[rule.metric_name]
                triggered = self._evaluate_condition(value, rule.condition, rule.threshold)
                
                if triggered:
                    # 创建告警
                    alert = Alert(
                        name=rule.name,
                        severity=rule.severity,
                        message=f"{rule.metric_name} {rule.condition} {rule.threshold} (current: {value})",
                        metric_name=rule.metric_name,
                        metric_value=value,
                        threshold=rule.threshold,
                        notification_channels=rule.notification_channels,
                    )
                    
                    self.alerts[alert.alert_id] = alert
                    self.alert_history.append(alert)
                    new_alerts.append(alert)
                    
                    rule.last_triggered = time.time()
                    
                    # 发送通知
                    self._send_notifications(alert)
            
            return new_alerts
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """评估条件"""
        if condition == ">":
            return value > threshold
        elif condition == "<":
            return value < threshold
        elif condition == ">=":
            return value >= threshold
        elif condition == "<=":
            return value <= threshold
        elif condition == "==":
            return value == threshold
        elif condition == "!=":
            return value != threshold
        return False
    
    def _send_notifications(self, alert: Alert):
        """发送通知"""
        # 检查静默
        if self._is_silenced(alert):
            return
        
        for channel in alert.notification_channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                try:
                    handler(alert)
                    alert.notified = True
                except Exception:
                    pass
    
    def _is_silenced(self, alert: Alert) -> bool:
        """检查是否静默"""
        for silence in self.silences.values():
            if time.time() < silence.get("expires_at", 0):
                if alert.name == silence.get("alert_name") or silence.get("match_all"):
                    return True
        return False
    
    def acknowledge(self, alert_id: str, by: str = "") -> bool:
        """确认告警"""
        with self._lock:
            alert = self.alerts.get(alert_id)
            if alert:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = time.time()
                return True
            return False
    
    def resolve(self, alert_id: str) -> bool:
        """解决告警"""
        with self._lock:
            alert = self.alerts.get(alert_id)
            if alert:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = time.time()
                return True
            return False
    
    def get_active_alerts(self, severity: AlertSeverity = None) -> List[Alert]:
        """获取活跃告警"""
        with self._lock:
            alerts = [a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE]
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            return sorted(alerts, key=lambda a: a.fired_at, reverse=True)
    
    def add_silence(self, alert_name: str, duration_seconds: int) -> str:
        """添加静默"""
        silence_id = uuid.uuid4().hex[:8]
        self.silences[silence_id] = {
            "alert_name": alert_name,
            "expires_at": time.time() + duration_seconds,
        }
        return silence_id


# ============== 主网监控管理器 ==============

class MainnetMonitor:
    """主网监控管理器"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.health_checker = HealthChecker()
        self.alert_manager = AlertManager()
        
        # 日志
        self.logs: deque = deque(maxlen=100000)
        
        # 仪表盘数据
        self.dashboard = DashboardData()
        
        # 监控间隔
        self.monitor_interval = 10  # 秒
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 初始化默认健康检查和告警规则
        self._init_default_checks()
        self._init_default_rules()
    
    def _init_default_checks(self):
        """初始化默认健康检查"""
        # API 健康检查
        self.health_checker.register_check(
            "api",
            lambda: {"status": "healthy", "message": "API responding"},
            ComponentType.API,
        )
        
        # 区块链健康检查
        self.health_checker.register_check(
            "blockchain",
            lambda: {"status": "healthy", "message": "Chain synced"},
            ComponentType.BLOCKCHAIN,
        )
        
        # 网络健康检查
        self.health_checker.register_check(
            "network",
            lambda: {"status": "healthy", "message": "Peers connected"},
            ComponentType.NETWORK,
        )
    
    def _init_default_rules(self):
        """初始化默认告警规则"""
        # CPU 使用率告警
        self.alert_manager.add_rule(AlertRule(
            name="High CPU Usage",
            metric_name="cpu_usage",
            condition=">",
            threshold=90,
            severity=AlertSeverity.WARNING,
        ))
        
        # 内存使用率告警
        self.alert_manager.add_rule(AlertRule(
            name="High Memory Usage",
            metric_name="memory_usage",
            condition=">",
            threshold=85,
            severity=AlertSeverity.WARNING,
        ))
        
        # 磁盘使用率告警
        self.alert_manager.add_rule(AlertRule(
            name="High Disk Usage",
            metric_name="disk_usage",
            condition=">",
            threshold=80,
            severity=AlertSeverity.ERROR,
        ))
        
        # 延迟告警
        self.alert_manager.add_rule(AlertRule(
            name="High Latency",
            metric_name="avg_latency_ms",
            condition=">",
            threshold=1000,
            severity=AlertSeverity.WARNING,
        ))
    
    def record_metric(self, name: str, value: float, metric_type: str = "gauge", labels: Dict = None):
        """记录指标"""
        if metric_type == "gauge":
            self.metrics_collector.gauge(name, value, labels)
        elif metric_type == "counter":
            self.metrics_collector.counter(name, value, labels)
        elif metric_type == "histogram":
            self.metrics_collector.histogram(name, value, labels)
        
        # 评估告警
        self.alert_manager.evaluate_rules({name: value})
    
    def log(self, level: str, message: str, component: str = "", context: Dict = None):
        """记录日志"""
        entry = LogEntry(
            level=level,
            message=message,
            component=component,
            context=context or {},
        )
        self.logs.append(entry)
    
    def get_logs(
        self,
        level: str = None,
        component: str = None,
        since: float = 0,
        limit: int = 100,
    ) -> List[LogEntry]:
        """获取日志"""
        logs = list(self.logs)
        
        if level:
            logs = [l for l in logs if l.level == level]
        if component:
            logs = [l for l in logs if l.component == component]
        if since > 0:
            logs = [l for l in logs if l.timestamp >= since]
        
        return logs[-limit:]
    
    def update_dashboard(self):
        """更新仪表盘"""
        # 运行健康检查
        health_results = self.health_checker.run_all_checks()
        
        # 更新健康状态
        self.dashboard.system_health = self.health_checker.get_overall_health()
        self.dashboard.healthy_components = sum(
            1 for c in health_results.values() if c.status == HealthStatus.HEALTHY
        )
        self.dashboard.unhealthy_components = sum(
            1 for c in health_results.values() if c.status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]
        )
        
        # 更新告警
        active_alerts = self.alert_manager.get_active_alerts()
        self.dashboard.active_alerts = len(active_alerts)
        self.dashboard.critical_alerts = sum(
            1 for a in active_alerts if a.severity == AlertSeverity.CRITICAL
        )
        
        # 更新资源指标
        self.dashboard.cpu_usage = self.metrics_collector.get_current("cpu_usage") or 0
        self.dashboard.memory_usage = self.metrics_collector.get_current("memory_usage") or 0
        self.dashboard.disk_usage = self.metrics_collector.get_current("disk_usage") or 0
        
        # 更新性能指标
        self.dashboard.avg_latency_ms = self.metrics_collector.get_current("avg_latency_ms") or 0
        self.dashboard.tps = self.metrics_collector.get_current("tps") or 0
        
        self.dashboard.updated_at = time.time()
    
    def get_dashboard(self) -> Dict:
        """获取仪表盘数据"""
        self.update_dashboard()
        return self.dashboard.to_dict()
    
    def get_health_status(self) -> Dict:
        """获取健康状态"""
        checks = self.health_checker.run_all_checks()
        return {
            "overall": self.health_checker.get_overall_health().value,
            "components": {k: v.to_dict() for k, v in checks.items()},
        }
    
    def get_alerts(self, severity: str = None, status: str = None) -> List[Dict]:
        """获取告警"""
        alerts = list(self.alert_manager.alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity.value == severity]
        if status:
            alerts = [a for a in alerts if a.status.value == status]
        
        return [a.to_dict() for a in sorted(alerts, key=lambda a: a.fired_at, reverse=True)]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        return self.alert_manager.acknowledge(alert_id)
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        return self.alert_manager.resolve(alert_id)
    
    def get_metrics(self, metric_names: List[str] = None, since: float = 0) -> Dict:
        """获取指标"""
        if metric_names:
            return {
                name: [m.to_dict() for m in self.metrics_collector.get_metric(name, since)]
                for name in metric_names
            }
        else:
            return {
                name: value
                for name, value in self.metrics_collector.get_all_current().items()
            }
    
    def add_health_check(self, component: str, check_func: Callable, component_type: str = "api"):
        """添加健康检查"""
        self.health_checker.register_check(
            component,
            check_func,
            ComponentType(component_type),
        )
    
    def add_alert_rule(
        self,
        name: str,
        metric_name: str,
        condition: str,
        threshold: float,
        severity: str = "warning",
    ) -> str:
        """添加告警规则"""
        rule = AlertRule(
            name=name,
            metric_name=metric_name,
            condition=condition,
            threshold=threshold,
            severity=AlertSeverity(severity),
        )
        self.alert_manager.add_rule(rule)
        return rule.rule_id
    
    def get_monitor_stats(self) -> Dict:
        """获取监控统计"""
        return {
            "metrics_count": len(self.metrics_collector.current_values),
            "health_checks": len(self.health_checker.checks),
            "alert_rules": len(self.alert_manager.rules),
            "active_alerts": len(self.alert_manager.get_active_alerts()),
            "total_logs": len(self.logs),
        }


# ============== 全局实例 ==============

_mainnet_monitor: Optional[MainnetMonitor] = None


def get_mainnet_monitor() -> MainnetMonitor:
    """获取主网监控单例"""
    global _mainnet_monitor
    if _mainnet_monitor is None:
        _mainnet_monitor = MainnetMonitor()
    return _mainnet_monitor
