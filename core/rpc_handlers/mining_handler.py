from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class MiningHandler(RPCHandlerBase):
    domain = "mining"

    def register_methods(self):
        self.register(
            "mining_getStatus", self.svc._mining_get_status,
            "获取挖矿状态",
            RPCPermission.PUBLIC
        )
        self.register(
            "mining_start", self.svc._mining_start,
            "开始挖矿",
            RPCPermission.USER
        )
        self.register(
            "mining_stop", self.svc._mining_stop,
            "停止挖矿",
            RPCPermission.USER
        )
        self.register(
            "mining_getRewards", self.svc._mining_get_rewards,
            "获取挖矿奖励统计",
            RPCPermission.PUBLIC
        )
        self.register(
            "mining_setMode", self.svc._mining_set_mode,
            "设置挖矿模式（只挖矿/只接单/挖矿+接单）",
            RPCPermission.USER
        )
        self.register(
            "mining_getScore", self.svc._mining_get_score,
            "获取矿工评分详情",
            RPCPermission.PUBLIC
        )
