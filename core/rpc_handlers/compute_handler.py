"""
[M-05] 算力市场领域 RPC Handler

从 NodeRPCService 提取 compute_* 相关 RPC 方法注册。
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
class ComputeHandler(RPCHandlerBase):
    """算力市场处理器 - 订单与陷阱题流程"""

    domain = "compute"

    def register_methods(self):
        self.register(
            "compute_submitOrder", self.svc._compute_submit_order,
            "提交算力订单",
            RPCPermission.USER,
        )
        self.register(
            "compute_getOrder", self.svc._compute_get_order,
            "查询算力订单",
            RPCPermission.USER,
        )
        self.register(
            "compute_getMarket", self.svc._compute_get_market,
            "获取算力市场信息",
            RPCPermission.PUBLIC,
        )
        self.register(
            "compute_getTrapQuestion", self.svc._compute_get_trap_question,
            "获取当前30分钟性能陷阱题",
            RPCPermission.USER,
        )
        self.register(
            "compute_submitTrapAnswer", self.svc._compute_submit_trap_answer,
            "提交当前30分钟性能陷阱题答案",
            RPCPermission.USER,
        )
        self.register(
            "compute_acceptOrder", self.svc._compute_accept_order,
            "接受算力订单",
            RPCPermission.USER,
        )
        self.register(
            "compute_completeOrder", self.svc._compute_complete_order,
            "完成算力订单并提交结果",
            RPCPermission.USER,
        )
        self.register(
            "compute_commitResult", self.svc._compute_commit_result,
            "提交订单结果承诺哈希",
            RPCPermission.USER,
        )
        self.register(
            "compute_revealResult", self.svc._compute_reveal_result,
            "提交订单结果明文摘要并结算",
            RPCPermission.USER,
        )
        self.register(
            "compute_getOrderEvents", self.svc._compute_get_order_events,
            "获取订单生命周期交易事件",
            RPCPermission.USER,
        )
        self.register(
            "compute_cancelOrder", self.svc._compute_cancel_order,
            "取消算力订单",
            RPCPermission.USER,
        )
