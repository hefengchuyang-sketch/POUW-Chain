"""
[M-24] 临时会话密钥领域 RPC Handler

从 NodeRPCService 提取 ephemeralKey_* 相关 RPC 方法注册。
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
class EphemeralKeyHandler(RPCHandlerBase):
    """临时会话密钥处理器 - 会话创建、获取与轮换"""

    domain = "ephemeralKey"

    def register_methods(self):
        self.register(
            "ephemeralKey_createSession", self.svc._ephemeral_create_session,
            "创建临时会话密钥",
            RPCPermission.USER,
        )
        self.register(
            "ephemeralKey_getSessionKey", self.svc._ephemeral_get_session_key,
            "获取会话密钥",
            RPCPermission.USER,
        )
        self.register(
            "ephemeralKey_rotateKey", self.svc._ephemeral_rotate_key,
            "轮换会话密钥",
            RPCPermission.USER,
        )
