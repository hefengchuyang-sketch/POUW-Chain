# Core 模块安全审计报告

**审计日期**: 2026-03-04  
**审计范围**: `core/` 目录所有 `.py` 文件（含子目录 `rpc/`, `rpc_handlers/`）  
**严重等级**: CRITICAL > HIGH > MEDIUM > LOW

---

## 摘要统计

| 类别 | CRITICAL | HIGH | MEDIUM | LOW | 合计 |
|------|----------|------|--------|-----|------|
| 1. 裸 except / 静默吞异常 | 0 | 1 | 1 | 0 | 2 |
| 2. 安全函数始终返回 True | 2 | 1 | 1 | 0 | 4 |
| 3. 关键路径 TODO | 2 | 2 | 1 | 0 | 5 |
| 4. 硬编码凭证 | 0 | 0 | 0 | 1 | 1 |
| 5. 非安全随机数 | 0 | 0 | 0 | 1 | 1 |
| 6. 开发模式绕过 | 2 | 2 | 1 | 0 | 5 |
| 7. 加密模块依赖分析 | - | - | - | - | (信息) |
| **合计** | **6** | **6** | **4** | **2** | **18** |

---

## 1. 裸 `except:` 或 `except: pass` — 静默吞异常

### 1.1 [HIGH] `core/rpc/server.py` L342 — `except: pass` 在错误解析中

```python
# L336-344
except urllib.error.HTTPError as e:
    error_data = e.read().decode('utf-8')
    try:
        error_json = json.loads(error_data)
        if 'error' in error_json:
            raise RPCError(error_json['error']['code'], error_json['error']['message'])
    except:          # ← 裸 except，吞掉所有异常（包括 KeyboardInterrupt, SystemExit）
        pass         # ← 静默忽略，可能隐藏 JSON 解析错误或键缺失
    raise RPCError(RPCErrorCode.INTERNAL_ERROR.value, str(e))
```

**风险**: JSON 解析失败或结构不匹配时，错误细节被完全丢弃。如果 `error_json['error']` 抛出 KeyError，真正的错误信息丢失。  
**修复建议**: 改为 `except (json.JSONDecodeError, KeyError, TypeError): pass`

---

### 1.2 [MEDIUM] `core/rpc/server.py` L354 — `is_connected()` 裸 except

```python
# L350-356
def is_connected(self) -> bool:
    try:
        self.call('node_getInfo', {})
        return True
    except:          # ← 裸 except，包括 KeyboardInterrupt
        return False
```

**风险**: `KeyboardInterrupt` 和 `SystemExit` 等不可恢复异常被静默捕获。  
**修复建议**: 改为 `except Exception:` 或更具体的 `except (ConnectionError, RPCError, OSError):`

---

## 2. 安全/验证函数始终返回 True（绕过安全检查）

### 2.1 [CRITICAL] `core/compute_market_v3.py` L1211-1216 — TEE 远程证明验证始终返回 True

```python
# L1211-1216
elif validation_type == ValidationType.TEE_ATTESTATION:
    # TEE 远程证明
    if order.execution_mode != TaskExecutionMode.TEE:
        return False, "订单未使用 TEE 模式"
    # TODO: 实际 TEE 证明验证
    return True, "TEE 证明验证通过"    # ← 无论传入什么都返回 True
```

**风险**: TEE 远程证明是可信计算安全核心。此函数声称"验证通过"但实际未执行任何验证。恶意矿工可声称使用 TEE 环境获取溢价，但实际未使用。  
**修复建议**: 必须实现真正的 TEE 远程证明验证（Intel SGX DCAP/EPID 或 AMD SEV-SNP 验证）

---

### 2.2 [CRITICAL] `core/zk_verification.py` L627-633 — 通用 ZK 证明验证仅检查非空

```python
# L627-633
def _verify_generic_proof(self, proof: ZKProof) -> bool:
    """通用证明验证"""
    # 基本验证
    if not proof.proof_data:
        return False
    
    return True      # ← 只要 proof_data 非空就通过，无实际数学验证
```

**风险**: ZK 证明验证是隐私计算的安全基础。此函数接受任何非空数据作为"有效证明"。攻击者可提交任意字节串绕过零知识验证。  
**修复建议**: 必须实现对应证明系统的数学验证（Groth16、PLONK 等）

---

### 2.3 [HIGH] `core/data_redundancy.py` L355-364 — 纠删码验证计算后丢弃结果

```python
# L355-364
def verify(self, shards: List[bytes]) -> bool:
    """验证纠删码"""
    if len(shards) != self.total_shards:
        return False
    
    # 验证奇偶校验
    shard_size = len(shards[0])
    expected_parity = bytes(shard_size)
    for shard in shards[:self.data_shards]:
        expected_parity = bytes(a ^ b for a, b in zip(expected_parity, shard))
    
    return True  # 简化验证    # ← 计算了 expected_parity 但从未与实际 parity shard 比较
```

**风险**: 计算了预期奇偶校验值但未与实际奇偶分片比较。数据损坏无法检测。  
**修复建议**: 添加 `return expected_parity == shards[self.data_shards]`（或对全部 parity shards 逐一校验）

---

### 2.4 [MEDIUM] `core/governance_enhanced.py` L496-551 — `_finalize_vote()` 所有分支都返回 True

```python
# 各分支都设置不同 stage 然后 return True：
# L506: proposal.stage = ProposalStage.REJECTED → return True
# L518: participation_rate < quorum → REJECTED → return True
# L531: veto → VETOED → return True
# L551: 最终 → return True
```

**风险**: 较低。此函数表示"结算完成"而非"投票通过"，各分支设置了正确的 stage 状态。返回值仅代表结算操作成功。  
**分类**: 实际为 **LOW（设计如此）**，但建议添加文档注释说明返回值含义

---

## 3. 关键路径 TODO — 未实现的安全/业务逻辑

### 3.1 [CRITICAL] `core/compute_market_v3.py` L1215 — TEE 证明验证未实现

```python
# TODO: 实际 TEE 证明验证
return True, "TEE 证明验证通过"
```

**影响**: TEE 节点获取做任务溢价但可伪造 TEE 环境。与 Finding 2.1 重复。  

---

### 3.2 [CRITICAL] `core/compute_market_v3.py` L1271 — 质押金销毁未实现

```python
# 销毁质押金
if stake_amount > 0:
    staked_rating.stake_burned = True
    # TODO: 实际销毁操作      # ← 标记已销毁但代币未真正销毁
```

**影响**: 评价质押金被标记为销毁但链上余额未扣除。攻击者可反复使用同一笔资金质押评价，操控矿工评分。

---

### 3.3 [HIGH] `core/compute_market_v3.py` L1049 — 结算引擎未集成

```python
# 记录结算（实际应调用链上结算模块）
# TODO: 集成 settlement_engine
```

**影响**: 矿工收益仅在内存/数据库更新，未上链。矿工收益记录可能与链上状态不一致。

---

### 3.4 [HIGH] `core/compute_scheduler.py` L1285-1287 — 三项链上操作未实现

```python
# TODO: 销毁交易上链（减少总供应量）
# TODO: 矿工激励交易上链（分配给区块矿工）
# TODO: 基金会多签转账（透明可追踪）
```

**影响**: 费用分配（销毁 + 矿工激励 + 基金会）仅在本地数据库记录，未通过共识上链。恶意节点可篡改本地结算记录。

---

### 3.5 [MEDIUM] `core/compute_market_v3.py` L1049 — 结算记录未持久化上链

与 3.3 关联。结算记录仅写入 SQLite，未通过区块共识确认。

---

## 4. 硬编码凭证

### 4.1 [LOW] 无真正的硬编码凭证 — 仅占位符

审计扫描了以下模式：`secret`, `password`, `api_key`, `token` + 赋值。

**发现**:
- `core/sdk_api.py` L728: `api_key="YOUR_API_KEY"` — SDK 文档模板占位符 ✓
- `core/sdk_api.py` L745: `"YOUR_API_KEY"` — SDK 文档模板占位符 ✓
- `core/tcp_network.py` L481: `b'POUW_NET_SECRET_v1'` — PBKDF2 salt，非凭证 ✓
- `core/crypto.py` L246: `b"Bitcoin seed"` — BIP32 标准 HMAC key ✓

**结论**: 未发现硬编码的真实密钥、密码或 token。网络密钥通过 `os.urandom(32)` 生成并加密存储。钱包私钥通过 `secrets` 生成。

---

## 5. 非加密安全随机数（`random` 模块）

### 5.1 [LOW] `core/miner.py` L56 — `random.random()` 模拟任务成功率

```python
# L50-56
def execute_task(self) -> bool:
    """模拟执行任务（Phase 3 兼容）。
    Returns:
        是否执行成功（模拟：基于 uptime 的成功率）
    """
    return random.random() < self.uptime
```

**判定**: 此函数明确标注为"模拟"用途（Phase 3 兼容），非生产代码路径。`core/load_testing.py` L260 的 `random.random()` 同理，用于负载测试权重选择。  
**结论**: 所有安全关键路径（密钥生成、签名、随机数）均使用 `secrets` 模块或 `os.urandom()`，符合安全要求。

---

## 6. 开发模式绕过

### 6.1 [CRITICAL] `core/compute_market_v3.py` L196-200 — 签名验证开发模式跳过

```python
# L196-200
def verify_signature(self, miner_public_key: str = "") -> bool:
    if not self.signature or not miner_public_key:
        if _MARKET_PRODUCTION:      # ← 仅当 POUW_ENV=production|mainnet 时拒绝
            return False
        # 开发模式宽容
        return True                 # ← 默认跳过！POUW_ENV 未设置 = 签名验证无效
```

**风险**: `_MARKET_PRODUCTION` 默认为 `False`（需要显式设置 `POUW_ENV=production`）。如果部署时忘记设置环境变量，矿工可无签名注册。  
**修复建议**: 反转默认值 — 应默认为安全模式，仅当 `POUW_ENV=development` 时才放宽

---

### 6.2 [CRITICAL] `core/consensus.py` L776-779 — 交易签名开发模式跳过

```python
# L775-779
except ImportError:
    import os
    if os.environ.get('MAINCOIN_DEV_MODE', '').lower() == 'true':
        pass  # 开发模式：跳过签名验证
    else:
        self.log(f"❌ 交易 {tx_id[:12]} 拒绝：缺少 ecdsa 库")
        return False
```

**风险**: 当 `MAINCOIN_DEV_MODE=true` 时，所有交易签名验证被完全跳过。如果此环境变量被意外设置到生产环境，将允许任何未签名交易。  
**安全注意**: 此处使用了独立的环境变量 `MAINCOIN_DEV_MODE`（而非 `POUW_ENV`），增加了配置混乱风险。  
**修复建议**: 统一环境变量；生产环境明确检查 `MAINCOIN_PRODUCTION=true` 时禁止跳过

---

### 6.3 [HIGH] `core/rpc_service.py` L3474-3476 — 自动见证开发模式绕过

```python
# L3471-3486
# Security: auto-witness ONLY in development mode (MAINCOIN_PRODUCTION != "true")
import os
is_production = os.environ.get("MAINCOIN_PRODUCTION", "").lower() == "true"

if not is_production:
    # 开发测试模式：自动模拟见证完成
    for ws in request.witness_sectors:
        exchange.add_witness(
            request.exchange_id,
            ws,
            block_height=self.current_height,
            block_hash=f"0x{request.exchange_id}",
            signature="dev_auto_witness"       # ← 硬编码签名
        )
```

**风险**: 自动见证使用硬编码签名 `"dev_auto_witness"`。默认状态（未设置 `MAINCOIN_PRODUCTION`）下兑换操作无需真实板块见证。  
**修复建议**: 同 6.1，应默认安全模式

---

### 6.4 [HIGH] `core/sector_coin.py` L393-396 — 签名验证 ImportError 静默通过

```python
# L393-398
except ImportError:
    import os
    if os.environ.get('MAINCOIN_PRODUCTION', '').lower() == 'true':
        return False, "签名验证不可用 (ecdsa library missing in production)"
    # ← 非生产环境下：ImportError 被忽略，代码继续执行后续逻辑
    #   签名验证被完全跳过
```

**风险**: 非生产环境下 `ecdsa` 缺失时签名验证被静默跳过。板块币转账不需要有效签名。  
**修复建议**: 非生产环境也应记录警告日志

---

### 6.5 [MEDIUM] `core/encrypted_task.py` L75-90 — XOR 模拟加密降级

```python
# L75-90
PRODUCTION_MODE = os.environ.get("POUW_ENV", "").lower() in ("production", "mainnet")

if not HAS_REAL_CRYPTO:
    if PRODUCTION_MODE:
        raise ImportError("🛑 严重安全错误: 生产环境必须安装加密库。")
    else:
        import warnings
        warnings.warn("⚠️ 加密库未安装，回退到 XOR 模拟加密（仅限开发/测试）。")
```

**风险**: 已有正确的生产环境保护机制。但未设置 `POUW_ENV` 时默认降级到 XOR 加密。  
**判定**: 设计合理但应在部署文档中强调环境变量配置

---

## 7. 加密模块依赖分析：`core.crypto` vs `core.wallet`

### 导入 `core.crypto`（ECDSASigner / ProductionWallet）的模块：

| 模块 | 导入内容 | 用途 | 生产安全 |
|------|----------|------|----------|
| `core/utxo_store.py` | `ECDSASigner` | UTXO 交易签名验证 | ✅ 无 fallback，缺库拒绝 |
| `core/compute_market_v3.py` | `ECDSASigner`, `HAS_ECDSA` | 矿工声明签名验证 | ⚠️ 开发模式绕过（见 6.1） |
| `core/sector_coin.py` | `ECDSASigner` | 板块币转账签名 | ⚠️ 非生产 ImportError 跳过（见 6.4） |
| `core/rpc_service.py` | `ProductionWallet`, `WalletInfo` | 钱包创建/导入/解锁 | ✅ 使用真实加密 |
| `core/dual_witness_exchange.py` | `ECDSASigner` | 兑换签名 | ⚠️ 需检查 ImportError 处理 |
| `core/consensus.py` | `ECDSASigner` | 交易签名验证 | ⚠️ DEV_MODE 绕过（见 6.2） |
| `core/compute_scheduler.py` | `ECDSASigner`, `HAS_ECDSA` | 任务签名 | 需检查 fallback |

### 导入 `core.wallet` 的模块：

| 模块 | 导入内容 | 用途 |
|------|----------|------|
| `core/rpc_service.py` | `WalletInfo` | 钱包信息数据类 |

### `core.crypto` 安全状态总结：

- **ECDSASigner.sign()**: ✅ 无 fallback，缺 ecdsa 库直接 raise RuntimeError
- **ECDSASigner.verify()**: ✅ 无 fallback，缺 ecdsa 库返回 False（拒绝所有签名）
- **密钥生成** (`generate_keypair`): ⚠️ 缺 ecdsa 时降级为 `SHA256(random_bytes)` 作为公钥 — 不安全但生产模式会拒绝
- **助记词**: ⚠️ 缺 mnemonic 库时使用内置简化词表

---

## 环境变量混乱风险

审计发现代码库中使用了 **三个不同的环境变量** 控制安全行为：

| 环境变量 | 使用位置 | 安全含义 |
|----------|----------|----------|
| `POUW_ENV` | compute_market_v3, network, encrypted_task | `production`/`mainnet` 启用安全 |
| `MAINCOIN_PRODUCTION` | crypto, sector_coin, rpc_service | `true` 启用安全 |
| `MAINCOIN_DEV_MODE` | consensus | `true` 禁用安全 |

**风险 [HIGH]**: 运维人员可能只设置了部分变量，导致某些模块在安全模式运行而其他模块在开发模式运行。`MAINCOIN_DEV_MODE` 尤其危险，因为它是"opt-in 不安全"而非"opt-in 安全"。

**修复建议**: 统一为单一环境变量（如 `POUW_ENV=production`），所有模块共享同一安全开关。

---

## 修复优先级总结

### CRITICAL（必须在生产部署前修复）— 6 项

1. **TEE 远程证明验证未实现** (compute_market_v3.py L1215) — 伪造 TEE 环境
2. **ZK 证明通用验证器无实际验证** (zk_verification.py L633) — 伪造零知识证明
3. **质押销毁未执行** (compute_market_v3.py L1271) — 无限质押评分操控
4. **签名验证默认跳过** (compute_market_v3.py L200) — 默认不安全
5. **DEV_MODE 交易签名绕过** (consensus.py L776) — 一个环境变量完全禁用签名
6. **环境变量不统一** — 配置混乱导致安全策略不一致

### HIGH（应在生产部署前修复）— 6 项

1. 裸 `except: pass` 吞异常 (rpc/server.py L342)
2. 纠删码验证未比较校验值 (data_redundancy.py L364)
3. 结算引擎未集成 (compute_market_v3.py L1049)
4. 链上结算未实现 (compute_scheduler.py L1285-1287)
5. RPC 自动见证开发模式绕过 (rpc_service.py L3474)
6. 板块币签名 ImportError 静默跳过 (sector_coin.py L393)

### MEDIUM（可接受但需文档）— 4 项

1. `is_connected()` 裸 except (rpc/server.py L354)
2. `_finalize_vote` 返回值语义 (governance_enhanced.py)
3. XOR 降级加密 (encrypted_task.py) — 已有生产保护
4. 板块币签名 ImportError 应记录日志

### LOW（设计如此 / 可接受）— 2 项

1. 无真实硬编码凭证 — 仅占位符
2. `random.random()` 仅用于模拟 / 负载测试 — 安全路径使用 `secrets`

---

*审计工具: 静态模式搜索（grep/regex），人工代码审查*  
*未覆盖: 动态运行时分析、依赖库漏洞扫描（CVE）*
