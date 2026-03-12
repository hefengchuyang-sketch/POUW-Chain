# POUW 区块链安全审计报告

**审计日期**: 2025-01  
**审计范围**: `core/*.py` 全部核心模块  
**排除项**: 已修复的18个已知问题  

---

## 一、CRITICAL（严重）

### C-1: 敏感 RPC 方法注册为 PUBLIC，缺乏真正认证

**文件**: [rpc_service.py](core/rpc_service.py#L380-L453)  
**描述**: `wallet_create`、`wallet_import`、`wallet_transfer`、`wallet_exportKeystore`、`wallet_importKeystore`、`miner_register`、`miner_updateProfile`、`mining_start`、`mining_stop` 等敏感写操作全部注册为 `RPCPermission.PUBLIC`。注释声称 "通过钱包连接状态验证"，但 `_check_permission()` 对 PUBLIC 方法 **直接返回 True 不做任何检查**（[见第1654行](core/rpc_service.py#L1654)）。

**攻击向量**: 任何人无需认证即可调用 `wallet_transfer` 转移连接钱包的资金、`mining_start/stop` 控制他人挖矿。  

**建议修复**: 将所有写操作改为 `RPCPermission.USER` 或 `RPCPermission.MINER`，并在 `_check_permission` 中要求签名验证。

---

### C-2: Keystore 导入后使用 SSH_PASSWORD 环境变量作为钱包密码

**文件**: [rpc_service.py](core/rpc_service.py#L2307)  
**描述**: `_wallet_import_keystore()` 成功解密 keystore 获取助记词后，调用 `self._wallet_import(mnemonic=mnemonic, password=os.environ.get("SSH_PASSWORD", ""))` — 直接读取系统 SSH 密码作为钱包恢复密码。

**攻击向量**:  
1. **凭证泄露**: SSH 密码通过 RPC 响应链路可能暴露  
2. **错误密钥派生**: 用户的 keystore 密码被替换为无关的 SSH_PASSWORD，导致生成错误的地址或覆盖正确的钱包  
3. 若 `SSH_PASSWORD` 为空字符串，则使用空密码恢复钱包

**建议修复**: 使用用户提供的 `password` 参数，删除对 `SSH_PASSWORD` 的引用。

---

### C-3: DAO 多签提款使用字符串包含检查替代密码学签名验证

**文件**: [dao_treasury.py](core/dao_treasury.py#L260-L290)（`execute_withdrawal` 方法）  
**描述**: `execute_withdrawal()` 通过 `if signer in self.multisig_signers` 检查签名者身份 — 这仅是检查字符串是否在列表中，**没有任何密码学签名验证**。

**攻击向量**: 任何知道或猜到签名者名称（如 "admin", "node1"）的人可以伪造多签提款，直接从 DAO 国库提取资金。  

**建议修复**: 要求每个签名者提供真实的 ECDSA 签名，并用其公钥验证。

---

### C-4: 治理 `_apply_parameter_change` 使用无限制 setattr

**文件**: [dao_treasury.py](core/dao_treasury.py#L637)  
**描述**: `_apply_parameter_change(parameter, new_value)` 直接调用 `setattr(self.config, parameter, new_value)` ，`parameter` 来自提案中的用户输入，**无白名单过滤**。

**攻击向量**: 攻击者可通过治理提案修改任意配置属性 — 包括 `multisig_signers`（多签列表）、`min_stake_to_propose`（设为0允许免费提案）、`quorum_percent`（设为0.001%绕过法定人数）等，从而完全控制治理系统。  

**建议修复**: 添加可修改参数白名单（`ALLOWED_GOVERNANCE_PARAMS`），拒绝不在白名单中的参数修改。

---

### C-5: `contrib_finalizeProposal` 和 `contrib_executeProposal` 注册为 PUBLIC

**文件**: [rpc_service.py](core/rpc_service.py#L611-L621)  
**描述**: 提案结算 (`contrib_finalizeProposal`) 和提案执行 (`contrib_executeProposal`) 都注册为 `RPCPermission.PUBLIC`，任何人可以在投票期结束后执行提案。

**攻击向量**: 攻击者可以趁没人注意时执行恶意提案（包括国库支出），无需任何身份验证。  

**建议修复**: `contrib_executeProposal` 改为 `RPCPermission.ADMIN`，或至少增加执行者身份验证。

---

## 二、HIGH（高危）

### H-1: `wallet_transfer` 实现引用未定义变量 `params`

**文件**: [rpc_service.py](core/rpc_service.py#L2478-L2479)  
**描述**: `_wallet_transfer()` 方法签名使用关键字参数 `(self, toAddress, amount, sector, memo, **kwargs)`，但方法体中引用了 `params.get('signature', '')` — `params` 在此作用域内未定义。

**攻击向量**: 所有通过 `wallet_transfer` 的转账都会因 `NameError` 崩溃，或者 `signature` 和 `public_key` 永远为空字符串。结合 `utxo_store.create_transfer` 在无 `public_key` 时跳过签名验证（仅打印警告），**所有转账都无需签名即可执行**。

**建议修复**: 从 `**kwargs` 中提取 `signature` 和 `public_key`，确保签名验证必须通过。

---

### H-2: UTXO 转账在无 public_key 时跳过签名验证

**文件**: [utxo_store.py](core/utxo_store.py#L340-L360)（`create_transfer` 方法）  
**描述**: `create_transfer()` 中，当 `public_key` 参数为空/未提供时，仅打印 `"⚠️ 未提供公钥，跳过签名验证"` 的警告就继续执行转账。

**攻击向量**: 配合 H-1 漏洞，所有 RPC 转账调用都不会传递 public_key，导致所有转账完全绕过密码学签名验证。  

**建议修复**: 在生产模式下，缺少 `public_key` 或 `signature` 时应拒绝交易，而非仅打印警告。

---

### H-3: 双见证引擎交易数据仅存内存，重启丢失

**文件**: [double_witness.py](core/double_witness.py)  
**描述**: `DoubleWitnessEngine` 将 `pending_transactions`、`confirmed_transactions` 和 `witnesses` 全部存储在内存字典中，没有持久化。

**攻击向量**: 节点重启后，所有未完成的双见证交易丢失，可能导致资金被锁定（扣款已执行但见证未记录），或被利用发起双重见证攻击。  

**建议修复**: 将见证交易状态持久化到 SQLite。

---

### H-4: treasury.py / protocol_fee_pool.py 所有状态仅在内存中

**文件**: [treasury.py](core/treasury.py)、[protocol_fee_pool.py](core/protocol_fee_pool.py)  
**描述**: `ProtocolFeePool` 和 `FeeDistributionEngine` 的全部状态（`total_burned`、`pool_balance`、`foundation_balance`、分配历史）完全存储在 Python 对象属性中，没有任何持久化。

**攻击向量**: 节点重启后，销毁记录和协议池余额归零，通缩机制失效，费用被重复分配。  

**建议修复**: 使用 SQLite 持久化所有费用池状态。

---

### H-5: consensus.py `receive_block_from_peer` 接受对端发送的难度值

**文件**: [consensus.py](core/consensus.py)（`receive_block_from_peer` 方法）  
**描述**: 从 peer 接收区块时，直接使用区块中携带的 difficulty 值更新本地共识难度，没有独立验证该难度值是否符合本地计算的难度调整规则。

**攻击向量**: 恶意节点可以发送低难度区块，降低网络共识门槛，加速51%攻击或制造大量廉价区块。  

**建议修复**: 接收 peer 区块时，独立计算预期难度并验证接收到的难度是否匹配。

---

### H-6: unified_consensus.py `_encrypt_payload` 使用 XOR 弱加密

**文件**: [unified_consensus.py](core/unified_consensus.py#L1014-L1020)  
**描述**: `_encrypt_payload()` 注释说 "简化实现，生产环境使用 AES-256-GCM"，但实际使用的是 XOR 对称加密 — 密钥流仅为 SHA-256 哈希的32字节循环使用。

**攻击向量**: 攻击者获取加密数据后，可通过已知明文攻击（JSON 结构可预测）轻松恢复密钥，窃取所有 "安全任务信封" 中的任务数据和用户信息。  

**建议修复**: 使用真正的 AES-256-GCM 加密，而非 XOR 回退。

---

### H-7: dual_witness_exchange.py 内存余额字典与数据库余额可能不一致

**文件**: [dual_witness_exchange.py](core/dual_witness_exchange.py)  
**描述**: `DualWitnessExchange` 同时维护内存字典 `_main_balances` 和数据库表 `main_balances`。`_get_main_balance()` 在 `unified_consensus.py` 中仅读取内存字典，写操作同时更新两处但非原子性。

**攻击向量**: 在并发场景下，内存和数据库的 MAIN 余额可能出现不一致，导致双花或余额凭空增加。  

**建议修复**: 使用单一数据源（数据库），消除冗余的内存字典。

---

### H-8: 浮点数用于金融计算，精度损失导致余额漂移

**文件**: [account.py](core/account.py)、[sector_coin.py](core/sector_coin.py)、[exchange_rate.py](core/exchange_rate.py)、[treasury.py](core/treasury.py)  
**描述**: 全项目使用 `float` 类型进行货币金额运算（加减乘除），包括余额、手续费、汇率计算。`float` 的 IEEE 754 精度约为小数点后 15-17 位，大量累积运算会导致漂移。

**攻击向量**: 通过精心构造的大量小额交易，利用浮点精度舍入错误，人为制造余额差异或绕过余额不足检查。例如 `0.1 + 0.2 != 0.3` 可导致 `current < amount` 检查异常通过。

**建议修复**: 使用 `decimal.Decimal` 或整数（如 satoshi 单位）表示金额。

---

## 三、MEDIUM（中等）

### M-1: wallet.py 开发模式签名验证接受任意64字符字符串

**文件**: [wallet.py](core/wallet.py#L300-L310)  
**描述**: 非生产环境下 `verify_signature()` 仅检查 `len(signature) == 64` 即返回 True。

**攻击向量**: 开发/测试网环境下，任何人可以用 64 个 "a" 字符作为签名通过验证。若 `POUW_ENV` 未正确配置为 production，主网也会使用此弱验证。  

**建议修复**: 即使在开发模式，也应进行实际的签名验证，或在环境变量检查中使用安全默认值（默认=production）。

---

### M-2: consensus.py 挖矿使用 `random` 模块而非 `secrets`

**文件**: [consensus.py](core/consensus.py#L781)  
**描述**: `mine_pouw()` 使用 `random.randint(0, 1000000)` 生成 nonce，`random` 模块使用 Mersenne Twister 伪随机数生成器，可被预测。

**攻击向量**: 其他矿工可以预测竞争者的 nonce 搜索空间，获得挖矿优势。  

**建议修复**: 使用 `secrets.randbelow()` 替代。

---

### M-3: compute_scheduler.py 存储加密密钥硬编码

**文件**: [compute_scheduler.py](core/compute_scheduler.py#L981)  
**描述**: `_STORAGE_KEY_SEED = "POUW_SCHEDULER_STORAGE_KEY_2026"` 硬编码在源码中，且 PBKDF2 仅使用 1000 次迭代。

**攻击向量**: 任何获取源码的人可以解密所有本地存储的任务数据。  

**建议修复**: 从安全配置文件或 HSM 加载密钥种子，增加 PBKDF2 迭代次数至至少 310000。

---

### M-4: treasury_manager.py `verify_audit_record` 是破坏性操作

**文件**: [treasury_manager.py](core/treasury_manager.py#L200-L220)  
**描述**: `AuditTrail.verify_audit_record()` 使用 `record.pop("hash")` 从记录字典中移除哈希字段，导致原始数据被修改。第二次验证同一记录会因为缺少 hash 字段而失败或产生错误。

**攻击向量**: 审计记录验证后变得不可再验证，破坏审计追溯能力。  

**建议修复**: 使用 `record_copy = dict(record); hash_value = record_copy.pop("hash")`，不修改原始字典。

---

### M-5: double_witness.py 使用 `random.sample` 选择见证节点

**文件**: [double_witness.py](core/double_witness.py)  
**描述**: `select_witnesses()` 使用 `random.sample()` 从候选列表中选择见证节点。`random` 模块可预测。

**攻击向量**: 恶意节点可以预测见证者选择结果，提前控制被选中的见证节点实施串谋攻击。  

**建议修复**: 使用 `secrets.SystemRandom().sample()` 或基于区块哈希的 VRF 方案。

---

### M-6: miner.py 新矿工默认满分信任

**文件**: [miner.py](core/miner.py)  
**描述**: `average_pouw_score()` 在矿工没有任何历史记录时返回 1.0（满分），新注册矿工立即获得最高优先级。

**攻击向量**: 攻击者可以不断创建新矿工 ID 获取高优先级任务分配（Sybil attack）。  

**建议修复**: 新矿工默认分数应设为 0.5 或更低，通过实际表现逐步提升。

---

### M-7: sandbox_executor.py 执行证明验证仅检查长度

**文件**: [sandbox_executor.py](core/sandbox_executor.py#L270-L280)  
**描述**: `verify_proof()` 对所有环境类型（TEE、ZK、FHE）仅检查 `len(proof_data) == 24` 即认为有效。

**攻击向量**: 矿工可以生成任意 24 字符的字符串作为 "执行证明" 通过验证，无需实际在安全环境中执行任务。  

**建议修复**: 实现真正的密码学证明验证：TEE 远程认证、ZK 证明验证等。

---

### M-8: exchange_rate.py 汇率状态仅在内存中

**文件**: [exchange_rate.py](core/exchange_rate.py)  
**描述**: `DynamicExchangeRate` 的所有汇率历史、板块指标和兑换订单都存储在内存中。

**攻击向量**: 节点重启后汇率重置为基础值，攻击者可以在重启后立即利用偏差汇率进行套利。  

**建议修复**: 持久化汇率历史和当前汇率到数据库。

---

### M-9: account.py 使用 float 且无持久化

**文件**: [account.py](core/account.py)  
**描述**: `Account` 类的所有余额（`block_balances`、`main_balance`、`frozen_main`）都是 float 类型的内存属性。

**攻击向量**: 除 H-8 所述的浮点精度问题外，`freeze_main` 不检查 `amount <= 0` 的情况，负数金额冻结可增加可用余额。  

**建议修复**: 添加 `amount > 0` 检查。

---

### M-10: blind_task_engine.py CAMOUFLAGE_SECRET 在模块加载时生成

**文件**: [blind_task_engine.py](core/blind_task_engine.py#L68)  
**描述**: `CAMOUFLAGE_SECRET = os.urandom(32)` 每次进程启动生成新密钥。

**攻击向量**: 节点重启后已分配的 camouflaged task ID 无法验证/关联到原始任务，导致盲任务结果验证失败。  

**建议修复**: 从持久化配置加载 CAMOUFLAGE_SECRET 或使用确定性派生。

---

### M-11: rpc_service.py `_wallet_create` 在内存中保留助记词

**文件**: [rpc_service.py](core/rpc_service.py#L2101)  
**描述**: `self.wallet_info = wallet_info` 将包含助记词的完整钱包信息保存为 RPC 服务实例的属性。任何其他 RPC 方法或内存转储都可以访问这些数据。

**攻击向量**: 进程内存转储、core dump 或其他 RPC 方法可以获取明文助记词。  

**建议修复**: 仅保留地址和签名所需的最小密钥材料，助记词返回后立即清除。

---

### M-12: `_wallet_transfer` 使用共享 `self.miner_address` 作为发送方

**文件**: [rpc_service.py](core/rpc_service.py#L2422-L2540)  
**描述**: 所有转账以 `self.miner_address`（服务实例的当前钱包地址）作为发送方。如果多个客户端并发操作，一个客户端的连接钱包可被另一客户端的转账请求使用。

**攻击向量**: Race condition — 用户 A 连接钱包后，用户 B 调用 `wallet_transfer` 可使用用户 A 的地址发起转账。  

**建议修复**: 转账时应从请求的认证上下文获取发送方地址，不依赖全局共享状态。

---

## 四、总结

| 等级 | 数量 | 关键主题 |
|------|------|----------|
| **CRITICAL** | 5 | RPC 无认证、SSH凭证泄露、多签伪造、治理参数注入、公开执行提案 |
| **HIGH** | 8 | 签名验证绕过、内存状态丢失、弱加密、浮点精度、难度操纵 |
| **MEDIUM** | 12 | 伪随机数、硬编码密钥、证明验证缺失、单点状态、竞态条件 |

### 最优先修复路径

1. **立即**: C-1 + C-2 + C-3 — 阻止未授权资金操作
2. **紧急**: H-1 + H-2 — 修复签名验证链路
3. **尽快**: C-4 + C-5 — 防止治理系统被劫持
4. **短期**: H-3 + H-4 — 持久化关键状态
5. **中期**: H-8 + M-3 — 修复浮点和密钥管理
