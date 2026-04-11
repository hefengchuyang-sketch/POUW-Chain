from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class SecurityHandler(RPCHandlerBase):
    domain = "security"

    def register_methods(self):
        self.register(
            "security_checkRequest", self.svc._security_check_request,
            "检查请求安全性",
            RPCPermission.PUBLIC
        )
        self.register(
            "security_reportThreat", self.svc._security_report_threat,
            "报告威胁",
            RPCPermission.USER
        )
        self.register(
            "security_getStats", self.svc._security_get_stats,
            "获取安全统计",
            RPCPermission.PUBLIC
        )
        self.register(
            "security_checkSybil", self.svc._security_check_sybil,
            "检测 Sybil 攻击",
            RPCPermission.PUBLIC
        )
