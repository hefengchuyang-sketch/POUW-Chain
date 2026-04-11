"""
[M-15] 区块链查询领域 RPC Handler

从 NodeRPCService 提取 blockchain_* 主查询接口注册。
方法实现仍在 NodeRPCService 中，通过 self.svc 委托调用。
"""

from core.rpc_handlers import RPCHandlerBase, register_handler_class

try:
    from core.rpc_service import RPCPermission
except ImportError:
    from enum import IntEnum

    class RPCPermission(IntEnum):
        PUBLIC = 0
        USER = 1
        MINER = 2
        ADMIN = 3


@register_handler_class
class BlockchainHandler(RPCHandlerBase):
    """区块链查询处理器 - 高度、区块与最新区块列表"""

    domain = "blockchain"

    def register_methods(self):
        self.register(
            "blockchain_getHeight", self.svc._blockchain_get_height,
            "获取当前区块高度",
            RPCPermission.PUBLIC,
        )
        self.register(
            "blockchain_getBlock", self.svc._blockchain_get_block,
            "获取区块详情",
            RPCPermission.PUBLIC,
        )
        self.register(
            "blockchain_getLatestBlocks", self.svc._blockchain_get_latest_blocks,
            "获取最近区块列表",
            RPCPermission.PUBLIC,
        )
