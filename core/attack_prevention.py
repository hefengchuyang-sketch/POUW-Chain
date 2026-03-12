"""
attack_prevention.py - 攻击防范系统

Phase 10 功能：
1. DDoS 防护
2. Sybil 攻击增强检测
3. 智能速率限制
4. 异常行为检测
5. 自动封禁与恢复
6. 威胁情报集成
"""

import time
import uuid
import hashlib
import threading
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum
from collections import defaultdict, deque
import json
import math


# ============== 枚举类型 ==============

class ThreatLevel(Enum):
    """威胁等级"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AttackType(Enum):
    """攻击类型"""
    DDOS = "ddos"
    SYBIL = "sybil"
    SPAM = "spam"
    BRUTEFORCE = "bruteforce"
    REPLAY = "replay"
    ECLIPSE = "eclipse"
    FRONTRUNNING = "frontrunning"
    GRIEFING = "griefing"


class BanReason(Enum):
    """封禁原因"""
    RATE_LIMIT = "rate_limit"
    DDOS_DETECTED = "ddos_detected"
    SYBIL_DETECTED = "sybil_detected"
    MALICIOUS_BEHAVIOR = "malicious_behavior"
    SPAM = "spam"
    MANUAL = "manual"


class DefenseAction(Enum):
    """防御动作"""
    ALLOW = "allow"
    THROTTLE = "throttle"
    CHALLENGE = "challenge"
    BLOCK = "block"
    BAN = "ban"


# ============== 数据结构 ==============

@dataclass
class RequestRecord:
    """请求记录"""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 来源
    source_ip: str = ""
    source_id: str = ""                # 用户/节点 ID
    
    # 请求
    endpoint: str = ""
    method: str = ""
    payload_size: int = 0
    
    # 时间
    timestamp: float = field(default_factory=time.time)
    processing_time_ms: float = 0
    
    # 结果
    success: bool = True
    blocked: bool = False
    threat_level: ThreatLevel = ThreatLevel.NONE


@dataclass
class ThreatIndicator:
    """威胁指标"""
    indicator_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 来源
    source_id: str = ""
    source_type: str = ""              # ip, address, node
    
    # 指标
    attack_type: AttackType = AttackType.DDOS
    threat_level: ThreatLevel = ThreatLevel.LOW
    
    # 证据
    evidence: List[Dict] = field(default_factory=list)
    request_count: int = 0
    suspicious_patterns: List[str] = field(default_factory=list)
    
    # 时间
    first_seen: float = field(default_factory=time.time)
    last_seen: float = 0
    
    # 状态
    active: bool = True
    resolved: bool = False


@dataclass
class BanRecord:
    """封禁记录"""
    ban_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 目标
    source_id: str = ""
    source_type: str = ""              # ip, address, node
    
    # 原因
    reason: BanReason = BanReason.RATE_LIMIT
    attack_type: Optional[AttackType] = None
    
    # 时间
    banned_at: float = field(default_factory=time.time)
    expires_at: float = 0              # 0 表示永久
    unbanned_at: float = 0
    
    # 状态
    active: bool = True
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at == 0:
            return False
        return time.time() > self.expires_at


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    name: str = "default"
    
    # 限制
    requests_per_second: float = 100
    requests_per_minute: float = 1000
    requests_per_hour: float = 10000
    
    # 突发
    burst_size: int = 50
    
    # 动态调整
    dynamic_enabled: bool = True
    min_rate: float = 10
    max_rate: float = 1000
    
    # 白名单/黑名单
    whitelist: Set[str] = field(default_factory=set)
    blacklist: Set[str] = field(default_factory=set)


# ============== 速率限制器 ==============

class TokenBucket:
    """令牌桶算法"""
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate               # 令牌填充速率（每秒）
        self.capacity = capacity       # 桶容量
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """消费令牌"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # 填充令牌
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """获取等待时间"""
        with self._lock:
            if self.tokens >= tokens:
                return 0
            needed = tokens - self.tokens
            return needed / self.rate


class SlidingWindowRateLimiter:
    """滑动窗口速率限制器"""
    
    def __init__(self, window_size: float, max_requests: int):
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.RLock()
    
    def is_allowed(self, identifier: str) -> bool:
        """检查是否允许请求"""
        with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # 清理过期请求
            while self.requests[identifier] and self.requests[identifier][0] < window_start:
                self.requests[identifier].popleft()
            
            # 检查限制
            if len(self.requests[identifier]) >= self.max_requests:
                return False
            
            self.requests[identifier].append(now)
            return True
    
    def get_remaining(self, identifier: str) -> int:
        """获取剩余配额"""
        with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            while self.requests[identifier] and self.requests[identifier][0] < window_start:
                self.requests[identifier].popleft()
            
            return max(0, self.max_requests - len(self.requests[identifier]))


# ============== DDoS 检测器 ==============

class DDoSDetector:
    """DDoS 攻击检测器"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 请求统计
        self.request_counts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.bandwidth_usage: Dict[str, int] = defaultdict(int)
        
        # 阈值
        self.rps_threshold = 100                 # 每秒请求阈值
        self.bandwidth_threshold = 10 * 1024 * 1024  # 10MB/s
        self.connection_threshold = 100          # 连接数阈值
        
        # 检测窗口
        self.window_seconds = 60
        
        # 检测结果
        self.detected_attacks: Dict[str, ThreatIndicator] = {}
    
    def record_request(self, source_id: str, payload_size: int = 0) -> ThreatLevel:
        """记录请求并检测"""
        with self._lock:
            now = time.time()
            
            # 记录请求时间
            self.request_counts[source_id].append(now)
            self.bandwidth_usage[source_id] += payload_size
            
            # 计算最近的请求速率
            window_start = now - self.window_seconds
            recent_requests = [t for t in self.request_counts[source_id] if t > window_start]
            
            rps = len(recent_requests) / self.window_seconds if recent_requests else 0
            
            # 检测 DDoS
            threat_level = ThreatLevel.NONE
            
            if rps > self.rps_threshold * 2:
                threat_level = ThreatLevel.CRITICAL
            elif rps > self.rps_threshold:
                threat_level = ThreatLevel.HIGH
            elif rps > self.rps_threshold * 0.5:
                threat_level = ThreatLevel.MEDIUM
            elif rps > self.rps_threshold * 0.3:
                threat_level = ThreatLevel.LOW
            
            if threat_level.value >= ThreatLevel.MEDIUM.value:
                self._record_threat(source_id, threat_level, rps)
            
            return threat_level
    
    def _record_threat(self, source_id: str, level: ThreatLevel, rps: float):
        """记录威胁"""
        if source_id not in self.detected_attacks:
            self.detected_attacks[source_id] = ThreatIndicator(
                source_id=source_id,
                source_type="ip",
                attack_type=AttackType.DDOS,
                threat_level=level,
            )
        
        indicator = self.detected_attacks[source_id]
        indicator.threat_level = level
        indicator.last_seen = time.time()
        indicator.request_count += 1
        indicator.evidence.append({
            "rps": rps,
            "timestamp": time.time(),
        })
    
    def get_active_threats(self) -> List[ThreatIndicator]:
        """获取活跃威胁"""
        with self._lock:
            cutoff = time.time() - self.window_seconds
            return [
                t for t in self.detected_attacks.values()
                if t.last_seen > cutoff and t.active
            ]


# ============== Sybil 检测器 ==============

class SybilDetector:
    """Sybil 攻击检测器（增强版）"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 节点信息
        self.nodes: Dict[str, Dict] = {}
        
        # 网络图
        self.connections: Dict[str, Set[str]] = defaultdict(set)
        
        # 行为模式
        self.behavior_patterns: Dict[str, List[Dict]] = defaultdict(list)
        
        # 检测参数
        self.min_stake = 100                     # 最小质押
        self.min_age_hours = 24                  # 最小账户年龄
        self.max_similarity_score = 0.8          # 最大相似度
        self.min_unique_peers = 3                # 最小独立对等节点
        
        # 检测结果
        self.sybil_clusters: List[Set[str]] = []
        self.suspected_nodes: Dict[str, ThreatIndicator] = {}
    
    def register_node(
        self,
        node_id: str,
        ip_address: str = "",
        stake: int = 0,
        created_at: float = 0,
    ):
        """注册节点"""
        with self._lock:
            self.nodes[node_id] = {
                "node_id": node_id,
                "ip_address": ip_address,
                "stake": stake,
                "created_at": created_at or time.time(),
                "reputation_score": 0.5,
            }
    
    def record_connection(self, node_a: str, node_b: str):
        """记录节点连接"""
        with self._lock:
            self.connections[node_a].add(node_b)
            self.connections[node_b].add(node_a)
    
    def record_behavior(self, node_id: str, action: str, details: Dict = None):
        """记录行为"""
        with self._lock:
            self.behavior_patterns[node_id].append({
                "action": action,
                "details": details or {},
                "timestamp": time.time(),
            })
            
            # 保留最近 1000 条
            if len(self.behavior_patterns[node_id]) > 1000:
                self.behavior_patterns[node_id] = self.behavior_patterns[node_id][-1000:]
    
    def analyze_node(self, node_id: str) -> Dict:
        """分析节点 Sybil 风险"""
        with self._lock:
            if node_id not in self.nodes:
                return {"error": "Node not found"}
            
            node = self.nodes[node_id]
            risk_factors = []
            risk_score = 0
            
            # 1. 检查质押
            if node["stake"] < self.min_stake:
                risk_factors.append(f"Low stake: {node['stake']}")
                risk_score += 0.2
            
            # 2. 检查账户年龄
            age_hours = (time.time() - node["created_at"]) / 3600
            if age_hours < self.min_age_hours:
                risk_factors.append(f"New account: {age_hours:.1f} hours")
                risk_score += 0.2
            
            # 3. 检查连接多样性
            peers = self.connections.get(node_id, set())
            unique_ips = set()
            for peer in peers:
                if peer in self.nodes:
                    unique_ips.add(self.nodes[peer].get("ip_address", ""))
            
            if len(unique_ips) < self.min_unique_peers:
                risk_factors.append(f"Few unique peers: {len(unique_ips)}")
                risk_score += 0.2
            
            # 4. 检查行为相似性
            similarity_scores = self._check_behavior_similarity(node_id)
            if similarity_scores:
                max_similarity = max(similarity_scores.values())
                if max_similarity > self.max_similarity_score:
                    risk_factors.append(f"High similarity with other nodes: {max_similarity:.2f}")
                    risk_score += 0.3
            
            # 5. 检查 IP 聚类
            same_ip_nodes = [
                nid for nid, n in self.nodes.items()
                if n.get("ip_address") == node.get("ip_address") and nid != node_id
            ]
            if len(same_ip_nodes) > 5:
                risk_factors.append(f"Many nodes from same IP: {len(same_ip_nodes)}")
                risk_score += 0.3
            
            # 确定威胁等级
            if risk_score >= 0.8:
                threat_level = ThreatLevel.CRITICAL
            elif risk_score >= 0.6:
                threat_level = ThreatLevel.HIGH
            elif risk_score >= 0.4:
                threat_level = ThreatLevel.MEDIUM
            elif risk_score >= 0.2:
                threat_level = ThreatLevel.LOW
            else:
                threat_level = ThreatLevel.NONE
            
            # 记录可疑节点
            if threat_level.value >= ThreatLevel.MEDIUM.value:
                self.suspected_nodes[node_id] = ThreatIndicator(
                    source_id=node_id,
                    source_type="node",
                    attack_type=AttackType.SYBIL,
                    threat_level=threat_level,
                    suspicious_patterns=risk_factors,
                )
            
            return {
                "node_id": node_id,
                "risk_score": round(risk_score, 2),
                "threat_level": threat_level.value,
                "risk_factors": risk_factors,
                "is_sybil": risk_score >= 0.6,
            }
    
    def _check_behavior_similarity(self, node_id: str) -> Dict[str, float]:
        """检查行为相似性"""
        if node_id not in self.behavior_patterns:
            return {}
        
        node_actions = [b["action"] for b in self.behavior_patterns[node_id]]
        if not node_actions:
            return {}
        
        similarities = {}
        
        for other_id, other_patterns in self.behavior_patterns.items():
            if other_id == node_id:
                continue
            
            other_actions = [b["action"] for b in other_patterns]
            if not other_actions:
                continue
            
            # 简化的 Jaccard 相似度
            set_a = set(node_actions[-100:])
            set_b = set(other_actions[-100:])
            
            intersection = len(set_a & set_b)
            union = len(set_a | set_b)
            
            if union > 0:
                similarity = intersection / union
                if similarity > 0.5:
                    similarities[other_id] = similarity
        
        return similarities
    
    def detect_clusters(self) -> List[Set[str]]:
        """检测 Sybil 集群"""
        with self._lock:
            # 基于 IP 聚类
            ip_clusters: Dict[str, Set[str]] = defaultdict(set)
            for node_id, node in self.nodes.items():
                ip = node.get("ip_address", "")
                if ip:
                    ip_clusters[ip].add(node_id)
            
            # 大于阈值的集群
            suspicious_clusters = [
                cluster for cluster in ip_clusters.values()
                if len(cluster) > 5
            ]
            
            # 基于行为相似性聚类
            behavior_clusters = self._cluster_by_behavior()
            
            self.sybil_clusters = suspicious_clusters + behavior_clusters
            return self.sybil_clusters
    
    def _cluster_by_behavior(self) -> List[Set[str]]:
        """基于行为聚类"""
        # 简化实现：返回高相似度节点对
        clusters = []
        checked = set()
        
        for node_id in self.behavior_patterns:
            if node_id in checked:
                continue
            
            similarities = self._check_behavior_similarity(node_id)
            similar_nodes = {n for n, s in similarities.items() if s > 0.8}
            
            if len(similar_nodes) >= 2:
                cluster = similar_nodes | {node_id}
                clusters.append(cluster)
                checked.update(cluster)
        
        return clusters


# ============== 攻击防范管理器 ==============

class AttackPreventionManager:
    """攻击防范管理器"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 检测器
        self.ddos_detector = DDoSDetector()
        self.sybil_detector = SybilDetector()
        
        # 速率限制
        self.rate_limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self.token_buckets: Dict[str, TokenBucket] = {}
        self.rate_config = RateLimitConfig()
        
        # 封禁列表
        self.bans: Dict[str, BanRecord] = {}
        
        # 请求历史
        self.request_history: deque = deque(maxlen=100000)
        
        # 威胁情报
        self.threat_intel: Dict[str, ThreatIndicator] = {}
        
        # 全局状态
        self.defense_level = ThreatLevel.NONE
        self.under_attack = False
        
        # 统计
        self.stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "throttled_requests": 0,
            "bans_issued": 0,
            "ddos_detected": 0,
            "sybil_detected": 0,
        }
        
        # 初始化默认速率限制器
        self._init_rate_limiters()
    
    def _init_rate_limiters(self):
        """初始化速率限制器"""
        # 全局限制
        self.rate_limiters["global"] = SlidingWindowRateLimiter(60, 10000)
        # 每 IP 限制
        self.rate_limiters["per_ip"] = SlidingWindowRateLimiter(60, 100)
        # 每用户限制
        self.rate_limiters["per_user"] = SlidingWindowRateLimiter(60, 200)
    
    def process_request(
        self,
        source_ip: str,
        source_id: str = "",
        endpoint: str = "",
        payload_size: int = 0,
    ) -> Tuple[DefenseAction, str]:
        """处理请求"""
        with self._lock:
            self.stats["total_requests"] += 1
            
            # 创建请求记录
            record = RequestRecord(
                source_ip=source_ip,
                source_id=source_id or source_ip,
                endpoint=endpoint,
                payload_size=payload_size,
            )
            
            # 1. 检查封禁
            ban = self._check_ban(source_ip, source_id)
            if ban:
                record.blocked = True
                self.stats["blocked_requests"] += 1
                return DefenseAction.BAN, f"Banned: {ban.reason.value}"
            
            # 2. 检查黑名单
            if source_ip in self.rate_config.blacklist or source_id in self.rate_config.blacklist:
                record.blocked = True
                self.stats["blocked_requests"] += 1
                return DefenseAction.BLOCK, "Blacklisted"
            
            # 3. 白名单跳过检查
            if source_ip in self.rate_config.whitelist or source_id in self.rate_config.whitelist:
                return DefenseAction.ALLOW, "Whitelisted"
            
            # 4. DDoS 检测
            ddos_threat = self.ddos_detector.record_request(source_ip, payload_size)
            record.threat_level = ddos_threat
            
            if ddos_threat.value >= ThreatLevel.CRITICAL.value:
                self._issue_ban(source_ip, "ip", BanReason.DDOS_DETECTED, AttackType.DDOS, 3600)
                self.stats["ddos_detected"] += 1
                return DefenseAction.BAN, "DDoS attack detected"
            
            if ddos_threat.value >= ThreatLevel.HIGH.value:
                self.stats["blocked_requests"] += 1
                return DefenseAction.BLOCK, "High threat level"
            
            # 5. 速率限制
            if not self.rate_limiters["per_ip"].is_allowed(source_ip):
                self.stats["throttled_requests"] += 1
                return DefenseAction.THROTTLE, "Rate limit exceeded"
            
            if source_id and not self.rate_limiters["per_user"].is_allowed(source_id):
                self.stats["throttled_requests"] += 1
                return DefenseAction.THROTTLE, "User rate limit exceeded"
            
            # 6. 全局限制
            if not self.rate_limiters["global"].is_allowed("global"):
                self.under_attack = True
                return DefenseAction.THROTTLE, "System overload"
            
            # 记录请求
            self.request_history.append(record)
            
            return DefenseAction.ALLOW, "OK"
    
    def _check_ban(self, source_ip: str, source_id: str) -> Optional[BanRecord]:
        """检查封禁状态"""
        for key in [source_ip, source_id]:
            if key in self.bans:
                ban = self.bans[key]
                if ban.active and not ban.is_expired():
                    return ban
                elif ban.is_expired():
                    ban.active = False
        return None
    
    def _issue_ban(
        self,
        source_id: str,
        source_type: str,
        reason: BanReason,
        attack_type: AttackType = None,
        duration_seconds: int = 3600,
    ) -> BanRecord:
        """发出封禁"""
        ban = BanRecord(
            source_id=source_id,
            source_type=source_type,
            reason=reason,
            attack_type=attack_type,
            expires_at=time.time() + duration_seconds if duration_seconds > 0 else 0,
        )
        
        self.bans[source_id] = ban
        self.stats["bans_issued"] += 1
        
        return ban
    
    def ban_source(
        self,
        source_id: str,
        reason: str = "manual",
        duration_seconds: int = 3600,
    ) -> BanRecord:
        """手动封禁"""
        with self._lock:
            return self._issue_ban(
                source_id,
                "manual",
                BanReason.MANUAL,
                duration_seconds=duration_seconds,
            )
    
    def unban_source(self, source_id: str) -> bool:
        """解除封禁"""
        with self._lock:
            if source_id in self.bans:
                self.bans[source_id].active = False
                self.bans[source_id].unbanned_at = time.time()
                return True
            return False
    
    def analyze_sybil(self, node_id: str) -> Dict:
        """分析 Sybil 风险"""
        return self.sybil_detector.analyze_node(node_id)
    
    def register_node(self, node_id: str, ip_address: str, stake: int = 0):
        """注册节点用于 Sybil 检测"""
        self.sybil_detector.register_node(node_id, ip_address, stake)
    
    def detect_sybil_clusters(self) -> List[Set[str]]:
        """检测 Sybil 集群"""
        clusters = self.sybil_detector.detect_clusters()
        self.stats["sybil_detected"] = len(clusters)
        return clusters
    
    def add_to_whitelist(self, source_id: str):
        """添加到白名单"""
        with self._lock:
            self.rate_config.whitelist.add(source_id)
    
    def add_to_blacklist(self, source_id: str):
        """添加到黑名单"""
        with self._lock:
            self.rate_config.blacklist.add(source_id)
    
    def get_threat_status(self) -> Dict:
        """获取威胁状态"""
        with self._lock:
            active_threats = self.ddos_detector.get_active_threats()
            sybil_threats = list(self.sybil_detector.suspected_nodes.values())
            
            # 计算全局威胁等级
            max_level = ThreatLevel.NONE
            for t in active_threats + sybil_threats:
                if t.threat_level.value > max_level.value:
                    max_level = t.threat_level
            
            self.defense_level = max_level
            
            return {
                "defense_level": max_level.value,
                "under_attack": self.under_attack,
                "active_ddos_threats": len(active_threats),
                "suspected_sybil_nodes": len(sybil_threats),
                "active_bans": len([b for b in self.bans.values() if b.active]),
                "stats": self.stats,
            }
    
    def get_rate_limit_status(self, source_id: str) -> Dict:
        """获取速率限制状态"""
        with self._lock:
            return {
                "remaining_per_ip": self.rate_limiters["per_ip"].get_remaining(source_id),
                "remaining_per_user": self.rate_limiters["per_user"].get_remaining(source_id),
                "is_banned": source_id in self.bans and self.bans[source_id].active,
            }


# ============== 全局实例 ==============

_attack_prevention_manager: Optional[AttackPreventionManager] = None


def get_attack_prevention_manager() -> AttackPreventionManager:
    """获取攻击防范管理器单例"""
    global _attack_prevention_manager
    if _attack_prevention_manager is None:
        _attack_prevention_manager = AttackPreventionManager()
    return _attack_prevention_manager
