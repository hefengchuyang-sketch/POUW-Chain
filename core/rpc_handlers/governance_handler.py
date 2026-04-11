from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class GovernanceHandler(RPCHandlerBase):
    domain = "governance"

    def register_methods(self):
        self.register(
            "governance_vote", self.svc._governance_vote,
            "提交治理投票",
            RPCPermission.USER
        )
        self.register(
            "governance_getProposals", self.svc._governance_get_proposals,
            "获取治理提案列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "governance_getProposal", self.svc._governance_get_proposal,
            "获取单个治理提案详情",
            RPCPermission.PUBLIC
        )
        self.register(
            "governance_createProposal", self.svc._governance_create_proposal,
            "创建治理提案",
            RPCPermission.USER
        )
