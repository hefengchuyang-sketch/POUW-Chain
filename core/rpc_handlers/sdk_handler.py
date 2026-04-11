from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class SDKHandler(RPCHandlerBase):
    domain = "sdk"

    def register_methods(self):
        self.register(
            "sdk_getOpenAPISpec", self.svc._sdk_get_openapi_spec,
            "获取 OpenAPI 规范",
            RPCPermission.PUBLIC
        )
        self.register(
            "sdk_generateSDK", self.svc._sdk_generate_sdk,
            "生成 SDK 代码",
            RPCPermission.PUBLIC
        )
        self.register(
            "sdk_getEndpoints", self.svc._sdk_get_endpoints,
            "获取 API 端点列表",
            RPCPermission.PUBLIC
        )
        self.register(
            "sdk_getExamples", self.svc._sdk_get_examples,
            "获取代码示例",
            RPCPermission.PUBLIC
        )
