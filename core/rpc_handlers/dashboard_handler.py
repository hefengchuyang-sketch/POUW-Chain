from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class DashboardHandler(RPCHandlerBase):
    domain = "dashboard"

    def register_methods(self):
        self.register(
            "dashboard_getStats", self.svc._dashboard_get_stats,
            "获取仪表盘综合统计",
            RPCPermission.PUBLIC
        )
        self.register(
            "dashboard_getRecentTasks", self.svc._dashboard_get_recent_tasks,
            "获取最近任务列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "dashboard_getRecentProposals", self.svc._dashboard_get_recent_proposals,
            "获取最近提案列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "dashboard_getBlockChart", self.svc._dashboard_get_block_chart,
            "获取出块类型分布图表",
            RPCPermission.PUBLIC
        )
        self.register(
            "dashboard_getRewardTrend", self.svc._dashboard_get_reward_trend,
            "获取奖励趋势图表",
            RPCPermission.PUBLIC
        )
