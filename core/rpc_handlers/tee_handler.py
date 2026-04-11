"""
[M-19] TEE 可信执行环境领域 RPC Handler

从 NodeRPCService 提取 tee_* 相关 RPC 方法注册。
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
class TEEHandler(RPCHandlerBase):
    """TEE 处理器 - 节点注册、认证、机密任务与审计查询"""

    domain = "tee"

    def register_methods(self):
        self.register(
            "tee_registerNode", self.svc._tee_register_node,
            "注册 TEE 节点",
            RPCPermission.MINER,
        )
        self.register(
            "tee_submitAttestation", self.svc._tee_submit_attestation,
            "提交 TEE 认证报告",
            RPCPermission.MINER,
        )
        self.register(
            "tee_getNodeInfo", self.svc._tee_get_node_info,
            "获取 TEE 节点信息",
            RPCPermission.PUBLIC,
        )
        self.register(
            "tee_listNodes", self.svc._tee_list_nodes,
            "列出所有 TEE 节点",
            RPCPermission.PUBLIC,
        )
        self.register(
            "tee_createConfidentialTask", self.svc._tee_create_confidential_task,
            "创建机密任务",
            RPCPermission.USER,
        )
        self.register(
            "tee_deployConfidentialModel", self.svc._tee_deploy_confidential_model,
            "部署端到端机密加密模型",
            RPCPermission.USER,
        )
        self.register(
            "tee_getTaskResult", self.svc._tee_get_task_result,
            "获取机密任务结果",
            RPCPermission.USER,
        )
        self.register(
            "tee_getPricing", self.svc._tee_get_pricing,
            "获取 TEE 定价信息",
            RPCPermission.PUBLIC,
        )
        self.register(
            "tee_getRolloutAudit", self.svc._tee_get_rollout_audit,
            "获取 TEE 灰度审计事件",
            RPCPermission.ADMIN,
        )
        self.register(
            "tee_getKmsAudit", self.svc._tee_get_kms_audit,
            "获取 TEE KMS gate 审计日志",
            RPCPermission.ADMIN,
        )
