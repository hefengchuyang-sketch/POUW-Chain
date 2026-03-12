"""
RPC 数据模型

包含 JSON-RPC 2.0 请求/响应模型、错误码、权限级别和方法注册表。
从 rpc_service.py 拆分，提升模块化。
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class RPCErrorCode(Enum):
    """RPC 错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # 自定义错误
    BLOCK_NOT_FOUND = -32000
    TX_NOT_FOUND = -32001
    ADDRESS_NOT_FOUND = -32002
    INSUFFICIENT_FUNDS = -32003
    NONCE_TOO_LOW = -32004
    GAS_LIMIT_EXCEEDED = -32005


class RPCError(Exception):
    """RPC 错误异常"""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


@dataclass
class RPCRequest:
    """JSON-RPC 2.0 请求"""
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: Any = None
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: Dict) -> 'RPCRequest':
        return cls(
            method=data.get('method', ''),
            params=data.get('params', {}),
            id=data.get('id'),
            jsonrpc=data.get('jsonrpc', '2.0')
        )

    def to_dict(self) -> Dict:
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
            "id": self.id
        }


@dataclass
class RPCResponse:
    """JSON-RPC 2.0 响应"""
    result: Any = None
    error_info: Dict = None
    id: Any = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict:
        resp = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error_info:
            resp["error"] = self.error_info
        else:
            resp["result"] = self.result
        return resp

    @staticmethod
    def success(result: Any, request_id: Any = None) -> 'RPCResponse':
        return RPCResponse(result=result, error_info=None, id=request_id)

    @staticmethod
    def make_error(code: int, message: str, request_id: Any = None) -> 'RPCResponse':
        return RPCResponse(result=None, error_info={"code": code, "message": message}, id=request_id)


class RPCPermission(Enum):
    """RPC 方法权限级别"""
    PUBLIC = "public"
    MINER = "miner"
    USER = "user"
    ADMIN = "admin"


class RPCMethodRegistry:
    """RPC 方法注册表（带权限控制）"""

    def __init__(self):
        self._methods: Dict[str, Callable] = {}
        self._descriptions: Dict[str, str] = {}
        self._permissions: Dict[str, RPCPermission] = {}

    def register(self, name: str, handler: Callable, description: str = "",
                 permission: RPCPermission = RPCPermission.PUBLIC):
        """注册 RPC 方法（带权限）"""
        self._methods[name] = handler
        self._descriptions[name] = description
        self._permissions[name] = permission

    def get(self, name: str) -> Optional[Callable]:
        """获取方法处理器"""
        return self._methods.get(name)

    def get_permission(self, name: str) -> RPCPermission:
        """获取方法所需权限"""
        return self._permissions.get(name, RPCPermission.PUBLIC)

    def list_methods(self) -> List[Dict]:
        """列出所有方法"""
        return [
            {
                "name": name,
                "description": self._descriptions.get(name, ""),
                "permission": self._permissions.get(name, RPCPermission.PUBLIC).value
            }
            for name in self._methods
        ]

    def list_public_methods(self) -> List[Dict]:
        """只列出公开方法"""
        return [
            {"name": name, "description": self._descriptions.get(name, "")}
            for name, perm in self._permissions.items()
            if perm == RPCPermission.PUBLIC
        ]

    def has(self, name: str) -> bool:
        return name in self._methods

    def count(self) -> int:
        return len(self._methods)
