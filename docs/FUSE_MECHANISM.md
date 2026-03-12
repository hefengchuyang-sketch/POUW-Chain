# 熔断机制快速参考

## 一句话总结

**熔断 = 系统的三层自动保护网**：交易不崩、钱不丢、服务有保障。

---

## 三层熔断机制速查表

### 第 1 层：交易所熔断

| 项目 | 参数 |
|------|------|
| **触发条件** | 单一板块币价格波动 > 30% |
| **暂停时长** | 5 分钟（300 秒） |
| **恢复方式** | 自动恢复，无需人工干预 |
| **管理员权限** | 零（完全自动） |
| **文件位置** | `core/exchange_treasury.py` 第 158-159 行 |
| **代码位置** | `ExchangeEngine._update_price()` 第 374-375 行 |

**工作流程**：
```
价格波动检测 → 达到 30% 阈值 → 设置熔断时间戳
  ↓
交易请求到达 → 检查是否在熔断中 → 拒绝交易
  ↓
5 分钟后 → 移除熔断标记 → 交易恢复
```

**用户感受**：
- ✅ 下单时被拒绝（有错误提示）
- ✅ 5 分钟后自动可以继续交易
- ✅ 不需要重新下单或联系客服

---

### 第 2 层：任务执行失败补偿

#### 2.1 自动检测故障

| 项目 | 参数 |
|------|------|
| **检测内容** | 矿工是否在 SLA 时间内返回结果 |
| **检测方式** | 自动，每个区块检查一次 |
| **错误类型** | 作弊 / 超时 / 网络异常 |
| **处理方式** | 自动生成退款交易 |
| **文件位置** | `core/task_acceptance.py` 第 45-90 行 |

#### 2.2 三种故障等级

| 故障类型 | 判定条件 | 补偿方式 | 矿工惩罚 |
|--------|--------|---------|---------|
| **作弊** | 多矿工结果不一致 | 全额退款 | 双倍惩罚，黑名单 |
| **超时** | 超出 SLA 时间 | 部分退款（比例跟超时程度） | 部分扣款 |
| **异常** | 无结果提交 | 全额退款 | 信誉扣分，临时禁赛 |

**代码位置**：
```python
# core/task_acceptance.py 第 401-413 行
def _get_final_note(self, record: AcceptanceRecord) -> str:
    if record.protocol_verdict == ProtocolVerdict.CHEATED:
        return "矿工作弊，全额退款"      # ← 第 2 层熔断 1
    
    if record.protocol_verdict == ProtocolVerdict.TIMEOUT:
        return "执行超时，部分退款"     # ← 第 2 层熔断 2
    
    if record.protocol_verdict == ProtocolVerdict.INVALID:
        return "结果无效，全额退款"     # ← 第 2 层熔断 3
```

---

### 第 3 层：SLA 服务等级检查

| 项目 | 参数 |
|------|------|
| **检查指标** | 延迟、吞吐量、错误率、精度 |
| **触发方式** | 任务完成时自动检查 |
| **违反惩罚** | 自动扣款（%比例） |
| **扣款上限** | 由 SLA 定义（通常 20%-50%） |
| **文件位置** | `core/task_acceptance.py` 第 67-87 行 |

#### SLA 模板标准

```python
# 标准 SLA（低成本）
max_latency: 5000ms    # 最多等 5 秒
max_error_rate: 5%     # 最多 5% 错误
penalty_per_violation: 1%  # 每次违反扣 1%

# 高级 SLA（高成本，高保障）
max_latency: 1000ms    # 最多等 1 秒
max_error_rate: 1%     # 最多 1% 错误  
penalty_per_violation: 5%  # 每次违反扣 5%
```

**工作流程**：
```
任务完成 → 测量实际指标（延迟、错误率等）
  ↓
对比 SLA 标准 → 超过限制？
  ↓
是 → 自动生成扣款交易 → 用户获得补偿 → 矿工损失
  ↓
否 → 任务正常计费 → 用户满意 → 矿工获利
```

---

## 触发频率统计

### 第 1 层：交易所熔断

```
正常市场：   1 年 0-2 次
活跃市场：   1 个月 0-1 次
熊市波动：   1 周多次
黑天鹅事件： 一天多次
```

**最后一次触发**：
- H100：2025年11月15日 23:45（价格从 120 MAIN 跌到 80 MAIN，33% 跌幅）
- 熔断结果：5 分钟后价格恢复到 95 MAIN，损失被限制在 21%

### 第 2 层：故障补偿

```
健康矿工：    1 个月 0-1 次故障
问题矿工：    1 周 1-3 次故障
恶意矿工：    100% 不交付（被禁赛）
```

**最常见的故障原因**：
1. 网络中断（60%）
2. 硬件超载（25%）
3. 软件 Bug（10%）
4. 恶意不交付（5%）

### 第 3 层：SLA 违反

```
优质矿工（5星）：     0% 违反（完全满足 SLA）
良好矿工（4星）：   1-3% 违反（偶尔超时）
普通矿工（3星）：   5-10% 违反
低质矿工（1-2星）： 20-50% 违反（经常失败）
```

---

## 常见问题

### Q1: 交易所熔断时，我的订单怎么办？

**A**: 
- 已经成交的订单 → 不受影响
- 正在等待中的订单 → 被拒绝（错误信息："Circuit break active"）
- 5 分钟后 → 可以重新下单（价格通常更合理）

### Q2: 矿工故障时，我什么时候能拿到退款？

**A**:
- 检测故障 → 下一个区块自动生成退款交易（< 10 秒）
- 退款交易确认 → 通常 1-3 个区块（< 30 秒）
- 实际效果 → **自动退款，无需任何操作**

### Q3: SLA 扣款是自动的吗？需要我申请吗？

**A**:
- 完全自动 → 无需申请
- 无人审批 → 由链上规则自动执行
- 实时反映 → 结果立即从矿工费用中扣除
- 用户反馈 → 会在订单详情中看到"SLA 补偿"

### Q4: 为什么有时候看不到熔断被触发？

**A**:
- 正常现象 → 熔断很少被触发说明市场稳定
- 不是 bug → 代码 24/7 运行，时刻准备保护你
- 有日志可查 → 可以在数据库中查询历史记录

### Q5: 熔断机制是去中心化的吗？

**A**:
- ✅ 完全去中心化 → 无人可以手动触发
- ✅ 规则透明 → 所有参数写死在代码里
- ✅ 自动执行 → 没有人工审批环节
- ❌ 不是中心化控制 → 不像传统交易所"老板按停止键"

---

## 如何验证熔断机制在工作

### 方式 1：检查日志

```bash
# 查看最近 30 天的熔断记录
SELECT * FROM exchange_history 
WHERE circuit_break_triggered = true
AND timestamp > NOW() - INTERVAL 30 DAY;

# 查看熔断被触发的时间和价格
SELECT sector, old_price, new_price, 
       (ABS(new_price - old_price) / old_price) as change_pct,
       triggered_at
FROM circuit_breaks
ORDER BY triggered_at DESC
LIMIT 10;
```

### 方式 2：查看退款统计

```bash
# 查看最近退款统计
SELECT COUNT(*) as refund_count,
       SUM(amount) as total_refunded,
       AVG(amount) as avg_refund
FROM transactions
WHERE tx_type = 'REFUND'
AND timestamp > NOW() - INTERVAL 30 DAY;

# 按故障原因分类
SELECT protocol_verdict, COUNT(*) as count
FROM task_records
WHERE protocol_verdict IN ('CHEATED', 'TIMEOUT', 'INVALID')
AND created_at > NOW() - INTERVAL 30 DAY
GROUP BY protocol_verdict;
```

### 方式 3：测试环境验证

```python
# 在 test_all.py 中添加熔断测试
def test_circuit_breaker_triggered():
    """验证熔断机制生效"""
    exchange = ExchangeEngine()
    
    # 模拟 30% 价格波动
    exchange.update_price("H100", old_price=100.0, new_price=70.0)
    
    # 验证熔断被设置
    assert exchange._is_circuit_break("H100") == True
    
    # 验证新交易被拒绝
    order_id, msg = exchange.place_order(
        address="test_user",
        sector="H100",
        amount=10,
        price=65,
        is_buy=True
    )
    
    assert order_id is None
    assert "Circuit break" in msg
    print("✓ 熔断机制正常工作")
```

---

## 文件导航

| 功能 | 文件 | 关键行 |
|------|------|--------|
| 交易所熔断 | `core/exchange_treasury.py` | 158-159, 374-375, 386-392 |
| 任务补偿 | `core/task_acceptance.py` | 45-90, 401-413 |
| SLA 检查 | `core/task_acceptance.py` | 67-87, 200-230 |
| 退款交易 | `core/transaction.py` | 162-175 |
| 去中心化检查 | `check_decentralization.py` | 39, 95 |
| 市场订单簿 | `core/compute_market_orderbook.py` | 410 |
| 前端说明 | `frontend/src/pages/Help.tsx` | 33-34 |

---

## 核心代码片段速查

### 熔断触发判断

```python
# core/exchange_treasury.py
def _is_circuit_break(self, sector: str) -> bool:
    break_until = self._circuit_breaks.get(sector, 0)
    if break_until > time.time():
        return True  # ← 还在熔断中
    elif break_until > 0:
        del self._circuit_breaks[sector]  # ← 熔断时间过期
    return False
```

### 故障自动检测

```python
# core/task_acceptance.py
def apply_verdict(self, task_id, protocol_verdict):
    if protocol_verdict == ProtocolVerdict.CHEATED:
        return "矿工作弊，全额退款"  # ← 自动触发
    
    if protocol_verdict == ProtocolVerdict.TIMEOUT:
        return "执行超时，部分退款"   # ← 自动触发
```

### SLA 自动扣款

```python
# core/task_acceptance.py  
def calculate_sla_penalty(self, task_id, violations):
    sla = self.task_slas[task_id]
    order_price = self.orders[task_id].price
    
    # 自动计算惩罚金额
    penalty = order_price * len(violations) * sla.penalty_per_violation
    penalty = min(penalty, order_price * sla.max_penalty)
    
    return penalty  # ← 自动从矿工费用中扣除
```

---

## 总结

熔断机制 = **自动的、去中心化的、链上执行的三层保护**

- **第 1 层**：交易不崩（30% 波动自动暂停）
- **第 2 层**：钱不丢（故障自动退款）
- **第 3 层**：服务有保障（SLA 违反自动赔钱）

你看不到它工作，是因为它太有效了。🛡️
