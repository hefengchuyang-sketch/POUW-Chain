"""
sdk_api.py - SDK 和 API 支持系统

Phase 10 功能：
1. 开发者 SDK
2. API 文档生成
3. 代码示例
4. SDK 客户端
5. API 版本管理
6. 请求/响应序列化
"""

import time
import uuid
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable, Type
from enum import Enum
import inspect


# ============== 枚举类型 ==============

class APIVersion(Enum):
    """API 版本"""
    V1 = "v1"
    V2 = "v2"


class HTTPMethod(Enum):
    """HTTP 方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class ParameterLocation(Enum):
    """参数位置"""
    QUERY = "query"
    PATH = "path"
    BODY = "body"
    HEADER = "header"


class AuthType(Enum):
    """认证类型"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    SIGNATURE = "signature"


# ============== 数据结构 ==============

@dataclass
class APIParameter:
    """API 参数"""
    name: str
    param_type: str = "string"         # string, integer, number, boolean, array, object
    location: ParameterLocation = ParameterLocation.BODY
    required: bool = False
    default: Any = None
    description: str = ""
    example: Any = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.param_type,
            "in": self.location.value,
            "required": self.required,
            "description": self.description,
            "example": self.example,
        }


@dataclass
class APIEndpoint:
    """API 端点"""
    path: str
    method: HTTPMethod = HTTPMethod.POST
    
    # 文档
    name: str = ""
    summary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # 参数
    parameters: List[APIParameter] = field(default_factory=list)
    
    # 响应
    response_type: str = "object"
    response_example: Any = None
    
    # 认证
    auth_required: bool = True
    auth_type: AuthType = AuthType.API_KEY
    
    # 处理函数
    handler: Optional[Callable] = None
    
    # 版本
    version: APIVersion = APIVersion.V1
    deprecated: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "method": self.method.value,
            "name": self.name,
            "summary": self.summary,
            "description": self.description,
            "tags": self.tags,
            "parameters": [p.to_dict() for p in self.parameters],
            "response_type": self.response_type,
            "auth_required": self.auth_required,
            "deprecated": self.deprecated,
        }


@dataclass
class APIDoc:
    """API 文档"""
    title: str = "POUW Chain API"
    version: str = "1.0.0"
    description: str = ""
    
    # 服务器
    servers: List[Dict] = field(default_factory=list)
    
    # 端点
    endpoints: List[APIEndpoint] = field(default_factory=list)
    
    # 认证
    security_schemes: Dict = field(default_factory=dict)
    
    # 标签
    tags: List[Dict] = field(default_factory=list)
    
    def to_openapi(self) -> Dict:
        """转换为 OpenAPI 格式"""
        paths = {}
        
        for endpoint in self.endpoints:
            if endpoint.path not in paths:
                paths[endpoint.path] = {}
            
            method_key = endpoint.method.value.lower()
            paths[endpoint.path][method_key] = {
                "summary": endpoint.summary,
                "description": endpoint.description,
                "tags": endpoint.tags,
                "parameters": [p.to_dict() for p in endpoint.parameters if p.location != ParameterLocation.BODY],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "example": endpoint.response_example,
                            }
                        }
                    }
                },
                "deprecated": endpoint.deprecated,
            }
            
            # 请求体
            body_params = [p for p in endpoint.parameters if p.location == ParameterLocation.BODY]
            if body_params:
                paths[endpoint.path][method_key]["requestBody"] = {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    p.name: {"type": p.param_type, "description": p.description}
                                    for p in body_params
                                },
                                "required": [p.name for p in body_params if p.required],
                            }
                        }
                    }
                }
        
        return {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "servers": self.servers or [{"url": "http://localhost:8545"}],
            "paths": paths,
            "components": {
                "securitySchemes": self.security_schemes or {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                    }
                }
            },
            "tags": self.tags,
        }


@dataclass
class CodeExample:
    """代码示例"""
    language: str                      # python, javascript, curl, etc.
    title: str = ""
    description: str = ""
    code: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "language": self.language,
            "title": self.title,
            "description": self.description,
            "code": self.code,
        }


@dataclass
class SDKMethod:
    """SDK 方法"""
    name: str
    endpoint: str
    method: HTTPMethod = HTTPMethod.POST
    
    # 参数
    parameters: List[APIParameter] = field(default_factory=list)
    
    # 返回类型
    return_type: str = "Dict"
    
    # 文档
    docstring: str = ""
    examples: List[CodeExample] = field(default_factory=list)


# ============== SDK 客户端生成器 ==============

class SDKGenerator:
    """SDK 生成器"""
    
    def __init__(self, api_doc: APIDoc):
        self.api_doc = api_doc
    
    def generate_python_sdk(self) -> str:
        """生成 Python SDK"""
        lines = [
            '"""',
            f'{self.api_doc.title} Python SDK',
            f'Version: {self.api_doc.version}',
            '"""',
            '',
            'import requests',
            'import json',
            'from typing import Dict, List, Optional, Any',
            '',
            '',
            'class POUWChainClient:',
            '    """POUW Chain API Client"""',
            '    ',
            '    def __init__(self, base_url: str = "http://localhost:8545", api_key: str = ""):',
            '        self.base_url = base_url.rstrip("/")',
            '        self.api_key = api_key',
            '        self.session = requests.Session()',
            '        if api_key:',
            '            self.session.headers["X-API-Key"] = api_key',
            '    ',
            '    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:',
            '        """发送请求"""',
            '        url = f"{self.base_url}{endpoint}"',
            '        response = self.session.request(method, url, **kwargs)',
            '        response.raise_for_status()',
            '        return response.json()',
            '    ',
            '    def rpc_call(self, method: str, params: Dict = None) -> Dict:',
            '        """JSON-RPC 调用"""',
            '        payload = {',
            '            "jsonrpc": "2.0",',
            '            "method": method,',
            '            "params": params or {},',
            '            "id": 1,',
            '        }',
            '        response = self.session.post(self.base_url, json=payload)',
            '        response.raise_for_status()',
            '        return response.json().get("result", {})',
            '',
        ]
        
        # 生成方法
        for endpoint in self.api_doc.endpoints:
            method_name = self._to_method_name(endpoint.name or endpoint.path)
            
            # 参数列表
            params = []
            for p in endpoint.parameters:
                if p.required:
                    params.append(f'{p.name}: {self._py_type(p.param_type)}')
                else:
                    default = repr(p.default) if p.default is not None else 'None'
                    params.append(f'{p.name}: {self._py_type(p.param_type)} = {default}')
            
            param_str = ', '.join(params)
            
            lines.extend([
                f'    def {method_name}(self{", " + param_str if params else ""}) -> Dict:',
                f'        """',
                f'        {endpoint.summary or endpoint.name}',
                f'        ',
                f'        {endpoint.description}',
                f'        """',
            ])
            
            # 构建请求
            if endpoint.method == HTTPMethod.POST:
                body_params = {p.name: p.name for p in endpoint.parameters if p.location == ParameterLocation.BODY}
                if body_params:
                    lines.append(f'        data = {{{", ".join(f"{k!r}: {v}" for k, v in body_params.items())}}}')
                    lines.append(f'        return self._request("POST", "{endpoint.path}", json=data)')
                else:
                    lines.append(f'        return self._request("POST", "{endpoint.path}")')
            else:
                query_params = [p.name for p in endpoint.parameters if p.location == ParameterLocation.QUERY]
                if query_params:
                    lines.append(f'        params = {{{", ".join(f"{p!r}: {p}" for p in query_params)}}}')
                    lines.append(f'        return self._request("{endpoint.method.value}", "{endpoint.path}", params=params)')
                else:
                    lines.append(f'        return self._request("{endpoint.method.value}", "{endpoint.path}")')
            
            lines.append('')
        
        return '\n'.join(lines)
    
    def generate_javascript_sdk(self) -> str:
        """生成 JavaScript SDK"""
        lines = [
            '/**',
            f' * {self.api_doc.title} JavaScript SDK',
            f' * Version: {self.api_doc.version}',
            ' */',
            '',
            'class POUWChainClient {',
            '  constructor(baseUrl = "http://localhost:8545", apiKey = "") {',
            '    this.baseUrl = baseUrl.replace(/\\/$/, "");',
            '    this.apiKey = apiKey;',
            '  }',
            '',
            '  async _request(method, endpoint, options = {}) {',
            '    const url = `${this.baseUrl}${endpoint}`;',
            '    const headers = {',
            '      "Content-Type": "application/json",',
            '      ...(this.apiKey && { "X-API-Key": this.apiKey }),',
            '    };',
            '    ',
            '    const response = await fetch(url, {',
            '      method,',
            '      headers,',
            '      ...options,',
            '    });',
            '    ',
            '    if (!response.ok) {',
            '      throw new Error(`HTTP ${response.status}: ${response.statusText}`);',
            '    }',
            '    ',
            '    return response.json();',
            '  }',
            '',
            '  async rpcCall(method, params = {}) {',
            '    const payload = {',
            '      jsonrpc: "2.0",',
            '      method,',
            '      params,',
            '      id: 1,',
            '    };',
            '    ',
            '    const response = await fetch(this.baseUrl, {',
            '      method: "POST",',
            '      headers: { "Content-Type": "application/json" },',
            '      body: JSON.stringify(payload),',
            '    });',
            '    ',
            '    const data = await response.json();',
            '    return data.result;',
            '  }',
            '',
        ]
        
        # 生成方法
        for endpoint in self.api_doc.endpoints:
            method_name = self._to_camel_case(endpoint.name or endpoint.path)
            
            params = [p.name for p in endpoint.parameters]
            param_str = ', '.join(params)
            
            lines.extend([
                f'  /**',
                f'   * {endpoint.summary or endpoint.name}',
                f'   * {endpoint.description}',
                f'   */',
                f'  async {method_name}({param_str}) {{',
            ])
            
            if endpoint.method == HTTPMethod.POST:
                body_params = [p.name for p in endpoint.parameters if p.location == ParameterLocation.BODY]
                if body_params:
                    lines.append(f'    const body = {{ {", ".join(body_params)} }};')
                    lines.append(f'    return this._request("POST", "{endpoint.path}", {{ body: JSON.stringify(body) }});')
                else:
                    lines.append(f'    return this._request("POST", "{endpoint.path}");')
            else:
                lines.append(f'    return this._request("{endpoint.method.value}", "{endpoint.path}");')
            
            lines.append('  }')
            lines.append('')
        
        lines.append('}')
        lines.append('')
        lines.append('module.exports = { POUWChainClient };')
        
        return '\n'.join(lines)
    
    def generate_curl_examples(self) -> List[CodeExample]:
        """生成 cURL 示例"""
        examples = []
        
        for endpoint in self.api_doc.endpoints:
            cmd_parts = ['curl']
            
            if endpoint.method != HTTPMethod.GET:
                cmd_parts.append(f'-X {endpoint.method.value}')
            
            cmd_parts.append(f'"http://localhost:8545{endpoint.path}"')
            cmd_parts.append('-H "Content-Type: application/json"')
            
            if endpoint.auth_required:
                cmd_parts.append('-H "X-API-Key: YOUR_API_KEY"')
            
            body_params = [p for p in endpoint.parameters if p.location == ParameterLocation.BODY]
            if body_params and endpoint.method in [HTTPMethod.POST, HTTPMethod.PUT, HTTPMethod.PATCH]:
                body = {p.name: p.example or f"<{p.param_type}>" for p in body_params}
                cmd_parts.append(f"-d '{json.dumps(body)}'")
            
            code = ' \\\n  '.join(cmd_parts)
            
            examples.append(CodeExample(
                language="curl",
                title=endpoint.name or endpoint.path,
                description=endpoint.summary,
                code=code,
            ))
        
        return examples
    
    def _to_method_name(self, name: str) -> str:
        """转换为 Python 方法名"""
        name = name.replace('/', '_').replace('-', '_').strip('_')
        return name.lower()
    
    def _to_camel_case(self, name: str) -> str:
        """转换为驼峰命名"""
        parts = name.replace('/', '_').replace('-', '_').strip('_').split('_')
        return parts[0].lower() + ''.join(p.title() for p in parts[1:])
    
    def _py_type(self, param_type: str) -> str:
        """转换为 Python 类型"""
        type_map = {
            'string': 'str',
            'integer': 'int',
            'number': 'float',
            'boolean': 'bool',
            'array': 'List',
            'object': 'Dict',
        }
        return type_map.get(param_type, 'Any')


# ============== API 注册器 ==============

class APIRegistry:
    """API 注册器"""
    
    def __init__(self):
        self.endpoints: Dict[str, APIEndpoint] = {}
        self.handlers: Dict[str, Callable] = {}
        self.versions: Dict[APIVersion, List[str]] = {
            APIVersion.V1: [],
            APIVersion.V2: [],
        }
    
    def register(
        self,
        path: str,
        method: HTTPMethod = HTTPMethod.POST,
        name: str = "",
        summary: str = "",
        description: str = "",
        tags: List[str] = None,
        parameters: List[APIParameter] = None,
        auth_required: bool = True,
        version: APIVersion = APIVersion.V1,
    ):
        """注册端点装饰器"""
        def decorator(func: Callable):
            endpoint = APIEndpoint(
                path=path,
                method=method,
                name=name or func.__name__,
                summary=summary or func.__doc__ or "",
                description=description,
                tags=tags or [],
                parameters=parameters or [],
                auth_required=auth_required,
                handler=func,
                version=version,
            )
            
            key = f"{method.value}:{path}"
            self.endpoints[key] = endpoint
            self.handlers[key] = func
            self.versions[version].append(key)
            
            return func
        
        return decorator
    
    def get_endpoint(self, method: str, path: str) -> Optional[APIEndpoint]:
        """获取端点"""
        key = f"{method}:{path}"
        return self.endpoints.get(key)
    
    def get_handler(self, method: str, path: str) -> Optional[Callable]:
        """获取处理函数"""
        key = f"{method}:{path}"
        return self.handlers.get(key)
    
    def get_all_endpoints(self, version: APIVersion = None) -> List[APIEndpoint]:
        """获取所有端点"""
        if version:
            keys = self.versions.get(version, [])
            return [self.endpoints[k] for k in keys if k in self.endpoints]
        return list(self.endpoints.values())


# ============== SDK API 管理器 ==============

class SDKAPIManager:
    """SDK API 管理器"""
    
    def __init__(self):
        self.registry = APIRegistry()
        
        # API 文档
        self.api_doc = APIDoc(
            title="POUW Chain API",
            version="1.0.0",
            description="Proof of Useful Work 区块链 API",
            servers=[
                {"url": "http://localhost:8545", "description": "本地开发"},
                {"url": "https://api.pouwchain.io", "description": "生产环境"},
            ],
            tags=[
                {"name": "blockchain", "description": "区块链操作"},
                {"name": "compute", "description": "计算任务"},
                {"name": "wallet", "description": "钱包操作"},
                {"name": "mining", "description": "挖矿操作"},
            ],
        )
        
        # 代码示例缓存
        self.examples_cache: Dict[str, List[CodeExample]] = {}
        
        # SDK 生成器
        self.sdk_generator: Optional[SDKGenerator] = None
        
        # 初始化默认端点
        self._init_default_endpoints()
    
    def _init_default_endpoints(self):
        """初始化默认端点"""
        # 区块链端点
        self.register_endpoint(
            path="/api/v1/blocks/latest",
            method=HTTPMethod.GET,
            name="getLatestBlock",
            summary="获取最新区块",
            tags=["blockchain"],
            auth_required=False,
        )
        
        self.register_endpoint(
            path="/api/v1/blocks/{height}",
            method=HTTPMethod.GET,
            name="getBlockByHeight",
            summary="根据高度获取区块",
            parameters=[
                APIParameter(
                    name="height",
                    param_type="integer",
                    location=ParameterLocation.PATH,
                    required=True,
                    description="区块高度",
                ),
            ],
            tags=["blockchain"],
            auth_required=False,
        )
        
        # 计算任务端点
        self.register_endpoint(
            path="/api/v1/tasks",
            method=HTTPMethod.POST,
            name="createTask",
            summary="创建计算任务",
            parameters=[
                APIParameter(name="task_type", param_type="string", required=True, description="任务类型"),
                APIParameter(name="payload", param_type="object", required=True, description="任务数据"),
                APIParameter(name="reward", param_type="integer", required=True, description="奖励金额"),
            ],
            tags=["compute"],
        )
        
        # 钱包端点
        self.register_endpoint(
            path="/api/v1/wallet/balance",
            method=HTTPMethod.GET,
            name="getBalance",
            summary="获取钱包余额",
            parameters=[
                APIParameter(name="address", param_type="string", location=ParameterLocation.QUERY, required=True),
            ],
            tags=["wallet"],
        )
    
    def register_endpoint(
        self,
        path: str,
        method: HTTPMethod = HTTPMethod.POST,
        name: str = "",
        summary: str = "",
        description: str = "",
        tags: List[str] = None,
        parameters: List[APIParameter] = None,
        auth_required: bool = True,
        version: APIVersion = APIVersion.V1,
    ):
        """注册端点"""
        endpoint = APIEndpoint(
            path=path,
            method=method,
            name=name,
            summary=summary,
            description=description,
            tags=tags or [],
            parameters=parameters or [],
            auth_required=auth_required,
            version=version,
        )
        
        key = f"{method.value}:{path}"
        self.registry.endpoints[key] = endpoint
        self.api_doc.endpoints.append(endpoint)
    
    def get_openapi_spec(self) -> Dict:
        """获取 OpenAPI 规范"""
        return self.api_doc.to_openapi()
    
    def generate_sdk(self, language: str) -> str:
        """生成 SDK"""
        generator = SDKGenerator(self.api_doc)
        
        if language == "python":
            return generator.generate_python_sdk()
        elif language == "javascript":
            return generator.generate_javascript_sdk()
        else:
            raise ValueError(f"Unsupported language: {language}")
    
    def get_examples(self, endpoint_path: str = None) -> List[CodeExample]:
        """获取代码示例"""
        generator = SDKGenerator(self.api_doc)
        
        if endpoint_path:
            # 特定端点的示例
            endpoint = None
            for ep in self.api_doc.endpoints:
                if ep.path == endpoint_path:
                    endpoint = ep
                    break
            
            if not endpoint:
                return []
            
            # 生成特定端点的示例
            examples = []
            
            # Python 示例
            examples.append(CodeExample(
                language="python",
                title=f"Python - {endpoint.name}",
                code=self._generate_python_example(endpoint),
            ))
            
            # JavaScript 示例
            examples.append(CodeExample(
                language="javascript",
                title=f"JavaScript - {endpoint.name}",
                code=self._generate_js_example(endpoint),
            ))
            
            return examples
        
        # 所有 cURL 示例
        return generator.generate_curl_examples()
    
    def _generate_python_example(self, endpoint: APIEndpoint) -> str:
        """生成 Python 示例"""
        lines = [
            'from pouw_sdk import POUWChainClient',
            '',
            'client = POUWChainClient("http://localhost:8545", api_key="YOUR_API_KEY")',
            '',
        ]
        
        method_name = endpoint.name.replace('-', '_').lower()
        params = [f'{p.name}={repr(p.example or p.default or "<value>")}' for p in endpoint.parameters]
        
        lines.append(f'result = client.{method_name}({", ".join(params)})')
        lines.append('print(result)')
        
        return '\n'.join(lines)
    
    def _generate_js_example(self, endpoint: APIEndpoint) -> str:
        """生成 JavaScript 示例"""
        lines = [
            'const { POUWChainClient } = require("pouw-sdk");',
            '',
            'const client = new POUWChainClient("http://localhost:8545", "YOUR_API_KEY");',
            '',
            'async function main() {',
        ]
        
        method_name = endpoint.name[0].lower() + endpoint.name[1:]
        params = [f'{p.example or p.default or "<value>"}' for p in endpoint.parameters]
        
        lines.append(f'  const result = await client.{method_name}({", ".join(repr(p) for p in params)});')
        lines.append('  console.log(result);')
        lines.append('}')
        lines.append('')
        lines.append('main().catch(console.error);')
        
        return '\n'.join(lines)
    
    def get_api_docs_markdown(self) -> str:
        """生成 Markdown 格式的 API 文档"""
        lines = [
            f'# {self.api_doc.title}',
            '',
            f'版本: {self.api_doc.version}',
            '',
            self.api_doc.description,
            '',
            '## 认证',
            '',
            '大多数 API 需要通过 `X-API-Key` 请求头进行认证。',
            '',
            '## 端点',
            '',
        ]
        
        # 按标签分组
        by_tag: Dict[str, List[APIEndpoint]] = defaultdict(list)
        for endpoint in self.api_doc.endpoints:
            tag = endpoint.tags[0] if endpoint.tags else "other"
            by_tag[tag].append(endpoint)
        
        for tag, endpoints in by_tag.items():
            lines.append(f'### {tag.title()}')
            lines.append('')
            
            for endpoint in endpoints:
                lines.append(f'#### {endpoint.method.value} {endpoint.path}')
                lines.append('')
                lines.append(f'**{endpoint.summary}**')
                lines.append('')
                
                if endpoint.description:
                    lines.append(endpoint.description)
                    lines.append('')
                
                if endpoint.parameters:
                    lines.append('**参数:**')
                    lines.append('')
                    lines.append('| 名称 | 类型 | 位置 | 必需 | 描述 |')
                    lines.append('|------|------|------|------|------|')
                    for p in endpoint.parameters:
                        required = '是' if p.required else '否'
                        lines.append(f'| {p.name} | {p.param_type} | {p.location.value} | {required} | {p.description} |')
                    lines.append('')
                
                lines.append('---')
                lines.append('')
        
        return '\n'.join(lines)
    
    def get_endpoints_list(self) -> List[Dict]:
        """获取端点列表"""
        return [ep.to_dict() for ep in self.api_doc.endpoints]
    
    def get_supported_languages(self) -> List[str]:
        """获取支持的 SDK 语言"""
        return ["python", "javascript", "typescript", "go", "java", "rust"]


# ============== 全局实例 ==============

_sdk_api_manager: Optional[SDKAPIManager] = None


def get_sdk_api_manager() -> SDKAPIManager:
    """获取 SDK API 管理器单例"""
    global _sdk_api_manager
    if _sdk_api_manager is None:
        _sdk_api_manager = SDKAPIManager()
    return _sdk_api_manager
