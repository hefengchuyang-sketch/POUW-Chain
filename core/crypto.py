"""
Crypto 模块 - 真正的加密实现

使用生产级加密库：
- ECDSA secp256k1 签名（与 BTC/ETH 相同）
- BIP39 助记词（标准 2048 词表）
- AES-256-GCM 钱包加密
- SHA-256, RIPEMD-160 哈希
"""

import os
import hashlib
import hmac
import base64
import secrets
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass, field

# 尝试导入生产级加密库
try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
    from ecdsa.util import sigencode_der, sigdecode_der
    HAS_ECDSA = True
except ImportError:
    HAS_ECDSA = False
    import os
    # 生产环境必须有 ecdsa 库
    if os.environ.get('MAINCOIN_PRODUCTION', '').lower() == 'true':
        raise ImportError("[ERROR] Production mode requires ecdsa: pip install ecdsa")
    print("[WARN] ecdsa not installed, using simulated signatures (test only)")

try:
    from mnemonic import Mnemonic
    HAS_MNEMONIC = True
except ImportError:
    HAS_MNEMONIC = False
    print("[WARN] mnemonic not installed, using simplified word list")

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    import logging
    logging.getLogger('crypto').warning(
        "cryptography 库未安装，加密功能不可用。生产环境请安装: pip install cryptography"
    )


def check_crypto_requirements():
    """启动时检查加密库是否可用。生产环境缺少任何库则拒绝启动。"""
    import os
    is_prod = os.environ.get('MAINCOIN_PRODUCTION', '').lower() == 'true'
    missing = []
    if not HAS_ECDSA:
        missing.append("ecdsa")
    if not HAS_CRYPTOGRAPHY:
        missing.append("cryptography")
    if not HAS_MNEMONIC:
        missing.append("mnemonic")
    
    if missing and is_prod:
        raise RuntimeError(
            f"[SECURITY] 生产环境缺少加密库: {', '.join(missing)}。"
            f"请安装: pip install {' '.join(missing)}"
        )
    elif missing:
        import logging
        logging.getLogger('crypto').warning(
            f"缺少加密库: {', '.join(missing)}。仅限测试环境使用。"
        )


# ============== BIP39 助记词 ==============

# 模块级 logger
import logging
logger = logging.getLogger(__name__)


class BIP39:
    """BIP39 助记词生成器。"""
    
    def __init__(self, language: str = "english"):
        self.language = language
        
        if HAS_MNEMONIC:
            self.mnemo = Mnemonic(language)
        else:
            self.mnemo = None
            logger.warning("mnemonic 库未安装，BIP39 助记词功能不可用")
    
    def generate(self, strength: int = 128) -> str:
        """生成助记词。
        
        Args:
            strength: 128 = 12词, 160 = 15词, 192 = 18词, 224 = 21词, 256 = 24词
        
        Returns:
            空格分隔的助记词
        """
        if self.mnemo:
            return self.mnemo.generate(strength)
        else:
            raise RuntimeError(
                "mnemonic 库未安装，无法生成 BIP39 助记词。"
                "请运行: pip install mnemonic"
            )
    
    def to_seed(self, mnemonic: str, passphrase: str = "") -> bytes:
        """将助记词转换为种子。"""
        if self.mnemo:
            return self.mnemo.to_seed(mnemonic, passphrase)
        else:
            raise RuntimeError(
                "mnemonic 库未安装，无法从助记词派生种子。"
                "请运行: pip install mnemonic"
            )
    
    def validate(self, mnemonic: str) -> bool:
        """验证助记词有效性。"""
        if self.mnemo:
            return self.mnemo.check(mnemonic)
        else:
            raise RuntimeError(
                "mnemonic 库未安装，无法验证助记词。"
                "请运行: pip install mnemonic"
            )


# ============== ECDSA 签名 ==============

@dataclass
class ECKeyPair:
    """椭圆曲线密钥对。"""
    private_key: bytes
    public_key: bytes
    private_key_hex: str = ""
    public_key_hex: str = ""
    address: str = ""
    
    def __post_init__(self):
        if not self.private_key_hex:
            self.private_key_hex = self.private_key.hex()
        if not self.public_key_hex:
            self.public_key_hex = self.public_key.hex()


class ECDSASigner:
    """ECDSA secp256k1 签名器（与 BTC/ETH 相同曲线）。"""
    
    @staticmethod
    def generate_keypair() -> ECKeyPair:
        """生成新密钥对。"""
        if HAS_ECDSA:
            sk = SigningKey.generate(curve=SECP256k1)
            vk = sk.get_verifying_key()
            
            return ECKeyPair(
                private_key=sk.to_string(),
                public_key=vk.to_string(),
            )
        else:
            raise RuntimeError(
                "[SECURITY] ecdsa 库缺失，无法生成密钥对。"
                "请安装: pip install ecdsa"
            )
    
    @staticmethod
    def from_seed(seed: bytes) -> ECKeyPair:
        """从种子派生密钥对。"""
        # BIP32 简化版本
        # 使用 HMAC-SHA512 派生
        key_material = hmac.new(
            b"Bitcoin seed",  # BIP32 标准
            seed,
            hashlib.sha512
        ).digest()
        
        private_key = key_material[:32]
        
        if HAS_ECDSA:
            sk = SigningKey.from_string(private_key, curve=SECP256k1)
            vk = sk.get_verifying_key()
            
            return ECKeyPair(
                private_key=sk.to_string(),
                public_key=vk.to_string(),
            )
        else:
            raise RuntimeError(
                "[SECURITY] ecdsa 库缺失，无法从种子派生密钥。"
                "请安装: pip install ecdsa"
            )
    
    @staticmethod
    def sign(private_key: bytes, message: bytes) -> bytes:
        """签名消息。
        
        安全加固：移除 HMAC 模拟签名回退路径。
        Security: No fallback — real ECDSA required.
        """
        if HAS_ECDSA:
            sk = SigningKey.from_string(private_key, curve=SECP256k1)
            signature = sk.sign(message, sigencode=sigencode_der)
            return signature
        else:
            raise RuntimeError(
                "[SECURITY] ecdsa 库缺失，无法执行签名操作。"
                "请安装: pip install ecdsa\n"
                "Security: ECDSA library required for signing, no HMAC fallback."
            )
    
    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """验证签名。
        
        安全加固：移除 HMAC 模拟验证回退路径。
        HMAC 用公钥做密钥，公钥是公开信息，任何人可伪造签名。
        Security: No HMAC fallback — HMAC(public_key, msg) is trivially forgeable.
        """
        if HAS_ECDSA:
            try:
                vk = VerifyingKey.from_string(public_key, curve=SECP256k1)
                return vk.verify(signature, message, sigdecode=sigdecode_der)
            except BadSignatureError:
                return False
            except Exception:
                return False
        else:
            # 安全加固：无 ecdsa 库时一律拒绝签名验证
            # Security: Always reject when ecdsa library is missing
            return False
    
    @staticmethod
    def public_key_to_address(public_key: bytes, prefix: str = "MAIN") -> str:
        """公钥转地址（类似 BTC 流程）。
        
        1. SHA256(公钥)
        2. RIPEMD160(SHA256结果)
        3. Base58Check 编码（简化为 Base32）
        """
        # SHA256
        sha256_hash = hashlib.sha256(public_key).digest()
        
        # RIPEMD160（如果可用）
        try:
            ripemd160 = hashlib.new('ripemd160')
            ripemd160.update(sha256_hash)
            hash160 = ripemd160.digest()
        except ValueError:
            # 某些系统不支持 RIPEMD160，使用 SHA256 截断
            hash160 = sha256_hash[:20]
        
        # Base32 编码（比 Base58 更简单）
        encoded = base64.b32encode(hash160).decode().rstrip('=')
        
        return f"{prefix}_{encoded}"


# ============== AES-256 加密 ==============

class AESCipher:
    """AES-256-GCM 加密器。"""
    
    @staticmethod
    def derive_key(password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """从密码派生加密密钥。"""
        if salt is None:
            salt = secrets.token_bytes(16)
        
        if HAS_CRYPTOGRAPHY:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=600000,
            )
            key = kdf.derive(password.encode())
        else:
            # 备用 PBKDF2
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt,
                600000,
                32
            )
        
        return key, salt
    
    @staticmethod
    def encrypt(plaintext: bytes, password: str) -> Dict[str, str]:
        """加密数据。
        
        Returns:
            {"ciphertext": "...", "salt": "...", "nonce": "..."}
        """
        key, salt = AESCipher.derive_key(password)
        nonce = secrets.token_bytes(12)
        
        if HAS_CRYPTOGRAPHY:
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        else:
            # 生产环境禁止无加密库运行
            raise RuntimeError(
                "[SECURITY] cryptography 库未安装，禁止使用不安全的回退加密。"
                "请安装: pip install cryptography"
            )
        
        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
        }
    
    @staticmethod
    def decrypt(encrypted: Dict[str, str], password: str) -> bytes:
        """解密数据。"""
        ciphertext = base64.b64decode(encrypted["ciphertext"])
        salt = base64.b64decode(encrypted["salt"])
        nonce = base64.b64decode(encrypted["nonce"])
        
        key, _ = AESCipher.derive_key(password, salt)
        
        if HAS_CRYPTOGRAPHY:
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        else:
            raise RuntimeError(
                "[SECURITY] cryptography 库未安装，无法解密。"
                "请安装: pip install cryptography"
            )
        
        return plaintext


# ============== 哈希工具 ==============

class HashUtils:
    """哈希工具集。"""
    
    @staticmethod
    def sha256(data: bytes) -> bytes:
        return hashlib.sha256(data).digest()
    
    @staticmethod
    def sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def double_sha256(data: bytes) -> bytes:
        """双 SHA256（BTC 风格）。"""
        return hashlib.sha256(hashlib.sha256(data).digest()).digest()
    
    @staticmethod
    def hash160(data: bytes) -> bytes:
        """RIPEMD160(SHA256(data))（BTC 地址生成）。"""
        sha = hashlib.sha256(data).digest()
        try:
            ripemd = hashlib.new('ripemd160')
            ripemd.update(sha)
            return ripemd.digest()
        except ValueError:
            return sha[:20]
    
    @staticmethod
    def merkle_root(hashes: list) -> str:
        """计算默克尔根。"""
        if not hashes:
            return HashUtils.sha256_hex(b"empty")
        
        if len(hashes) == 1:
            return hashes[0] if isinstance(hashes[0], str) else hashes[0].hex()
        
        # 如果奇数，复制最后一个
        if len(hashes) % 2 == 1:
            hashes = hashes + [hashes[-1]]
        
        # 两两配对哈希
        next_level = []
        for i in range(0, len(hashes), 2):
            h1 = hashes[i] if isinstance(hashes[i], str) else hashes[i].hex()
            h2 = hashes[i+1] if isinstance(hashes[i+1], str) else hashes[i+1].hex()
            combined = bytes.fromhex(h1 + h2)
            next_level.append(HashUtils.sha256_hex(combined))
        
        return HashUtils.merkle_root(next_level)


# ============== 生产级钱包 ==============

@dataclass
class ProductionWallet:
    """生产级钱包。"""
    wallet_id: str
    mnemonic: str  # 应该加密存储
    keypair: ECKeyPair
    addresses: Dict[str, str] = field(default_factory=dict)
    created_at: float = 0.0
    encrypted: bool = False
    
    @classmethod
    def create(cls, passphrase: str = "", word_count: int = 12) -> "ProductionWallet":
        """创建新钱包。"""
        import time
        
        # 生成助记词
        strength = {12: 128, 15: 160, 18: 192, 21: 224, 24: 256}.get(word_count, 128)
        bip39 = BIP39()
        mnemonic = bip39.generate(strength)
        
        # 派生种子和密钥
        seed = bip39.to_seed(mnemonic, passphrase)
        keypair = ECDSASigner.from_seed(seed)
        
        # 生成地址
        main_address = ECDSASigner.public_key_to_address(keypair.public_key, "MAIN")
        
        wallet_id = HashUtils.sha256_hex(keypair.public_key)[:16]
        
        return cls(
            wallet_id=wallet_id,
            mnemonic=mnemonic,
            keypair=keypair,
            addresses={"MAIN": main_address},
            created_at=time.time(),
        )
    
    @classmethod
    def from_mnemonic(cls, mnemonic: str, passphrase: str = "") -> "ProductionWallet":
        """从助记词恢复钱包。"""
        import time
        
        bip39 = BIP39()
        if not bip39.validate(mnemonic):
            raise ValueError("无效的助记词")
        
        seed = bip39.to_seed(mnemonic, passphrase)
        keypair = ECDSASigner.from_seed(seed)
        
        main_address = ECDSASigner.public_key_to_address(keypair.public_key, "MAIN")
        wallet_id = HashUtils.sha256_hex(keypair.public_key)[:16]
        
        return cls(
            wallet_id=wallet_id,
            mnemonic=mnemonic,
            keypair=keypair,
            addresses={"MAIN": main_address},
            created_at=time.time(),
        )
    
    def add_sector_address(self, sector: str):
        """添加板块地址。"""
        address = ECDSASigner.public_key_to_address(self.keypair.public_key, sector)
        self.addresses[sector] = address
        return address
    
    def sign(self, message: bytes) -> bytes:
        """签名消息。"""
        return ECDSASigner.sign(self.keypair.private_key, message)
    
    def verify(self, message: bytes, signature: bytes) -> bool:
        """验证签名。"""
        return ECDSASigner.verify(self.keypair.public_key, message, signature)
    
    def encrypt_and_save(self, password: str) -> Dict:
        """加密并导出钱包。"""
        import json as _json
        wallet_data = {
            "wallet_id": self.wallet_id,
            "mnemonic": self.mnemonic,
            "private_key": self.keypair.private_key_hex,
            "created_at": self.created_at,
        }
        
        plaintext = _json.dumps(wallet_data).encode()
        encrypted = AESCipher.encrypt(plaintext, password)
        encrypted["addresses"] = self.addresses
        encrypted["encrypted"] = True
        
        return encrypted
    
    @classmethod
    def load_encrypted(cls, encrypted: Dict, password: str) -> "ProductionWallet":
        """加载加密钱包。"""
        import json as _json
        plaintext = AESCipher.decrypt(encrypted, password)
        decoded = plaintext.decode()
        
        # 严格 JSON 解析（移除 ast.literal_eval 后备以防止 DoS 攻击）
        try:
            wallet_data = _json.loads(decoded)
        except _json.JSONDecodeError as e:
            raise ValueError(f"Invalid wallet keystore format: {e}")
        
        if not isinstance(wallet_data, dict) or "mnemonic" not in wallet_data:
            raise ValueError("Keystore missing required 'mnemonic' field")
        
        return cls.from_mnemonic(wallet_data["mnemonic"])


# ============== 导出 ==============

def get_crypto_status() -> Dict[str, bool]:
    """获取加密库状态。"""
    return {
        "ecdsa": HAS_ECDSA,
        "mnemonic": HAS_MNEMONIC,
        "cryptography": HAS_CRYPTOGRAPHY,
        "production_ready": HAS_ECDSA and HAS_MNEMONIC and HAS_CRYPTOGRAPHY,
    }


# 测试
if __name__ == "__main__":
    print("=== 加密模块测试 ===")
    print(f"加密库状态: {get_crypto_status()}")
    
    print("\n1. BIP39 助记词测试")
    bip39 = BIP39()
    mnemonic = bip39.generate(128)
    print(f"   助记词: {mnemonic}")
    print(f"   验证: {bip39.validate(mnemonic)}")
    
    print("\n2. 密钥对测试")
    keypair = ECDSASigner.generate_keypair()
    print(f"   私钥: {keypair.private_key_hex[:32]}...")
    print(f"   公钥: {keypair.public_key_hex[:32]}...")
    
    print("\n3. 签名验证测试")
    message = b"Hello, POUW Chain!"
    signature = ECDSASigner.sign(keypair.private_key, message)
    print(f"   签名: {signature.hex()[:32]}...")
    print(f"   验证: {ECDSASigner.verify(keypair.public_key, message, signature)}")
    
    print("\n4. 地址生成测试")
    address = ECDSASigner.public_key_to_address(keypair.public_key, "MAIN")
    print(f"   地址: {address}")
    
    print("\n5. AES 加密测试")
    plaintext = b"Secret wallet data"
    test_password = "test_only_" + secrets.token_hex(8)
    encrypted = AESCipher.encrypt(plaintext, test_password)
    decrypted = AESCipher.decrypt(encrypted, test_password)
    print(f"   原文: {plaintext}")
    print(f"   解密: {decrypted}")
    print(f"   匹配: {plaintext == decrypted}")
    
    print("\n6. 生产钱包测试")
    wallet = ProductionWallet.create(word_count=12)
    print(f"   钱包 ID: {wallet.wallet_id}")
    print(f"   助记词: {wallet.mnemonic}")
    print(f"   主地址: {wallet.addresses['MAIN']}")
    
    print("\n✅ 所有测试完成!")
