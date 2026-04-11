"""
[M-06] 加密任务领域 RPC Handler

从 NodeRPCService 提取 encryptedTask_* 相关 RPC 方法注册。
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
class EncryptedTaskHandler(RPCHandlerBase):
    """加密任务处理器 - 加密任务创建、执行、查询与结算"""

    domain = "encryptedTask"

    def register_methods(self):
        self.register(
            "encryptedTask_create", self.svc._encrypted_task_create,
            "创建加密任务",
            RPCPermission.USER,
        )
        self.register(
            "encryptedTask_submit", self.svc._encrypted_task_submit,
            "提交加密任务到网络",
            RPCPermission.USER,
        )
        self.register(
            "encryptedTask_getStatus", self.svc._encrypted_task_get_status,
            "获取加密任务状态",
            RPCPermission.PUBLIC,
        )
        self.register(
            "encryptedTask_getResult", self.svc._encrypted_task_get_result,
            "获取加密任务结果",
            RPCPermission.USER,
        )
        self.register(
            "encryptedTask_process", self.svc._encrypted_task_process,
            "处理加密任务（矿工）",
            RPCPermission.MINER,
        )
        self.register(
            "encryptedTask_getBillingReport", self.svc._encrypted_task_billing,
            "获取任务计费报告",
            RPCPermission.USER,
        )
        self.register(
            "encryptedTask_generateKeypair", self.svc._encrypted_task_generate_keypair,
            "生成加密密钥",
            RPCPermission.USER,
        )
        self.register(
            "encryptedTask_registerMiner", self.svc._encrypted_task_register_miner,
            "注册矿工公钥",
            RPCPermission.MINER,
        )
        self.register(
            "encryptedTask_cancel", self.svc._encrypted_task_cancel,
            "取消加密任务（退还预算，国库补偿矿工带宽）",
            RPCPermission.USER,
        )
