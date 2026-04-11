from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class LoadTestHandler(RPCHandlerBase):
    domain = "loadTest"

    def register_methods(self):
        self.register(
            "loadTest_runScenario", self.svc._load_test_run,
            "运行负载测试场景",
            RPCPermission.ADMIN
        )
        self.register(
            "loadTest_getResults", self.svc._load_test_get_results,
            "获取测试结果",
            RPCPermission.ADMIN
        )
        self.register(
            "loadTest_getMetrics", self.svc._load_test_get_metrics,
            "获取性能指标",
            RPCPermission.PUBLIC
        )
