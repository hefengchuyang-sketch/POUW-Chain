# -*- coding: utf-8 -*-
"""
任务验收与 SLA 机制 - 计算正确性 ≠ 用户满意度

协议层边界声明：
├── 模块：task_acceptance
├── 层级：SERVICE (服务层)
├── 类别：MARKET_OPTIONAL (市场可选)
├── 共识影响：✗ 不影响
└── 确定性要求：✗ 不要求

核心原则：
┌─────────────────────────────────────────────────────────────┐
│  共识永远不关心"好不好用"，只关心"有没有作弊"               │
└─────────────────────────────────────────────────────────────┘

三层分离：
- 协议层：只判断是否正确执行、是否一致
- 服务层：判断是否满足任务 SLA
- 应用层：用户评价、争议、仲裁
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json


# ========== 验收状态定义 ==========

class AcceptanceLevel(Enum):
    """验收层级"""
    PROTOCOL = "protocol"       # 协议层验收
    SERVICE = "service"         # 服务层验收
    APPLICATION = "application" # 应用层验收


class ProtocolVerdict(Enum):
    """协议层判定（共识相关）"""
    EXECUTED = "executed"           # 正确执行
    CONSISTENT = "consistent"       # 结果一致
    CHEATED = "cheated"             # 作弊
    TIMEOUT = "timeout"             # 超时
    INVALID = "invalid"             # 无效


class ServiceVerdict(Enum):
    """服务层判定（SLA 相关）"""
    MET = "met"                     # 满足 SLA
    PARTIAL = "partial"             # 部分满足
    VIOLATED = "violated"           # 违反 SLA
    PENDING = "pending"             # 待判定


class ApplicationVerdict(Enum):
    """应用层判定（用户相关）"""
    ACCEPTED = "accepted"           # 用户接受
    DISPUTED = "disputed"           # 争议中
    REJECTED = "rejected"           # 用户拒绝
    AUTO_ACCEPTED = "auto_accepted" # 超时自动接受


# ========== SLA 定义 ==========

@dataclass
class SLADefinition:
    """服务等级协议定义"""
    sla_id: str
    name: str
    
    # 性能指标
    max_latency_ms: int                    # 最大延迟
    min_throughput: float                  # 最小吞吐量
    max_error_rate: float                  # 最大错误率
    
    # 质量指标（AI 任务特有）
    min_accuracy: Optional[float] = None   # 最小精度
    min_similarity: Optional[float] = None # 最小相似度
    
    # 可用性指标
    uptime_percent: float = 99.0           # 可用性百分比
    
    # 惩罚规则
    penalty_per_violation: float = 0.01    # 每次违反的惩罚（占订单金额）
    max_penalty: float = 0.50              # 最大惩罚上限


# 预定义 SLA 模板
SLA_TEMPLATES: Dict[str, SLADefinition] = {
    "standard": SLADefinition(
        sla_id="sla_standard",
        name="标准服务",
        max_latency_ms=5000,
        min_throughput=1.0,
        max_error_rate=0.05,
        uptime_percent=95.0,
        penalty_per_violation=0.01,
        max_penalty=0.20
    ),
    "premium": SLADefinition(
        sla_id="sla_premium",
        name="高级服务",
        max_latency_ms=2000,
        min_throughput=5.0,
        max_error_rate=0.01,
        min_accuracy=0.95,
        uptime_percent=99.0,
        penalty_per_violation=0.02,
        max_penalty=0.30
    ),
    "ai_inference": SLADefinition(
        sla_id="sla_ai_inference",
        name="AI 推理服务",
        max_latency_ms=1000,
        min_throughput=10.0,
        max_error_rate=0.001,
        min_accuracy=0.90,
        min_similarity=0.85,
        uptime_percent=99.5,
        penalty_per_violation=0.05,
        max_penalty=0.50
    ),
    "rendering": SLADefinition(
        sla_id="sla_rendering",
        name="渲染服务",
        max_latency_ms=60000,  # 渲染可以慢
        min_throughput=0.1,
        max_error_rate=0.01,
        uptime_percent=95.0,
        penalty_per_violation=0.03,
        max_penalty=0.40
    ),
}


# ========== 验收记录 ==========

@dataclass
class AcceptanceRecord:
    """验收记录"""
    task_id: str
    order_id: str
    miner_id: str
    buyer_id: str
    
    # 协议层判定
    protocol_verdict: ProtocolVerdict
    protocol_evidence: Dict[str, Any] = field(default_factory=dict)
    protocol_timestamp: Optional[datetime] = None
    
    # 服务层判定
    service_verdict: ServiceVerdict = ServiceVerdict.PENDING
    sla_id: Optional[str] = None
    sla_metrics: Dict[str, float] = field(default_factory=dict)
    service_timestamp: Optional[datetime] = None
    
    # 应用层判定
    application_verdict: ApplicationVerdict = ApplicationVerdict.ACCEPTED
    user_rating: Optional[int] = None  # 1-5
    user_comment: Optional[str] = None
    application_timestamp: Optional[datetime] = None
    
    # 争议信息
    dispute_id: Optional[str] = None
    dispute_reason: Optional[str] = None
    arbitration_result: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "order_id": self.order_id,
            "miner_id": self.miner_id,
            "buyer_id": self.buyer_id,
            "protocol": {
                "verdict": self.protocol_verdict.value,
                "evidence": self.protocol_evidence,
                "timestamp": self.protocol_timestamp.isoformat() if self.protocol_timestamp else None
            },
            "service": {
                "verdict": self.service_verdict.value,
                "sla_id": self.sla_id,
                "metrics": self.sla_metrics,
                "timestamp": self.service_timestamp.isoformat() if self.service_timestamp else None
            },
            "application": {
                "verdict": self.application_verdict.value,
                "rating": self.user_rating,
                "comment": self.user_comment,
                "timestamp": self.application_timestamp.isoformat() if self.application_timestamp else None
            }
        }


# ========== 验收服务 ==========

class TaskAcceptanceService:
    """
    任务验收服务
    
    实现三层分离的验收机制
    """
    
    def __init__(self):
        self.records: Dict[str, AcceptanceRecord] = {}
        self.sla_templates = SLA_TEMPLATES.copy()
    
    # ========== 协议层验收（共识相关） ==========
    
    def protocol_verify(
        self,
        task_id: str,
        order_id: str,
        miner_id: str,
        buyer_id: str,
        execution_proof: Dict[str, Any],
        witness_results: List[Dict[str, Any]]
    ) -> tuple[ProtocolVerdict, Dict[str, Any]]:
        """
        协议层验收
        
        只判断：
        1. 是否正确执行（有执行证明）
        2. 是否结果一致（多节点验证一致）
        3. 是否作弊（执行时间过短、结果篡改等）
        
        Returns:
            (verdict, evidence)
        """
        evidence = {
            "execution_proof_hash": self._hash_proof(execution_proof),
            "witness_count": len(witness_results),
            "checked_at": datetime.now().isoformat()
        }
        
        # 检查 1：是否有执行证明
        if not execution_proof:
            return ProtocolVerdict.INVALID, evidence
        
        # 检查 2：执行时间是否合理（防止作弊）
        if execution_proof.get("execution_time_ms", 0) < 10:
            evidence["cheat_reason"] = "执行时间过短"
            return ProtocolVerdict.CHEATED, evidence
        
        # 检查 3：结果一致性
        if len(witness_results) >= 2:
            result_hashes = set(
                r.get("result_hash") for r in witness_results
            )
            if len(result_hashes) > 1:
                evidence["inconsistent_hashes"] = list(result_hashes)
                # 不直接判定作弊，可能是非确定性问题
                evidence["warning"] = "结果不一致，需人工审查"
        
        # 检查 4：超时
        if execution_proof.get("timeout", False):
            return ProtocolVerdict.TIMEOUT, evidence
        
        # 通过所有检查
        evidence["all_checks_passed"] = True
        verdict = ProtocolVerdict.CONSISTENT if len(witness_results) >= 2 else ProtocolVerdict.EXECUTED
        
        # 创建记录
        record = AcceptanceRecord(
            task_id=task_id,
            order_id=order_id,
            miner_id=miner_id,
            buyer_id=buyer_id,
            protocol_verdict=verdict,
            protocol_evidence=evidence,
            protocol_timestamp=datetime.now()
        )
        self.records[task_id] = record
        
        return verdict, evidence
    
    # ========== 服务层验收（SLA 相关） ==========
    
    def service_verify(
        self,
        task_id: str,
        sla_id: str,
        actual_metrics: Dict[str, float]
    ) -> tuple[ServiceVerdict, Dict[str, Any]]:
        """
        服务层验收
        
        判断是否满足 SLA 约定的指标
        
        Args:
            task_id: 任务 ID
            sla_id: SLA 模板 ID
            actual_metrics: 实际指标（latency_ms, throughput, error_rate 等）
            
        Returns:
            (verdict, details)
        """
        if task_id not in self.records:
            return ServiceVerdict.PENDING, {"error": "未找到协议层记录"}
        
        record = self.records[task_id]
        
        # 协议层必须通过
        if record.protocol_verdict in [ProtocolVerdict.CHEATED, ProtocolVerdict.INVALID]:
            return ServiceVerdict.VIOLATED, {"error": "协议层未通过"}
        
        sla = self.sla_templates.get(sla_id)
        if not sla:
            return ServiceVerdict.PENDING, {"error": f"未知 SLA: {sla_id}"}
        
        violations = []
        passed = []
        
        # 检查各项指标
        if "latency_ms" in actual_metrics:
            if actual_metrics["latency_ms"] > sla.max_latency_ms:
                violations.append(f"延迟超标: {actual_metrics['latency_ms']}ms > {sla.max_latency_ms}ms")
            else:
                passed.append("latency")
        
        if "throughput" in actual_metrics:
            if actual_metrics["throughput"] < sla.min_throughput:
                violations.append(f"吞吐量不足: {actual_metrics['throughput']} < {sla.min_throughput}")
            else:
                passed.append("throughput")
        
        if "error_rate" in actual_metrics:
            if actual_metrics["error_rate"] > sla.max_error_rate:
                violations.append(f"错误率超标: {actual_metrics['error_rate']} > {sla.max_error_rate}")
            else:
                passed.append("error_rate")
        
        if sla.min_accuracy and "accuracy" in actual_metrics:
            if actual_metrics["accuracy"] < sla.min_accuracy:
                violations.append(f"精度不足: {actual_metrics['accuracy']} < {sla.min_accuracy}")
            else:
                passed.append("accuracy")
        
        # 判定
        if len(violations) == 0:
            verdict = ServiceVerdict.MET
        elif len(violations) <= len(passed):
            verdict = ServiceVerdict.PARTIAL
        else:
            verdict = ServiceVerdict.VIOLATED
        
        # 更新记录
        record.service_verdict = verdict
        record.sla_id = sla_id
        record.sla_metrics = actual_metrics
        record.service_timestamp = datetime.now()
        
        return verdict, {
            "sla_name": sla.name,
            "passed": passed,
            "violations": violations,
            "penalty": min(len(violations) * sla.penalty_per_violation, sla.max_penalty)
        }
    
    # ========== 应用层验收（用户相关） ==========
    
    def application_verify(
        self,
        task_id: str,
        user_accepts: bool,
        rating: Optional[int] = None,
        comment: Optional[str] = None
    ) -> tuple[ApplicationVerdict, Dict[str, Any]]:
        """
        应用层验收
        
        用户主观评价
        """
        if task_id not in self.records:
            return ApplicationVerdict.ACCEPTED, {"error": "未找到记录，默认接受"}
        
        record = self.records[task_id]
        
        if user_accepts:
            verdict = ApplicationVerdict.ACCEPTED
        else:
            verdict = ApplicationVerdict.REJECTED
        
        record.application_verdict = verdict
        record.user_rating = rating
        record.user_comment = comment
        record.application_timestamp = datetime.now()
        
        return verdict, {
            "protocol_verdict": record.protocol_verdict.value,
            "service_verdict": record.service_verdict.value,
            "application_verdict": verdict.value,
            "final_note": self._get_final_note(record)
        }
    
    def _get_final_note(self, record: AcceptanceRecord) -> str:
        """生成最终说明"""
        # 协议层通过是前提
        if record.protocol_verdict == ProtocolVerdict.CHEATED:
            return "矿工作弊，全额退款"
        
        if record.protocol_verdict == ProtocolVerdict.TIMEOUT:
            return "执行超时，部分退款"
        
        # 用户不满意但协议层通过
        if record.application_verdict == ApplicationVerdict.REJECTED:
            if record.protocol_verdict in [ProtocolVerdict.EXECUTED, ProtocolVerdict.CONSISTENT]:
                return "用户主观不满意，但矿工无作弊，可申请争议仲裁"
        
        return "任务完成"
    
    # ========== 争议处理 ==========
    
    def raise_dispute(
        self,
        task_id: str,
        reason: str
    ) -> str:
        """
        发起争议
        
        只有在协议层通过但用户不满意时才能发起
        """
        if task_id not in self.records:
            return "任务不存在"
        
        record = self.records[task_id]
        
        # 作弊不需要争议，直接惩罚
        if record.protocol_verdict == ProtocolVerdict.CHEATED:
            return "矿工已被判定作弊，无需争议"
        
        dispute_id = f"dispute_{task_id}_{int(datetime.now().timestamp())}"
        record.dispute_id = dispute_id
        record.dispute_reason = reason
        record.application_verdict = ApplicationVerdict.DISPUTED
        
        return dispute_id
    
    def resolve_dispute(
        self,
        dispute_id: str,
        result: str,  # "buyer_wins", "miner_wins", "split"
        refund_ratio: float = 0.0
    ) -> Dict[str, Any]:
        """解决争议"""
        for task_id, record in self.records.items():
            if record.dispute_id == dispute_id:
                record.arbitration_result = result
                if result == "buyer_wins":
                    record.application_verdict = ApplicationVerdict.REJECTED
                elif result == "miner_wins":
                    record.application_verdict = ApplicationVerdict.ACCEPTED
                
                return {
                    "dispute_id": dispute_id,
                    "result": result,
                    "refund_ratio": refund_ratio,
                    "message": f"争议已解决: {result}"
                }
        
        return {"error": "争议不存在"}
    
    # ========== 工具方法 ==========
    
    def _hash_proof(self, proof: Dict[str, Any]) -> str:
        """计算证明哈希"""
        return hashlib.sha256(
            json.dumps(proof, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def get_record(self, task_id: str) -> Optional[AcceptanceRecord]:
        """获取验收记录"""
        return self.records.get(task_id)


# ========== 单例 ==========

_acceptance_service: Optional[TaskAcceptanceService] = None

def get_acceptance_service() -> TaskAcceptanceService:
    """获取验收服务实例"""
    global _acceptance_service
    if _acceptance_service is None:
        _acceptance_service = TaskAcceptanceService()
    return _acceptance_service
