from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class NodeHandler(RPCHandlerBase):
    domain = "node"

    def register_methods(self):
        self.register(
            "node_getInfo", self.svc._node_get_info,
            "获取节点信息",
            RPCPermission.PUBLIC
        )
        self.register(
            "node_getPeers", self.svc._node_get_peers,
            "获取对等节点列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "node_isSyncing", self.svc._node_is_syncing,
            "检查节点是否在同步",
            RPCPermission.PUBLIC
        )
