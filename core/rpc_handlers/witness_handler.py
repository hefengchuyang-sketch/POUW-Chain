from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class WitnessHandler(RPCHandlerBase):
    domain = "witness"

    def register_methods(self):
        self.register(
            "witness_request", self.svc._witness_request,
            "请求交易见证",
            RPCPermission.MINER
        )
        self.register(
            "witness_getStatus", self.svc._witness_get_status,
            "获取见证状态",
            RPCPermission.PUBLIC
        )
