"""
e2e_encryption.py - 端到端加密层

为文件传输和任务数据提供端到端加密保护：
- 数据在客户端加密，只有持有密钥的接收方能解密
- 服务器全程不接触明文数据
- 基于 X25519 ECDH 密钥协商 + AES-256-GCM 对称加密

加密流程：
    1. 发送方生成临时 X25519 密钥对
    2. 用接收方公钥 + 自己私钥做 ECDH → 派生 AES-256 会话密钥
    3. 每个数据块用 AES-256-GCM 独立加密（每块独立 nonce）
    4. 接收方用自己的私钥 + 发送方公钥重建会话密钥解密

安全特性：
    - 前向保密：每次传输使用临时密钥对
    - 认证加密：GCM 模式提供完整性 + 机密性
    - 抗重放：每块独立 nonce + 序号绑定
    - 服务器零知识：服务器只转发密文，无法解密
"""

import os
import hashlib
import secrets
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from core.crypto_utils import aes_gcm_encrypt, aes_gcm_decrypt, sha256_hex

logger = logging.getLogger(__name__)

# ==================== ECDH 密钥交换 ====================

def generate_x25519_keypair() -> Tuple[bytes, bytes]:
    """生成 X25519 密钥对。
    
    Returns:
        (private_key_bytes, public_key_bytes)
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        sk = X25519PrivateKey.generate()
        pk = sk.public_key()
        return sk.private_bytes_raw(), pk.public_bytes_raw()
    except ImportError:
        pass
    
    try:
        from ecdsa import SECP256k1, SigningKey
        sk = SigningKey.generate(curve=SECP256k1)
        return sk.to_string(), sk.get_verifying_key().to_string()
    except ImportError:
        raise RuntimeError(
            "端到端加密需要 cryptography 或 ecdsa 库。"
            "请运行: pip install cryptography"
        )


def derive_shared_key(
    my_private: bytes,
    peer_public: bytes,
    context: bytes = b"e2e-file-transfer-v1",
) -> bytes:
    """ECDH 共享密钥派生 → 32 字节 AES-256 密钥。
    
    使用 HKDF-SHA256 从 ECDH 共享秘密派生对称密钥。
    context 参数绑定用途，防止跨协议密钥重用。
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey, X25519PublicKey,
        )
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes

        sk = X25519PrivateKey.from_private_bytes(my_private)
        pk = X25519PublicKey.from_public_bytes(peer_public)
        shared = sk.exchange(pk)

        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"maincoin-e2e-v1",
            info=context,
        ).derive(shared)
    except ImportError:
        pass

    try:
        from ecdsa import SECP256k1, SigningKey, VerifyingKey, ECDH as EcdhObj
        sk = SigningKey.from_string(my_private, curve=SECP256k1)
        ecdh = EcdhObj(curve=SECP256k1)
        ecdh.load_private_key(sk)
        vk = VerifyingKey.from_string(peer_public, curve=SECP256k1)
        shared = ecdh.generate_sharedsecret_bytes()
        # HKDF fallback: HMAC-based
        import hmac
        prk = hmac.new(b"maincoin-e2e-v1", shared, hashlib.sha256).digest()
        return hmac.new(prk, context + b"\x01", hashlib.sha256).digest()
    except ImportError:
        raise RuntimeError("需要 cryptography 或 ecdsa 库")


# ==================== E2E 加密/解密 ====================

# 加密块头格式: [4字节magic][4字节块序号][12字节nonce][16字节tag][密文...]
E2E_MAGIC = b'\xe2\xee\x01\x00'  # E2E v1
HEADER_SIZE = 4 + 4 + 12 + 16     # 36 字节头


def e2e_encrypt_chunk(
    plaintext: bytes,
    session_key: bytes,
    chunk_index: int,
) -> bytes:
    """端到端加密单个数据块。
    
    每块使用独立随机 nonce + 块序号绑定 AAD，防止重排序攻击。
    
    Args:
        plaintext: 明文数据
        session_key: 32 字节 AES-256 密钥
        chunk_index: 块序号（绑定到 AAD 防重排序）
    
    Returns:
        加密后的字节串 = magic(4) + index(4) + nonce(12) + tag(16) + ciphertext
    """
    nonce = os.urandom(12)
    
    # 块序号作为 AAD（Additional Authenticated Data），防止块被重排序
    aad = chunk_index.to_bytes(4, 'big')
    
    ciphertext, _, tag = _aes_gcm_encrypt_with_aad(plaintext, session_key, nonce, aad)
    
    # 组装: magic + index + nonce + tag + ciphertext
    header = E2E_MAGIC + aad + nonce + tag
    return header + ciphertext


def e2e_decrypt_chunk(
    encrypted_data: bytes,
    session_key: bytes,
    expected_index: int,
) -> bytes:
    """端到端解密单个数据块。
    
    Args:
        encrypted_data: e2e_encrypt_chunk 的输出
        session_key: 32 字节 AES-256 密钥
        expected_index: 期望的块序号（校验防重排序）
    
    Returns:
        解密后的明文
    
    Raises:
        ValueError: 格式错误、认证失败或块序号不匹配
    """
    if len(encrypted_data) < HEADER_SIZE:
        raise ValueError("E2E 加密数据太短")
    
    magic = encrypted_data[:4]
    if magic != E2E_MAGIC:
        raise ValueError("E2E 魔术字节不匹配（非 E2E 加密数据）")
    
    index_bytes = encrypted_data[4:8]
    actual_index = int.from_bytes(index_bytes, 'big')
    if actual_index != expected_index:
        raise ValueError(
            f"E2E 块序号不匹配: 期望 {expected_index}, 实际 {actual_index}（可能遭受重排序攻击）"
        )
    
    nonce = encrypted_data[8:20]
    tag = encrypted_data[20:36]
    ciphertext = encrypted_data[36:]
    
    aad = index_bytes  # 与加密时相同的 AAD
    return _aes_gcm_decrypt_with_aad(ciphertext, session_key, nonce, tag, aad)


# ==================== AAD 版 AES-GCM ====================

def _aes_gcm_encrypt_with_aad(
    plaintext: bytes,
    key: bytes,
    nonce: bytes,
    aad: bytes,
) -> Tuple[bytes, bytes, bytes]:
    """带 AAD 的 AES-256-GCM 加密。"""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        ct_with_tag = aesgcm.encrypt(nonce, plaintext, aad)
        ciphertext = ct_with_tag[:-16]
        tag = ct_with_tag[-16:]
        return ciphertext, nonce, tag
    except ImportError:
        pass
    
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(aad)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext, nonce, tag
    except ImportError:
        pass
    
    try:
        from Cryptodome.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(aad)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext, nonce, tag
    except ImportError:
        raise RuntimeError("No AES-GCM library available")


def _aes_gcm_decrypt_with_aad(
    ciphertext: bytes,
    key: bytes,
    nonce: bytes,
    tag: bytes,
    aad: bytes,
) -> bytes:
    """带 AAD 的 AES-256-GCM 解密。"""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        ct_with_tag = ciphertext + tag
        return aesgcm.decrypt(nonce, ct_with_tag, aad)
    except ImportError:
        pass
    
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(aad)
        return cipher.decrypt_and_verify(ciphertext, tag)
    except ImportError:
        pass
    
    try:
        from Cryptodome.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(aad)
        return cipher.decrypt_and_verify(ciphertext, tag)
    except ImportError:
        raise RuntimeError("No AES-GCM library available")


# ==================== E2E 会话管理 ====================

@dataclass
class E2ESession:
    """端到端加密会话。"""
    session_id: str
    my_private_key: bytes
    my_public_key: bytes
    peer_public_key: bytes = b""
    session_key: bytes = b""        # ECDH 派生的 AES-256 密钥
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0         # 会话过期时间
    role: str = "initiator"         # initiator 或 responder
    
    def derive_session_key(self, peer_public: bytes) -> bytes:
        """收到对方公钥后派生会话密钥。"""
        self.peer_public_key = peer_public
        self.session_key = derive_shared_key(self.my_private_key, peer_public)
        return self.session_key
    
    @property
    def is_ready(self) -> bool:
        return len(self.session_key) == 32
    
    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at


class E2ESessionManager:
    """E2E 会话管理器。
    
    管理端到端加密密钥协商会话的生命周期。
    每个文件传输（上传/下载）可以关联一个 E2E 会话。
    """
    
    SESSION_TTL = 3600  # 会话存活 1 小时
    MAX_SESSIONS = 1000  # 最多同时 1000 个会话
    
    def __init__(self):
        self._sessions: Dict[str, E2ESession] = {}
    
    def create_session(self, session_id: str = "") -> E2ESession:
        """创建新的 E2E 会话（生成密钥对）。
        
        Returns:
            E2ESession（my_public_key 可发送给对方）
        """
        self._cleanup_expired()
        
        if len(self._sessions) >= self.MAX_SESSIONS:
            raise RuntimeError("E2E 会话数量超过上限")
        
        if not session_id:
            session_id = secrets.token_hex(16)
        
        priv, pub = generate_x25519_keypair()
        
        session = E2ESession(
            session_id=session_id,
            my_private_key=priv,
            my_public_key=pub,
            created_at=time.time(),
            expires_at=time.time() + self.SESSION_TTL,
        )
        self._sessions[session_id] = session
        
        logger.info(f"E2E 会话已创建: {session_id}")
        return session
    
    def complete_handshake(self, session_id: str, peer_public_key: bytes) -> bytes:
        """完成密钥协商（收到对方公钥后派生会话密钥）。
        
        Returns:
            会话密钥（32 字节）
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"E2E 会话不存在: {session_id}")
        if session.is_expired:
            del self._sessions[session_id]
            raise ValueError(f"E2E 会话已过期: {session_id}")
        
        session.derive_session_key(peer_public_key)
        logger.info(f"E2E 密钥协商完成: {session_id}")
        return session.session_key
    
    def get_session(self, session_id: str) -> Optional[E2ESession]:
        """获取会话（不存在或过期返回 None）。"""
        session = self._sessions.get(session_id)
        if session and session.is_expired:
            del self._sessions[session_id]
            return None
        return session
    
    def remove_session(self, session_id: str):
        """销毁会话（传输完成后清理密钥材料）。"""
        session = self._sessions.pop(session_id, None)
        if session:
            # 尽量覆盖密钥材料（Python 不保证立即释放，但尽力而为）
            session.session_key = b'\x00' * 32
            session.my_private_key = b'\x00' * len(session.my_private_key)
    
    def _cleanup_expired(self):
        """清理过期会话。"""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if s.expires_at > 0 and now > s.expires_at
        ]
        for sid in expired:
            self.remove_session(sid)


# ==================== 便捷函数 ====================

def e2e_encrypt_data(data: bytes, recipient_public_key: bytes) -> Tuple[bytes, bytes]:
    """一次性端到端加密（适用于小数据）。
    
    生成临时密钥对 → ECDH → AES-GCM 加密。
    
    Args:
        data: 明文数据
        recipient_public_key: 接收方 X25519 公钥（32 字节）
    
    Returns:
        (encrypted_data, sender_public_key)
        接收方用 sender_public_key + 自己的私钥可解密
    """
    priv, pub = generate_x25519_keypair()
    session_key = derive_shared_key(priv, recipient_public_key)
    encrypted = e2e_encrypt_chunk(data, session_key, chunk_index=0)
    return encrypted, pub


def e2e_decrypt_data(
    encrypted_data: bytes,
    sender_public_key: bytes,
    my_private_key: bytes,
) -> bytes:
    """一次性端到端解密（适用于小数据）。
    
    Args:
        encrypted_data: e2e_encrypt_data 的输出
        sender_public_key: 发送方的临时公钥
        my_private_key: 接收方的 X25519 私钥
    
    Returns:
        解密后的明文
    """
    session_key = derive_shared_key(my_private_key, sender_public_key)
    return e2e_decrypt_chunk(encrypted_data, session_key, expected_index=0)
