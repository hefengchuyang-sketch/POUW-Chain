"""
[C-10] 跨库崩溃恢复日志（Write-Ahead Journal）

解决 on_block_mined 回调中跨 2 个 SQLite 数据库写入的原子性问题：
  1. sector_coins.db → mint_block_reward
  2. utxo.db → create_coinbase_utxo

如果进程在步骤 1 和步骤 2 之间崩溃，板块币已铸造但 UTXO 未创建，
导致状态不一致。

机制:
  1. 写操作前：将操作意图写入 journal (状态 = PENDING)
  2. 所有步骤完成后：将 journal 标记为 COMMITTED
  3. 启动时：检查 PENDING 状态的 journal，执行补偿操作

Journal 存储在独立的 data/block_journal.db 中。
"""

import sqlite3
import json
import time
import os
import threading
from pathlib import Path
from enum import Enum
from typing import Optional, Dict, Callable


class JournalState(Enum):
    PENDING = "PENDING"
    STEP1_DONE = "STEP1_DONE"      # sector_coins 写入完成
    COMMITTED = "COMMITTED"         # 全部完成
    ROLLED_BACK = "ROLLED_BACK"    # 已回滚


class BlockMiningJournal:
    """
    挖矿出块的跨库写入日志。
    
    使用方式:
        journal = BlockMiningJournal()
        
        # 启动时检查未完成事务
        journal.recover_pending(sector_ledger, utxo_store)
        
        # 出块时
        jid = journal.begin(block_height, block_hash, miner, sector, reward)
        sector_ledger.mint_block_reward(...)
        journal.mark_step1_done(jid)
        utxo_store.create_coinbase_utxo(...)
        journal.commit(jid)
    """
    
    def __init__(self, db_path: str = "data/block_journal.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mining_journal (
                    journal_id TEXT PRIMARY KEY,
                    block_height INTEGER NOT NULL,
                    block_hash TEXT NOT NULL,
                    miner_address TEXT NOT NULL,
                    sector TEXT NOT NULL,
                    block_reward REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT 'PENDING',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_state ON mining_journal(state)")
            conn.commit()
        finally:
            conn.close()
    
    def begin(self, block_height: int, block_hash: str,
              miner_address: str, sector: str, block_reward: float) -> str:
        """记录写入意图，返回 journal_id"""
        import uuid
        jid = f"j_{block_height}_{uuid.uuid4().hex[:8]}"
        now = time.time()
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO mining_journal 
                    (journal_id, block_height, block_hash, miner_address, sector, block_reward, state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (jid, block_height, block_hash, miner_address, sector, block_reward,
                      JournalState.PENDING.value, now, now))
                conn.commit()
            finally:
                conn.close()
        
        return jid
    
    def mark_step1_done(self, journal_id: str):
        """标记步骤1（板块币铸造）完成"""
        self._update_state(journal_id, JournalState.STEP1_DONE)
    
    def commit(self, journal_id: str):
        """标记全部完成"""
        self._update_state(journal_id, JournalState.COMMITTED)
    
    def _update_state(self, journal_id: str, state: JournalState):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "UPDATE mining_journal SET state = ?, updated_at = ? WHERE journal_id = ?",
                    (state.value, time.time(), journal_id)
                )
                conn.commit()
            finally:
                conn.close()
    
    def get_pending_entries(self) -> list:
        """获取所有未完成的 journal 条目"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM mining_journal 
                WHERE state IN (?, ?)
                ORDER BY block_height ASC
            """, (JournalState.PENDING.value, JournalState.STEP1_DONE.value)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    
    def recover_pending(self, sector_ledger, utxo_store, log_fn=None):
        """
        启动时恢复未完成的事务。
        
        策略:
        - PENDING 状态: 步骤1都没完成，不需要补偿（sector_coins 有自己的原子性）
        - STEP1_DONE 状态: 板块币已铸造但 UTXO 未创建 → 补创建 UTXO
        """
        _log = log_fn or (lambda msg: print(f"[Journal] {msg}"))
        
        entries = self.get_pending_entries()
        if not entries:
            return
        
        _log(f"发现 {len(entries)} 个未完成的出块事务，开始恢复...")
        
        for entry in entries:
            jid = entry["journal_id"]
            state = entry["state"]
            height = entry["block_height"]
            
            if state == JournalState.PENDING.value:
                # 步骤1未完成 — sector_coins.mint_block_reward 是单DB原子操作
                # 要么完成了要么没有，无需补偿，直接标记放弃
                _log(f"  Journal {jid} (height={height}): PENDING → 标记为已回滚")
                self._update_state(jid, JournalState.ROLLED_BACK)
                
            elif state == JournalState.STEP1_DONE.value:
                # 板块币已铸造，UTXO 未创建 → 需要补创建
                _log(f"  Journal {jid} (height={height}): STEP1_DONE → 补创建 UTXO")
                
                if utxo_store:
                    try:
                        txid, utxo = utxo_store.create_coinbase_utxo(
                            miner_address=entry["miner_address"],
                            amount=entry["block_reward"],
                            sector=entry["sector"],
                            block_height=entry["block_height"],
                            block_hash=entry["block_hash"]
                        )
                        _log(f"  UTXO 补创建成功: {txid}")
                        self.commit(jid)
                    except Exception as e:
                        _log(f"  UTXO 补创建失败: {e}，保留 journal 条目等待下次恢复")
                else:
                    _log(f"  utxo_store 不可用，跳过恢复")


# ==================== 全局单例 ====================

_journal_instance: Optional[BlockMiningJournal] = None
_journal_lock = threading.Lock()


def get_mining_journal(db_path: str = "data/block_journal.db") -> BlockMiningJournal:
    """获取全局 journal 单例"""
    global _journal_instance
    if _journal_instance is None:
        with _journal_lock:
            if _journal_instance is None:
                _journal_instance = BlockMiningJournal(db_path)
    return _journal_instance
