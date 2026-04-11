from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class MinerHandler(RPCHandlerBase):
    domain = "miner"

    def register_methods(self):
        self.register(
            "miner_getList", self.svc._miner_get_list,
            "获取矿工列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "miner_getInfo", self.svc._miner_get_info,
            "获取矿工详细信息",
            RPCPermission.PUBLIC
        )
        self.register(
            "miner_getBehaviorReport", self.svc._miner_get_behavior_report,
            "获取矿工行为报告",
            RPCPermission.PUBLIC
        )
        self.register(
            "miner_register", self.svc._miner_register,
            "注册成为矿工/算力提供者",
            RPCPermission.USER
        )
        self.register(
            "miner_updateProfile", self.svc._miner_update_profile,
            "更新矿工资料",
            RPCPermission.USER
        )
