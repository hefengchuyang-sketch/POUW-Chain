from core.rpc_service import RPCPermission
from core.rpc_handlers import RPCHandlerBase, register_handler_class

@register_handler_class
class TxHandler(RPCHandlerBase):
    domain = "tx"

    def register_methods(self):
        self.register(
            "tx_send", self.svc._tx_send,
            "发送已签名交易到网络",
            RPCPermission.USER
        )
        self.register(
            "tx_get", self.svc._tx_get,
            "通过 TXID 查询交易",
            RPCPermission.PUBLIC
        )
        self.register(
            "tx_getByAddress", self.svc._tx_get_by_address,
            "查询地址相关交易",
            RPCPermission.PUBLIC
        )
