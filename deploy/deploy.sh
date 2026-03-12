#!/bin/bash
# POUW Chain - 单节点部署脚本
# 在每台服务器上运行此脚本
#
# 用法:
#   bash deploy.sh <node_number>
#   例: bash deploy.sh 1   # 部署种子节点
#       bash deploy.sh 2   # 部署节点2
#       bash deploy.sh 3   # 部署节点3

set -e

NODE_NUM=${1:-1}
INSTALL_DIR="/opt/pouw-chain"
DATA_DIR="/data/pouw"
LOG_DIR="/var/log/pouw"

echo "========================================="
echo "  POUW Chain 节点部署 - Node $NODE_NUM"
echo "========================================="

# 1. 系统依赖
echo "[1/6] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq python3.11 python3.11-venv python3-pip git ufw

# 2. 防火墙
echo "[2/6] 配置防火墙..."
ufw allow 9333/tcp comment "POUW P2P"
ufw allow 8545/tcp comment "POUW RPC"
ufw allow 22/tcp comment "SSH"
ufw --force enable

# 3. 创建目录
echo "[3/6] 创建目录..."
mkdir -p $INSTALL_DIR $DATA_DIR $LOG_DIR

# 4. 部署代码
echo "[4/6] 部署代码..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd $INSTALL_DIR && git pull
else
    # 首次部署 - 复制代码（或 git clone）
    echo "请将代码复制到 $INSTALL_DIR"
    echo "例: scp -r ./* root@server:$INSTALL_DIR/"
fi

# 5. Python 环境
echo "[5/6] 配置 Python 环境..."
cd $INSTALL_DIR
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. 复制配置
echo "[6/6] 配置节点..."
cp deploy/config.node${NODE_NUM}.yaml $INSTALL_DIR/config.yaml
echo "请编辑 $INSTALL_DIR/config.yaml 填写正确的 IP 和钱包地址"

# 创建 systemd 服务
cat > /etc/systemd/system/pouw-chain.service << EOF
[Unit]
Description=POUW Multi-Sector Chain Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python main.py --config config.yaml --data-dir $DATA_DIR
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/node.log
StandardError=append:$LOG_DIR/node.err

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo ""
echo "后续步骤:"
echo "  1. 编辑配置:  nano $INSTALL_DIR/config.yaml"
echo "  2. 启动节点:  systemctl start pouw-chain"
echo "  3. 查看状态:  systemctl status pouw-chain"
echo "  4. 查看日志:  tail -f $LOG_DIR/node.log"
echo "  5. 开机自启:  systemctl enable pouw-chain"
echo ""
