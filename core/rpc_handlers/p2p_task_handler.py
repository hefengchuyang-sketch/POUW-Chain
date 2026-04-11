from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class P2PTaskHandler(RPCHandlerBase):
    domain = "p2pTask"

    def register_methods(self):
        self.register(
            "p2pTask_create", self.svc._p2p_task_create,
            "创建 P2P 分布式任务",
            RPCPermission.USER
        )
        self.register(
            "p2pTask_distribute", self.svc._p2p_task_distribute,
            "分发任务到 P2P 网络",
            RPCPermission.USER
        )
        self.register(
            "p2pTask_getStatus", self.svc._p2p_task_get_status,
            "获取 P2P 任务状态",
            RPCPermission.PUBLIC
        )
        self.register(
            "p2pTask_getList", self.svc._p2p_task_get_list,
            "获取所有 P2P 任务列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "p2pTask_getStats", self.svc._p2p_task_get_stats,
            "获取 P2P 任务分发器统计",
            RPCPermission.PUBLIC
        )
        self.register(
            "p2pTask_cancel", self.svc._p2p_task_cancel,
            "取消 P2P 任务",
            RPCPermission.USER
        )
        self.register(
            "p2pTask_registerMiner", self.svc._p2p_task_register_miner,
            "注册矿工节点",
            RPCPermission.USER
        )
        self.register(
            "p2pTask_getMiners", self.svc._p2p_task_get_miners,
            "获取可用矿工列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "p2pTask_getResult", self.svc._p2p_task_get_result,
            "获取任务计算结果",
            RPCPermission.USER
        )
