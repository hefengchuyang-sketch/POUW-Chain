# MainCoin 前端代码审计报告

> 审计范围: `frontend/src/` 全部源代码  
> 技术栈: React 18.2 + TypeScript 5.2 + Vite 5.0 + TailwindCSS 3.3 + Zustand 4.4  
> 总文件数: 22 个源文件 (1 入口 + 1 路由 + 1 布局 + 1 API + 1 Store + 1 CSS + 16 页面)  
> API 总行数: 2132 行 · 页面总行数: ~8500+ 行

---

## 一、文件清单

| 文件 | 用途 | 行数 |
|---|---|---:|
| `main.tsx` | React 18 入口 (StrictMode + BrowserRouter) | ~13 |
| `App.tsx` | 路由表 (18 页面，Connect 独立布局) | ~82 |
| `api/index.ts` | 全部 JSON-RPC 2.0 + REST 接口封装 | 2132 |
| `store/index.ts` | Zustand 状态管理 (3 个 Store) | ~82 |
| `index.css` | TailwindCSS + 自定义暗色主题 + 组件样式 | 427 |
| `components/Layout.tsx` | 侧边栏 + 顶栏 + 通知 + 系统状态轮询 | ~280 |
| `components/P2PTasks.tsx` | P2P 分布式任务列表 | ~240 |
| `pages/Dashboard.tsx` | 仪表盘 (统计卡片 + 饼图 + 最近任务) | ~447 |
| `pages/Tasks.tsx` | 任务管理 + 创建任务弹窗 (三步表单) | ~711 |
| `pages/TaskDetail.tsx` | VSCode 风格任务详情 (文件树/日志/输出) | ~609 |
| `pages/Market.tsx` | GPU 算力市场 (板块 → 区块 → 下单) | ~517 |
| `pages/Wallet.tsx` | 钱包 (余额/转账/兑换/质押评价) | ~879 |
| `pages/Orders.tsx` | 订单列表 (搜索/筛选/展开明细) | ~400 |
| `pages/Account.tsx` | 账户身份 (地址/私钥/助记词/密钥导出) | ~539 |
| `pages/Connect.tsx` | 钱包连接 (创建/导入助记词/密钥文件) | ~973 |
| `pages/Mining.tsx` | 挖矿控制 (开始/停止/奖励图表) | ~400 |
| `pages/Miners.tsx` | 矿工列表 (搜索/筛选/排序/详情弹窗) | ~443 |
| `pages/Governance.tsx` | 治理提案列表 + 创建提案弹窗 | ~500 |
| `pages/ProposalDetail.tsx` | 提案详情 + 投票面板 | ~400 |
| `pages/Explorer.tsx` | 区块浏览器 (板块/搜索/UTXO 追溯) | ~722 |
| `pages/Statistics.tsx` | 网络统计 (折线图/柱状图/饼图) | ~500 |
| `pages/Provider.tsx` | 算力提供者 (注册/挖矿/仪表盘) | ~500 |
| `pages/Privacy.tsx` | 隐私评分 + 地址分析 + 混币 + 路线图 | ~616 |
| `pages/Help.tsx` | 帮助中心 (FAQ + 入门指南) | ~160 |
| `pages/Settings.tsx` | 设置 (通用/外观/通知/网络/隐私) | ~532 |

---

## 二、架构评估

### 2.1 整体架构

**优点：**
- 统一的 JSON-RPC 2.0 通信协议，所有后端调用通过 `rpcCall()` 和 `request()` 两个底层函数
- 每个 API 模块都有完善的 fallback（try/catch 返回空默认值），页面不会因接口失败崩溃
- TypeScript 严格模式 (`strict: true`, `noUnusedLocals`, `noUnusedParameters`)
- 组件内数据获取逻辑清晰：useEffect → fetch → setState → render
- 暗色终端风格 UI 一致性好，CSS 变量 + Tailwind 自定义主题组合得当

**架构问题：**
1. **单文件 API 层过于庞大** — `api/index.ts` 达 2132 行，包含 20+ 个 API 模块和 40+ 个接口定义，应拆分为 `api/wallet.ts`, `api/mining.ts`, `api/governance.ts` 等独立模块
2. **无全局错误处理** — 每个 API 调用独立 try/catch，但没有统一的错误上报/Toast 通知机制
3. **Store 利用率低** — Zustand 只有 3 个简单 Store，大量数据通过 useState 管理在页面组件内。应将共享数据（如矿工列表、市场数据等）放入 Store
4. **无 API 请求缓存** — 每次组件挂载都重新 fetch，没有使用 SWR/React Query 等缓存策略
5. **无国际化支持** — UI 文案全部硬编码中文，Settings 页面虽有语言选项但没有实际的 i18n 框架

---

## 三、关键问题 (按严重程度排序)

### 🔴 严重 (P0)

#### 3.1 Account.tsx — 密钥导出使用假数据
- **文件**: `pages/Account.tsx` ExportKeyModal 组件
- **行号**: ExportKeyModal 的 `handleExport` 函数
- **描述**: 导出密钥文件时创建的 Blob 内容为硬编码字符串 `'encrypted_keystore_content'`，实际应调用 `walletApi.exportKeystore()` 获取真实加密密钥
- **影响**: 用户以为自己下载了备份，实际得到的是无效文件，资产有丢失风险

```typescript
// 当前代码 (假数据!)：
const blob = new Blob(['encrypted_keystore_content'], { type: 'application/json' })

// 应改为：
const keystore = await walletApi.exportKeystore(password)
const blob = new Blob([JSON.stringify(keystore)], { type: 'application/json' })
```

#### 3.2 ProposalDetail.tsx — 投票权硬编码
- **文件**: `pages/ProposalDetail.tsx`
- **描述**: 投票权数值固定写死为 `1,250`，不是从 API 获取
- **影响**: 所有用户看到完全相同的投票权数值，投票权重无法正确反映实际持仓

```tsx
// 两处硬编码:
<p className="text-sm text-console-muted mb-4">您的投票权: 1,250</p>
<p className="text-sm text-console-muted">使用 1,250 投票权</p>
```

#### 3.3 Privacy.tsx — 混币弹窗无实际 API 调用
- **文件**: `pages/Privacy.tsx` MixerModal 组件
- **描述**: 混币服务弹窗（MixerModal）step 2 只展示旋转动画，没有调用任何 API 执行混币操作
- **影响**: 用户以为混币在进行中，实际什么都没发生

---

### 🟡 中等 (P1)

#### 3.4 axios 依赖已安装但完全未使用
- **文件**: `package.json`
- **描述**: `axios@1.6.2` 在 dependencies 中，但整个项目全部使用原生 `fetch`（在 `api/index.ts` 中）
- **影响**: 增加了约 30KB 的打包体积
- **建议**: 从 `package.json` 中移除 `axios`

#### 3.5 Tasks.tsx — useAccountStore() 调用但未使用返回值
- **文件**: `pages/Tasks.tsx` 第 48 行
- **描述**: `useAccountStore()` 被调用但没有解构任何值，也没有利用返回值
- **影响**: 不必要的状态订阅，可能导致组件在账户状态变化时无意义地重渲染

```tsx
// 第 48 行:
useAccountStore()  // 调用了但什么也没拿
```

#### 3.6 Provider.tsx — 不安全的类型断言
- **文件**: `pages/Provider.tsx` `fetchProviderStatus` 函数
- **描述**: 使用 `(m as any).isLocal` 和 `myMiner as unknown as ProviderProfile` 进行不安全的类型转换
- **影响**: 运行时可能出现属性缺失导致 crash

```typescript
const myMiner = minerList.miners.find(m => 
  m.address.includes(account?.address?.slice(0, 16) || 'not_found') || 
  (m as any).isLocal  // ← any 类型
)
if (myMiner) {
  setProfile(myMiner as unknown as ProviderProfile)  // ← 双重类型断言
}
```

#### 3.7 Market.tsx — 重复数据获取逻辑
- **文件**: `pages/Market.tsx`
- **描述**: `fetchData`（在 useEffect 内定义）和 `refreshData` 函数几乎完全相同，逻辑重复
- **建议**: 提取为一个共享的 `loadData` 函数，在 useEffect 和刷新按钮中共用

#### 3.8 Governance.tsx — any 类型使用
- **文件**: `pages/Governance.tsx` 约第 93 行
- **描述**: 提案数据映射时使用 `any` 类型
- **建议**: 使用 `api/index.ts` 中已定义好的 `Proposal` 接口

#### 3.9 Statistics.tsx — 不安全的类型断言
- **文件**: `pages/Statistics.tsx`
- **描述**: 使用 `as unknown as` 访问 API 响应中未在类型定义中声明的额外字段
- **建议**: 扩展 API 类型定义以包含这些字段，或使用可选链

#### 3.10 Settings.tsx — SettingCard 组件状态与父组件断开
- **文件**: `pages/Privacy.tsx` SettingCard 子组件
- **描述**: SettingCard 组件内部使用 `useState(enabled)` 管理开关状态，但该状态独立于父组件，切换开关不会反映到外部
- **影响**: 隐私设置中的自动混币、地址轮换等开关只是"装饰性"的，没有实际效果

---

### 🟢 轻微 (P2)

#### 3.11 Miners.tsx — 硬编码默认值
- **文件**: `pages/Miners.tsx`
- **描述**: 矿工卡片中 `uptime`、`avgResponseTime`、`joinDate` 使用硬编码默认值而非从 API 获取

#### 3.12 ProposalDetail.tsx — "相关链接"使用 `<a href="#">`
- **文件**: `pages/ProposalDetail.tsx`
- **描述**: "在区块浏览器中查看"和"讨论论坛"链接的 `href` 为 `#`，点击后回到页面顶部
- **建议**: 链接到实际的区块浏览器地址（如 `/explorer?tx={txId}`），或在开发中时隐藏

#### 3.13 Provider.tsx — 使用 `<a href="/connect">` 而非 `<Link>`
- **文件**: `pages/Provider.tsx` 未连接钱包提示
- **描述**: 使用原生 `<a>` 标签而非 React Router 的 `<Link>` 组件，触发整页刷新
- **建议**: 改为 `<Link to="/connect">`

---

## 四、未使用的代码

### 4.1 未使用的 API 模块 (7 个)

以下 API 模块在 `api/index.ts` 中定义并导出，但没有被任何页面组件导入使用：

| API 模块 | 行号 | 描述 | 建议 |
|---|---:|---|---|
| `marketApi` | 915 | 算力市场订单 | Market.tsx 实际使用 minerApi + orderbookApi，此模块冗余 |
| `blockchainApi` | 1335 | 区块链查询 | 功能与 `explorerApi` 高度重叠 |
| `pricingApi` | 1376 | 动态定价 (6 个方法) | 可集成到 Market 或 Tasks 页面 |
| `queueApi` | 1550 | 任务队列 (4 个方法) | 可集成到 TaskDetail 页面显示排队状态 |
| `marketMonitorApi` | 1598 | 市场监控面板 (3 个方法) | 可集成到 Dashboard 或 Statistics |
| `settlementApi` | 1655 | 结算记录 (3 个方法) | 可集成到 Orders 或 Wallet |
| `billingApi` | 1694 | 资源计费 (3 个方法) | 可集成到 Task 创建流程 |

**总计约 350+ 行未使用代码**

### 4.2 未使用的 npm 依赖

| 包名 | 版本 | 说明 |
|---|---|---|
| `axios` | 1.6.2 | 全项目使用原生 fetch，未发现任何 axios import |
| `date-fns` | 2.30 | 未在源码中发现 import，所有日期格式化用 `toLocaleString()` |

### 4.3 未使用/多余的 TypeScript 配置

- `tsconfig.json` 配置了路径别名 `@/* → src/*`，但全项目无任何文件使用 `@/` 导入（全部使用 `../` 相对路径）
- `vite.config.ts` 缺少对应的 `resolve.alias` 配置，即使使用 `@/` 路径也不会在构建时正确解析

---

## 五、API 调用全景

### 5.1 所有页面 API 使用情况

| 页面 | 使用的 API 模块 | 真实 RPC 调用 | 轮询/自动刷新 |
|---|---|:---:|:---:|
| Dashboard | dashboardApi, statsApi, miningApi | ✅ | ❌ |
| Tasks | taskApi, encryptedTaskApi | ✅ | ❌ |
| TaskDetail | taskApi, stakingApi | ✅ | ✅ 3s/5s (运行状态) |
| Market | minerApi, orderbookApi | ✅ | ❌ |
| Wallet | walletApi, transferApi, accountApi, exchangeApi, stakingApi | ✅ | ❌ |
| Orders | orderApi | ✅ | ❌ |
| Account | walletApi | ✅ (但导出用假数据) | ❌ |
| Connect | walletApi | ✅ | ❌ |
| Mining | miningApi | ✅ | ✅ 10s |
| Miners | minerApi | ✅ | ❌ |
| Governance | governanceApi | ✅ | ❌ |
| ProposalDetail | governanceApi | ✅ | ❌ |
| Explorer | explorerApi, utxoApi | ✅ | ✅ (可切换) |
| Statistics | statsApi, dashboardApi | ✅ | ❌ |
| Provider | minerApi, miningApi | ✅ | ❌ |
| Privacy | privacyApi | ✅ (混币除外) | ❌ |
| Help | - (纯静态) | N/A | N/A |
| Settings | - (仅 localStorage) | N/A | N/A |
| Layout | 直接 rpcCall | ✅ | ✅ 30s (系统状态) |
| P2PTasks | p2pTaskApi | ✅ | ✅ 10s |

**结论**: 除 Help 和 Settings 外，所有页面都使用真实 RPC 调用，无 `console.log` 占位符式的假接口。

### 5.2 REST vs RPC 混用

`api/index.ts` 同时导出了 `rpcCall()` (JSON-RPC over `/rpc`) 和 `request()` (REST over `/api`)。但仅有极少数方法使用 `request()`：
- `minerApi.getMinerBehaviorReport()` — 使用 REST
- `marketApi.getQuotes()` / `acceptQuote()` — 使用 REST

其余全部使用 JSON-RPC。REST 方法可能是遗留代码或未实现的后端端点。

---

## 六、加载/错误状态覆盖

| 页面 | 加载中 | 错误/重试 | 空数据 | 未连接提示 |
|---|:---:|:---:|:---:|:---:|
| Dashboard | ✅ 骨架屏 | ✅ 重试按钮 | ✅ | ❌ |
| Tasks | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ❌ |
| TaskDetail | ✅ 旋转加载 | ❌ console.error | ✅ | ❌ |
| Market | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ❌ |
| Wallet | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ✅ |
| Orders | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ✅ |
| Account | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ❌ |
| Connect | ✅ 按钮状态 | ✅ 错误提示 | N/A | N/A |
| Mining | ✅ 旋转加载 | ✅ 操作结果提示 | ✅ | ❌ |
| Miners | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ❌ |
| Governance | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ❌ |
| ProposalDetail | ✅ 旋转加载 | ✅ 404 提示 | N/A | ❌ |
| Explorer | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ❌ |
| Statistics | ✅ 旋转加载 | ❌ 静默 catch | ✅ | ❌ |
| Provider | ✅ 旋转加载 | ❌ console.error | N/A | ✅ |
| Privacy | ✅ 旋转加载 | ❌ console.error | ✅ | ❌ |

**主要缺陷**: 大多数页面在 API 失败时仅 `console.error`，不向用户展示任何错误反馈。建议：
- 引入全局 Toast/Notification 系统（已有 `useNotificationStore`，但页面中未使用）
- 对关键操作（转账、下单、投票）添加明确的错误 UI

---

## 七、UX / 可访问性问题

### 7.1 可访问性 (a11y)

| 问题 | 影响文件 | 描述 |
|---|---|---|
| 缺少 `aria-label` | 多个页面 | 纯图标按钮（如复制、刷新、外部链接）缺少 `aria-label`，屏幕阅读器无法描述 |
| 自定义 Toggle 开关缺少语义 | Settings.tsx, Privacy.tsx | 自定义 CSS 开关不使用 `<input type="checkbox" role="switch">`，键盘无法操作 |
| `<details>` 交互 | Help.tsx | FAQ 使用 `<details>` + `list-none`，移除了默认的展开/折叠标记但无 ARIA 标注 |
| 颜色对比度 | index.css | 部分 `text-console-text-muted` 在深色背景上对比度不足 (需实测 WCAG 2.1 AA) |
| 板块选择按钮 | Market.tsx | GPU 板块选择使用纯色差区分选中/未选中状态，色盲用户可能无法辨别 |

### 7.2 UX 问题

| 问题 | 文件 | 描述 |
|---|---|---|
| 无分页 | Tasks, Orders, Explorer, Miners | 所有列表无分页，数据量大时性能和可用性下降 |
| 无表单验证提示 | Tasks.tsx 创建任务 | 步骤可直接跳转，不验证前一步是否填写完整 |
| 助记词验证仅验证 3 个词 | Connect.tsx | 安全性尚可但可能不够严谨 |
| 兑换无确认二次弹窗 | Wallet.tsx | 兑换操作直接执行，不像转账那样有确认步骤 |
| 投票后不刷新数据 | ProposalDetail.tsx | 投票成功后关闭弹窗但不刷新提案数据，用户看到的仍是旧票数 |

---

## 八、路由完整性

```
App.tsx 路由表 (18 路由):
├── /connect               → Connect.tsx (独立布局)
└── <Layout>
    ├── /                   → Dashboard.tsx
    ├── /tasks              → Tasks.tsx
    ├── /tasks/:taskId      → TaskDetail.tsx
    ├── /market             → Market.tsx
    ├── /wallet             → Wallet.tsx
    ├── /orders             → Orders.tsx
    ├── /account            → Account.tsx
    ├── /mining             → Mining.tsx
    ├── /miners             → Miners.tsx
    ├── /governance         → Governance.tsx
    ├── /governance/:id     → ProposalDetail.tsx
    ├── /statistics         → Statistics.tsx
    ├── /explorer           → Explorer.tsx
    ├── /provider           → Provider.tsx
    ├── /help               → Help.tsx
    ├── /settings           → Settings.tsx
    └── /privacy            → Privacy.tsx
```

**问题:**
1. **无 404 页面** — 访问不存在的路径会显示空白的 Layout
2. **无路由守卫** — 需要钱包连接的页面（Wallet, Orders, Mining, Provider 等）各自独立检查 `isConnected`，应统一为 `ProtectedRoute` 高阶组件
3. **P2PTasks 组件未独立路由** — `P2PTasks.tsx` 是一个组件，嵌入在 Tasks.tsx 中，但没有独立路由可访问

---

## 九、Store 使用分析

| Store | 字段 | 使用者 |
|---|---|---|
| `useAccountStore` | account, isConnected, isLoading, error | Layout, Tasks(未用), Wallet, Orders, Provider |
| `useNotificationStore` | notifications, add, remove, clearAll | 仅 Layout (展示) |
| `useUIStore` | sidebarOpen, theme | 仅 Layout |

**问题:**
- `useNotificationStore` 只有 Layout 消费通知列表，但**没有任何页面调用 `addNotification()`**。通知系统形同虚设。
- `useAccountStore` 被 Tasks.tsx 导入和调用但未使用返回值。
- 大量页面使用 `console.error()` 而非 `addNotification({ type: 'error', ... })` 上报错误。

---

## 十、潜在的重复代码

| 模式 | 涉及文件 | 描述 |
|---|---|---|
| 数据获取模式 | 所有页面 | `useState + useEffect + async fetch + setLoading + try/catch` 在 16 个页面中重复，可提取为自定义 Hook (`useFetch`, `useRpc`) |
| GPU 类型常量 | Market.tsx, Provider.tsx, Tasks.tsx | GPU 型号列表在多处独立维护，应统一为共享常量 |
| 复制到剪贴板 | Explorer.tsx, Account.tsx, TaskDetail.tsx, Connect.tsx | 复制功能在多个文件中独立实现，可提取为 `useCopyToClipboard` Hook |
| 加载/空状态 UI | 所有页面 | 旋转加载图标和空状态提示的 JSX 高度相似 |
| fetchData 与 refreshData | Market.tsx | 同一文件中两个函数几乎完全相同 |
| `api/index.ts` 内重叠 | blockchainApi vs explorerApi | `getHeight`, `getBlock`, `getLatestBlocks` 在两个 API 模块中重复定义 |

---

## 十一、构建/配置问题

| 问题 | 文件 | 描述 |
|---|---|---|
| `@/` 路径别名无效 | tsconfig.json + vite.config.ts | tsconfig 配置了 `@/* → src/*`，但 vite.config.ts 缺少 `resolve.alias`。虽然目前没有文件使用此别名，但配置不一致容易误导开发者 |
| Vite proxy `/rpc` rewrite | vite.config.ts | `/rpc` 被 rewrite 为空 `''`，实际请求到 `http://localhost:8545`，需确认后端是否监听根路径 |
| `devDependencies` 完整性 | package.json | 未看到 `eslint` 或 `prettier` 配置，代码风格依赖开发者自觉 |

---

## 十二、改进建议优先级

### 必须修复 (P0)
1. ✗ Account.tsx 密钥导出改为真实 API 调用
2. ✗ ProposalDetail.tsx 投票权从 API 动态获取
3. ✗ Privacy.tsx MixerModal 实现真实混币 API 调用

### 建议修复 (P1)
4. 移除 `axios` 和 `date-fns` 未使用依赖
5. 修复 Tasks.tsx 中无意义的 `useAccountStore()` 调用
6. Provider.tsx 消除 `as any` / `as unknown as` 类型断言
7. 合并 Market.tsx 重复的 fetch 逻辑
8. 投票成功后刷新提案数据
9. 添加 404 路由
10. 使用 `useNotificationStore` 替代 `console.error` 做用户可见的错误反馈
11. 清理 7 个未使用的 API 模块或集成到相应页面

### 建议优化 (P2)
12. 拆分 `api/index.ts` 为多个模块文件
13. 提取公共 Hook (`useFetch`, `useCopyToClipboard`)
14. 统一 GPU 类型常量
15. 列表页面添加分页
16. 添加路由守卫 (`ProtectedRoute`)
17. 补充 `aria-label` 和键盘可访问性
18. 配置 ESLint + Prettier
19. 修复 `vite.config.ts` 中的 `resolve.alias` 配置一致性

---

*审计完成 — 共发现 3 个严重问题、7 个中等问题、3 个轻微问题、7 个未使用 API 模块、2 个未使用 npm 依赖。*
