# 深度代码审计报告 — POUW 区块链后端

**审计日期**: 2025 年  
**审计范围**: `core/` 目录下关键模块  
**审计方法**: 逐行人工代码审查

---

## 摘要

发现 **12 个新 Bug**，其中 **3 个 CRITICAL**、**5 个 HIGH**、**4 个 MEDIUM**。

---

## Bug #1 — `rollback_to_height()` 引用不存在的表和列（UTXO 回滚完全失效）

**严重级别**: 🔴 CRITICAL  
**文件**: `core/utxo_store.py` 第 834–893 行  
**类别**: 数据损坏 / 逻辑错误

**问题描述**:  
`rollback_to_height()` 方法引用了三个不存在的数据库对象:
1. `tx_inputs` 表（行 851、875）— `_init_db()` 中从未创建
2. `tx_outputs` 表（行 879）— 同上
3. `spent_tx_id` 列（行 862）— 实际列名为 `spent_txid`

同时，`self._lock`（行 847）在 `UTXOStore.__init__` 中从未定义。

这意味着**链重组（reorg）时 UTXO 回滚完全崩溃**，会抛出 `AttributeError` 或 `sqlite3.OperationalError`，导致 UTXO 状态与区块链不一致。

**代码片段**:
```python
# utxo_store.py, line 847-893
def rollback_to_height(self, height: int) -> int:
    with self._lock:                    # ← BUG: _lock 未定义
        with self._conn() as conn:
            spent_inputs = conn.execute("""
                SELECT input_utxo_id FROM tx_inputs     # ← BUG: 表不存在
                WHERE tx_id IN (
                    SELECT tx_id FROM transactions WHERE block_height > ?
                )
            """, (height,)).fetchall()

            for row in spent_inputs:
                conn.execute("""
                    UPDATE utxos SET status = 'unspent', spent_tx_id = NULL  # ← BUG: 列名应为 spent_txid
                    WHERE utxo_id = ? AND status = 'spent'
                """, (utxo_id,))

            conn.execute("""
                DELETE FROM tx_inputs WHERE tx_id IN (   # ← BUG: 表不存在
                    SELECT tx_id FROM transactions WHERE block_height > ?
                )
            """, (height,))
            conn.execute("""
                DELETE FROM tx_outputs WHERE tx_id IN (  # ← BUG: 表不存在
                    SELECT tx_id FROM transactions WHERE block_height > ?
                )
            """, (height,))
```

**修复方案**:
```python
def __init__(self, db_path: str = "data/utxo.db"):
    self.db_path = Path(db_path)
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
    self._local = threading.local()
    self._lock = threading.Lock()   # ← 添加锁
    self._init_db()

def rollback_to_height(self, height: int) -> int:
    with self._lock:
        with self._exclusive_conn() as conn:
            # Step 1: 找出 > height 的交易，恢复被消费的 UTXO
            txids_to_rollback = conn.execute(
                "SELECT txid FROM transactions WHERE block_height > ?",
                (height,)
            ).fetchall()
            txid_list = [r[0] for r in txids_to_rollback]

            restored = 0
            for txid in txid_list:
                # 解析交易 inputs，恢复被消费的 UTXO
                tx_row = conn.execute(
                    "SELECT inputs FROM transactions WHERE txid = ?", (txid,)
                ).fetchone()
                if tx_row:
                    inputs = json.loads(tx_row[0])
                    for inp in inputs:
                        input_txid = inp.get('txid', '')
                        input_index = inp.get('index', 0)
                        utxo_id = f"{input_txid}:{input_index}"
                        cursor = conn.execute(
                            "UPDATE utxos SET status = 'unspent', spent_txid = '' WHERE utxo_id = ? AND status = 'spent'",
                            (utxo_id,)
                        )
                        restored += cursor.rowcount

            # Step 2: 删除 > height 产生的 UTXO
            deleted_utxos = conn.execute(
                "SELECT COUNT(*) FROM utxos WHERE block_height > ?", (height,)
            ).fetchone()[0]
            conn.execute("DELETE FROM utxos WHERE block_height > ?", (height,))

            # Step 3: 删除 > height 的交易
            deleted_txs = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE block_height > ?", (height,)
            ).fetchone()[0]
            conn.execute("DELETE FROM transactions WHERE block_height > ?", (height,))

            return deleted_utxos + deleted_txs
```

---

## Bug #2 — `finalize_proposal()` 迭代 votes 字典的 values 导致 AttributeError

**严重级别**: 🔴 CRITICAL  
**文件**: `core/dao_treasury.py` 第 817–822 行  
**类别**: 逻辑错误 / 运行时崩溃

**问题描述**:  
`self.votes` 是 `defaultdict(list)`，键为 `proposal_id`，值为 `List[Vote]`。`self.votes.values()` 返回的是每个 proposal 的投票列表（`List[Vote]`），不是单个 `Vote` 对象。

代码 `v.voter for v in self.votes.values()` 中，`v` 是一个 `list`，调用 `v.voter` 和 `v.proposal_id` 会抛出 `AttributeError: 'list' object has no attribute 'voter'`。

**后果**: 任何提案的结算（finalize）都会崩溃，DAO 治理功能完全失效。

**代码片段**:
```python
# dao_treasury.py, line 817-822
unique_voters = len(set(
    v.voter for v in self.votes.values()     # ← BUG: v 是 List[Vote]，不是 Vote
    if v.proposal_id == proposal_id           # ← BUG: list 没有 proposal_id 属性
))
```

**修复方案**:
```python
# self.votes[proposal_id] 已经只包含该提案的投票，直接使用
unique_voters = len(set(
    v.voter for v in self.votes.get(proposal_id, [])
))
```

---

## Bug #3 — `get_block_by_hash()` 缺少线程锁保护（竞态条件）

**严重级别**: 🟡 HIGH  
**文件**: `core/consensus.py` 第 1472–1484 行  
**类别**: 竞态条件

**问题描述**:  
`get_block_by_hash()` 在遍历 `self.chain` 时没有获取 `self._lock`，而 `get_block_by_height()` 在同一操作上正确使用了锁。由于 `self.chain` 在 `add_block()`（行 1282–1283）中会被裁剪赋值（`self.chain = self.chain[-self._max_cache_size:]`），并发读写可能导致迭代期间列表被修改，触发 `RuntimeError` 或返回错误结果。

**代码片段**:
```python
# consensus.py, line 1472-1484
def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
    for block in self.chain:          # ← BUG: 没有加锁
        if block.hash == block_hash:
            return block
    # ...

# 对比 get_block_by_height (line 1451):
def get_block_by_height(self, height: int) -> Optional[Block]:
    with self._lock:                  # ← 正确加锁
        for block in self.chain:
            if block.height == height:
                return block
```

**修复方案**:
```python
def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
    with self._lock:
        for block in self.chain:
            if block.hash == block_hash:
                return block

    # 回退到数据库
    try:
        row = self._db_conn.execute(
            "SELECT block_data FROM blocks WHERE hash = ?",
            (block_hash,)
        ).fetchone()
        if row:
            block_dict = json.loads(row['block_data'])
            return self._dict_to_block(block_dict)
    except Exception:
        pass
    return None
```

---

## Bug #4 — `_block_get_by_height()` 用列表索引代替区块高度（缓存裁剪后返回错误区块）

**严重级别**: 🔴 CRITICAL  
**文件**: `core/rpc_service.py` 第 1900–1912 行  
**类别**: 逻辑错误 / 数据损坏

**问题描述**:  
`self.consensus_engine.chain` 是一个内存缓存列表，在区块链高度超过 200 后会被裁剪（只保留最近 200 个区块）。裁剪后，`chain[0]` 不再是高度 0 的区块，但 RPC 方法使用 `height` 参数直接作为列表索引访问 `chain[height]`，**返回的是完全错误的区块**。

例如：链高度 500 时，`chain[0]` 实际是高度 301 的区块，但 `_block_get_by_height(0)` 会返回它。

**代码片段**:
```python
# rpc_service.py, line 1900-1912
def _block_get_by_height(self, height: int = 0, sector: str = None, **kwargs):
    if self.consensus_engine and height < len(self.consensus_engine.chain):
        block = self.consensus_engine.chain[height]   # ← BUG: height 当索引用
        block_dict = block.to_dict()
        # ...
        return block_dict
    return {"height": height, "error": "Block not found"}
```

**修复方案**:
```python
def _block_get_by_height(self, height: int = 0, sector: str = None, **kwargs):
    if self.consensus_engine:
        block = self.consensus_engine.get_block_by_height(height)  # 使用正确的查找方法
        if block:
            block_dict = block.to_dict()
            block_dict['prevHash'] = block.prev_hash
            block_dict['txCount'] = len(block.transactions)
            block_dict['reward'] = block.block_reward
            block_dict['size'] = block.get_size()
            block_dict['transactions'] = block.transactions
            return block_dict
    return {"height": height, "error": "Block not found"}
```

---

## Bug #5 — `protocol_fee_pool.py vote_on_proposal()` 无重复投票检查

**严重级别**: 🟡 HIGH  
**文件**: `core/protocol_fee_pool.py` 第 363–395 行  
**类别**: 安全漏洞

**问题描述**:  
同一个 voter 可以反复调用 `vote_on_proposal()`，每次调用都会累加 `votes_for` 或 `votes_against` 和 `voter_count`。攻击者只需一个账户反复投票即可操纵提案通过或否决。

对比 `dao_treasury.py vote()` 有正确的重复投票检查（行 732–735）。

**代码片段**:
```python
# protocol_fee_pool.py, line 386-394
def vote_on_proposal(self, proposal_id, voter, voter_stake, vote_for):
    # ... validation ...
    # 记录投票 — 无重复检查！
    voting_power = voter_stake
    if vote_for:
        proposal.votes_for += voting_power    # ← 可反复累加
    else:
        proposal.votes_against += voting_power
    proposal.voter_count += 1                 # ← 无限增长
    return True, "投票成功"
```

**修复方案**:
```python
def vote_on_proposal(
    self,
    proposal_id: str,
    voter: str,
    voter_stake: float,
    vote_for: bool,
) -> Tuple[bool, str]:
    proposal = self.proposals.get(proposal_id)
    if not proposal:
        return False, "提案不存在"

    if proposal.status != SpendingStatus.VOTING:
        return False, f"提案状态不是投票中: {proposal.status.value}"

    if time.time() > proposal.voting_ends:
        return False, "投票已结束"

    if voter_stake < self.MIN_STAKE_TO_VOTE:
        return False, f"质押不足: 需要 {self.MIN_STAKE_TO_VOTE}"

    # ← 添加重复投票检查
    if not hasattr(proposal, '_voters'):
        proposal._voters = set()
    if voter in proposal._voters:
        return False, "已投票，不能重复投票"
    proposal._voters.add(voter)

    voting_power = voter_stake
    if vote_for:
        proposal.votes_for += voting_power
    else:
        proposal.votes_against += voting_power
    proposal.voter_count += 1

    return True, "投票成功"
```

---

## Bug #6 — `_block_get_by_hash()` RPC 遍历 chain 无锁保护

**严重级别**: 🟡 HIGH  
**文件**: `core/rpc_service.py` 第 1914–1926 行  
**类别**: 竞态条件

**问题描述**:  
`_block_get_by_hash()` 直接遍历 `self.consensus_engine.chain`，不走 consensus engine 的线程安全方法。与 Bug #3 同源，但影响面是 RPC 层面——任何客户端调用 `block_getByHash` 都可能命中竞态。

**代码片段**:
```python
# rpc_service.py, line 1914-1926
def _block_get_by_hash(self, hash: str = "", **kwargs):
    if self.consensus_engine and hash:
        for block in self.consensus_engine.chain:   # ← 直接遍历，无锁
            if block.hash == hash:
                # ...
                return block_dict
    return None
```

**修复方案**:
```python
def _block_get_by_hash(self, hash: str = "", **kwargs):
    if self.consensus_engine and hash:
        block = self.consensus_engine.get_block_by_hash(hash)  # 使用引擎方法
        if block:
            block_dict = block.to_dict()
            block_dict['prevHash'] = block.prev_hash
            block_dict['txCount'] = len(block.transactions)
            block_dict['reward'] = block.block_reward
            block_dict['size'] = block.get_size()
            block_dict['transactions'] = block.transactions
            return block_dict
    return None
```

---

## Bug #7 — `_chain_get_info()` 每次调用遍历全部区块计算交易数（O(n) 性能问题）

**严重级别**: 🟠 MEDIUM  
**文件**: `core/rpc_service.py` 第 1940–1960 行  
**类别**: 性能 / 潜在 DoS

**问题描述**:  
`_chain_get_info()` 是一个 PUBLIC RPC 方法，每次调用时遍历 `self.consensus_engine.chain` 所有区块来计算 `total_transactions`。在区块数取缓存上限（200 块）以下时还行，但该方法还不加锁地读取 `chain`，与 Bug #3 同为竞态风险。

更严重的问题是**它没有加锁**地遍历 `chain`：

**代码片段**:
```python
# rpc_service.py, line 1947-1951
if self.consensus_engine:
    # ...
    for block in self.consensus_engine.chain:     # ← 无锁遍历
        total_transactions += len(block.transactions)
```

**修复方案**:
```python
if self.consensus_engine:
    height = self.consensus_engine.get_chain_height()
    difficulty = self.consensus_engine.current_difficulty

    with self.consensus_engine._lock:
        total_transactions = sum(len(b.transactions) for b in self.consensus_engine.chain)
        if self.consensus_engine.chain:
            last_block_time = self.consensus_engine.chain[-1].timestamp
```

---

## Bug #8 — `_wallet_unlock()` 密码验证可被绕过

**严重级别**: 🟡 HIGH  
**文件**: `core/rpc_service.py` 第 2578–2618 行  
**类别**: 安全漏洞

**问题描述**:  
`_wallet_unlock()` 中，密码验证失败时（`from_mnemonic` 异常），代码直接 `pass` 跳过验证并继续到 `_refresh_wallet_session()` 解锁钱包。这意味着**任何密码（甚至空字符串已被前面挡掉，但任何非空字符串）都能解锁钱包**。

**代码片段**:
```python
# rpc_service.py, line 2589-2612
if hasattr(self, 'wallet_info') and self.wallet_info:
    try:
        from core.crypto import ProductionWallet
        test_wallet = ProductionWallet.from_mnemonic(
            self.wallet_info.mnemonic, passphrase=password
        )
        if test_wallet.addresses.get('MAIN') != self.miner_address:
            test_wallet2 = ProductionWallet.from_mnemonic(
                self.wallet_info.mnemonic, passphrase=""
            )
            if test_wallet2.addresses.get('MAIN') != self.miner_address:
                return {"success": False, "message": "密码验证失败"}
    except Exception:
        pass  # ← BUG: 异常被吞掉，直接跳到下面的 _refresh_wallet_session()

self._refresh_wallet_session()   # ← 无论密码对错都执行
return {"success": True, ...}
```

**修复方案**:
```python
if hasattr(self, 'wallet_info') and self.wallet_info:
    try:
        from core.crypto import ProductionWallet
        test_wallet = ProductionWallet.from_mnemonic(
            self.wallet_info.mnemonic, passphrase=password
        )
        if test_wallet.addresses.get('MAIN') != self.miner_address:
            test_wallet2 = ProductionWallet.from_mnemonic(
                self.wallet_info.mnemonic, passphrase=""
            )
            if test_wallet2.addresses.get('MAIN') != self.miner_address:
                return {"success": False, "message": "密码验证失败 / Invalid password"}
    except Exception:
        return {"success": False, "message": "密码验证失败 / Password verification error"}

self._refresh_wallet_session()
return {"success": True, ...}
```

---

## Bug #9 — `_staking_stake()` 和 `_staking_unstake()` 是空壳实现（返回假数据）

**严重级别**: 🟡 HIGH  
**文件**: `core/rpc_service.py` 第 3182–3232 行  
**类别**: 逻辑错误 / 数据完整性

**问题描述**:  
`_staking_stake()` 不检查余额、不扣款、不写入任何持久化存储——直接返回 `"success": True` 和一个随机 `stake_id`。`_staking_unstake()` 更离谱，硬编码返回 `"unstakedAmount": 10.0` 而不管实际质押了多少。

这两个方法是完全的空壳，但被注册为可调用的 RPC USER 方法，前端可以调用它们并认为操作已完成。

**代码片段**:
```python
# rpc_service.py, line 3191-3206
def _staking_stake(self, amount, sector="MAIN", duration=30, **kwargs):
    if not self.miner_address:
        return {"success": False, "error": "请先连接钱包"}
    if amount <= 0:
        return {"success": False, "error": "质押金额必须大于0"}

    stake_id = f"stake_{uuid.uuid4().hex[:12]}"
    return {
        "success": True,                        # ← 没有扣款！
        "stakeId": stake_id,                     # ← 随机 ID，未持久化
        "amount": amount,
        "estimatedApy": 12.5,                    # ← 硬编码假 APY
        # ...
    }

def _staking_unstake(self, stakeId, **kwargs):
    return {
        "success": True,
        "unstakedAmount": 10.0,                  # ← 硬编码假金额
        "rewards": 0.5,                          # ← 硬编码假奖励
    }
```

**修复方案**:  
需要接入真实的质押管理器（`staking_manager`），或在方法中明确返回错误提示"功能未实现"以避免前端误解。最低限度修复：

```python
def _staking_stake(self, amount: float, sector: str = "MAIN", duration: int = 30, **kwargs) -> Dict:
    return {
        "success": False,
        "error": "staking_not_implemented",
        "message": "质押功能尚未上线，请关注后续更新 / Staking is not yet available"
    }

def _staking_unstake(self, stakeId: str, **kwargs) -> Dict:
    return {
        "success": False,
        "error": "staking_not_implemented",
        "message": "解除质押功能尚未上线 / Unstaking is not yet available"
    }
```

---

## Bug #10 — `dual_witness_exchange.py` 请求兑换金额使用精度不安全的浮点乘法

**严重级别**: 🟠 MEDIUM  
**文件**: `core/dual_witness_exchange.py` 第 398–399 行  
**类别**: 精度问题 / 数据不一致

**问题描述**:  
`request_exchange()` 计算 MAIN 金额时使用了原始浮点乘法 `amount * rate`，但同一个类的 `calculate_main_amount()` 方法（行 339）使用了精度安全的 `safe_mul` + `to_display`。这导致兑换请求中记录的 `target_main_amount` 与通过 `calculate_main_amount()` 查询得到的金额可能有微小差异。

**代码片段**:
```python
# dual_witness_exchange.py, line 398-399
rate = self.get_exchange_rate(sector)
main_amount = amount * rate                   # ← 浮点不安全

# 对比 line 339 (同一个类):
def calculate_main_amount(self, sector, sector_coin_amount):
    from .precision import safe_mul, to_display
    rate = self.get_exchange_rate(sector)
    return to_display(safe_mul(sector_coin_amount, rate))   # ← 精度安全
```

**修复方案**:
```python
# 使用精度安全的计算方法
main_amount = self.calculate_main_amount(sector, amount)
```

---

## Bug #11 — `_account_get_transactions()` 直接打开新的 SQLite 连接（绕过连接管理）

**严重级别**: 🟠 MEDIUM  
**文件**: `core/rpc_service.py` 第 2140–2180 行  
**类别**: 资源泄漏 / 架构问题

**问题描述**:  
`_account_get_transactions()` 不使用 `self.utxo_store` 的连接管理，而是手动 `sqlite3.connect()` 打开 `utxo.db` 的新连接。虽然最后调用了 `conn.close()`，但如果中间抛异常（如 JSON 解析失败），`close()` 可能不被执行。更重要的是这绕过了 UTXOStore 的线程安全连接管理，可能导致并发读取冲突。

**代码片段**:
```python
# rpc_service.py, line 2145-2176
conn = sqlite3.connect(utxo_db_path)         # ← 手动打开新连接
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
rows = cursor.execute("""
    SELECT ... FROM transactions
    WHERE (from_address = ? OR to_address = ?) AND tx_type = 'exchange'
    ...
""", ...).fetchall()
# ... 处理行 ...
conn.close()                                   # ← 异常时泄漏
```

**修复方案**:
```python
# 使用 UTXOStore 的交易历史查询方法
if self.utxo_store and target_address:
    try:
        exchange_txs = self.utxo_store.get_transaction_history(target_address, limit=limit)
        for tx in exchange_txs:
            if tx.tx_type == 'exchange':
                txs.append({
                    "txId": tx.txid[:16] if tx.txid else "",
                    "from": tx.from_address,
                    "to": tx.to_address,
                    "amount": tx.amount,
                    "coin": "MAIN",
                    "status": "confirmed",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(tx.timestamp)),
                    "blockHeight": tx.block_height or 0,
                    "txType": "EXCHANGE",
                })
    except Exception as e:
        print(f"获取UTXO交易历史失败: {e}")
```

---

## Bug #12 — `create_exchange_transaction()` 使用 `_conn()` 而非 `_exclusive_conn()`（并发铸币风险）

**严重级别**: 🟠 MEDIUM  
**文件**: `core/utxo_store.py` 第 756–820 行  
**类别**: 竞态条件 / 数据完整性

**问题描述**:  
`create_exchange_transaction()` 使用普通的 `_conn()` 上下文管理器来创建 UTXO 和交易记录，而不是 `_exclusive_conn()`。普通 `_conn()` 不会执行 `BEGIN EXCLUSIVE`，因此在并发场景下，同一个 `exchange_id` 的兑换交易可能被重复写入，导致重复铸币。

对比 `create_transfer()` 正确使用了 `_exclusive_conn()`（行 420）。

**代码片段**:
```python
# utxo_store.py, line 797 (在 create_exchange_transaction 内)
with self._conn() as conn:              # ← 应使用 _exclusive_conn()
    conn.execute("""
        INSERT INTO utxos ...           # ← 创建铸币 UTXO
    """, (...))
    conn.execute("""
        INSERT INTO transactions ...    # ← 记录兑换交易
    """, (...))
```

**修复方案**:
```python
# 使用排他事务防止并发重复铸币
with self._exclusive_conn() as conn:
    # 先检查是否已存在此 exchange_id 的交易（幂等性）
    existing = conn.execute(
        "SELECT 1 FROM transactions WHERE memo LIKE ?",
        (f"%{exchange_id}%",)
    ).fetchone()
    if existing:
        return {"success": False, "error": "兑换交易已存在 / Exchange TX already recorded"}

    conn.execute("""INSERT INTO utxos ...""", (...))
    conn.execute("""INSERT INTO transactions ...""", (...))
```

---

## 按严重级别汇总

| 级别 | 数量 | Bug 编号 |
|------|------|----------|
| 🔴 CRITICAL | 3 | #1, #2, #4 |
| 🟡 HIGH | 5 | #3, #5, #6, #8, #9 |
| 🟠 MEDIUM | 4 | #7, #10, #11, #12 |

## 按类别汇总

| 类别 | Bug 编号 |
|------|----------|
| 逻辑错误 / 运行时崩溃 | #1, #2, #4, #9 |
| 竞态条件 | #3, #6, #7, #12 |
| 安全漏洞 | #5, #8 |
| 精度/数据不一致 | #10 |
| 资源泄漏 | #11 |

---

## 建议修复优先级

1. **立即修复** (CRITICAL): Bug #1, #2, #4 — 链重组、DAO 治理和区块查询完全损坏
2. **尽快修复** (HIGH): Bug #3, #5, #6, #8 — 安全漏洞和竞态条件
3. **计划修复** (MEDIUM): Bug #7, #9, #10, #11, #12 — 性能和代码质量问题
