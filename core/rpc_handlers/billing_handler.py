"""
[M-22] 资源计费领域 RPC Handler

从 NodeRPCService 提取 billing_* 相关 RPC 方法注册。
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
class BillingHandler(RPCHandlerBase):
    """资源计费处理器 - 使用上报、费用计算与费率查询"""

    domain = "billing"

    def register_methods(self):
        self.register(
            "billing_recordUsage", self.svc._billing_record_usage,
            "记录资源使用",
            RPCPermission.MINER,
        )
        self.register(
            "billing_calculateCost", self.svc._billing_calculate_cost,
            "计算资源费用",
            RPCPermission.PUBLIC,
        )
        self.register(
            "billing_getDetailedBilling", self.svc._billing_get_detailed,
            "获取详细计费",
            RPCPermission.USER,
        )
        self.register(
            "billing_getRates", self.svc._billing_get_rates,
            "获取计费费率",
            RPCPermission.PUBLIC,
        )
        self.register(
            "billing_estimateTask", self.svc._billing_estimate_task,
            "估算任务费用",
            RPCPermission.PUBLIC,
        )
