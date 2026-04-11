from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class PrivacyHandler(RPCHandlerBase):
    domain = "privacy"

    def register_methods(self):
        self.register(
            "privacy_getStatus", self.svc._privacy_get_status,
            "获取隐私状态",
            RPCPermission.PUBLIC
        )
        self.register(
            "privacy_rotateAddress", self.svc._privacy_rotate_address,
            "轮换地址",
            RPCPermission.USER
        )
