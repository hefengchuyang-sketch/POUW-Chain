"""
smart_contract_audit.py - 智能合约审计与自动结算系统

Phase 10 功能：
1. 合约代码审计
2. 安全漏洞检测
3. 自动结算引擎
4. 财务透明追踪
5. 合约生命周期管理
6. 争议仲裁
"""

import time
import uuid
import hashlib
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


# ============== 枚举类型 ==============

class VulnerabilitySeverity(Enum):
    """漏洞严重性"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VulnerabilityType(Enum):
    """漏洞类型"""
    REENTRANCY = "reentrancy"
    OVERFLOW = "overflow"
    UNDERFLOW = "underflow"
    ACCESS_CONTROL = "access_control"
    FRONT_RUNNING = "front_running"
    DOS = "dos"
    LOGIC_ERROR = "logic_error"
    UNCHECKED_CALL = "unchecked_call"
    TIMESTAMP_DEPENDENCE = "timestamp_dependence"
    GAS_LIMIT = "gas_limit"


class ContractStatus(Enum):
    """合约状态"""
    DRAFT = "draft"
    AUDITING = "auditing"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"


class SettlementStatus(Enum):
    """结算状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DISPUTED = "disputed"


class DisputeStatus(Enum):
    """争议状态"""
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


# ============== 数据结构 ==============

@dataclass
class Vulnerability:
    """漏洞"""
    vuln_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 类型
    vuln_type: VulnerabilityType = VulnerabilityType.LOGIC_ERROR
    severity: VulnerabilitySeverity = VulnerabilitySeverity.LOW
    
    # 位置
    file_path: str = ""
    line_number: int = 0
    code_snippet: str = ""
    
    # 描述
    title: str = ""
    description: str = ""
    recommendation: str = ""
    
    # 状态
    confirmed: bool = False
    fixed: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "vuln_id": self.vuln_id,
            "type": self.vuln_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "line": self.line_number,
            "fixed": self.fixed,
        }


@dataclass
class AuditReport:
    """审计报告"""
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 合约
    contract_id: str = ""
    contract_hash: str = ""
    
    # 审计信息
    auditor_id: str = ""
    audit_version: str = "1.0"
    
    # 结果
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    passed: bool = False
    score: float = 0                   # 0-100
    
    # 统计
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    
    # 时间
    started_at: float = 0
    completed_at: float = 0
    
    # 建议
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "contract_id": self.contract_id,
            "passed": self.passed,
            "score": self.score,
            "vulnerabilities": {
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
                "info": self.info_count,
            },
            "completed_at": self.completed_at,
        }


@dataclass
class SmartContract:
    """智能合约"""
    contract_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    
    # 基本信息
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    
    # 代码
    source_code: str = ""
    bytecode: str = ""
    abi: Dict = field(default_factory=dict)
    code_hash: str = ""
    
    # 部署
    deployed_address: str = ""
    deployer: str = ""
    
    # 状态
    status: ContractStatus = ContractStatus.DRAFT
    
    # 审计
    audit_reports: List[str] = field(default_factory=list)
    last_audit_passed: bool = False
    
    # 权限
    owner: str = ""
    admins: List[str] = field(default_factory=list)
    
    # 时间
    created_at: float = field(default_factory=time.time)
    deployed_at: float = 0
    
    def compute_hash(self):
        """计算代码哈希"""
        self.code_hash = hashlib.sha256(self.source_code.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        return {
            "contract_id": self.contract_id,
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "code_hash": self.code_hash[:16] + "..." if self.code_hash else "",
            "last_audit_passed": self.last_audit_passed,
            "deployed_address": self.deployed_address,
        }


@dataclass
class Settlement:
    """结算记录"""
    settlement_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 合约
    contract_id: str = ""
    
    # 交易
    task_id: str = ""
    order_id: str = ""
    
    # 金额
    total_amount: int = 0
    fee_amount: int = 0
    net_amount: int = 0
    
    # 参与方
    payer: str = ""
    payee: str = ""
    
    # 分配
    distribution: Dict[str, int] = field(default_factory=dict)
    
    # 状态
    status: SettlementStatus = SettlementStatus.PENDING
    
    # 时间
    created_at: float = field(default_factory=time.time)
    processed_at: float = 0
    completed_at: float = 0
    
    # 交易哈希
    tx_hash: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "settlement_id": self.settlement_id,
            "contract_id": self.contract_id,
            "total_amount": self.total_amount,
            "status": self.status.value,
            "payer": self.payer,
            "payee": self.payee,
            "created_at": self.created_at,
        }


@dataclass
class Dispute:
    """争议"""
    dispute_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 关联
    settlement_id: str = ""
    contract_id: str = ""
    
    # 参与方
    initiator: str = ""
    respondent: str = ""
    
    # 争议内容
    reason: str = ""
    evidence: List[Dict] = field(default_factory=list)
    amount_disputed: int = 0
    
    # 仲裁
    arbitrator: str = ""
    ruling: str = ""
    
    # 状态
    status: DisputeStatus = DisputeStatus.OPEN
    
    # 时间
    created_at: float = field(default_factory=time.time)
    resolved_at: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "dispute_id": self.dispute_id,
            "settlement_id": self.settlement_id,
            "status": self.status.value,
            "initiator": self.initiator,
            "amount": self.amount_disputed,
            "created_at": self.created_at,
        }


# ============== 漏洞检测器 ==============

class VulnerabilityDetector:
    """漏洞检测器"""
    
    def __init__(self):
        # 检测规则
        self.rules: List[Dict] = self._init_rules()
    
    def _init_rules(self) -> List[Dict]:
        """初始化检测规则"""
        return [
            {
                "type": VulnerabilityType.REENTRANCY,
                "pattern": r"call\s*\(.*value.*\)|\.transfer\(|\.send\(",
                "severity": VulnerabilitySeverity.HIGH,
                "title": "Potential Reentrancy",
                "description": "External call before state update may allow reentrancy",
                "recommendation": "Use checks-effects-interactions pattern",
            },
            {
                "type": VulnerabilityType.OVERFLOW,
                "pattern": r"\+\+|\+=|[a-zA-Z_]+\s*\+\s*[a-zA-Z_]+",
                "severity": VulnerabilitySeverity.MEDIUM,
                "title": "Potential Integer Overflow",
                "description": "Arithmetic operation without overflow check",
                "recommendation": "Use SafeMath or Solidity 0.8+",
            },
            {
                "type": VulnerabilityType.ACCESS_CONTROL,
                "pattern": r"tx\.origin|owner\s*==|msg\.sender\s*==",
                "severity": VulnerabilitySeverity.HIGH,
                "title": "Access Control Issue",
                "description": "Weak access control pattern detected",
                "recommendation": "Use proper access control modifiers",
            },
            {
                "type": VulnerabilityType.TIMESTAMP_DEPENDENCE,
                "pattern": r"block\.timestamp|now\s*[<>=]",
                "severity": VulnerabilitySeverity.LOW,
                "title": "Timestamp Dependence",
                "description": "Block timestamp can be manipulated by miners",
                "recommendation": "Avoid using timestamp for critical logic",
            },
            {
                "type": VulnerabilityType.UNCHECKED_CALL,
                "pattern": r"\.call\(|\.delegatecall\(",
                "severity": VulnerabilitySeverity.MEDIUM,
                "title": "Unchecked Low-Level Call",
                "description": "Return value of low-level call not checked",
                "recommendation": "Always check return value of low-level calls",
            },
            {
                "type": VulnerabilityType.DOS,
                "pattern": r"for\s*\(.*length|while\s*\(",
                "severity": VulnerabilitySeverity.MEDIUM,
                "title": "Potential DoS",
                "description": "Unbounded loop may cause gas exhaustion",
                "recommendation": "Implement pagination or gas limits",
            },
        ]
    
    def analyze(self, source_code: str, file_path: str = "") -> List[Vulnerability]:
        """分析代码漏洞"""
        vulnerabilities = []
        lines = source_code.split("\n")
        
        for line_num, line in enumerate(lines, 1):
            for rule in self.rules:
                if re.search(rule["pattern"], line, re.IGNORECASE):
                    vuln = Vulnerability(
                        vuln_type=rule["type"],
                        severity=rule["severity"],
                        file_path=file_path,
                        line_number=line_num,
                        code_snippet=line.strip()[:100],
                        title=rule["title"],
                        description=rule["description"],
                        recommendation=rule["recommendation"],
                    )
                    vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    def calculate_score(self, vulnerabilities: List[Vulnerability]) -> float:
        """计算安全评分"""
        if not vulnerabilities:
            return 100.0
        
        # 权重
        weights = {
            VulnerabilitySeverity.CRITICAL: 25,
            VulnerabilitySeverity.HIGH: 15,
            VulnerabilitySeverity.MEDIUM: 8,
            VulnerabilitySeverity.LOW: 3,
            VulnerabilitySeverity.INFO: 1,
        }
        
        total_penalty = sum(weights.get(v.severity, 0) for v in vulnerabilities)
        score = max(0, 100 - total_penalty)
        
        return score


# ============== 合约审计器 ==============

class ContractAuditor:
    """合约审计器"""
    
    def __init__(self):
        self.detector = VulnerabilityDetector()
        self.auditor_id = f"auditor_{uuid.uuid4().hex[:8]}"
        
        # 审计记录
        self.reports: Dict[str, AuditReport] = {}
    
    def audit(self, contract: SmartContract) -> AuditReport:
        """执行审计"""
        report = AuditReport(
            contract_id=contract.contract_id,
            contract_hash=contract.code_hash or hashlib.sha256(contract.source_code.encode()).hexdigest(),
            auditor_id=self.auditor_id,
            started_at=time.time(),
        )
        
        # 检测漏洞
        vulnerabilities = self.detector.analyze(contract.source_code, contract.name)
        report.vulnerabilities = vulnerabilities
        
        # 统计
        for vuln in vulnerabilities:
            if vuln.severity == VulnerabilitySeverity.CRITICAL:
                report.critical_count += 1
            elif vuln.severity == VulnerabilitySeverity.HIGH:
                report.high_count += 1
            elif vuln.severity == VulnerabilitySeverity.MEDIUM:
                report.medium_count += 1
            elif vuln.severity == VulnerabilitySeverity.LOW:
                report.low_count += 1
            else:
                report.info_count += 1
        
        # 计算评分
        report.score = self.detector.calculate_score(vulnerabilities)
        
        # 判断是否通过
        report.passed = (
            report.critical_count == 0 and
            report.high_count == 0 and
            report.score >= 70
        )
        
        # 生成建议
        if report.critical_count > 0:
            report.recommendations.append("Fix all critical vulnerabilities before deployment")
        if report.high_count > 0:
            report.recommendations.append("Address high severity issues to improve security")
        if report.score < 80:
            report.recommendations.append("Consider a more thorough security review")
        
        report.completed_at = time.time()
        
        self.reports[report.report_id] = report
        
        return report


# ============== 自动结算引擎 ==============

class SettlementEngine:
    """自动结算引擎
    
    通过 transfer_fn 回调连接实际的区块链转账系统。
    """
    
    def __init__(self, transfer_fn=None):
        """
        Args:
            transfer_fn: 转账回调函数 (payer, payee, amount) -> tx_hash
                         如果为 None，使用内部记账模式（记录交易但不执行链上转账）
        """
        self.settlements: Dict[str, Settlement] = {}
        self.pending_queue: List[str] = []
        self.transfer_fn = transfer_fn
        
        # 费率配置
        self.platform_fee_rate = 0.02        # 平台费 2%
        self.min_fee = 1                      # 最低费用
        
        # 统计
        self.stats = {
            "total_settlements": 0,
            "total_volume": 0,
            "total_fees": 0,
            "successful": 0,
            "failed": 0,
        }
    
    def create_settlement(
        self,
        contract_id: str,
        task_id: str,
        payer: str,
        payee: str,
        amount: int,
        distribution: Dict[str, int] = None,
    ) -> Settlement:
        """创建结算"""
        fee = max(self.min_fee, int(amount * self.platform_fee_rate))
        
        settlement = Settlement(
            contract_id=contract_id,
            task_id=task_id,
            total_amount=amount,
            fee_amount=fee,
            net_amount=amount - fee,
            payer=payer,
            payee=payee,
            distribution=distribution or {payee: amount - fee},
        )
        
        self.settlements[settlement.settlement_id] = settlement
        self.pending_queue.append(settlement.settlement_id)
        self.stats["total_settlements"] += 1
        
        return settlement
    
    def process_settlement(self, settlement_id: str) -> Dict:
        """处理结算
        
        如果配置了 transfer_fn，通过区块链执行实际转账。
        否则使用内部记账模式（生成确定性交易哈希）。
        """
        settlement = self.settlements.get(settlement_id)
        if not settlement:
            return {"error": "Settlement not found"}
        
        settlement.status = SettlementStatus.PROCESSING
        settlement.processed_at = time.time()
        
        try:
            # 验证金额
            if settlement.total_amount <= 0:
                raise ValueError("Invalid amount")
            
            # 验证分配
            total_distributed = sum(settlement.distribution.values())
            if total_distributed != settlement.net_amount:
                raise ValueError("Distribution mismatch")
            
            # 执行转账
            if self.transfer_fn:
                # 通过区块链转账回调执行真实交易
                for payee_addr, amount in settlement.distribution.items():
                    tx_hash = self.transfer_fn(settlement.payer, payee_addr, amount)
                    if not tx_hash:
                        raise ValueError(f"Transfer failed: {settlement.payer} -> {payee_addr}")
                settlement.tx_hash = tx_hash  # 最后一笔交易的哈希
            else:
                # 内部记账模式：生成确定性交易哈希
                import hmac as _hmac
                tx_data = f"{settlement.settlement_id}:{settlement.payer}:{settlement.payee}:{settlement.total_amount}:{settlement.processed_at}"
                settlement.tx_hash = _hmac.new(
                    b"POUW_SETTLEMENT_V1",
                    tx_data.encode(),
                    hashlib.sha256,
                ).hexdigest()
            
            settlement.status = SettlementStatus.COMPLETED
            settlement.completed_at = time.time()
            
            self.stats["successful"] += 1
            self.stats["total_volume"] += settlement.total_amount
            self.stats["total_fees"] += settlement.fee_amount
            
            return {
                "status": "success",
                "settlement_id": settlement_id,
                "tx_hash": settlement.tx_hash,
            }
            
        except Exception as e:
            settlement.status = SettlementStatus.FAILED
            self.stats["failed"] += 1
            logger.error(f"结算处理失败: {e}")
            return {"error": "settlement_failed"}
    
    def process_pending(self) -> List[Dict]:
        """处理待处理结算"""
        results = []
        
        while self.pending_queue:
            settlement_id = self.pending_queue.pop(0)
            result = self.process_settlement(settlement_id)
            results.append(result)
        
        return results
    
    def get_settlement_status(self, settlement_id: str) -> Optional[Dict]:
        """获取结算状态"""
        settlement = self.settlements.get(settlement_id)
        if settlement:
            return settlement.to_dict()
        return None


# ============== 智能合约审计管理器 ==============

class SmartContractAuditManager:
    """智能合约审计管理器"""
    
    def __init__(self):
        self.auditor = ContractAuditor()
        self.settlement_engine = SettlementEngine()
        
        # 存储
        self.contracts: Dict[str, SmartContract] = {}
        self.disputes: Dict[str, Dispute] = {}
        
        # 财务透明
        self.financial_records: List[Dict] = []
        
        # 统计
        self.stats = {
            "contracts_registered": 0,
            "contracts_audited": 0,
            "contracts_deployed": 0,
            "audits_passed": 0,
            "audits_failed": 0,
            "disputes_opened": 0,
            "disputes_resolved": 0,
        }
    
    def register_contract(
        self,
        name: str,
        source_code: str,
        owner: str,
        description: str = "",
    ) -> SmartContract:
        """注册合约"""
        contract = SmartContract(
            name=name,
            source_code=source_code,
            owner=owner,
            description=description,
        )
        contract.compute_hash()
        
        self.contracts[contract.contract_id] = contract
        self.stats["contracts_registered"] += 1
        
        return contract
    
    def audit_contract(self, contract_id: str) -> AuditReport:
        """审计合约"""
        contract = self.contracts.get(contract_id)
        if not contract:
            raise ValueError("Contract not found")
        
        contract.status = ContractStatus.AUDITING
        
        report = self.auditor.audit(contract)
        contract.audit_reports.append(report.report_id)
        contract.last_audit_passed = report.passed
        
        if report.passed:
            contract.status = ContractStatus.APPROVED
            self.stats["audits_passed"] += 1
        else:
            contract.status = ContractStatus.DRAFT
            self.stats["audits_failed"] += 1
        
        self.stats["contracts_audited"] += 1
        
        return report
    
    def deploy_contract(self, contract_id: str, deployer: str) -> Dict:
        """部署合约"""
        contract = self.contracts.get(contract_id)
        if not contract:
            return {"error": "Contract not found"}
        
        if not contract.last_audit_passed:
            return {"error": "Contract must pass audit before deployment"}
        
        # 生成部署地址
        deploy_data = f"{contract_id}:{deployer}:{time.time()}"
        contract.deployed_address = "0x" + hashlib.sha256(deploy_data.encode()).hexdigest()[:40]
        contract.deployer = deployer
        contract.status = ContractStatus.DEPLOYED
        contract.deployed_at = time.time()
        
        self.stats["contracts_deployed"] += 1
        
        return {
            "status": "deployed",
            "contract_id": contract_id,
            "address": contract.deployed_address,
        }
    
    def create_settlement(
        self,
        contract_id: str,
        task_id: str,
        payer: str,
        payee: str,
        amount: int,
    ) -> Settlement:
        """创建结算"""
        # 记录财务
        self._record_financial_event(
            event_type="settlement_created",
            contract_id=contract_id,
            amount=amount,
            parties={"payer": payer, "payee": payee},
        )
        
        return self.settlement_engine.create_settlement(
            contract_id=contract_id,
            task_id=task_id,
            payer=payer,
            payee=payee,
            amount=amount,
        )
    
    def process_settlement(self, settlement_id: str) -> Dict:
        """处理结算"""
        result = self.settlement_engine.process_settlement(settlement_id)
        
        settlement = self.settlement_engine.settlements.get(settlement_id)
        if settlement and settlement.status == SettlementStatus.COMPLETED:
            self._record_financial_event(
                event_type="settlement_completed",
                settlement_id=settlement_id,
                amount=settlement.total_amount,
                fee=settlement.fee_amount,
                tx_hash=settlement.tx_hash,
            )
        
        return result
    
    def open_dispute(
        self,
        settlement_id: str,
        initiator: str,
        reason: str,
        evidence: List[Dict] = None,
    ) -> Dispute:
        """开启争议"""
        settlement = self.settlement_engine.settlements.get(settlement_id)
        if not settlement:
            raise ValueError("Settlement not found")
        
        # 确定对方
        respondent = settlement.payee if initiator == settlement.payer else settlement.payer
        
        dispute = Dispute(
            settlement_id=settlement_id,
            contract_id=settlement.contract_id,
            initiator=initiator,
            respondent=respondent,
            reason=reason,
            evidence=evidence or [],
            amount_disputed=settlement.total_amount,
        )
        
        # 暂停结算
        settlement.status = SettlementStatus.DISPUTED
        
        self.disputes[dispute.dispute_id] = dispute
        self.stats["disputes_opened"] += 1
        
        return dispute
    
    def resolve_dispute(
        self,
        dispute_id: str,
        arbitrator: str,
        ruling: str,
        winner: str,
    ) -> Dict:
        """解决争议"""
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return {"error": "Dispute not found"}
        
        dispute.arbitrator = arbitrator
        dispute.ruling = ruling
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolved_at = time.time()
        
        # 根据裁决处理结算
        settlement = self.settlement_engine.settlements.get(dispute.settlement_id)
        if settlement:
            if winner == settlement.payee:
                # 原结算继续
                settlement.status = SettlementStatus.PENDING
            else:
                # 退款
                settlement.status = SettlementStatus.FAILED
        
        self.stats["disputes_resolved"] += 1
        
        return {
            "dispute_id": dispute_id,
            "status": "resolved",
            "winner": winner,
            "ruling": ruling,
        }
    
    def _record_financial_event(self, event_type: str, **details):
        """记录财务事件"""
        self.financial_records.append({
            "event_type": event_type,
            "timestamp": time.time(),
            **details,
        })
    
    def get_financial_transparency_report(
        self,
        start_time: float = 0,
        end_time: float = 0,
    ) -> Dict:
        """获取财务透明报告"""
        if end_time == 0:
            end_time = time.time()
        
        records = [
            r for r in self.financial_records
            if start_time <= r["timestamp"] <= end_time
        ]
        
        # 统计
        total_volume = sum(r.get("amount", 0) for r in records)
        total_fees = sum(r.get("fee", 0) for r in records)
        
        return {
            "period": {
                "start": start_time,
                "end": end_time,
            },
            "total_transactions": len(records),
            "total_volume": total_volume,
            "total_fees": total_fees,
            "settlement_stats": self.settlement_engine.stats,
            "recent_events": records[-10:],
        }
    
    def get_contract_status(self, contract_id: str) -> Optional[Dict]:
        """获取合约状态"""
        contract = self.contracts.get(contract_id)
        if contract:
            return contract.to_dict()
        return None
    
    def get_audit_stats(self) -> Dict:
        """获取审计统计"""
        return {
            **self.stats,
            "audit_reports": len(self.auditor.reports),
            "settlement_stats": self.settlement_engine.stats,
        }


# ============== 全局实例 ==============

_smart_contract_audit_manager: Optional[SmartContractAuditManager] = None


def get_smart_contract_audit_manager() -> SmartContractAuditManager:
    """获取智能合约审计管理器单例"""
    global _smart_contract_audit_manager
    if _smart_contract_audit_manager is None:
        _smart_contract_audit_manager = SmartContractAuditManager()
    return _smart_contract_audit_manager
