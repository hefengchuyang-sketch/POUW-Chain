from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class BlockHandler(RPCHandlerBase):
    domain = "block"

    def register_methods(self):
        self.register(
            "block_getLatest", self.svc._block_get_latest,
            "获取最新区块",
            RPCPermission.PUBLIC
        )
        self.register(
            "block_getByHeight", self.svc._block_get_by_height,
            "通过高度获取区块",
            RPCPermission.PUBLIC
        )
        self.register(
            "block_getByHash", self.svc._block_get_by_hash,
            "通过哈希获取区块",
            RPCPermission.PUBLIC
        )
