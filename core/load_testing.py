"""
load_testing.py - 高并发负载测试框架

Phase 10 功能：
1. 并发用户模拟
2. 场景定义与执行
3. 性能指标收集
4. 压力测试
5. 报告生成
6. 瓶颈识别
"""

import time
import uuid
import threading
import statistics
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import json


# ============== 枚举类型 ==============

class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LoadPattern(Enum):
    """负载模式"""
    CONSTANT = "constant"              # 恒定负载
    RAMP_UP = "ramp_up"                # 逐渐增加
    RAMP_DOWN = "ramp_down"            # 逐渐减少
    SPIKE = "spike"                    # 突发峰值
    STEP = "step"                      # 阶梯式
    WAVE = "wave"                      # 波浪式


class MetricType(Enum):
    """指标类型"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    CONCURRENCY = "concurrency"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"


# ============== 数据结构 ==============

@dataclass
class RequestResult:
    """请求结果"""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 请求信息
    scenario_name: str = ""
    action_name: str = ""
    
    # 结果
    success: bool = True
    error_message: str = ""
    response_data: Any = None
    
    # 时间
    start_time: float = 0
    end_time: float = 0
    latency_ms: float = 0
    
    # 用户
    user_id: str = ""


@dataclass
class TestScenario:
    """测试场景"""
    name: str
    description: str = ""
    
    # 动作序列
    actions: List[Dict] = field(default_factory=list)
    
    # 配置
    think_time_ms: int = 1000          # 思考时间
    randomize_think_time: bool = True
    
    # 权重（用于混合场景）
    weight: float = 1.0
    
    def add_action(
        self,
        name: str,
        func: Callable,
        params: Dict = None,
        assertions: List[Callable] = None,
    ):
        """添加动作"""
        self.actions.append({
            "name": name,
            "func": func,
            "params": params or {},
            "assertions": assertions or [],
        })


@dataclass
class LoadProfile:
    """负载配置"""
    # 并发配置
    initial_users: int = 10
    max_users: int = 100
    spawn_rate: float = 10             # 每秒增加用户数
    
    # 时间配置
    duration_seconds: int = 60
    ramp_up_seconds: int = 10
    ramp_down_seconds: int = 10
    
    # 负载模式
    pattern: LoadPattern = LoadPattern.CONSTANT
    
    # 阈值
    target_rps: float = 0              # 目标 RPS
    max_latency_ms: float = 1000       # 最大延迟
    max_error_rate: float = 0.01       # 最大错误率


@dataclass
class PerformanceMetrics:
    """性能指标"""
    # 延迟（毫秒）
    latency_min: float = 0
    latency_max: float = 0
    latency_avg: float = 0
    latency_p50: float = 0
    latency_p90: float = 0
    latency_p95: float = 0
    latency_p99: float = 0
    latency_std: float = 0
    
    # 吞吐量
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    requests_per_second: float = 0
    
    # 错误率
    error_rate: float = 0
    
    # 并发
    peak_concurrency: int = 0
    avg_concurrency: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "latency": {
                "min": round(self.latency_min, 2),
                "max": round(self.latency_max, 2),
                "avg": round(self.latency_avg, 2),
                "p50": round(self.latency_p50, 2),
                "p90": round(self.latency_p90, 2),
                "p95": round(self.latency_p95, 2),
                "p99": round(self.latency_p99, 2),
            },
            "throughput": {
                "total_requests": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "rps": round(self.requests_per_second, 2),
            },
            "error_rate": round(self.error_rate * 100, 2),
            "concurrency": {
                "peak": self.peak_concurrency,
                "avg": round(self.avg_concurrency, 2),
            },
        }


@dataclass
class TestReport:
    """测试报告"""
    test_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 基本信息
    name: str = ""
    description: str = ""
    
    # 配置
    load_profile: LoadProfile = field(default_factory=LoadProfile)
    scenarios: List[str] = field(default_factory=list)
    
    # 状态
    status: TestStatus = TestStatus.PENDING
    
    # 时间
    started_at: float = 0
    completed_at: float = 0
    duration_seconds: float = 0
    
    # 指标
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    
    # 详细结果
    results_by_scenario: Dict[str, PerformanceMetrics] = field(default_factory=dict)
    results_by_action: Dict[str, PerformanceMetrics] = field(default_factory=dict)
    
    # 时间序列数据
    timeseries: List[Dict] = field(default_factory=list)
    
    # 瓶颈分析
    bottlenecks: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "status": self.status.value,
            "duration_seconds": round(self.duration_seconds, 2),
            "metrics": self.metrics.to_dict(),
            "bottlenecks": self.bottlenecks,
            "recommendations": self.recommendations,
        }


# ============== 虚拟用户 ==============

class VirtualUser:
    """虚拟用户"""
    
    def __init__(self, user_id: str, scenarios: List[TestScenario]):
        self.user_id = user_id
        self.scenarios = scenarios
        self.active = True
        self.current_scenario: Optional[TestScenario] = None
        
        # 统计
        self.requests_sent = 0
        self.requests_successful = 0
        self.requests_failed = 0
        
        # 结果收集
        self.results: List[RequestResult] = []
    
    def run_iteration(self) -> List[RequestResult]:
        """运行一次迭代"""
        if not self.active or not self.scenarios:
            return []
        
        # 选择场景（加权随机）
        total_weight = sum(s.weight for s in self.scenarios)
        r = random.random() * total_weight
        cumulative = 0
        
        for scenario in self.scenarios:
            cumulative += scenario.weight
            if r <= cumulative:
                self.current_scenario = scenario
                break
        
        if not self.current_scenario:
            self.current_scenario = self.scenarios[0]
        
        results = []
        
        # 执行场景中的所有动作
        for action in self.current_scenario.actions:
            if not self.active:
                break
            
            result = self._execute_action(action)
            results.append(result)
            self.results.append(result)
            
            # 思考时间
            if self.current_scenario.randomize_think_time:
                think_time = random.uniform(
                    self.current_scenario.think_time_ms * 0.5,
                    self.current_scenario.think_time_ms * 1.5
                )
            else:
                think_time = self.current_scenario.think_time_ms
            
            time.sleep(think_time / 1000)
        
        return results
    
    def _execute_action(self, action: Dict) -> RequestResult:
        """执行单个动作"""
        result = RequestResult(
            scenario_name=self.current_scenario.name,
            action_name=action["name"],
            user_id=self.user_id,
            start_time=time.time(),
        )
        
        try:
            # 执行函数
            func = action["func"]
            params = action["params"]
            response = func(**params)
            
            result.response_data = response
            result.success = True
            self.requests_successful += 1
            
            # 执行断言
            for assertion in action.get("assertions", []):
                if not assertion(response):
                    result.success = False
                    result.error_message = "Assertion failed"
                    self.requests_failed += 1
                    self.requests_successful -= 1
                    break
            
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            self.requests_failed += 1
        
        result.end_time = time.time()
        result.latency_ms = (result.end_time - result.start_time) * 1000
        self.requests_sent += 1
        
        return result
    
    def stop(self):
        """停止用户"""
        self.active = False


# ============== 负载测试引擎 ==============

class LoadTestEngine:
    """负载测试引擎"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 场景
        self.scenarios: Dict[str, TestScenario] = {}
        
        # 测试
        self.tests: Dict[str, TestReport] = {}
        self.current_test: Optional[TestReport] = None
        
        # 用户
        self.users: Dict[str, VirtualUser] = {}
        
        # 执行控制
        self.running = False
        self.executor: Optional[ThreadPoolExecutor] = None
        
        # 实时指标
        self.realtime_results: deque = deque(maxlen=100000)
        self.concurrency_samples: List[int] = []
    
    def register_scenario(self, scenario: TestScenario):
        """注册测试场景"""
        with self._lock:
            self.scenarios[scenario.name] = scenario
    
    def create_scenario(
        self,
        name: str,
        description: str = "",
        think_time_ms: int = 1000,
    ) -> TestScenario:
        """创建测试场景"""
        scenario = TestScenario(
            name=name,
            description=description,
            think_time_ms=think_time_ms,
        )
        self.register_scenario(scenario)
        return scenario
    
    def run_test(
        self,
        name: str,
        scenario_names: List[str],
        load_profile: LoadProfile,
    ) -> TestReport:
        """运行负载测试"""
        with self._lock:
            if self.running:
                raise RuntimeError("A test is already running")
            
            # 验证场景
            scenarios = []
            for sn in scenario_names:
                if sn not in self.scenarios:
                    raise ValueError(f"Scenario {sn} not found")
                scenarios.append(self.scenarios[sn])
            
            # 创建测试报告
            report = TestReport(
                name=name,
                load_profile=load_profile,
                scenarios=scenario_names,
                status=TestStatus.RUNNING,
                started_at=time.time(),
            )
            
            self.tests[report.test_id] = report
            self.current_test = report
            self.running = True
            self.realtime_results.clear()
            self.concurrency_samples.clear()
        
        try:
            # 执行测试
            self._execute_test(report, scenarios, load_profile)
            report.status = TestStatus.COMPLETED
        except Exception as e:
            report.status = TestStatus.FAILED
            report.bottlenecks.append({"type": "error", "message": str(e)})
        finally:
            with self._lock:
                report.completed_at = time.time()
                report.duration_seconds = report.completed_at - report.started_at
                self.running = False
                self._calculate_metrics(report)
                self._analyze_bottlenecks(report)
        
        return report
    
    def _execute_test(
        self,
        report: TestReport,
        scenarios: List[TestScenario],
        profile: LoadProfile,
    ):
        """执行测试"""
        end_time = time.time() + profile.duration_seconds
        
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=profile.max_users + 10)
        
        # 用户管理
        active_users = []
        user_futures = {}
        
        try:
            while time.time() < end_time and self.running:
                current_time = time.time() - report.started_at
                
                # 计算目标用户数
                target_users = self._calculate_target_users(
                    current_time,
                    profile,
                )
                
                # 调整用户数
                while len(active_users) < target_users:
                    user = VirtualUser(
                        user_id=f"user_{uuid.uuid4().hex[:8]}",
                        scenarios=scenarios,
                    )
                    self.users[user.user_id] = user
                    active_users.append(user)
                    
                    # 提交用户任务
                    future = self.executor.submit(self._run_user, user, end_time)
                    user_futures[user.user_id] = future
                
                while len(active_users) > target_users:
                    user = active_users.pop()
                    user.stop()
                
                # 记录并发数
                self.concurrency_samples.append(len(active_users))
                
                # 记录时间序列数据
                if len(self.realtime_results) > 0:
                    recent = list(self.realtime_results)[-100:]
                    latencies = [r.latency_ms for r in recent]
                    errors = sum(1 for r in recent if not r.success)
                    
                    report.timeseries.append({
                        "timestamp": current_time,
                        "concurrency": len(active_users),
                        "avg_latency": statistics.mean(latencies) if latencies else 0,
                        "error_count": errors,
                    })
                
                time.sleep(0.5)
            
            # 停止所有用户
            for user in active_users:
                user.stop()
            
            # 等待所有任务完成
            for future in user_futures.values():
                try:
                    future.result(timeout=5)
                except Exception:
                    pass
            
        finally:
            if self.executor:
                self.executor.shutdown(wait=False)
    
    def _run_user(self, user: VirtualUser, end_time: float):
        """运行虚拟用户"""
        while user.active and time.time() < end_time:
            results = user.run_iteration()
            with self._lock:
                for r in results:
                    self.realtime_results.append(r)
    
    def _calculate_target_users(self, current_time: float, profile: LoadProfile) -> int:
        """计算目标用户数"""
        if profile.pattern == LoadPattern.CONSTANT:
            if current_time < profile.ramp_up_seconds:
                # 爬坡阶段
                progress = current_time / profile.ramp_up_seconds
                return int(profile.initial_users + (profile.max_users - profile.initial_users) * progress)
            elif current_time > profile.duration_seconds - profile.ramp_down_seconds:
                # 下降阶段
                remaining = profile.duration_seconds - current_time
                progress = remaining / profile.ramp_down_seconds
                return int(profile.initial_users + (profile.max_users - profile.initial_users) * progress)
            else:
                return profile.max_users
        
        elif profile.pattern == LoadPattern.SPIKE:
            # 中间时刻突发
            mid_point = profile.duration_seconds / 2
            if abs(current_time - mid_point) < 5:
                return profile.max_users
            return profile.initial_users
        
        elif profile.pattern == LoadPattern.STEP:
            # 阶梯式增长
            step_duration = profile.duration_seconds / 5
            step = int(current_time / step_duration)
            step = min(step, 4)
            users_per_step = (profile.max_users - profile.initial_users) / 4
            return int(profile.initial_users + step * users_per_step)
        
        elif profile.pattern == LoadPattern.WAVE:
            # 波浪式
            import math
            amplitude = (profile.max_users - profile.initial_users) / 2
            mid = (profile.max_users + profile.initial_users) / 2
            period = profile.duration_seconds / 3
            return int(mid + amplitude * math.sin(2 * math.pi * current_time / period))
        
        return profile.max_users
    
    def _calculate_metrics(self, report: TestReport):
        """计算性能指标"""
        with self._lock:
            results = list(self.realtime_results)
            
            if not results:
                return
            
            # 延迟计算
            latencies = sorted([r.latency_ms for r in results])
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            
            metrics = report.metrics
            metrics.total_requests = len(results)
            metrics.successful_requests = len(successful)
            metrics.failed_requests = len(failed)
            
            if latencies:
                metrics.latency_min = min(latencies)
                metrics.latency_max = max(latencies)
                metrics.latency_avg = statistics.mean(latencies)
                metrics.latency_std = statistics.stdev(latencies) if len(latencies) > 1 else 0
                
                # 百分位数
                metrics.latency_p50 = self._percentile(latencies, 50)
                metrics.latency_p90 = self._percentile(latencies, 90)
                metrics.latency_p95 = self._percentile(latencies, 95)
                metrics.latency_p99 = self._percentile(latencies, 99)
            
            # 吞吐量
            if report.duration_seconds > 0:
                metrics.requests_per_second = len(results) / report.duration_seconds
            
            # 错误率
            metrics.error_rate = len(failed) / len(results) if results else 0
            
            # 并发
            if self.concurrency_samples:
                metrics.peak_concurrency = max(self.concurrency_samples)
                metrics.avg_concurrency = statistics.mean(self.concurrency_samples)
            
            # 按场景/动作分组
            by_scenario: Dict[str, List[RequestResult]] = defaultdict(list)
            by_action: Dict[str, List[RequestResult]] = defaultdict(list)
            
            for r in results:
                by_scenario[r.scenario_name].append(r)
                by_action[f"{r.scenario_name}.{r.action_name}"].append(r)
            
            for name, res in by_scenario.items():
                report.results_by_scenario[name] = self._calculate_group_metrics(res)
            
            for name, res in by_action.items():
                report.results_by_action[name] = self._calculate_group_metrics(res)
    
    def _calculate_group_metrics(self, results: List[RequestResult]) -> PerformanceMetrics:
        """计算分组指标"""
        metrics = PerformanceMetrics()
        
        if not results:
            return metrics
        
        latencies = sorted([r.latency_ms for r in results])
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        metrics.total_requests = len(results)
        metrics.successful_requests = len(successful)
        metrics.failed_requests = len(failed)
        
        if latencies:
            metrics.latency_min = min(latencies)
            metrics.latency_max = max(latencies)
            metrics.latency_avg = statistics.mean(latencies)
            metrics.latency_p95 = self._percentile(latencies, 95)
        
        metrics.error_rate = len(failed) / len(results)
        
        return metrics
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not data:
            return 0
        k = (len(data) - 1) * percentile / 100
        f = int(k)
        c = f + 1
        if c >= len(data):
            return data[-1]
        return data[f] + (data[c] - data[f]) * (k - f)
    
    def _analyze_bottlenecks(self, report: TestReport):
        """分析瓶颈"""
        metrics = report.metrics
        profile = report.load_profile
        
        # 延迟过高
        if metrics.latency_p95 > profile.max_latency_ms:
            report.bottlenecks.append({
                "type": "latency",
                "severity": "high",
                "message": f"P95 latency ({metrics.latency_p95:.0f}ms) exceeds threshold ({profile.max_latency_ms}ms)",
            })
            report.recommendations.append("Consider optimizing slow operations or adding caching")
        
        # 错误率过高
        if metrics.error_rate > profile.max_error_rate:
            report.bottlenecks.append({
                "type": "error_rate",
                "severity": "critical",
                "message": f"Error rate ({metrics.error_rate*100:.1f}%) exceeds threshold ({profile.max_error_rate*100:.1f}%)",
            })
            report.recommendations.append("Investigate error causes and add retry mechanisms")
        
        # 吞吐量低
        if profile.target_rps > 0 and metrics.requests_per_second < profile.target_rps * 0.8:
            report.bottlenecks.append({
                "type": "throughput",
                "severity": "medium",
                "message": f"RPS ({metrics.requests_per_second:.1f}) below target ({profile.target_rps})",
            })
            report.recommendations.append("Consider horizontal scaling or async processing")
        
        # 延迟方差大
        if metrics.latency_std > metrics.latency_avg:
            report.bottlenecks.append({
                "type": "consistency",
                "severity": "low",
                "message": "High latency variance indicates inconsistent performance",
            })
            report.recommendations.append("Look for resource contention or GC pauses")
        
        # 找出最慢的动作
        slowest_actions = sorted(
            report.results_by_action.items(),
            key=lambda x: x[1].latency_p95,
            reverse=True,
        )[:3]
        
        for action_name, action_metrics in slowest_actions:
            if action_metrics.latency_p95 > metrics.latency_avg * 2:
                report.bottlenecks.append({
                    "type": "slow_action",
                    "severity": "medium",
                    "action": action_name,
                    "message": f"Action {action_name} has P95 latency of {action_metrics.latency_p95:.0f}ms",
                })
    
    def stop_test(self) -> bool:
        """停止当前测试"""
        with self._lock:
            if not self.running:
                return False
            
            self.running = False
            
            for user in self.users.values():
                user.stop()
            
            if self.current_test:
                self.current_test.status = TestStatus.CANCELLED
            
            return True
    
    def get_test_status(self, test_id: str) -> Optional[Dict]:
        """获取测试状态"""
        with self._lock:
            report = self.tests.get(test_id)
            if report:
                return report.to_dict()
            return None
    
    def get_realtime_metrics(self) -> Dict:
        """获取实时指标"""
        with self._lock:
            if not self.realtime_results:
                return {}
            
            recent = list(self.realtime_results)[-1000:]
            latencies = [r.latency_ms for r in recent]
            errors = sum(1 for r in recent if not r.success)
            
            return {
                "total_requests": len(self.realtime_results),
                "recent_avg_latency": statistics.mean(latencies) if latencies else 0,
                "recent_error_rate": errors / len(recent) if recent else 0,
                "active_users": len([u for u in self.users.values() if u.active]),
            }


# ============== 全局实例 ==============

_load_test_engine: Optional[LoadTestEngine] = None


def get_load_test_engine() -> LoadTestEngine:
    """获取负载测试引擎单例"""
    global _load_test_engine
    if _load_test_engine is None:
        _load_test_engine = LoadTestEngine()
    return _load_test_engine
