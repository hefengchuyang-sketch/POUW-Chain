"""
[M-04] 调度领域 RPC Handler

从 NodeRPCService 提取 ComputeScheduler 相关 RPC 方法注册。
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
class SchedulerHandler(RPCHandlerBase):
    """调度领域处理器 — 矿工注册心跳、任务提交与盲批次挑战"""

    domain = "scheduler"

    def register_methods(self):
        self.register(
            "scheduler_registerMiner", self.svc._scheduler_register_miner,
            "矿工注册到调度器",
            RPCPermission.MINER,
        )
        self.register(
            "scheduler_heartbeat", self.svc._scheduler_heartbeat,
            "矿工心跳（获取待执行任务",
            RPCPermission.MINER,
        )
        self.register(
            "scheduler_submitResult", self.svc._scheduler_submit_result,
            "矿工提交任务结果",
            RPCPermission.MINER,
        )
        self.register(
            "scheduler_getTask", self.svc._scheduler_get_task,
            "查询任务状态",
            RPCPermission.PUBLIC,
        )
        self.register(
            "scheduler_rateMiner", self.svc._scheduler_rate_miner,
            "用户评价矿工",
            RPCPermission.USER,
        )
        self.register(
            "scheduler_getBlindBatch", self.svc._scheduler_get_blind_batch,
            "获取矿工盲批次挖矿挑战",
            RPCPermission.MINER,
        )
        self.register(
            "scheduler_submitBlindBatch", self.svc._scheduler_submit_blind_batch,
            "提交盲批次挖矿结果",
            RPCPermission.MINER,
        )
        self.register(
            "scheduler_getMinerTrust", self.svc._scheduler_get_miner_trust,
            "查询矿工信誉分",
            RPCPermission.PUBLIC,
        )
