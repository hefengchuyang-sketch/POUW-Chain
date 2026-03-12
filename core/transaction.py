"""
Transaction 模块 - 经济事件交易记录

Phase 5 实现：
- 统一 Transaction 类型，用于上链审计
- 支持类型：ORDER_CREATED, ORDER_SCHEDULED, POUW_SUBMITTED, SETTLEMENT, REFUND
- 所有经济事件必须生成 Transaction 并记录到 MainChain
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class TxType(Enum):
    """交易类型枚举。"""
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SCHEDULED = "ORDER_SCHEDULED"
    ORDER_EXECUTING = "ORDER_EXECUTING"
    POUW_SUBMITTED = "POUW_SUBMITTED"
    POUW_VERIFIED = "POUW_VERIFIED"
    SETTLEMENT = "SETTLEMENT"
    REFUND = "REFUND"
    CONVERT_REQUEST = "CONVERT_REQUEST"
    CONVERT_CONFIRMED = "CONVERT_CONFIRMED"
    MINING_REWARD = "MINING_REWARD"


@dataclass
class Transaction:
    """区块链交易/经济事件记录。

    所有经济活动必须生成 Transaction 并上链，确保可审计。

    Attributes:
        tx_id: 交易唯一标识
        tx_type: 交易类型
        data: 交易数据（订单ID、金额、PoUW分数等）
        timestamp: 创建时间戳
        source_node: 发起节点 ID
        nonce: 交易序号（防止重放攻击）
        witnesses: 见证节点列表
        confirmed: 是否已确认
    """
    tx_type: TxType
    data: Dict[str, Any]
    source_node: str = "local"
    tx_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    nonce: int = 0
    witnesses: List[str] = field(default_factory=list)
    confirmed: bool = False

    def add_witness(self, node_id: str):
        """添加见证节点。"""
        if node_id not in self.witnesses:
            self.witnesses.append(node_id)

    def confirm(self):
        """确认交易。"""
        self.confirmed = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于区块存储）。"""
        return {
            "tx_id": self.tx_id,
            "tx_type": self.tx_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "source_node": self.source_node,
            "nonce": self.nonce,
            "witnesses": self.witnesses,
            "confirmed": self.confirmed,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Transaction":
        """从字典恢复。"""
        tx = cls(
            tx_type=TxType(d["tx_type"]),
            data=d["data"],
            source_node=d.get("source_node", "local"),
            tx_id=d["tx_id"],
            timestamp=d["timestamp"],
            nonce=d.get("nonce", 0),
            witnesses=d.get("witnesses", []),
            confirmed=d.get("confirmed", False),
        )
        return tx

    def __repr__(self) -> str:
        return (
            f"Tx({self.tx_id[:8]}, {self.tx_type.value}, "
            f"witnesses={len(self.witnesses)}, confirmed={self.confirmed})"
        )


# ============== 交易工厂函数 ==============

def create_order_tx(
    order_id: str,
    account_id: str,
    block_type: str,
    machine_count: int,
    budget_main: float,
    task_type: Optional[str] = None,
    source_node: str = "local",
) -> Transaction:
    """创建订单交易。"""
    return Transaction(
        tx_type=TxType.ORDER_CREATED,
        data={
            "order_id": order_id,
            "account_id": account_id,
            "block_type": block_type,
            "machine_count": machine_count,
            "budget_main": budget_main,
            "task_type": task_type,
        },
        source_node=source_node,
    )


def create_pouw_tx(
    order_id: str,
    miner_id: str,
    task_id: str,
    score: float,
    verified: bool,
    source_node: str = "local",
) -> Transaction:
    """创建 PoUW 提交交易。"""
    return Transaction(
        tx_type=TxType.POUW_SUBMITTED,
        data={
            "order_id": order_id,
            "miner_id": miner_id,
            "task_id": task_id,
            "score": score,
            "verified": verified,
        },
        source_node=source_node,
    )


def create_settlement_tx(
    order_id: str,
    payments: Dict[str, float],
    total_paid: float,
    source_node: str = "local",
) -> Transaction:
    """创建结算交易。"""
    return Transaction(
        tx_type=TxType.SETTLEMENT,
        data={
            "order_id": order_id,
            "payments": payments,
            "total_paid": total_paid,
        },
        source_node=source_node,
    )


def create_refund_tx(
    order_id: str,
    account_id: str,
    amount: float,
    reason: str,
    source_node: str = "local",
) -> Transaction:
    """创建退款交易。"""
    return Transaction(
        tx_type=TxType.REFUND,
        data={
            "order_id": order_id,
            "account_id": account_id,
            "amount": amount,
            "reason": reason,
        },
        source_node=source_node,
    )
