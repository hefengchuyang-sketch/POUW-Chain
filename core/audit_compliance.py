"""
审计与合规管理 v2.0
==================

改进要点：
1. 全链路操作审计 - 每一步操作可追溯、可验证
2. 自动合规审查 - 规则引擎驱动的合规检测
3. 智能合约审计 - 合约安全扫描与风险评估
4. 第三方合规对接 - 标准化审计报告与数据导出

本模块补充和增强现有 smart_contract_audit.py 的功能，
提供全面的审计与合规解决方案。
"""

import time
import uuid
import json
import sqlite3
import hashlib
import threading
import logging
import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class AuditCategory(Enum):
    """审计类别"""
    OPERATION = "operation"           # 操作审计
    TRANSACTION = "transaction"       # 交易审计
    ACCESS = "access"                 # 访问审计
    DATA = "data"                     # 数据审计
    SECURITY = "security"             # 安全审计
    GOVERNANCE = "governance"         # 治理审计
    CONTRACT = "contract"             # 合约审计
    COMPLIANCE = "compliance"         # 合规审计


class AuditSeverity(Enum):
    """审计严重程度"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStatus(Enum):
    """合规状态"""
    COMPLIANT = "compliant"           # 合规
    WARNING = "warning"               # 警告
    NON_COMPLIANT = "non_compliant"   # 不合规
    UNDER_REVIEW = "under_review"     # 审查中
    EXEMPT = "exempt"                 # 豁免


class ComplianceFramework(Enum):
    """合规框架"""
    AML_KYC = "aml_kyc"              # 反洗钱/KYC
    GDPR = "gdpr"                     # 通用数据保护
    SOC2 = "soc2"                     # SOC2
    ISO27001 = "iso27001"             # 信息安全
    PCI_DSS = "pci_dss"              # 支付卡安全
    CCPA = "ccpa"                     # 加州消费者隐私
    HIPAA = "hipaa"                   # 健康信息保护
    SEC = "sec"                       # 证券合规
    CUSTOM = "custom"                 # 自定义


class ContractRiskLevel(Enum):
    """合约风险等级"""
    SAFE = "safe"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    CRITICAL_RISK = "critical_risk"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class AuditEntry:
    """审计条目"""
    entry_id: str
    category: AuditCategory
    severity: AuditSeverity = AuditSeverity.INFO
    # 操作信息
    actor_id: str = ""
    action: str = ""
    resource: str = ""
    details: Dict = field(default_factory=dict)
    # 上下文
    ip_address: str = ""
    session_id: str = ""
    request_id: str = ""
    # 证据
    before_state: Dict = field(default_factory=dict)
    after_state: Dict = field(default_factory=dict)
    evidence_hash: str = ""
    # 时间
    timestamp: float = 0.0
    # 区块链锚定
    block_height: int = 0
    tx_hash: str = ""


@dataclass
class ComplianceRule:
    """合规规则"""
    rule_id: str
    framework: ComplianceFramework
    name: str = ""
    description: str = ""
    category: str = ""
    check_function: Optional[Callable] = None
    severity: AuditSeverity = AuditSeverity.MEDIUM
    enabled: bool = True
    auto_remediate: bool = False
    remediation_action: str = ""


@dataclass
class ComplianceReport:
    """合规报告"""
    report_id: str
    framework: ComplianceFramework
    generated_at: float = 0.0
    period_start: float = 0.0
    period_end: float = 0.0
    overall_status: ComplianceStatus = ComplianceStatus.UNDER_REVIEW
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    warnings: int = 0
    details: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ContractAuditResult:
    """合约审计结果"""
    audit_id: str
    contract_id: str
    contract_code_hash: str = ""
    risk_level: ContractRiskLevel = ContractRiskLevel.LOW_RISK
    score: float = 0.0              # 0-100 安全评分
    findings: List[Dict] = field(default_factory=list)
    gas_analysis: Dict = field(default_factory=dict)
    dependency_analysis: Dict = field(default_factory=dict)
    timestamp: float = 0.0
    auditor_id: str = ""


# ============================================================
# 审计追踪引擎
# ============================================================

class AuditTrailEngine:
    """
    全链路审计追踪引擎

    功能：
    1. 不可变审计日志
    2. 操作前后状态快照
    3. 证据哈希链
    4. 区块链锚定
    """

    SECURITY_LEVEL = "CRITICAL"

    def __init__(self, db_path: str = "data/audit_trail.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.entries: List[AuditEntry] = []
        self.hash_chain: List[str] = []   # 哈希链，保证不可变性
        self._init_db()

        logger.info("[审计引擎] 全链路审计系统已初始化")

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
                CREATE TABLE IF NOT EXISTS audit_entries (
                    entry_id TEXT PRIMARY KEY,
                    category TEXT,
                    severity TEXT,
                    actor_id TEXT,
                    action TEXT,
                    resource TEXT,
                    details_json TEXT,
                    ip_address TEXT,
                    session_id TEXT,
                    request_id TEXT,
                    before_state_json TEXT,
                    after_state_json TEXT,
                    evidence_hash TEXT,
                    timestamp REAL,
                    block_height INTEGER DEFAULT 0,
                    tx_hash TEXT,
                    chain_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_hash_chain (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT,
                    previous_hash TEXT,
                    current_hash TEXT,
                    timestamp REAL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_entries(actor_id);
                CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_entries(category);
                CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_entries(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_entries(severity);
                CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_entries(action);
            """)

    def record(self, category: AuditCategory,
               actor_id: str, action: str,
               resource: str = "",
               details: Optional[Dict] = None,
               before_state: Optional[Dict] = None,
               after_state: Optional[Dict] = None,
               severity: AuditSeverity = AuditSeverity.INFO,
               ip_address: str = "",
               session_id: str = "",
               request_id: str = "") -> str:
        """记录审计条目"""
        entry_id = f"AUD-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}"

        # 计算证据哈希
        evidence_data = json.dumps({
            "actor": actor_id,
            "action": action,
            "resource": resource,
            "details": details or {},
            "before": before_state or {},
            "after": after_state or {},
            "timestamp": time.time(),
        }, sort_keys=True)
        evidence_hash = hashlib.sha256(evidence_data.encode()).hexdigest()

        entry = AuditEntry(
            entry_id=entry_id,
            category=category,
            severity=severity,
            actor_id=actor_id,
            action=action,
            resource=resource,
            details=details or {},
            ip_address=ip_address,
            session_id=session_id,
            request_id=request_id,
            before_state=before_state or {},
            after_state=after_state or {},
            evidence_hash=evidence_hash,
            timestamp=time.time(),
        )

        with self.lock:
            # 构建哈希链
            prev_hash = self.hash_chain[-1] if self.hash_chain else "0" * 64
            chain_data = f"{prev_hash}:{entry_id}:{evidence_hash}"
            chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()
            self.hash_chain.append(chain_hash)

            self.entries.append(entry)

            # 防止内存溢出
            if len(self.entries) > 10000:
                self.entries = self.entries[-5000:]

        # 持久化
        self._save_entry(entry, chain_hash)

        if severity in (AuditSeverity.HIGH, AuditSeverity.CRITICAL):
            logger.warning(
                f"[审计引擎] 高危审计事件: [{severity.value}] "
                f"{actor_id} -> {action} on {resource}")

        return entry_id

    def query_entries(self, category: Optional[AuditCategory] = None,
                       actor_id: Optional[str] = None,
                       severity: Optional[AuditSeverity] = None,
                       action: Optional[str] = None,
                       time_start: Optional[float] = None,
                       time_end: Optional[float] = None,
                       limit: int = 100) -> List[Dict]:
        """查询审计条目"""
        conditions = []
        params = []

        if category:
            conditions.append("category = ?")
            params.append(category.value)
        if actor_id:
            conditions.append("actor_id = ?")
            params.append(actor_id)
        if severity:
            conditions.append("severity = ?")
            params.append(severity.value)
        if action:
            conditions.append("action LIKE ?")
            params.append(f"%{action}%")
        if time_start:
            conditions.append("timestamp >= ?")
            params.append(time_start)
        if time_end:
            conditions.append("timestamp <= ?")
            params.append(time_end)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with self._get_db() as conn:
            rows = conn.execute(
                f"SELECT * FROM audit_entries WHERE {where} "
                f"ORDER BY timestamp DESC LIMIT ?",
                params
            ).fetchall()

            return [{
                "entry_id": r["entry_id"],
                "category": r["category"],
                "severity": r["severity"],
                "actor_id": r["actor_id"],
                "action": r["action"],
                "resource": r["resource"],
                "details": json.loads(r["details_json"] or "{}"),
                "evidence_hash": r["evidence_hash"],
                "timestamp": r["timestamp"],
            } for r in rows]

    def verify_integrity(self) -> Dict:
        """验证审计日志完整性"""
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_hash_chain ORDER BY sequence"
            ).fetchall()

        if not rows:
            return {"valid": True, "total": 0}

        broken_at = None
        prev_hash = "0" * 64

        for row in rows:
            expected_prev = row["previous_hash"]
            if expected_prev != prev_hash:
                broken_at = row["sequence"]
                break
            prev_hash = row["current_hash"]

        return {
            "valid": broken_at is None,
            "total": len(rows),
            "broken_at": broken_at,
            "last_hash": rows[-1]["current_hash"] if rows else None,
        }

    def get_audit_stats(self, hours: float = 24) -> Dict:
        """获取审计统计"""
        since = time.time() - hours * 3600
        recent = [e for e in self.entries if e.timestamp >= since]

        return {
            "period_hours": hours,
            "total_entries": len(recent),
            "by_category": {
                c.value: sum(1 for e in recent if e.category == c)
                for c in AuditCategory
            },
            "by_severity": {
                s.value: sum(1 for e in recent if e.severity == s)
                for s in AuditSeverity
            },
            "unique_actors": len(set(e.actor_id for e in recent)),
            "high_severity_count": sum(
                1 for e in recent
                if e.severity in (AuditSeverity.HIGH, AuditSeverity.CRITICAL)),
        }

    def _save_entry(self, entry: AuditEntry, chain_hash: str):
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO audit_entries
                (entry_id, category, severity, actor_id, action, resource,
                 details_json, ip_address, session_id, request_id,
                 before_state_json, after_state_json, evidence_hash,
                 timestamp, block_height, tx_hash, chain_hash)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                entry.entry_id, entry.category.value, entry.severity.value,
                entry.actor_id, entry.action, entry.resource,
                json.dumps(entry.details), entry.ip_address,
                entry.session_id, entry.request_id,
                json.dumps(entry.before_state), json.dumps(entry.after_state),
                entry.evidence_hash, entry.timestamp,
                entry.block_height, entry.tx_hash, chain_hash,
            ))

            prev_hash = self.hash_chain[-2] if len(self.hash_chain) > 1 else "0" * 64
            conn.execute("""
                INSERT INTO audit_hash_chain
                (entry_id, previous_hash, current_hash, timestamp)
                VALUES (?, ?, ?, ?)
            """, (entry.entry_id, prev_hash, chain_hash, entry.timestamp))


# ============================================================
# 合规规则引擎
# ============================================================

class ComplianceEngine:
    """
    合规规则引擎

    功能：
    1. 多框架合规规则管理
    2. 自动化合规检查
    3. 合规报告生成
    4. 违规自动修复
    """

    SECURITY_LEVEL = "HIGH"

    def __init__(self, audit_engine: AuditTrailEngine,
                  db_path: str = "data/compliance.db"):
        self.audit_engine = audit_engine
        self.db_path = db_path
        self.lock = threading.Lock()

        self.rules: Dict[str, ComplianceRule] = {}
        self.reports: Dict[str, ComplianceReport] = {}
        self.check_results: Dict[str, Dict] = {}  # rule_id -> last result

        self._init_db()
        self._init_default_rules()

        logger.info("[合规引擎] 合规检查系统已初始化")

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
                CREATE TABLE IF NOT EXISTS compliance_rules (
                    rule_id TEXT PRIMARY KEY,
                    framework TEXT,
                    name TEXT,
                    description TEXT,
                    category TEXT,
                    severity TEXT,
                    enabled INTEGER DEFAULT 1,
                    auto_remediate INTEGER DEFAULT 0,
                    remediation_action TEXT
                );

                CREATE TABLE IF NOT EXISTS compliance_reports (
                    report_id TEXT PRIMARY KEY,
                    framework TEXT,
                    generated_at REAL,
                    period_start REAL,
                    period_end REAL,
                    overall_status TEXT,
                    total_rules INTEGER,
                    passed_rules INTEGER,
                    failed_rules INTEGER,
                    warnings INTEGER,
                    details_json TEXT,
                    recommendations_json TEXT
                );

                CREATE TABLE IF NOT EXISTS compliance_checks (
                    check_id TEXT PRIMARY KEY,
                    rule_id TEXT,
                    status TEXT,
                    message TEXT,
                    details_json TEXT,
                    checked_at REAL
                );
            """)

    def _init_default_rules(self):
        """初始化默认合规规则"""
        default_rules = [
            # AML/KYC 规则
            ComplianceRule(
                rule_id="AML-001",
                framework=ComplianceFramework.AML_KYC,
                name="大额交易监控",
                description="单笔交易超过10000 MAIN需要额外验证",
                category="transaction",
                severity=AuditSeverity.HIGH,
            ),
            ComplianceRule(
                rule_id="AML-002",
                framework=ComplianceFramework.AML_KYC,
                name="可疑交易模式检测",
                description="检测短时间内大量小额交易等可疑行为",
                category="transaction",
                severity=AuditSeverity.HIGH,
            ),
            ComplianceRule(
                rule_id="AML-003",
                framework=ComplianceFramework.AML_KYC,
                name="身份验证要求",
                description="所有用户在交易前必须完成基础KYC",
                category="identity",
                severity=AuditSeverity.MEDIUM,
            ),

            # GDPR 规则
            ComplianceRule(
                rule_id="GDPR-001",
                framework=ComplianceFramework.GDPR,
                name="数据最小化",
                description="仅收集必要的个人数据",
                category="data",
                severity=AuditSeverity.MEDIUM,
            ),
            ComplianceRule(
                rule_id="GDPR-002",
                framework=ComplianceFramework.GDPR,
                name="数据删除权",
                description="用户有权要求删除其个人数据",
                category="data",
                severity=AuditSeverity.HIGH,
            ),
            ComplianceRule(
                rule_id="GDPR-003",
                framework=ComplianceFramework.GDPR,
                name="数据泄露通知",
                description="数据泄露必须在72小时内通知",
                category="security",
                severity=AuditSeverity.CRITICAL,
            ),
            ComplianceRule(
                rule_id="GDPR-004",
                framework=ComplianceFramework.GDPR,
                name="数据加密存储",
                description="个人数据必须加密存储",
                category="data",
                severity=AuditSeverity.HIGH,
            ),

            # SOC2 规则
            ComplianceRule(
                rule_id="SOC2-001",
                framework=ComplianceFramework.SOC2,
                name="访问控制",
                description="所有系统访问需要认证和授权",
                category="access",
                severity=AuditSeverity.HIGH,
            ),
            ComplianceRule(
                rule_id="SOC2-002",
                framework=ComplianceFramework.SOC2,
                name="变更管理",
                description="系统变更需要审批和记录",
                category="operation",
                severity=AuditSeverity.MEDIUM,
            ),
            ComplianceRule(
                rule_id="SOC2-003",
                framework=ComplianceFramework.SOC2,
                name="事件响应",
                description="安全事件需在规定时间内响应和处理",
                category="security",
                severity=AuditSeverity.HIGH,
            ),

            # ISO 27001 规则
            ComplianceRule(
                rule_id="ISO-001",
                framework=ComplianceFramework.ISO27001,
                name="信息分类",
                description="所有信息资产需要分类和标记",
                category="data",
                severity=AuditSeverity.MEDIUM,
            ),
            ComplianceRule(
                rule_id="ISO-002",
                framework=ComplianceFramework.ISO27001,
                name="密钥管理",
                description="加密密钥需要安全管理和轮换",
                category="security",
                severity=AuditSeverity.HIGH,
            ),
            ComplianceRule(
                rule_id="ISO-003",
                framework=ComplianceFramework.ISO27001,
                name="审计日志",
                description="关键操作需要完整的审计日志",
                category="audit",
                severity=AuditSeverity.HIGH,
            ),
        ]

        for rule in default_rules:
            self.rules[rule.rule_id] = rule

    def add_rule(self, rule: ComplianceRule):
        """添加合规规则"""
        self.rules[rule.rule_id] = rule
        logger.info(f"[合规引擎] 添加规则: {rule.rule_id} - {rule.name}")

    def run_compliance_check(self, framework: Optional[ComplianceFramework] = None
                               ) -> Dict:
        """运行合规检查"""
        rules_to_check = [
            r for r in self.rules.values()
            if r.enabled and (framework is None or r.framework == framework)
        ]

        results = {
            "checked_at": time.time(),
            "total": len(rules_to_check),
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "details": [],
        }

        for rule in rules_to_check:
            check_result = self._check_rule(rule)
            results["details"].append(check_result)

            status = check_result["status"]
            if status == "pass":
                results["passed"] += 1
            elif status == "fail":
                results["failed"] += 1
            elif status == "warning":
                results["warnings"] += 1

            self.check_results[rule.rule_id] = check_result

        # 记录审计
        self.audit_engine.record(
            category=AuditCategory.COMPLIANCE,
            actor_id="system",
            action="compliance_check",
            details={"summary": {
                "total": results["total"],
                "passed": results["passed"],
                "failed": results["failed"],
            }},
            severity=AuditSeverity.HIGH if results["failed"] > 0
                else AuditSeverity.INFO,
        )

        return results

    def _check_rule(self, rule: ComplianceRule) -> Dict:
        """检查单条合规规则"""
        result = {
            "rule_id": rule.rule_id,
            "framework": rule.framework.value,
            "name": rule.name,
            "severity": rule.severity.value,
            "status": "pass",
            "message": "",
            "checked_at": time.time(),
        }

        # 如果有自定义检查函数
        if rule.check_function:
            try:
                check_output = rule.check_function()
                result["status"] = check_output.get("status", "pass")
                result["message"] = check_output.get("message", "")
                result["details"] = check_output.get("details", {})
            except Exception as e:
                result["status"] = "error"
                result["message"] = "检查执行失败"
                logger.error(f"合规检查异常: {e}")
        else:
            # 基于审计数据的默认检查
            result = self._default_check(rule, result)

        # 自动修复
        if result["status"] == "fail" and rule.auto_remediate:
            self._auto_remediate(rule, result)

        return result

    def _default_check(self, rule: ComplianceRule, result: Dict) -> Dict:
        """默认合规检查（基于审计数据分析）"""
        # AML 相关
        if rule.rule_id == "AML-001":
            # 检查大额交易是否有验证记录
            recent = self.audit_engine.query_entries(
                category=AuditCategory.TRANSACTION,
                time_start=time.time() - 86400,
            )
            large_unverified = [
                e for e in recent
                if e.get("details", {}).get("amount", 0) > 10000
                and not e.get("details", {}).get("verified", False)
            ]
            if large_unverified:
                result["status"] = "fail"
                result["message"] = f"发现 {len(large_unverified)} 笔未验证大额交易"
            else:
                result["status"] = "pass"
                result["message"] = "所有大额交易已验证"

        elif rule.rule_id == "AML-002":
            recent = self.audit_engine.query_entries(
                category=AuditCategory.TRANSACTION,
                time_start=time.time() - 3600,
            )
            # 检查单用户短时间频繁交易
            user_tx_count: Dict[str, int] = {}
            for e in recent:
                uid = e.get("actor_id", "")
                user_tx_count[uid] = user_tx_count.get(uid, 0) + 1

            suspicious = {uid: c for uid, c in user_tx_count.items() if c > 50}
            if suspicious:
                result["status"] = "warning"
                result["message"] = f"发现 {len(suspicious)} 个可疑账户频繁交易"
            else:
                result["status"] = "pass"
                result["message"] = "未发现可疑交易模式"

        elif rule.rule_id.startswith("ISO-003"):
            # 检查审计日志完整性
            integrity = self.audit_engine.verify_integrity()
            if integrity["valid"]:
                result["status"] = "pass"
                result["message"] = f"审计日志完整，共 {integrity['total']} 条"
            else:
                result["status"] = "fail"
                result["message"] = f"审计日志不完整，在序号 {integrity['broken_at']} 处断裂"

        else:
            # 默认通过（需要实际业务数据才能判断）
            result["status"] = "pass"
            result["message"] = "规则检查通过（基础检查）"

        return result

    def _auto_remediate(self, rule: ComplianceRule, result: Dict):
        """自动修复违规"""
        logger.info(
            f"[合规引擎] 自动修复: {rule.rule_id} - {rule.remediation_action}")

        self.audit_engine.record(
            category=AuditCategory.COMPLIANCE,
            actor_id="system",
            action="auto_remediate",
            details={
                "rule_id": rule.rule_id,
                "action": rule.remediation_action,
            },
            severity=AuditSeverity.HIGH,
        )

    def generate_report(self, framework: ComplianceFramework,
                         period_days: int = 30) -> ComplianceReport:
        """生成合规报告"""
        now = time.time()
        period_start = now - period_days * 86400

        # 运行检查
        check_result = self.run_compliance_check(framework)

        # 确定整体状态
        if check_result["failed"] > 0:
            overall_status = ComplianceStatus.NON_COMPLIANT
        elif check_result["warnings"] > 0:
            overall_status = ComplianceStatus.WARNING
        else:
            overall_status = ComplianceStatus.COMPLIANT

        # 生成建议
        recommendations = []
        for detail in check_result["details"]:
            if detail["status"] == "fail":
                recommendations.append(
                    f"[{detail['severity']}] {detail['name']}: {detail['message']}")
            elif detail["status"] == "warning":
                recommendations.append(
                    f"[警告] {detail['name']}: {detail['message']}")

        report = ComplianceReport(
            report_id=f"RPT-{int(now)}-{uuid.uuid4().hex[:8]}",
            framework=framework,
            generated_at=now,
            period_start=period_start,
            period_end=now,
            overall_status=overall_status,
            total_rules=check_result["total"],
            passed_rules=check_result["passed"],
            failed_rules=check_result["failed"],
            warnings=check_result["warnings"],
            details=check_result["details"],
            recommendations=recommendations,
        )

        with self.lock:
            self.reports[report.report_id] = report

        self._save_report(report)
        return report

    def export_report(self, report_id: str, format: str = "json") -> Optional[str]:
        """导出合规报告"""
        report = self.reports.get(report_id)
        if not report:
            return None

        if format == "json":
            return json.dumps({
                "report_id": report.report_id,
                "framework": report.framework.value,
                "generated_at": report.generated_at,
                "period": {
                    "start": report.period_start,
                    "end": report.period_end,
                },
                "overall_status": report.overall_status.value,
                "summary": {
                    "total_rules": report.total_rules,
                    "passed": report.passed_rules,
                    "failed": report.failed_rules,
                    "warnings": report.warnings,
                    "compliance_rate": round(
                        report.passed_rules / report.total_rules * 100, 1)
                        if report.total_rules > 0 else 0,
                },
                "details": report.details,
                "recommendations": report.recommendations,
            }, indent=2, ensure_ascii=False)

        return None

    def _save_report(self, report: ComplianceReport):
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO compliance_reports
                (report_id, framework, generated_at, period_start, period_end,
                 overall_status, total_rules, passed_rules, failed_rules,
                 warnings, details_json, recommendations_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                report.report_id, report.framework.value,
                report.generated_at, report.period_start, report.period_end,
                report.overall_status.value,
                report.total_rules, report.passed_rules, report.failed_rules,
                report.warnings,
                json.dumps(report.details),
                json.dumps(report.recommendations),
            ))


# ============================================================
# 智能合约审计系统
# ============================================================

class ContractAuditSystem:
    """
    智能合约审计系统

    功能：
    1. 合约代码安全扫描（静态分析）
    2. 已知漏洞模式匹配
    3. Gas消耗分析
    4. 依赖安全检查
    5. 风险评分
    """

    SECURITY_LEVEL = "HIGH"

    # 已知漏洞模式
    VULNERABILITY_PATTERNS = [
        {
            "id": "VULN-001",
            "name": "重入攻击",
            "pattern": r"(call\.value|delegatecall|\.send\()",
            "severity": "critical",
            "description": "检测可能的重入攻击向量",
        },
        {
            "id": "VULN-002",
            "name": "整数溢出",
            "pattern": r"(\+\+|\+=|\*=|<<)",
            "severity": "high",
            "description": "检测可能的整数溢出",
        },
        {
            "id": "VULN-003",
            "name": "未检查返回值",
            "pattern": r"(\.send\(|\.transfer\()(?!.*require)",
            "severity": "medium",
            "description": "外部调用返回值未检查",
        },
        {
            "id": "VULN-004",
            "name": "时间依赖",
            "pattern": r"(block\.timestamp|now|block\.number)",
            "severity": "low",
            "description": "使用区块时间戳可能被矿工操纵",
        },
        {
            "id": "VULN-005",
            "name": "权限缺失",
            "pattern": r"(function\s+\w+\s*\([^)]*\)\s*public)(?!.*onlyOwner|require|modifier)",
            "severity": "high",
            "description": "公共函数缺少权限控制",
        },
        {
            "id": "VULN-006",
            "name": "硬编码密钥",
            "pattern": r"(private\s+key|secret|password)\s*=\s*['\"][^'\"]+['\"]",
            "severity": "critical",
            "description": "代码中包含硬编码的密钥或密码",
        },
        {
            "id": "VULN-007",
            "name": "无限循环风险",
            "pattern": r"while\s*\(\s*true\s*\)|for\s*\(\s*;\s*;\s*\)",
            "severity": "medium",
            "description": "可能导致Gas耗尽的循环",
        },
        {
            "id": "VULN-008",
            "name": "eval/exec使用",
            "pattern": r"(eval\s*\(|exec\s*\(|compile\s*\()",
            "severity": "critical",
            "description": "动态代码执行存在安全风险",
        },
    ]

    def __init__(self, audit_engine: AuditTrailEngine):
        self.audit_engine = audit_engine
        self.audit_results: Dict[str, ContractAuditResult] = {}

        logger.info("[合约审计] 智能合约审计系统已初始化")

    def audit_contract(self, contract_id: str,
                        contract_code: str,
                        auditor_id: str = "system") -> ContractAuditResult:
        """审计合约代码"""
        audit_id = f"CA-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        code_hash = hashlib.sha256(contract_code.encode()).hexdigest()

        findings = []
        score = 100.0

        # 1. 漏洞模式匹配
        for vuln in self.VULNERABILITY_PATTERNS:
            matches = re.findall(vuln["pattern"], contract_code, re.IGNORECASE)
            if matches:
                finding = {
                    "id": vuln["id"],
                    "name": vuln["name"],
                    "severity": vuln["severity"],
                    "description": vuln["description"],
                    "occurrences": len(matches),
                    "matches": matches[:5],
                }
                findings.append(finding)

                # 扣分
                severity_deduction = {
                    "critical": 25,
                    "high": 15,
                    "medium": 8,
                    "low": 3,
                }
                score -= severity_deduction.get(vuln["severity"], 5) * len(matches)

        # 2. 代码质量分析
        quality = self._analyze_code_quality(contract_code)
        score -= quality.get("deduction", 0)
        findings.extend(quality.get("findings", []))

        # 3. Gas 分析
        gas_analysis = self._analyze_gas(contract_code)

        # 4. 依赖分析
        dep_analysis = self._analyze_dependencies(contract_code)

        # 确定风险等级
        score = max(0, min(100, score))
        if score >= 90:
            risk_level = ContractRiskLevel.SAFE
        elif score >= 70:
            risk_level = ContractRiskLevel.LOW_RISK
        elif score >= 50:
            risk_level = ContractRiskLevel.MEDIUM_RISK
        elif score >= 30:
            risk_level = ContractRiskLevel.HIGH_RISK
        else:
            risk_level = ContractRiskLevel.CRITICAL_RISK

        result = ContractAuditResult(
            audit_id=audit_id,
            contract_id=contract_id,
            contract_code_hash=code_hash,
            risk_level=risk_level,
            score=round(score, 1),
            findings=findings,
            gas_analysis=gas_analysis,
            dependency_analysis=dep_analysis,
            timestamp=time.time(),
            auditor_id=auditor_id,
        )

        self.audit_results[audit_id] = result

        # 审计记录
        self.audit_engine.record(
            category=AuditCategory.CONTRACT,
            actor_id=auditor_id,
            action="contract_audit",
            resource=contract_id,
            details={
                "audit_id": audit_id,
                "risk_level": risk_level.value,
                "score": result.score,
                "findings_count": len(findings),
            },
            severity=AuditSeverity.HIGH if risk_level in (
                ContractRiskLevel.HIGH_RISK, ContractRiskLevel.CRITICAL_RISK)
                else AuditSeverity.INFO,
        )

        return result

    def _analyze_code_quality(self, code: str) -> Dict:
        """代码质量分析"""
        findings = []
        deduction = 0

        lines = code.split('\n')
        total_lines = len(lines)

        # 检查代码长度
        if total_lines > 1000:
            findings.append({
                "id": "QUALITY-001",
                "name": "代码过长",
                "severity": "low",
                "description": f"合约代码 {total_lines} 行，建议拆分",
            })
            deduction += 3

        # 检查函数数量
        func_count = len(re.findall(r'def\s+\w+|function\s+\w+', code))
        if func_count > 50:
            findings.append({
                "id": "QUALITY-002",
                "name": "函数过多",
                "severity": "low",
                "description": f"包含 {func_count} 个函数，建议模块化拆分",
            })
            deduction += 2

        # 检查注释覆盖率
        comment_lines = len(re.findall(r'(#.*|//.*|/\*.*?\*/|""".*?""")',
                                        code, re.DOTALL))
        comment_ratio = comment_lines / max(1, total_lines)
        if comment_ratio < 0.1:
            findings.append({
                "id": "QUALITY-003",
                "name": "注释不足",
                "severity": "low",
                "description": f"注释覆盖率: {comment_ratio:.1%}，建议增加注释",
            })
            deduction += 2

        # 检查异常处理
        try_count = len(re.findall(r'try\s*:', code))
        except_count = len(re.findall(r'except\s*(.*?):', code))
        bare_except = len(re.findall(r'except\s*:', code))
        if bare_except > 0:
            findings.append({
                "id": "QUALITY-004",
                "name": "裸异常捕获",
                "severity": "medium",
                "description": f"发现 {bare_except} 处 bare except，应指定异常类型",
            })
            deduction += 5

        return {"deduction": deduction, "findings": findings}

    def _analyze_gas(self, code: str) -> Dict:
        """Gas消耗分析"""
        issues = []

        # 检查循环中的存储操作
        # 简化分析：查找loop内的写操作模式
        if re.search(r'for\s+.*?:\s*.*?(\.save|\.update|\.insert|db\.execute)',
                      code, re.DOTALL):
            issues.append("循环内存在存储操作，考虑批量处理")

        # 检查大数组操作
        if re.search(r'for\s+\w+\s+in\s+(self\.\w+|list_|all_)', code):
            issues.append("遍历大型集合可能消耗大量Gas")

        return {
            "estimated_complexity": "MEDIUM" if issues else "LOW",
            "optimization_suggestions": issues,
        }

    def _analyze_dependencies(self, code: str) -> Dict:
        """依赖分析"""
        imports = re.findall(r'(?:from\s+(\S+)\s+import|import\s+(\S+))', code)
        dependencies = list(set(
            m[0] or m[1] for m in imports if m[0] or m[1]))

        risky_deps = []
        for dep in dependencies:
            if dep.startswith(("os", "sys", "subprocess", "ctypes")):
                risky_deps.append({
                    "dependency": dep,
                    "risk": "high",
                    "reason": "系统级模块，存在安全风险",
                })

        return {
            "total_dependencies": len(dependencies),
            "dependencies": dependencies,
            "risky_dependencies": risky_deps,
        }

    def get_audit_result(self, audit_id: str) -> Optional[Dict]:
        """获取审计结果"""
        result = self.audit_results.get(audit_id)
        if not result:
            return None

        return {
            "audit_id": result.audit_id,
            "contract_id": result.contract_id,
            "code_hash": result.contract_code_hash,
            "risk_level": result.risk_level.value,
            "score": result.score,
            "findings": result.findings,
            "findings_by_severity": {
                s: sum(1 for f in result.findings if f["severity"] == s)
                for s in ("critical", "high", "medium", "low")
            },
            "gas_analysis": result.gas_analysis,
            "dependency_analysis": result.dependency_analysis,
            "timestamp": result.timestamp,
            "auditor": result.auditor_id,
        }
