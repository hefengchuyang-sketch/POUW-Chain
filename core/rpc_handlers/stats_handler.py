from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class StatsHandler(RPCHandlerBase):
    domain = "stats"

    def register_methods(self):
        self.register(
            "stats_getNetwork", self.svc._stats_get_network,
            "获取网络统计信息",
            RPCPermission.PUBLIC
        )
        self.register(
            "stats_getBlocks", self.svc._stats_get_blocks,
            "获取区块统计",
            RPCPermission.PUBLIC
        )
        self.register(
            "stats_getTasks", self.svc._stats_get_tasks,
            "获取任务统计",
            RPCPermission.PUBLIC
        )
