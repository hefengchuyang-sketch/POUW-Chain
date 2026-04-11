"""
[M-26] DID 去中心化身份领域 RPC Handler

从 NodeRPCService 提取 did_* 相关 RPC 方法注册。
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
class DIDHandler(RPCHandlerBase):
    """DID 处理器 - 身份创建、绑定、凭证与信誉查询"""

    domain = "did"

    def register_methods(self):
        self.register(
            "did_create", self.svc._did_create,
            "创建 DID 身份",
            RPCPermission.USER,
        )
        self.register(
            "did_resolve", self.svc._did_resolve,
            "解析 DID",
            RPCPermission.PUBLIC,
        )
        self.register(
            "did_bindWallet", self.svc._did_bind_wallet,
            "绑定钱包地址",
            RPCPermission.USER,
        )
        self.register(
            "did_issueCredential", self.svc._did_issue_credential,
            "颁发凭证",
            RPCPermission.ADMIN,
        )
        self.register(
            "did_verifyCredential", self.svc._did_verify_credential,
            "验证凭证",
            RPCPermission.PUBLIC,
        )
        self.register(
            "did_getReputation", self.svc._did_get_reputation,
            "获取信誉",
            RPCPermission.PUBLIC,
        )
        self.register(
            "did_getReputationTier", self.svc._did_get_reputation_tier,
            "获取信誉等级",
            RPCPermission.PUBLIC,
        )
        self.register(
            "did_checkSybilRisk", self.svc._did_check_sybil_risk,
            "检查女巫风险",
            RPCPermission.PUBLIC,
        )
