"""
[M-08] E2E 加密领域 RPC Handler

从 NodeRPCService 提取 e2e_* 相关 RPC 方法注册。
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
class E2EHandler(RPCHandlerBase):
    """E2E 加密处理器 - 会话握手与分块传输"""

    domain = "e2e"

    def register_methods(self):
        self.register(
            "e2e_createSession", self.svc._e2e_create_session,
            "创建 E2E 加密会话（返回临时公钥）",
            RPCPermission.USER,
        )
        self.register(
            "e2e_handshake", self.svc._e2e_handshake,
            "完成 E2E 密钥协商（提交客户端公钥）",
            RPCPermission.USER,
        )
        self.register(
            "e2e_uploadChunk", self.svc._e2e_upload_chunk,
            "E2E 加密上传：客户端加密 -> 服务端解密存储",
            RPCPermission.USER,
        )
        self.register(
            "e2e_downloadChunk", self.svc._e2e_download_chunk,
            "E2E 加密下载：服务端加密 -> 客户端解密",
            RPCPermission.USER,
        )
        self.register(
            "e2e_closeSession", self.svc._e2e_close_session,
            "关闭 E2E 会话（销毁密钥材料）",
            RPCPermission.USER,
        )
