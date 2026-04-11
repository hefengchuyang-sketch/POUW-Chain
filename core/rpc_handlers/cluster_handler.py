from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class ClusterHandler(RPCHandlerBase):
    domain = "cluster"

    def register_methods(self):
        self.register(
            "cluster_hardware", self.svc._cluster_hardware,
            "Cluster hardware info",
            RPCPermission.PUBLIC
        )
        self.register(
            "cluster_execute", self.svc._cluster_execute,
            "Cluster execute task",
            RPCPermission.PUBLIC
        )
