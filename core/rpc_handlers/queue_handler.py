"""
[M-14] 任务队列领域 RPC Handler

从 NodeRPCService 提取 queue_* 相关 RPC 方法注册。
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
class QueueHandler(RPCHandlerBase):
    """任务队列处理器 - 入队、排位、预估等待与统计"""

    domain = "queue"

    def register_methods(self):
        self.register(
            "queue_enqueue", self.svc._queue_enqueue,
            "任务入队",
            RPCPermission.USER,
        )
        self.register(
            "queue_getPosition", self.svc._queue_get_position,
            "获取队列位置",
            RPCPermission.USER,
        )
        self.register(
            "queue_getEstimatedWaitTime", self.svc._queue_get_estimated_wait_time,
            "获取预估等待时间",
            RPCPermission.USER,
        )
        self.register(
            "queue_getStats", self.svc._queue_get_stats,
            "获取队列统计",
            RPCPermission.PUBLIC,
        )
