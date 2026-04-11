from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class MonitorHandler(RPCHandlerBase):
    domain = "monitor"

    def register_methods(self):
        self.register(
            "monitor_getHealth", self.svc._monitor_get_health,
            "获取系统健康状态",
            RPCPermission.PUBLIC
        )
        self.register(
            "monitor_getDashboard", self.svc._monitor_get_dashboard,
            "获取监控面板",
            RPCPermission.PUBLIC
        )
        self.register(
            "monitor_getAlerts", self.svc._monitor_get_alerts,
            "获取告警列表",
            RPCPermission.ADMIN
        )
        self.register(
            "monitor_recordMetric", self.svc._monitor_record_metric,
            "记录指标",
            RPCPermission.MINER
        )
