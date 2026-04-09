# 主流程评审与改进建议（2026-04-09）

## 结论摘要

当前主流程已经可以闭环运行：

- 节点启动 -> 模块初始化 -> RPC 暴露
- 计算市场下单/查单/市场查询优先走 ComputeMarketV3
- 订单生命周期事件可查询（create/accept/result_commit/result_reveal/settle 等）
- 自动化测试全绿（非集成 + 集成）

但从设计最优角度看，仍有可改进空间，主要集中在“兼容层并存”和“挑战分来源治理化”两类。

## 已验证闭环

1. 启动闭环
- main.py 初始化 compute_market_v3 并注入 rpc_service。

2. 调度闭环
- compute_submitOrder / compute_getOrder / compute_getMarket / compute_acceptOrder / compute_completeOrder
  默认优先走 ComputeMarketV3。

3. 事件闭环
- compute_getOrderEvents 可读取订单交易化生命周期。

4. 测试闭环
- tests（不含 integration）通过
- tests/integration 通过

## 发现的问题与风险（按优先级）

### P1: 兼容路径仍较重，存在双轨维护成本

现状：
- rpc_service 中 compute_* 方法虽然优先走 V3，但仍保留较多 market_orders 旧逻辑兜底。

风险：
- 未来迭代可能出现“新逻辑改了，旧兜底忘记同步”的行为分叉。
- 排障成本增加（同一个接口两套语义）。

建议：
- 引入 feature flag：compute.v3_required。
- 在测试和预发布环境开启 strict 模式：若未命中 V3 直接报错，不走旧兜底。
- 旧路径仅保留只读兼容窗口，规划下线时间。

### P1: 协议挑战分仍偏本地时间窗口，跨节点一致性有潜在风险

现状：
- 调度挑战分使用时间窗口参与哈希。

风险：
- 节点时钟偏差会导致挑战分不一致。
- 回放/审计时难以复算出同一顺序。

建议：
- 挑战随机源改为链上可复现源（例如前一区块哈希 + 高度 + 订单哈希）。
- 将 challenge_seed 写入订单事件，便于审计复算。

### P2: 扩展模块接入率不均衡

现状：
- main.py 中初始化了较多扩展模块，但并非都注入 RPC 或参与运行主环。

风险：
- “已实现但未接线”会造成能力感知偏差。

建议：
- 增加模块接入矩阵文档（初始化/注入RPC/生产路径使用/测试覆盖）。
- 对未接线模块明确标注为实验态或内部工具态。

## 建议的下一步改造（可执行）

1. 新增 strict 路由开关
- 配置项：compute.v3_required=true
- 行为：compute_* 接口若 V3 不可用则直接失败，不再回退旧 market_orders 写路径。

2. 挑战种子治理化
- 增加配置项：dispatch.challenge_source = chain|time_window
- 默认 chain，time_window 仅测试可用。

3. 文档治理
- 在 README 和 docs 中明确：
  - 当前默认主路径为 ComputeMarketV3
  - 旧路径为兼容兜底，非长期目标
  - 下线计划与版本窗口

## 本次目录整理记录

已做保守整理（不影响业务代码路径）：

- 根目录临时脚本 -> scripts/scratch/
  - grep_handle.py
  - temp_dump.py

- 根目录测试/运行输出 -> logs/archive/
  - node.log
  - node_out.txt
  - pytest_results.log

以上为“归档移动”，非删除。

## 判定

- 功能闭环：是
- 设计最优：尚未完全最优（仍建议按上面 P1/P2 项持续收敛）
- 当前可用性：可用于继续联调与增量迭代
