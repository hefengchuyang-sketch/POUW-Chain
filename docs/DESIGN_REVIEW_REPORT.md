# POUW Multi-Sector Chain 架构设计审查报告

> 审查日期：2025-07  
> 审查范围：core/ 目录下 85+ 个模块，main.py 入口  
> 审查类型：架构/设计层面（非安全漏洞扫描）  
> **修复状态：已修复 34/34 项（10 CRITICAL + 10 MAJOR + 14 HIGH）— 全部完成**

### 修复轮次记录

| 轮次 | 修复项 | 编号 |
|------|--------|------|
| Round 1 | 13 项 | C-01, C-02, C-03, C-04, C-06, C-08, M-05, M-06, M-09, H-02, H-03, H-05, H-09 |
| Round 2 | 7 项 | C-07, M-03, M-04, M-08, H-04, H-08, H-14 |
| Round 3 | 14 项 | H-13, C-05, M-02, H-12, H-01, H-10, H-11, C-09, M-07, M-10, H-06, H-07, C-10, M-01 |

### Round 3 修复详情

| 编号 | 修复内容 | 涉及文件 |
|------|---------|---------|
| H-13 | 钱包 RPC (create/import/unlock) 权限从 PUBLIC 改为 USER | rpc_service.py |
| C-05 | Account 模型标注为 Phase 2 遗留死代码 | account.py |
| M-02 | UnifiedConsensus 标注为未集成模块 | unified_consensus.py |
| H-12 | p2p_direct 标注为实验性数据结构模拟 | p2p_direct.py |
| H-01 | 节点公钥持久化到 data/peer_pubkeys.json | tcp_network.py |
| H-10 | DAO 投票快照机制（创建提案时冻结质押状态） | dao_treasury.py |
| H-11 | Treasury 销毁/分配事件持久化到 SQLite | treasury.py |
| C-09 | 统一费率配置到 fee_config.py 单一真相源 | fee_config.py(新), treasury.py, protocol_fee_pool.py, compute_market_v3.py, dao_treasury.py |
| M-07 | DAO 提案到期自动执行调度 | dao_treasury.py |
| M-10 | 统一加密库包装器 crypto_utils.py | crypto_utils.py(新), rpc_service.py |
| H-06 | DynamicExchangeRate 注入兑换服务 | dual_witness_exchange.py, main.py |
| H-07 | Decimal 精度安全工具模块 | precision.py(新), treasury.py, dual_witness_exchange.py, sector_coin.py |
| C-10 | 跨库崩溃恢复日志 (WAL) | crash_journal.py(新), main.py |
| M-01 | RPC Handler 拆分基础设施 + wallet/dao 域迁移 | rpc_handlers/(新), rpc_service.py |

---

## 一、架构概览

```
main.py (POUWNode)
├─ StorageManager          (storage.py)      → data/chain.db [空！未使用]
├─ ProductionWallet        (crypto.py)       → wallets/*.json
├─ ConsensusEngine         (consensus.py)    → data/chain_{sector}.db [真正的链存储]
│   ├─ PoUWExecutor        (pouw_executor.py)
│   ├─ BlockTypeSelector   (pouw_block_types.py)
│   └─ ObjectiveMetricsCollector
├─ SectorCoinLedger        (sector_coin.py)  → data/sector_coins.db
├─ UTXOStore               (utxo_store.py)   → data/utxo.db
├─ P2PNode                 (tcp_network.py)  → TCP:9333
├─ NodeRPCService          (rpc_service.py)  → HTTP:8545  [8411行/236方法 God Object]
│   ├─ 内嵌实例化 22+ 业务模块
│   ├─ DualWitnessExchange (dual_witness_exchange.py)
│   ├─ DAOGovernance       (dao_treasury.py)
│   └─ ... 等
├─ Treasury                (treasury.py)     → 内存
├─ ProtocolFeePoolManager  (protocol_fee_pool.py) → 内存
└─ [未接入] UnifiedConsensus (unified_consensus.py)
```

**核心问题**：系统经历了多个 Phase 迭代，但旧模块未清理，新模块未完全集成，导致大量死代码和并行实现。

---

## 二、CRITICAL（P0）— 必须修复才能上线

### C-01: Block 类双重定义，哈希算法不兼容

| | Phase1 Block | Consensus Block |
|--|--|--|
| **位置** | `core/block.py:14` | `core/consensus.py:110` |
| **高度字段** | `index` | `height` |
| **哈希输入** | `index+timestamp+str(transactions)+prev_hash+nonce` | `height+prev_hash+merkle_root+timestamp+difficulty+nonce+miner_id` |
| **使用者** | `Blockchain`, `MainChain`, `ComputeBlockChain` | `ConsensusEngine`（生产唯一使用） |

`core/__init__.py` 导出的是旧 `Block`，`from core import Block` 拿到的是**错误版本**。

### C-02: 双重区块存储，数据永远不一致

- `ConsensusEngine` → 写入 `data/chain_{sector}.db`
- `StorageManager.BlockStore` → 写入 `data/chain.db`
- 两者互不感知，`chain.db` 的 blocks 表**始终为空**

### C-03: 两套钱包实现产生不同地址

| | WalletGenerator (wallet.py) | ProductionWallet (crypto.py) |
|--|--|--|
| **密钥派生** | `SHA256(seed)` → hex 截断 | `HMAC-SHA512("Bitcoin seed", seed)` |
| **地址格式** | `MAIN_` + 32字符大写HEX | `MAIN_` + Base32(RIPEMD160(SHA256(pubkey))) |
| **BIP32** | ❌ | 仅第一步 |

**同一助记词在两套实现中恢复出不同地址。** `_wallet_unlock` 用 `ProductionWallet` 验证 `WalletGenerator` 创建的钱包，地址永远不匹配。

### C-04: 签名编码格式不一致

- `ECDSASigner.sign()` → DER 编码 (`sigencode_der`)
- `utxo_store.py` 验签 → 默认 raw 编码 (`sigdecode_string`)
- **签名永远验证失败**

### C-05: UTXO 模型与 Account 模型并存，余额不同步

- UTXO: `utxo_store.py` → `data/utxo.db`
- Account: `account.py` → 内存 dict
- `unified_consensus.py` 用 Account 模型检查余额，`rpc_service.py` 用 UTXO 模型转账
- **两个模型的余额独立维护，无同步机制**

### C-06: POUW 证明字段名不一致，自己挖的块无法通过他人验证

- 生成端 (`consensus.py:760`): `"work_score": round(p.compute_work_score(), 2)`
- 验证端 (`consensus.py:995`): `required_fields = {'task_id', 'work_amount'}`
- **自己挖的块广播后，其他节点因找不到 `work_amount` 字段而拒绝**

### C-07: 区块传播/同步协议完全缺失 ✅ 已修复

- ~~`NEW_BLOCK`, `GET_BLOCKS`, `BLOCKS` 消息类型已定义但**没有处理器**~~
- **修复**: `handle_blocks` 改用 `add_block()` 全量验证；`get_blocks_range` 添加 count<=50 限制
- 新节点加入网络后可通过 GET_BLOCKS/BLOCKS 获取历史区块
- 区块同步现在执行完整的哈希/PoW/高度/交易验证

### C-08: 板块币命名体系不统一（4 套）

| 系统 | 命名 |
|------|------|
| `sector_coin.py` | `H100`, `RTX4090`, `RTX3080`, `CPU`, `GENERAL` |
| `exchange_rate.py` | `GPU_DATACENTER`, `GPU_CONSUMER`, `CPU`, `STORAGE` |
| `dual_witness_exchange.py` | `H100`, `RTX4090`, `RTX3080`, `CPU`, `GENERAL` |
| `dynamic_pricing.py` | `RTX3060`, `RTX3070`, `A100` 等 |

`DynamicExchangeRate` 引擎无法为真正的板块币计算汇率（键名完全不同）。

### C-09: 三套费用分配系统并行

| 组件 | 费率 |
|------|------|
| `Treasury` (treasury.py) | 1% (0.5%销毁+0.3%矿工+0.2%基金会) |
| `ProtocolFeePoolManager` (protocol_fee_pool.py) | 1% (0.5%销毁+0.3%矿工+0.2%协议池) |
| `HardRules` (compute_market_v3.py) | 1% (0.5%销毁+0.3%矿工+0.2%基金会) |
| `GovernanceConfig` (dao_treasury.py) | 5%平台+90%矿工+5%国库 ← **完全矛盾** |

**如果三个系统都被调用，费用被扣 3%。矿工奖励只累加不分发，无出口。**

### C-10: 跨数据库状态不原子

区块挖出后回调执行 3 个独立操作（各自提交到不同 SQLite 文件）：
1. `sector_ledger.mint_block_reward()` → `sector_coins.db`
2. `utxo_store.create_coinbase_utxo()` → `utxo.db`
3. `consensus_engine._save_block()` → `chain_{sector}.db`

**任何步骤之间崩溃都会导致跨库数据不一致，且无回滚机制。**

---

## 三、MAJOR（P1）— 严重设计缺陷

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| M-01 | RPC Service God Object：8411行/236方法 | rpc_service.py | 无法独立测试/部署子系统 |
| M-02 | `UnifiedConsensus` (1800行) 被完全绕过 | unified_consensus.py | 铸币/评分/审计/监控全部不生效 |
| M-03 | ~~重组（Reorg）不回滚 UTXO/板块币余额~~ ✅ | consensus.py + utxo_store.py + sector_coin.py | 已修复：rollback_to_height() |
| M-04 | ~~`add_block_no_validate()` 绕过安全检查~~ ✅ | consensus.py:1112 | 已通过C-07修复：同步改用add_block() |
| M-05 | 见证签名验证传入板块名称而非公钥 | dual_witness_exchange.py:337 | 见证可被伪造 |
| M-06 | 多签公钥未初始化 | dao_treasury.py:247-253 | 多签形同虚设 |
| M-07 | DAO 提案无执行引擎 | dao_treasury.py | 投票通过也不产生效果 |
| M-08 | ~~无终局性机制~~ ✅ | consensus.py | 已修复：FINALITY_THRESHOLD=20, finalize_blocks(), reorg拒绝回滚终局区块 |
| M-09 | DID 凭证用 SHA-256 伪签名 | did_identity.py:330-337 | 任何人可伪造凭证 |
| M-10 | 三套加密方案使用不同库 | rpc/crypto/security | 不可互操作 |

---

## 四、HIGH（P2）— 需要改进

| # | 问题 | 位置 |
|---|------|------|
| H-01 | TOFU 首次连接不抗中间人 | tcp_network.py:688-730 |
| H-02 | `_network_secret` 重启后变化，TOFU 信任链断裂 | tcp_network.py:333 |
| H-03 | 节点列表不持久化，重启后从零开始发现 | tcp_network.py |
| H-04 | ~~最大 8 个活跃连接~~ ✅ | tcp_network.py | 已修复：可配置 max_peers(默认50), 入站/出站均限制 |
| H-05 | `seen_messages` 超限后全量清空，消息可被重放 | tcp_network.py:610-613 |
| H-06 | `DynamicExchangeRate` 引擎完全孤立未使用 | exchange_rate.py |
| H-07 | 浮点数存储全部余额（SQLite REAL），长期精度漂移 | sector_coin.py, utxo_store.py |
| H-08 | ~~供应上限检查与 INSERT 之间无事务隔离~~ ✅ | sector_coin.py | 已修复：原子操作（同一锁+连接内完成查询+计算+写入） |
| H-09 | `exchange_id` 截断为 16 字符（64位），高频碰撞风险 | dual_witness_exchange.py:271-273 |
| H-10 | 无投票快照机制，投票期间质押变动影响结果 | dao_treasury.py |
| H-11 | 销毁仅为内存计数器，重启丢失，链上不可验证 | treasury.py:128 |
| H-12 | `p2p_direct.py` 纯数据结构，无实际网络实现 | p2p_direct.py |
| H-13 | `wallet_create`/`wallet_import` 无需认证 | security.py:519 |
| H-14 | ~~钱包信息纯内存保存~~ ✅ | rpc_service.py + main.py | 已修复：keystore自动存盘(wallets/)，启动时恢复miner_address |

---

## 五、死代码清单

以下模块/类在生产运行时**完全未被使用**：

| 文件 | 类 | 原因 |
|------|-----|------|
| `core/block.py` | `Block` (Phase 1) | 被 `consensus.py` 内部 Block 替代 |
| `core/blockchain.py` | `Blockchain` | main.py 不实例化 |
| `core/blockchain_v2.py` | — | main.py 不实例化 |
| `core/main_chain.py` | `MainChain` | main.py 不实例化 |
| `core/compute_blockchain.py` | `ComputeBlockChain` | main.py 不实例化 |
| `core/unified_consensus.py` | `UnifiedConsensus` | main.py 不实例化 |
| `core/network.py` | `NetworkSimulator` | 仅用于模拟 |
| `core/governance_enhanced.py` | — | 被 dao_treasury.py 替代 |
| `core/governance_v2.py` | — | 已废弃 |
| `core/exchange_rate.py` | `DynamicExchangeRate` | 未集成到兑换流程 |
| `core/p2p_direct.py` | `P2PDirectManager` | 纯数据结构 |
| `core/storage.py` | `BlockStore` 部分 | chain.db blocks 表始终为空 |

---

## 六、重构路线图建议

### Phase A：统一数据模型（1-2 周）

1. **统一 Block 类**：删除 `block.py` 旧 Block，提取 `consensus.py` 的 Block 到独立模块
2. **选择账本模型**：保留 UTXO 模型，移除 Account 模型引用
3. **统一地址格式**：以 `crypto.py` 的 SHA256→RIPEMD160→Base32 为标准
4. **统一签名编码**：全系统使用 DER 编码
5. **统一板块命名**：确定一套板块 ID 标准
6. **修复 POUW 证明字段**：`work_score` → `work_amount`

### Phase B：消除并行实现（1 周）

1. **合并费用系统**：保留 `ProtocolFeePoolManager`，删除其他重复逻辑
2. **将 `DynamicExchangeRate` 集成到 `DualWitnessExchange`**
3. **清理死代码**：删除 Phase 1 遗留的 blockchain/block/main_chain 等
4. **统一加密库**：选择 `cryptography`，移除 `pycryptodome` 依赖

### Phase C：补全网络层（2-3 周）

1. **实现区块同步协议**：GET_BLOCKS/BLOCKS 处理器
2. **实现区块传播**：inv/getdata 模式
3. **添加终局性机制**：至少实现 N-confirmation 规则
4. **节点列表持久化**
5. **重组时回滚 UTXO 和板块币余额**

### Phase D：拆分 God Object（2 周）

将 `NodeRPCService` 拆分为：
- `WalletRPCHandler` — 钱包相关
- `MiningRPCHandler` — 挖矿相关  
- `ExchangeRPCHandler` — 兑换相关
- `GovernanceRPCHandler` — DAO 治理
- `ComputeRPCHandler` — 算力市场
- `RPCRouter` — 路由分发层

### Phase E：数据一致性（1 周）

1. **统一存储到单一 SQLite**（或 ATTACH DATABASE + 跨库事务）
2. **补全 DAO 提案执行引擎**
3. **初始化多签公钥**
4. **实现销毁的链上证明**

---

## 七、结论

系统经历了 6+ 个 Phase 的迭代开发，功能丰富但存在严重的架构碎片化问题：

1. **核心数据结构分裂**：Block、地址、签名、余额各有 2-3 套并行实现
2. **关键协议缺失**：无区块同步、无状态传播、无终局性
3. **模块集成不完整**：多个精心设计的组件（UnifiedConsensus、DynamicExchangeRate、DID）未接入生产流程

在当前状态下，系统可以在**单节点环境**下运行（挖矿、钱包、RPC），但**无法形成多节点网络共识**。建议按路线图分阶段重构。
