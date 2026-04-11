"""
[M-28] 数据冗余领域 RPC Handler

从 NodeRPCService 提取 redundancy_* 相关 RPC 方法注册。
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
class RedundancyHandler(RPCHandlerBase):
    """数据冗余处理器 - 存储、检索、备份与统计"""

    domain = "redundancy"

    def register_methods(self):
        self.register(
            "redundancy_storeData", self.svc._redundancy_store_data,
            "存储数据（带冗余）",
            RPCPermission.USER,
        )
        self.register(
            "redundancy_retrieveData", self.svc._redundancy_retrieve_data,
            "检索数据",
            RPCPermission.USER,
        )
        self.register(
            "redundancy_createBackup", self.svc._redundancy_create_backup,
            "创建备份",
            RPCPermission.ADMIN,
        )
        self.register(
            "redundancy_getStats", self.svc._redundancy_get_stats,
            "获取冗余统计",
            RPCPermission.PUBLIC,
        )
