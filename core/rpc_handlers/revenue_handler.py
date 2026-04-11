from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class RevenueHandler(RPCHandlerBase):
    domain = "revenue"

    def register_methods(self):
        self.register(
            "revenue_recordEarning", self.svc._revenue_record_earning,
            "记录收益",
            RPCPermission.MINER
        )
        self.register(
            "revenue_getMinerStats", self.svc._revenue_get_miner_stats,
            "获取矿工收益统计",
            RPCPermission.USER
        )
        self.register(
            "revenue_getLeaderboard", self.svc._revenue_get_leaderboard,
            "获取收益排行",
            RPCPermission.PUBLIC
        )
        self.register(
            "revenue_getForecast", self.svc._revenue_get_forecast,
            "获取收益预测",
            RPCPermission.USER
        )
