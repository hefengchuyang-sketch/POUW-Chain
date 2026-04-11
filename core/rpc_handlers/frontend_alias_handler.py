from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class FrontendAliasHandler(RPCHandlerBase):
    domain = "frontendAlias"

    def register_methods(self):
        self.register(
            "status", self.svc._node_get_info,
            "获取节点状态（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "miner_getSectorList", self.svc._frontend_miner_get_sector_list,
            "获取板块币列表（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "miner_getGpuList", self.svc._frontend_miner_get_gpu_list,
            "获取 GPU 列表（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "miner_getEarnings", self.svc._settlement_get_miner_earnings,
            "获取矿工收益（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "market_getComputeOrders", self.svc._compute_get_market,
            "获取算力订单（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "market_createOrder", self.svc._compute_submit_order,
            "创建市场订单（别名）",
            RPCPermission.USER
        )
        self.register(
            "blockchain_getBlocks", self.svc._blockchain_get_latest_blocks,
            "获取区块列表（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "blockchain_getTransaction", self.svc._tx_get,
            "获取交易详情（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "network_getStatus", self.svc._stats_get_network,
            "获取网络状态（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "network_getPeerList", self.svc._node_get_peers,
            "获取节点列表（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "network_getRecentTransactions", self.svc._mempool_get_pending,
            "获取最近交易（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "billing_getDetailed", self.svc._frontend_billing_get_detailed,
            "获取详细计费（别名）",
            RPCPermission.USER
        )
        self.register(
            "dashboard_getSummary", self.svc._dashboard_get_stats,
            "获取仪表盘摘要（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "dashboard_getSectorDistribution", self.svc._frontend_dashboard_get_sector_distribution,
            "获取板块分布（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "exchange_getOrderBook", self.svc._orderbook_get_orderbook,
            "获取订单簿（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "exchange_getMarketInfo", self.svc._orderbook_get_market_price,
            "获取市场信息（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "exchange_createOrder", self.svc._frontend_exchange_create_order,
            "创建交易所订单（别名）",
            RPCPermission.USER
        )
        self.register(
            "p2p_getStatus", self.svc._p2p_get_nat_info,
            "获取 P2P 状态（别名）",
            RPCPermission.PUBLIC
        )
        self.register(
            "dataLifecycle_getStatus", self.svc._frontend_data_lifecycle_get_status,
            "获取数据生命周期状态（别名）",
            RPCPermission.PUBLIC
        )
