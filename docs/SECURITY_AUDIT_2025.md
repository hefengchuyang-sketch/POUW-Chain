# POUW Multi-Sector Chain — 后端安全审计报告

**审计日期**: 2025 年  
**审计范围**: `core/` 目录下全部 Python 后端代码  
**审计类别**: 共识机制、区块链核心、密码学、经济模型、网络/P2P、治理、RPC 服务  

---

## 漏洞汇总

| # | 严重等级 | 类别 | 简述 |
|---|----------|------|------|
| 1 | **FATAL** | RPC / UTXO | `wallet_transfer` 注册为 PUBLIC 且 UTXO 层允许跳过签名验证 |
| 2 | **FATAL** | RPC / 交易 | `_tx_send` 完全模拟，返回假 txid，无任何链上处理 |
| 3 | **SEVERE** | 密码学 | ECDSA 回退到 HMAC 伪验签，公钥作 HMAC 密钥 |
| 4 | **SEVERE** | 共识 | POUW 区块完全跳过 PoW 难度验证 |
| 5 | **SEVERE** | 共识 | `add_block_no_validate` 跳过所有共识/UTXO 验证 |
| 6 | **HIGH** | RPC | 挖矿控制端点 (start/stop/setMode) 注册为 PUBLIC |
| 7 | **HIGH** | RPC | 钱包敏感操作 (create/import/unlock/exportKeystore) 全部 PUBLIC |
| 8 | **HIGH** | RPC | 本地请求自动授信 (localhost auto-trust) |
| 9 | **HIGH** | 区块链核心 | `blockchain.py` `is_valid()` 不验证 PoW 难度 |
| 10 | **HIGH** | UTXO | `create_exchange_transaction` 凭空创建 UTXO，无源消耗 |
| 11 | **MEDIUM** | 密码学 | 加密任务存在 XOR 回退路径 |
| 12 | **MEDIUM** | 密码学 | 钱包加密密钥基于可预测的机器指纹 |
| 13 | **MEDIUM** | 区块链核心 | `block.py` 哈希使用 `str(self.transactions)` 非确定性序列化 |
| 14 | **MEDIUM** | 共识 | 区块未包含矿工签名，任何人可伪造矿工身份 |
| 15 | **MEDIUM** | 治理 / 仲裁 | 仲裁投票后全局 `random.seed()` 被篡改 |

---

## 详细分析

---

### 漏洞 #1 — FATAL: 转账端点无认证 + UTXO 层跳过签名验证

**类别**: RPC 服务 / UTXO 核心  
**文件/行号**:  
- [core/rpc_service.py](core/rpc_service.py#L411-L414) — `wallet_transfer` 注册为 `RPCPermission.PUBLIC`  
- [core/utxo_store.py](core/utxo_store.py#L316-L322) — 未提供 public_key 时仅输出 warning 并继续执行  

**描述**:  
`wallet_transfer` RPC 方法被注册为 `RPCPermission.PUBLIC`（第 411 行注释称"通过钱包连接状态验证"），这意味着 `_check_permission()` 对该方法直接返回 `True`，不做任何身份检查。虽然 `rpc/server.py` 的 `do_POST` 中对 `AUTHENTICATED_WRITE_METHODS` 集合做了额外的 `role == 'guest'` 拦截，但 `wallet_transfer` 同时也出现在 `AUTHENTICATED_WRITE_METHODS` 集合中，这造成**两套规则相互矛盾**——注册权限是 PUBLIC，但 server 层又要求非 guest。

更严重的是，即使请求到达了 UTXO 层，`create_transfer()` 在调用方未提供 `public_key` 参数时**仅记录一条 warning 日志就放行**（第 316-322 行），不做任何签名验证。攻击者只需构造不带 `public_key` 和 `signature` 字段的请求即可绕过验证。

**攻击场景**:
```
POST /rpc
{
  "jsonrpc": "2.0",
  "method": "wallet_transfer",
  "params": {
    "to_address": "attacker_addr",
    "amount": 999999,
    "sector": "MAIN"
  },
  "id": 1
}
```
无需 API Key、无需签名，只要知道某个有余额的地址即可发起转账。

**修复建议**:
1. 将 `wallet_transfer` 权限改为 `RPCPermission.USER`，并在 `_check_permission` 中验证 `auth_context['user_address']` 与转账发起地址一致。
2. `utxo_store.py` 的 `create_transfer()` **必须**在未提供签名/公钥时直接返回失败，而非仅记录 warning。

---

### 漏洞 #2 — FATAL: `_tx_send` 完全模拟，返回虚假交易 ID

**类别**: RPC 服务 / 交易  
**文件/行号**: [core/rpc_service.py](core/rpc_service.py#L1664-L1682)  

**描述**:  
核心的交易发送方法 `_tx_send` 内部完全是模拟实现：直接使用 `uuid.uuid4()` 生成假的 txid，不做任何签名验证、余额检查、UTXO 消耗或区块打包。代码如下：

```python
def _tx_send(self, params: Dict) -> Dict:
    """发送交易"""
    txid = f"tx_{uuid.uuid4().hex[:16]}"
    # ... 直接返回模拟结果
```

这意味着通过 `tx_send` 接口发送的交易**不会记录到任何区块链状态中**，客户端拿到的 txid 无法在链上查询到真实状态。

**攻击场景**:
- 任何人发送 `tx_send` 会收到"成功"的假 txid，导致前端/用户误以为交易已确认。
- 可用于"确认欺诈"：向用户展示虚假的交易确认。

**修复建议**:
将 `_tx_send` 重写为调用 UTXO store 的 `create_transfer` 方法，执行完整的签名验证→UTXO 选择→交易创建→广播到内存池的流程。或者在生产部署前标记该接口为不可用。

---

### 漏洞 #3 — SEVERE: ECDSA 库缺失时回退到 HMAC 伪签名验证

**类别**: 密码学  
**文件/行号**: [core/crypto.py](core/crypto.py#L247-L264)  

**描述**:  
当 `ecdsa` Python 库未安装时，`ECDSASigner` 的 `verify()` 回退到使用 HMAC-SHA256，**将「公钥」作为 HMAC 密钥**：

```python
# 模拟验证（使用 HMAC 作为简化签名验证）
mac = hmac.new(public_key, message, hashlib.sha256).digest()
# 在模拟模式下，只要签名长度正确就通过
return len(signature) == 64
```

实际上验证逻辑只检查签名长度是否为 64 字节，完全不做密码学验证。这意味着在没有 ecdsa 库的环境中，**任何 64 字节的随机数据都能通过签名验证**。

同时 `sign()` 的回退模式也使用 HMAC（用私钥作为 HMAC key），生成的签名可被任何获得私钥的人验证——但由于 `verify()` 根本不验证 HMAC 值，所以签名形同虚设。

**攻击场景**:
部署环境未安装 `ecdsa` 库（例如 `requirements.txt` 中依赖安装失败但服务启动未阻断），攻击者可以用任意 64 字节数据伪造任何地址的签名。

**修复建议**:
1. 删除回退逻辑，在 `ecdsa` 库缺失时 **raise ImportError** 阻止服务启动。
2. 在 `main.py` 或启动脚本中添加关键依赖检查。

---

### 漏洞 #4 — SEVERE: POUW 区块完全跳过工作量证明验证

**类别**: 共识机制  
**文件/行号**: [core/consensus.py](core/consensus.py#L780-L784)  

**描述**:  
在 `mine_pouw()` 方法中，POUW 区块的出块逻辑为：

```python
block.nonce = random.randint(0, 1000000)
block.hash = block.compute_hash()
```

**没有任何难度目标检查**。只要收集到足够的 POUW proof（`total_work >= 50.0`），就直接用随机 nonce 算一个 hash 作为区块哈希。而在 `validate_block()` 中（第 870 行左右），PoW 难度验证**仅对 `consensus_type == POW` 的区块执行**，POUW 区块走的是单独分支，不检查哈希前导零。

**攻击场景**:
恶意矿工可以提交伪造的 POUW proof（quality_score 和 execution_time 都是自报的，未经独立验证者二次确认），在 `total_work` 达到 50 后直接出块，**无需消耗任何计算资源**。

**修复建议**:
1. POUW 区块也应包含最低难度要求（即使低于纯 PoW）。
2. POUW proof 必须经过**独立验证节点**的二次计算确认，而非仅检查矿工自报的 `quality_score > 0`。

---

### 漏洞 #5 — SEVERE: `add_block_no_validate` 跳过全部共识/UTXO 验证

**类别**: 共识机制  
**文件/行号**: [core/consensus.py](core/consensus.py#L1066-L1095)  

**描述**:  
此方法用于区块同步场景，仅检查：
- `block.height` 是否等于 `latest_height + 1`
- `block.prev_hash` 是否匹配
- `block.hash` 是否非空

**不验证**：PoW 难度、交易签名、UTXO 双花、coinbase 金额、merkle root。

**攻击场景**:
恶意节点向其他节点推送包含非法交易（如凭空增发 coinbase、双花 UTXO）的区块。接收方通过 `receive_block_from_peer` → `add_block_no_validate` 直接接受并写入链中。

**修复建议**:
1. 将 `add_block_no_validate` 改为仅在初始同步且已验证检查点（checkpoint）的场景下使用。
2. 正常的节点间区块同步**必须**走完整的 `add_block()` 路径。

---

### 漏洞 #6 — HIGH: 挖矿控制端点注册为 PUBLIC

**类别**: RPC 服务  
**文件/行号**: [core/rpc_service.py](core/rpc_service.py#L449-L462)  

**描述**:  
`mining_start`、`mining_stop`、`mining_setMode` 均注册为 `RPCPermission.PUBLIC`。虽然注释称"通过钱包连接状态验证"，但 `_check_permission()` 对 PUBLIC 直接返回 True，不做任何钱包连接检查。

**攻击场景**:
攻击者可以远程调用 `mining_stop` 使目标节点停止挖矿，或者使用 `mining_setMode` 改变矿工策略，影响网络算力分布。

**修复建议**:
将挖矿控制方法的权限改为 `RPCPermission.MINER` 或 `RPCPermission.USER`，确保只有认证后的矿工本人可控制。

---

### 漏洞 #7 — HIGH: 钱包全部操作注册为 PUBLIC

**类别**: RPC 服务  
**文件/行号**: [core/rpc_service.py](core/rpc_service.py#L385-L425)  

**描述**:  
以下方法全部注册为 `RPCPermission.PUBLIC`：
- `wallet_create` — 创建新钱包
- `wallet_import` — 从助记词导入
- `wallet_unlock` — 解锁钱包
- `wallet_lock` — 锁定钱包
- `wallet_exportKeystore` — **导出加密密钥文件**
- `wallet_importKeystore` — 从密钥文件导入

`wallet_exportKeystore` 尤其危险，允许未认证用户导出钱包密钥文件。

**攻击场景**:
1. 攻击者调用 `wallet_exportKeystore` 获取节点上已连接钱包的加密密钥文件。
2. 对密钥文件进行离线暴力破解密码。
3. 获取私钥后完全控制钱包资产。

**修复建议**:
`wallet_exportKeystore` 至少需要 `RPCPermission.USER` 并验证调用者身份。`wallet_unlock` 也应限制频率以防暴力破解。

---

### 漏洞 #8 — HIGH: 本地请求自动授信 (Localhost Auto-Trust)

**类别**: RPC 服务  
**文件/行号**: [core/rpc/server.py](core/rpc/server.py#L118-L126)  

**描述**:  
RPC HTTP Handler 中，来自 `127.0.0.1` 的请求自动获得 `role='local'` 和 `is_local=True` 标识。在 `do_POST` 处理中，`is_local` 的请求可能跳过某些认证检查。

**攻击场景**:
在同一台服务器上运行的**任何进程**（包括被攻破的其他服务、恶意容器逃逸等）都可以通过本地回环地址绕过认证。在共享服务器或容器化部署中风险尤为突出。

**修复建议**:
1. 移除 localhost 自动授信，改为基于 API Key 或 token 的统一认证。
2. 如需保留本地管理通道，应使用 Unix Domain Socket 并限制文件权限。

---

### 漏洞 #9 — HIGH: `blockchain.py` 链验证不检查 PoW 难度

**类别**: 区块链核心  
**文件/行号**: [core/blockchain.py](core/blockchain.py)  

**描述**:  
`Blockchain.is_valid()` 仅检查：
1. 每个区块的 `previous_hash` 等于前一区块的实际 hash
2. 区块的 `hash` 等于 `compute_hash()` 的结果

**不检查**哈希是否满足当时的难度目标。攻击者可以构造一条哈希有效但完全不满足难度要求的假链。

**攻击场景**:
在链重组对比中，攻击者提交一条极易计算的长链（每个区块难度为 0），节点在 `is_valid()` 检查后将其视为合法链。

**修复建议**:
在 `is_valid()` 中增加难度验证：检查 `block.hash` 的前 N 位是否满足 `block.difficulty` 要求。

---

### 漏洞 #10 — HIGH: 兑换交易凭空创建 UTXO

**类别**: UTXO 核心  
**文件/行号**: [core/utxo_store.py](core/utxo_store.py#L700) (大约)  

**描述**:  
`create_exchange_transaction()` 用于处理板块币兑换为 MAIN 币的操作。该方法创建 MAIN 币的新 UTXO 给用户，但对应的板块币**没有真正消耗/销毁源 UTXO**，而是使用 "virtual input" 虚拟输入。

**攻击场景**:
通过反复调用兑换接口，可以将同一笔板块币反复兑换为 MAIN 币，实现无限增发。

**修复建议**:
兑换操作必须原子性地消耗源板块币 UTXO 并创建目标 MAIN UTXO，保持总量守恒。

---

### 漏洞 #11 — MEDIUM: 加密任务存在 XOR 回退路径

**类别**: 密码学  
**文件/行号**: [core/encrypted_task.py](core/encrypted_task.py#L200-L250) (大约)  

**描述**:  
`HybridEncryption` 在 RSA/AES-GCM 不可用时回退到 XOR"加密"：

```python
encrypted = bytes(a ^ b for a, b in zip(data, key_extended))
```

XOR 使用短密钥循环扩展（repeating key XOR），可被频率分析等经典方法在多项式时间内破解。虽然代码注释称生产模式会阻断此路径，但该检查仅在模块加载时执行，运行时可被绕过。

**攻击场景**:
如果在生产环境中 `cryptography` 库加载失败（例如 C 扩展编译问题），系统会静默降级到 XOR，敏感计算任务数据将以极弱加密传输。

**修复建议**:
删除 XOR 回退逻辑；`cryptography` 库缺失时应直接 raise 而非降级。

---

### 漏洞 #12 — MEDIUM: 钱包加密基于可预测的机器指纹

**类别**: 密码学  
**文件/行号**: [core/security.py](core/security.py#L440-L470) (大约)  

**描述**:  
`WalletEncryptor` 使用 `_get_machine_key()` 方法将**主机名 + 平台信息 + MAC 地址**拼接后取 SHA-256 作为 AES-GCM 密钥的一部分。这些信息均可公开获取或推测。

**攻击场景**:
攻击者获取到加密的钱包文件后，只需知道目标机器的主机名和平台信息（通常可通过 OSINT 获取），即可重建密钥并解密钱包。

**修复建议**:
使用由用户提供的密码（passphrase）+ PBKDF2/Argon2 派生密钥，不依赖可预测的机器信息。

---

### 漏洞 #13 — MEDIUM: 区块哈希使用非确定性序列化

**类别**: 区块链核心  
**文件/行号**: [core/block.py](core/block.py)  

**描述**:  
`Block.compute_hash()` 使用 `str(self.transactions)` 将交易列表序列化后参与哈希计算。如果交易是 dict 类型，在 Python 3.7+ 中 dict 是有序的，但如果交易内部存在嵌套或从不同来源反序列化，字段顺序可能不一致，导致不同节点对同一区块计算出不同的哈希。

**攻击场景**:
两个节点对同一区块计算出不同的哈希，导致共识分裂和链分叉。

**修复建议**:
使用 `json.dumps(self.transactions, sort_keys=True, separators=(',', ':'))` 进行确定性序列化。

---

### 漏洞 #14 — MEDIUM: 区块无矿工签名，矿工身份可伪造

**类别**: 共识机制  
**文件/行号**: [core/consensus.py](core/consensus.py#L30-L70) — Block dataclass 定义  

**描述**:  
`Block` 数据类中 `miner_id` 字段仅为字符串，区块中**不包含矿工的数字签名**。`compute_hash()` 虽然将 `miner_id` 纳入哈希输入，但由于没有签名，任何人都可以用任意 `miner_id` 创建区块并自行计算 hash。

**攻击场景**:
攻击者冒充高声誉矿工身份出块，获取该矿工的声誉奖励加成，同时将恶意交易打包入块。

**修复建议**:
Block 结构中增加 `miner_signature` 字段，`validate_block()` 在接受区块前验证签名与 `miner_id` 对应的公钥是否匹配。

---

### 漏洞 #15 — MEDIUM: 仲裁投票篡改全局随机种子

**类别**: 治理 / 仲裁  
**文件/行号**: [core/arbitration.py](core/arbitration.py#L289-L292)  

**描述**:  
`_initiate_voting()` 方法中：

```python
seed = int(hashlib.sha256(dispute.task_id.encode()).hexdigest()[:8], 16)
random.seed(seed)
selected = random.sample(eligible, ...)
```

调用 `random.seed()` 设置了**全局**随机种子。这会影响同一进程中所有使用 `random` 模块的地方，包括共识模块（POUW 区块的 `random.randint` nonce 计算）。

**攻击场景**:
1. 攻击者提交一个精心构造 task_id 的仲裁请求。
2. 全局随机种子被设置为已知值。
3. 攻击者可以预测后续所有 `random` 调用的输出，包括 POUW 区块的 nonce 和其他随机决策。

**修复建议**:
使用 `random.Random(seed)` 创建独立的局部 Random 实例，或使用 `secrets` 模块。

---

## 架构级问题

### A1 — 网络层为纯模拟

**文件**: [core/network.py](core/network.py), [core/node.py](core/node.py)  

`NetworkSimulator` 基于 Python 线程和 `queue.Queue` 实现节点间通信，**不是真正的 P2P 网络**。在真实部署中：
- 无节点发现机制（无 DHT/Kademlia）
- 无 Eclipse 攻击防护
- 无消息签名/验证
- 无 Sybil 防护

### A2 — 权限模型矛盾

**文件**: [core/rpc_service.py](core/rpc_service.py) 注册处 vs [core/security.py](core/security.py) 中 `PUBLIC_RPC_METHODS` / `AUTHENTICATED_WRITE_METHODS`

权限被定义在三个不同位置：
1. `rpc_service.py` 中的 `RPCPermission` 注册
2. `security.py` 中的 `PUBLIC_RPC_METHODS` 集合
3. `rpc/server.py` 中的 `AUTHENTICATED_WRITE_METHODS` 硬编码检查

三者之间不同步，导致同一方法可能在不同层获得不同的权限判定。

### A3 — 无交易内存池 (Mempool)

系统不存在独立的 mempool 机制。`_tx_send` 是模拟的（见漏洞 #2），`wallet_transfer` 直接在 UTXO store 中即时执行，没有交易排队、费率竞争、或替换（RBF）机制。这意味着交易没有经过区块确认就已经在 UTXO 层生效。

---

## 优先修复路线图

```
阶段一（紧急 — 部署前必须修复）:
  ├── #1  修复 wallet_transfer 权限 + UTXO 签名强制验证
  ├── #2  实现真正的 _tx_send 或禁用该端点
  ├── #3  删除 ECDSA HMAC 回退，强制依赖 ecdsa 库
  └── #7  将敏感钱包操作权限改为 USER

阶段二（高优先级 — 上线前修复）:
  ├── #4  POUW 区块增加最低难度 + 独立验证
  ├── #5  add_block_no_validate 改为仅限特定同步场景
  ├── #6  挖矿控制端点改为 MINER 权限
  ├── #8  移除 localhost 自动授信
  ├── #9  blockchain.py 增加难度验证
  └── #10 修复兑换交易的 UTXO 守恒

阶段三（中期 — 迭代改进）:
  ├── #11 删除 XOR 加密回退
  ├── #12 钱包加密改用密码派生密钥
  ├── #13 使用确定性 JSON 序列化
  ├── #14 增加区块矿工签名
  ├── #15 修复全局随机种子污染
  └── 架构：统一权限模型，实现 mempool
```

---

*本报告仅覆盖静态代码审计，不包含动态渗透测试。建议在修复后进行完整的安全测试。*
