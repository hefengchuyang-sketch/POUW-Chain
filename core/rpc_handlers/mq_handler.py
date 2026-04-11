"""
[M-27] 消息队列领域 RPC Handler

从 NodeRPCService 提取 mq_* 相关 RPC 方法注册。
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
class MQHandler(RPCHandlerBase):
    """消息队列处理器 - 发布、订阅与队列统计"""

    domain = "mq"

    def register_methods(self):
        self.register(
            "mq_publish", self.svc._mq_publish,
            "发布消息到队列",
            RPCPermission.USER,
        )
        self.register(
            "mq_subscribe", self.svc._mq_subscribe,
            "订阅消息队列",
            RPCPermission.USER,
        )
        self.register(
            "mq_getQueueStats", self.svc._mq_get_queue_stats,
            "获取队列统计信息",
            RPCPermission.PUBLIC,
        )
        self.register(
            "mq_emitEvent", self.svc._mq_emit_event,
            "发送事件",
            RPCPermission.USER,
        )
