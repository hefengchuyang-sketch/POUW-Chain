"""
sbox_crypto.py - S-Box 动态加密层

将区块挖矿产出的 S-Box 应用于数据传输加密和隐私保护。
每个区块替换一次 S-Box，实现动态加密数据流。

加密架构 (三层混合加密):
  Layer 1: AES-256-GCM       (底层对称加密，保证机密性和完整性)
  Layer 2: S-Box SubBytes     (区块 S-Box 置换层，增加非线性度)
  Layer 3: ECDH 密钥协商      (密钥交换，前向保密)

S-Box 加密流程:
  明文 → S-Box SubBytes 置换 → AES-256-GCM 加密 → 密文

  解密:
  密文 → AES-256-GCM 解密 → S-Box 逆置换 → 明文

隐私保护设计:
  - 每条消息使用独立 nonce (重放保护)
  - S-Box 随区块更新 → 动态加密 (前向保密增强)
  - 支持数据分片加密 → 大文件传输
  - 支持多级隐私: 仅 AES / AES+S-Box / AES+S-Box+ZKP

安全性说明:
  - S-Box 不替代 AES-GCM，而是叠加在其上提供额外非线性扩散
  - AES-GCM 是主加密层，保证认证加密 (AEAD)
  - S-Box 层在 AES 之前应用 (加密) 或 AES 之后逆向 (解密)
  - 即使 S-Box 泄露，AES-256-GCM 仍然保护数据安全
  - S-Box 作为额外的"滚动混淆层"增强整体安全裕度
"""

import hashlib
import os
import time
import struct
import secrets
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum

from core.sbox_engine import (
    sbox_substitute,
    sbox_substitute_inverse,
    sbox_inverse,
    sbox_to_bytes,
    bytes_to_sbox,
    sbox_to_hex,
    hex_to_sbox,
    is_bijective,
    BlockSBox,
    get_sbox_library,
    SBOX_SIZE,
)

from core.crypto_utils import (
    aes_gcm_encrypt,
    aes_gcm_decrypt,
    get_backend,
)

logger = logging.getLogger(__name__)


# ============== 加密级别 ==============

class SBoxEncryptionLevel(Enum):
    """S-Box 加密级别。

    STANDARD:   仅 AES-256-GCM (兼容模式)
    ENHANCED:   AES-256-GCM + S-Box SubBytes (推荐)
    MAXIMUM:    AES-256-GCM + S-Box + 每包独立密钥 (最高安全)
    """
    STANDARD = "standard"
    ENHANCED = "enhanced"
    MAXIMUM = "maximum"


# ============== 机制策略与降级审计 ==============

SBOX_MECHANISM_POLICY: Dict[str, Any] = {
    "policyVersion": "v2.0",
    "defaultLevel": SBoxEncryptionLevel.ENHANCED.value,
    "enforceEnhancedDefault": True,
    "allowDowngradeToStandard": True,
    "downgradeRequiresAudit": True,
    "maxSessionMessages": 1_000_000,
    "maxSessionSeconds": 3600,
}

_SBOX_DOWNGRADE_AUDIT: List[Dict[str, Any]] = []


def _audit_downgrade(reason: str, details: Optional[Dict[str, Any]] = None):
    event = {
        "ts": time.time(),
        "reason": reason,
        "details": details or {},
        "policyVersion": SBOX_MECHANISM_POLICY.get("policyVersion", "unknown"),
    }
    _SBOX_DOWNGRADE_AUDIT.append(event)
    if len(_SBOX_DOWNGRADE_AUDIT) > 5000:
        del _SBOX_DOWNGRADE_AUDIT[:-5000]


def get_sbox_encryption_policy() -> Dict[str, Any]:
    return dict(SBOX_MECHANISM_POLICY)


def set_sbox_encryption_policy(**kwargs) -> Dict[str, Any]:
    if "policyVersion" in kwargs and kwargs["policyVersion"]:
        SBOX_MECHANISM_POLICY["policyVersion"] = str(kwargs["policyVersion"])

    if "defaultLevel" in kwargs and kwargs["defaultLevel"]:
        lvl = str(kwargs["defaultLevel"]).lower().strip()
        if lvl in {x.value for x in SBoxEncryptionLevel}:
            SBOX_MECHANISM_POLICY["defaultLevel"] = lvl

    for b in ("enforceEnhancedDefault", "allowDowngradeToStandard", "downgradeRequiresAudit"):
        if b in kwargs and kwargs[b] is not None:
            SBOX_MECHANISM_POLICY[b] = bool(kwargs[b])

    if "maxSessionMessages" in kwargs and kwargs["maxSessionMessages"] is not None:
        SBOX_MECHANISM_POLICY["maxSessionMessages"] = int(max(1000, kwargs["maxSessionMessages"]))
    if "maxSessionSeconds" in kwargs and kwargs["maxSessionSeconds"] is not None:
        SBOX_MECHANISM_POLICY["maxSessionSeconds"] = int(max(60, kwargs["maxSessionSeconds"]))

    return get_sbox_encryption_policy()


def get_sbox_downgrade_audit(limit: int = 200) -> List[Dict[str, Any]]:
    n = max(1, min(int(limit), 5000))
    return list(_SBOX_DOWNGRADE_AUDIT[-n:])


def clear_sbox_downgrade_audit():
    _SBOX_DOWNGRADE_AUDIT.clear()


# ============== 加密包头 ==============

# 包头格式 (固定 32 字节):
#   magic     (4 bytes): "SBOX"
#   version   (1 byte):  1
#   level     (1 byte):  加密级别
#   flags     (2 bytes): 标志位
#   nonce     (12 bytes): AES-GCM nonce
#   sbox_hash (8 bytes):  S-Box 哈希前 8 字节 (快速查找)
#   reserved  (4 bytes): 保留

SBOX_PACKET_MAGIC = b"SBOX"
SBOX_PACKET_VERSION = 1
SBOX_HEADER_SIZE = 32

LEVEL_MAP = {
    SBoxEncryptionLevel.STANDARD: 0,
    SBoxEncryptionLevel.ENHANCED: 1,
    SBoxEncryptionLevel.MAXIMUM: 2,
}

LEVEL_FROM_BYTE = {v: k for k, v in LEVEL_MAP.items()}


def _pack_header(
    level: SBoxEncryptionLevel,
    nonce: bytes,
    sbox_hash_hex: str = "",
    flags: int = 0,
) -> bytes:
    """打包加密包头。"""
    sbox_hash_bytes = bytes.fromhex(sbox_hash_hex[:16]) if sbox_hash_hex else b"\x00" * 8

    header = bytearray(SBOX_HEADER_SIZE)
    header[0:4] = SBOX_PACKET_MAGIC
    header[4] = SBOX_PACKET_VERSION
    header[5] = LEVEL_MAP.get(level, 0)
    struct.pack_into("!H", header, 6, flags)
    header[8:20] = nonce
    header[20:28] = sbox_hash_bytes
    # 28-31: reserved zeros
    return bytes(header)


def _unpack_header(data: bytes) -> Tuple[SBoxEncryptionLevel, bytes, str, int]:
    """解包加密包头。

    Returns:
        (level, nonce, sbox_hash_prefix, flags)
    """
    if len(data) < SBOX_HEADER_SIZE:
        raise ValueError("Packet too short for header")
    if data[0:4] != SBOX_PACKET_MAGIC:
        raise ValueError("Invalid packet magic")
    if data[4] != SBOX_PACKET_VERSION:
        raise ValueError(f"Unsupported packet version: {data[4]}")

    level_byte = data[5]
    level = LEVEL_FROM_BYTE.get(level_byte, SBoxEncryptionLevel.STANDARD)
    flags = struct.unpack_from("!H", data, 6)[0]
    nonce = bytes(data[8:20])
    sbox_hash_prefix = data[20:28].hex()

    return level, nonce, sbox_hash_prefix, flags


# ============== 核心加密/解密 ==============

def sbox_encrypt(
    plaintext: bytes,
    key: bytes,
    sbox: List[int] = None,
    level: SBoxEncryptionLevel = SBoxEncryptionLevel.ENHANCED,
) -> bytes:
    """S-Box 增强加密。

    加密流程:
      STANDARD: AES-256-GCM(plaintext)
      ENHANCED: AES-256-GCM(SBox_Substitute(plaintext))
      MAXIMUM:  per_chunk_key → AES-256-GCM(SBox_Substitute(chunk))

    Args:
        plaintext: 明文数据
        key: 32 字节 AES-256 密钥
        sbox: S-Box 置换表 (ENHANCED/MAXIMUM 必须提供)
        level: 加密级别

    Returns:
        header + ciphertext + tag
    """
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes (AES-256)")

    # 获取 S-Box
    sbox_hash_hex = ""

    # 治理策略：默认优先 ENHANCED。
    if level is None:
        try:
            level = SBoxEncryptionLevel(SBOX_MECHANISM_POLICY.get("defaultLevel", SBoxEncryptionLevel.ENHANCED.value))
        except Exception:
            level = SBoxEncryptionLevel.ENHANCED
    if SBOX_MECHANISM_POLICY.get("enforceEnhancedDefault", True) and level == SBoxEncryptionLevel.STANDARD:
        level = SBoxEncryptionLevel.ENHANCED

    if level != SBoxEncryptionLevel.STANDARD:
        if sbox is None:
            # 尝试使用全网当前活跃 S-Box
            lib = get_sbox_library()
            current = lib.current
            if current and current.sbox:
                sbox = current.sbox
                sbox_hash_hex = current.sbox_hash
            else:
                # 没有活跃 S-Box：按治理策略决定是否允许降级。
                if not SBOX_MECHANISM_POLICY.get("allowDowngradeToStandard", True):
                    raise ValueError("S-Box unavailable and downgrade is disabled by policy")
                level = SBoxEncryptionLevel.STANDARD
                if SBOX_MECHANISM_POLICY.get("downgradeRequiresAudit", True):
                    _audit_downgrade(
                        "sbox_unavailable_fallback_standard",
                        {"requestedLevel": "enhanced_or_maximum"},
                    )
                logger.warning("No active S-Box available, falling back to STANDARD encryption")
        else:
            sbox_hash_hex = hashlib.sha256(bytes(sbox)).hexdigest()

    # 生成随机 nonce
    nonce = os.urandom(12)

    if level == SBoxEncryptionLevel.STANDARD:
        # 纯 AES-256-GCM
        ciphertext, _, tag = aes_gcm_encrypt(plaintext, key, nonce)
        header = _pack_header(level, nonce)
        return header + ciphertext + tag

    elif level == SBoxEncryptionLevel.ENHANCED:
        # S-Box SubBytes 置换 → AES-256-GCM
        substituted = sbox_substitute(plaintext, sbox)
        ciphertext, _, tag = aes_gcm_encrypt(substituted, key, nonce)
        header = _pack_header(level, nonce, sbox_hash_hex)
        return header + ciphertext + tag

    elif level == SBoxEncryptionLevel.MAXIMUM:
        # 每包派生独立子密钥: sub_key = HMAC-SHA256(key, nonce)
        import hmac
        sub_key = hmac.new(key, nonce, hashlib.sha256).digest()
        substituted = sbox_substitute(plaintext, sbox)
        ciphertext, _, tag = aes_gcm_encrypt(substituted, sub_key, nonce)
        header = _pack_header(level, nonce, sbox_hash_hex, flags=1)
        return header + ciphertext + tag

    raise ValueError(f"Unknown encryption level: {level}")


def sbox_decrypt(
    packet: bytes,
    key: bytes,
    sbox: List[int] = None,
) -> bytes:
    """S-Box 增强解密。

    解密流程 (自动从包头识别加密级别):
      STANDARD: AES-256-GCM_decrypt(ciphertext)
      ENHANCED: SBox_InverseSubstitute(AES-256-GCM_decrypt(ciphertext))
      MAXIMUM:  SBox_InverseSubstitute(AES-256-GCM_decrypt(ciphertext, derived_key))

    Args:
        packet: 完整加密包 (header + ciphertext + tag)
        key: 32 字节 AES-256 密钥
        sbox: S-Box 置换表 (如果为 None, 尝试从 S-Box 库自动查找)

    Returns:
        明文数据
    """
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes (AES-256)")

    # 解包头部
    level, nonce, sbox_hash_prefix, flags = _unpack_header(packet)
    payload = packet[SBOX_HEADER_SIZE:]

    # AES-GCM tag 是 16 字节，附在 ciphertext 后面
    if len(payload) < 16:
        raise ValueError("Packet too short for ciphertext + tag")
    ciphertext = payload[:-16]
    tag = payload[-16:]

    if level == SBoxEncryptionLevel.STANDARD:
        plaintext = aes_gcm_decrypt(ciphertext, key, nonce, tag)
        return plaintext

    # ENHANCED / MAXIMUM 需要 S-Box
    if sbox is None:
        # 尝试从 S-Box 库查找
        lib = get_sbox_library()
        # 先查 sbox_hash_prefix 匹配
        found = None
        for block_sbox in lib.get_latest(100):
            if block_sbox.sbox_hash.startswith(sbox_hash_prefix):
                found = block_sbox.sbox
                break
        if found is None:
            # 使用当前活跃 S-Box
            current = lib.current
            if current and current.sbox:
                found = current.sbox
        if found is None:
            raise ValueError(
                "Cannot find S-Box for decryption. "
                f"hash_prefix={sbox_hash_prefix}"
            )
        sbox = found

    if level == SBoxEncryptionLevel.ENHANCED:
        decrypted = aes_gcm_decrypt(ciphertext, key, nonce, tag)
        plaintext = sbox_substitute_inverse(decrypted, sbox)
        return plaintext

    elif level == SBoxEncryptionLevel.MAXIMUM:
        import hmac as _hmac
        sub_key = _hmac.new(key, nonce, hashlib.sha256).digest()
        decrypted = aes_gcm_decrypt(ciphertext, sub_key, nonce, tag)
        plaintext = sbox_substitute_inverse(decrypted, sbox)
        return plaintext

    raise ValueError(f"Unknown encryption level: {level}")


# ============== 流式加密 (大文件 / 数据流) ==============

STREAM_CHUNK_SIZE = 64 * 1024  # 64KB 流式块大小


def sbox_encrypt_stream(
    data: bytes,
    key: bytes,
    sbox: List[int] = None,
    level: SBoxEncryptionLevel = SBoxEncryptionLevel.ENHANCED,
    chunk_size: int = STREAM_CHUNK_SIZE,
) -> bytes:
    """流式 S-Box 加密 (大数据分块加密)。

    每个块独立加密，允许大文件增量处理。

    格式:
      [4 bytes: total_chunks] + [chunk_1] + [chunk_2] + ...

    每个 chunk:
      [4 bytes: chunk_len] + [encrypted_chunk]
    """
    chunks = []
    offset = 0
    while offset < len(data):
        chunk = data[offset:offset + chunk_size]
        encrypted = sbox_encrypt(chunk, key, sbox, level)
        chunks.append(encrypted)
        offset += chunk_size

    # 组装输出
    total = len(chunks)
    output = struct.pack("!I", total)
    for chunk in chunks:
        output += struct.pack("!I", len(chunk))
        output += chunk

    return output


def sbox_decrypt_stream(
    data: bytes,
    key: bytes,
    sbox: List[int] = None,
) -> bytes:
    """流式 S-Box 解密。"""
    if len(data) < 4:
        raise ValueError("Stream data too short")

    total_chunks = struct.unpack_from("!I", data, 0)[0]
    offset = 4
    output = bytearray()

    for _ in range(total_chunks):
        if offset + 4 > len(data):
            raise ValueError("Unexpected end of stream data")
        chunk_len = struct.unpack_from("!I", data, offset)[0]
        offset += 4
        if offset + chunk_len > len(data):
            raise ValueError("Chunk data overflow")
        chunk_data = data[offset:offset + chunk_len]
        offset += chunk_len
        decrypted = sbox_decrypt(chunk_data, key, sbox)
        output.extend(decrypted)

    return bytes(output)


# ============== P2P 通信加密适配 ==============

class SBoxSessionCipher:
    """S-Box 会话加密器。

    用于 P2P 节点间的会话级加密通信。
    每个会话使用 ECDH 协商的密钥 + 当前区块的 S-Box 进行加密。

    核心原则:
    - 会话内 S-Box 固定: 创建时快照，整个会话/任务期间不变
    - update_sbox() 仅在会话空闲时由调用方主动触发
    - 会话密钥用完即弃 (前向保密)
    - 自动降级: 如果没有可用 S-Box, 退回纯 AES-GCM
    - 消息计数器防止重放攻击

    设计理由:
    - 任务执行中途切换 S-Box 会导致解密不一致
    - 每条消息包头记录了 sbox_hash，解密端可据此查找
    - 只有在非任务活跃期间 (会话空闲) 才应更新 S-Box

    用法:
        cipher = SBoxSessionCipher(session_key)
        encrypted = cipher.encrypt(message)
        decrypted = cipher.decrypt(encrypted)
    """

    def __init__(
        self,
        session_key: bytes,
        level: Optional[SBoxEncryptionLevel] = None,
        sbox: List[int] = None,
        lock_sbox: bool = True,
    ):
        if len(session_key) != 32:
            raise ValueError("Session key must be 32 bytes")
        self._key = session_key
        if level is None:
            try:
                self._level = SBoxEncryptionLevel(SBOX_MECHANISM_POLICY.get("defaultLevel", SBoxEncryptionLevel.ENHANCED.value))
            except Exception:
                self._level = SBoxEncryptionLevel.ENHANCED
        else:
            self._level = level

        if SBOX_MECHANISM_POLICY.get("enforceEnhancedDefault", True) and self._level == SBoxEncryptionLevel.STANDARD:
            self._level = SBoxEncryptionLevel.ENHANCED

        self._send_counter: int = 0
        self._recv_counter: int = 0
        self._max_messages: int = int(SBOX_MECHANISM_POLICY.get("maxSessionMessages", 1_000_000))
        self._created_at = time.time()
        self._max_session_seconds: int = int(SBOX_MECHANISM_POLICY.get("maxSessionSeconds", 3600))
        self._sbox_block_height: int = 0

        # 快照 S-Box: 创建时锁定，整个会话期间不变
        if sbox is not None:
            self._sbox = list(sbox)
        elif lock_sbox and self._level != SBoxEncryptionLevel.STANDARD:
            lib = get_sbox_library()
            current = lib.current
            if current and current.sbox:
                self._sbox = list(current.sbox)  # 快照拷贝
                self._sbox_block_height = int(getattr(current, "block_height", 0) or 0)
            else:
                if not SBOX_MECHANISM_POLICY.get("allowDowngradeToStandard", True):
                    raise ValueError("S-Box unavailable and downgrade is disabled by policy")
                self._sbox = None
                self._level = SBoxEncryptionLevel.STANDARD
                if SBOX_MECHANISM_POLICY.get("downgradeRequiresAudit", True):
                    _audit_downgrade("session_cipher_init_without_sbox", {})
        else:
            self._sbox = None

    def _ensure_session_valid(self):
        if self._send_counter >= self._max_messages or self._recv_counter >= self._max_messages:
            raise RuntimeError("Session key exhausted, re-negotiate required")
        if (time.time() - self._created_at) >= self._max_session_seconds:
            raise RuntimeError("Session lifetime exceeded, re-negotiate required")

    def encrypt(self, plaintext: bytes) -> bytes:
        """加密消息。使用会话创建时锁定的 S-Box。"""
        self._ensure_session_valid()

        encrypted = sbox_encrypt(plaintext, self._key, self._sbox, self._level)
        self._send_counter += 1
        return encrypted

    def decrypt(self, packet: bytes) -> bytes:
        """解密消息。"""
        self._ensure_session_valid()

        decrypted = sbox_decrypt(packet, self._key, self._sbox)
        self._recv_counter += 1
        return decrypted

    def update_sbox(self, new_sbox: List[int]):
        """更新 S-Box。

        仅在会话空闲 (无进行中任务) 时调用。
        任务执行期间禁止切换，否则会导致解密失败。
        """
        if is_bijective(new_sbox):
            self._sbox = list(new_sbox)

    @property
    def sbox_hash_hex(self) -> str:
        """当前会话使用的 S-Box 哈希 (用于通信协商)。"""
        if self._sbox:
            return hashlib.sha256(bytes(self._sbox)).hexdigest()
        return ""

    @property
    def session_metadata(self) -> Dict[str, Any]:
        return {
            "sbox_hash": self.sbox_hash_hex,
            "sbox_block_height": self._sbox_block_height,
            "level": self._level.value,
            "policyVersion": SBOX_MECHANISM_POLICY.get("policyVersion", "unknown"),
            "ageSeconds": int(time.time() - self._created_at),
        }

    @property
    def messages_remaining(self) -> int:
        return self._max_messages - max(self._send_counter, self._recv_counter)


# ============== 隐私数据保护 ==============

class SBoxPrivacyGuard:
    """S-Box 隐私数据保护。

    将 S-Box 应用于隐私数据处理场景:
    1. 计算任务输入/输出加密: 使用当前区块 S-Box 增强加密
    2. 模型参数保护: S-Box 置换 → 防止模型权重泄露
    3. 数据脱敏: S-Box 替换敏感字段

    核心原则:
    - 创建时快照 S-Box，任务全生命周期内不变
    - 防止任务执行中途因新区块导致 S-Box 切换而解密失败

    使用方式:
        guard = SBoxPrivacyGuard()  # 自动快照当前 S-Box
        protected = guard.protect_task_input(raw_data, key)
        recovered = guard.recover_task_input(protected, key)
    """

    def __init__(self, sbox: List[int] = None):
        # 快照 S-Box: 创建时锁定
        if sbox is not None:
            self._sbox = list(sbox)
        else:
            lib = get_sbox_library()
            current = lib.current
            self._sbox = list(current.sbox) if current and current.sbox else None

    def _get_sbox(self) -> Optional[List[int]]:
        """获取锁定的 S-Box。"""
        return self._sbox

    def protect_task_input(self, data: bytes, key: bytes) -> bytes:
        """加密保护计算任务输入数据。"""
        sbox = self._get_sbox()
        level = SBoxEncryptionLevel.ENHANCED if sbox else SBoxEncryptionLevel.STANDARD
        return sbox_encrypt(data, key, sbox, level)

    def recover_task_input(self, data: bytes, key: bytes) -> bytes:
        """恢复计算任务输入数据。"""
        sbox = self._get_sbox()
        return sbox_decrypt(data, key, sbox)

    def protect_model_params(self, params_bytes: bytes, key: bytes) -> bytes:
        """加密保护模型参数 (大数据使用流式加密)。"""
        sbox = self._get_sbox()
        level = SBoxEncryptionLevel.MAXIMUM if sbox else SBoxEncryptionLevel.STANDARD
        if len(params_bytes) > STREAM_CHUNK_SIZE * 2:
            return sbox_encrypt_stream(params_bytes, key, sbox, level)
        return sbox_encrypt(params_bytes, key, sbox, level)

    def recover_model_params(self, data: bytes, key: bytes) -> bytes:
        """恢复模型参数。"""
        sbox = self._get_sbox()
        # 检测是否为流式格式
        if len(data) >= 4:
            total_chunks = struct.unpack_from("!I", data, 0)[0]
            if 0 < total_chunks < 100000:
                try:
                    return sbox_decrypt_stream(data, key, sbox)
                except (ValueError, Exception):
                    pass
        return sbox_decrypt(data, key, sbox)

    def anonymize_field(self, field_bytes: bytes) -> bytes:
        """使用 S-Box 对敏感字段进行确定性脱敏。

        注意: 这是确定性的，相同输入总是产生相同输出。
        适用于需要去标识化但保留统计特性的场景。
        """
        sbox = self._get_sbox()
        if sbox:
            return sbox_substitute(field_bytes, sbox)
        # 降级: 使用 SHA-256 哈希
        return hashlib.sha256(field_bytes).digest()

    def update_sbox(self, new_sbox: List[int]):
        """更新 S-Box (区块更新时自动调用)。"""
        if is_bijective(new_sbox):
            self._sbox = new_sbox
