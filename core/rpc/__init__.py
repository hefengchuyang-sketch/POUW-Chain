"""
RPC 包 - 模块化 RPC 服务

结构:
    core/rpc/
    ├── __init__.py     # 统一导出
    ├── models.py       # 数据模型 (RPCRequest, RPCResponse, RPCError, ...)
    └── server.py       # HTTP 服务器 (RPCServer, RPCHTTPHandler, RPCClient)

NodeRPCService 仍在 core/rpc_service.py 中 (7700+ 行)，后续可进一步拆分为 handler mixins。
"""

# 模型
from .models import (
    RPCErrorCode,
    RPCError,
    RPCRequest,
    RPCResponse,
    RPCPermission,
    RPCMethodRegistry,
)

# 服务器
from .server import (
    RPCHTTPHandler,
    RPCServer,
    RPCClient,
)

__all__ = [
    # 模型
    "RPCErrorCode",
    "RPCError",
    "RPCRequest",
    "RPCResponse",
    "RPCPermission",
    "RPCMethodRegistry",
    # 服务器
    "RPCHTTPHandler",
    "RPCServer",
    "RPCClient",
]
