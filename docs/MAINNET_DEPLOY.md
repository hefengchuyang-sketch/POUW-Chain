# POUW Chain - 主网化部署指南

## 一、已完成的 Bug 修复

### Bug 1: 区块验证缺少 UTXO 检查 ✅
- **文件**: `core/consensus.py` → `validate_block()` + `_validate_block_transactions()`
- **修复内容**:
  - 交易输入的 UTXO 存在性检查
  - 块内双花检测（同一 UTXO 在一个区块中被两次引用）
  - Coinbase 成熟度 100 确认检查
  - 输入金额 ≥ 输出金额 + 手续费 检查

### Bug 2: 挖出的区块不通过 P2P 广播 ✅
- **文件**: `main.py` → `on_block_mined()`
- **修复内容**:
  - 矿工挖到区块后通过 `asyncio.run_coroutine_threadsafe()` 线程安全地广播到所有 P2P 节点
  - 使用 `MessageType.NEW_BLOCK` 消息类型

### Bug 3: 新节点无法同步历史区块 ✅
- **文件**: `main.py` → `handle_get_blocks()` / `handle_blocks()` / `initial_sync()`
- **修复内容**:
  - 实现 `GET_BLOCKS` → `BLOCKS` 请求/响应协议
  - 节点启动后 8 秒自动向第一个 peer 请求历史区块
  - 批量同步，每批 50 个区块，自动请求下一批直到追平
  - `consensus.py` 新增 `get_blocks_range()` + `receive_block_from_peer()` + `add_block_no_validate()`

### Bug 4: 所有区块加载到内存导致 OOM ✅
- **文件**: `core/consensus.py` → `_load_or_create_genesis()` / `add_block()`
- **修复内容**:
  - 只缓存最近 200 个区块在内存中
  - 新增 `_chain_height` 独立追踪链高度
  - `get_block_by_height()` / `get_block_by_hash()` 增加 DB 回退查询
  - `add_block()` 自动裁剪超出缓存大小的旧区块

### 附加修复
- `docker-compose.yml`: 移除引用不存在 `app_v2.py` 的 WebUI 服务
- `main.py`: UTXO 存储注入到共识引擎
- `consensus.py`: `get_chain_info` 使用 `_chain_height` 而非 `len(self.chain)-1`

---

## 二、Docker 本地 3 节点测试（第 2 周）

### 前置条件
- Docker Desktop 已安装
- docker-compose 可用

### 启动
```powershell
# 构建并启动 3 节点 (bootstrap + node1 + miner)
docker-compose up -d bootstrap node1 miner

# 或使用测试脚本
.\scripts\test_3node.ps1 -Build
```

### 验证
```powershell
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f miner

# RPC 测试
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"chain_getInfo","params":[],"id":1}'

# 测试脚本
.\scripts\test_3node.ps1
```

### 验证清单
- [ ] 3 个容器全部 Running
- [ ] 每个节点 RPC 可访问 (8545/8546/8548)
- [ ] miner 节点持续出块（高度递增）
- [ ] node1 同步 miner 出的区块（高度跟随）
- [ ] bootstrap 同步所有区块

### 停止
```powershell
.\scripts\test_3node.ps1 -Down
# 或
docker-compose down -v
```

---

## 三、3 节点公网部署（第 3 周）

### 服务器要求
| 节点 | 角色 | 最低配置 | 推荐配置 |
|------|------|----------|----------|
| Node 1 | 种子节点 + 矿工 | 2C4G | 4C8G |
| Node 2 | 矿工 | 2C4G | 4C8G |
| Node 3 | 全节点 | 1C2G | 2C4G |

### 部署步骤

#### 1. 准备服务器
购买 3 台 VPS (推荐 Ubuntu 22.04)，记录公网 IP：
```
Node 1 (Seed):  1.2.3.4
Node 2 (Miner): 5.6.7.8
Node 3 (Full):  9.10.11.12
```

#### 2. 上传代码到每台服务器
```bash
scp -r . root@1.2.3.4:/opt/pouw-chain/
scp -r . root@5.6.7.8:/opt/pouw-chain/
scp -r . root@9.10.11.12:/opt/pouw-chain/
```

#### 3. 在每台服务器执行部署
```bash
# Node 1 (种子节点)
ssh root@1.2.3.4
cd /opt/pouw-chain && bash deploy/deploy.sh 1
# 编辑 config.yaml，填写 external_ip=1.2.3.4 和 miner_address

# Node 2
ssh root@5.6.7.8
cd /opt/pouw-chain && bash deploy/deploy.sh 2
# 编辑 config.yaml，填写 external_ip=5.6.7.8, bootstrap=1.2.3.4:9333

# Node 3
ssh root@9.10.11.12
cd /opt/pouw-chain && bash deploy/deploy.sh 3
# 编辑 config.yaml，填写 external_ip=9.10.11.12, bootstrap=1.2.3.4:9333
```

#### 4. 启动节点（按顺序）
```bash
# 先启动种子节点
ssh root@1.2.3.4 "systemctl start pouw-chain"

# 等待 10 秒，启动其他节点
ssh root@5.6.7.8 "systemctl start pouw-chain"
ssh root@9.10.11.12 "systemctl start pouw-chain"
```

#### 5. 验证
```bash
# 检查每个节点状态
for IP in 1.2.3.4 5.6.7.8 9.10.11.12; do
  echo "=== $IP ==="
  curl -s http://$IP:8545 -X POST -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"chain_getInfo","params":[],"id":1}' | python3 -m json.tool
done
```

---

## 四、压力测试（第 4 周）

### 运行压力测试
```bash
# 基础压力测试 (100 请求)
bash scripts/stress_test.sh 8545 100

# 高压测试 (1000 请求)
bash scripts/stress_test.sh 8545 1000
```

### 监控指标
- **出块间隔**: 应稳定在 30 秒左右
- **RPC 吞吐**: 目标 > 100 TPS
- **内存使用**: 应保持稳定（不再因区块累积而 OOM）
- **P2P 同步延迟**: 新区块应在 < 5 秒内传播到所有节点

### 监控命令
```bash
# 持续监控链高度
watch -n 5 'curl -s http://localhost:8545 -X POST -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"chain_getInfo\",\"params\":[],\"id\":1}"'

# 内存使用
docker stats pouw-bootstrap pouw-node1 pouw-miner

# 日志
tail -f /var/log/pouw/node.log
```

---

## 五、架构变更总览

```
修改文件:
├── core/consensus.py      # +130 行（UTXO 验证 + 按需加载 + P2P 接收）
├── main.py                # +80 行（P2P 广播 + 区块同步 + 处理器）
├── docker-compose.yml     # 修复 WebUI 服务
├── deploy/
│   ├── config.node1.yaml  # 种子节点配置模板
│   ├── config.node2.yaml  # 矿工节点配置模板
│   ├── config.node3.yaml  # 全节点配置模板
│   └── deploy.sh          # 自动化部署脚本
├── scripts/
│   ├── test_3node.ps1     # Windows 3节点测试
│   └── stress_test.sh     # 压力测试
└── MAINNET_DEPLOY.md      # 本文档
```
