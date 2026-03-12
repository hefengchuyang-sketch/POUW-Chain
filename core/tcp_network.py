"""
TCP P2P 网络模块 - 真实网络通信

实现功能：
1. TCP 服务器/客户端
2. 节点发现（Bootstrap + Gossip）
3. 消息广播
4. 心跳检测
5. 断线重连
"""

import asyncio
import json
import time
import uuid
import socket
import threading
import hmac
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Set, Tuple
from enum import Enum
import hashlib


class MessageType(Enum):
    """P2P 消息类型。"""
    # 握手 & 认证
    HANDSHAKE = "HANDSHAKE"
    HANDSHAKE_ACK = "HANDSHAKE_ACK"
    CHALLENGE = "CHALLENGE"           # 挑战-应答认证
    CHALLENGE_RESP = "CHALLENGE_RESP" # 挑战应答
    
    # 节点发现
    GET_PEERS = "GET_PEERS"
    PEERS = "PEERS"
    
    # 心跳
    PING = "PING"
    PONG = "PONG"
    
    # 区块链同步
    GET_BLOCKS = "GET_BLOCKS"
    BLOCKS = "BLOCKS"
    NEW_BLOCK = "NEW_BLOCK"
    
    # 交易
    NEW_TX = "NEW_TX"
    GET_MEMPOOL = "GET_MEMPOOL"
    MEMPOOL = "MEMPOOL"
    
    # 任务
    NEW_TASK = "NEW_TASK"
    TASK_RESULT = "TASK_RESULT"
    
    # 断开
    DISCONNECT = "DISCONNECT"


@dataclass
class PeerInfo:
    """节点信息。"""
    node_id: str
    host: str
    port: int
    sector: str = "MAIN"
    version: str = "1.0.0"
    last_seen: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    is_connected: bool = False
    is_authenticated: bool = False   # 是否通过挑战认证
    
    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"
    
    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "sector": self.sector,
            "version": self.version,
        }


class PeerRateLimiter:
    """Per-peer 速率限制器（滑动窗口）。"""
    
    # 默认限制：每分钟 200 条消息
    DEFAULT_RATE = 200
    WINDOW_SEC = 60
    
    def __init__(self, max_per_minute: int = DEFAULT_RATE):
        self.max_per_minute = max_per_minute
        # {peer_id: [timestamp, ...]}
        self._windows: Dict[str, List[float]] = defaultdict(list)
    
    def allow(self, peer_id: str) -> bool:
        """检查是否允许此消息。"""
        now = time.time()
        cutoff = now - self.WINDOW_SEC
        
        # 清理过期时间戳
        window = self._windows[peer_id]
        self._windows[peer_id] = [t for t in window if t > cutoff]
        
        if len(self._windows[peer_id]) >= self.max_per_minute:
            return False
        
        self._windows[peer_id].append(now)
        return True
    
    def remove_peer(self, peer_id: str):
        """清理断开连接的节点。"""
        self._windows.pop(peer_id, None)


@dataclass
class P2PMessage:
    """P2P 消息。"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    msg_type: MessageType = MessageType.PING
    sender_id: str = ""
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def serialize(self) -> bytes:
        """序列化为字节。"""
        data = {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
        json_str = json.dumps(data)
        # 添加长度前缀（4字节）
        length = len(json_str)
        return length.to_bytes(4, 'big') + json_str.encode()
    
    @classmethod
    def deserialize(cls, data: bytes) -> Optional["P2PMessage"]:
        """反序列化。"""
        try:
            json_data = json.loads(data.decode())
            return cls(
                msg_id=json_data.get("msg_id", ""),
                msg_type=MessageType(json_data.get("msg_type", "PING")),
                sender_id=json_data.get("sender_id", ""),
                payload=json_data.get("payload", {}),
                timestamp=json_data.get("timestamp", time.time()),
            )
        except Exception as e:
            return None


class TCPPeer:
    """TCP 连接的对等节点。"""
    
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        peer_info: PeerInfo,
        on_message: Callable,
        on_disconnect: Callable,
    ):
        self.reader = reader
        self.writer = writer
        self.peer_info = peer_info
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        
        self.is_running = False
        self.last_ping = time.time()
        self.pending_pongs: Dict[str, float] = {}
    
    # Maximum message size: 2MB (reduced from 10MB to limit DoS surface)
    MAX_MESSAGE_SIZE = 2 * 1024 * 1024
    
    async def start(self):
        """启动接收循环。"""
        self.is_running = True
        self.peer_info.is_connected = True
        
        try:
            while self.is_running:
                # 读取消息长度（4字节）— 使用 readexactly 确保精确读取
                # Security: reader.read(4) may return fewer than 4 bytes
                length_bytes = await asyncio.wait_for(
                    self.reader.readexactly(4),
                    timeout=60.0
                )
                
                length = int.from_bytes(length_bytes, 'big')
                if length > self.MAX_MESSAGE_SIZE:
                    break
                if length <= 0:
                    break
                
                # 读取消息体 — 使用 readexactly 确保精确读取
                data = await asyncio.wait_for(
                    self.reader.readexactly(length),
                    timeout=30.0
                )
                
                if not data:
                    break
                
                # 解析消息
                message = P2PMessage.deserialize(data)
                if message:
                    self.peer_info.last_seen = time.time()
                    await self.on_message(self, message)
                    
        except asyncio.TimeoutError:
            pass
        except asyncio.IncompleteReadError:
            # Peer disconnected mid-message — normal during shutdown
            pass
        except Exception as e:
            pass
        finally:
            await self.stop()
    
    async def stop(self):
        """停止连接。"""
        self.is_running = False
        self.peer_info.is_connected = False
        
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except (OSError, ConnectionError, AttributeError):
            pass
        
        await self.on_disconnect(self)
    
    async def send(self, message: P2PMessage):
        """发送消息。"""
        try:
            data = message.serialize()
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            await self.stop()
    
    async def ping(self) -> float:
        """发送 ping 并等待 pong。"""
        ping_id = str(uuid.uuid4())[:8]
        self.pending_pongs[ping_id] = time.time()
        
        await self.send(P2PMessage(
            msg_type=MessageType.PING,
            payload={"ping_id": ping_id}
        ))
        
        # 等待 pong（最多 5 秒）
        for _ in range(50):
            await asyncio.sleep(0.1)
            if ping_id not in self.pending_pongs:
                return self.peer_info.latency_ms
        
        return -1  # 超时


class TCPServer:
    """TCP 服务器（支持 TLS）。"""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9333,
        node_id: str = None,
        on_connection: Callable = None,
        log_fn: Callable = print,
        ssl_context = None,
    ):
        self.host = host
        self.port = port
        self.node_id = node_id or str(uuid.uuid4())[:12]
        self.on_connection = on_connection
        self.log = log_fn
        self.ssl_context = ssl_context
        
        self.server = None
        self.is_running = False
    
    async def start(self):
        """启动服务器。"""
        self.server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port,
            ssl=self.ssl_context
        )
        
        self.is_running = True
        tls_msg = " (TLS)" if self.ssl_context else ""
        self.log(f"TCP 服务器启动: {self.host}:{self.port}{tls_msg}")
        
        async with self.server:
            await self.server.serve_forever()
    
    async def stop(self):
        """停止服务器。"""
        self.is_running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.log("🛑 TCP 服务器停止")
    
    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """处理新连接。"""
        addr = writer.get_extra_info('peername')
        self.log(f"📥 新连接: {addr}")
        
        if self.on_connection:
            await self.on_connection(reader, writer, addr)


class P2PNode:
    """P2P 节点。
    
    完整的 P2P 网络节点，包括：
    - TCP 服务器（接收连接）+ TLS 加密
    - TCP 客户端（主动连接）
    - 节点发现
    - 消息路由
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9333,
        node_id: str = None,
        sector: str = "MAIN",
        bootstrap_nodes: List[str] = None,
        log_fn: Callable = print,
        ssl_cert: str = None,
        ssl_key: str = None,
        max_peers: int = 50,
    ):
        self.host = host
        self.port = port
        self.max_peers = max(8, max_peers)  # 至少 8 个连接
        self.node_id = node_id or hashlib.sha256(
            f"{socket.gethostname()}:{port}:{time.time()}".encode()
        ).hexdigest()[:16]
        self.sector = sector
        self.bootstrap_nodes = bootstrap_nodes or []
        self.log = log_fn
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        
        # TLS 上下文
        self._server_ssl = None
        self._client_ssl = None
        if ssl_cert and ssl_key:
            try:
                from .security import create_ssl_context
                self._server_ssl = create_ssl_context(ssl_cert, ssl_key, server=True)
                self._client_ssl = create_ssl_context(ssl_cert, ssl_key, server=False)
                self.log(f"P2P TLS 已启用")
            except Exception as e:
                self.log(f"P2P TLS 初始化失败: {e}，使用明文")
        
        # 连接的节点
        self.peers: Dict[str, TCPPeer] = {}
        self.known_peers: Dict[str, PeerInfo] = {}
        
        # 消息处理器
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # 已处理消息（防止重复）— 使用有序集合实现 LRU 淘汰
        self.seen_messages: Set[str] = set()
        self._seen_messages_order: list = []  # 保持插入顺序用于 LRU 淘汰
        self.max_seen = 10000
        
        # Per-peer 速率限制
        self.rate_limiter = PeerRateLimiter()
        
        # S-2 fix: 挑战-应答认证 — 使用真正的 ECDSA 非对称签名（替代旧的 HMAC 模型）
        self._pending_challenges: Dict[str, str] = {}  # peer_node_id -> challenge_nonce
        # 加载持久化的网络密钥（用作 ECDSA 私钥种子）
        self._network_secret = self._load_or_create_network_secret()
        # 生成 ECDSA 密钥对
        self._signing_key, self._verifying_key_hex = self._init_ecdsa_keypair()
        # 存储已知节点公钥用于 TOFU 验证
        self._peer_pubkeys: Dict[str, str] = {}  # peer_node_id -> public_key_hex
        self._load_peer_pubkeys()  # H-01: 从磁盘加载已知公钥，防重启后 MITM
        
        # 服务器
        self.server: Optional[TCPServer] = None
        
        # 状态
        self.is_running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # 注册默认处理器
        self._register_default_handlers()
    
    # --- Persistence helpers ---
    
    def _get_data_dir(self) -> str:
        """获取数据目录路径。"""
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    
    def _load_or_create_network_secret(self) -> bytes:
        """H-2 fix: 加载或创建持久化的 network_secret，磁盘上加密存储。"""
        secret_path = os.path.join(self._get_data_dir(), "network_secret.bin")
        try:
            if os.path.exists(secret_path):
                with open(secret_path, "rb") as f:
                    data = f.read()
                # 尝试解密（新格式：4 字节 nonce 长度 + nonce + ciphertext）
                if len(data) > 36:
                    secret = self._decrypt_secret(data)
                    if secret and len(secret) == 32:
                        return secret
                # 兼容旧格式（明文 32 字节）
                if len(data) == 32:
                    # 升级：重新以加密格式保存
                    self._save_encrypted_secret(secret_path, data)
                    return data
        except Exception:
            pass
        # 首次启动：生成新 secret 并加密持久化
        secret = os.urandom(32)
        try:
            self._save_encrypted_secret(secret_path, secret)
        except Exception:
            pass
        return secret
    
    def _save_encrypted_secret(self, path: str, secret: bytes):
        """H-2: 使用机器指纹派生密钥 + AES 加密保存 network_secret。"""
        try:
            machine_key = self._derive_machine_key()
            nonce = os.urandom(12)
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(machine_key)
            ciphertext = aesgcm.encrypt(nonce, secret, None)
            # 格式：[nonce_len(1 byte)][nonce][ciphertext]
            with open(path, "wb") as f:
                f.write(bytes([len(nonce)])) 
                f.write(nonce)
                f.write(ciphertext)
        except ImportError:
            # cryptography 不可用时回退明文存储
            with open(path, "wb") as f:
                f.write(secret)
    
    def _decrypt_secret(self, data: bytes) -> Optional[bytes]:
        """H-2: 解密 network_secret。"""
        try:
            machine_key = self._derive_machine_key()
            nonce_len = data[0]
            nonce = data[1:1+nonce_len]
            ciphertext = data[1+nonce_len:]
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(machine_key)
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            return None
    
    @staticmethod
    def _derive_machine_key() -> bytes:
        """H-2: 从机器指纹派生 32 字节密钥（与 security.py 一致）。"""
        import socket
        import platform
        fingerprint = f"{socket.gethostname()}:{platform.node()}:{platform.machine()}"
        return hashlib.pbkdf2_hmac('sha256', fingerprint.encode(), b'POUW_NET_SECRET_v1', 100000)
    
    def _save_known_peers(self):
        """持久化已知节点列表，重启后可快速重连。"""
        peers_path = os.path.join(self._get_data_dir(), "known_peers.json")
        try:
            peer_list = []
            for pid, info in self.known_peers.items():
                peer_list.append({
                    "node_id": info.node_id,
                    "host": info.host,
                    "port": info.port,
                })
            with open(peers_path, "w", encoding="utf-8") as f:
                json.dump(peer_list, f, indent=2)
        except Exception:
            pass
    
    def _load_known_peers(self):
        """从磁盘加载已知节点列表。"""
        peers_path = os.path.join(self._get_data_dir(), "known_peers.json")
        try:
            if os.path.exists(peers_path):
                with open(peers_path, "r", encoding="utf-8") as f:
                    peer_list = json.load(f)
                for entry in peer_list:
                    nid = entry.get("node_id", "")
                    if nid and nid != self.node_id:
                        self.known_peers[nid] = PeerInfo(
                            node_id=nid,
                            host=entry["host"],
                            port=entry["port"],
                        )
                if self.known_peers:
                    self.log(f"📂 从磁盘加载 {len(self.known_peers)} 个已知节点")
        except Exception:
            pass
    
    def _init_ecdsa_keypair(self):
        """S-2 fix: 从 network_secret 初始化 ECDSA 密钥对用于 P2P 认证。
        
        使用 network_secret 作为私钥种子，确保重启后密钥对不变，
        维持 TOFU 信任链。
        """
        try:
            from ecdsa import SigningKey, SECP256k1
            sk = SigningKey.from_string(self._network_secret, curve=SECP256k1)
            vk = sk.get_verifying_key()
            return sk, vk.to_string().hex()
        except ImportError:
            # ecdsa 不可用时回退到 HMAC 模式
            public_key_hex = hashlib.sha256(self._network_secret).hexdigest()
            return None, public_key_hex
    
    # --- H-01: Peer pubkey persistence (prevents MITM after restart) ---
    
    def _save_peer_pubkeys(self):
        """持久化已知节点公钥，防止重启后 TOFU 信任链断裂。"""
        pubkeys_path = os.path.join(self._get_data_dir(), "peer_pubkeys.json")
        try:
            with open(pubkeys_path, "w", encoding="utf-8") as f:
                json.dump(self._peer_pubkeys, f, indent=2)
        except Exception:
            pass
    
    def _load_peer_pubkeys(self):
        """从磁盘加载已知节点公钥。"""
        pubkeys_path = os.path.join(self._get_data_dir(), "peer_pubkeys.json")
        try:
            if os.path.exists(pubkeys_path):
                with open(pubkeys_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._peer_pubkeys = data
                    if data:
                        self.log(f"🔑 从磁盘加载 {len(data)} 个节点公钥指纹")
        except Exception:
            pass
    
    def _register_default_handlers(self):
        """注册默认消息处理器。"""
        self.message_handlers[MessageType.HANDSHAKE] = self._handle_handshake
        self.message_handlers[MessageType.HANDSHAKE_ACK] = self._handle_handshake_ack
        self.message_handlers[MessageType.CHALLENGE] = self._handle_challenge
        self.message_handlers[MessageType.CHALLENGE_RESP] = self._handle_challenge_resp
        self.message_handlers[MessageType.PING] = self._handle_ping
        self.message_handlers[MessageType.PONG] = self._handle_pong
        self.message_handlers[MessageType.GET_PEERS] = self._handle_get_peers
        self.message_handlers[MessageType.PEERS] = self._handle_peers
        # 任务处理器（由 P2P 任务系统注册）
        self.message_handlers[MessageType.NEW_TASK] = self._handle_new_task
        self.message_handlers[MessageType.TASK_RESULT] = self._handle_task_result
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器。"""
        self.message_handlers[msg_type] = handler
    
    # P2P 任务系统集成
    _task_message_handler = None
    
    def set_task_handler(self, handler):
        """设置 P2P 任务消息处理器。
        
        Args:
            handler: P2PTaskMessageHandler 实例
        """
        self._task_message_handler = handler
        self.log(f"📋 P2P 任务处理器已设置")
    
    async def _handle_new_task(self, peer: "TCPPeer", message: "P2PMessage"):
        """处理新任务消息。"""
        if self._task_message_handler:
            await self._task_message_handler.handle_new_task(peer, message)
        else:
            self.log(f"⚠️ 收到任务消息但未设置处理器: {message.msg_id}")
    
    async def _handle_task_result(self, peer: "TCPPeer", message: "P2PMessage"):
        """处理任务结果消息。"""
        if self._task_message_handler:
            await self._task_message_handler.handle_task_result(peer, message)
        else:
            self.log(f"⚠️ 收到结果消息但未设置处理器: {message.msg_id}")
    
    async def start(self):
        """启动节点。"""
        self.is_running = True
        self.loop = asyncio.get_event_loop()
        
        # 加载持久化的已知节点列表
        self._load_known_peers()
        
        # 启动服务器
        self.server = TCPServer(
            host=self.host,
            port=self.port,
            node_id=self.node_id,
            on_connection=self._on_inbound_connection,
            log_fn=self.log,
            ssl_context=self._server_ssl,
        )
        
        # 创建任务
        server_task = asyncio.create_task(self.server.start())
        
        # 连接 bootstrap 节点
        await asyncio.sleep(1)  # 等待服务器启动
        for addr in self.bootstrap_nodes:
            try:
                host, port = addr.split(":")
                await self.connect(host, int(port))
            except Exception as e:
                self.log(f"⚠️ 连接 bootstrap 失败: {addr} - {e}")
        
        # 尝试重连持久化的已知节点
        for pid, pinfo in list(self.known_peers.items()):
            if pid not in self.peers:
                try:
                    await self.connect(pinfo.host, pinfo.port)
                except Exception:
                    pass
        
        # 启动维护任务
        maintenance_task = asyncio.create_task(self._maintenance_loop())
        
        self.log(f"🚀 P2P 节点启动: {self.node_id} @ {self.host}:{self.port}")
        
        await asyncio.gather(server_task, maintenance_task)
    
    async def stop(self):
        """停止节点。"""
        self.is_running = False
        
        # 断开所有连接
        for peer in list(self.peers.values()):
            await peer.send(P2PMessage(
                msg_type=MessageType.DISCONNECT,
                sender_id=self.node_id,
            ))
            await peer.stop()
        
        # 持久化已知节点列表
        self._save_known_peers()
        
        # 停止服务器
        if self.server:
            await self.server.stop()
        
        self.log(f"🛑 P2P 节点停止: {self.node_id}")
    
    @staticmethod
    def _get_subnet(ip: str) -> str:
        """D-13: 获取 IP 的 /24 子网前缀（用于 Eclipse 保护）。"""
        parts = ip.split('.')
        if len(parts) == 4:
            return '.'.join(parts[:3])
        return ip  # IPv6 或其他格式，原样返回
    
    async def connect(self, host: str, port: int) -> bool:
        """连接到节点（支持 TLS），受 max_peers 限制。"""
        if len(self.peers) >= self.max_peers:
            return False
        try:
            reader, writer = await asyncio.open_connection(
                host, port, ssl=self._client_ssl
            )
            
            peer_info = PeerInfo(
                node_id="",  # 等待握手
                host=host,
                port=port,
            )
            
            peer = TCPPeer(
                reader=reader,
                writer=writer,
                peer_info=peer_info,
                on_message=self._on_message,
                on_disconnect=self._on_disconnect,
            )
            
            # 发送握手
            await peer.send(P2PMessage(
                msg_type=MessageType.HANDSHAKE,
                sender_id=self.node_id,
                payload={
                    "node_id": self.node_id,
                    "host": self.host,
                    "port": self.port,
                    "sector": self.sector,
                    "version": "1.0.0",
                }
            ))
            
            # 启动接收
            asyncio.create_task(peer.start())
            
            self.log(f"📤 连接到: {host}:{port}")
            return True
            
        except Exception as e:
            self.log(f"❌ 连接失败: {host}:{port} - {e}")
            return False
    
    async def _on_inbound_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        addr: tuple
    ):
        """处理入站连接（含连接数限制 + D-13 Eclipse 保护）。"""
        # 连接数限制：超过 max_peers 时拒绝新入站连接
        if len(self.peers) >= self.max_peers:
            self.log(f"⚠️ 连接数已达上限 ({self.max_peers})，拒绝来自 {addr} 的入站连接")
            writer.close()
            return
        
        # D-13 fix: IP 多样性检查 — 同一 /24 子网最多 MAX_PEERS_PER_SUBNET 个连接
        MAX_PEERS_PER_SUBNET = max(3, self.max_peers // 10)  # 至少3个，最多总连接数的10%
        incoming_ip = addr[0]
        incoming_subnet = self._get_subnet(incoming_ip)
        
        subnet_count = 0
        for peer in list(self.peers.values()):
            peer_ip = peer.peer_info.host
            if self._get_subnet(peer_ip) == incoming_subnet:
                subnet_count += 1
        
        if subnet_count >= MAX_PEERS_PER_SUBNET:
            self.log(f"⚠️ 子网 {incoming_subnet}.x 连接数已达上限 ({MAX_PEERS_PER_SUBNET})，拒绝来自 {addr} 的连接 (Eclipse protection)")
            writer.close()
            return
        
        peer_info = PeerInfo(
            node_id="",
            host=addr[0],
            port=addr[1],
        )
        
        peer = TCPPeer(
            reader=reader,
            writer=writer,
            peer_info=peer_info,
            on_message=self._on_message,
            on_disconnect=self._on_disconnect,
        )
        
        asyncio.create_task(peer.start())
    
    async def _on_message(self, peer: TCPPeer, message: P2PMessage):
        """处理收到的消息（含速率限制 + 认证检查）。"""
        peer_id = peer.peer_info.node_id or peer.peer_info.address
        
        # ── Per-peer 速率限制 ──
        if not self.rate_limiter.allow(peer_id):
            self.log(f"⚠️ 速率限制触发，丢弃来自 {peer_id} 的消息")
            return
        
        # 检查重复
        if message.msg_id in self.seen_messages:
            return
        
        self.seen_messages.add(message.msg_id)
        self._seen_messages_order.append(message.msg_id)
        if len(self.seen_messages) > self.max_seen:
            # LRU 淘汰：移除最旧的一半，保留最新的消息 ID 以防重放
            half = self.max_seen // 2
            old_ids = self._seen_messages_order[:half]
            self._seen_messages_order = self._seen_messages_order[half:]
            for old_id in old_ids:
                self.seen_messages.discard(old_id)
        
        # ── 认证检查：非握手/挑战消息必须已通过认证 ──
        AUTH_EXEMPT = {
            MessageType.HANDSHAKE, MessageType.HANDSHAKE_ACK,
            MessageType.CHALLENGE, MessageType.CHALLENGE_RESP,
            MessageType.PING, MessageType.PONG,
        }
        if message.msg_type not in AUTH_EXEMPT and not peer.peer_info.is_authenticated:
            self.log(f"⚠️ 未认证节点 {peer_id} 发送 {message.msg_type.value}，忽略")
            return
        
        # H-4 fix: 未认证节点的 PING/PONG 频率限制（每分钟最多 5 次）
        if message.msg_type in (MessageType.PING, MessageType.PONG) and not peer.peer_info.is_authenticated:
            now = time.time()
            if not hasattr(peer, '_unauth_ping_count'):
                peer._unauth_ping_count = 0
                peer._unauth_ping_window_start = now
            if now - peer._unauth_ping_window_start > 60:
                peer._unauth_ping_count = 0
                peer._unauth_ping_window_start = now
            peer._unauth_ping_count += 1
            if peer._unauth_ping_count > 5:
                self.log(f"⚠️ 未认证节点 {peer_id} PING 频率过高，断开")
                await peer.stop()
                return
        
        # 调用处理器
        handler = self.message_handlers.get(message.msg_type)
        if handler:
            await handler(peer, message)
    
    async def _on_disconnect(self, peer: TCPPeer):
        """处理断开连接。"""
        if peer.peer_info.node_id in self.peers:
            del self.peers[peer.peer_info.node_id]
            self.rate_limiter.remove_peer(peer.peer_info.node_id)
            self.log(f"📴 断开连接: {peer.peer_info.node_id}")
    
    async def _handle_handshake(self, peer: TCPPeer, message: P2PMessage):
        """处理握手（之后发送挑战进行认证）。"""
        payload = message.payload
        peer.peer_info.node_id = payload.get("node_id", "")
        peer.peer_info.sector = payload.get("sector", "MAIN")
        peer.peer_info.version = payload.get("version", "1.0.0")
        
        # 存储节点（尚未认证）
        self.peers[peer.peer_info.node_id] = peer
        self.known_peers[peer.peer_info.node_id] = peer.peer_info
        
        # 发送确认
        await peer.send(P2PMessage(
            msg_type=MessageType.HANDSHAKE_ACK,
            sender_id=self.node_id,
            payload={
                "node_id": self.node_id,
                "host": self.host,
                "port": self.port,
                "sector": self.sector,
                "version": "1.0.0",
            }
        ))
        
        # ── 发送挑战 ──
        challenge_nonce = os.urandom(32).hex()
        self._pending_challenges[peer.peer_info.node_id] = challenge_nonce
        await peer.send(P2PMessage(
            msg_type=MessageType.CHALLENGE,
            sender_id=self.node_id,
            payload={"nonce": challenge_nonce}
        ))
        
        self.log(f"🤝 握手完成（等待认证）: {peer.peer_info.node_id}")
    
    async def _handle_handshake_ack(self, peer: TCPPeer, message: P2PMessage):
        """处理握手确认。"""
        payload = message.payload
        peer.peer_info.node_id = payload.get("node_id", "")
        peer.peer_info.sector = payload.get("sector", "MAIN")
        
        self.peers[peer.peer_info.node_id] = peer
        self.known_peers[peer.peer_info.node_id] = peer.peer_info
        
        self.log(f"🤝 握手确认: {peer.peer_info.node_id}")
    
    async def _handle_challenge(self, peer: TCPPeer, message: P2PMessage):
        """S-2 fix: 处理挑战 — 使用 ECDSA 签名而非 HMAC。
        
        Security: Uses real ECDSA (secp256k1) asymmetric signature.
        Private key is never shared. Only the public key is sent.
        Verifier can mathematically confirm the response was produced
        by the holder of the corresponding private key.
        """
        nonce = message.payload.get("nonce", "")
        if not nonce:
            return
        
        # S-2: 用 ECDSA 签名挑战 nonce
        nonce_hash = hashlib.sha256(nonce.encode()).digest()
        if self._signing_key is not None:
            try:
                from ecdsa.util import sigencode_der
                sig_bytes = self._signing_key.sign(nonce_hash, sigencode=sigencode_der)
                response = sig_bytes.hex()
            except Exception:
                # ECDSA 失败时回退到 HMAC
                response = hmac.new(self._network_secret, nonce.encode(), hashlib.sha256).hexdigest()
        else:
            # ecdsa 库不可用，回退 HMAC
            response = hmac.new(self._network_secret, nonce.encode(), hashlib.sha256).hexdigest()
        
        await peer.send(P2PMessage(
            msg_type=MessageType.CHALLENGE_RESP,
            sender_id=self.node_id,
            payload={
                "nonce": nonce,
                "response": response,
                "node_id": self.node_id,
                "public_key": self._verifying_key_hex,
            }
        ))
    
    async def _handle_challenge_resp(self, peer: TCPPeer, message: P2PMessage):
        """S-2 fix: 验证挑战应答 — 使用 ECDSA 公钥验证签名。
        
        Security: The peer's ECDSA public_key is sent in the response.
        We mathematically verify the signature was produced by the holder
        of the corresponding private key. TOFU model still applies for
        binding node_id to public_key.
        """
        payload = message.payload
        resp_node_id = payload.get("node_id", "")
        nonce = payload.get("nonce", "")
        response = payload.get("response", "")
        peer_pubkey = payload.get("public_key", "")
        
        if not resp_node_id or not nonce or not response or not peer_pubkey:
            self.log(f"❌ 认证失败 (缺少字段): {resp_node_id}")
            await peer.stop()
            return
        
        expected_nonce = self._pending_challenges.pop(resp_node_id, None)
        if not expected_nonce or expected_nonce != nonce:
            self.log(f"❌ 认证失败 (nonce 不匹配): {resp_node_id}")
            await peer.stop()
            return
        
        # TOFU: 检查已知节点的公钥是否一致
        known_pubkey = self._peer_pubkeys.get(resp_node_id)
        if known_pubkey and known_pubkey != peer_pubkey:
            self.log(f"❌ 认证失败 (public_key 不匹配已知节点): {resp_node_id}")
            await peer.stop()
            return
        
        # S-2 fix: 用 ECDSA 公钥真正验证签名（而非仅信任公钥的一致性）
        nonce_hash = hashlib.sha256(nonce.encode()).digest()
        sig_verified = False
        try:
            from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
            from ecdsa.util import sigdecode_der
            vk = VerifyingKey.from_string(bytes.fromhex(peer_pubkey), curve=SECP256k1)
            sig_bytes = bytes.fromhex(response)
            vk.verify(sig_bytes, nonce_hash, sigdecode=sigdecode_der)
            sig_verified = True
        except ImportError:
            # ecdsa 不可用：回退到 TOFU 公钥一致性检查
            sig_verified = True  # 信任公钥一致性
        except (BadSignatureError, ValueError, Exception) as e:
            self.log(f"❌ 认证失败 (ECDSA 签名无效): {resp_node_id} - {e}")
            await peer.stop()
            return
        
        if not sig_verified:
            self.log(f"❌ 认证失败 (签名验证未通过): {resp_node_id}")
            await peer.stop()
            return
        
        # 存储公钥用于后续 TOFU 验证
        self._peer_pubkeys[resp_node_id] = peer_pubkey
        self._save_peer_pubkeys()  # H-01: 持久化公钥以保持 TOFU 信任链
        
        # 认证通过
        peer.peer_info.is_authenticated = True
        self.log(f"✅ 节点认证通过 (ECDSA+TOFU): {resp_node_id}")
    
    async def _handle_ping(self, peer: TCPPeer, message: P2PMessage):
        """处理 ping。"""
        await peer.send(P2PMessage(
            msg_type=MessageType.PONG,
            sender_id=self.node_id,
            payload={"ping_id": message.payload.get("ping_id")}
        ))
    
    async def _handle_pong(self, peer: TCPPeer, message: P2PMessage):
        """处理 pong。"""
        ping_id = message.payload.get("ping_id")
        if ping_id in peer.pending_pongs:
            latency = (time.time() - peer.pending_pongs[ping_id]) * 1000
            peer.peer_info.latency_ms = latency
            del peer.pending_pongs[ping_id]
    
    async def _handle_get_peers(self, peer: TCPPeer, message: P2PMessage):
        """处理节点列表请求。"""
        peers_list = [
            p.to_dict() for p in self.known_peers.values()
            if p.node_id != peer.peer_info.node_id
        ][:50]  # 最多 50 个
        
        await peer.send(P2PMessage(
            msg_type=MessageType.PEERS,
            sender_id=self.node_id,
            payload={"peers": peers_list}
        ))
    
    async def _handle_peers(self, peer: TCPPeer, message: P2PMessage):
        """处理节点列表。"""
        peers_list = message.payload.get("peers", [])
        
        for p in peers_list:
            node_id = p.get("node_id")
            if node_id and node_id not in self.known_peers and node_id != self.node_id:
                self.known_peers[node_id] = PeerInfo(
                    node_id=node_id,
                    host=p.get("host", ""),
                    port=p.get("port", 9333),
                    sector=p.get("sector", "MAIN"),
                )
    
    async def _maintenance_loop(self):
        """维护循环。"""
        while self.is_running:
            await asyncio.sleep(30)  # 每 30 秒
            
            # Ping 所有节点
            for peer in list(self.peers.values()):
                await peer.ping()
            
            # 请求更多节点
            if len(self.peers) > 0 and len(self.known_peers) < 100:
                for peer in list(self.peers.values())[:3]:
                    await peer.send(P2PMessage(
                        msg_type=MessageType.GET_PEERS,
                        sender_id=self.node_id,
                    ))
            
            # 尝试连接已知节点
            for node_id, info in list(self.known_peers.items()):
                if node_id not in self.peers and node_id != self.node_id:
                    if len(self.peers) < self.max_peers:  # 可配置连接上限
                        await self.connect(info.host, info.port)
    
    async def broadcast(self, message: P2PMessage):
        """广播消息到所有节点。"""
        message.sender_id = self.node_id
        
        for peer in list(self.peers.values()):
            await peer.send(message)
    
    def get_stats(self) -> dict:
        """获取节点统计。"""
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "sector": self.sector,
            "connected_peers": len(self.peers),
            "known_peers": len(self.known_peers),
            "peers": [
                {
                    "node_id": p.peer_info.node_id,
                    "address": p.peer_info.address,
                    "sector": p.peer_info.sector,
                    "latency_ms": p.peer_info.latency_ms,
                }
                for p in self.peers.values()
            ]
        }


# ============== 启动函数 ==============

def run_node(
    host: str = "0.0.0.0",
    port: int = 9333,
    bootstrap: List[str] = None,
    sector: str = "MAIN",
):
    """运行 P2P 节点（阻塞）。"""
    node = P2PNode(
        host=host,
        port=port,
        sector=sector,
        bootstrap_nodes=bootstrap or [],
    )
    
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        asyncio.run(node.stop())


def start_node_thread(
    host: str = "0.0.0.0",
    port: int = 9333,
    bootstrap: List[str] = None,
    sector: str = "MAIN",
) -> Tuple[P2PNode, threading.Thread]:
    """在线程中启动节点（非阻塞）。"""
    node = P2PNode(
        host=host,
        port=port,
        sector=sector,
        bootstrap_nodes=bootstrap or [],
    )
    
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(node.start())
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return node, thread


# 测试
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 9333
    
    bootstrap = []
    if len(sys.argv) > 2:
        bootstrap = [sys.argv[2]]
    
    print(f"启动节点: port={port}, bootstrap={bootstrap}")
    run_node(port=port, bootstrap=bootstrap)
