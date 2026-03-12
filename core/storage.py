"""
Storage 模块 - 数据持久化

支持多种存储后端：
1. SQLite（默认，无需额外安装）
2. LevelDB（可选，需要 plyvel）
3. 文件存储（备用）

存储内容：
- 区块链数据
- 钱包数据
- 交易池
- 节点状态
"""

import os
import json
import time
import sqlite3
import hashlib
import threading

from core import db
from typing import Dict, List, Optional, Any, Iterator
from dataclasses import dataclass, asdict
from pathlib import Path
from contextlib import contextmanager

# 尝试导入 LevelDB
try:
    import plyvel
    HAS_LEVELDB = True
except ImportError:
    HAS_LEVELDB = False


# ============== 存储接口 ==============

class StorageBackend:
    """存储后端接口。"""
    
    def get(self, key: str) -> Optional[bytes]:
        raise NotImplementedError
    
    def put(self, key: str, value: bytes):
        raise NotImplementedError
    
    def delete(self, key: str):
        raise NotImplementedError
    
    def exists(self, key: str) -> bool:
        raise NotImplementedError
    
    def iterate(self, prefix: str = "") -> Iterator[tuple]:
        raise NotImplementedError
    
    def close(self):
        raise NotImplementedError


# ============== SQLite 存储 ==============

class SQLiteStorage(StorageBackend):
    """SQLite 存储后端。"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        
        # 初始化表
        self._init_tables()
    
    @property
    def conn(self) -> sqlite3.Connection:
        """获取线程本地连接。"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = db.connect(self.db_path)
        return self._local.conn
    
    def _init_tables(self):
        """初始化数据库表。"""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    created_at REAL,
                    updated_at REAL
                )
            """)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY,
                    hash TEXT UNIQUE,
                    prev_hash TEXT,
                    timestamp REAL,
                    data BLOB,
                    sector TEXT
                )
            """)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_id TEXT PRIMARY KEY,
                    block_height INTEGER,
                    from_addr TEXT,
                    to_addr TEXT,
                    amount REAL,
                    fee REAL,
                    timestamp REAL,
                    data BLOB,
                    status TEXT
                )
            """)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    wallet_id TEXT PRIMARY KEY,
                    address TEXT,
                    encrypted_data BLOB,
                    created_at REAL,
                    sector TEXT
                )
            """)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS peers (
                    node_id TEXT PRIMARY KEY,
                    host TEXT,
                    port INTEGER,
                    sector TEXT,
                    last_seen REAL,
                    is_bootstrap INTEGER
                )
            """)
            
            # 创建索引
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_blocks_sector ON blocks(sector)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_addr)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_addr)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_height)")
    
    def get(self, key: str) -> Optional[bytes]:
        cursor = self.conn.execute(
            "SELECT value FROM kv_store WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row['value'] if row else None
    
    def put(self, key: str, value: bytes):
        now = time.time()
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO kv_store (key, value, created_at, updated_at)
                VALUES (?, ?, COALESCE((SELECT created_at FROM kv_store WHERE key = ?), ?), ?)
            """, (key, value, key, now, now))
    
    def delete(self, key: str):
        with self.conn:
            self.conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
    
    def exists(self, key: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM kv_store WHERE key = ?", (key,)
        )
        return cursor.fetchone() is not None
    
    def iterate(self, prefix: str = "") -> Iterator[tuple]:
        cursor = self.conn.execute(
            "SELECT key, value FROM kv_store WHERE key LIKE ?",
            (prefix + "%",)
        )
        for row in cursor:
            yield row['key'], row['value']
    
    def close(self):
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# ============== LevelDB 存储 ==============

class LevelDBStorage(StorageBackend):
    """LevelDB 存储后端。"""
    
    def __init__(self, db_path: str):
        if not HAS_LEVELDB:
            raise ImportError("plyvel 未安装")
        
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        self.db = plyvel.DB(db_path, create_if_missing=True)
    
    def get(self, key: str) -> Optional[bytes]:
        return self.db.get(key.encode())
    
    def put(self, key: str, value: bytes):
        self.db.put(key.encode(), value)
    
    def delete(self, key: str):
        self.db.delete(key.encode())
    
    def exists(self, key: str) -> bool:
        return self.db.get(key.encode()) is not None
    
    def iterate(self, prefix: str = "") -> Iterator[tuple]:
        with self.db.iterator(prefix=prefix.encode()) as it:
            for key, value in it:
                yield key.decode(), value
    
    def close(self):
        self.db.close()


# ============== 区块存储 ==============

class BlockStore:
    """区块存储。"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def save_block(self, block_data: dict) -> bool:
        """保存区块。"""
        try:
            with self.storage.conn:
                self.storage.conn.execute("""
                    INSERT OR REPLACE INTO blocks 
                    (height, hash, prev_hash, timestamp, data, sector)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    block_data.get('height'),
                    block_data.get('hash'),
                    block_data.get('prev_hash'),
                    block_data.get('timestamp'),
                    json.dumps(block_data).encode(),
                    block_data.get('sector', 'MAIN'),
                ))
            return True
        except Exception as e:
            print(f"保存区块失败: {e}")
            return False
    
    def get_block_by_height(self, height: int, sector: str = "MAIN") -> Optional[dict]:
        """按高度获取区块。"""
        cursor = self.storage.conn.execute(
            "SELECT data FROM blocks WHERE height = ? AND sector = ?",
            (height, sector)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None
    
    def get_block_by_hash(self, hash: str) -> Optional[dict]:
        """按哈希获取区块。"""
        cursor = self.storage.conn.execute(
            "SELECT data FROM blocks WHERE hash = ?", (hash,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None
    
    def get_latest_block(self, sector: str = "MAIN") -> Optional[dict]:
        """获取最新区块。"""
        cursor = self.storage.conn.execute(
            "SELECT data FROM blocks WHERE sector = ? ORDER BY height DESC LIMIT 1",
            (sector,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None
    
    def get_chain_height(self, sector: str = "MAIN") -> int:
        """获取链高度。"""
        cursor = self.storage.conn.execute(
            "SELECT MAX(height) as height FROM blocks WHERE sector = ?",
            (sector,)
        )
        row = cursor.fetchone()
        return row['height'] if row and row['height'] is not None else -1
    
    def get_blocks_range(
        self,
        start: int,
        end: int,
        sector: str = "MAIN"
    ) -> List[dict]:
        """获取区块范围。"""
        cursor = self.storage.conn.execute(
            "SELECT data FROM blocks WHERE height >= ? AND height <= ? AND sector = ? ORDER BY height",
            (start, end, sector)
        )
        return [json.loads(row['data']) for row in cursor]


# ============== 交易存储 ==============

class TransactionStore:
    """交易存储。"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def save_transaction(self, tx_data: dict) -> bool:
        """保存交易。"""
        try:
            with self.storage.conn:
                self.storage.conn.execute("""
                    INSERT OR REPLACE INTO transactions
                    (tx_id, block_height, from_addr, to_addr, amount, fee, timestamp, data, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tx_data.get('tx_id'),
                    tx_data.get('block_height', -1),
                    tx_data.get('from_addr', ''),
                    tx_data.get('to_addr', ''),
                    tx_data.get('amount', 0),
                    tx_data.get('fee', 0),
                    tx_data.get('timestamp', time.time()),
                    json.dumps(tx_data).encode(),
                    tx_data.get('status', 'pending'),
                ))
            return True
        except Exception as e:
            print(f"保存交易失败: {e}")
            return False
    
    def get_transaction(self, tx_id: str) -> Optional[dict]:
        """获取交易。"""
        cursor = self.storage.conn.execute(
            "SELECT data FROM transactions WHERE tx_id = ?", (tx_id,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row['data'])
        return None
    
    def get_address_transactions(
        self,
        address: str,
        limit: int = 100
    ) -> List[dict]:
        """获取地址相关交易。"""
        cursor = self.storage.conn.execute("""
            SELECT data FROM transactions 
            WHERE from_addr = ? OR to_addr = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (address, address, limit))
        return [json.loads(row['data']) for row in cursor]
    
    def get_pending_transactions(self, limit: int = 1000) -> List[dict]:
        """获取待处理交易。"""
        cursor = self.storage.conn.execute("""
            SELECT data FROM transactions 
            WHERE status = 'pending'
            ORDER BY fee DESC, timestamp ASC LIMIT ?
        """, (limit,))
        return [json.loads(row['data']) for row in cursor]
    
    def update_transaction_status(self, tx_id: str, status: str, block_height: int = None):
        """更新交易状态。"""
        with self.storage.conn:
            if block_height is not None:
                self.storage.conn.execute("""
                    UPDATE transactions SET status = ?, block_height = ? WHERE tx_id = ?
                """, (status, block_height, tx_id))
            else:
                self.storage.conn.execute("""
                    UPDATE transactions SET status = ? WHERE tx_id = ?
                """, (status, tx_id))


# ============== 钱包存储 ==============

class WalletStore:
    """钱包存储。"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def save_wallet(self, wallet_data: dict) -> bool:
        """保存加密钱包。"""
        try:
            with self.storage.conn:
                self.storage.conn.execute("""
                    INSERT OR REPLACE INTO wallets
                    (wallet_id, address, encrypted_data, created_at, sector)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    wallet_data.get('wallet_id'),
                    wallet_data.get('address', ''),
                    json.dumps(wallet_data).encode(),
                    wallet_data.get('created_at', time.time()),
                    wallet_data.get('sector', 'MAIN'),
                ))
            return True
        except Exception as e:
            print(f"保存钱包失败: {e}")
            return False
    
    def get_wallet(self, wallet_id: str) -> Optional[dict]:
        """获取钱包。"""
        cursor = self.storage.conn.execute(
            "SELECT encrypted_data FROM wallets WHERE wallet_id = ?", (wallet_id,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row['encrypted_data'])
        return None
    
    def list_wallets(self) -> List[dict]:
        """列出所有钱包。"""
        cursor = self.storage.conn.execute(
            "SELECT wallet_id, address, sector, created_at FROM wallets"
        )
        return [dict(row) for row in cursor]
    
    def delete_wallet(self, wallet_id: str) -> bool:
        """删除钱包。"""
        try:
            with self.storage.conn:
                self.storage.conn.execute(
                    "DELETE FROM wallets WHERE wallet_id = ?", (wallet_id,)
                )
            return True
        except Exception:
            return False


# ============== 节点存储 ==============

class PeerStore:
    """节点存储。"""
    
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage
    
    def save_peer(self, peer_data: dict) -> bool:
        """保存节点。"""
        try:
            with self.storage.conn:
                self.storage.conn.execute("""
                    INSERT OR REPLACE INTO peers
                    (node_id, host, port, sector, last_seen, is_bootstrap)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    peer_data.get('node_id'),
                    peer_data.get('host'),
                    peer_data.get('port'),
                    peer_data.get('sector', 'MAIN'),
                    peer_data.get('last_seen', time.time()),
                    1 if peer_data.get('is_bootstrap') else 0,
                ))
            return True
        except Exception as e:
            print(f"保存节点失败: {e}")
            return False
    
    def get_peers(self, sector: str = None, limit: int = 100) -> List[dict]:
        """获取节点列表。"""
        if sector:
            cursor = self.storage.conn.execute("""
                SELECT * FROM peers WHERE sector = ?
                ORDER BY last_seen DESC LIMIT ?
            """, (sector, limit))
        else:
            cursor = self.storage.conn.execute("""
                SELECT * FROM peers ORDER BY last_seen DESC LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor]
    
    def get_bootstrap_peers(self) -> List[dict]:
        """获取 bootstrap 节点。"""
        cursor = self.storage.conn.execute(
            "SELECT * FROM peers WHERE is_bootstrap = 1"
        )
        return [dict(row) for row in cursor]
    
    def remove_stale_peers(self, max_age: float = 86400):
        """移除过期节点。"""
        cutoff = time.time() - max_age
        with self.storage.conn:
            self.storage.conn.execute(
                "DELETE FROM peers WHERE last_seen < ? AND is_bootstrap = 0",
                (cutoff,)
            )


# ============== 主存储管理器 ==============

class StorageManager:
    """存储管理器。"""
    
    def __init__(self, data_dir: str = "./data", use_leveldb: bool = False):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化存储后端
        if use_leveldb and HAS_LEVELDB:
            self.kv = LevelDBStorage(str(self.data_dir / "leveldb"))
        else:
            self.kv = None
        
        # SQLite 总是可用
        self.sqlite = SQLiteStorage(str(self.data_dir / "chain.db"))
        
        # 初始化各个存储
        self.blocks = BlockStore(self.sqlite)
        self.transactions = TransactionStore(self.sqlite)
        self.wallets = WalletStore(self.sqlite)
        self.peers = PeerStore(self.sqlite)
    
    def close(self):
        """关闭所有连接。"""
        if self.kv:
            self.kv.close()
        self.sqlite.close()
    
    def get_stats(self) -> dict:
        """获取存储统计。"""
        return {
            "data_dir": str(self.data_dir),
            "db_size": (self.data_dir / "chain.db").stat().st_size if (self.data_dir / "chain.db").exists() else 0,
            "chain_height": self.blocks.get_chain_height(),
            "wallet_count": len(self.wallets.list_wallets()),
            "peer_count": len(self.peers.get_peers()),
        }


# ============== 便捷函数 ==============

_storage: Optional[StorageManager] = None

def get_storage(data_dir: str = "./data") -> StorageManager:
    """获取全局存储管理器。"""
    global _storage
    if _storage is None:
        _storage = StorageManager(data_dir)
    return _storage


def close_storage():
    """关闭全局存储。"""
    global _storage
    if _storage:
        _storage.close()
        _storage = None


# 测试
if __name__ == "__main__":
    print("=== 存储模块测试 ===")
    
    # 创建存储
    storage = StorageManager("./test_data")
    
    print("\n1. 区块存储测试")
    block = {
        "height": 0,
        "hash": "genesis_hash_000",
        "prev_hash": "",
        "timestamp": time.time(),
        "sector": "MAIN",
        "transactions": [],
    }
    storage.blocks.save_block(block)
    print(f"   保存区块: 高度 {block['height']}")
    
    loaded = storage.blocks.get_block_by_height(0)
    print(f"   加载区块: {loaded['hash'][:20]}...")
    
    print("\n2. 交易存储测试")
    tx = {
        "tx_id": "tx_001",
        "from_addr": "MAIN_ALICE",
        "to_addr": "MAIN_BOB",
        "amount": 100.0,
        "fee": 0.1,
        "status": "pending",
    }
    storage.transactions.save_transaction(tx)
    print(f"   保存交易: {tx['tx_id']}")
    
    loaded = storage.transactions.get_transaction("tx_001")
    print(f"   加载交易: {loaded['from_addr']} -> {loaded['to_addr']}")
    
    print("\n3. 钱包存储测试")
    wallet = {
        "wallet_id": "wallet_001",
        "address": "MAIN_TEST_ADDRESS",
        "encrypted_data": "xxx",
        "sector": "MAIN",
    }
    storage.wallets.save_wallet(wallet)
    print(f"   保存钱包: {wallet['wallet_id']}")
    
    wallets = storage.wallets.list_wallets()
    print(f"   钱包数量: {len(wallets)}")
    
    print("\n4. 节点存储测试")
    peer = {
        "node_id": "node_001",
        "host": "127.0.0.1",
        "port": 9333,
        "sector": "MAIN",
        "is_bootstrap": True,
    }
    storage.peers.save_peer(peer)
    print(f"   保存节点: {peer['node_id']}")
    
    peers = storage.peers.get_bootstrap_peers()
    print(f"   Bootstrap 节点: {len(peers)}")
    
    print("\n5. 统计信息")
    stats = storage.get_stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")
    
    # 清理
    storage.close()
    import shutil
    shutil.rmtree("./test_data", ignore_errors=True)
    
    print("\n✅ 所有测试完成!")
