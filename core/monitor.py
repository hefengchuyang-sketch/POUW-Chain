# -*- coding: utf-8 -*-
"""
监控告警模块

提供系统级监控和异常告警功能。

特性:
- 异常交易检测（大额、高频）
- 双花尝试告警
- 矿工异常行为检测
- 系统性能指标
- 可配置的告警规则
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
from datetime import datetime
import json
from pathlib import Path


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("monitor")


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertType(Enum):
    """告警类型"""
    LARGE_TRANSACTION = "large_transaction"
    HIGH_FREQUENCY = "high_frequency"
    DOUBLE_SPEND_ATTEMPT = "double_spend_attempt"
    SIGNATURE_FAILURE = "signature_failure"
    NONCE_VIOLATION = "nonce_violation"
    MINER_ANOMALY = "miner_anomaly"
    SYSTEM_OVERLOAD = "system_overload"
    NETWORK_ISSUE = "network_issue"
    FORK_DETECTED = "fork_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


@dataclass
class Alert:
    """告警对象"""
    alert_id: str
    alert_type: AlertType
    level: AlertLevel
    message: str
    details: Dict[str, Any]
    timestamp: float
    source: str = ""
    acknowledged: bool = False
    resolved: bool = False
    
    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "source": self.source,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved
        }


@dataclass
class MonitorConfig:
    """监控配置"""
    # 大额交易阈值
    large_transaction_threshold: float = 1000.0
    
    # 高频交易阈值（每分钟）
    high_frequency_threshold: int = 20
    
    # 双花检测窗口（秒）
    double_spend_window: int = 60
    
    # 签名失败阈值（触发告警）
    signature_failure_threshold: int = 5
    
    # 系统负载阈值
    cpu_threshold: float = 90.0
    memory_threshold: float = 90.0
    
    # 告警保留时间（秒）
    alert_retention: int = 86400 * 7  # 7 天
    
    # 告警回调
    alert_callbacks: List[Callable] = field(default_factory=list)


class TransactionMonitor:
    """交易监控器"""
    
    def __init__(self, config: MonitorConfig = None):
        self.config = config or MonitorConfig()
        
        # 交易计数
        self.tx_counts: Dict[str, list] = defaultdict(list)  # address -> [(timestamp, txid)]
        
        # 签名失败计数
        self.signature_failures: Dict[str, int] = defaultdict(int)
        
        # nonce 违规记录
        self.nonce_violations: Dict[str, list] = defaultdict(list)
        
        self._lock = threading.Lock()
    
    def on_transaction(self, tx_data: dict) -> Optional[Alert]:
        """
        监控新交易
        
        Args:
            tx_data: 交易数据 {txid, from_address, to_address, amount, ...}
        
        Returns:
            Alert 如果触发告警，否则 None
        """
        from_addr = tx_data.get("from_address", "")
        amount = tx_data.get("amount", 0)
        txid = tx_data.get("txid", "")
        now = time.time()
        
        # 大额交易检测
        if amount >= self.config.large_transaction_threshold:
            return Alert(
                alert_id=f"alert_{txid[:16]}",
                alert_type=AlertType.LARGE_TRANSACTION,
                level=AlertLevel.WARNING,
                message=f"Large transaction detected: {amount} MAIN",
                details={
                    "txid": txid,
                    "from": from_addr,
                    "to": tx_data.get("to_address", ""),
                    "amount": amount
                },
                timestamp=now,
                source="transaction_monitor"
            )
        
        # 高频交易检测
        with self._lock:
            # 清理旧记录
            cutoff = now - 60
            self.tx_counts[from_addr] = [
                (t, tid) for t, tid in self.tx_counts[from_addr] if t > cutoff
            ]
            self.tx_counts[from_addr].append((now, txid))
            
            if len(self.tx_counts[from_addr]) > self.config.high_frequency_threshold:
                return Alert(
                    alert_id=f"alert_hf_{from_addr[:16]}_{int(now)}",
                    alert_type=AlertType.HIGH_FREQUENCY,
                    level=AlertLevel.WARNING,
                    message=f"High frequency transactions from {from_addr[:20]}...",
                    details={
                        "address": from_addr,
                        "tx_count": len(self.tx_counts[from_addr]),
                        "threshold": self.config.high_frequency_threshold,
                        "window": "1 minute"
                    },
                    timestamp=now,
                    source="transaction_monitor"
                )
        
        return None
    
    def on_signature_failure(self, address: str, txid: str) -> Optional[Alert]:
        """
        记录签名验证失败
        
        Returns:
            Alert 如果达到阈值
        """
        with self._lock:
            self.signature_failures[address] += 1
            
            if self.signature_failures[address] >= self.config.signature_failure_threshold:
                self.signature_failures[address] = 0  # 重置
                return Alert(
                    alert_id=f"alert_sig_{address[:16]}_{int(time.time())}",
                    alert_type=AlertType.SIGNATURE_FAILURE,
                    level=AlertLevel.CRITICAL,
                    message=f"Multiple signature failures from {address[:20]}...",
                    details={
                        "address": address,
                        "last_txid": txid,
                        "failure_count": self.config.signature_failure_threshold
                    },
                    timestamp=time.time(),
                    source="transaction_monitor"
                )
        
        return None
    
    def on_nonce_violation(self, address: str, expected: int, received: int, txid: str) -> Alert:
        """
        记录 Nonce 违规（可能的双花尝试）
        """
        now = time.time()
        
        with self._lock:
            self.nonce_violations[address].append({
                "timestamp": now,
                "expected": expected,
                "received": received,
                "txid": txid
            })
            # 每个地址最多保留 100 条违规记录，防止无界增长
            if len(self.nonce_violations[address]) > 100:
                self.nonce_violations[address] = self.nonce_violations[address][-100:]
        
        # 判断是否可能是双花
        level = AlertLevel.WARNING
        if received < expected:
            level = AlertLevel.CRITICAL  # 尝试使用旧 nonce，可能是双花
        
        return Alert(
            alert_id=f"alert_nonce_{txid[:16]}",
            alert_type=AlertType.NONCE_VIOLATION if received > expected else AlertType.DOUBLE_SPEND_ATTEMPT,
            level=level,
            message=f"Nonce violation: expected {expected}, got {received}",
            details={
                "address": address,
                "expected_nonce": expected,
                "received_nonce": received,
                "txid": txid,
                "possible_double_spend": received < expected
            },
            timestamp=now,
            source="transaction_monitor"
        )


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, config: MonitorConfig = None):
        self.config = config or MonitorConfig()
        self.metrics: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
    
    def record_metric(self, name: str, value: float):
        """记录指标"""
        now = time.time()
        with self._lock:
            # 保留最近 1 小时的数据
            cutoff = now - 3600
            self.metrics[name] = [
                (t, v) for t, v in self.metrics[name] if t > cutoff
            ]
            self.metrics[name].append((now, value))
    
    def get_metric_avg(self, name: str, window: int = 60) -> Optional[float]:
        """获取指标平均值"""
        now = time.time()
        cutoff = now - window
        
        with self._lock:
            values = [v for t, v in self.metrics[name] if t > cutoff]
            if values:
                return sum(values) / len(values)
        return None
    
    def check_system_health(self) -> List[Alert]:
        """
        检查系统健康状态
        
        Returns:
            告警列表
        """
        alerts = []
        now = time.time()
        
        # 检查 CPU
        cpu_avg = self.get_metric_avg("cpu_percent")
        if cpu_avg and cpu_avg > self.config.cpu_threshold:
            alerts.append(Alert(
                alert_id=f"alert_cpu_{int(now)}",
                alert_type=AlertType.SYSTEM_OVERLOAD,
                level=AlertLevel.WARNING,
                message=f"High CPU usage: {cpu_avg:.1f}%",
                details={"cpu_percent": cpu_avg, "threshold": self.config.cpu_threshold},
                timestamp=now,
                source="system_monitor"
            ))
        
        # 检查内存
        memory_avg = self.get_metric_avg("memory_percent")
        if memory_avg and memory_avg > self.config.memory_threshold:
            alerts.append(Alert(
                alert_id=f"alert_mem_{int(now)}",
                alert_type=AlertType.SYSTEM_OVERLOAD,
                level=AlertLevel.WARNING,
                message=f"High memory usage: {memory_avg:.1f}%",
                details={"memory_percent": memory_avg, "threshold": self.config.memory_threshold},
                timestamp=now,
                source="system_monitor"
            ))
        
        return alerts
    
    def get_system_stats(self) -> dict:
        """获取系统统计"""
        return {
            "cpu_avg_1min": self.get_metric_avg("cpu_percent", 60),
            "memory_avg_1min": self.get_metric_avg("memory_percent", 60),
            "tx_rate_1min": self.get_metric_avg("tx_rate", 60),
            "block_rate_1min": self.get_metric_avg("block_rate", 60),
        }


class AlertManager:
    """告警管理器"""
    
    def __init__(self, config: MonitorConfig = None, persist_path: str = "data/alerts.json"):
        self.config = config or MonitorConfig()
        self.persist_path = Path(persist_path)
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.alerts: List[Alert] = []
        self.callbacks: List[Callable[[Alert], None]] = []
        
        self._lock = threading.Lock()
        
        # 加载历史告警
        self._load_alerts()
    
    def add_callback(self, callback: Callable[[Alert], None]):
        """添加告警回调"""
        self.callbacks.append(callback)
    
    def emit(self, alert: Alert):
        """发送告警"""
        with self._lock:
            self.alerts.append(alert)
        
        # 记录日志
        log_func = logger.info
        if alert.level == AlertLevel.WARNING:
            log_func = logger.warning
        elif alert.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY):
            log_func = logger.critical
        
        log_func(f"[{alert.alert_type.value}] {alert.message}")
        
        # 调用回调
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        # 持久化
        self._save_alerts()
    
    def get_alerts(
        self,
        level: AlertLevel = None,
        alert_type: AlertType = None,
        since: float = None,
        limit: int = 100,
        unresolved_only: bool = False
    ) -> List[Alert]:
        """
        获取告警列表
        
        Args:
            level: 过滤级别
            alert_type: 过滤类型
            since: 起始时间
            limit: 返回数量限制
            unresolved_only: 仅返回未解决的
        
        Returns:
            告警列表
        """
        with self._lock:
            result = self.alerts.copy()
        
        if level:
            result = [a for a in result if a.level == level]
        
        if alert_type:
            result = [a for a in result if a.alert_type == alert_type]
        
        if since:
            result = [a for a in result if a.timestamp >= since]
        
        if unresolved_only:
            result = [a for a in result if not a.resolved]
        
        # 按时间倒序
        result.sort(key=lambda a: a.timestamp, reverse=True)
        
        return result[:limit]
    
    def acknowledge(self, alert_id: str) -> bool:
        """确认告警"""
        with self._lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    self._save_alerts()
                    return True
        return False
    
    def resolve(self, alert_id: str) -> bool:
        """解决告警"""
        with self._lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    self._save_alerts()
                    return True
        return False
    
    def cleanup(self):
        """清理过期告警"""
        cutoff = time.time() - self.config.alert_retention
        with self._lock:
            self.alerts = [a for a in self.alerts if a.timestamp > cutoff]
            self._save_alerts()
    
    def get_summary(self) -> dict:
        """获取告警摘要"""
        with self._lock:
            total = len(self.alerts)
            by_level = defaultdict(int)
            by_type = defaultdict(int)
            unresolved = 0
            
            for alert in self.alerts:
                by_level[alert.level.value] += 1
                by_type[alert.alert_type.value] += 1
                if not alert.resolved:
                    unresolved += 1
        
        return {
            "total": total,
            "unresolved": unresolved,
            "by_level": dict(by_level),
            "by_type": dict(by_type)
        }
    
    def _save_alerts(self):
        """保存告警到文件"""
        try:
            data = [a.to_dict() for a in self.alerts[-1000:]]  # 保留最近 1000 条
            with open(self.persist_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alerts: {e}")
    
    def _load_alerts(self):
        """从文件加载告警"""
        if not self.persist_path.exists():
            return
        
        try:
            with open(self.persist_path, 'r') as f:
                data = json.load(f)
            
            for item in data:
                alert = Alert(
                    alert_id=item["alert_id"],
                    alert_type=AlertType(item["alert_type"]),
                    level=AlertLevel(item["level"]),
                    message=item["message"],
                    details=item["details"],
                    timestamp=item["timestamp"],
                    source=item.get("source", ""),
                    acknowledged=item.get("acknowledged", False),
                    resolved=item.get("resolved", False)
                )
                self.alerts.append(alert)
        except Exception as e:
            logger.error(f"Failed to load alerts: {e}")


# 全局监控器
_tx_monitor: Optional[TransactionMonitor] = None
_sys_monitor: Optional[SystemMonitor] = None
_alert_manager: Optional[AlertManager] = None


def get_transaction_monitor() -> TransactionMonitor:
    """获取交易监控器"""
    global _tx_monitor
    if _tx_monitor is None:
        _tx_monitor = TransactionMonitor()
    return _tx_monitor


def get_system_monitor() -> SystemMonitor:
    """获取系统监控器"""
    global _sys_monitor
    if _sys_monitor is None:
        _sys_monitor = SystemMonitor()
    return _sys_monitor


def get_alert_manager() -> AlertManager:
    """获取告警管理器"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def emit_alert(alert: Alert):
    """发送告警"""
    get_alert_manager().emit(alert)


# 便捷函数
def monitor_transaction(tx_data: dict):
    """监控交易（便捷函数）"""
    tx_mon = get_transaction_monitor()
    alert = tx_mon.on_transaction(tx_data)
    if alert:
        emit_alert(alert)


def record_signature_failure(address: str, txid: str):
    """记录签名失败（便捷函数）"""
    tx_mon = get_transaction_monitor()
    alert = tx_mon.on_signature_failure(address, txid)
    if alert:
        emit_alert(alert)


def record_nonce_violation(address: str, expected: int, received: int, txid: str):
    """记录 Nonce 违规（便捷函数）"""
    tx_mon = get_transaction_monitor()
    alert = tx_mon.on_nonce_violation(address, expected, received, txid)
    emit_alert(alert)


# 测试
if __name__ == "__main__":
    print("=" * 60)
    print("监控告警系统测试")
    print("=" * 60)
    
    # 配置
    config = MonitorConfig(
        large_transaction_threshold=100,
        high_frequency_threshold=5
    )
    
    tx_monitor = TransactionMonitor(config)
    alert_manager = AlertManager(config)
    
    # 添加回调
    alert_manager.add_callback(lambda a: print(f"   📢 回调: {a.message}"))
    
    # 测试大额交易
    print("\n1. 大额交易测试:")
    alert = tx_monitor.on_transaction({
        "txid": "tx_large_001",
        "from_address": "MAIN_ALICE123",
        "to_address": "MAIN_BOB456",
        "amount": 500
    })
    if alert:
        alert_manager.emit(alert)
        print(f"   ✅ 触发告警: {alert.message}")
    
    # 测试高频交易
    print("\n2. 高频交易测试:")
    for i in range(7):
        alert = tx_monitor.on_transaction({
            "txid": f"tx_hf_{i}",
            "from_address": "MAIN_SPAMMER",
            "to_address": "MAIN_TARGET",
            "amount": 1
        })
        if alert:
            alert_manager.emit(alert)
            print(f"   ✅ 第 {i+1} 笔触发告警: {alert.message}")
    
    # 测试 Nonce 违规
    print("\n3. Nonce 违规测试:")
    alert = tx_monitor.on_nonce_violation("MAIN_ATTACKER", 10, 5, "tx_double_spend")
    alert_manager.emit(alert)
    print(f"   ✅ 触发告警: {alert.message}")
    
    # 查看摘要
    print("\n4. 告警摘要:")
    summary = alert_manager.get_summary()
    for k, v in summary.items():
        print(f"   {k}: {v}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
