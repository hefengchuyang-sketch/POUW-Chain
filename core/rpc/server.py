"""
RPC HTTP 服务器和客户端

从 rpc_service.py 拆分，包含：
- RPCHTTPHandler: HTTP 请求处理器
- RPCServer: HTTP 服务器（带安全加固）
- RPCClient: RPC 客户端
"""

import json
import os
import mimetypes
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional, Any

from .models import RPCErrorCode, RPCError, RPCRequest, RPCResponse


class RPCHTTPHandler(BaseHTTPRequestHandler):
    """HTTP RPC 请求处理器"""

    rpc_service = None
    static_dir: str = None
    rate_limiter = None
    api_auth = None
    cors_origins: list = None

    def log_message(self, format, *args):
        pass

    def _get_client_ip(self) -> str:
        """获取客户端真实 IP。
        Get client IP address.
        
        安全加固：不信任 X-Forwarded-For 头（防止 IP 伪造绕过 localhost 认证）。
        Security: Do NOT trust X-Forwarded-For header to prevent localhost auth bypass.
        Only use the actual TCP connection IP (self.client_address).
        If behind a trusted reverse proxy, configure TRUSTED_PROXY_IPS.
        """
        # 直接使用 TCP 连接的真实 IP，不信任代理头
        # Use actual TCP connection IP, never trust proxy headers
        return self.client_address[0] if self.client_address else '0.0.0.0'

    def _check_rate_limit(self) -> bool:
        if not self.rate_limiter:
            return True
        ip = self._get_client_ip()
        allowed, remaining = self.rate_limiter.is_allowed(ip)
        if not allowed:
            self.send_response(429)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Retry-After', '60')
            self.end_headers()
            err = json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32099, "message": "Rate limit exceeded"}})
            self.wfile.write(err.encode())
            return False
        return True

    def _get_cors_origin(self) -> str:
        origin = self.headers.get('Origin', '')
        if not self.cors_origins or '*' in self.cors_origins:
            return origin or '*'
        if origin in self.cors_origins:
            return origin
        if not origin:
            return ''
        return ''

    def do_GET(self):
        if not self.static_dir or not os.path.isdir(self.static_dir):
            self.send_error(404, "Frontend not deployed")
            return

        path = self.path.split('?')[0].split('#')[0]
        if path == '/':
            path = '/index.html'

        safe_path = os.path.normpath(path.lstrip('/'))
        if safe_path.startswith('..'):
            self.send_error(403, "Forbidden")
            return

        file_path = os.path.join(self.static_dir, safe_path)

        # SPA fallback: routes like /demo are frontend routes, not physical files.
        # If the requested path has no extension and does not exist, serve index.html.
        if not os.path.exists(file_path):
            _, ext = os.path.splitext(safe_path)
            if ext == '':
                file_path = os.path.join(self.static_dir, 'index.html')
        
        # 安全加固：防止 Windows 路径遍历攻击
        # Security: prevent path traversal on Windows via realpath check
        real_file = os.path.realpath(file_path)
        real_static = os.path.realpath(self.static_dir)
        try:
            common = os.path.commonpath([real_static, real_file])
        except ValueError:
            self.send_error(403, "Forbidden")
            return
        if common != real_static:
            self.send_error(403, "Forbidden")
            return

        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        try:
            file_size = os.path.getsize(file_path)
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(file_size))
            # Use configured CORS origin instead of hardcoded '*'
            cors_origin = self._get_cors_origin()
            if cors_origin:
                self.send_header('Access-Control-Allow-Origin', cors_origin)
            if '/assets/' in self.path:
                self.send_header('Cache-Control', 'public, max-age=31536000')
            else:
                self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception as e:
            import logging
            logging.getLogger('rpc').error(f"Static file error: {e}")
            self.send_error(500, "Internal server error")

    def _extract_auth_context(self) -> Dict:
        requested_user = (self.headers.get('X-Auth-User', '') or '').strip()
        import os
        allow_user_override = os.getenv('ALLOW_AUTH_USER_OVERRIDE', 'false').lower() == 'true'

        # 先尝试 API Key / Bearer Token 认证
        if self.api_auth:
            auth_context = self.api_auth.authenticate_request(self.headers)
            if auth_context.get('role') != 'guest':
                # 默认禁止请求头覆盖认证身份；开发演示可通过环境变量显式开启
                if requested_user and allow_user_override:
                    auth_context['user'] = requested_user
                    auth_context['user_address'] = requested_user
                return auth_context

        # Localhost 自动信任（可通过环境变量禁用以提升安全性）
        # Security: REQUIRE_LOCAL_AUTH=true 强制本地请求也需要 API Key
        require_local_auth = os.getenv('REQUIRE_LOCAL_AUTH', 'true').lower() == 'true'
        
        client_ip = self._get_client_ip()
        if client_ip in ('127.0.0.1', '::1', 'localhost') and not require_local_auth:
            # 开发/测试环境：本地请求自动信任
            # 生产环境：设置 REQUIRE_LOCAL_AUTH=true 禁用自动信任
            # 若携带 X-Auth-User，则按该用户身份执行（便于本地多角色演示）
            effective_user = requested_user if (requested_user and allow_user_override) else 'local_admin'
            return {
                'role': 'local',
                'user': effective_user,
                'user_address': effective_user,
                'is_admin': False if (requested_user and allow_user_override) else True,
                'is_local': True,
            }

        return {"role": "guest"}

    def _send_json(self, data: Dict, status: int = 200):
        try:
            json_str = json.dumps(data, ensure_ascii=False, default=str)
        except TypeError as e:
            import logging
            logging.getLogger('rpc').error(f"JSON serialization failed: {e}")
            data = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Serialization error"}}
            json_str = json.dumps(data, ensure_ascii=False)
            status = 500

        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        cors_origin = self._get_cors_origin()
        if cors_origin:
            self.send_header('Access-Control-Allow-Origin', cors_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Auth-User')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
        self.wfile.write(json_str.encode('utf-8'))

    def do_OPTIONS(self):
        if not self._check_rate_limit():
            return
        self.send_response(200)
        cors_origin = self._get_cors_origin()
        if cors_origin:
            self.send_header('Access-Control-Allow-Origin', cors_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Auth-User')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_POST(self):
        if not self._check_rate_limit():
            return
        try:
            content_length_raw = self.headers.get('Content-Length', '0')
            try:
                content_length = int(content_length_raw)
            except (ValueError, TypeError):
                self._send_json(
                    RPCResponse.make_error(-32600, "Invalid Content-Length").to_dict(), 400
                )
                return
            if content_length < 0:
                self._send_json(
                    RPCResponse.make_error(-32600, "Invalid Content-Length").to_dict(), 400
                )
                return
            if content_length > 1048576:
                self._send_json(
                    RPCResponse.make_error(-32099, "Request too large").to_dict(), 413
                )
                return
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            auth_context = self._extract_auth_context()
            request = RPCRequest.from_dict(data)

            from core.security import PUBLIC_RPC_METHODS, AUTHENTICATED_WRITE_METHODS
            role = auth_context.get('role', 'guest')
            is_local = auth_context.get('is_local', False)

            if request.method in AUTHENTICATED_WRITE_METHODS:
                # 写操作：API Key 认证 或 localhost 本地访问
                if role == 'guest':
                    self._send_json(
                        RPCResponse.make_error(-32003, "Authentication required: provide X-API-Key header or use localhost").to_dict(), 403
                    )
                    return
                # 非本地访问的写操作须有 user_address
                if not is_local and not auth_context.get('user_address'):
                    self._send_json(
                        RPCResponse.make_error(-32003, "Authentication incomplete: user address not identified").to_dict(), 403
                    )
                    return
            elif request.method not in PUBLIC_RPC_METHODS:
                # 未注册方法需 admin 或 localhost
                if role == 'guest':
                    self._send_json(
                        RPCResponse.make_error(-32003, "Authentication required").to_dict(), 403
                    )
                    return

            response = self.rpc_service.handle_request(request, auth_context)
            self._send_json(response.to_dict())
        except json.JSONDecodeError:
            self._send_json(
                RPCResponse.make_error(RPCErrorCode.PARSE_ERROR.value, "Invalid JSON").to_dict(),
                400
            )
        except Exception as e:
            import traceback
            import logging
            logging.getLogger('rpc').error(f"RPC error: {e}", exc_info=True)
            self._send_json(
                RPCResponse.make_error(RPCErrorCode.INTERNAL_ERROR.value, "Internal server error").to_dict(),
                500
            )


class RPCServer:
    """RPC HTTP 服务器（带安全加固）"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8545, static_dir: str = None,
                 ssl_cert: str = None, ssl_key: str = None, admin_key: str = "",
                 cors_origins: list = None, rate_limit: int = 200):
        self.host = host
        self.port = port
        self.static_dir = static_dir
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.server = None
        self._thread = None

        # 延迟导入 NodeRPCService 避免循环
        from core.rpc_service import NodeRPCService
        self.rpc_service = NodeRPCService()

        # 初始化安全组件
        from core.security import APIKeyAuth, RateLimiter
        self.api_auth = APIKeyAuth(admin_key)
        self.rate_limiter = RateLimiter(max_requests=rate_limit, window_seconds=60)
        self.cors_origins = cors_origins or []

    def start(self):
        """启动服务器"""
        RPCHTTPHandler.rpc_service = self.rpc_service
        RPCHTTPHandler.static_dir = self.static_dir
        RPCHTTPHandler.rate_limiter = self.rate_limiter
        RPCHTTPHandler.api_auth = self.api_auth
        RPCHTTPHandler.cors_origins = self.cors_origins

        self.server = HTTPServer((self.host, self.port), RPCHTTPHandler)

        protocol = "http"
        if self.ssl_cert and self.ssl_key:
            try:
                from core.security import create_ssl_context
                ssl_ctx = create_ssl_context(self.ssl_cert, self.ssl_key, server=True)
                if ssl_ctx:
                    self.server.socket = ssl_ctx.wrap_socket(self.server.socket, server_side=True)
                    protocol = "https"
            except Exception as e:
                print(f"[WARN] HTTPS setup failed, using HTTP: {e}")

        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

        frontend_msg = f" (Frontend: {self.static_dir})" if self.static_dir else ""
        admin_msg = ""
        if self.api_auth and self.api_auth.auto_generated:
            key = self.api_auth.admin_key
            masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "(hidden)"
            admin_msg = (
                "\n  Admin API Key auto-generated (masked in logs): "
                f"{masked}. Set POUW_ADMIN_KEY to pin a fixed key."
            )
        print(f"RPC Server started at {protocol}://{self.host}:{self.port}{frontend_msg}{admin_msg}")

    def stop(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            self.server = None


class RPCClient:
    """RPC 客户端"""

    def __init__(self, endpoint: str = "http://127.0.0.1:8545"):
        self.endpoint = endpoint
        self._request_id = 0
        self._ssl_context = self._build_ssl_context()

    @staticmethod
    def _build_ssl_context():
        """构建 SSL 上下文，支持 MAINCOIN_CA_CERT 证书验证。"""
        import ssl
        import os
        ca_path = os.environ.get("MAINCOIN_CA_CERT", "")
        if ca_path and os.path.exists(ca_path):
            ctx = ssl.create_default_context(cafile=ca_path)
            return ctx
        return None  # 使用系统默认

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def call(self, method: str, params: Dict = None) -> Any:
        import urllib.request

        request = RPCRequest(
            method=method,
            params=params or {},
            id=self._next_id()
        )

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(request.to_dict()).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req, timeout=30, context=self._ssl_context) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if 'error' in data and data['error']:
                    raise RPCError(data['error']['code'], data['error']['message'])
                return data.get('result')
        except urllib.error.HTTPError as e:
            error_data = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_data)
                if 'error' in error_json:
                    raise RPCError(error_json['error']['code'], error_json['error']['message'])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
            raise RPCError(RPCErrorCode.INTERNAL_ERROR.value, "RPC request failed")
        except Exception as e:
            if isinstance(e, RPCError):
                raise
            raise RPCError(RPCErrorCode.INTERNAL_ERROR.value, "RPC request failed")

    def is_connected(self) -> bool:
        try:
            self.call('node_getInfo', {})
            return True
        except Exception:
            return False

    def get_node_info(self) -> Dict:
        return self.call('node_getInfo', {})

    def get_balance(self, address: str, sector: str = None) -> Dict:
        params = {'address': address}
        if sector:
            params['sector'] = sector
        return self.call('account_getBalance', params)

    def send_transaction(self, tx_data: Dict) -> Dict:
        return self.call('tx_send', {'transaction': tx_data})

    def get_transaction(self, txid: str) -> Optional[Dict]:
        return self.call('tx_get', {'txid': txid})

    def get_chain_info(self, sector: str = None) -> Dict:
        params = {}
        if sector:
            params['sector'] = sector
        return self.call('chain_getInfo', params)

    def list_methods(self) -> List[Dict]:
        return self.call('rpc_listMethods', {})
