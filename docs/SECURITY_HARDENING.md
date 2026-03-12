# 安全加固指南

本文档说明如何在生产环境中启用额外的安全特性。

---

## 🔒 生产环境安全加固

### 1. 强制本地请求认证

**问题**: 默认情况下，来自 `127.0.0.1` 的请求自动获得管理员权限（`is_admin=True`），这在容器环境或存在 SSRF 漏洞时可能导致提权。

**解决方案**: 设置环境变量 `REQUIRE_LOCAL_AUTH=true` 强制所有请求（包括本地）都需要 API Key 认证。

#### 启用方法

**方式 1: 环境变量**
```bash
export REQUIRE_LOCAL_AUTH=true
python main.py
```

**方式 2: Docker Compose**
```yaml
services:
  maincoin:
    image: maincoin:latest
    environment:
      - REQUIRE_LOCAL_AUTH=true
    ports:
      - "8545:8545"
```

**方式 3: Systemd 服务**
```ini
[Service]
Environment="REQUIRE_LOCAL_AUTH=true"
ExecStart=/usr/bin/python3 /opt/maincoin/main.py
```

#### 验证配置

启用后，即使从本地访问也需要提供 API Key：

```bash
# ❌ 未认证请求将失败
curl http://127.0.0.1:8545/rpc -X POST \
  -H "Content-Type: application/json" \
  -d '{"method":"wallet_balance","params":{},"id":1}'

# ✅ 需要 API Key
curl http://127.0.0.1:8545/rpc -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_admin_api_key" \
  -d '{"method":"wallet_balance","params":{},"id":1}'
```

---

### 2. 异常处理改进

**修复内容**: 将裸 `except:` 替换为 `except Exception:`，避免捕获系统信号（`KeyboardInterrupt`, `SystemExit`）。

**影响范围**:
- ✅ 日志文件创建失败 (main.py)
- ✅ 设备检测失败 (main.py)
- ✅ 端口检测失败 (main.py)
- ✅ 信号注册失败 (main.py)

**改进效果**:
- Ctrl+C 可以立即响应
- 系统退出信号不会被意外捕获
- 失败原因会记录到日志

---

## 🚀 生产环境最佳实践

### 反向代理配置

生产环境应通过反向代理（Nginx/Traefik）暴露 RPC 服务，而非直接绑定公网 IP。

**Nginx 示例**:
```nginx
upstream maincoin_backend {
    server 127.0.0.1:8545;
}

server {
    listen 443 ssl;
    server_name api.maincoin.io;

    ssl_certificate /etc/letsencrypt/live/api.maincoin.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.maincoin.io/privkey.pem;

    location /rpc {
        proxy_pass http://maincoin_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # 限速保护
        limit_req zone=api burst=20 nodelay;
    }
}
```

### API Key 管理

1. **生成强随机密钥**:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **定期轮换密钥**（建议每 90 天）

3. **按用途隔离密钥**:
   - 前端只读密钥
   - 后台管理密钥
   - 矿工注册密钥

---

## 📊 安全检查清单

部署前检查：

- [ ] `REQUIRE_LOCAL_AUTH=true` 已设置
- [ ] RPC 绑定 `127.0.0.1`（非 `0.0.0.0`）
- [ ] 使用反向代理暴露服务
- [ ] TLS 证书已配置（`ssl_cert`, `ssl_key`）
- [ ] API Key 已生成并妥善保管
- [ ] 防火墙规则仅开放必要端口
- [ ] 日志记录已启用
- [ ] DDoS 防护已配置（`attack_prevention.py`）

---

## 🔍 故障排查

### 问题: 本地请求被拒绝

**症状**: 设置 `REQUIRE_LOCAL_AUTH=true` 后本地测试失败

**解决**:
1. 确认 API Key 已在 `config.yaml` 中配置
2. 检查请求头是否包含 `X-API-Key` 或 `Authorization: Bearer <key>`
3. 查看日志 `logs/node.log` 确认认证失败原因

### 问题: KeyboardInterrupt 不响应

**症状**: Ctrl+C 无法终止进程

**解决**:
1. 确认已应用异常处理改进（检查 git diff）
2. 使用 `kill -TERM <pid>` 发送 SIGTERM 信号
3. 最后手段：`kill -9 <pid>` 强制终止

---

## 📚 相关文档

- [API 认证文档](API.md#authentication)
- [RPC 配置指南](../config.yaml)
- [安全审计报告](SECURITY_AUDIT_CORE_2026.md)
- [生产部署指南](PRODUCTION_READINESS_REPORT.md)

---

**更新时间**: 2026-03-08  
**适用版本**: v0.5.0+
