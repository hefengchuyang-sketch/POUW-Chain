# POUW 区块链前端全面审计报告 V2

> **审计范围**: `frontend/src/` 下全部页面组件、API 层、状态管理  
> **参照基线**: [FRONTEND_AUDIT_REPORT.md](FRONTEND_AUDIT_REPORT.md)（2025-01 版，30 个 Bug）  
> **审计日期**: 2025-07  
> **审计方式**: 逐文件静态分析 + 前后端 RPC 方法名交叉验证（~210 个后端注册方法 vs 前端全部调用）

---

## 审计方法

1. 完整读取前端全部 24 个 `.ts/.tsx` 源文件（共约 15,000+ 行）
2. 从 `core/rpc_service.py` + `core/rpc_handlers/` 提取全部后端注册 RPC 方法名（~210 个）
3. 逐一交叉验证前端 API 调用 → 后端方法名注册、参数匹配、返回类型匹配
4. 检查状态管理、生命周期、安全、用户反馈、类型安全

---

## 一、前版修复状态（3/30 已修复）

| # | Bug 描述 | 状态 |
|---|---------|------|
| 1 | `exchangeApi.getHistory` catch 块返回 `success: true` | ✅ **已修复** — 现在返回 `success: false` |
| 4 | TaskDetail.tsx "暂停"和"停止"按钮调用相同 API | ✅ **已修复** — 暂停按钮已移除，仅保留"取消任务" |
| 5 | Statistics.tsx `'90d'` 与 API 类型不匹配 | ✅ **已修复** — `TimeRange` 已改为 `'24h' \| '7d' \| '30d'` |

其余 **27 个 Bug 仍然存在**，不再逐一重复描述，请参阅前版报告 Bug #2-3, #6-30。

---

## 二、新发现 Bug（前版未覆盖）

### NEW-1. [Fatal] `accountApi.exportWallet` 返回类型与后端实际响应完全不匹配

- **文件**: [api/index.ts](src/api/index.ts#L520-L525)
- **行号**: 520-525
- **描述**: 前版审计（Bug #2）发现缺少 `password` 参数，现已修复传入 `password`。但返回类型声明为 `Promise<{ mnemonic: string } | null>`，而后端 `wallet_exportKeystore` 实际返回 `{ success: boolean, keystore: string, filename: string, message: string }`。任何调用 `.mnemonic` 的代码都会得到 `undefined`。
  ```typescript
  // 当前代码（错误）
  exportWallet: async (password: string = ''): Promise<{ mnemonic: string } | null> => {
    return await rpcCall<{ mnemonic: string }>('wallet_exportKeystore', { password })
  }
  
  // 正确写法
  exportWallet: async (password: string): Promise<{ success: boolean; keystore: string; filename: string; message: string } | null> => {
    return await rpcCall<{ success: boolean; keystore: string; filename: string; message: string }>('wallet_exportKeystore', { password })
  }
  ```
- **严重程度**: **Fatal** — 函数返回值形状完全错误，任何使用方都会取到 `undefined`
- **与前版关系**: Bug #2 的延续问题，前版只发现参数缺失，未发现类型不匹配

---

### NEW-2. [Severe] TaskDetail RatingModal 非原子操作：staking 与 rating 分离

- **文件**: [pages/TaskDetail.tsx](src/pages/TaskDetail.tsx#L521-L530)
- **行号**: 521-530
- **描述**: `handleSubmit` 先调用 `stakingApi.stake(stakeAmount, 'MAIN')` 质押代币，再调用 `taskApi.acceptResult(taskId, rating)` 提交评价。两步操作不是原子的：
  1. 如果 `stake` 成功但 `acceptResult` 失败 → 用户代币被质押但评价未记录，资金被锁
  2. `finally` 块无条件调用 `onClose()` → 失败时弹窗也关闭，用户无法得知操作是否成功
  ```typescript
  // 当前代码
  try {
    await stakingApi.stake(stakeAmount, 'MAIN')   // 步骤1: 质押
    await taskApi.acceptResult(taskId, rating)      // 步骤2: 评价（可能失败）
  } catch (err) {
    console.error('评价提交失败:', err)             // 无 UI 反馈
  } finally {
    onClose()                                        // 无条件关闭
  }
  ```
- **严重程度**: **Severe** — 可能导致资金损失且无用户反馈
- **修复建议**: 
  1. 颠倒顺序：先 `acceptResult` 成功后再 `stake`
  2. 失败时不调用 `onClose()`，改为在弹窗内显示错误信息
  3. 成功时给出明确的成功提示

---

### NEW-3. [Severe] Provider.tsx 矿工身份识别使用不可靠的 16 字符前缀子串匹配

- **文件**: [pages/Provider.tsx](src/pages/Provider.tsx#L98-L100)
- **行号**: 98-100
- **描述**:
  ```typescript
  const myMiner = minerList.miners.find(m => 
    m.address.includes(account?.address?.slice(0, 16) || 'not_found') || 
    (m as any).isLocal
  )
  ```
  三个问题：
  1. `address.includes(slice(0, 16))` — 子串匹配不是精确比较，如果多个矿工地址共享16字符前缀，会匹配到错误的矿工
  2. `(m as any).isLocal` — 强制 `any` 类型转换访问 `Miner` 类型上不存在的 `isLocal` 字段
  3. 整个矿工识别逻辑应由后端提供，而非前端遍历全部矿工列表匹配
- **严重程度**: **Severe** — 可能显示其他矿工的数据和状态
- **修复建议**:
  ```typescript
  // 使用精确匹配
  const myMiner = minerList.miners.find(m => m.address === account?.address)
  ```
  或添加专用 API：`minerApi.getMyMiner()` → `miner_getSelf`

---

### NEW-4. [Severe] Provider.tsx `setProfile` 双重类型断言跨类型赋值

- **文件**: [pages/Provider.tsx](src/pages/Provider.tsx#L102)
- **行号**: 102
- **描述**:
  ```typescript
  setProfile(myMiner as unknown as ProviderProfile)
  ```
  `myMiner` 类型为 `Miner`（来自 `minerApi.getMiners()`），通过 `as unknown as ProviderProfile` 强制转换。`Miner` 和 `ProviderProfile` 是不同的接口，字段不完全对齐。后续使用 `profile.xxx` 时可能访问到不存在的字段或得到 `undefined`。
- **严重程度**: **Severe** — 运行时多个字段将为 `undefined`
- **修复建议**: 创建一个从 `Miner` 到 `ProviderProfile` 的规范化映射函数。

---

### NEW-5. [Medium] Connect.tsx 助记词导入使用空密码创建钱包

- **文件**: [pages/Connect.tsx](src/pages/Connect.tsx#L285)
- **行号**: 285
- **描述**:
  ```typescript
  const result = await walletApi.import(importMnemonic.trim(), '')
  ```
  导入助记词时固定传入空字符串作为密码。这意味着生成的 keystore 文件是未加密的（或使用空密码加密），任何获取到 keystore 文件的人都可以直接导入钱包。
  
  对比新建钱包流程（步骤1.5），用户需要设置强密码 (`createPassword`)。但导入流程完全跳过了密码设置。
- **严重程度**: **Medium** — 安全性降级，与新建钱包的安全标准不一致
- **修复建议**: 在导入助记词前增加密码设置步骤，将用户密码传入 `walletApi.import()`。

---

### NEW-6. [Medium] Connect.tsx 创建钱包流程：验证通过后无法回退修改密码

- **文件**: [pages/Connect.tsx](src/pages/Connect.tsx#L246-L260)
- **行号**: 246-260
- **描述**: `handleFinalizeWallet` 在助记词验证通过后直接将账户设入 store 并跳转首页。如果用户在步骤2（查看助记词）发现问题想回去改密码：
  1. `handleBack` 从 step 2 → step 1.5 会清空 `mnemonic` 和 `walletData`
  2. 但原始密码 `createPassword` 仍然保留，后端已经用该密码创建了钱包
  3. 如果用户改密码重新创建，后端可能已经有了旧钱包的数据
  
  这不是崩溃 Bug，但流程设计上存在混淆：用户可能以为回退后可以"重来"，实际上后端状态已经改变。
- **严重程度**: **Medium** — 用户体验混淆
- **修复建议**: 回退时显示警告"将生成新的钱包地址，之前的助记词将失效"。

---

### NEW-7. [Medium] Governance.tsx 创建提案后不传递 `fetchProposals` 回调

- **文件**: [pages/Governance.tsx](src/pages/Governance.tsx#L199)
- **行号**: 199
- **描述**: 前版 Bug #8 指出了此问题但未修复。进一步分析：
  ```typescript
  <CreateProposalModal onClose={() => setShowCreateModal(false)} />
  ```
  `onClose` 只关闭弹窗，不触发列表刷新。`fetchProposals` 已定义且可用，但未传递给子组件。
  
  同样地，在投票操作后 (`ProposalDetail.tsx`)，虽然会刷新当前提案数据，但返回提案列表页时列表不会自动刷新。
- **严重程度**: **Medium**（前版 Bug #8 的补充说明）
- **修复建议**:
  ```typescript
  <CreateProposalModal 
    onClose={() => { setShowCreateModal(false); fetchProposals(); }} 
  />
  ```

---

### NEW-8. [Medium] 多个页面 `useNotificationStore` 定义了但从未使用

- **文件**: TaskDetail.tsx, Provider.tsx, P2PTasks.tsx, ProposalDetail.tsx 等
- **描述**: 前版审计多次提到 "错误仅输出到 `console.error`"（Bug #9, #10, #26），但从更高层面看：整个前端项目定义了 `useNotificationStore` 通知系统，Layout.tsx 也有通知铃铛和通知列表 UI，但几乎所有页面都未使用它。这是一个系统性的遗漏：
  - **TaskDetail.tsx**: 质押/评价失败 → `console.error`
  - **Provider.tsx**: 注册/挖矿操作失败 → `console.error`
  - **P2PTasks.tsx**: 分发/取消失败 → `console.error`
  - **ProposalDetail.tsx**: 投票失败 → `console.error`
  - **Mining.tsx**: 模式切换失败 → `console.error`
  
  用户在所有关键操作失败时都无法得到可见反馈。
- **严重程度**: **Medium** — 系统性用户体验缺陷
- **修复建议**: 在所有页面的 catch 块中添加 `addNotification({ type: 'error', message: '...' })`。

---

### NEW-9. [Low] Explorer.tsx `explorerApi.search()` 连续尝试策略不区分网络错误和"未找到"

- **文件**: [api/index.ts](src/api/index.ts#L1970-L2002)
- **行号**: 1970-2002
- **描述**: `explorerApi.search()` 是一个客户端组合函数，依次尝试 `tx_get` → `block_getByHash` → `account_getBalance`，每步的 catch 块都静默吞掉错误继续下一步。
  ```typescript
  try { /* tx_get */ } catch {} // 网络超时也被吞掉
  try { /* block_getByHash */ } catch {} // 继续尝试
  try { /* account_getBalance */ } catch {} // 继续尝试
  ```
  如果后端完全不可用（网络故障），三个请求都会超时，用户等待很久最终得到"未找到"提示，而实际原因是网络问题。
- **严重程度**: **Low** — 不会产生错误数据，但用户体验差
- **修复建议**: 在 catch 中区分网络错误类型。如果是 `TypeError: Failed to fetch` 级别的错误，直接返回网络错误而非继续尝试。

---

### NEW-10. [Low] Layout.tsx 系统状态轮询失败时显示陈旧数据

- **文件**: [components/Layout.tsx](src/components/Layout.tsx)
- **描述**: Layout 组件每 30 秒调用 `statsApi.getChainInfo()` 更新状态栏（区块高度、连接节点数等）。当 API 调用失败时，catch 块仅 `console.error`，状态栏继续显示上次成功的旧数据。用户无法知道网络已断开。
- **严重程度**: **Low**
- **修复建议**: 连续 N 次失败后状态栏显示"连接中断"警告标识。

---

## 三、RPC 方法名交叉验证结果

对前端 `api/index.ts` 中全部 ~115 个 RPC 调用与后端 ~210 个注册方法进行了逐一比对：

| 检查项 | 结果 |
|--------|------|
| 前端调用未注册的后端方法 | **0 个** — 全部匹配 |
| 后端注册但前端未使用的方法 | ~95 个（正常，后端功能大于前端展示） |
| 方法名拼写错误 | **0 个** |
| 参数名严重不匹配 | **0 个**（注：Python 后端对参数名宽松） |

**结论**: 前后端 RPC 方法名完全匹配，无调用缺失。主要风险集中在**返回值类型声明**与**UI 逻辑**层面。

---

## 四、路由与页面对应检查（无变化）

| 路由 | 组件 | 状态 |
|------|------|------|
| `/` | Dashboard | ✅ |
| `/tasks` | Tasks | ✅ |
| `/tasks/:taskId` | TaskDetail | ✅ |
| `/market` | Market | ✅ |
| `/wallet` | Wallet | ✅ |
| `/orders` | Orders | ✅ |
| `/account` | Account | ✅ |
| `/mining` | Mining | ✅ |
| `/provider` | Provider | ✅ |
| `/governance` | Governance | ✅ |
| `/governance/:proposalId` | ProposalDetail | ✅ |
| `/miners` | Miners | ✅ |
| `/explorer` | Explorer | ✅ |
| `/statistics` | Statistics | ✅ |
| `/privacy` | Privacy | ✅ |
| `/settings` | Settings | ✅ |
| `/help` | Help | ✅ |
| `/connect` | Connect（独立路由） | ✅ |

全部 18 个路由正确对应。

---

## 五、汇总统计

### 前版 Bug 状态

| 状态 | 数量 |
|------|------|
| ✅ 已修复 | 3 |
| ❌ 仍存在 | 27 |

### 新发现 Bug

| 严重程度 | 数量 |
|----------|------|
| Fatal | 1 |
| Severe | 3 |
| Medium | 4 |
| Low | 2 |
| **小计** | **10** |

### 总计（当前未修复）

| 严重程度 | 前版 | 新发现 | 合计 |
|----------|------|--------|------|
| Fatal | 2 | 1 | **3** |
| Severe | 3 | 3 | **6** |
| Medium | 11 | 4 | **15** |
| Low | 11 | 2 | **13** |
| **合计** | **27** | **10** | **37** |

---

## 六、最高优先级修复建议（Top 8）

| 优先级 | Bug | 说明 | 预估工作量 |
|--------|-----|------|-----------|
| P0 | 前版#3 | 移除 localStorage 中的助记词存储 | 10 分钟 |
| P0 | NEW-1 | 修复 `accountApi.exportWallet` 返回类型 | 5 分钟 |
| P0 | 前版#2 | `accountApi.exportWallet` 功能重新设计（与 NEW-1 一起） | 15 分钟 |
| P1 | NEW-2 | TaskDetail 评价弹窗原子性 + 用户反馈 | 20 分钟 |
| P1 | NEW-3 | Provider 矿工精确匹配 | 5 分钟 |
| P1 | NEW-8 | 全局添加 `useNotificationStore` 错误提示 | 60 分钟 |
| P1 | 前版#7 | Provider miningApi.start 补充 mode 参数 | 5 分钟 |
| P2 | NEW-5 | Connect 导入助记词增加密码步骤 | 30 分钟 |
