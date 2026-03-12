"""
compute_futures.py - 算力期货与预定合约

Phase 9 功能：
1. 算力期货合约 - 预定未来算力
2. 价格锁定机制
3. 保证金系统
4. 违约惩罚（矿工 & 用户）
5. 合约交割
"""

import time
import uuid
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import defaultdict


# ============== 枚举类型 ==============

class ContractType(Enum):
    """合约类型"""
    SPOT = "spot"                      # 现货
    FUTURES = "futures"                # 期货
    RESERVATION = "reservation"        # 预定
    SUBSCRIPTION = "subscription"      # 订阅（长期）


class ContractStatus(Enum):
    """合约状态"""
    PENDING = "pending"                # 待生效
    ACTIVE = "active"                  # 生效中
    DELIVERING = "delivering"          # 交割中
    COMPLETED = "completed"            # 已完成
    CANCELLED = "cancelled"            # 已取消
    DEFAULTED = "defaulted"            # 已违约
    DISPUTED = "disputed"              # 争议中


class PartyType(Enum):
    """当事方类型"""
    USER = "user"
    MINER = "miner"


class DefaultReason(Enum):
    """违约原因"""
    USER_NO_PAYMENT = "user_no_payment"            # 用户未付款
    USER_CANCEL = "user_cancel"                     # 用户取消
    MINER_NO_DELIVERY = "miner_no_delivery"        # 矿工未交付
    MINER_CANCEL = "miner_cancel"                   # 矿工取消
    MINER_QUALITY_ISSUE = "miner_quality_issue"    # 质量问题
    FORCE_MAJEURE = "force_majeure"                 # 不可抗力


# ============== 数据结构 ==============

@dataclass
class ResourceReservation:
    """资源预定"""
    gpu_type: str
    gpu_count: int = 1
    gpu_memory_gb: int = 0
    
    start_time: float = 0                  # 开始时间
    end_time: float = 0                    # 结束时间
    duration_hours: float = 0              # 时长
    
    utilization_guarantee: float = 0.95    # 利用率保证


@dataclass
class MarginDeposit:
    """保证金"""
    deposit_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    party_type: PartyType = PartyType.USER
    party_id: str = ""
    
    amount: float = 0                      # 保证金金额
    currency: str = "POUW"
    
    deposited_at: float = field(default_factory=time.time)
    locked_until: float = 0                # 锁定到期时间
    
    is_locked: bool = True
    released: bool = False
    released_at: float = 0
    
    # 扣减记录
    deductions: List[Dict] = field(default_factory=list)
    remaining: float = 0
    
    def __post_init__(self):
        self.remaining = self.amount
    
    def deduct(self, amount: float, reason: str) -> bool:
        """扣减保证金"""
        if amount > self.remaining:
            return False
        
        self.remaining -= amount
        self.deductions.append({
            "amount": amount,
            "reason": reason,
            "time": time.time(),
        })
        return True
    
    def to_dict(self) -> Dict:
        return {
            "deposit_id": self.deposit_id,
            "party_type": self.party_type.value,
            "party_id": self.party_id,
            "amount": self.amount,
            "remaining": self.remaining,
            "is_locked": self.is_locked,
            "locked_until": self.locked_until,
        }


@dataclass
class PenaltyRule:
    """违约惩罚规则"""
    early_cancel_penalty_rate: float = 0.1     # 提前取消惩罚率
    no_show_penalty_rate: float = 0.3          # 不履约惩罚率
    quality_penalty_rate: float = 0.2          # 质量问题惩罚率
    
    # 时间相关惩罚
    cancel_before_24h_penalty: float = 0.05    # 24小时前取消
    cancel_before_12h_penalty: float = 0.10    # 12小时前取消
    cancel_before_1h_penalty: float = 0.20     # 1小时前取消
    cancel_after_start_penalty: float = 0.50   # 开始后取消
    
    # 最低惩罚
    min_penalty_amount: float = 1.0


@dataclass
class FuturesContract:
    """期货合约"""
    contract_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    contract_type: ContractType = ContractType.FUTURES
    
    # 参与方
    user_id: str = ""
    miner_id: str = ""
    
    # 资源
    reservation: ResourceReservation = None
    
    # 价格
    locked_price: float = 0                # 锁定价格 (每GPU小时)
    total_value: float = 0                 # 合约总价值
    spot_price_at_creation: float = 0      # 创建时现货价格
    
    # 保证金
    user_margin: Optional[MarginDeposit] = None
    miner_margin: Optional[MarginDeposit] = None
    margin_rate: float = 0.2               # 保证金率
    
    # 时间
    created_at: float = field(default_factory=time.time)
    effective_at: float = 0                # 生效时间
    expires_at: float = 0                  # 到期时间
    delivery_deadline: float = 0           # 交割截止
    
    # 状态
    status: ContractStatus = ContractStatus.PENDING
    
    # 违约
    defaulted_by: Optional[PartyType] = None
    default_reason: Optional[DefaultReason] = None
    penalty_applied: float = 0
    
    # 交割
    delivered_hours: float = 0
    delivery_quality_score: float = 0
    
    # 链上
    tx_hash: str = ""
    settlement_tx: str = ""
    
    def compute_hash(self) -> str:
        """计算合约哈希"""
        data = f"{self.contract_id}{self.user_id}{self.miner_id}"
        data += f"{self.locked_price}{self.total_value}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        return {
            "contract_id": self.contract_id,
            "contract_type": self.contract_type.value,
            "user_id": self.user_id,
            "miner_id": self.miner_id,
            "gpu_type": self.reservation.gpu_type if self.reservation else None,
            "gpu_count": self.reservation.gpu_count if self.reservation else 0,
            "duration_hours": self.reservation.duration_hours if self.reservation else 0,
            "locked_price": self.locked_price,
            "total_value": self.total_value,
            "margin_rate": self.margin_rate,
            "status": self.status.value,
            "start_time": self.reservation.start_time if self.reservation else 0,
            "end_time": self.reservation.end_time if self.reservation else 0,
            "created_at": self.created_at,
        }


@dataclass
class DeliveryRecord:
    """交割记录"""
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    contract_id: str = ""
    
    # 交割详情
    start_time: float = 0
    end_time: float = 0
    duration_hours: float = 0
    
    # 质量
    avg_utilization: float = 0
    uptime_percent: float = 0
    quality_score: float = 0
    
    # 验证
    verified: bool = False
    verified_by: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "contract_id": self.contract_id,
            "duration_hours": self.duration_hours,
            "avg_utilization": self.avg_utilization,
            "quality_score": self.quality_score,
            "verified": self.verified,
        }


# ============== 期货合约管理器 ==============

class FuturesContractManager:
    """期货合约管理器"""
    
    # 默认配置
    DEFAULT_MARGIN_RATE = 0.2              # 20% 保证金
    MAX_RESERVATION_DAYS = 30              # 最长预定天数
    MIN_RESERVATION_HOURS = 1              # 最短预定小时
    
    def __init__(self):
        self.contracts: Dict[str, FuturesContract] = {}
        self.margins: Dict[str, MarginDeposit] = {}
        self.deliveries: Dict[str, List[DeliveryRecord]] = defaultdict(list)
        self._lock = threading.RLock()
        
        self.penalty_rule = PenaltyRule()
        
        # 用户/矿工的合约索引
        self.user_contracts: Dict[str, List[str]] = defaultdict(list)
        self.miner_contracts: Dict[str, List[str]] = defaultdict(list)
    
    def create_futures_contract(
        self,
        user_id: str,
        miner_id: str,
        gpu_type: str,
        gpu_count: int,
        start_time: float,
        duration_hours: float,
        locked_price: float,
        spot_price: float = None,
        margin_rate: float = None,
    ) -> FuturesContract:
        """创建期货合约"""
        with self._lock:
            if margin_rate is None:
                margin_rate = self.DEFAULT_MARGIN_RATE
            
            # 创建资源预定
            reservation = ResourceReservation(
                gpu_type=gpu_type,
                gpu_count=gpu_count,
                start_time=start_time,
                end_time=start_time + duration_hours * 3600,
                duration_hours=duration_hours,
            )
            
            # 计算总价值
            total_value = locked_price * duration_hours * gpu_count
            
            # 创建合约
            contract = FuturesContract(
                contract_type=ContractType.FUTURES,
                user_id=user_id,
                miner_id=miner_id,
                reservation=reservation,
                locked_price=locked_price,
                total_value=total_value,
                spot_price_at_creation=spot_price or locked_price,
                margin_rate=margin_rate,
                effective_at=start_time,
                expires_at=start_time + duration_hours * 3600,
                delivery_deadline=start_time + duration_hours * 3600 + 3600,  # 1小时缓冲
            )
            
            self.contracts[contract.contract_id] = contract
            self.user_contracts[user_id].append(contract.contract_id)
            self.miner_contracts[miner_id].append(contract.contract_id)
            
            return contract
    
    def deposit_margin(
        self,
        contract_id: str,
        party_type: PartyType,
        party_id: str,
        amount: float,
    ) -> MarginDeposit:
        """存入保证金"""
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                raise ValueError("Contract not found")
            
            # 验证当事方
            if party_type == PartyType.USER and party_id != contract.user_id:
                raise ValueError("Party mismatch")
            if party_type == PartyType.MINER and party_id != contract.miner_id:
                raise ValueError("Party mismatch")
            
            # 计算所需保证金
            required_margin = contract.total_value * contract.margin_rate
            if amount < required_margin:
                raise ValueError(f"Insufficient margin. Required: {required_margin}")
            
            # 创建保证金记录
            margin = MarginDeposit(
                party_type=party_type,
                party_id=party_id,
                amount=amount,
                locked_until=contract.expires_at,
            )
            
            self.margins[margin.deposit_id] = margin
            
            # 关联到合约
            if party_type == PartyType.USER:
                contract.user_margin = margin
            else:
                contract.miner_margin = margin
            
            # 检查是否双方都已缴纳保证金
            if contract.user_margin and contract.miner_margin:
                contract.status = ContractStatus.ACTIVE
            
            return margin
    
    def activate_contract(self, contract_id: str) -> bool:
        """激活合约"""
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return False
            
            if not contract.user_margin or not contract.miner_margin:
                return False
            
            contract.status = ContractStatus.ACTIVE
            return True
    
    def cancel_contract(
        self,
        contract_id: str,
        cancelled_by: PartyType,
        reason: str = "",
    ) -> Tuple[bool, float]:
        """取消合约（计算违约金）"""
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return False, 0
            
            if contract.status not in [ContractStatus.PENDING, ContractStatus.ACTIVE]:
                return False, 0
            
            # 计算距离开始时间
            time_until_start = contract.effective_at - time.time()
            hours_until_start = time_until_start / 3600
            
            # 确定惩罚率
            if time_until_start < 0:
                # 已经开始
                penalty_rate = self.penalty_rule.cancel_after_start_penalty
            elif hours_until_start < 1:
                penalty_rate = self.penalty_rule.cancel_before_1h_penalty
            elif hours_until_start < 12:
                penalty_rate = self.penalty_rule.cancel_before_12h_penalty
            elif hours_until_start < 24:
                penalty_rate = self.penalty_rule.cancel_before_24h_penalty
            else:
                penalty_rate = self.penalty_rule.early_cancel_penalty_rate
            
            # 计算惩罚金额
            penalty_amount = max(
                contract.total_value * penalty_rate,
                self.penalty_rule.min_penalty_amount
            )
            
            # 从违约方保证金中扣除
            if cancelled_by == PartyType.USER:
                margin = contract.user_margin
                default_reason = DefaultReason.USER_CANCEL
            else:
                margin = contract.miner_margin
                default_reason = DefaultReason.MINER_CANCEL
            
            if margin:
                margin.deduct(penalty_amount, f"Cancellation penalty: {reason}")
            
            # 更新合约状态
            contract.status = ContractStatus.CANCELLED
            contract.defaulted_by = cancelled_by
            contract.default_reason = default_reason
            contract.penalty_applied = penalty_amount
            
            return True, penalty_amount
    
    def record_delivery(
        self,
        contract_id: str,
        duration_hours: float,
        avg_utilization: float = 1.0,
        uptime_percent: float = 100.0,
    ) -> DeliveryRecord:
        """记录交割"""
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                raise ValueError("Contract not found")
            
            # 计算质量分数
            quality_score = (avg_utilization * 0.5 + uptime_percent / 100 * 0.5) * 100
            
            record = DeliveryRecord(
                contract_id=contract_id,
                start_time=time.time() - duration_hours * 3600,
                end_time=time.time(),
                duration_hours=duration_hours,
                avg_utilization=avg_utilization,
                uptime_percent=uptime_percent,
                quality_score=quality_score,
            )
            
            self.deliveries[contract_id].append(record)
            
            # 更新合约交割进度
            contract.delivered_hours += duration_hours
            contract.status = ContractStatus.DELIVERING
            
            # 检查是否完成交割
            if contract.reservation and contract.delivered_hours >= contract.reservation.duration_hours:
                contract.status = ContractStatus.COMPLETED
                contract.delivery_quality_score = quality_score
                
                # 释放保证金
                self._release_margins(contract)
            
            return record
    
    def _release_margins(self, contract: FuturesContract):
        """释放保证金"""
        for margin in [contract.user_margin, contract.miner_margin]:
            if margin and margin.is_locked:
                margin.is_locked = False
                margin.released = True
                margin.released_at = time.time()
    
    def handle_default(
        self,
        contract_id: str,
        defaulted_by: PartyType,
        reason: DefaultReason,
    ) -> Tuple[bool, float]:
        """处理违约"""
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return False, 0
            
            # 确定惩罚率
            if reason in [DefaultReason.MINER_NO_DELIVERY, DefaultReason.USER_NO_PAYMENT]:
                penalty_rate = self.penalty_rule.no_show_penalty_rate
            elif reason == DefaultReason.MINER_QUALITY_ISSUE:
                penalty_rate = self.penalty_rule.quality_penalty_rate
            else:
                penalty_rate = self.penalty_rule.early_cancel_penalty_rate
            
            # 计算惩罚
            penalty_amount = contract.total_value * penalty_rate
            
            # 扣除保证金
            if defaulted_by == PartyType.USER:
                margin = contract.user_margin
            else:
                margin = contract.miner_margin
            
            if margin:
                actual_penalty = min(penalty_amount, margin.remaining)
                margin.deduct(actual_penalty, f"Default penalty: {reason.value}")
                
                # 将惩罚金转给对方
                other_margin = contract.miner_margin if defaulted_by == PartyType.USER else contract.user_margin
                if other_margin:
                    other_margin.remaining += actual_penalty
            else:
                actual_penalty = 0
            
            # 更新合约状态
            contract.status = ContractStatus.DEFAULTED
            contract.defaulted_by = defaulted_by
            contract.default_reason = reason
            contract.penalty_applied = actual_penalty
            
            return True, actual_penalty
    
    def settle_contract(self, contract_id: str) -> Dict:
        """结算合约"""
        with self._lock:
            contract = self.contracts.get(contract_id)
            if not contract:
                return {"error": "Contract not found"}
            
            if contract.status != ContractStatus.COMPLETED:
                return {"error": f"Contract not completed: {contract.status.value}"}
            
            # 计算最终结算
            settlement = {
                "contract_id": contract_id,
                "total_value": contract.total_value,
                "delivered_hours": contract.delivered_hours,
                "quality_score": contract.delivery_quality_score,
            }
            
            # 用户支付
            user_payment = contract.total_value
            if contract.delivery_quality_score < 95:
                # 质量不足打折
                discount = (100 - contract.delivery_quality_score) / 100 * 0.2
                user_payment *= (1 - discount)
            
            settlement["user_payment"] = user_payment
            settlement["miner_earning"] = user_payment * 0.95  # 5% 平台费
            settlement["platform_fee"] = user_payment * 0.05
            
            # 释放保证金
            if contract.user_margin:
                settlement["user_margin_returned"] = contract.user_margin.remaining
            if contract.miner_margin:
                settlement["miner_margin_returned"] = contract.miner_margin.remaining
            
            return settlement
    
    def get_contract(self, contract_id: str) -> Optional[Dict]:
        """获取合约信息"""
        with self._lock:
            contract = self.contracts.get(contract_id)
            if contract:
                return contract.to_dict()
            return None
    
    def get_user_contracts(self, user_id: str) -> List[Dict]:
        """获取用户合约"""
        with self._lock:
            contract_ids = self.user_contracts.get(user_id, [])
            return [self.contracts[cid].to_dict() for cid in contract_ids if cid in self.contracts]
    
    def get_miner_contracts(self, miner_id: str) -> List[Dict]:
        """获取矿工合约"""
        with self._lock:
            contract_ids = self.miner_contracts.get(miner_id, [])
            return [self.contracts[cid].to_dict() for cid in contract_ids if cid in self.contracts]
    
    def get_active_reservations(
        self,
        miner_id: str = None,
        start_time: float = None,
        end_time: float = None,
    ) -> List[Dict]:
        """获取活跃预定"""
        with self._lock:
            reservations = []
            
            for contract in self.contracts.values():
                if contract.status not in [ContractStatus.ACTIVE, ContractStatus.DELIVERING]:
                    continue
                
                if miner_id and contract.miner_id != miner_id:
                    continue
                
                if start_time and contract.reservation.end_time < start_time:
                    continue
                
                if end_time and contract.reservation.start_time > end_time:
                    continue
                
                reservations.append({
                    "contract_id": contract.contract_id,
                    "miner_id": contract.miner_id,
                    "gpu_type": contract.reservation.gpu_type,
                    "gpu_count": contract.reservation.gpu_count,
                    "start_time": contract.reservation.start_time,
                    "end_time": contract.reservation.end_time,
                    "locked_price": contract.locked_price,
                })
            
            return reservations
    
    def check_availability(
        self,
        miner_id: str,
        gpu_type: str,
        start_time: float,
        duration_hours: float,
    ) -> Dict:
        """检查可用性"""
        with self._lock:
            end_time = start_time + duration_hours * 3600
            
            conflicts = []
            for contract in self.contracts.values():
                if contract.miner_id != miner_id:
                    continue
                if contract.status not in [ContractStatus.ACTIVE, ContractStatus.DELIVERING, ContractStatus.PENDING]:
                    continue
                if contract.reservation.gpu_type != gpu_type:
                    continue
                
                # 检查时间重叠
                if not (end_time <= contract.reservation.start_time or start_time >= contract.reservation.end_time):
                    conflicts.append(contract.contract_id)
            
            return {
                "available": len(conflicts) == 0,
                "conflicts": conflicts,
            }


# ============== 期货市场 ==============

class FuturesMarket:
    """期货市场"""
    
    def __init__(self, contract_manager: FuturesContractManager = None):
        self.contract_manager = contract_manager or FuturesContractManager()
        self._lock = threading.RLock()
        
        # 期货价格曲线
        self.futures_prices: Dict[str, Dict[int, float]] = defaultdict(dict)  # gpu_type -> {days_ahead -> price}
    
    def get_futures_price(
        self,
        gpu_type: str,
        days_ahead: int,
        spot_price: float,
    ) -> float:
        """获取期货价格"""
        with self._lock:
            # 简单的期货定价模型
            # 期货价格 = 现货价格 * (1 + 无风险利率 * 天数/365 + 存储成本)
            
            risk_free_rate = 0.05           # 5% 年化
            convenience_yield = 0.02        # 便利收益
            
            # 期货溢价/贴水
            if days_ahead <= 7:
                premium = 0.02 * days_ahead  # 短期小溢价
            elif days_ahead <= 30:
                premium = 0.015 * days_ahead  # 中期
            else:
                premium = 0.01 * days_ahead   # 长期贴水
            
            futures_price = spot_price * (1 + (risk_free_rate - convenience_yield) * days_ahead / 365 + premium)
            
            # 缓存
            self.futures_prices[gpu_type][days_ahead] = futures_price
            
            return round(futures_price, 4)
    
    def get_futures_curve(
        self,
        gpu_type: str,
        spot_price: float,
        max_days: int = 30,
    ) -> List[Dict]:
        """获取期货价格曲线"""
        curve = []
        
        for days in range(1, max_days + 1):
            price = self.get_futures_price(gpu_type, days, spot_price)
            curve.append({
                "days_ahead": days,
                "price": price,
                "premium_percent": round((price / spot_price - 1) * 100, 2),
            })
        
        return curve
    
    def quote_reservation(
        self,
        gpu_type: str,
        gpu_count: int,
        start_time: float,
        duration_hours: float,
        spot_price: float,
    ) -> Dict:
        """报价预定"""
        with self._lock:
            days_ahead = max(1, int((start_time - time.time()) / 86400))
            
            # 获取期货价格
            futures_price = self.get_futures_price(gpu_type, days_ahead, spot_price)
            
            # 计算总价值
            total_value = futures_price * duration_hours * gpu_count
            
            # 保证金
            margin_required = total_value * 0.2
            
            return {
                "gpu_type": gpu_type,
                "gpu_count": gpu_count,
                "start_time": start_time,
                "duration_hours": duration_hours,
                "spot_price": spot_price,
                "futures_price": futures_price,
                "days_ahead": days_ahead,
                "premium_percent": round((futures_price / spot_price - 1) * 100, 2),
                "total_value": round(total_value, 4),
                "margin_required": round(margin_required, 4),
                "margin_rate": 0.2,
            }


# ============== 全局实例 ==============

_contract_manager: Optional[FuturesContractManager] = None
_futures_market: Optional[FuturesMarket] = None


def get_futures_system() -> Tuple[FuturesContractManager, FuturesMarket]:
    """获取期货系统单例"""
    global _contract_manager, _futures_market
    
    if _contract_manager is None:
        _contract_manager = FuturesContractManager()
        _futures_market = FuturesMarket(_contract_manager)
    
    return _contract_manager, _futures_market
