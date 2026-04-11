from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class MempoolHandler(RPCHandlerBase):
    domain = "mempool"

    def register_methods(self):
        self.register(
            "mempool_getInfo", self.svc._mempool_get_info,
            "获取 mempool 状态",
            RPCPermission.PUBLIC
        )
        self.register(
            "mempool_getPending", self.svc._mempool_get_pending,
            "获取待打包交易",
            RPCPermission.PUBLIC
        )
