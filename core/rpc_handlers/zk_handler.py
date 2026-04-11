from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class ZKHandler(RPCHandlerBase):
    domain = "zk"

    def register_methods(self):
        self.register(
            "zk_generateProof", self.svc._zk_generate_proof,
            "生成零知识证明",
            RPCPermission.MINER
        )
        self.register(
            "zk_verifyProof", self.svc._zk_verify_proof,
            "验证零知识证明",
            RPCPermission.PUBLIC
        )
        self.register(
            "zk_getProofStats", self.svc._zk_get_proof_stats,
            "获取证明统计",
            RPCPermission.PUBLIC
        )
