"""
[M-20] 订单簿领域 RPC Handler

从 NodeRPCService 提取 orderbook_* 相关 RPC 方法注册。
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
class OrderBookHandler(RPCHandlerBase):
    """订单簿处理器 - 挂单、撤单、深度与成交查询"""

    domain = "orderbook"

    def register_methods(self):
        self.register(
            "orderbook_submitAsk", self.svc._orderbook_submit_ask,
            "矿工提交卖单",
            RPCPermission.MINER,
        )
        self.register(
            "orderbook_submitBid", self.svc._orderbook_submit_bid,
            "用户提交买单",
            RPCPermission.USER,
        )
        self.register(
            "orderbook_cancelOrder", self.svc._orderbook_cancel_order,
            "取消订单",
            RPCPermission.USER,
        )
        self.register(
            "orderbook_getOrderBook", self.svc._orderbook_get_orderbook,
            "获取订单",
            RPCPermission.PUBLIC,
        )
        self.register(
            "orderbook_getMarketPrice", self.svc._orderbook_get_market_price,
            "获取市场价格",
            RPCPermission.PUBLIC,
        )
        self.register(
            "orderbook_getMyOrders", self.svc._orderbook_get_my_orders,
            "获取我的订单",
            RPCPermission.USER,
        )
        self.register(
            "orderbook_getMatches", self.svc._orderbook_get_matches,
            "获取成交记录",
            RPCPermission.PUBLIC,
        )
