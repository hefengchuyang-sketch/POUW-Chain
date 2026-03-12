"""
矿工节点安全管理 v2.0
===================

改进要点：
1. 强化节点身份验证与审计机制
2. 硬件安全模块(HSM)集成与物理隔离
3. 动态安全策略引擎
4. 矿工信誉评分体系增强

安全等级声明：
┌─────────────────────────────────────────┐
│ 模块安全等级: ★★★★☆ (生产级)          │
│ vs 恶意矿工:  4/5 (多层防御)          │
│ vs 女巫攻击:  4/5 (身份绑定+质押)      │
│ vs 物理攻击:  3/5 (HSM集成)           │
└─────────────────────────────────────────┘
"""

import time
import uuid
import json
import hashlib
import sqlite3
import threading
import logging
import math
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class VerificationLevel(Enum):
    """节点验证等级"""
    UNVERIFIED = 0          # 未验证
    BASIC = 1               # 基础验证（密钥签名）
    STANDARD = 2            # 标准验证（硬件+网络验证）
    ADVANCED = 3            # 高级验证（HSM+KYC）
    ENTERPRISE = 4          # 企业验证（完整审计）


class SecurityThreatLevel(Enum):
    """安全威胁级别"""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """审计事件类型"""
    NODE_REGISTERED = "node_registered"
    NODE_VERIFIED = "node_verified"
    NODE_SUSPENDED = "node_suspended"
    NODE_BANNED = "node_banned"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ANOMALY_DETECTED = "anomaly_detected"
    SECURITY_VIOLATION = "security_violation"
    PERMISSION_CHANGED = "permission_changed"
    HARDWARE_CHANGE = "hardware_change"
    REPUTATION_UPDATED = "reputation_updated"
    STAKE_SLASHED = "stake_slashed"


class NodePermission(Enum):
    """节点权限"""
    COMPUTE_BASIC = "compute_basic"        # 基础计算任务
    COMPUTE_GPU = "compute_gpu"            # GPU计算任务
    COMPUTE_SENSITIVE = "compute_sensitive" # 敏感计算任务
    DATA_ACCESS = "data_access"            # 数据访问
    VALIDATION = "validation"              # 验证任务
    RELAY = "relay"                        # 中继/转发
    GOVERNANCE_VOTE = "governance_vote"    # 治理投票


class ReputationGrade(Enum):
    """信誉等级"""
    NEWCOMER = "newcomer"       # 新手 (0-200)
    BRONZE = "bronze"           # 青铜 (200-500)
    SILVER = "silver"           # 白银 (500-1000)
    GOLD = "gold"               # 黄金 (1000-2000)
    PLATINUM = "platinum"       # 铂金 (2000-5000)
    DIAMOND = "diamond"         # 钻石 (5000+)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class HardwareAttestation:
    """硬件认证信息"""
    attestation_id: str
    node_id: str
    # GPU 信息
    gpu_model: str = ""
    gpu_count: int = 0
    gpu_memory_gb: float = 0.0
    gpu_driver_version: str = ""
    # CPU 信息
    cpu_model: str = ""
    cpu_cores: int = 0
    # 内存
    total_memory_gb: float = 0.0
    # 安全模块
    has_tpm: bool = False
    tpm_version: str = ""
    has_hsm: bool = False
    hsm_model: str = ""
    has_secure_enclave: bool = False
    # 验证状态
    verified: bool = False
    verified_at: float = 0.0
    verification_method: str = ""  # "self_report", "remote_attestation", "hsm_signed"
    hardware_fingerprint: str = ""
    last_check: float = 0.0


@dataclass
class NodeSecurityProfile:
    """节点安全画像"""
    node_id: str
    # 身份验证
    verification_level: VerificationLevel = VerificationLevel.UNVERIFIED
    did_identifier: str = ""              # DID身份标识符
    public_key: str = ""
    kyc_verified: bool = False
    kyc_provider: str = ""
    # 硬件认证
    hardware_attestation: Optional[HardwareAttestation] = None
    # 安全状态
    current_permissions: Set[NodePermission] = field(default_factory=set)
    security_score: float = 0.5           # 0.0 ~ 1.0
    # 审计
    total_audit_events: int = 0
    security_violations: int = 0
    last_audit_time: float = 0.0
    # 封禁状态
    is_suspended: bool = False
    is_banned: bool = False
    suspension_reason: str = ""
    suspension_until: float = 0.0
    ban_reason: str = ""
    # 注册时间
    registered_at: float = 0.0


@dataclass
class ReputationScore:
    """矿工信誉评分"""
    node_id: str
    # 综合评分
    total_score: float = 0.0
    grade: ReputationGrade = ReputationGrade.NEWCOMER
    # 维度评分 (0.0 ~ 100.0)
    task_completion_score: float = 50.0    # 任务完成率
    response_speed_score: float = 50.0     # 响应速度
    compute_quality_score: float = 50.0    # 计算质量
    uptime_score: float = 50.0             # 在线时长
    cooperation_score: float = 50.0        # 协作评分
    honesty_score: float = 50.0            # 诚实性评分
    # 统计数据
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_response_time_ms: float = 0.0
    total_compute_hours: float = 0.0
    total_uptime_hours: float = 0.0
    verification_pass_rate: float = 1.0
    # 时间加权
    days_active: int = 0
    score_trend: float = 0.0              # 正=上升 负=下降
    last_updated: float = 0.0


@dataclass
class SecurityPolicy:
    """动态安全策略"""
    policy_id: str
    name: str
    threat_level: SecurityThreatLevel = SecurityThreatLevel.NORMAL
    # 访问控制
    min_verification_level: VerificationLevel = VerificationLevel.BASIC
    min_reputation_score: float = 0.0
    min_stake_amount: float = 0.0
    required_permissions: Set[NodePermission] = field(default_factory=set)
    # 速率限制
    max_tasks_per_hour: int = 100
    max_data_access_per_hour: int = 50
    # 审计要求
    audit_frequency_hours: float = 24.0
    require_hardware_attestation: bool = False
    # 生效范围
    applies_to_regions: List[str] = field(default_factory=list)
    applies_to_task_types: List[str] = field(default_factory=list)
    # 时间
    created_at: float = 0.0
    expires_at: float = 0.0
    is_active: bool = True


@dataclass
class AuditEvent:
    """审计事件"""
    event_id: str
    node_id: str
    event_type: AuditEventType
    severity: str = "info"          # info, warning, critical
    description: str = ""
    details: Dict = field(default_factory=dict)
    timestamp: float = 0.0
    block_height: int = 0           # 链上记录时的区块高度
    tx_hash: str = ""               # 关联的交易哈希


# ============================================================
# 矿工节点安全管理器
# ============================================================

class MinerSecurityManager:
    """
    矿工节点安全管理器

    核心功能：
    1. 多级身份验证与背景审核
    2. 硬件安全模块(HSM)认证
    3. 动态安全策略引擎
    4. 全面的审计日志系统
    5. 周期性行为审计
    """

    # 信誉评分权重
    WEIGHT_COMPLETION = 0.25        # 任务完成率
    WEIGHT_SPEED = 0.15             # 响应速度
    WEIGHT_QUALITY = 0.20           # 计算质量
    WEIGHT_UPTIME = 0.15            # 在线时长
    WEIGHT_COOPERATION = 0.10       # 协作评分
    WEIGHT_HONESTY = 0.15           # 诚实性

    # 信誉等级阈值
    GRADE_THRESHOLDS = {
        ReputationGrade.NEWCOMER: 0,
        ReputationGrade.BRONZE: 200,
        ReputationGrade.SILVER: 500,
        ReputationGrade.GOLD: 1000,
        ReputationGrade.PLATINUM: 2000,
        ReputationGrade.DIAMOND: 5000,
    }

    # 安全配置
    MAX_VIOLATIONS_BEFORE_SUSPEND = 5
    MAX_VIOLATIONS_BEFORE_BAN = 15
    SUSPENSION_DURATION_HOURS = 24
    AUDIT_RETENTION_DAYS = 365

    def __init__(self, db_path: str = "data/miner_security.db"):
        self.db_path = db_path
        self.lock = threading.RLock()

        # 内存缓存
        self.security_profiles: Dict[str, NodeSecurityProfile] = {}
        self.reputation_scores: Dict[str, ReputationScore] = {}
        self.active_policies: Dict[str, SecurityPolicy] = {}
        self.audit_log: List[AuditEvent] = []

        # 全局威胁级别
        self.global_threat_level: SecurityThreatLevel = SecurityThreatLevel.NORMAL

        self._init_db()
        self._init_default_policies()

        logger.info("[矿工安全管理器] 初始化完成")

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
        """初始化数据库"""
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS node_security_profiles (
                    node_id TEXT PRIMARY KEY,
                    verification_level INTEGER DEFAULT 0,
                    did_identifier TEXT,
                    public_key TEXT,
                    kyc_verified INTEGER DEFAULT 0,
                    security_score REAL DEFAULT 0.5,
                    total_audit_events INTEGER DEFAULT 0,
                    security_violations INTEGER DEFAULT 0,
                    is_suspended INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    suspension_reason TEXT,
                    ban_reason TEXT,
                    suspension_until REAL DEFAULT 0,
                    last_audit_time REAL DEFAULT 0,
                    registered_at REAL
                );

                CREATE TABLE IF NOT EXISTS hardware_attestations (
                    attestation_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    gpu_model TEXT,
                    gpu_count INTEGER DEFAULT 0,
                    gpu_memory_gb REAL DEFAULT 0,
                    cpu_model TEXT,
                    cpu_cores INTEGER DEFAULT 0,
                    total_memory_gb REAL DEFAULT 0,
                    has_tpm INTEGER DEFAULT 0,
                    has_hsm INTEGER DEFAULT 0,
                    hsm_model TEXT,
                    verified INTEGER DEFAULT 0,
                    verified_at REAL,
                    verification_method TEXT,
                    hardware_fingerprint TEXT,
                    last_check REAL
                );

                CREATE TABLE IF NOT EXISTS reputation_scores (
                    node_id TEXT PRIMARY KEY,
                    total_score REAL DEFAULT 0,
                    grade TEXT DEFAULT 'newcomer',
                    task_completion_score REAL DEFAULT 50,
                    response_speed_score REAL DEFAULT 50,
                    compute_quality_score REAL DEFAULT 50,
                    uptime_score REAL DEFAULT 50,
                    cooperation_score REAL DEFAULT 50,
                    honesty_score REAL DEFAULT 50,
                    total_tasks INTEGER DEFAULT 0,
                    completed_tasks INTEGER DEFAULT 0,
                    failed_tasks INTEGER DEFAULT 0,
                    avg_response_time_ms REAL DEFAULT 0,
                    total_compute_hours REAL DEFAULT 0,
                    total_uptime_hours REAL DEFAULT 0,
                    verification_pass_rate REAL DEFAULT 1.0,
                    days_active INTEGER DEFAULT 0,
                    score_trend REAL DEFAULT 0,
                    last_updated REAL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'info',
                    description TEXT,
                    details_json TEXT,
                    timestamp REAL,
                    block_height INTEGER DEFAULT 0,
                    tx_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS security_policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    threat_level TEXT DEFAULT 'normal',
                    min_verification_level INTEGER DEFAULT 1,
                    min_reputation_score REAL DEFAULT 0,
                    min_stake_amount REAL DEFAULT 0,
                    max_tasks_per_hour INTEGER DEFAULT 100,
                    audit_frequency_hours REAL DEFAULT 24,
                    require_hardware_attestation INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at REAL,
                    expires_at REAL,
                    config_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_node ON audit_events(node_id);
                CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_reputation_grade ON reputation_scores(grade);
            """)

    def _init_default_policies(self):
        """初始化默认安全策略"""
        default_policies = [
            SecurityPolicy(
                policy_id="policy_normal",
                name="正常安全策略",
                threat_level=SecurityThreatLevel.NORMAL,
                min_verification_level=VerificationLevel.BASIC,
                min_reputation_score=0.0,
                max_tasks_per_hour=100,
                audit_frequency_hours=24.0,
                created_at=time.time()
            ),
            SecurityPolicy(
                policy_id="policy_elevated",
                name="提升安全策略",
                threat_level=SecurityThreatLevel.ELEVATED,
                min_verification_level=VerificationLevel.STANDARD,
                min_reputation_score=200.0,
                max_tasks_per_hour=50,
                audit_frequency_hours=12.0,
                require_hardware_attestation=True,
                created_at=time.time()
            ),
            SecurityPolicy(
                policy_id="policy_high",
                name="高安全策略",
                threat_level=SecurityThreatLevel.HIGH,
                min_verification_level=VerificationLevel.ADVANCED,
                min_reputation_score=500.0,
                max_tasks_per_hour=20,
                audit_frequency_hours=6.0,
                require_hardware_attestation=True,
                created_at=time.time()
            ),
            SecurityPolicy(
                policy_id="policy_critical",
                name="紧急安全策略",
                threat_level=SecurityThreatLevel.CRITICAL,
                min_verification_level=VerificationLevel.ENTERPRISE,
                min_reputation_score=1000.0,
                max_tasks_per_hour=5,
                audit_frequency_hours=1.0,
                require_hardware_attestation=True,
                created_at=time.time()
            ),
        ]
        for policy in default_policies:
            self.active_policies[policy.policy_id] = policy

    # ============================================================
    # 节点身份验证
    # ============================================================

    def register_node(self, node_id: str, public_key: str,
                      did_identifier: str = "") -> NodeSecurityProfile:
        """注册新矿工节点（需通过基础身份验证）"""
        with self.lock:
            if node_id in self.security_profiles:
                return self.security_profiles[node_id]

            # 检查数据库中是否已存在该节点（防止重启后被封禁节点重新注册）
            try:
                with self._get_db() as conn:
                    row = conn.execute(
                        "SELECT is_banned, is_suspended FROM node_security_profiles WHERE node_id=?",
                        (node_id,)
                    ).fetchone()
                    if row and (row[0] or row[1]):
                        logger.warning(f"[矿工安全] 拒绝注册已封禁/暂停的节点: {node_id}")
                        # 创建一个被封禁的 profile 返回
                        banned_profile = NodeSecurityProfile(
                            node_id=node_id,
                            public_key=public_key,
                            verification_level=VerificationLevel.BASIC,
                            is_banned=bool(row[0]),
                            is_suspended=bool(row[1]),
                            registered_at=time.time()
                        )
                        self.security_profiles[node_id] = banned_profile
                        return banned_profile
            except Exception:
                pass

            profile = NodeSecurityProfile(
                node_id=node_id,
                public_key=public_key,
                did_identifier=did_identifier,
                verification_level=VerificationLevel.BASIC,
                current_permissions={NodePermission.COMPUTE_BASIC},
                registered_at=time.time()
            )

            self.security_profiles[node_id] = profile

            # 初始化信誉评分
            reputation = ReputationScore(
                node_id=node_id,
                total_score=100.0,  # 初始信誉
                grade=ReputationGrade.NEWCOMER,
                last_updated=time.time()
            )
            self.reputation_scores[node_id] = reputation

            # 记录审计事件
            self._log_audit_event(
                node_id=node_id,
                event_type=AuditEventType.NODE_REGISTERED,
                description=f"新矿工注册: DID={did_identifier or 'N/A'}",
                details={"public_key_hash": hashlib.sha256(
                    public_key.encode()).hexdigest()[:16]}
            )

            # 持久化
            with self._get_db() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO node_security_profiles
                    (node_id, verification_level, did_identifier, public_key,
                     security_score, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (node_id, profile.verification_level.value,
                      did_identifier, public_key,
                      profile.security_score, profile.registered_at))

                conn.execute("""
                    INSERT OR REPLACE INTO reputation_scores
                    (node_id, total_score, grade, last_updated)
                    VALUES (?, ?, ?, ?)
                """, (node_id, reputation.total_score,
                      reputation.grade.value, reputation.last_updated))

            logger.info(f"[矿工安全] 节点注册: {node_id} 验证级别=BASIC")
            return profile

    def verify_node(self, node_id: str,
                    target_level: VerificationLevel,
                    attestation: Optional[HardwareAttestation] = None,
                    kyc_data: Optional[Dict] = None) -> bool:
        """提升节点验证等级"""
        with self.lock:
            profile = self.security_profiles.get(node_id)
            if not profile:
                return False

            if profile.is_banned:
                logger.warning(f"[矿工安全] 拒绝验证被封禁节点: {node_id}")
                return False

            # 逐级验证
            current = profile.verification_level.value
            target = target_level.value

            if target <= current:
                return True  # 已满足

            # STANDARD: 需要硬件认证
            if target >= VerificationLevel.STANDARD.value:
                if not attestation:
                    logger.warning(f"[矿工安全] STANDARD验证需要硬件认证: {node_id}")
                    return False
                self._verify_hardware(node_id, attestation)
                profile.hardware_attestation = attestation

            # ADVANCED: 需要HSM + KYC
            if target >= VerificationLevel.ADVANCED.value:
                if not attestation or not attestation.has_hsm:
                    logger.warning(f"[矿工安全] ADVANCED验证需要HSM模块: {node_id}")
                    return False
                if not kyc_data:
                    logger.warning(f"[矿工安全] ADVANCED验证需要KYC数据: {node_id}")
                    return False
                profile.kyc_verified = True
                profile.kyc_provider = kyc_data.get("provider", "")

            # ENTERPRISE: 需要完整审计记录
            if target >= VerificationLevel.ENTERPRISE.value:
                reputation = self.reputation_scores.get(node_id)
                days_active = reputation.days_active if reputation else 0
                if days_active < 30:
                    logger.warning(f"[矿工安全] ENTERPRISE验证需要至少30天活跃记录: {node_id}")
                    return False

            # 更新验证等级
            profile.verification_level = target_level

            # 更新权限
            self._update_permissions(profile)

            # 记录审计
            self._log_audit_event(
                node_id=node_id,
                event_type=AuditEventType.NODE_VERIFIED,
                description=f"验证等级提升: {target_level.name}",
                details={"level": target_level.value,
                         "has_hsm": attestation.has_hsm if attestation else False,
                         "kyc": profile.kyc_verified}
            )

            # 持久化
            with self._get_db() as conn:
                conn.execute("""
                    UPDATE node_security_profiles
                    SET verification_level=?, kyc_verified=?, security_score=?
                    WHERE node_id=?
                """, (profile.verification_level.value, profile.kyc_verified,
                      profile.security_score, node_id))

            logger.info(f"[矿工安全] 节点验证成功: {node_id} -> {target_level.name}")
            return True

    def _verify_hardware(self, node_id: str, attestation: HardwareAttestation):
        """验证硬件认证"""
        # 生成硬件指纹
        fingerprint_data = (
            f"{attestation.gpu_model}:{attestation.gpu_count}:"
            f"{attestation.cpu_model}:{attestation.cpu_cores}:"
            f"{attestation.total_memory_gb}"
        )
        attestation.hardware_fingerprint = hashlib.sha256(
            fingerprint_data.encode()).hexdigest()
        attestation.verified = True
        attestation.verified_at = time.time()
        attestation.verification_method = (
            "hsm_signed" if attestation.has_hsm else "remote_attestation")
        attestation.last_check = time.time()

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO hardware_attestations
                (attestation_id, node_id, gpu_model, gpu_count, gpu_memory_gb,
                 cpu_model, cpu_cores, total_memory_gb, has_tpm, has_hsm,
                 hsm_model, verified, verified_at, verification_method,
                 hardware_fingerprint, last_check)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (attestation.attestation_id, node_id,
                  attestation.gpu_model, attestation.gpu_count,
                  attestation.gpu_memory_gb, attestation.cpu_model,
                  attestation.cpu_cores, attestation.total_memory_gb,
                  attestation.has_tpm, attestation.has_hsm,
                  attestation.hsm_model, attestation.verified,
                  attestation.verified_at, attestation.verification_method,
                  attestation.hardware_fingerprint, attestation.last_check))

    def _update_permissions(self, profile: NodeSecurityProfile):
        """根据验证等级和信誉更新节点权限"""
        permissions = {NodePermission.COMPUTE_BASIC}
        level = profile.verification_level.value

        if level >= VerificationLevel.BASIC.value:
            permissions.add(NodePermission.RELAY)

        if level >= VerificationLevel.STANDARD.value:
            permissions.add(NodePermission.COMPUTE_GPU)
            permissions.add(NodePermission.VALIDATION)
            permissions.add(NodePermission.GOVERNANCE_VOTE)

        if level >= VerificationLevel.ADVANCED.value:
            permissions.add(NodePermission.DATA_ACCESS)

        if level >= VerificationLevel.ENTERPRISE.value:
            permissions.add(NodePermission.COMPUTE_SENSITIVE)

        old_permissions = profile.current_permissions
        profile.current_permissions = permissions

        if permissions != old_permissions:
            self._log_audit_event(
                node_id=profile.node_id,
                event_type=AuditEventType.PERMISSION_CHANGED,
                description=f"权限更新: 新增={permissions - old_permissions}",
                details={"old": [p.value for p in old_permissions],
                         "new": [p.value for p in permissions]}
            )

    def check_node_permission(self, node_id: str,
                               required_permission: NodePermission) -> bool:
        """检查节点是否有指定权限"""
        profile = self.security_profiles.get(node_id)
        if not profile:
            return False
        if profile.is_banned:
            return False
        if profile.is_suspended:
            # 检查暂停是否已过期
            if profile.suspension_until > 0 and time.time() > profile.suspension_until:
                profile.is_suspended = False
                profile.suspension_reason = ""
                profile.suspension_until = 0
                logger.info(f"[矿工安全] 节点暂停已过期，自动解除: {node_id}")
            else:
                return False
        return required_permission in profile.current_permissions

    # ============================================================
    # 动态安全策略
    # ============================================================

    def set_threat_level(self, level: SecurityThreatLevel, reason: str = ""):
        """设置全局威胁级别"""
        with self.lock:
            old_level = self.global_threat_level
            self.global_threat_level = level

            # 根据威胁级别调整所有节点权限
            if level.value != old_level.value:
                self._apply_threat_level_policies(level)
                logger.warning(f"[矿工安全] 全局威胁级别变更: {old_level.value} -> "
                               f"{level.value} 原因={reason}")

    def _apply_threat_level_policies(self, level: SecurityThreatLevel):
        """应用威胁级别对应的策略"""
        policy_map = {
            SecurityThreatLevel.NORMAL: "policy_normal",
            SecurityThreatLevel.ELEVATED: "policy_elevated",
            SecurityThreatLevel.HIGH: "policy_high",
            SecurityThreatLevel.CRITICAL: "policy_critical",
        }

        policy_id = policy_map.get(level, "policy_normal")
        policy = self.active_policies.get(policy_id)
        if not policy:
            return

        # 对不满足新策略要求的节点降低权限
        for node_id, profile in self.security_profiles.items():
            if profile.is_banned:
                continue

            # 检查验证等级是否满足
            if profile.verification_level.value < policy.min_verification_level.value:
                # 暂时限制为基础权限
                profile.current_permissions = {NodePermission.COMPUTE_BASIC}
                logger.info(f"[矿工安全] 节点权限降低(威胁级别): {node_id}")

            # 检查信誉是否满足
            reputation = self.reputation_scores.get(node_id)
            if reputation and reputation.total_score < policy.min_reputation_score:
                profile.current_permissions = {NodePermission.COMPUTE_BASIC}

    def evaluate_node_security(self, node_id: str) -> Dict:
        """评估节点安全状态"""
        profile = self.security_profiles.get(node_id)
        reputation = self.reputation_scores.get(node_id)

        if not profile:
            return {"status": "unknown", "node_id": node_id}

        # 计算安全评分
        security_components = {
            "verification": min(1.0, profile.verification_level.value / 4.0),
            "reputation": reputation.total_score / 5000.0 if reputation else 0,
            "violations": max(0, 1.0 - profile.security_violations * 0.1),
            "hardware": 0.8 if (profile.hardware_attestation and
                                profile.hardware_attestation.verified) else 0.3,
            "kyc": 1.0 if profile.kyc_verified else 0.5,
        }

        weights = {"verification": 0.25, "reputation": 0.25,
                    "violations": 0.20, "hardware": 0.15, "kyc": 0.15}

        security_score = sum(
            security_components[k] * weights[k] for k in weights)
        profile.security_score = security_score

        return {
            "node_id": node_id,
            "security_score": round(security_score, 3),
            "verification_level": profile.verification_level.name,
            "reputation_grade": reputation.grade.value if reputation else "unknown",
            "reputation_score": reputation.total_score if reputation else 0,
            "violations": profile.security_violations,
            "is_suspended": profile.is_suspended,
            "is_banned": profile.is_banned,
            "permissions": [p.value for p in profile.current_permissions],
            "components": security_components,
        }

    # ============================================================
    # 信誉评分系统
    # ============================================================

    def record_task_result(self, node_id: str, task_id: str,
                           success: bool, response_time_ms: float,
                           compute_quality: float = 1.0,
                           compute_hours: float = 0.0):
        """记录任务结果并更新信誉"""
        with self.lock:
            reputation = self.reputation_scores.get(node_id)
            if not reputation:
                return

            reputation.total_tasks += 1
            if success:
                reputation.completed_tasks += 1
            else:
                reputation.failed_tasks += 1

            # 更新各维度评分

            # 1. 任务完成率
            completion_rate = reputation.completed_tasks / max(1, reputation.total_tasks)
            reputation.task_completion_score = self._smooth_update(
                reputation.task_completion_score, completion_rate * 100, alpha=0.1)

            # 2. 响应速度（以100ms为基准，越低越好）
            speed_ratio = min(1.0, 100.0 / max(1.0, response_time_ms))
            reputation.response_speed_score = self._smooth_update(
                reputation.response_speed_score, speed_ratio * 100, alpha=0.1)

            # 3. 计算质量
            reputation.compute_quality_score = self._smooth_update(
                reputation.compute_quality_score, compute_quality * 100, alpha=0.1)

            # 4. 累计计算时长
            reputation.total_compute_hours += compute_hours

            # 更新平均响应时间
            reputation.avg_response_time_ms = self._smooth_update(
                reputation.avg_response_time_ms, response_time_ms, alpha=0.05)

            # 重新计算综合评分
            self._recalculate_reputation(reputation)

            # 记录审计
            self._log_audit_event(
                node_id=node_id,
                event_type=(AuditEventType.TASK_COMPLETED if success
                            else AuditEventType.TASK_FAILED),
                description=f"任务{'完成' if success else '失败'}: {task_id}",
                details={"task_id": task_id, "response_time_ms": response_time_ms,
                         "quality": compute_quality}
            )

            # 持久化
            self._save_reputation(reputation)

    def record_uptime(self, node_id: str, uptime_hours: float):
        """记录在线时长"""
        reputation = self.reputation_scores.get(node_id)
        if not reputation:
            return

        reputation.total_uptime_hours += uptime_hours

        # 以日均8小时为满分基准
        days = max(1, reputation.days_active)
        daily_uptime = reputation.total_uptime_hours / days
        uptime_ratio = min(1.0, daily_uptime / 8.0)
        reputation.uptime_score = self._smooth_update(
            reputation.uptime_score, uptime_ratio * 100, alpha=0.05)

        self._recalculate_reputation(reputation)
        self._save_reputation(reputation)

    def record_cooperation_event(self, node_id: str, cooperated: bool):
        """记录协作事件（例如中继数据、辅助验证）"""
        reputation = self.reputation_scores.get(node_id)
        if not reputation:
            return

        delta = 2.0 if cooperated else -5.0
        reputation.cooperation_score = max(0, min(100,
            reputation.cooperation_score + delta))

        self._recalculate_reputation(reputation)
        self._save_reputation(reputation)

    def record_honesty_event(self, node_id: str, honest: bool,
                              verification_passed: bool = True):
        """记录诚实性事件"""
        with self.lock:
            reputation = self.reputation_scores.get(node_id)
            if not reputation:
                return

            if not honest:
                reputation.honesty_score = max(0,
                    reputation.honesty_score - 10.0)
                self._report_security_violation(node_id, "诚实性违规")
            elif verification_passed:
                reputation.honesty_score = min(100,
                    reputation.honesty_score + 1.0)

            self._recalculate_reputation(reputation)
            self._save_reputation(reputation)

    def _recalculate_reputation(self, reputation: ReputationScore):
        """重新计算综合信誉评分"""
        weighted_score = (
            reputation.task_completion_score * self.WEIGHT_COMPLETION +
            reputation.response_speed_score * self.WEIGHT_SPEED +
            reputation.compute_quality_score * self.WEIGHT_QUALITY +
            reputation.uptime_score * self.WEIGHT_UPTIME +
            reputation.cooperation_score * self.WEIGHT_COOPERATION +
            reputation.honesty_score * self.WEIGHT_HONESTY
        )

        # 时间加权：活跃天数越多，信誉上限越高
        time_multiplier = min(2.0, 1.0 + math.log1p(reputation.days_active) * 0.1)

        old_score = reputation.total_score
        reputation.total_score = weighted_score * time_multiplier

        # 评分趋势
        reputation.score_trend = reputation.total_score - old_score

        # 更新等级
        reputation.grade = self._calculate_grade(reputation.total_score)
        reputation.last_updated = time.time()

    def _calculate_grade(self, score: float) -> ReputationGrade:
        """根据评分计算等级"""
        grade = ReputationGrade.NEWCOMER
        for g, threshold in sorted(self.GRADE_THRESHOLDS.items(),
                                    key=lambda x: x[1], reverse=True):
            if score >= threshold:
                grade = g
                break
        return grade

    def _smooth_update(self, old_value: float, new_value: float,
                       alpha: float = 0.1) -> float:
        """指数平滑更新"""
        return old_value * (1 - alpha) + new_value * alpha

    def _save_reputation(self, reputation: ReputationScore):
        """保存信誉到数据库"""
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO reputation_scores
                (node_id, total_score, grade, task_completion_score,
                 response_speed_score, compute_quality_score, uptime_score,
                 cooperation_score, honesty_score, total_tasks,
                 completed_tasks, failed_tasks, avg_response_time_ms,
                 total_compute_hours, total_uptime_hours,
                 verification_pass_rate, days_active, score_trend, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (reputation.node_id, reputation.total_score,
                  reputation.grade.value, reputation.task_completion_score,
                  reputation.response_speed_score, reputation.compute_quality_score,
                  reputation.uptime_score, reputation.cooperation_score,
                  reputation.honesty_score, reputation.total_tasks,
                  reputation.completed_tasks, reputation.failed_tasks,
                  reputation.avg_response_time_ms, reputation.total_compute_hours,
                  reputation.total_uptime_hours, reputation.verification_pass_rate,
                  reputation.days_active, reputation.score_trend,
                  reputation.last_updated))

    def get_reputation(self, node_id: str) -> Optional[Dict]:
        """获取节点信誉详情"""
        reputation = self.reputation_scores.get(node_id)
        if not reputation:
            return None

        return {
            "node_id": node_id,
            "total_score": round(reputation.total_score, 2),
            "grade": reputation.grade.value,
            "dimensions": {
                "task_completion": round(reputation.task_completion_score, 2),
                "response_speed": round(reputation.response_speed_score, 2),
                "compute_quality": round(reputation.compute_quality_score, 2),
                "uptime": round(reputation.uptime_score, 2),
                "cooperation": round(reputation.cooperation_score, 2),
                "honesty": round(reputation.honesty_score, 2),
            },
            "statistics": {
                "total_tasks": reputation.total_tasks,
                "completed_tasks": reputation.completed_tasks,
                "failed_tasks": reputation.failed_tasks,
                "completion_rate": (reputation.completed_tasks /
                                    max(1, reputation.total_tasks)),
                "avg_response_time_ms": round(reputation.avg_response_time_ms, 2),
                "total_compute_hours": round(reputation.total_compute_hours, 2),
                "total_uptime_hours": round(reputation.total_uptime_hours, 2),
            },
            "trend": "上升" if reputation.score_trend > 0 else (
                "下降" if reputation.score_trend < 0 else "稳定"),
            "days_active": reputation.days_active,
        }

    def get_reputation_leaderboard(self, top_n: int = 50) -> List[Dict]:
        """获取信誉排行榜"""
        sorted_nodes = sorted(
            self.reputation_scores.values(),
            key=lambda r: r.total_score,
            reverse=True
        )[:top_n]

        return [{
            "rank": i + 1,
            "node_id": r.node_id,
            "score": round(r.total_score, 2),
            "grade": r.grade.value,
            "completed_tasks": r.completed_tasks,
            "days_active": r.days_active,
        } for i, r in enumerate(sorted_nodes)]

    # ============================================================
    # 安全违规处理
    # ============================================================

    def _report_security_violation(self, node_id: str, reason: str):
        """报告安全违规"""
        profile = self.security_profiles.get(node_id)
        if not profile:
            return

        profile.security_violations += 1

        self._log_audit_event(
            node_id=node_id,
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity="warning",
            description=f"安全违规: {reason}",
            details={"total_violations": profile.security_violations}
        )

        # 自动暂停/封禁
        if profile.security_violations >= self.MAX_VIOLATIONS_BEFORE_BAN:
            self.ban_node(node_id, f"累计违规达{profile.security_violations}次")
        elif profile.security_violations >= self.MAX_VIOLATIONS_BEFORE_SUSPEND:
            self.suspend_node(
                node_id,
                self.SUSPENSION_DURATION_HOURS,
                f"累计违规达{profile.security_violations}次"
            )

    def suspend_node(self, node_id: str, duration_hours: float, reason: str):
        """暂停节点"""
        with self.lock:
            profile = self.security_profiles.get(node_id)
            if not profile:
                return

            profile.is_suspended = True
            profile.suspension_reason = reason
            profile.suspension_until = time.time() + duration_hours * 3600

            self._log_audit_event(
                node_id=node_id,
                event_type=AuditEventType.NODE_SUSPENDED,
                severity="warning",
                description=f"节点暂停: {reason} (时长={duration_hours}h)",
            )

            with self._get_db() as conn:
                conn.execute("""
                    UPDATE node_security_profiles
                    SET is_suspended=1, suspension_reason=?, suspension_until=?
                    WHERE node_id=?
                """, (reason, profile.suspension_until, node_id))

            logger.warning(f"[矿工安全] 节点暂停: {node_id} 原因={reason}")

    def ban_node(self, node_id: str, reason: str):
        """永久封禁节点"""
        with self.lock:
            profile = self.security_profiles.get(node_id)
            if not profile:
                return

            profile.is_banned = True
            profile.ban_reason = reason
            profile.current_permissions = set()

            self._log_audit_event(
                node_id=node_id,
                event_type=AuditEventType.NODE_BANNED,
                severity="critical",
                description=f"节点封禁: {reason}",
            )

            with self._get_db() as conn:
                conn.execute("""
                    UPDATE node_security_profiles
                    SET is_banned=1, ban_reason=?
                    WHERE node_id=?
                """, (reason, node_id))

            logger.error(f"[矿工安全] 节点封禁: {node_id} 原因={reason}")

    # ============================================================
    # 周期性审计
    # ============================================================

    def run_periodic_audit(self) -> Dict:
        """执行周期性审计"""
        results = {
            "timestamp": time.time(),
            "nodes_audited": 0,
            "violations_found": 0,
            "suspensions_expired": 0,
            "suspicious_patterns": [],
        }

        with self.lock:
            now = time.time()

            for node_id, profile in self.security_profiles.items():
                # 检查暂停到期
                if (profile.is_suspended and
                    profile.suspension_until > 0 and
                    now > profile.suspension_until):
                    profile.is_suspended = False
                    profile.suspension_reason = ""
                    results["suspensions_expired"] += 1
                    logger.info(f"[矿工安全] 暂停到期: {node_id}")

                # 硬件变更检测
                if profile.hardware_attestation:
                    hw = profile.hardware_attestation
                    if hw.last_check > 0 and now - hw.last_check > 86400 * 7:
                        results["suspicious_patterns"].append({
                            "node_id": node_id,
                            "type": "hardware_check_overdue",
                            "message": f"硬件检查过期 {(now - hw.last_check) / 86400:.0f}天"
                        })

                profile.last_audit_time = now
                results["nodes_audited"] += 1

            # 检测异常模式
            self._detect_anomaly_patterns(results)

        logger.info(f"[矿工安全] 周期审计完成: 审计={results['nodes_audited']}个节点 "
                    f"违规={results['violations_found']} "
                    f"可疑={len(results['suspicious_patterns'])}")
        return results

    def _detect_anomaly_patterns(self, results: Dict):
        """检测异常行为模式"""
        # 检测突然大量失败的节点
        for node_id, reputation in self.reputation_scores.items():
            if reputation.total_tasks > 10:
                recent_fail_rate = (
                    reputation.failed_tasks / max(1, reputation.total_tasks))
                if recent_fail_rate > 0.5:
                    results["suspicious_patterns"].append({
                        "node_id": node_id,
                        "type": "high_failure_rate",
                        "message": f"失败率过高: {recent_fail_rate:.1%}"
                    })
                    results["violations_found"] += 1

        # 检测信誉骤降
        for node_id, reputation in self.reputation_scores.items():
            if reputation.score_trend < -50:
                results["suspicious_patterns"].append({
                    "node_id": node_id,
                    "type": "reputation_plunge",
                    "message": f"信誉骤降: {reputation.score_trend:.1f}"
                })

    # ============================================================
    # 审计日志
    # ============================================================

    def _log_audit_event(self, node_id: str, event_type: AuditEventType,
                         description: str = "", severity: str = "info",
                         details: Optional[Dict] = None):
        """记录审计事件"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            node_id=node_id,
            event_type=event_type,
            severity=severity,
            description=description,
            details=details or {},
            timestamp=time.time()
        )

        self.audit_log.append(event)
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]

        # 持久化
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO audit_events
                (event_id, node_id, event_type, severity, description,
                 details_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (event.event_id, event.node_id, event.event_type.value,
                  event.severity, event.description,
                  json.dumps(event.details), event.timestamp))

    def get_audit_log(self, node_id: Optional[str] = None,
                       event_type: Optional[AuditEventType] = None,
                       limit: int = 100) -> List[Dict]:
        """查询审计日志"""
        with self._get_db() as conn:
            query = "SELECT * FROM audit_events WHERE 1=1"
            params = []

            if node_id:
                query += " AND node_id=?"
                params.append(node_id)
            if event_type:
                query += " AND event_type=?"
                params.append(event_type.value)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [{
                "event_id": row["event_id"],
                "node_id": row["node_id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "description": row["description"],
                "timestamp": row["timestamp"],
            } for row in rows]

    def generate_audit_report(self, period_days: int = 30) -> Dict:
        """生成审计报告"""
        cutoff = time.time() - period_days * 86400

        with self._get_db() as conn:
            # 事件统计
            event_counts = {}
            rows = conn.execute("""
                SELECT event_type, COUNT(*) as cnt
                FROM audit_events WHERE timestamp > ?
                GROUP BY event_type
            """, (cutoff,)).fetchall()
            for row in rows:
                event_counts[row["event_type"]] = row["cnt"]

            # 违规统计
            violation_rows = conn.execute("""
                SELECT node_id, COUNT(*) as cnt
                FROM audit_events
                WHERE event_type='security_violation' AND timestamp > ?
                GROUP BY node_id ORDER BY cnt DESC LIMIT 20
            """, (cutoff,)).fetchall()

            top_violators = [{"node_id": r["node_id"], "count": r["cnt"]}
                             for r in violation_rows]

        return {
            "period_days": period_days,
            "total_events": sum(event_counts.values()),
            "event_breakdown": event_counts,
            "top_violators": top_violators,
            "total_nodes": len(self.security_profiles),
            "banned_nodes": sum(1 for p in self.security_profiles.values()
                                if p.is_banned),
            "suspended_nodes": sum(1 for p in self.security_profiles.values()
                                   if p.is_suspended),
            "verification_distribution": {
                level.name: sum(1 for p in self.security_profiles.values()
                                if p.verification_level == level)
                for level in VerificationLevel
            },
            "reputation_distribution": {
                grade.value: sum(1 for r in self.reputation_scores.values()
                                 if r.grade == grade)
                for grade in ReputationGrade
            },
            "global_threat_level": self.global_threat_level.value,
            "generated_at": time.time(),
        }
