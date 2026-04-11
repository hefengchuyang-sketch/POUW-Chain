"""
[M-10] 动态定价领域 RPC Handler

从 NodeRPCService 提取 pricing_* 相关 RPC 方法注册。
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
class PricingHandler(RPCHandlerBase):
    """动态定价处理器 - 基础价格、实时价格与预测查询"""

    domain = "pricing"

    def register_methods(self):
        self.register(
            "pricing_getBaseRates", self.svc._pricing_get_base_rates,
            "获取所有 GPU 基础价格",
            RPCPermission.PUBLIC,
        )
        self.register(
            "pricing_getRealTimePrice", self.svc._pricing_get_real_time_price,
            "获取实时价格",
            RPCPermission.PUBLIC,
        )
        self.register(
            "pricing_calculatePrice", self.svc._pricing_calculate_price,
            "计算任务价格",
            RPCPermission.PUBLIC,
        )
        self.register(
            "pricing_getMarketState", self.svc._pricing_get_market_state,
            "获取市场供需状态",
            RPCPermission.PUBLIC,
        )
        self.register(
            "pricing_getStrategies", self.svc._pricing_get_strategies,
            "获取所有定价策略",
            RPCPermission.PUBLIC,
        )
        self.register(
            "pricing_getTimeSlotSchedule", self.svc._pricing_get_time_slot_schedule,
            "获取时段价格",
            RPCPermission.PUBLIC,
        )
        self.register(
            "pricing_getPriceForecast", self.svc._pricing_get_price_forecast,
            "获取价格预测",
            RPCPermission.PUBLIC,
        )
