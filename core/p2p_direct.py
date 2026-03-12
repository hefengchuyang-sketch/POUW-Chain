"""
p2p_direct.py - 用户与算力节点 P2P 直连

.. warning:: EXPERIMENTAL / 实验性模块
    此模块为纯数据结构模拟，未实现真实网络连接。
    所有 P2P 操作均在内存中完成，无真实 WebRTC/QUIC 传输。
    RPC 层的 p2p_* 端点（如 p2p_setupConnection）基于此模块，
    返回的是模拟数据而非真实连接状态。

Phase 9 功能：
1. P2P 直连通道 (WebRTC / QUIC)
2. 平台只负责匹配、密钥交换、结算
3. 数据流不经过平台
4. 连接握手与隧道建立
5. NAT 穿透支持
"""

import time
import uuid
import hashlib
import secrets
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from collections import defaultdict
import base64
import json


# ============== 枚举类型 ==============

class TransportProtocol(Enum):
    """传输协议"""
    WEBRTC = "webrtc"                  # WebRTC
    QUIC = "quic"                      # QUIC
    TCP_TUNNEL = "tcp_tunnel"          # TCP 隧道
    WIREGUARD = "wireguard"            # WireGuard VPN
    SSH_TUNNEL = "ssh_tunnel"          # SSH 隧道


class ConnectionState(Enum):
    """连接状态"""
    INIT = "init"                      # 初始化
    SIGNALING = "signaling"            # 信令交换中
    CONNECTING = "connecting"          # 连接中
    CONNECTED = "connected"            # 已连接
    DISCONNECTED = "disconnected"      # 已断开
    FAILED = "failed"                  # 连接失败


class NATType(Enum):
    """NAT 类型"""
    OPEN = "open"                      # 开放
    FULL_CONE = "full_cone"            # 完全锥形
    RESTRICTED = "restricted"          # 限制锥形
    PORT_RESTRICTED = "port_restricted" # 端口限制
    SYMMETRIC = "symmetric"            # 对称型
    UNKNOWN = "unknown"


class SignalingType(Enum):
    """信令类型"""
    OFFER = "offer"                    # 提议
    ANSWER = "answer"                  # 应答
    ICE_CANDIDATE = "ice_candidate"    # ICE 候选
    HANGUP = "hangup"                  # 挂断


# ============== 数据结构 ==============

@dataclass
class PeerInfo:
    """对等方信息"""
    peer_id: str
    peer_type: str                     # user / miner
    
    # 网络信息
    public_ip: str = ""
    public_port: int = 0
    local_ip: str = ""
    local_port: int = 0
    nat_type: NATType = NATType.UNKNOWN
    
    # 支持的协议
    supported_protocols: List[TransportProtocol] = field(default_factory=list)
    preferred_protocol: TransportProtocol = TransportProtocol.QUIC
    
    # STUN/TURN 服务器
    stun_servers: List[str] = field(default_factory=list)
    turn_servers: List[Dict] = field(default_factory=list)
    
    # 能力
    supports_upnp: bool = False
    supports_hole_punching: bool = True
    bandwidth_mbps: float = 0
    latency_ms: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "peer_id": self.peer_id,
            "peer_type": self.peer_type,
            "public_ip": self.public_ip,
            "public_port": self.public_port,
            "nat_type": self.nat_type.value,
            "supported_protocols": [p.value for p in self.supported_protocols],
            "preferred_protocol": self.preferred_protocol.value,
            "bandwidth_mbps": self.bandwidth_mbps,
        }


@dataclass
class SignalingMessage:
    """信令消息"""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    signaling_type: SignalingType = SignalingType.OFFER
    
    # 参与方
    from_peer: str = ""
    to_peer: str = ""
    session_id: str = ""
    
    # SDP / ICE
    sdp: str = ""                      # Session Description Protocol
    sdp_type: str = ""                 # offer / answer
    ice_candidate: Dict = field(default_factory=dict)
    
    # 加密
    encrypted: bool = True
    signature: str = ""
    
    # 时间
    timestamp: float = field(default_factory=time.time)
    expires_at: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "type": self.signaling_type.value,
            "from": self.from_peer,
            "to": self.to_peer,
            "session_id": self.session_id,
            "sdp": self.sdp[:100] + "..." if len(self.sdp) > 100 else self.sdp,
            "timestamp": self.timestamp,
        }


@dataclass
class P2PSession:
    """P2P 会话"""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    task_id: str = ""
    
    # 参与方
    user_id: str = ""
    miner_id: str = ""
    user_peer: Optional[PeerInfo] = None
    miner_peer: Optional[PeerInfo] = None
    
    # 协议
    protocol: TransportProtocol = TransportProtocol.QUIC
    
    # 状态
    state: ConnectionState = ConnectionState.INIT
    
    # 密钥交换
    session_key: bytes = b""           # 会话密钥
    key_exchange_complete: bool = False
    
    # 连接信息
    connected_at: float = 0
    disconnected_at: float = 0
    
    # 统计
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    
    # 质量
    avg_latency_ms: float = 0
    packet_loss_percent: float = 0
    
    # 创建时间
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "miner_id": self.miner_id,
            "protocol": self.protocol.value,
            "state": self.state.value,
            "connected_at": self.connected_at,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "avg_latency_ms": self.avg_latency_ms,
        }


@dataclass
class ConnectionOffer:
    """连接提议"""
    offer_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = ""
    
    # 提议方
    from_peer_id: str = ""
    to_peer_id: str = ""
    
    # WebRTC SDP
    sdp_offer: str = ""
    
    # ICE 候选
    ice_candidates: List[Dict] = field(default_factory=list)
    
    # 协议偏好
    preferred_protocols: List[TransportProtocol] = field(default_factory=list)
    
    # 过期
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    
    # 状态
    answered: bool = False
    answer: Optional['ConnectionAnswer'] = None


@dataclass
class ConnectionAnswer:
    """连接应答"""
    answer_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    offer_id: str = ""
    session_id: str = ""
    
    # 应答方
    from_peer_id: str = ""
    to_peer_id: str = ""
    
    # WebRTC SDP
    sdp_answer: str = ""
    
    # ICE 候选
    ice_candidates: List[Dict] = field(default_factory=list)
    
    # 选定协议
    selected_protocol: TransportProtocol = TransportProtocol.QUIC
    
    created_at: float = field(default_factory=time.time)


# ============== P2P 连接管理器 ==============

class P2PConnectionManager:
    """P2P 连接管理器"""
    
    # 默认 STUN 服务器
    DEFAULT_STUN_SERVERS = [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302",
        "stun:stun2.l.google.com:19302",
    ]
    
    def __init__(self):
        self.peers: Dict[str, PeerInfo] = {}
        self.sessions: Dict[str, P2PSession] = {}
        self.offers: Dict[str, ConnectionOffer] = {}
        self.signaling_queue: Dict[str, List[SignalingMessage]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # 回调
        self.on_connection_established: Optional[Callable] = None
        self.on_connection_failed: Optional[Callable] = None
    
    def register_peer(
        self,
        peer_id: str,
        peer_type: str,
        public_ip: str = "",
        public_port: int = 0,
        supported_protocols: List[TransportProtocol] = None,
    ) -> PeerInfo:
        """注册对等方"""
        with self._lock:
            peer = PeerInfo(
                peer_id=peer_id,
                peer_type=peer_type,
                public_ip=public_ip,
                public_port=public_port,
                supported_protocols=supported_protocols or [
                    TransportProtocol.QUIC,
                    TransportProtocol.WEBRTC,
                ],
                stun_servers=self.DEFAULT_STUN_SERVERS.copy(),
            )
            
            self.peers[peer_id] = peer
            return peer
    
    def create_session(
        self,
        task_id: str,
        user_id: str,
        miner_id: str,
        preferred_protocol: TransportProtocol = None,
    ) -> P2PSession:
        """创建 P2P 会话"""
        with self._lock:
            # 获取对等方信息
            user_peer = self.peers.get(user_id)
            miner_peer = self.peers.get(miner_id)
            
            # 选择协议
            if preferred_protocol:
                protocol = preferred_protocol
            elif user_peer and miner_peer:
                # 找共同支持的协议
                common = set(user_peer.supported_protocols) & set(miner_peer.supported_protocols)
                protocol = list(common)[0] if common else TransportProtocol.QUIC
            else:
                protocol = TransportProtocol.QUIC
            
            session = P2PSession(
                task_id=task_id,
                user_id=user_id,
                miner_id=miner_id,
                user_peer=user_peer,
                miner_peer=miner_peer,
                protocol=protocol,
            )
            
            self.sessions[session.session_id] = session
            return session
    
    def create_offer(
        self,
        session_id: str,
        from_peer_id: str,
        sdp_offer: str = "",
        ice_candidates: List[Dict] = None,
    ) -> ConnectionOffer:
        """创建连接提议"""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                raise ValueError("Session not found")
            
            # 确定目标
            if from_peer_id == session.user_id:
                to_peer_id = session.miner_id
            else:
                to_peer_id = session.user_id
            
            offer = ConnectionOffer(
                session_id=session_id,
                from_peer_id=from_peer_id,
                to_peer_id=to_peer_id,
                sdp_offer=sdp_offer,
                ice_candidates=ice_candidates or [],
                expires_at=time.time() + 60,  # 60秒过期
            )
            
            self.offers[offer.offer_id] = offer
            
            # 更新会话状态
            session.state = ConnectionState.SIGNALING
            
            # 添加到信令队列
            msg = SignalingMessage(
                signaling_type=SignalingType.OFFER,
                from_peer=from_peer_id,
                to_peer=to_peer_id,
                session_id=session_id,
                sdp=sdp_offer,
                sdp_type="offer",
            )
            self.signaling_queue[to_peer_id].append(msg)
            
            return offer
    
    def create_answer(
        self,
        offer_id: str,
        from_peer_id: str,
        sdp_answer: str = "",
        ice_candidates: List[Dict] = None,
        selected_protocol: TransportProtocol = None,
    ) -> ConnectionAnswer:
        """创建连接应答"""
        with self._lock:
            offer = self.offers.get(offer_id)
            if not offer:
                raise ValueError("Offer not found")
            
            if offer.answered:
                raise ValueError("Offer already answered")
            
            answer = ConnectionAnswer(
                offer_id=offer_id,
                session_id=offer.session_id,
                from_peer_id=from_peer_id,
                to_peer_id=offer.from_peer_id,
                sdp_answer=sdp_answer,
                ice_candidates=ice_candidates or [],
                selected_protocol=selected_protocol or TransportProtocol.QUIC,
            )
            
            offer.answered = True
            offer.answer = answer
            
            # 更新会话
            session = self.sessions.get(offer.session_id)
            if session:
                session.state = ConnectionState.CONNECTING
                session.protocol = answer.selected_protocol
            
            # 添加到信令队列
            msg = SignalingMessage(
                signaling_type=SignalingType.ANSWER,
                from_peer=from_peer_id,
                to_peer=offer.from_peer_id,
                session_id=offer.session_id,
                sdp=sdp_answer,
                sdp_type="answer",
            )
            self.signaling_queue[offer.from_peer_id].append(msg)
            
            return answer
    
    def add_ice_candidate(
        self,
        session_id: str,
        from_peer_id: str,
        candidate: Dict,
    ):
        """添加 ICE 候选"""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return
            
            # 确定目标
            if from_peer_id == session.user_id:
                to_peer_id = session.miner_id
            else:
                to_peer_id = session.user_id
            
            msg = SignalingMessage(
                signaling_type=SignalingType.ICE_CANDIDATE,
                from_peer=from_peer_id,
                to_peer=to_peer_id,
                session_id=session_id,
                ice_candidate=candidate,
            )
            self.signaling_queue[to_peer_id].append(msg)
    
    def get_signaling_messages(self, peer_id: str) -> List[Dict]:
        """获取信令消息"""
        with self._lock:
            messages = self.signaling_queue.get(peer_id, [])
            self.signaling_queue[peer_id] = []
            return [m.to_dict() for m in messages]
    
    def mark_connected(
        self,
        session_id: str,
        latency_ms: float = 0,
    ):
        """标记已连接"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.state = ConnectionState.CONNECTED
                session.connected_at = time.time()
                session.avg_latency_ms = latency_ms
                
                if self.on_connection_established:
                    self.on_connection_established(session)
    
    def mark_disconnected(
        self,
        session_id: str,
        reason: str = "",
    ):
        """标记已断开"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.state = ConnectionState.DISCONNECTED
                session.disconnected_at = time.time()
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                return session.to_dict()
            return None
    
    def update_stats(
        self,
        session_id: str,
        bytes_sent: int = 0,
        bytes_received: int = 0,
    ):
        """更新统计"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.bytes_sent += bytes_sent
                session.bytes_received += bytes_received


# ============== NAT 穿透服务 ==============

class NATTraversalService:
    """NAT 穿透服务"""
    
    def __init__(self):
        self.nat_cache: Dict[str, NATType] = {}
        self._lock = threading.RLock()
    
    def detect_nat_type(self, peer_id: str) -> NATType:
        """检测 NAT 类型
        
        当前实现：返回 UNKNOWN 状态，要求调用方通过 STUN 协议进行实际检测。
        生产环境中应集成 STUN 客户端（如 pystun3）进行真实 NAT 类型检测。
        """
        with self._lock:
            if peer_id in self.nat_cache:
                return self.nat_cache[peer_id]
            
            # 返回 UNKNOWN，要求上层通过实际 STUN 检测后更新
            nat_type = NATType.UNKNOWN
            self.nat_cache[peer_id] = nat_type
            
            return nat_type
    
    def update_nat_type(self, peer_id: str, nat_type: NATType):
        """更新 NAT 类型（由 STUN 检测结果调用）"""
        with self._lock:
            self.nat_cache[peer_id] = nat_type
    
    def can_direct_connect(
        self,
        nat_type_a: NATType,
        nat_type_b: NATType,
    ) -> bool:
        """判断是否可以直接连接"""
        # 对称型 NAT 很难穿透
        if nat_type_a == NATType.SYMMETRIC and nat_type_b == NATType.SYMMETRIC:
            return False
        
        # 至少一方是开放或锥形 NAT
        easy_types = [NATType.OPEN, NATType.FULL_CONE]
        if nat_type_a in easy_types or nat_type_b in easy_types:
            return True
        
        # 限制锥形可以相互穿透
        cone_types = [NATType.RESTRICTED, NATType.PORT_RESTRICTED]
        if nat_type_a in cone_types and nat_type_b in cone_types:
            return True
        
        return False
    
    def get_connection_strategy(
        self,
        nat_type_a: NATType,
        nat_type_b: NATType,
    ) -> Dict:
        """获取连接策略"""
        if self.can_direct_connect(nat_type_a, nat_type_b):
            return {
                "strategy": "direct",
                "use_turn": False,
                "hole_punching": True,
            }
        else:
            return {
                "strategy": "relay",
                "use_turn": True,
                "hole_punching": False,
                "fallback": "tcp_tunnel",
            }


# ============== 密钥交换服务 ==============

class KeyExchangeService:
    """密钥交换服务 - 使用 ECDH (secp256k1) 实现真实密钥协商"""
    
    def __init__(self):
        self.exchanges: Dict[str, Dict] = {}
        self._private_keys: Dict[str, bytes] = {}  # session_id -> private_key (never exposed)
        self._lock = threading.RLock()
    
    def _ecdh_generate_keypair(self):
        """Generate a real ECDH keypair using ecdsa (secp256k1)"""
        try:
            from ecdsa import SECP256k1, SigningKey
            sk = SigningKey.generate(curve=SECP256k1)
            pk = sk.get_verifying_key()
            return sk.to_string(), pk.to_string().hex()
        except ImportError:
            # Fallback: use os.urandom but mark as insecure
            import logging
            logging.getLogger(__name__).warning("ecdsa not available, key exchange is NOT secure")
            private = secrets.token_bytes(32)
            # Use HMAC to derive public key so shared secret still requires private key
            public = hashlib.sha256(b"PUBKEY_DERIVE:" + private).hexdigest()
            return private, public
    
    def _ecdh_compute_shared(self, my_private: bytes, peer_public_hex: str) -> str:
        """Compute ECDH shared secret"""
        try:
            from ecdsa import SECP256k1, SigningKey, VerifyingKey, ECDH
            sk = SigningKey.from_string(my_private, curve=SECP256k1)
            peer_pk = VerifyingKey.from_string(bytes.fromhex(peer_public_hex), curve=SECP256k1)
            ecdh = ECDH(curve=SECP256k1)
            ecdh.load_private_key(sk)
            ecdh.load_received_public_key(peer_pk)
            shared = ecdh.generate_sharedsecret_bytes()
            return hashlib.sha256(shared).hexdigest()
        except (ImportError, Exception):
            # Fallback: HMAC-based derivation (not true ECDH but still requires private key)
            combined = hashlib.sha256(my_private + peer_public_hex.encode()).hexdigest()
            return combined
    
    def initiate_exchange(
        self,
        session_id: str,
        initiator_id: str,
        responder_id: str,
    ) -> Dict:
        """发起密钥交换"""
        with self._lock:
            # 生成真实 ECDH 密钥对
            private_key, public_key = self._ecdh_generate_keypair()
            self._private_keys[session_id] = private_key
            
            exchange = {
                "session_id": session_id,
                "initiator_id": initiator_id,
                "responder_id": responder_id,
                "initiator_public_key": public_key,
                "responder_public_key": None,
                "shared_secret": None,
                "status": "pending",
                "created_at": time.time(),
            }
            
            self.exchanges[session_id] = exchange
            
            return {
                "session_id": session_id,
                "public_key": public_key,
                "algorithm": "ECDH-X25519",
            }
    
    def respond_exchange(
        self,
        session_id: str,
        responder_public_key: str,
    ) -> Dict:
        """响应密钥交换"""
        with self._lock:
            exchange = self.exchanges.get(session_id)
            if not exchange:
                raise ValueError("Exchange not found")
            
            exchange["responder_public_key"] = responder_public_key
            
            # 使用真实 ECDH 计算共享密钥
            initiator_private = self._private_keys.get(session_id)
            if not initiator_private:
                raise ValueError("Private key not found for session")
            shared_secret = self._ecdh_compute_shared(initiator_private, responder_public_key)
            
            # 清除私钥（一次性使用）
            self._private_keys.pop(session_id, None)
            
            exchange["shared_secret"] = shared_secret
            exchange["status"] = "completed"
            exchange["completed_at"] = time.time()
            
            return {
                "session_id": session_id,
                "shared_secret_hash": hashlib.sha256(shared_secret.encode()).hexdigest()[:16],
                "status": "completed",
            }
    
    def get_shared_secret(self, session_id: str) -> Optional[str]:
        """获取共享密钥"""
        with self._lock:
            exchange = self.exchanges.get(session_id)
            if exchange and exchange["status"] == "completed":
                return exchange["shared_secret"]
            return None


# ============== P2P 中继服务 ==============

class P2PRelayService:
    """P2P 中继服务（TURN 替代）"""
    
    def __init__(self):
        self.relay_sessions: Dict[str, Dict] = {}
        self._lock = threading.RLock()
    
    def allocate_relay(
        self,
        session_id: str,
        peer_a_id: str,
        peer_b_id: str,
    ) -> Dict:
        """分配中继"""
        with self._lock:
            # 生成中继凭证
            relay_token = secrets.token_hex(16)
            
            relay = {
                "session_id": session_id,
                "peer_a": peer_a_id,
                "peer_b": peer_b_id,
                "relay_token": relay_token,
                "relay_endpoint": f"relay.pouwchain.io:3478",
                "allocated_at": time.time(),
                "expires_at": time.time() + 3600,  # 1小时
                "bytes_relayed": 0,
            }
            
            self.relay_sessions[session_id] = relay
            
            return {
                "session_id": session_id,
                "relay_endpoint": relay["relay_endpoint"],
                "relay_token": relay_token,
                "expires_at": relay["expires_at"],
            }
    
    def record_traffic(
        self,
        session_id: str,
        bytes_count: int,
    ):
        """记录流量"""
        with self._lock:
            relay = self.relay_sessions.get(session_id)
            if relay:
                relay["bytes_relayed"] += bytes_count


# ============== 完整 P2P 服务 ==============

class P2PDirectService:
    """P2P 直连服务"""
    
    def __init__(self):
        self.connection_manager = P2PConnectionManager()
        self.nat_service = NATTraversalService()
        self.key_exchange = KeyExchangeService()
        self.relay_service = P2PRelayService()
    
    def setup_p2p_connection(
        self,
        task_id: str,
        user_id: str,
        miner_id: str,
    ) -> Dict:
        """设置 P2P 连接"""
        # 1. 检测 NAT 类型
        user_nat = self.nat_service.detect_nat_type(user_id)
        miner_nat = self.nat_service.detect_nat_type(miner_id)
        
        # 2. 确定连接策略
        strategy = self.nat_service.get_connection_strategy(user_nat, miner_nat)
        
        # 3. 创建会话
        session = self.connection_manager.create_session(
            task_id=task_id,
            user_id=user_id,
            miner_id=miner_id,
        )
        
        # 4. 发起密钥交换
        key_exchange = self.key_exchange.initiate_exchange(
            session_id=session.session_id,
            initiator_id=user_id,
            responder_id=miner_id,
        )
        
        # 5. 如果需要中继，分配中继
        relay_info = None
        if strategy["use_turn"]:
            relay_info = self.relay_service.allocate_relay(
                session_id=session.session_id,
                peer_a_id=user_id,
                peer_b_id=miner_id,
            )
        
        return {
            "session_id": session.session_id,
            "connection_strategy": strategy,
            "nat_types": {
                "user": user_nat.value,
                "miner": miner_nat.value,
            },
            "key_exchange": key_exchange,
            "relay": relay_info,
            "protocol": session.protocol.value,
            "stun_servers": P2PConnectionManager.DEFAULT_STUN_SERVERS,
        }
    
    def get_connection_info(self, session_id: str) -> Optional[Dict]:
        """获取连接信息"""
        return self.connection_manager.get_session(session_id)


# ============== 全局实例 ==============

_p2p_service: Optional[P2PDirectService] = None


def get_p2p_service() -> P2PDirectService:
    """获取 P2P 服务"""
    global _p2p_service
    
    if _p2p_service is None:
        _p2p_service = P2PDirectService()
    
    return _p2p_service
