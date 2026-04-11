"""
[M-17] 质押管理领域 RPC Handler

从 NodeRPCService 提取 staking_* 相关 RPC 方法注册。
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
class StakingHandler(RPCHandlerBase):
    """质押管理处理器 - 记录查询、质押与解押"""

    domain = "staking"

    def register_methods(self):
        self.register(
            "staking_getRecords", self.svc._staking_get_records,
            "获取质押记录",
            RPCPermission.PUBLIC,
        )
        self.register(
            "staking_stake", self.svc._staking_stake,
            "质押代币",
            RPCPermission.USER,
        )
        self.register(
            "staking_unstake", self.svc._staking_unstake,
            "解除质押",
            RPCPermission.USER,
        )
