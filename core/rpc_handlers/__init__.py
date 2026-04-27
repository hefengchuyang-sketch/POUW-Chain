"""
[M-01] RPC Handler 拆分基础设施

将 NodeRPCService 的 8400+ 行拆分为领域处理器（Domain Handler）。
每个 Handler 负责一组相关 RPC 方法的注册和实现。

架构模式:
    1. RPCHandlerBase 定义 handler 基类（持有 service 引用）
    2. 各领域 Handler 继承 RPCHandlerBase
    3. NodeRPCService 创建 handler 实例并调用 register_methods()
    4. Handler 方法通过 self.svc 访问 NodeRPCService 状态

迁移路径:
    Phase 1: 创建基础设施 + 提取 wallet/dao 域
    Phase 2: 提取 account 域
    Phase 3: 提取 task 域
    Phase 4: 提取 scheduler 域
    Phase 5: 提取 compute 域
    Phase 6: 提取 encryptedTask 域
    Phase 7: 提取 file 域
    Phase 8: 提取 e2e 域
    Phase 9: 提取 p2pTunnel 域
    Phase 10: 提取 pricing 域
    Phase 11: 提取 budget 域
    Phase 12: 提取 settlement 域
    Phase 13: 提取 market 域
    Phase 14: 提取 queue 域
    Phase 15: 提取 blockchain/order 域
    Phase 16: 提取 staking/rpc_meta 域
    Phase 17: 提取 tee 域
    Phase 18: 提取 orderbook 域
    Phase 19: 提取 futures/billing 域
    Phase 20: 提取 dataLifecycle/ephemeralKey 域
    Phase 21: 提取 p2p/did 域
    Phase 22: 提取 mq/redundancy 域
    Phase 23: 提取 loadTest/zk 域
    Phase 24: 提取 security/audit/revenue/monitor/sdk 域
    Phase 25: 提取 p2pTask/cluster 域
    Phase 26: 提取 frontend alias 域
    Phase 27: 提取 governance/contrib 域
    Phase 28: 提取基础链路域（dashboard/miner/stats/tx/mempool/block/chain/mining/sector/privacy/node/witness）
    Phase 29: 逐步迁移其他域
    Phase 30: NodeRPCService 仅保留 handle_request + handler 调度

使用方式:
    from core.rpc_handlers import RPCHandlerBase, load_all_handlers
    
    class WalletHandler(RPCHandlerBase):
        domain = "wallet"
        
        def register_methods(self):
            self.register("wallet_create", self._wallet_create, "创建钱包", RPCPermission.USER)
        
        def _wallet_create(self, **kwargs):
            return self.svc._wallet_create(**kwargs)  # 委托到 service
"""

from typing import TYPE_CHECKING, List, Type

if TYPE_CHECKING:
    from core.rpc_service import NodeRPCService


class RPCHandlerBase:
    """
    RPC 领域处理器基类。
    
    每个子类负责一组相关 RPC 方法。
    通过 self.svc 访问 NodeRPCService 的完整状态。
    """
    
    # 子类必须设置: 领域名称（用于日志和注册）
    domain: str = "base"
    
    def __init__(self, service: 'NodeRPCService'):
        self.svc = service
    
    def register(self, method_name: str, handler, description: str, permission):
        """便捷注册方法到 service.registry"""
        self.svc.registry.register(method_name, handler, description, permission)
    
    def register_methods(self):
        """子类重写：注册所有 RPC 方法到 registry"""
        raise NotImplementedError(f"{self.__class__.__name__} must implement register_methods()")


# ==================== Handler 注册表 ====================

# 所有已知的 handler 类（在此列表中注册）
_handler_classes: List[Type[RPCHandlerBase]] = []


def register_handler_class(cls: Type[RPCHandlerBase]):
    """装饰器: 注册 handler 类到全局列表"""
    _handler_classes.append(cls)
    return cls


def load_all_handlers(service: 'NodeRPCService') -> List[RPCHandlerBase]:
    """
    实例化并注册所有已发现的 handler。
    
    Returns:
        已加载的 handler 实例列表
    """
    # 触发 handler 模块的导入（使 @register_handler_class 生效）
    _discover_handlers()
    
    handlers = []
    for cls in _handler_classes:
        try:
            handler = cls(service)
            handler.register_methods()
            handlers.append(handler)
        except Exception as e:
            print(f"[RPC] Handler {cls.domain} 加载失败: {e}")
    
    return handlers


def _discover_handlers():
    try:
        from core.rpc_handlers import security_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import audit_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import revenue_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import monitor_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import sdk_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import load_test_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import zk_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import p2p_task_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import cluster_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import frontend_alias_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import governance_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import contrib_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import dashboard_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import miner_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import stats_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import tx_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import mempool_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import block_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import chain_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import mining_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import sector_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import privacy_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import node_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import witness_handler  # noqa: F401
    except ImportError:
        pass
    # 导入其余 handler 模块
    try:
        from core.rpc_handlers import account_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import task_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import scheduler_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import compute_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import encrypted_task_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import file_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import e2e_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import p2p_tunnel_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import pricing_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import budget_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import settlement_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import market_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import queue_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import blockchain_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import order_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import staking_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import rpc_meta_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import tee_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import orderbook_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import futures_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import billing_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import data_lifecycle_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import ephemeral_key_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import p2p_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import did_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import mq_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import redundancy_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import wallet_handler  # noqa: F401
    except ImportError:
        pass
    try:
        from core.rpc_handlers import dao_handler  # noqa: F401
    except ImportError:
        pass
