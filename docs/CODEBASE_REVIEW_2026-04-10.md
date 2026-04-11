# MainCoin 项目完整性与合理性审查（2026-04-10）

## 1. 项目快照

- 仓库文件总数（含依赖与构建产物）：10676
- Python 源文件：144
- 最大热点文件：
  - `core/rpc_service.py`：11743 行
  - `core/consensus.py`：2989 行
  - `core/compute_market_v3.py`：2145 行
  - `core/unified_consensus.py`：2053 行

结论：项目功能覆盖很广，但核心后端呈现明显“巨石模块”趋势，后续维护与安全审计成本高。

---

## 2. 高优先级问题（P0 / P1）

### P0-1: RPC 入口与业务耦合过重

- 现状：`core/rpc_service.py` 超 11k 行，承载路由注册、权限、钱包、任务、市场、文件、治理等跨领域逻辑。
- 风险：
  - 权限回归概率高（注册点多、改动面大）
  - 代码审计与故障定位成本高
  - 单测难以聚焦，容易出现“改一处破多处”

建议：继续推进 `core/rpc_handlers/` 拆分，将读写接口按域迁移（wallet/account/task/market/governance/file）。

### P1-1: 公共接口与敏感接口边界仍需持续收口

- 已完成的加固：`wallet_getInfo`、`wallet_getBalance`、`account_getTransactions`、`wallet_getTransactions`、`account_getSubAddresses` 已收口到 USER 权限。
- 仍需做：对所有带 address / history / owner / key 字段的方法建立统一审计清单，定期扫描是否误回到 PUBLIC。

建议：将“权限基线规则”写入 CI（脚本验证 registry 中敏感接口不为 PUBLIC）。

### P1-2: 配置与实现漂移风险

- 现状：存在多份配置（`config.yaml` / `config.mainnet.yaml` / `config.local.peer2.yaml` / `deploy/config.node*.yaml`），长期容易发生参数语义漂移。
- 风险：线上行为与配置预期不一致。

建议：
1. 建立配置 schema（字段、类型、默认值、环境适用范围）
2. 启动时做 schema 校验并输出差异告警

---

## 3. 中优先级问题（P2）

### P2-1: 依赖与加密后端策略较分散

- 从代码与文档可见，`cryptography` 与 `pycryptodome` 存在并行路径。
- 风险：不同运行环境触发不同分支，行为不一致。

建议：
- 生产环境统一单一主后端（推荐 `cryptography`），其他后端仅限开发 fallback。
- 文档与启动检查保持一致。

### P2-2: 文档/脚本中存在历史接口名

- 部分集成脚本和文档仍有历史方法名或示例参数。
- 风险：新同学按文档联调失败，误判后端故障。

建议：
- 建立“RPC 方法真值表”（从 registry 导出）并作为文档源。

### P2-3: 集成测试脚本历史重复较多

- 已完成阶段性整理：新增 `tests/integration/rpc_auth_helper.py`，并将多脚本认证逻辑收敛。
- 建议继续：将 URL、TLS、超时、重试策略也统一到 helper。

---

## 4. 代码整理（可执行分期）

### Phase A（1-2 天，低风险）

1. 统一测试辅助：
   - 把 integration 脚本中的 RPC URL、超时、SSL 参数统一到 helper
2. 补权限回归测试模板：
   - 每新增敏感接口必须配 guest/user/admin 三态测试
3. 建立目录说明：
   - 在 `core/` 下补 `README` 说明各模块边界

### Phase B（3-5 天，中风险）

1. 继续拆分 RPC：
   - `account_handler.py`
   - `task_handler.py`
   - `market_handler.py`
2. 迁移后保持旧方法名兼容层（避免前端一次性改动过大）
3. 每次迁移后运行权限回归与 smoke

### Phase C（1-2 周，中高风险）

1. 配置治理：
   - 引入配置 schema + 启动校验
   - 输出“当前生效配置”快照
2. 依赖治理：
   - 统一加密后端优先级策略
   - 清理重复/历史依赖
3. 质量门禁：
   - CI 增加敏感方法权限扫描
   - 增加超大文件行数告警阈值（如 > 2000 行）

---

## 5. 本次审查结论

项目已经具备较强功能完整度与一定安全基础，但当前最大风险在于“复杂度集中”与“长期演进一致性”。

优先策略：
- 先守住权限边界（已在做）
- 再拆 RPC 巨石
- 最后统一配置与依赖策略

这条路径可以在不打断业务迭代的情况下，逐步把系统从“能跑”推进到“可长期维护”。
