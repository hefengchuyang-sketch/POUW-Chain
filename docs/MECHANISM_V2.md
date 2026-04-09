# Mechanism V2 Blueprint

## 目标

- 有用计算：PoUW 结果必须可验证，避免空转算力。
- 安全性：默认启用 S-Box 增强层，降级路径必须可审计。
- 不可预知性：任务挑战绑定链上上下文，抑制预训练与抢跑。
- 可持续出块：哈希难度 + 工作量难度双通道联动，防抖与防投机并存。

## 分层设计

1. 共识层（Consensus）
- 哈希难度通道：控制区块哈希目标。
- 工作量难度通道：控制 PoUW 最低工作阈值。
- 空闲激励控制：无单场景保持活性，但引入惩罚窗口防投机。

2. 任务与证明层（PoUW）
- challenge 由 `prev_hash + block_height + time_window + miner_id` 派生。
- proof 使用结构化 `proof_json`，包含输入/挑战/轨迹/输出摘要和时间窗。
- 验证节点执行最小可验证子集校验（commitment、proof_hash、窗口、重复提交）。

3. 加密层（S-Box + AES-GCM）
- AES-GCM 负责机密性与完整性。
- S-Box 作为滚动非线性增强层，默认优先 ENHANCED。
- 会话元数据携带 `sbox_hash` 与 `sbox_block_height`。
- 会话重协商触发：消息上限或会话寿命超限。

4. 治理与运维层
- 机制策略版本化（version/rollout/max_ratio_step）。
- 支持灰度调参与回滚到上一策略。
- 降级事件可查询审计（S-Box unavailable fallback）。

## 关键策略

- `enforceEnhancedDefault=true`
- `allowDowngradeToStandard=true`（可关闭）
- `downgradeRequiresAudit=true`
- `max_ratio_step` 限制单轮 S-Box 比例变化，防止参数突变。

## 回滚策略

- 共识机制使用 `configure_mechanism_strategy(..., rollback_to_previous=True)`。
- S-Box 策略通过 RPC 或模块函数恢复为上一版配置。

## 已落地接口

- RPC: `chain_updateMechanismStrategy`
- RPC: `sbox_getEncryptionPolicy`
- RPC: `sbox_setEncryptionPolicy`
- RPC: `sbox_getDowngradeAudit`

## 当前状态与待优化

已闭环：

- 主程序默认接入 ComputeMarketV3（下单/查单/市场查询优先走 V3 路径）。
- 订单生命周期事件可查询（create/accept/result_commit/result_reveal/settle）。
- 评分派单采用加权抽签，包含质量、可靠性、时效与惩罚项。

待优化：

- 兼容兜底路径仍存在，建议增加 `compute.v3_required` 严格模式并逐步下线旧写路径。
- 协议挑战分建议从本地时间窗口切换为链上可复现随机源，提升跨节点一致性与审计可复算性。
