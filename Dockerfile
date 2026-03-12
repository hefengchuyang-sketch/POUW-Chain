# POUW Multi-Sector Chain - Docker 镜像

# === 构建阶段：安装编译依赖和前端 ===
FROM python:3.11.12-slim AS builder

# 元数据
LABEL maintainer="POUW Chain Team"
LABEL version="2.0.0"
LABEL description="POUW Multi-Sector Blockchain Node"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libleveldb-dev \
    libsnappy-dev \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js（安全方式，使用 GPG 密钥验证）
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN cd frontend && npm ci --production=false && npx vite build && rm -rf node_modules

# === 运行阶段：最小化镜像 ===
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV POUW_DATA_DIR=/data
ENV POUW_CONFIG=/app/config.yaml
ENV MAINCOIN_PRODUCTION=true

# 仅安装运行时依赖（不含编译工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libleveldb-dev \
    libsnappy-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从构建阶段复制 Python 包和应用代码
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# 创建数据目录
RUN mkdir -p /data /wallets /logs

# 创建非 root 用户运行
RUN groupadd -r pouw && useradd -r -g pouw -d /app -s /sbin/nologin pouw \
    && chown -R pouw:pouw /app /data /wallets /logs

# 暴露端口
# P2P 端口
EXPOSE 9333
# RPC 端口
EXPOSE 8545
# WebSocket 端口
EXPOSE 8546
# Web UI 端口
EXPOSE 8501

# 健康检查 - 验证 RPC 服务实际可用
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,json; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8545',data=json.dumps({'jsonrpc':'2.0','method':'blockchain_getHeight','params':{},'id':1}).encode(),headers={'Content-Type':'application/json'}),timeout=5); d=json.loads(r.read()); assert d.get('result')" || exit 1

# 数据卷
VOLUME ["/data", "/wallets", "/logs"]

# 切换到非 root 用户
USER pouw

# 默认命令
ENTRYPOINT ["python", "main.py"]
CMD ["--config", "/app/config.yaml", "--data-dir", "/data"]
