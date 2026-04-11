"""
[M-12] 结算领域 RPC Handler

从 NodeRPCService 提取 settlement_* 相关 RPC 方法注册。
方法实现仍在 NodeRPCService 中，通过 self.svc 委托调用。
"""

from core.rpc_handlers import RPCHandlerBase, register_handler_class

try:
    from core.rpc_service import RPCPermission
except ImportError:
    from enum import IntEnum

    class RPCPermission(IntEnum):
        PUBLIC = 0
        USER = 1
        MINER = 2
        ADMIN = 3


@register_handler_class
class SettlementHandler(RPCHandlerBase):
    """结算处理器 - 任务结算、账单与矿工收益查询"""

    domain = "settlement"

    def register_methods(self):
        self.register(
            "settlement_settleTask", self.svc._settlement_settle_task,
            "结算任务",
            RPCPermission.MINER,
        )
        self.register(
            "settlement_getRecord", self.svc._settlement_get_record,
            "获取结算记录",
            RPCPermission.USER,
        )
        self.register(
            "settlement_getDetailedBill", self.svc._settlement_get_detailed_bill,
            "获取详细账单",
            RPCPermission.USER,
        )
        self.register(
            "settlement_getMinerEarnings", self.svc._settlement_get_miner_earnings,
            "获取矿工收益",
            RPCPermission.MINER,
        )
