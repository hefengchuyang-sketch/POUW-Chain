# POUW Multi-Sector Chain — 生产环境就绪评估报告
# Production Readiness Assessment Report

**审查日期 / Date**: 2025-01  
**审查范围 / Scope**: 全栈代码审查 (Full-stack code audit)  
**审查方法 / Method**: 4 并行深度审计 (crypto, RPC, storage/network, wallet/transaction)

---

## 总结 / Executive Summary

### 🔴 结论：系统尚未达到上线标准 / NOT READY FOR PRODUCTION

经过全面深度代码审计，我们发现了 **~15 个致命级 (FATAL)、~18 个严重级 (SEVERE)、~28 个高危级 (HIGH)** 安全和架构问题。

本次审查已修复了最关键的安全漏洞（共计 **20+ 项修复**），但仍有若干需要大幅重构的架构性问题尚未解决。

After a comprehensive deep code audit, we found **~15 FATAL, ~18 SEVERE, ~28 HIGH** security and architecture issues.

This review has fixed the most critical security vulnerabilities (**20+ fixes total**), but several architecture-level issues requiring significant refactoring remain unfixed.

---

## ✅ 已修复的安全漏洞 / Fixed Security Issues

### FATAL 级修复 / FATAL Fixes

| # | 问题 / Issue | 文件 / File | 说明 / Description |
|---|---|---|---|
| F-1 | HMAC 伪签名后门 | `core/crypto.py` | `sign()` 和 `verify()` 在缺少 ecdsa 库时回退到 HMAC 签名，任何人可用公钥伪造签名。**已修复**: sign() 现在抛出 RuntimeError，verify() 返回 False |
| F-2 | RPC 写操作无权限 | `core/rpc_service.py` | wallet_transfer, miner_register 等 11 个写操作注册为 PUBLIC。**已修复**: 全部改为 USER 或 ADMIN |
| F-3 | Keystore 导入密码泄露 | `core/rpc_service.py` | `_wallet_import_keystore` 使用 SSH_PASSWORD 环境变量而非用户密码。**已修复**: 使用用户提供的密码 |
| F-4 | 见证签名未验证 | `core/dual_witness_exchange.py` | `add_witness()` 接受 signature 参数但从未验证。**已修复**: 添加 ECDSA 签名验证 + 超时检查 |
| F-5 | 板块币转账无签名 | `core/sector_coin.py` | `transfer()` 无需任何签名即可从任意地址转出。**已修复**: 添加 signature + public_key 验证 |
| F-6 | MAIN 无供应上限 | `core/dual_witness_exchange.py` | MAIN 可无限铸造。**已修复**: 添加 MAIN_MAX_SUPPLY = 100,000,000 上限 |
| F-7 | 板块币无供应上限 | `core/sector_coin.py` | 板块币 get_block_reward 永远不会归零。**已修复**: 添加 MAX_SUPPLY 每板块 21,000,000，奖励可归零 |

### SEVERE 级修复 / SEVERE Fixes

| # | 问题 / Issue | 文件 / File | 说明 / Description |
|---|---|---|---|
| S-1 | X-Auth-User 头注入 | `core/rpc/server.py` | localhost 连接信任 X-Auth-User 头，攻击者可伪造用户身份。**已修复**: 固定返回 'local_admin' |
| S-2 | wallet_unlock 不验证密码 | `core/rpc_service.py` | 解锁钱包不检查密码正确性。**已修复**: 用密码重新派生验证地址匹配 |
| S-3 | DAO 参数无边界 | `core/dao_treasury.py` | `_apply_parameter_change` 使用 setattr 无限制修改参数。**已修复**: 添加 PARAMETER_BOUNDS 验证 |
| S-4 | stake 接受负数 | `core/dao_treasury.py` | `stake()` 未验证金额为正数。**已修复**: 添加正数和上限验证 |

### HIGH 级修复 / HIGH Fixes

| # | 问题 / Issue | 文件 / File | 说明 / Description |
|---|---|---|---|
| H-1 | 错误信息泄露 | `core/rpc_service.py` | handle_request 和 wallet 操作返回 str(e) 暴露内部错误。**已修复**: 返回通用错误信息，详情仅记录日志 |
| H-2 | Windows 路径穿越 | `core/rpc/server.py` | do_GET 静态文件可被 Windows 路径遍历绕过。**已修复**: 添加 realpath 检查 |
| H-3 | do_GET CORS 硬编码 | `core/rpc/server.py` | Access-Control-Allow-Origin 硬编码为 '*'。**已修复**: 使用 _get_cors_origin() |
| H-4 | Content-Length 注入 | `core/rpc/server.py` | Content-Length 无负数/非法值检查。**已修复**: 添加 ValueError 检查 |
| H-5 | XOR 解密仍可用 | `core/rpc_service.py` | 不安全的 xor-pbkdf2 密钥文件仍可导入。**已修复**: 拒绝 XOR 格式导入 |
| H-6 | 兑换率任意传入 | `core/sector_coin.py` | exchange_to_main 接受调用者传入任意 rate。**已修复**: 添加最大兑换率 10.0 限制 |
| H-7 | tx_id 截断碰撞 | `core/dual_witness_exchange.py` | _mint_main 的 tx_id 截断为 16 字符。**已修复**: 使用完整 SHA-256 + 随机熵 |
| H-8 | contrib_executeProposal 公开 | `core/rpc_service.py` | 执行提案为 PUBLIC。**已修复**: 改为 ADMIN |
| H-9 | 兑换超时未执行 | `core/dual_witness_exchange.py` | 定义了 86400s 超时但从未检查。**已修复**: add_witness 中主动检查并失败 |

---

## 🔴 未修复的关键问题（需架构重构） / Remaining Critical Issues

### FATAL — 需在上线前解决 / Must Fix Before Production

#### 1. P2P 认证完全无效 (FATAL)
- **文件**: `core/tcp_network.py`
- **问题**: Challenge-response 认证使用 node_id 作为 HMAC 密钥，而 node_id 是公开的
- **影响**: 任何人可以冒充任何节点
- **修复方案**: 使用 Ed25519 非对称签名替换 HMAC 认证
- **工作量估计**: 3-5 天

#### 2. P2P 密钥交换伪造 (FATAL)
- **文件**: `core/p2p_direct.py`
- **问题**: "ECDH-X25519" 密钥交换实际是 SHA256(random_bytes)，不是真正的 ECDH
- **影响**: 无前向保密性，中间人攻击
- **修复方案**: 使用 cryptography 库实现真正的 X25519 ECDH
- **工作量估计**: 2-3 天

#### 3. 单例钱包会话共享 (FATAL)
- **文件**: `core/rpc_service.py`
- **问题**: NodeRPCService 是单例，`self.wallet_info` / `self.miner_address` 被所有连接共享
- **影响**: 用户 A 登录钱包后，用户 B 可以操作 A 的钱包
- **缓解**: 当前为单节点设计，已限制 wallet 操作需要 USER 权限。多用户场景需要重构
- **修复方案**: 实现 per-session 或 per-token 钱包绑定
- **工作量估计**: 2-3 天

#### 4. 浮点数金融计算 (SEVERE → 架构级)
- **文件**: 全系统 (`sector_coin.py`, `utxo_store.py`, `dual_witness_exchange.py`, `dao_treasury.py`)
- **问题**: 所有金额使用 IEEE 754 double，存储在 SQLite REAL 列
- **影响**: 精度丢失、舍入错误，可能被利用进行 "分拆攻击" 获利
- **修复方案**: 迁移到 Satoshi 模型 (整数最小单位)，所有 REAL 列改 INTEGER
- **工作量估计**: 5-7 天（涉及全系统重构）

### SEVERE — 需尽快修复 / Should Fix Soon

| # | 问题 / Issue | 文件 / File | 说明 |
|---|---|---|---|
| 1 | wallet.py 48 词后备列表仅 ~67 位熵 | `core/wallet.py` | 助记词安全性不足 |
| 2 | wallet.py 无 BIP32/BIP44 派生 | `core/wallet.py` | 所有板块共享同一密钥 |
| 3 | 国库/DAO 状态仅内存 | `core/dao_treasury.py` | 重启后丢失所有质押、提案、投票 |
| 4 | 治理投票无防重复 | `core/rpc_service.py` | 同一用户可多次投票 |
| 5 | TCP reader.read() 非精确 | `core/tcp_network.py` | 应使用 readexactly() 防止消息截断 |
| 6 | UTXO float 金额 + 竞态 | `core/utxo_store.py` | create_exchange_transaction 非排他连接 |
| 7 | TLS 默认 CERT_OPTIONAL | `core/security.py` | 生产应该要求 CERT_REQUIRED |
| 8 | API Key 明文存内存 | `core/security.py` | 应使用 key hash 比对 |
| 9 | WalletEncryptor 后备种子不安全 | `core/security.py` | fallback_seed_not_secure 名称已说明 |
| 10 | 跨数据库原子性缺失 | `dual_witness_exchange.py` | 销毁板块币和铸造 MAIN 不在同一事务 |

### HIGH — 应在上线前修复 / Should Fix

| # | 问题 / Issue | 文件 / File |
|---|---|---|
| 1 | storage.py LIKE 注入 (% 和 _ 字符) | `core/storage.py` |
| 2 | db.py synchronous=NORMAL 断电可丢数据 | `core/db.py` |
| 3 | transaction.py tx_id 截断 12 字符 (~16M 碰撞) | `core/transaction.py` |
| 4 | P2P 10MB 消息上限过大 | `core/tcp_network.py` |
| 5 | P2P seen_messages 清理非原子 | `core/tcp_network.py` |
| 6 | ~60 处 RPC 方法仍返回 str(e) | `core/rpc_service.py` |
| 7 | budget_deposit 接受任意 userId/amount | `core/rpc_service.py` |
| 8 | compute_cancel_order 无所有权检查 | `core/rpc_service.py` |
| 9 | 区块/交易查询无分页上限 | `core/rpc_service.py` |
| 10 | 线程不安全的共享字典 | `core/rpc_service.py` |
| 11 | signaling 消息无签名验证 | `core/p2p_direct.py` |
| 12 | random.sample() 见证选择可预测 | `core/dual_witness_exchange.py` |

---

## 上线前最低要求清单 / Minimum Pre-Launch Checklist

### 必须完成 (Must Have) 🔴

- [ ] **P2P 网络认证重构** — 使用非对称签名替换 HMAC(node_id)
- [ ] **P2P 密钥交换** — 实现真正的 X25519 ECDH
- [ ] **浮点数 → 整数迁移** — 所有金融数据使用整数最小单位 (satoshi model)
- [ ] **BIP32/BIP44 HD 钱包** — 每板块派生独立密钥
- [ ] **ecdsa 库强制依赖** — 启动时检查，无库则拒绝启动
- [ ] **跨数据库事务原子性** — exchange 操作的 burn + mint 原子化
- [ ] **DAO 状态持久化** — 质押、提案、投票写入数据库
- [ ] **安全审计** — 第三方安全审计

### 建议完成 (Should Have) 🟡

- [ ] **wallet 会话隔离** — per-session/per-token 钱包绑定
- [ ] **TLS CERT_REQUIRED** — 生产环境强制证书验证
- [ ] **API Key 哈希存储** — 不在内存中保留明文 key
- [ ] **全面错误泄露修复** — 审查全部 ~60 处 str(e) 返回
- [ ] **查询分页限制** — 防止 DoS
- [ ] **投票防重复** — 每提案每地址只能投一次
- [ ] **TCP readexactly()** — 替换 reader.read()
- [ ] **随机数安全** — 见证选择使用 secrets.SystemRandom

### 可以推后 (Nice to Have) 🟢

- [ ] **监控告警系统** — Prometheus/Grafana
- [ ] **日志审计** — 结构化日志 + 审计追踪
- [ ] **负载测试** — 压测 TPS 和并发
- [ ] **灾备方案** — 数据备份 + 恢复流程

---

## 架构评估 / Architecture Assessment

### 优势 / Strengths
1. **清晰的多板块设计** — 板块独立运行，MAIN 作为跨板块结算
2. **双见证机制** — 兑换需要多板块确认，防止单点操控
3. **POUW 工作证明** — 结合挖矿和有用工作
4. **模块化结构** — 各组件职责清晰，便于独立测试
5. **Keystore V3** — AES-256-GCM + PBKDF2 310000 次迭代

### 风险 / Risks
1. **ecdsa 库缺失** — 整个签名体系依赖可选库，缺失则全面退化
2. **单进程架构** — 无水平扩展能力
3. **SQLite 存储** — 不适合高并发场景
4. **内存状态** — DAO/Treasury 重启丢失
5. **浮点精度** — 核心金融系统使用 float 是致命架构缺陷

---

## 本次修复的文件清单 / Files Modified in This Audit

| 文件 | 修改数量 | 关键修复 |
|---|---|---|
| `core/crypto.py` | 2 处 | 移除 HMAC 签名后门 |
| `core/rpc_service.py` | ~18 处 | 权限修复、密码验证、错误泄露、SSH_PASSWORD、XOR 禁用 |
| `core/rpc/server.py` | 4 处 | X-Auth-User 注入、路径穿越、CORS、Content-Length |
| `core/dual_witness_exchange.py` | 3 处 | 见证签名验证、MAIN 供应上限、tx_id 完整哈希、超时检查 |
| `core/sector_coin.py` | 4 处 | 转账签名、供应上限、奖励归零、兑换率限制 |
| `core/dao_treasury.py` | 2 处 | 参数边界、质押金额验证 |

---

*报告由 GitHub Copilot 自动化安全审计生成 / Generated by GitHub Copilot automated security audit*
