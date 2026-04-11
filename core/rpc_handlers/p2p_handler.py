"""
[M-25] P2P 直连接口领域 RPC Handler

从 NodeRPCService 提取 p2p_* 相关 RPC 方法注册。
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
class P2PHandler(RPCHandlerBase):
    """P2P 直连处理器 - 连接建立、信令交换与状态查询"""

    domain = "p2p"

    def register_methods(self):
        self.register(
            "p2p_setupConnection", self.svc._p2p_setup_connection,
            "建立 P2P 连接",
            RPCPermission.USER,
        )
        self.register(
            "p2p_createOffer", self.svc._p2p_create_offer,
            "创建连接 Offer",
            RPCPermission.USER,
        )
        self.register(
            "p2p_createAnswer", self.svc._p2p_create_answer,
            "创建连接 Answer",
            RPCPermission.USER,
        )
        self.register(
            "p2p_getConnectionStatus", self.svc._p2p_get_connection_status,
            "获取连接状态",
            RPCPermission.USER,
        )
        self.register(
            "p2p_listConnections", self.svc._p2p_list_connections,
            "列出活跃连接",
            RPCPermission.USER,
        )
        self.register(
            "p2p_closeConnection", self.svc._p2p_close_connection,
            "关闭 P2P 连接",
            RPCPermission.USER,
        )
        self.register(
            "p2p_getNATInfo", self.svc._p2p_get_nat_info,
            "获取 NAT 信息",
            RPCPermission.PUBLIC,
        )
