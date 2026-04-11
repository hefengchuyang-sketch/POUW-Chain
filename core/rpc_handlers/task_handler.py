"""
[M-03] 任务领域 RPC Handler

从 NodeRPCService 提取任务相关 RPC 方法注册。
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
class TaskHandler(RPCHandlerBase):
    """任务领域处理器 — 任务查询、创建、取消、纠纷、结果验收"""

    domain = "task"

    def register_methods(self):
        self.register(
            "task_getList", self.svc._task_get_list,
            "获取任务列表",
            RPCPermission.PUBLIC,
        )
        self.register(
            "task_getInfo", self.svc._task_get_info,
            "获取任务详情",
            RPCPermission.PUBLIC,
        )
        self.register(
            "task_create", self.svc._task_create,
            "创建新任务",
            RPCPermission.USER,
        )
        self.register(
            "task_cancel", self.svc._task_cancel,
            "取消任务",
            RPCPermission.USER,
        )
        self.register(
            "task_raiseDispute", self.svc._task_raise_dispute,
            "对任务发起纠纷",
            RPCPermission.USER,
        )
        self.register(
            "task_acceptResult", self.svc._task_accept_result,
            "接受任务结果并评价",
            RPCPermission.USER,
        )
        self.register(
            "task_getFiles", self.svc._task_get_files,
            "获取任务文件列表",
            RPCPermission.PUBLIC,
        )
        self.register(
            "task_getLogs", self.svc._task_get_logs,
            "获取任务日志",
            RPCPermission.PUBLIC,
        )
        self.register(
            "task_getOutputs", self.svc._task_get_outputs,
            "获取任务输出文件",
            RPCPermission.PUBLIC,
        )
        self.register(
            "task_getRuntimeStatus", self.svc._task_get_runtime_status,
            "获取任务运行状态",
            RPCPermission.PUBLIC,
        )
