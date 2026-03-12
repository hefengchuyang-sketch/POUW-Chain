# POUW 区块链前端全面审计报告

> **审计范围**: `frontend/src/` 下全部 24 个 `.ts/.tsx` 文件  
> **技术栈**: React 18.2 + TypeScript 5.2 + Vite 5.0 + Zustand 4.4.7 + react-router-dom 6.20  
> **TypeScript 编译**: `npx tsc --noEmit` **通过（零错误）**  
> **审计日期**: 2025-01

---

## 严重程度定义

| 级别 | 描述 |
|------|------|
| **Fatal** | 数据丢失、资金风险、安全漏洞 |
| **Severe** | 功能完全失效或产生错误结果 |
| **Medium** | 功能局部异常、用户体验显著下降 |
| **Low** | 代码质量问题、潜在隐患、可改进项 |

---

## BUG 清单

### 1. [Fatal] API 层 `exchangeApi.getHistory` catch 块返回 `success: true`

- **文件**: [api/index.ts](src/api/index.ts#L419)
- **行号**: 419
- **描述**: `getHistory` 的 catch 块返回 `{ success: true, exchanges: [], total: 0, error: String(e) }`。当 RPC 调用失败时，返回值声称成功，导致上层代码无法区分正常空数据与请求失败。用户可能以为兑换历史为空而实际是网络故障。
- **严重程度**: **Fatal**
- **修复建议**:
  ```typescript
  // 将 success: true 改为 success: false
  return {
    success: false,
    exchanges: [],
    total: 0,
    error: String(e)
  }
  ```

---

### 2. [Fatal] `accountApi.exportWallet` 调用 `wallet_exportKeystore` 缺少 password 参数

- **文件**: [api/index.ts](src/api/index.ts#L520-L525)
- **行号**: 520-525
- **描述**: `accountApi.exportWallet()` 调用 `wallet_exportKeystore` RPC 方法但不传递任何参数，而此 RPC 方法需要 `password` 参数（参见第138行 `walletApi.exportKeystore(password)` 的正确用法）。这意味着此函数永远会被后端拒绝，返回 null。
- **严重程度**: **Fatal**
- **修复建议**: 此函数要么需要接受 `password` 参数并传递，要么应改为调用正确的 RPC 方法。当前代码形同虚设。

---

### 3. [Fatal] Connect.tsx 将助记词存储在 localStorage

- **文件**: [pages/Connect.tsx](src/pages/Connect.tsx)
- **行号**: 钱包创建流程中 `localStorage.setItem('pouw_wallet_mnemonic', ...)`
- **描述**: 创建钱包时将助记词明文保存到 `localStorage`。助记词是钱包的最高权限凭证，任何 XSS 攻击或恶意浏览器扩展都可以读取 `localStorage`，导致用户资金被盗。
- **严重程度**: **Fatal**
- **修复建议**: 不应将助记词持久化到 `localStorage`。仅在创建流程中让用户备份一次后即清除。如需在 Account 页面重新展示，应提示"助记词仅在创建时显示一次"。

---

### 4. [Severe] TaskDetail.tsx "暂停"和"停止"按钮调用相同 API

- **文件**: [pages/TaskDetail.tsx](src/pages/TaskDetail.tsx#L263-L290)
- **行号**: 263-290
- **描述**: 当任务状态为 `running` 时，"暂停"按钮和"停止"按钮都调用 `taskApi.cancelTask(taskId)`。后端 `task_cancel` 是不可逆操作（取消任务），没有暂停语义。用户点"暂停"实际效果是取消任务，造成不可逆的数据损失。
- **严重程度**: **Severe**
- **修复建议**: 
  1. 如后端不支持暂停功能，应移除"暂停"按钮，避免误导用户。
  2. 如后端支持暂停，需新增 `task_pause` RPC 方法并在 `taskApi` 中添加对应函数。

---

### 5. [Severe] Statistics.tsx 传入 `'90d'` 但 API 类型仅接受 `'24h' | '7d' | '30d'`

- **文件**: [pages/Statistics.tsx](src/pages/Statistics.tsx#L65)
- **行号**: 65, 92-94
- **描述**: `TimeRange` 类型定义为 `'24h' | '7d' | '30d' | '90d'`，UI 上也提供 90d 选项按钮。但 `statsApi.getBlockStats` 和 `statsApi.getTaskStats` 的参数类型为 `'24h' | '7d' | '30d'`，不接受 `'90d'`。TypeScript 在某些情况对此不会报错是因为第92行使用了 `as '24h' | '7d' | '30d'` 强制类型断言——但运行时后端会收到 `'90d'` 字符串,可能返回错误或未定义行为。
- **严重程度**: **Severe**
- **修复建议**: 要么在后端添加 `90d` 支持，要么从 UI 移除 90d 选项，或在前端对 90d 做特殊处理（如分多次请求 30d 数据拼接）。

---

### 6. [Severe] ProposalDetail.tsx 除零风险：`totalVotes` 默认为 `|| 1`

- **文件**: [pages/ProposalDetail.tsx](src/pages/ProposalDetail.tsx#L80)
- **行号**: 80
- **描述**: `const totalVotes = (proposal.votesFor + proposal.votesAgainst + proposal.votesAbstain) || 1` — 当三项都为 0 时 `totalVotes` 被设为 1，导致 `quorumPercentage = Math.min(100, (1 / proposal.quorum * 100))`。这不会崩溃但结果语义错误——在 0 票时会显示一个非零的法定人数百分比。此外，在后续的"已确认投票后刷新"逻辑中，`totalVotes` 也用于计算百分比，0 票应正确显示为 0%。
- **严重程度**: **Severe**
- **修复建议**: 在计算百分比时使用条件判断：`totalVotes > 0 ? (proposal.votesFor / totalVotes * 100) : 0`，而非设置 fallback 值为 1。

---

### 7. [Severe] Provider.tsx `miningApi.start` 缺少第二个参数 `mode`

- **文件**: [pages/Provider.tsx](src/pages/Provider.tsx#L160)
- **行号**: 160
- **描述**: `miningApi.start(account?.address)` 只传了地址，没有传 `mode` 参数。API 定义为 `start(address?, mode?)`。对比 Mining.tsx 页面的正确调用 `miningApi.start(account.address, selectedMode)`。缺少 mode 会导致后端以默认模式启动，不尊重用户在 Provider 页面的预期。
- **严重程度**: **Severe**
- **修复建议**: 
  ```typescript
  const result = await miningApi.start(account?.address, 'mine_and_task')
  ```

---

### 8. [Medium] Governance.tsx 创建提案后不刷新提案列表

- **文件**: [pages/Governance.tsx](src/pages/Governance.tsx#L261-L272)
- **行号**: 261-272
- **描述**: `CreateProposalModal` 中创建成功后仅调用 `onClose()` 关闭弹窗，不会通知父组件刷新提案列表。用户创建提案后看不到新提案，需手动点刷新。
- **严重程度**: **Medium**
- **修复建议**: `onClose` 改为 `onSuccess` 回调，或在 Governance 父组件中监听 `showCreateModal` 从 true→false 后自动调用 `fetchProposals()`。

---

### 9. [Medium] ProposalDetail.tsx 投票成功/失败无用户反馈

- **文件**: [pages/ProposalDetail.tsx](src/pages/ProposalDetail.tsx#L311-L330)
- **行号**: 311-330
- **描述**: 投票按钮的 onClick 处理器在 `governanceApi.vote()` 调用后没有任何成功或失败提示。成功时只是安静地关闭弹窗、刷新数据。失败时仅 `console.error`。用户无法确认投票是否生效。
- **严重程度**: **Medium**
- **修复建议**: 添加 toast 通知或在 VoteModal 中显示成功/失败消息。

---

### 10. [Medium] P2PTasks.tsx `handleDistribute` / `handleCancel` 无错误反馈

- **文件**: [components/P2PTasks.tsx](src/components/P2PTasks.tsx)
- **描述**: 分发任务和取消任务的错误仅输出到 `console.error`，用户界面无任何提示。操作失败时用户不知道发生了什么。
- **严重程度**: **Medium**
- **修复建议**: 使用 `useNotificationStore` 添加错误通知。

---

### 11. [Medium] Tasks.tsx 使用 `alert()` 做表单验证

- **文件**: [pages/Tasks.tsx](src/pages/Tasks.tsx#L700)
- **行号**: ~700 (CreateTaskModal 验证逻辑)
- **描述**: CreateTaskModal 在验证失败时调用 `alert()` 弹窗，不符合 React UI 规范，体验差且阻塞线程。
- **严重程度**: **Medium**
- **修复建议**: 使用表单内联错误提示（如红色文字）或通知组件替代 `alert()`。

---

### 12. [Medium] Tasks.tsx CreateTaskModal 使用 `(formData as any).gitUrl`

- **文件**: [pages/Tasks.tsx](src/pages/Tasks.tsx#L637)
- **行号**: ~637
- **描述**: 通过 `as any` 类型断言强制访问 `gitUrl` 属性，绕过了 TypeScript 类型检查。若 `formData` 结构变化，此处不会有编译时警告。
- **严重程度**: **Medium**
- **修复建议**: 在 formData 类型定义中添加 `gitUrl?: string` 属性。

---

### 13. [Medium] Privacy.tsx 使用 `alert()` 显示地址轮换结果

- **文件**: [pages/Privacy.tsx](src/pages/Privacy.tsx#L83)
- **行号**: 83
- **描述**: `handleRotateAddress` 成功后调用 `alert(\`地址已轮换！新地址: ${result.newAddress}\`)`。生产环境不应使用 `alert()`，且新地址包含敏感信息不应用弹窗明文展示。
- **严重程度**: **Medium**
- **修复建议**: 使用 UI 内的成功消息卡片展示结果。

---

### 14. [Medium] Explorer.tsx `copied` 状态在多个复制按钮间共享有冲突

- **文件**: [pages/Explorer.tsx](src/pages/Explorer.tsx)
- **描述**: `copied` 是 string 类型的单一状态，多个 Copy 按钮（hash, miner, txid, from, to）共用。但每次复制操作都会设置 `setCopied(label)` 然后 2 秒后清除。如果用户快速连续点击不同复制按钮，前一个的绿色对勾会提前消失或与新的冲突。
- **严重程度**: **Medium**（功能上可用但行为不精确）
- **修复建议**: 为每个可复制元素使用独立状态，或使用 `Map<string, boolean>` 追踪多个复制状态。

---

### 15. [Medium] Orders.tsx 双重过滤：`statusFilter` 同时在 API 层和前端过滤

- **文件**: [pages/Orders.tsx](src/pages/Orders.tsx#L85-L95)
- **行号**: 85-95
- **描述**: `fetchOrders()` 将 `statusFilter` 传给 `orderApi.getList(statusFilter)` 做后端过滤，但 `filteredOrders` 又在前端对 `order.status !== statusFilter` 再过滤一次。这是多余的双重过滤。当后端正确过滤时无问题；如果后端返回了不同 status 映射的名称（如 `active` vs `executing`），则前端二次过滤会导致数据丢失。
- **严重程度**: **Medium**
- **修复建议**: 任选其一：后端过滤 or 前端过滤。如果信任后端数据，前端的 `statusFilter` 判断可以移除；如需前端过滤，则 API 不传 status 参数。

---

### 16. [Medium] Vite proxy `/rpc` rewrite 将路径重写为空

- **文件**: [vite.config.ts](vite.config.ts#L10-L14)
- **行号**: 10-14
- **描述**: `/rpc` 代理配置的 `rewrite: (path) => path.replace(/^\/rpc/, '')` 会将 `/rpc` 重写为 `''`（空路径），实际请求变成 `http://localhost:8545/`（根路径）。而 API 层所有 RPC 调用发送到 `POST /rpc`。如果后端 RPC 监听在 `/` 根路径而非 `/rpc` 子路径上，这样可以工作；但如果后端是标准 JSON-RPC 监听在 `/` 上，这也许无问题——但语义上容易混淆。需确认后端是否期望根路径还是 `/rpc` 路径接收请求。
- **严重程度**: **Medium**
- **修复建议**: 确认后端 RPC 端点路径，确保代理配置与后端一致。

---

### 17. [Medium] Statistics.tsx 使用 `as unknown as` 双重类型断言提取未声明字段

- **文件**: [pages/Statistics.tsx](src/pages/Statistics.tsx#L107-L112)
- **行号**: 107-112
- **描述**: 
  ```typescript
  const distribution = (taskData as unknown as { distribution?: TaskDistributionItem[] }).distribution
  const dailyData = (blockData as unknown as { dailyData?: DailyBlockData[] }).dailyData
  ```
  使用 `as unknown as` 双重类型断言强行从 API 返回值中提取未在类型定义中声明的字段。如果后端不返回这些字段，值为 `undefined` 但不会报错，页面会静默显示空内容。
- **严重程度**: **Medium**
- **修复建议**: 在 `BlockStats` 和 `TaskStats` 类型定义中添加 `distribution` 和 `dailyData` 字段，或使用安全的可选链。

---

### 18. [Medium] Privacy.tsx SettingCard 的 toggle 状态是组件内部状态，修改不持久化

- **文件**: [pages/Privacy.tsx](src/pages/Privacy.tsx#L509-L520)
- **行号**: 509-520
- **描述**: `SettingCard` 组件内部使用 `useState(enabled)` 管理开关状态。用户切换后状态仅在组件生命周期内有效，页面刷新后恢复默认值。且切换操作没有调用任何 API 保存配置。
- **严重程度**: **Medium**
- **修复建议**: 将状态提升到父组件并调用 API 或 localStorage 持久化。

---

### 19. [Low] Account.tsx 私钥永远显示为硬编码字符串

- **文件**: [pages/Account.tsx](src/pages/Account.tsx#L81)
- **行号**: 81
- **描述**: `const privateKey = '*** 私钥已加密存储于本地 ***'`。即使用户点击"显示私钥"按钮，看到的也只是这个硬编码字符串。复制按钮也只会复制这个字符串到剪贴板。功能形同虚设。
- **严重程度**: **Low**（安全上不构成风险，但功能不完整）
- **修复建议**: 如不打算暴露私钥（推荐做法），应移除"显示/复制"按钮并明确告知用户通过导出 keystore 文件备份。

---

### 20. [Low] Miners.tsx 硬编码虚假数据填充 MinerDisplay 扩展字段

- **文件**: [pages/Miners.tsx](src/pages/Miners.tsx#L100-L112)
- **行号**: 100-112
- **描述**: 
  ```typescript
  avgResponseTime: 1.5,     // 硬编码
  uptime: m.completedTasks > 0 ? 99.5 : 95,  // 硬编码估算
  joinDate: Date.now() - 90 * 24 * 60 * 60 * 1000,  // 硬编码3个月前
  lastActive: Date.now(),   // 硬编码为当前时间
  ```
  多个字段使用硬编码假数据，UI 展示的数据不真实。
- **严重程度**: **Low**
- **修复建议**: 在后端 `miner_getList` 接口中返回这些字段，或在 UI 上标注"数据暂不可用"。

---

### 21. [Low] Statistics.tsx `avgBlockTime` 硬编码为 12

- **文件**: [pages/Statistics.tsx](src/pages/Statistics.tsx#L101)
- **行号**: 101
- **描述**: `const avgBlockTime = totalBlocks > 0 ? 12 : 0` — 平均出块时间被硬编码为 12 秒，不反映真实网络状态。
- **严重程度**: **Low**
- **修复建议**: 从后端获取实际的平均出块时间，或在 UI 标注为"设计目标值"。

---

### 22. [Low] Statistics.tsx `avgTaskDuration` 固定为 0

- **文件**: [pages/Statistics.tsx](src/pages/Statistics.tsx#L105)
- **行号**: 105
- **描述**: `avgTaskDuration: 0` 硬编码为 0，卡片显示"0min"。
- **严重程度**: **Low**
- **修复建议**: 从后端获取或隐藏此卡片直到数据可用。

---

### 23. [Low] Governance.tsx `proposalTypes` 和 `typeLabels` 中一致性问题

- **文件**: [pages/Governance.tsx](src/pages/Governance.tsx#L30-L55)
- **行号**: 30-55
- **描述**: `proposalTypes` 筛选器包含 `feature` 和 `governance` 类型，但 `typeLabels` 映射只有 `parameter`、`funding`、`protocol`、`emergency`。同时 CreateProposalModal 的选项也只有后四种。如果提案的 `type` 是 `feature` 或 `governance`，`typeLabels` 会 fallback 到 `|| 'badge-info'`，且标签会直接显示原始类型名。
- **严重程度**: **Low**
- **修复建议**: 统一筛选器选项和 `typeLabels` 映射的 key，使之一致。

---

### 24. [Low] Statistics.tsx PieChart label 显示 `${value}%` 但值不一定是百分比

- **文件**: [pages/Statistics.tsx](src/pages/Statistics.tsx#L177)
- **行号**: 177
- **描述**: `label={({ type, value }) => \`${type}: ${value}%\`}` 将 `blockTypeData` 的 `value`（区块数量）当成百分比显示。如果 taskBlocks=100, idleBlocks=50，PieChart 会显示 "任务区块: 100%"，这不是百分比而是绝对数。
- **严重程度**: **Low**
- **修复建议**: 计算百分比 `Math.round(value / total * 100)` 后再加 `%`，或不加 `%` 单位。

---

### 25. [Low] Explorer.tsx `copied` 2秒后清空可能导致组件已卸载时 setState

- **文件**: [pages/Explorer.tsx](src/pages/Explorer.tsx#L153)
- **行号**: 153
- **描述**: `setTimeout(() => setCopied(''), 2000)` — 如果用户在 2 秒内导航离开 Explorer 页面，组件卸载后 `setCopied` 仍会被调用。React 18+ 不再警告但这仍是不良实践。
- **严重程度**: **Low**
- **修复建议**: 在 `useEffect` cleanup 中清除 timeout。

---

### 26. [Low] Account.tsx ExportKeyModal `handleExport` 使用 `alert()` 提示密码不匹配

- **文件**: [pages/Account.tsx](src/pages/Account.tsx#L471)
- **行号**: ~471
- **描述**: `alert('密码不匹配')` 在生产环境中应使用内联错误提示。
- **严重程度**: **Low**
- **修复建议**: 使用表单内联错误状态替代 `alert()`。

---

### 27. [Low] Mining.tsx `fetchData` 定义在组件内且作为 `setInterval` 回调导致闭包问题

- **文件**: [pages/Mining.tsx](src/pages/Mining.tsx#L86-L102)
- **行号**: 86-102
- **描述**: `fetchData` 在组件体内定义，然后在 `useEffect(() => { ...; const interval = setInterval(fetchData, 10000) }, [])` 中使用。由于 `useEffect` 依赖为空数组 `[]`，`fetchData` 引用的是初始闭包，不会捕获后续的状态更新。虽然在此场景中 `fetchData` 不依赖组件状态（它只调 API 和 set state），所以实际影响不大，但 `useEffect` missing deps 是一个 lint warning。
- **严重程度**: **Low**
- **修复建议**: 将 `fetchData` 用 `useCallback` 包裹并添加到 `useEffect` 依赖数组中。

---

### 28. [Low] Provider.tsx `useEffect` 缺少 `account` 依赖

- **文件**: [pages/Provider.tsx](src/pages/Provider.tsx#L137-L143)
- **行号**: 137-143
- **描述**: 
  ```typescript
  useEffect(() => {
    if (isConnected) { fetchProviderStatus() }
    else { setLoading(false) }
  }, [isConnected])
  ```
  `fetchProviderStatus` 内部引用了 `account?.address`，但 `useEffect` 依赖数组只有 `[isConnected]`。如果 `account` 变化但 `isConnected` 不变，不会重新获取数据。
- **严重程度**: **Low**
- **修复建议**: 添加 `account?.address` 到依赖数组。

---

### 29. [Low] Wallet.tsx `useEffect` 缺少 `account` 依赖（同上模式）

- **文件**: [pages/Wallet.tsx](src/pages/Wallet.tsx#L246-L253)
- **行号**: 246-253
- **描述**: `useEffect` 依赖 `[isConnected]`，但 `fetchWalletData` 内部依赖 `account` 状态。
- **严重程度**: **Low**
- **修复建议**: 同上。

---

### 30. [Low] Settings.tsx 的 RPC endpoint 修改不会生效

- **文件**: [pages/Settings.tsx](src/pages/Settings.tsx#L394-L401)
- **行号**: 394-401
- **描述**: 网络设置中允许用户修改 RPC 节点地址，但 API 层的 `RPC_URL` 是硬编码为 `'/rpc'` 的常量。用户修改的设置只保存在 localStorage，不会影响实际 RPC 调用地址。功能完全无效。
- **严重程度**: **Low**
- **修复建议**: API 层的 `RPC_URL` 应从 Settings 读取配置，或在 Settings 中标注此功能尚未实现。

---

## 路由与页面对应检查

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

**结论**: 所有 18 个路由与页面组件一一对应，无遗漏或错配。

---

## Store 状态检查

| Store | 持久化 | 问题 |
|-------|--------|------|
| `useAccountStore` | `wallet_address` → localStorage | `setConnected(false)` 同时清除 `pouw_wallet_mnemonic`，行为正确 |
| `useNotificationStore` | 无持久化 | 正常 — 通知不需要持久化 |
| `useUIStore` | 无持久化 | 低优先级改进：`sidebarOpen` 和 `theme` 可考虑持久化 |

**结论**: Store 层基本健康，无严重 bug。`useNotificationStore` 定义了但多数页面未使用（见各页面错误处理仅用 `console.error`）。

---

## 汇总统计

| 严重程度 | 数量 |
|----------|------|
| Fatal | 3 |
| Severe | 4 |
| Medium | 12 |
| Low | 11 |
| **合计** | **30** |

---

## 最高优先级修复建议（Top 5）

1. **修复 `exchangeApi.getHistory` catch 块的 `success: true`** — 一行改动，影响最大
2. **移除 localStorage 中的助记词存储** — 关键安全问题
3. **修复 TaskDetail.tsx 暂停按钮** — 用户操作不可逆
4. **修复 `accountApi.exportWallet` 缺少 password 参数** — 功能完全失效
5. **修复 Statistics.tsx 90d 时间范围与 API 类型不匹配** — 可能导致后端错误
