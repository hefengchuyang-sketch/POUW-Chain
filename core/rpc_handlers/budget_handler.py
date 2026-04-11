"""
[M-11] 预算管理领域 RPC Handler

从 NodeRPCService 提取 budget_* 相关 RPC 方法注册。
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
class BudgetHandler(RPCHandlerBase):
    """预算管理处理器 - 充值、余额查询与预算锁定"""

    domain = "budget"

    def register_methods(self):
        self.register(
            "budget_deposit", self.svc._budget_deposit,
            "用户充值",
            RPCPermission.USER,
        )
        self.register(
            "budget_getBalance", self.svc._budget_get_balance,
            "获取用户余额",
            RPCPermission.USER,
        )
        self.register(
            "budget_lockForTask", self.svc._budget_lock_for_task,
            "为任务锁定预算",
            RPCPermission.USER,
        )
        self.register(
            "budget_getLockInfo", self.svc._budget_get_lock_info,
            "获取预算锁定信息",
            RPCPermission.USER,
        )
