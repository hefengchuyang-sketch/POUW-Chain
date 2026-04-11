"""
[M-02] 账户领域 RPC Handler

从 NodeRPCService 提取账户相关 RPC 方法注册。
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
class AccountHandler(RPCHandlerBase):
    """账户领域处理器 — 余额、UTXO、历史、子地址与钱包别名接口"""

    domain = "account"

    def register_methods(self):
        # === 账户主接口 ===
        self.register(
            "account_getBalance", self.svc._account_get_balance,
            "查询地址余额",
            RPCPermission.PUBLIC,
        )
        self.register(
            "account_getUTXOs", self.svc._account_get_utxos,
            "获取地址可用 UTXO",
            RPCPermission.PUBLIC,
        )
        self.register(
            "account_traceUTXO", self.svc._account_trace_utxo,
            "追溯 UTXO 来源直到 coinbase",
            RPCPermission.PUBLIC,
        )
        self.register(
            "account_getNonce", self.svc._account_get_nonce,
            "获取地址 nonce",
            RPCPermission.PUBLIC,
        )
        self.register(
            "account_getTransactions", self.svc._account_get_transactions,
            "获取交易历史",
            RPCPermission.USER,
        )
        self.register(
            "account_getSubAddresses", self.svc._account_get_sub_addresses,
            "获取子地址列表",
            RPCPermission.USER,
        )
        self.register(
            "account_createSubAddress", self.svc._account_create_sub_address,
            "创建子地址",
            RPCPermission.USER,
        )

        # === 钱包别名（由账户能力支撑） ===
        self.register(
            "wallet_getBalance", self.svc._account_get_balance,
            "获取钱包余额（别名）",
            RPCPermission.USER,
        )
        self.register(
            "wallet_getTransactions", self.svc._account_get_transactions,
            "获取钱包交易记录（别名）",
            RPCPermission.USER,
        )
