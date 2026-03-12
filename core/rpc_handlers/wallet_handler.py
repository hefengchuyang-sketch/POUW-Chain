"""
[M-01] 钱包领域 RPC Handler

从 NodeRPCService 提取的钱包相关 RPC 方法注册。
方法实现仍在 NodeRPCService 中，通过 self.svc 委托调用。
后续迁移时可将方法实现也移入本文件。

包含 10 个 RPC 方法:
  wallet_create, wallet_import, wallet_getInfo, wallet_unlock, wallet_lock,
  wallet_transfer, wallet_exportKeystore, wallet_importKeystore
  + 别名: wallet_getAddress, wallet_getBalance
"""

from core.rpc_handlers import RPCHandlerBase, register_handler_class

try:
    from core.rpc_service import RPCPermission
except ImportError:
    # 防止循环导入
    from enum import IntEnum
    class RPCPermission(IntEnum):
        PUBLIC = 0
        USER = 1
        MINER = 2
        ADMIN = 3


@register_handler_class
class WalletHandler(RPCHandlerBase):
    """钱包领域处理器 — 管理钱包创建、导入、解锁、转账、密钥管理"""
    
    domain = "wallet"
    
    def register_methods(self):
        """注册钱包相关 RPC 方法"""
        
        # [H-13] wallet_create/import/unlock 需认证，防止远程攻击者篡改节点钱包
        self.register(
            "wallet_create", self.svc._wallet_create,
            "创建新钱包（生成助记词）",
            RPCPermission.USER
        )
        self.register(
            "wallet_import", self.svc._wallet_import,
            "从助记词导入钱包",
            RPCPermission.USER
        )
        self.register(
            "wallet_getInfo", self.svc._wallet_get_info,
            "获取当前钱包信息",
            RPCPermission.PUBLIC
        )
        self.register(
            "wallet_unlock", self.svc._wallet_unlock,
            "解锁钱包",
            RPCPermission.USER
        )
        self.register(
            "wallet_lock", self.svc._wallet_lock,
            "锁定钱包（清除敏感数据）",
            RPCPermission.USER
        )
        self.register(
            "wallet_transfer", self.svc._wallet_transfer,
            "发送转账交易",
            RPCPermission.USER
        )
        self.register(
            "wallet_exportKeystore", self.svc._wallet_export_keystore,
            "导出加密密钥文件",
            RPCPermission.USER
        )
        self.register(
            "wallet_importKeystore", self.svc._wallet_import_keystore,
            "从密钥文件导入钱包",
            RPCPermission.USER
        )
        
        # 注意: wallet_getBalance/wallet_getTransactions 是别名，
        # 指向 account 域方法，保留在 rpc_service.py 中注册
