"""
[M-18] RPC 元信息领域 Handler

从 NodeRPCService 提取 rpc_* 元信息接口注册。
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
class RPCMetaHandler(RPCHandlerBase):
    """RPC 元信息处理器 - 列出可用方法"""

    domain = "rpc_meta"

    def register_methods(self):
        self.register(
            "rpc_listMethods", self.svc._rpc_list_methods,
            "列出所有可用 RPC 方法",
            RPCPermission.PUBLIC,
        )
