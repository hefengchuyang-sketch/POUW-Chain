# -*- coding: utf-8 -*-
"""
钱包管理模块

提供钱包生成、地址派生、签名等功能。
"""

import hashlib
import secrets
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field

from mnemonic import Mnemonic
import ecdsa
from ecdsa import SECP256k1, SigningKey, VerifyingKey


# 支持的板块列表
SUPPORTED_SECTORS = ["MAIN", "H100", "A100", "RTX4090", "RTX4080", "RTX3090", "CPU"]


@dataclass
class WalletInfo:
    """钱包信息"""
    mnemonic: str
    master_private_key: str
    addresses: Dict[str, str]  # sector -> address
    public_keys: Dict[str, str] = field(default_factory=dict)


class WalletGenerator:
    """
    钱包生成器
    
    支持:
    - BIP39 助记词生成（需要 mnemonic 库）
    - 多板块地址派生
    - ECDSA 签名（需要 ecdsa 库）
    """
    
    # 地址前缀
    ADDRESS_PREFIX = "MAIN_"
    
    def __init__(self, word_count: int = 12):
        """
        初始化钱包生成器
        
        Args:
            word_count: 助记词数量（12, 15, 18, 21, 24）
        """
        self.word_count = word_count
        self.mnemo = Mnemonic("english")
    
    def generate_mnemonic(self) -> str:
        """
        生成助记词
        
        Returns:
            12/24 个单词的助记词
        """
        # 使用标准 BIP39
        strength = 128 if self.word_count == 12 else 256
        return self.mnemo.generate(strength=strength)
    
    def mnemonic_to_seed(self, mnemonic: str, passphrase: str = "") -> bytes:
        """
        助记词转种子
        
        Args:
            mnemonic: 助记词
            passphrase: 可选密码
        
        Returns:
            64 字节种子
        """
        return self.mnemo.to_seed(mnemonic, passphrase)
    
    def derive_master_key(self, seed: bytes) -> str:
        """
        从种子派生主私钥
        
        Args:
            seed: 64 字节种子
        
        Returns:
            主私钥（hex）
        """
        return hashlib.sha256(seed).hexdigest()
    
    def derive_sector_address(self, master_key: str, sector: str) -> Tuple[str, str]:
        """
        派生板块地址
        
        Args:
            master_key: 主私钥
            sector: 板块名称
        
        Returns:
            (address, private_key)
        """
        # 派生板块私钥
        sector_key = hashlib.sha256(f"{master_key}:{sector}".encode()).hexdigest()
        
        # 生成地址
        addr_hash = hashlib.sha256(sector_key.encode()).hexdigest()
        address = f"{self.ADDRESS_PREFIX}{addr_hash[:32].upper()}"
        
        return address, sector_key
    
    def generate_wallet(self, passphrase: str = "") -> WalletInfo:
        """
        生成完整钱包
        
        Args:
            passphrase: 可选密码
        
        Returns:
            WalletInfo 对象
        """
        # 生成助记词
        mnemonic = self.generate_mnemonic()
        
        # 转换为种子
        seed = self.mnemonic_to_seed(mnemonic, passphrase)
        
        # 派生主私钥
        master_key = self.derive_master_key(seed)
        
        # 派生各板块地址
        addresses = {}
        for sector in SUPPORTED_SECTORS:
            address, _ = self.derive_sector_address(master_key, sector)
            addresses[sector] = address
        
        return WalletInfo(
            mnemonic=mnemonic,
            master_private_key=master_key,
            addresses=addresses
        )
    
    def restore_wallet(self, mnemonic: str, passphrase: str = "") -> Optional[WalletInfo]:
        """
        从助记词恢复钱包
        
        Args:
            mnemonic: 助记词
            passphrase: 可选密码
        
        Returns:
            WalletInfo 对象，如果助记词无效返回 None
        """
        # 验证助记词（单词数 + BIP39 校验和）
        words = mnemonic.strip().split()
        if len(words) not in [12, 15, 18, 21, 24]:
            return None
        if not self.mnemo.check(mnemonic.strip()):
            return None
        
        # 转换为种子
        seed = self.mnemonic_to_seed(mnemonic, passphrase)
        
        # 派生主私钥
        master_key = self.derive_master_key(seed)
        
        # 派生各板块地址
        addresses = {}
        for sector in SUPPORTED_SECTORS:
            address, _ = self.derive_sector_address(master_key, sector)
            addresses[sector] = address
        
        return WalletInfo(
            mnemonic=mnemonic,
            master_private_key=master_key,
            addresses=addresses
        )
    
    @staticmethod
    def sign_message(private_key: str, message: str) -> str:
        """
        签名消息
        
        Args:
            private_key: 私钥（hex）
            message: 待签名消息
        
        Returns:
            签名（hex）
        """
        from ecdsa.util import sigencode_der
        key_bytes = bytes.fromhex(private_key)[:32]
        sk = SigningKey.from_string(key_bytes, curve=SECP256k1)
        message_hash = hashlib.sha256(message.encode()).digest()
        signature = sk.sign(message_hash, sigencode=sigencode_der)
        return signature.hex()
    
    @staticmethod
    def verify_signature(address: str, message: str, signature: str, public_key: str = None) -> bool:
        """
        验证签名
        
        Args:
            address: 地址
            message: 原始消息
            signature: 签名
            public_key: 公钥（可选）
        
        Returns:
            验证是否通过
        """
        if not public_key:
            return False
        try:
            from ecdsa.util import sigdecode_der
            vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
            message_hash = hashlib.sha256(message.encode()).digest()
            return vk.verify(bytes.fromhex(signature), message_hash, sigdecode=sigdecode_der)
        except Exception:
            return False
    
    @staticmethod
    def generate_address() -> str:
        """
        生成随机地址（用于测试）
        
        Returns:
            随机地址
        """
        random_bytes = secrets.token_bytes(32)
        addr_hash = hashlib.sha256(random_bytes).hexdigest()
        return f"MAIN_{addr_hash[:32].upper()}"


class WalletManager:
    """
    钱包管理器
    
    管理用户的多个钱包，支持：
    - 创建/导入钱包
    - 地址查询
    - 签名操作
    """
    
    def __init__(self):
        self.wallets: Dict[str, WalletInfo] = {}
        self.generator = WalletGenerator()
    
    def create_wallet(self, wallet_id: str = None, passphrase: str = "") -> Tuple[str, WalletInfo]:
        """
        创建新钱包
        
        Args:
            wallet_id: 钱包ID（可选，自动生成）
            passphrase: 密码短语
        
        Returns:
            (wallet_id, WalletInfo)
        """
        if not wallet_id:
            wallet_id = f"wallet_{secrets.token_hex(8)}"
        
        wallet = self.generator.generate_wallet(passphrase)
        self.wallets[wallet_id] = wallet
        
        return wallet_id, wallet
    
    def import_wallet(self, wallet_id: str, mnemonic: str, passphrase: str = "") -> Optional[WalletInfo]:
        """
        导入钱包
        
        Args:
            wallet_id: 钱包ID
            mnemonic: 助记词
            passphrase: 密码短语
        
        Returns:
            WalletInfo 或 None
        """
        wallet = self.generator.restore_wallet(mnemonic, passphrase)
        if wallet:
            self.wallets[wallet_id] = wallet
        return wallet
    
    def get_wallet(self, wallet_id: str) -> Optional[WalletInfo]:
        """获取钱包"""
        return self.wallets.get(wallet_id)
    
    def get_address(self, wallet_id: str, sector: str = "MAIN") -> Optional[str]:
        """获取指定板块的地址"""
        wallet = self.wallets.get(wallet_id)
        if wallet:
            return wallet.addresses.get(sector)
        return None
    
    def sign(self, wallet_id: str, message: str) -> Optional[str]:
        """使用钱包签名"""
        wallet = self.wallets.get(wallet_id)
        if wallet:
            return WalletGenerator.sign_message(wallet.master_private_key, message)
        return None
    
    def list_wallets(self) -> List[str]:
        """列出所有钱包ID"""
        return list(self.wallets.keys())


# 便捷函数
def generate_wallet(passphrase: str = "") -> WalletInfo:
    """生成新钱包"""
    return WalletGenerator().generate_wallet(passphrase)


def restore_wallet(mnemonic: str, passphrase: str = "") -> Optional[WalletInfo]:
    """从助记词恢复钱包"""
    return WalletGenerator().restore_wallet(mnemonic, passphrase)


def generate_address() -> str:
    """生成随机地址"""
    return WalletGenerator.generate_address()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("钱包生成器测试")
    print("=" * 60)
    
    # 生成钱包
    gen = WalletGenerator()
    wallet = gen.generate_wallet()
    
    print(f"\n助记词: {'*' * 20} (已隐藏)")
    print(f"主私钥: {'*' * 16}... (已隐藏)")
    print("\n地址:")
    for sector, addr in wallet.addresses.items():
        print(f"  {sector}: {addr}")
    
    # 签名测试
    message = "Hello, POUW Chain!"
    signature = gen.sign_message(wallet.master_private_key, message)
    print(f"\n签名测试:")
    print(f"  消息: {message}")
    print(f"  签名: {signature[:32]}...")
    
    # 恢复测试
    restored = gen.restore_wallet(wallet.mnemonic)
    if restored and restored.addresses == wallet.addresses:
        print("\n✅ 钱包恢复测试通过")
    else:
        print("\n❌ 钱包恢复测试失败")
    
    print("\n" + "=" * 60)
