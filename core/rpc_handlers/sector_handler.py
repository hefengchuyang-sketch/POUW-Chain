from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class SectorHandler(RPCHandlerBase):
    domain = "sector"

    def register_methods(self):
        self.register(
            "sector_getExchangeRates", self.svc._sector_get_exchange_rates,
            "获取板块币兑换比率",
            RPCPermission.PUBLIC
        )
        self.register(
            "sector_requestExchange", self.svc._sector_request_exchange,
            "请求兑换板块币为MAIN",
            RPCPermission.USER
        )
        self.register(
            "sector_getExchangeHistory", self.svc._sector_get_exchange_history,
            "获取兑换历史",
            RPCPermission.PUBLIC
        )
        self.register(
            "sector_cancelExchange", self.svc._sector_cancel_exchange,
            "取消兑换请求",
            RPCPermission.USER
        )
