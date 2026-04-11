from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class AuditHandler(RPCHandlerBase):
    domain = "audit"

    def register_methods(self):
        self.register(
            "audit_submitContract", self.svc._audit_submit_contract,
            "提交合约审计",
            RPCPermission.USER
        )
        self.register(
            "audit_getReport", self.svc._audit_get_report,
            "获取审计报告",
            RPCPermission.USER
        )
        self.register(
            "audit_autoSettle", self.svc._audit_auto_settle,
            "自动结算",
            RPCPermission.MINER
        )
        self.register(
            "audit_getSettlementHistory", self.svc._audit_get_settlement_history,
            "获取结算历史",
            RPCPermission.USER
        )
