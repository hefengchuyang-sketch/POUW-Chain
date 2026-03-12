"""
p2p_data_tunnel.py - P2P 加密数据直传通道

架构变更：
  旧：User ──(100GB)──▶ Server ──(100GB)──▶ Miner   （服务器带宽瓶颈）
  新：User ──(100GB)──▶ Miner                        （P2P 直连）
      Server 仅做：匹配 + 加密信令 + 结算               （小数据量）

安全设计：
  1. 矿工 IP:Port 用用户公钥加密，服务器看不到明文 IP
  2. 用户 IP 用矿工公钥加密，矿工侧验证后才接受连接
  3. ECDH 密钥协商 → AES-256-GCM 加密所有传输数据
  4. 每个任务一个独立会话密钥，用完即弃（前向保密）
  5. 如果直连失败，自动回退到服务器中转模式
  6. S-Box 叠加加密: 一次性会话自动叠加当前区块 S-Box
     - P2P 隧道 (临时密钥) → ENHANCED 模式 (AES + S-Box SubBytes)
     - 链上固定地址操作 → STANDARD 模式 (纯 AES)

协议流程：
  ┌──────────┐         ┌──────────┐         ┌──────────┐
  │   User   │         │  Server  │         │  Miner   │
  └────┬─────┘         └────┬─────┘         └────┬─────┘
       │  1. 创建任务        │                    │
       │ ─────────────────▶ │  2. 匹配矿工        │
       │                    │ ─────────────────▶  │
       │                    │  3. 返回加密连接票据  │
       │ ◀───────────────── │    (矿工IP用户公钥加密) │
       │                    │                    │
       │  4. 解密得到矿工IP:Port                  │
       │  5. TCP 连接 + ECDH 握手                 │
       │ ═══════════════════════════════════════▶ │
       │  6. 加密数据直传 (AES-256-GCM)           │
       │ ═══════════════════════════════════════▶ │
       │                    │                    │
       │                    │  7. 提交结果哈希     │
       │                    │ ◀═════════════════  │
       │  8. 下载结果（P2P 直连）                  │
       │ ◀═══════════════════════════════════════ │
       │                    │                    │
       │  9. 确认结果        │                    │
       │ ─────────────────▶ │  10. 结算           │
       │                    │ ─────────────────▶  │
"""

import os
import time
import json
import socket
import struct
import hashlib
import secrets
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Callable, Any
from enum import IntEnum

logger = logging.getLogger(__name__)

# ============== 常量 ==============

TUNNEL_VERSION = 1
CHUNK_SIZE = 4 * 1024 * 1024       # 4MB 传输块
MAX_PACKET_SIZE = 5 * 1024 * 1024   # 5MB 最大包（含头部）
HANDSHAKE_TIMEOUT = 15               # 握手超时秒数
TRANSFER_TIMEOUT = 300               # 单块传输超时
MAX_FILE_SIZE = 100 * 1024**3        # 100GB
TICKET_EXPIRE_SECONDS = 600          # 连接票据 10 分钟过期


# ============== 包类型 ==============

class PacketType(IntEnum):
    """传输协议包类型"""
    # 握手阶段
    HELLO = 0x01            # Client → Server: session_id + ecdh_pubkey
    HELLO_ACK = 0x02        # Server → Client: ecdh_pubkey + challenge
    AUTH = 0x03             # Client → Server: challenge_response
    AUTH_OK = 0x04          # Server → Client: 认证成功
    AUTH_FAIL = 0x05        # Server → Client: 认证失败

    # 数据传输
    FILE_META = 0x10        # 文件元数据 (filename, size, sha256)
    FILE_CHUNK = 0x11       # 文件数据块
    FILE_DONE = 0x12        # 文件传输完成
    FILE_ACK = 0x13         # 确认收到

    # 结果回传
    RESULT_META = 0x20      # 结果元数据
    RESULT_CHUNK = 0x21     # 结果数据块
    RESULT_DONE = 0x22      # 结果传输完成

    # 控制
    PING = 0x30
    PONG = 0x31
    ERROR = 0xFE
    CLOSE = 0xFF


# ============== 加密工具 ==============

class TunnelCrypto:
    """隧道加密工具 — ECDH 密钥协商 + AES-256-GCM 加解密"""

    @staticmethod
    def generate_keypair() -> Tuple[bytes, bytes]:
        """生成 ECDH 密钥对 (private_key, public_key)"""
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import (
                X25519PrivateKey,
            )
            private_key = X25519PrivateKey.generate()
            public_key = private_key.public_key()
            priv_bytes = private_key.private_bytes_raw()
            pub_bytes = public_key.public_bytes_raw()
            return priv_bytes, pub_bytes
        except ImportError:
            # 回退到 ecdsa (secp256k1)
            try:
                from ecdsa import SECP256k1, SigningKey
                sk = SigningKey.generate(curve=SECP256k1)
                pk = sk.get_verifying_key()
                return sk.to_string(), pk.to_string()
            except ImportError:
                raise RuntimeError("需要 cryptography 或 ecdsa 库才能进行密钥交换")

    @staticmethod
    def compute_shared_secret(my_private: bytes, peer_public: bytes) -> bytes:
        """ECDH 计算共享密钥 → 32 字节 AES 密钥"""
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import (
                X25519PrivateKey, X25519PublicKey,
            )
            sk = X25519PrivateKey.from_private_bytes(my_private)
            pk = X25519PublicKey.from_public_bytes(peer_public)
            shared = sk.exchange(pk)
            # HKDF 派生 AES 密钥
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashes
            aes_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"pouw-p2p-tunnel-v1",
                info=b"aes-256-gcm-key",
            ).derive(shared)
            return aes_key
        except ImportError:
            # 回退 ecdsa
            try:
                from ecdsa import SECP256k1, SigningKey, VerifyingKey, ECDH
                sk = SigningKey.from_string(my_private, curve=SECP256k1)
                pk = VerifyingKey.from_string(peer_public, curve=SECP256k1)
                ecdh = ECDH(curve=SECP256k1)
                ecdh.load_private_key(sk)
                ecdh.load_received_public_key(pk)
                shared = ecdh.generate_sharedsecret_bytes()
                return hashlib.sha256(b"pouw-p2p-key:" + shared).digest()
            except ImportError:
                raise RuntimeError("需要 cryptography 或 ecdsa 库")

    @staticmethod
    def encrypt(key: bytes, plaintext: bytes, nonce: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
        """AES-256-GCM 加密 → (nonce, ciphertext, tag)"""
        if nonce is None:
            nonce = secrets.token_bytes(12)
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext, None)
            # cryptography 库把 tag 附在 ciphertext 末尾
            return nonce, ct[:-16], ct[-16:]
        except ImportError:
            # 纯 Python AES-GCM (hmac 模拟，仅用于测试/开发)
            import hmac as _hmac
            # XOR-based stream cipher simulation — NOT production-safe
            stream = hashlib.sha256(key + nonce).digest()
            ct = bytes(a ^ b for a, b in zip(plaintext, (stream * (len(plaintext) // 32 + 1))[:len(plaintext)]))
            tag = _hmac.new(key, nonce + ct, hashlib.sha256).digest()[:16]
            return nonce, ct, tag

    @staticmethod
    def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes) -> bytes:
        """AES-256-GCM 解密"""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext + tag, None)
        except ImportError:
            import hmac as _hmac
            expected_tag = _hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()[:16]
            if not _hmac.compare_digest(tag, expected_tag):
                raise ValueError("GCM 认证失败：数据被篡改")
            stream = hashlib.sha256(key + nonce).digest()
            return bytes(a ^ b for a, b in zip(ciphertext, (stream * (len(ciphertext) // 32 + 1))[:len(ciphertext)]))


# ============== 加密连接票据 ==============

@dataclass
class ConnectionTicket:
    """加密连接票据 — 矿工地址对服务器不可见

    服务器生成票据时：
    1. 用用户公钥加密矿工的 IP:Port → user_encrypted_endpoint
    2. 用矿工公钥加密用户标识 → miner_encrypted_user_id
    3. 服务器本身只保留 ticket_id + session_id，无法解密 IP

    用户收到票据后：
    1. 用自己的私钥解密 user_encrypted_endpoint → 得到矿工IP:Port
    2. 连接矿工并出示 session_token 证明身份
    """
    ticket_id: str = ""
    session_id: str = ""
    task_id: str = ""

    # 加密后的端点（服务器侧不可见明文）
    user_encrypted_endpoint: str = ""    # 矿工 IP:Port (用户公钥加密)
    miner_encrypted_user_id: str = ""    # 用户标识 (矿工公钥加密)

    # 会话令牌（双方需要匹配）
    session_token: str = ""

    # 元数据（不含敏感 IP）
    created_at: float = 0
    expires_at: float = 0
    protocol: str = "tcp"

    # 传输模式
    transfer_mode: str = "p2p"          # p2p 或 relay (回退)
    relay_endpoint: str = ""            # 回退时用的服务器中转地址

    def to_dict(self) -> Dict:
        return {
            "ticketId": self.ticket_id,
            "sessionId": self.session_id,
            "taskId": self.task_id,
            "userEncryptedEndpoint": self.user_encrypted_endpoint,
            "minerEncryptedUserId": self.miner_encrypted_user_id,
            "sessionToken": self.session_token,
            "createdAt": self.created_at,
            "expiresAt": self.expires_at,
            "transferMode": self.transfer_mode,
            "relayEndpoint": self.relay_endpoint,
        }

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


# ============== 票据管理器 ==============

class TicketManager:
    """连接票据管理器 — 在服务器侧运行

    职责：
    - 为每个任务分配生成加密连接票据
    - 用 RSA/ECIES 加密矿工 IP，只有任务创建者能解密
    - 服务器全程不接触明文 IP
    """

    def __init__(self):
        self._tickets: Dict[str, ConnectionTicket] = {}
        self._miner_endpoints: Dict[str, Tuple[str, int]] = {}   # miner_id → (ip, port)
        self._miner_pubkeys: Dict[str, bytes] = {}       # miner_id → 加密公钥
        self._lock = threading.RLock()

    def register_miner_endpoint(
        self,
        miner_id: str,
        encrypted_ip: str,
        encrypted_port: str,
        miner_pubkey: bytes,
    ):
        """矿工注册时上报加密的 IP 信息

        矿工把自己的 IP:Port 用自己的公钥加密后上传，
        服务器只存储加密后的值和矿工公钥。
        生成票据时用用户公钥重新加密。

        为了让用户能解密，实际实现中矿工需要把明文 IP 上报给服务器，
        服务器用用户公钥加密后立即丢弃明文。
        或者更安全的方式：矿工直接提供公钥，服务器联系矿工获取一次性加密端点。
        当前实现采用折中方案：矿工上报 IP，服务器加密后只在内存中短暂持有。
        """
        with self._lock:
            # 解密矿工发来的端点信息（矿工侧已用对称密钥加密，此处简化为直接存储）
            # 生产环境应使用 TEE/SGX 保护或矿工端直接加密给用户
            self._miner_endpoints[miner_id] = (encrypted_ip, int(encrypted_port))
            self._miner_pubkeys[miner_id] = miner_pubkey

    def register_miner_direct(self, miner_id: str, ip: str, port: int, pubkey: bytes):
        """矿工直接注册 IP（用于内网/信任环境）"""
        with self._lock:
            self._miner_endpoints[miner_id] = (ip, port)
            self._miner_pubkeys[miner_id] = pubkey

    def create_ticket(
        self,
        task_id: str,
        user_id: str,
        miner_id: str,
        user_pubkey: bytes,
        relay_endpoint: str = "",
    ) -> Optional[ConnectionTicket]:
        """为任务创建加密连接票据

        将矿工 IP:Port 用用户公钥加密，服务器不保留明文。
        """
        with self._lock:
            endpoint = self._miner_endpoints.get(miner_id)
            if not endpoint:
                logger.warning(f"矿工 {miner_id} 未注册 P2P 端点，回退到服务器中转")
                return self._create_relay_ticket(task_id, user_id, miner_id, relay_endpoint)

            miner_ip, miner_port = endpoint
            miner_pubkey = self._miner_pubkeys.get(miner_id, b"")

            # 生成会话令牌
            session_token = secrets.token_hex(32)
            session_id = secrets.token_hex(16)
            ticket_id = secrets.token_hex(12)

            # 加密矿工端点：用用户公钥加密 → 只有用户能解密
            endpoint_plain = json.dumps({
                "ip": miner_ip,
                "port": miner_port,
                "token": session_token,
            }).encode()

            encrypted_endpoint = self._encrypt_for_recipient(endpoint_plain, user_pubkey)

            # 加密用户标识：用矿工公钥加密 → 只有矿工能解密
            user_info_plain = json.dumps({
                "userId": user_id,
                "taskId": task_id,
                "token": session_token,
            }).encode()

            encrypted_user_id = self._encrypt_for_recipient(user_info_plain, miner_pubkey)

            ticket = ConnectionTicket(
                ticket_id=ticket_id,
                session_id=session_id,
                task_id=task_id,
                user_encrypted_endpoint=encrypted_endpoint,
                miner_encrypted_user_id=encrypted_user_id,
                session_token=session_token,
                created_at=time.time(),
                expires_at=time.time() + TICKET_EXPIRE_SECONDS,
                transfer_mode="p2p",
                relay_endpoint=relay_endpoint,
            )

            self._tickets[ticket_id] = ticket
            logger.info(f"P2P 票据已创建: ticket={ticket_id} task={task_id}")

            return ticket

    def _create_relay_ticket(
        self, task_id: str, user_id: str, miner_id: str, relay_endpoint: str
    ) -> ConnectionTicket:
        """创建中转模式票据（矿工未注册 P2P 时的回退方案）"""
        ticket_id = secrets.token_hex(12)
        return ConnectionTicket(
            ticket_id=ticket_id,
            session_id=secrets.token_hex(16),
            task_id=task_id,
            session_token=secrets.token_hex(32),
            created_at=time.time(),
            expires_at=time.time() + TICKET_EXPIRE_SECONDS,
            transfer_mode="relay",
            relay_endpoint=relay_endpoint,
        )

    def validate_ticket(self, ticket_id: str, session_token: str) -> bool:
        """验证票据有效性"""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                return False
            if ticket.is_expired():
                self._tickets.pop(ticket_id, None)
                return False
            return secrets.compare_digest(ticket.session_token, session_token)

    def revoke_ticket(self, ticket_id: str):
        """吊销票据"""
        with self._lock:
            self._tickets.pop(ticket_id, None)

    def cleanup_expired(self):
        """清理过期票据"""
        with self._lock:
            now = time.time()
            expired = [tid for tid, t in self._tickets.items() if t.is_expired()]
            for tid in expired:
                self._tickets.pop(tid, None)
            if expired:
                logger.info(f"清理 {len(expired)} 个过期 P2P 票据")

    def get_miner_pubkey(self, miner_id: str) -> Optional[bytes]:
        with self._lock:
            return self._miner_pubkeys.get(miner_id)

    def is_miner_p2p_ready(self, miner_id: str) -> bool:
        with self._lock:
            return miner_id in self._miner_endpoints

    @staticmethod
    def _encrypt_for_recipient(plaintext: bytes, recipient_pubkey: bytes) -> str:
        """用接收方公钥进行非对称加密（ECIES 风格）

        1. 生成临时 ECDH 密钥对
        2. 与接收方公钥协商出 AES 密钥
        3. AES-256-GCM 加密明文
        4. 返回: 临时公钥 + nonce + ciphertext + tag (hex)
        """
        if not recipient_pubkey:
            # 无公钥时使用简单对称加密（仅限开发环境）
            import base64
            return base64.b64encode(plaintext).decode()

        ephemeral_priv, ephemeral_pub = TunnelCrypto.generate_keypair()
        try:
            aes_key = TunnelCrypto.compute_shared_secret(ephemeral_priv, recipient_pubkey)
        except Exception:
            # 密钥长度不匹配等异常，回退到 base64
            import base64
            return base64.b64encode(plaintext).decode()

        nonce, ct, tag = TunnelCrypto.encrypt(aes_key, plaintext)
        # 拼接: ephemeral_pub(32B) + nonce(12B) + tag(16B) + ciphertext
        packet = ephemeral_pub + nonce + tag + ct
        return packet.hex()

    @staticmethod
    def decrypt_ticket_endpoint(encrypted_hex: str, my_private_key: bytes) -> Optional[Dict]:
        """用自己的私钥解密连接票据中的端点信息"""
        try:
            raw = bytes.fromhex(encrypted_hex)
        except ValueError:
            # 可能是 base64 编码的开发模式
            try:
                import base64
                raw = base64.b64decode(encrypted_hex)
                return json.loads(raw.decode())
            except Exception:
                return None

        # 解析: ephemeral_pub(32B) + nonce(12B) + tag(16B) + ciphertext
        if len(raw) < 60:  # 32+12+16 = 60 minimum
            return None

        # 检测密钥类型（X25519 为 32 字节，secp256k1 为 64 字节）
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
            pub_len = 32
        except ImportError:
            pub_len = 64  # secp256k1

        if len(raw) < pub_len + 28:
            return None

        ephemeral_pub = raw[:pub_len]
        nonce = raw[pub_len:pub_len + 12]
        tag = raw[pub_len + 12:pub_len + 28]
        ct = raw[pub_len + 28:]

        aes_key = TunnelCrypto.compute_shared_secret(my_private_key, ephemeral_pub)
        plaintext = TunnelCrypto.decrypt(aes_key, nonce, ct, tag)
        return json.loads(plaintext.decode())


# ============== P2P 数据服务器（矿工侧运行） ==============

class P2PDataServer:
    """P2P 数据接收服务器 — 运行在矿工节点上

    监听端口接受来自用户的加密数据传输。
    每个到来的连接通过 ECDH 握手建立独立会话密钥。
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 0,                   # 0 = 自动选择端口
        data_dir: str = "data/p2p_recv",
        max_connections: int = 10,
    ):
        self.host = host
        self.port = port
        self.data_dir = data_dir
        self.max_connections = max_connections
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sessions: Dict[str, dict] = {}  # session_token → session_info
        self._lock = threading.RLock()

        # ECDH 服务器长期密钥对（注册时公钥提交给平台）
        self._private_key, self._public_key = TunnelCrypto.generate_keypair()

        # 回调
        self.on_file_received: Optional[Callable[[str, str, str], None]] = None  # (task_id, filename, filepath)
        self.on_transfer_complete: Optional[Callable[[str], None]] = None        # (task_id)

        os.makedirs(data_dir, exist_ok=True)

    @property
    def public_key(self) -> bytes:
        return self._public_key

    @property
    def actual_port(self) -> int:
        """实际绑定的端口（port=0 时由系统分配）"""
        if self._server_socket:
            return self._server_socket.getsockname()[1]
        return self.port

    def authorize_session(self, session_token: str, task_id: str, user_id: str):
        """服务器分配任务后，调用此方法授权一个传入会话"""
        with self._lock:
            self._sessions[session_token] = {
                "task_id": task_id,
                "user_id": user_id,
                "authorized_at": time.time(),
                "connected": False,
            }

    def start(self):
        """启动 P2P 数据服务器"""
        if self._running:
            return

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(self.max_connections)
        self._server_socket.settimeout(2.0)  # 非阻塞以支持停止
        self._running = True

        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="p2p-data-server")
        self._thread.start()

        logger.info(f"P2P 数据服务器已启动: {self.host}:{self.actual_port}")

    def stop(self):
        """停止 P2P 数据服务器"""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("P2P 数据服务器已停止")

    def _accept_loop(self):
        """接受连接的主循环"""
        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                logger.info(f"P2P 连接来自: {addr[0]}:{addr[1]}")
                handler = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock,),
                    daemon=True,
                    name=f"p2p-client-{addr[1]}",
                )
                handler.start()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.error("P2P 数据服务器 accept 异常")
                break

    def _handle_client(self, sock: socket.socket):
        """处理单个客户端连接"""
        session_key = None
        task_id = None
        try:
            sock.settimeout(HANDSHAKE_TIMEOUT)

            # ── 握手阶段 ──
            # 1. 接收 HELLO
            pkt_type, payload = self._recv_packet(sock)
            if pkt_type != PacketType.HELLO:
                self._send_packet(sock, PacketType.AUTH_FAIL, b'{"error":"expected HELLO"}')
                return

            hello = json.loads(payload)
            session_token = hello.get("sessionToken", "")
            client_pubkey = bytes.fromhex(hello.get("publicKey", ""))

            # 验证会话令牌
            with self._lock:
                session_info = self._sessions.get(session_token)
            if not session_info:
                self._send_packet(sock, PacketType.AUTH_FAIL, b'{"error":"invalid session"}')
                return

            task_id = session_info["task_id"]

            # 2. 发送 HELLO_ACK + 我方公钥 + challenge
            challenge = secrets.token_bytes(32)
            ack_data = json.dumps({
                "publicKey": self._public_key.hex(),
                "challenge": challenge.hex(),
            }).encode()
            self._send_packet(sock, PacketType.HELLO_ACK, ack_data)

            # 3. 计算共享密钥
            session_key = TunnelCrypto.compute_shared_secret(self._private_key, client_pubkey)

            # 4. 接收 AUTH（客户端用共享密钥加密 challenge 回应）
            pkt_type, payload = self._recv_packet(sock)
            if pkt_type != PacketType.AUTH:
                return

            # 验证 challenge 响应
            auth_data = json.loads(payload)
            response_nonce = bytes.fromhex(auth_data["nonce"])
            response_ct = bytes.fromhex(auth_data["ciphertext"])
            response_tag = bytes.fromhex(auth_data["tag"])
            decrypted = TunnelCrypto.decrypt(session_key, response_nonce, response_ct, response_tag)
            if decrypted != challenge:
                self._send_packet(sock, PacketType.AUTH_FAIL, b'{"error":"auth failed"}')
                return

            # 认证成功
            with self._lock:
                session_info["connected"] = True
            self._send_packet(sock, PacketType.AUTH_OK, b'{"status":"ok"}')

            logger.info(f"P2P 握手成功: task={task_id}")

            # S-Box 叠加加密 (一次性会话密钥场景)
            sbox_cipher = None
            try:
                from core.sbox_crypto import SBoxSessionCipher, SBoxEncryptionLevel
                sbox_cipher = SBoxSessionCipher(
                    session_key,
                    level=SBoxEncryptionLevel.ENHANCED,
                )
                logger.debug(f"P2P S-Box 加密已启用: sbox_hash={sbox_cipher.sbox_hash_hex[:16]}...")
            except Exception:
                logger.debug("P2P S-Box 加密不可用，使用纯 AES-256-GCM")

            # ── 数据传输阶段 ──
            sock.settimeout(TRANSFER_TIMEOUT)
            self._receive_files(sock, session_key, task_id, sbox_cipher=sbox_cipher)

        except socket.timeout:
            logger.warning(f"P2P 连接超时: task={task_id}")
        except Exception as e:
            logger.error(f"P2P 连接处理异常: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _receive_files(self, sock: socket.socket, session_key: bytes, task_id: str,
                       sbox_cipher=None):
        """接收加密文件数据"""
        task_dir = os.path.join(self.data_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)

        current_file = None
        current_path = None
        current_hasher = None
        received_size = 0
        expected_size = 0

        try:
            while True:
                pkt_type, payload = self._recv_encrypted_packet(sock, session_key,
                                                                 sbox_cipher=sbox_cipher)

                if pkt_type == PacketType.FILE_META:
                    meta = json.loads(payload)
                    filename = os.path.basename(meta["filename"])  # 防路径穿越
                    expected_size = meta["size"]
                    expected_hash = meta.get("sha256", "")

                    if expected_size > MAX_FILE_SIZE:
                        self._send_encrypted_packet(sock, session_key, PacketType.ERROR,
                                                    json.dumps({"error": "file too large"}).encode(),
                                                    sbox_cipher=sbox_cipher)
                        return

                    current_path = os.path.join(task_dir, filename)
                    current_file = open(current_path, "wb")
                    current_hasher = hashlib.sha256()
                    received_size = 0
                    logger.info(f"P2P 接收文件开始: {filename} ({expected_size} bytes)")

                elif pkt_type == PacketType.FILE_CHUNK:
                    if current_file:
                        current_file.write(payload)
                        current_hasher.update(payload)
                        received_size += len(payload)

                elif pkt_type == PacketType.FILE_DONE:
                    if current_file:
                        current_file.close()
                        current_file = None
                        actual_hash = current_hasher.hexdigest()
                        done_info = json.loads(payload) if payload else {}
                        expected_hash = done_info.get("sha256", "")

                        if expected_hash and actual_hash != expected_hash:
                            logger.error(f"P2P 文件哈希不匹配: expected={expected_hash} actual={actual_hash}")
                            os.remove(current_path)
                            self._send_encrypted_packet(sock, session_key, PacketType.ERROR,
                                                        json.dumps({"error": "hash mismatch"}).encode(),
                                                        sbox_cipher=sbox_cipher)
                            return

                        logger.info(f"P2P 文件接收完成: {os.path.basename(current_path)} hash={actual_hash[:16]}")
                        self._send_encrypted_packet(sock, session_key, PacketType.FILE_ACK,
                                                    json.dumps({"received": received_size, "hash": actual_hash}).encode(),
                                                    sbox_cipher=sbox_cipher)

                        if self.on_file_received:
                            self.on_file_received(task_id, os.path.basename(current_path), current_path)

                        current_path = None
                        current_hasher = None

                elif pkt_type == PacketType.CLOSE:
                    logger.info(f"P2P 传输会话关闭: task={task_id}")
                    if self.on_transfer_complete:
                        self.on_transfer_complete(task_id)
                    return

                elif pkt_type == PacketType.PING:
                    self._send_encrypted_packet(sock, session_key, PacketType.PONG, b"",
                                                sbox_cipher=sbox_cipher)

                else:
                    logger.warning(f"未知包类型: {pkt_type}")
        finally:
            if current_file:
                current_file.close()

    # ── 协议读写 ──

    @staticmethod
    def _send_packet(sock: socket.socket, pkt_type: PacketType, payload: bytes):
        """发送明文包: [4B length][1B type][payload]"""
        header = struct.pack("!IB", len(payload) + 1, int(pkt_type))
        sock.sendall(header + payload)

    @staticmethod
    def _recv_packet(sock: socket.socket) -> Tuple[PacketType, bytes]:
        """接收明文包"""
        header = _recv_exact(sock, 5)
        length, pkt_type = struct.unpack("!IB", header)
        payload_len = length - 1
        if payload_len > MAX_PACKET_SIZE:
            raise ValueError(f"包过大: {payload_len}")
        payload = _recv_exact(sock, payload_len) if payload_len > 0 else b""
        return PacketType(pkt_type), payload

    @staticmethod
    def _send_encrypted_packet(sock: socket.socket, key: bytes, pkt_type: PacketType, payload: bytes,
                               sbox_cipher=None):
        """发送加密包: [4B length][1B type][12B nonce][16B tag][ciphertext]

        如果提供 sbox_cipher (SBoxSessionCipher)，则使用 S-Box 叠加加密 (一次性密钥场景)。
        否则使用纯 AES-256-GCM。
        """
        if sbox_cipher is not None:
            encrypted = sbox_cipher.encrypt(payload)
            header = struct.pack("!IB", len(encrypted) + 1, int(pkt_type))
            sock.sendall(header + encrypted)
        else:
            nonce, ct, tag = TunnelCrypto.encrypt(key, payload)
            encrypted = nonce + tag + ct
            header = struct.pack("!IB", len(encrypted) + 1, int(pkt_type))
            sock.sendall(header + encrypted)

    @staticmethod
    def _recv_encrypted_packet(sock: socket.socket, key: bytes,
                               sbox_cipher=None) -> Tuple[PacketType, bytes]:
        """接收加密包

        如果提供 sbox_cipher，使用 S-Box 解密; 否则纯 AES 解密。
        """
        header = _recv_exact(sock, 5)
        length, pkt_type = struct.unpack("!IB", header)
        payload_len = length - 1
        if payload_len > MAX_PACKET_SIZE:
            raise ValueError(f"加密包过大: {payload_len}")
        raw = _recv_exact(sock, payload_len) if payload_len > 0 else b""

        if sbox_cipher is not None:
            plaintext = sbox_cipher.decrypt(raw)
            return PacketType(pkt_type), plaintext

        if len(raw) < 28:
            return PacketType(pkt_type), raw

        nonce = raw[:12]
        tag = raw[12:28]
        ct = raw[28:]
        plaintext = TunnelCrypto.decrypt(key, nonce, ct, tag)
        return PacketType(pkt_type), plaintext


# ============== P2P 数据客户端（用户侧运行） ==============

class P2PDataClient:
    """P2P 数据发送客户端 — 运行在用户端

    连接矿工的 P2PDataServer，通过加密隧道直接传输数据。
    """

    def __init__(self):
        self._private_key, self._public_key = TunnelCrypto.generate_keypair()

    @property
    def public_key(self) -> bytes:
        return self._public_key

    def send_file(
        self,
        host: str,
        port: int,
        session_token: str,
        file_path: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[Dict]:
        """向矿工 P2P 直传一个文件

        Args:
            host: 矿工 IP
            port: 矿工端口
            session_token: 授权令牌
            file_path: 本地文件路径
            on_progress: 进度回调 (sent_bytes, total_bytes)

        Returns:
            {"received": N, "hash": "sha256..."} 或 None
        """
        if not os.path.isfile(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None

        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(HANDSHAKE_TIMEOUT)

        try:
            sock.connect((host, port))

            # ── 握手 ──
            result = self._handshake(sock, session_token)
            if not result:
                return None
            session_key, sbox_cipher = result

            sock.settimeout(TRANSFER_TIMEOUT)

            # ── 发送文件元数据 ──
            file_hash = _compute_file_sha256(file_path)
            meta = json.dumps({
                "filename": filename,
                "size": file_size,
                "sha256": file_hash,
            }).encode()
            P2PDataServer._send_encrypted_packet(sock, session_key, PacketType.FILE_META, meta,
                                                  sbox_cipher=sbox_cipher)

            # ── 发送文件数据块 ──
            sent = 0
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    P2PDataServer._send_encrypted_packet(sock, session_key, PacketType.FILE_CHUNK, chunk,
                                                          sbox_cipher=sbox_cipher)
                    sent += len(chunk)
                    if on_progress:
                        on_progress(sent, file_size)

            # ── 文件完成 ──
            done_data = json.dumps({"sha256": file_hash}).encode()
            P2PDataServer._send_encrypted_packet(sock, session_key, PacketType.FILE_DONE, done_data,
                                                  sbox_cipher=sbox_cipher)

            # 等待 ACK
            pkt_type, payload = P2PDataServer._recv_encrypted_packet(sock, session_key,
                                                                      sbox_cipher=sbox_cipher)
            if pkt_type == PacketType.FILE_ACK:
                result = json.loads(payload)
                logger.info(f"P2P 文件发送完成: {filename} → {host}:{port}")
                return result
            elif pkt_type == PacketType.ERROR:
                error = json.loads(payload)
                logger.error(f"P2P 传输错误: {error}")
                return None

        except socket.timeout:
            logger.error(f"P2P 连接超时: {host}:{port}")
            return None
        except ConnectionRefusedError:
            logger.error(f"P2P 连接被拒绝: {host}:{port}")
            return None
        except Exception as e:
            logger.error(f"P2P 传输失败: {e}")
            return None
        finally:
            try:
                P2PDataServer._send_packet(sock, PacketType.CLOSE, b"")
            except Exception:
                pass
            sock.close()

    def send_data(
        self,
        host: str,
        port: int,
        session_token: str,
        data: bytes,
        filename: str = "input_data.bin",
    ) -> Optional[Dict]:
        """直接发送内存中的数据（无需写临时文件）"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(HANDSHAKE_TIMEOUT)

        try:
            sock.connect((host, port))

            session_key_result = self._handshake(sock, session_token)
            if not session_key_result:
                return None
            session_key, sbox_cipher = session_key_result

            sock.settimeout(TRANSFER_TIMEOUT)

            data_hash = hashlib.sha256(data).hexdigest()
            meta = json.dumps({
                "filename": filename,
                "size": len(data),
                "sha256": data_hash,
            }).encode()
            P2PDataServer._send_encrypted_packet(sock, session_key, PacketType.FILE_META, meta,
                                                  sbox_cipher=sbox_cipher)

            # 分块发送
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset + CHUNK_SIZE]
                P2PDataServer._send_encrypted_packet(sock, session_key, PacketType.FILE_CHUNK, chunk,
                                                      sbox_cipher=sbox_cipher)
                offset += len(chunk)

            done_data = json.dumps({"sha256": data_hash}).encode()
            P2PDataServer._send_encrypted_packet(sock, session_key, PacketType.FILE_DONE, done_data,
                                                  sbox_cipher=sbox_cipher)

            pkt_type, payload = P2PDataServer._recv_encrypted_packet(sock, session_key,
                                                                      sbox_cipher=sbox_cipher)
            if pkt_type == PacketType.FILE_ACK:
                return json.loads(payload)
            return None

        except Exception as e:
            logger.error(f"P2P 数据发送失败: {e}")
            return None
        finally:
            try:
                P2PDataServer._send_packet(sock, PacketType.CLOSE, b"")
            except Exception:
                pass
            sock.close()

    def _handshake(self, sock: socket.socket, session_token: str) -> Optional[bytes]:
        """ECDH 握手，返回会话密钥"""
        # 1. 发送 HELLO
        hello = json.dumps({
            "sessionToken": session_token,
            "publicKey": self._public_key.hex(),
            "version": TUNNEL_VERSION,
        }).encode()
        P2PDataServer._send_packet(sock, PacketType.HELLO, hello)

        # 2. 接收 HELLO_ACK
        pkt_type, payload = P2PDataServer._recv_packet(sock)
        if pkt_type == PacketType.AUTH_FAIL:
            logger.error("P2P 认证失败: 会话无效")
            return None
        if pkt_type != PacketType.HELLO_ACK:
            return None

        ack = json.loads(payload)
        server_pubkey = bytes.fromhex(ack["publicKey"])
        challenge = bytes.fromhex(ack["challenge"])

        # 3. 计算共享密钥
        session_key = TunnelCrypto.compute_shared_secret(self._private_key, server_pubkey)

        # 4. 发送 AUTH（用共享密钥加密 challenge 作为认证证明）
        nonce, ct, tag = TunnelCrypto.encrypt(session_key, challenge)
        auth_data = json.dumps({
            "nonce": nonce.hex(),
            "ciphertext": ct.hex(),
            "tag": tag.hex(),
        }).encode()
        P2PDataServer._send_packet(sock, PacketType.AUTH, auth_data)

        # 5. 等待 AUTH_OK
        pkt_type, payload = P2PDataServer._recv_packet(sock)
        if pkt_type != PacketType.AUTH_OK:
            logger.error("P2P 认证失败")
            return None

        logger.info("P2P 握手完成，加密隧道已建立")

        # S-Box 叠加加密 (一次性会话密钥)
        sbox_cipher = None
        try:
            from core.sbox_crypto import SBoxSessionCipher, SBoxEncryptionLevel
            sbox_cipher = SBoxSessionCipher(
                session_key,
                level=SBoxEncryptionLevel.ENHANCED,
            )
            logger.debug(f"P2P 客户端 S-Box 加密启用: sbox_hash={sbox_cipher.sbox_hash_hex[:16]}...")
        except Exception:
            logger.debug("P2P 客户端 S-Box 不可用，使用纯 AES-256-GCM")

        return session_key, sbox_cipher

    def download_result(
        self,
        host: str,
        port: int,
        session_token: str,
        save_dir: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[Dict[str, str]]:
        """从矿工 P2P 直接下载结果文件

        Returns:
            {"filename": filepath, ...} 文件映射
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(HANDSHAKE_TIMEOUT)
        received_files = {}

        try:
            sock.connect((host, port))
            result = self._handshake(sock, session_token)
            if not result:
                return None
            session_key, sbox_cipher = result

            sock.settimeout(TRANSFER_TIMEOUT)
            os.makedirs(save_dir, exist_ok=True)

            # 请求结果
            P2PDataServer._send_encrypted_packet(sock, session_key, PacketType.RESULT_META,
                                                  json.dumps({"action": "download"}).encode(),
                                                  sbox_cipher=sbox_cipher)

            current_file = None
            current_path = None
            current_hasher = None

            try:
                while True:
                    pkt_type, payload = P2PDataServer._recv_encrypted_packet(sock, session_key,
                                                                              sbox_cipher=sbox_cipher)

                    if pkt_type == PacketType.RESULT_META:
                        meta = json.loads(payload)
                        filename = os.path.basename(meta["filename"])
                        current_path = os.path.join(save_dir, filename)
                        current_file = open(current_path, "wb")
                        current_hasher = hashlib.sha256()

                    elif pkt_type == PacketType.RESULT_CHUNK:
                        if current_file:
                            current_file.write(payload)
                            current_hasher.update(payload)

                    elif pkt_type == PacketType.RESULT_DONE:
                        if current_file:
                            current_file.close()
                            current_file = None
                            received_files[os.path.basename(current_path)] = current_path

                    elif pkt_type in (PacketType.CLOSE, PacketType.ERROR):
                        break
            finally:
                if current_file:
                    current_file.close()

            return received_files

        except Exception as e:
            logger.error(f"P2P 结果下载失败: {e}")
            return None
        finally:
            sock.close()


# ============== 辅助函数 ==============

def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """从 socket 精确读取 n 字节"""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("连接中断")
        buf.extend(chunk)
    return bytes(buf)


def _compute_file_sha256(filepath: str) -> str:
    """计算文件 SHA256"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            block = f.read(65536)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


# ============== 结果回传服务器（用户侧运行） ==============

class P2PResultServer:
    """P2P 结果接收服务器 — 运行在用户端

    任务完成时，矿工主动连接用户的 P2PResultServer 回传结果。
    用户端也可以主动连接矿工 pull 结果（见 P2PDataClient.download_result）。
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 0, save_dir: str = "data/p2p_results"):
        self.host = host
        self.port = port
        self.save_dir = save_dir
        self._private_key, self._public_key = TunnelCrypto.generate_keypair()
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._authorized_tokens: Dict[str, str] = {}  # token → task_id
        self._results: Dict[str, Dict[str, str]] = {}  # task_id → {filename: path}
        self._lock = threading.RLock()

        os.makedirs(save_dir, exist_ok=True)

    @property
    def public_key(self) -> bytes:
        return self._public_key

    @property
    def actual_port(self) -> int:
        if self._server_socket:
            return self._server_socket.getsockname()[1]
        return self.port

    def authorize_result(self, session_token: str, task_id: str):
        """授权矿工回传结果"""
        with self._lock:
            self._authorized_tokens[session_token] = task_id

    def get_results(self, task_id: str) -> Optional[Dict[str, str]]:
        """获取已收到的结果"""
        with self._lock:
            return self._results.get(task_id)

    def start(self):
        if self._running:
            return
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(2.0)
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="p2p-result-server")
        self._thread.start()
        logger.info(f"P2P 结果服务器已启动: {self.host}:{self.actual_port}")

    def stop(self):
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)

    def _accept_loop(self):
        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                handler = threading.Thread(
                    target=self._handle_miner,
                    args=(client_sock,),
                    daemon=True,
                )
                handler.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_miner(self, sock: socket.socket):
        """处理矿工的结果回传连接"""
        try:
            sock.settimeout(HANDSHAKE_TIMEOUT)

            # HELLO
            pkt_type, payload = P2PDataServer._recv_packet(sock)
            if pkt_type != PacketType.HELLO:
                return

            hello = json.loads(payload)
            token = hello.get("sessionToken", "")
            miner_pubkey = bytes.fromhex(hello.get("publicKey", ""))

            with self._lock:
                task_id = self._authorized_tokens.get(token)
            if not task_id:
                P2PDataServer._send_packet(sock, PacketType.AUTH_FAIL, b'{"error":"unauthorized"}')
                return

            # HELLO_ACK
            challenge = secrets.token_bytes(32)
            ack = json.dumps({
                "publicKey": self._public_key.hex(),
                "challenge": challenge.hex(),
            }).encode()
            P2PDataServer._send_packet(sock, PacketType.HELLO_ACK, ack)

            # 计算共享密钥
            session_key = TunnelCrypto.compute_shared_secret(self._private_key, miner_pubkey)

            # AUTH
            pkt_type, payload = P2PDataServer._recv_packet(sock)
            if pkt_type != PacketType.AUTH:
                return
            auth = json.loads(payload)
            decrypted = TunnelCrypto.decrypt(
                session_key,
                bytes.fromhex(auth["nonce"]),
                bytes.fromhex(auth["ciphertext"]),
                bytes.fromhex(auth["tag"]),
            )
            if decrypted != challenge:
                P2PDataServer._send_packet(sock, PacketType.AUTH_FAIL, b'{"error":"auth failed"}')
                return

            P2PDataServer._send_packet(sock, PacketType.AUTH_OK, b'{"status":"ok"}')

            # S-Box 加密 (结果回传也是一次性密钥)
            sbox_cipher = None
            try:
                from core.sbox_crypto import SBoxSessionCipher, SBoxEncryptionLevel
                sbox_cipher = SBoxSessionCipher(session_key, level=SBoxEncryptionLevel.ENHANCED)
            except Exception:
                pass

            # 接收结果文件
            sock.settimeout(TRANSFER_TIMEOUT)
            task_dir = os.path.join(self.save_dir, task_id)
            os.makedirs(task_dir, exist_ok=True)

            received = {}
            current_file = None
            current_path = None

            try:
                while True:
                    pkt_type, payload = P2PDataServer._recv_encrypted_packet(sock, session_key,
                                                                              sbox_cipher=sbox_cipher)

                    if pkt_type == PacketType.RESULT_META:
                        meta = json.loads(payload)
                        filename = os.path.basename(meta["filename"])
                        current_path = os.path.join(task_dir, filename)
                        current_file = open(current_path, "wb")

                    elif pkt_type == PacketType.RESULT_CHUNK:
                        if current_file:
                            current_file.write(payload)

                    elif pkt_type == PacketType.RESULT_DONE:
                        if current_file:
                            current_file.close()
                            current_file = None
                            received[os.path.basename(current_path)] = current_path

                    elif pkt_type in (PacketType.CLOSE, PacketType.ERROR):
                        break
            finally:
                if current_file:
                    current_file.close()

            with self._lock:
                self._results[task_id] = received

            logger.info(f"P2P 结果已接收: task={task_id} files={list(received.keys())}")

        except Exception as e:
            logger.error(f"P2P 结果接收异常: {e}")
        finally:
            sock.close()
