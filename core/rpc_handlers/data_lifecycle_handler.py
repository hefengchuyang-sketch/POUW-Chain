"""
[M-23] 数据生命周期领域 RPC Handler

从 NodeRPCService 提取 dataLifecycle_* 相关 RPC 方法注册。
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
class DataLifecycleHandler(RPCHandlerBase):
    """数据生命周期处理器 - 资产注册、销毁与证明查询"""

    domain = "dataLifecycle"

    def register_methods(self):
        self.register(
            "dataLifecycle_registerAsset", self.svc._data_register_asset,
            "注册数据资产",
            RPCPermission.USER,
        )
        self.register(
            "dataLifecycle_requestDestruction", self.svc._data_request_destruction,
            "请求数据销毁",
            RPCPermission.USER,
        )
        self.register(
            "dataLifecycle_getDestructionProof", self.svc._data_get_destruction_proof,
            "获取销毁证明",
            RPCPermission.USER,
        )
        self.register(
            "dataLifecycle_listAssets", self.svc._data_list_assets,
            "列出数据资产",
            RPCPermission.USER,
        )
