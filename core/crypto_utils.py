"""
crypto_utils.py — 统一加密工具封装 (Single Crypto Library Wrapper)

M-10 修复: 系统中存在三套加密库（cryptography, PyCryptodome/Crypto, Cryptodome）。
此模块统一封装 AES-256-GCM 加密/解密、随机数生成等常用操作，
其他模块统一调用此封装，无需关心底层库。

优先使用 cryptography 库（更现代、维护更活跃）。
如果不可用，回退到 PyCryptodome。
"""

import os
import hashlib
import base64
from typing import Tuple


# 确定可用的底层库
_BACKEND = None

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _BACKEND = "cryptography"
except ImportError:
    pass

if _BACKEND is None:
    try:
        from Crypto.Cipher import AES as _AES_Crypto
        _BACKEND = "pycryptodome"
    except ImportError:
        try:
            from Cryptodome.Cipher import AES as _AES_Cryptodome
            _BACKEND = "cryptodome"
        except ImportError:
            pass


def get_backend() -> str:
    """返回当前使用的加密库名称。"""
    return _BACKEND or "none"


def aes_gcm_encrypt(plaintext: bytes, key: bytes, nonce: bytes = None) -> Tuple[bytes, bytes, bytes]:
    """AES-256-GCM 加密。
    
    Args:
        plaintext: 明文字节
        key: 32 字节密钥
        nonce: 12 字节 nonce（缺省自动生成）
    
    Returns:
        (ciphertext, nonce, tag) 元组
    
    Raises:
        RuntimeError: 无可用加密库
    """
    if nonce is None:
        nonce = os.urandom(12)
    
    if _BACKEND == "cryptography":
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        ct_with_tag = aesgcm.encrypt(nonce, plaintext, None)
        # cryptography 库将 tag 附加在密文末尾（最后 16 字节）
        ciphertext = ct_with_tag[:-16]
        tag = ct_with_tag[-16:]
        return ciphertext, nonce, tag
    
    elif _BACKEND == "pycryptodome":
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext, nonce, tag
    
    elif _BACKEND == "cryptodome":
        from Cryptodome.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return ciphertext, nonce, tag
    
    else:
        raise RuntimeError("No AES-GCM crypto library available. Install 'cryptography' or 'pycryptodome'.")


def aes_gcm_decrypt(ciphertext: bytes, key: bytes, nonce: bytes, tag: bytes) -> bytes:
    """AES-256-GCM 解密。
    
    Args:
        ciphertext: 密文字节
        key: 32 字节密钥
        nonce: 12 字节 nonce
        tag: 16 字节认证标签
    
    Returns:
        明文字节
    
    Raises:
        ValueError: MAC 验证失败（密码错误或数据损坏）
        RuntimeError: 无可用加密库
    """
    if _BACKEND == "cryptography":
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        ct_with_tag = ciphertext + tag
        return aesgcm.decrypt(nonce, ct_with_tag, None)
    
    elif _BACKEND == "pycryptodome":
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
    
    elif _BACKEND == "cryptodome":
        from Cryptodome.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
    
    else:
        raise RuntimeError("No AES-GCM crypto library available.")


def derive_key_pbkdf2(password: str, salt: bytes, iterations: int = 310000, dklen: int = 32) -> bytes:
    """PBKDF2-SHA256 密钥派生。"""
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, dklen=dklen)


def random_bytes(n: int) -> bytes:
    """生成 n 字节密码学安全随机数。"""
    return os.urandom(n)


def sha256(data: bytes) -> bytes:
    """SHA-256 哈希。"""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    """SHA-256 哈希（hex 字符串）。"""
    return hashlib.sha256(data).hexdigest()
