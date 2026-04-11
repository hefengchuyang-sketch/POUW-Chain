"""
[M-21] 算力期货领域 RPC Handler

从 NodeRPCService 提取 futures_* 相关 RPC 方法注册。
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
class FuturesHandler(RPCHandlerBase):
    """算力期货处理器 - 合约创建、保证金与结算"""

    domain = "futures"

    def register_methods(self):
        self.register(
            "futures_createContract", self.svc._futures_create_contract,
            "创建期货合约",
            RPCPermission.USER,
        )
        self.register(
            "futures_depositMargin", self.svc._futures_deposit_margin,
            "缴纳保证金",
            RPCPermission.USER,
        )
        self.register(
            "futures_getContract", self.svc._futures_get_contract,
            "获取合约详情",
            RPCPermission.PUBLIC,
        )
        self.register(
            "futures_listContracts", self.svc._futures_list_contracts,
            "列出期货合约",
            RPCPermission.PUBLIC,
        )
        self.register(
            "futures_cancelContract", self.svc._futures_cancel_contract,
            "取消期货合约",
            RPCPermission.USER,
        )
        self.register(
            "futures_settleContract", self.svc._futures_settle_contract,
            "结算期货合约",
            RPCPermission.USER,
        )
        self.register(
            "futures_getPricingCurve", self.svc._futures_get_pricing_curve,
            "获取期货定价曲线",
            RPCPermission.PUBLIC,
        )
