"""
[M-16] 订单查询领域 RPC Handler

从 NodeRPCService 提取 order_* 相关 RPC 方法注册。
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
class OrderHandler(RPCHandlerBase):
    """订单查询处理器 - 列表与详情查询"""

    domain = "order"

    def register_methods(self):
        self.register(
            "order_getList", self.svc._order_get_list,
            "获取订单列表",
            RPCPermission.PUBLIC,
        )
        self.register(
            "order_getDetail", self.svc._order_get_detail,
            "获取订单详情",
            RPCPermission.PUBLIC,
        )
