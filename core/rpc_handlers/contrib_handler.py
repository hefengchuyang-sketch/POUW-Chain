from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class ContribHandler(RPCHandlerBase):
    domain = "contrib"

    def register_methods(self):
        self.register(
            "contrib_createProposal", self.svc._contrib_create_proposal,
            "创建贡献权重治理提案",
            RPCPermission.USER
        )
        self.register(
            "contrib_vote", self.svc._contrib_vote,
            "贡献权重治理投票",
            RPCPermission.USER
        )
        self.register(
            "contrib_getProposals", self.svc._contrib_get_proposals,
            "获取贡献权重治理提案列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "contrib_getProposal", self.svc._contrib_get_proposal,
            "获取单个提案详情",
            RPCPermission.PUBLIC
        )
        self.register(
            "contrib_getVoterPower", self.svc._contrib_get_voter_power,
            "获取用户投票权详情",
            RPCPermission.PUBLIC
        )
        self.register(
            "contrib_simulateVote", self.svc._contrib_simulate_vote,
            "模拟投票影响",
            RPCPermission.PUBLIC
        )
        self.register(
            "contrib_stake", self.svc._contrib_stake,
            "锁仓质押",
            RPCPermission.USER
        )
        self.register(
            "contrib_unstake", self.svc._contrib_unstake,
            "解除锁仓",
            RPCPermission.USER
        )
        self.register(
            "contrib_finalizeProposal", self.svc._contrib_finalize_proposal,
            "结算提案",
            RPCPermission.USER
        )
        self.register(
            "contrib_executeProposal", self.svc._contrib_execute_proposal,
            "执行已通过提案",
            RPCPermission.ADMIN
        )
        self.register(
            "contrib_getStats", self.svc._contrib_get_stats,
            "获取治理统计",
            RPCPermission.PUBLIC
        )
        self.register(
            "contrib_checkProposerEligibility", self.svc._contrib_check_proposer_eligibility,
            "检查地址是否有资格提交提案",
            RPCPermission.PUBLIC
        )
        self.register(
            "contrib_getProposalTimeRemaining", self.svc._contrib_get_proposal_time_remaining,
            "获取提案剩余时间信息",
            RPCPermission.PUBLIC
        )
        self.register(
            "contrib_checkExpiredProposals", self.svc._contrib_check_expired_proposals,
            "检查并标记过期提案",
            RPCPermission.ADMIN
        )
        self.register(
            "contrib_getPassRequirements", self.svc._contrib_get_pass_requirements,
            "获取提案通过的所有要求",
            RPCPermission.PUBLIC
        )
