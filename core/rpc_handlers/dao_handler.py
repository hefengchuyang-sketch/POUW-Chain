"""
[M-01] DAO 治理领域 RPC Handler

从 NodeRPCService 提取的 DAO/国库治理相关 RPC 方法注册。
包含 15 个 RPC 方法:
  dao_stake, dao_unstake, dao_createProposal, dao_vote, dao_executeProposal,
  dao_getProposalStatus, dao_listProposals, dao_getTreasury, dao_getTreasuryConfig,
  dao_setTreasuryRate, dao_getTreasuryReport, dao_createTreasuryProposal,
  dao_treasuryWithdraw, dao_getGovernanceParams, dao_getStakingInfo
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
class DAOHandler(RPCHandlerBase):
    """DAO 领域处理器 — 质押、提案、投票、国库管理"""
    
    domain = "dao"
    
    def register_methods(self):
        """注册 DAO 相关 RPC 方法"""
        
        self.register(
            "dao_stake", self.svc._dao_stake,
            "质押代币", RPCPermission.USER
        )
        self.register(
            "dao_unstake", self.svc._dao_unstake,
            "解除质押", RPCPermission.USER
        )
        self.register(
            "dao_createProposal", self.svc._dao_create_proposal,
            "创建治理提案", RPCPermission.USER
        )
        self.register(
            "dao_vote", self.svc._dao_vote,
            "提案投票", RPCPermission.USER
        )
        self.register(
            "dao_executeProposal", self.svc._dao_execute_proposal,
            "执行提案", RPCPermission.USER
        )
        self.register(
            "dao_getProposalStatus", self.svc._dao_get_proposal_status,
            "获取提案状态", RPCPermission.PUBLIC
        )
        self.register(
            "dao_listProposals", self.svc._dao_list_proposals,
            "列出所有提案", RPCPermission.PUBLIC
        )
        self.register(
            "dao_getTreasury", self.svc._dao_get_treasury,
            "获取国库信息", RPCPermission.PUBLIC
        )
        self.register(
            "dao_getTreasuryConfig", self.svc._dao_get_treasury_config,
            "获取财库配置（税率等）", RPCPermission.PUBLIC
        )
        self.register(
            "dao_setTreasuryRate", self.svc._dao_set_treasury_rate,
            "修改财库税率（需管理员）", RPCPermission.ADMIN
        )
        self.register(
            "dao_getTreasuryReport", self.svc._dao_get_treasury_report,
            "获取财库透明度报告", RPCPermission.PUBLIC
        )
        self.register(
            "dao_createTreasuryProposal", self.svc._dao_create_treasury_proposal,
            "创建财库资金提案", RPCPermission.USER
        )
        self.register(
            "dao_treasuryWithdraw", self.svc._dao_treasury_withdraw,
            "财库提款（需多签/提案通过）", RPCPermission.ADMIN
        )
        self.register(
            "dao_getGovernanceParams", self.svc._dao_get_governance_params,
            "获取治理参数", RPCPermission.PUBLIC
        )
        self.register(
            "dao_getStakingInfo", self.svc._dao_get_staking_info,
            "获取质押信息", RPCPermission.USER
        )
        
        # === 国库透明度接口 ===
        self.register(
            "dao_getTreasuryLimits", self.svc._dao_get_treasury_limits,
            "获取国库补偿限制及使用情况（用户可见）", RPCPermission.PUBLIC
        )
        
        # === 板块动态管理接口 ===
        self.register(
            "sector_getList", self.svc._sector_get_list,
            "获取所有板块列表及状态", RPCPermission.PUBLIC
        )
        self.register(
            "sector_add", self.svc._sector_add,
            "提议新增板块（需社区投票通过）", RPCPermission.USER
        )
        self.register(
            "sector_deactivate", self.svc._sector_deactivate,
            "提议废除板块（需社区投票通过）", RPCPermission.USER
        )
