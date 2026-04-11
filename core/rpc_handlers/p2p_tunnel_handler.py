"""
[M-09] P2P 数据隧道领域 RPC Handler

从 NodeRPCService 提取 p2pTunnel_* 相关 RPC 方法注册。
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
class P2PTunnelHandler(RPCHandlerBase):
    """P2P 数据隧道处理器 - 端点注册、票据申请与状态查询"""

    domain = "p2pTunnel"

    def register_methods(self):
        self.register(
            "p2pTunnel_registerEndpoint", self.svc._p2p_tunnel_register_endpoint,
            "矿工注册 P2P 数据端点",
            RPCPermission.USER,
        )
        self.register(
            "p2pTunnel_requestTicket", self.svc._p2p_tunnel_request_ticket,
            "请求 P2P 连接票据（用户侧）",
            RPCPermission.USER,
        )
        self.register(
            "p2pTunnel_getStatus", self.svc._p2p_tunnel_get_status,
            "查询 P2P 传输状态",
            RPCPermission.USER,
        )
        self.register(
            "p2pTunnel_startServer", self.svc._p2p_tunnel_start_server,
            "启动矿工侧 P2P 数据服务器",
            RPCPermission.USER,
        )
        self.register(
            "p2pTunnel_getMinerP2PInfo", self.svc._p2p_tunnel_get_miner_info,
            "查询矿工 P2P 可用状态",
            RPCPermission.PUBLIC,
        )
