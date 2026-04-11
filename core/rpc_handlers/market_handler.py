"""
[M-13] 市场监控领域 RPC Handler

从 NodeRPCService 提取 market_* 相关 RPC 方法注册。
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
class MarketHandler(RPCHandlerBase):
    """市场监控处理器 - 市场面板、供需曲线、报价与接单"""

    domain = "market"

    def register_methods(self):
        self.register(
            "market_getDashboard", self.svc._market_get_dashboard,
            "获取市场监控面板",
            RPCPermission.PUBLIC,
        )
        self.register(
            "market_getSupplyDemandCurve", self.svc._market_get_supply_demand_curve,
            "获取供需曲线",
            RPCPermission.PUBLIC,
        )
        self.register(
            "market_getQueueStatus", self.svc._market_get_queue_status,
            "获取任务队列状态",
            RPCPermission.PUBLIC,
        )
        self.register(
            "market_updateSupplyDemand", self.svc._market_update_supply_demand,
            "更新供需数据",
            RPCPermission.MINER,
        )
        self.register(
            "market_getQuotes", self.svc._market_get_quotes,
            "获取任务报价列表",
            RPCPermission.PUBLIC,
        )
        self.register(
            "market_acceptQuote", self.svc._market_accept_quote,
            "接受报价",
            RPCPermission.USER,
        )
