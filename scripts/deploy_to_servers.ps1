# POUW Chain - 一键部署脚本 (Windows PowerShell)
# 用法: .\scripts\deploy_to_servers.ps1

$ErrorActionPreference = "Continue"

# ============== 服务器配置 ==============
$servers = @(
    @{ Name = "Node1-Seed";  IP = "118.195.149.137"; Config = "config.node1.yaml" },
    @{ Name = "Node2-Miner"; IP = "1.13.141.28";     Config = "config.node2.yaml" },
    @{ Name = "Node3-Full";  IP = "175.27.156.47";    Config = "config.node3.yaml" }
)
$password = $env:SSH_PASSWORD
$remotePath = "/opt/pouw-chain"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  POUW Chain - 3 节点公网部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查是否有 sshpass (WSL) 或 plink
$usePlink = $false
if (Get-Command plink -ErrorAction SilentlyContinue) {
    $usePlink = $true
    Write-Host "使用 plink 进行自动化部署" -ForegroundColor Green
} else {
    Write-Host $env:SSH_PASSWORD
    Write-Host "自动化部署需要手动输入密码。" -ForegroundColor Yellow
    Write-Host "每次 scp/ssh 命令都会提示输入密码: $password" -ForegroundColor Yellow
    Write-Host $env:SSH_PASSWORD
}

foreach ($server in $servers) {
    $ip = $server.IP
    $name = $server.Name
    $config = $server.Config
    
    Write-Host "`n============================================" -ForegroundColor Magenta
    Write-Host "  部署 $name ($ip)" -ForegroundColor Magenta
    Write-Host "============================================" -ForegroundColor Magenta
    
    # Step 1: 在远程创建目录
    Write-Host "[1/5] 创建远程目录..." -ForegroundColor Cyan
    ssh -o StrictHostKeyChecking=no root@$ip "mkdir -p $remotePath/core $remotePath/deploy $remotePath/data $remotePath/wallets $remotePath/logs"
    
    # Step 2: 上传核心文件
    Write-Host "[2/5] 上传核心代码..." -ForegroundColor Cyan
    scp -o StrictHostKeyChecking=no -r core/*.py root@${ip}:${remotePath}/core/
    scp -o StrictHostKeyChecking=no main.py requirements.txt root@${ip}:${remotePath}/
    scp -o StrictHostKeyChecking=no deploy/$config root@${ip}:${remotePath}/config.yaml
    
    # Step 3: 上传部署脚本
    Write-Host "[3/5] 上传部署脚本..." -ForegroundColor Cyan
    scp -o StrictHostKeyChecking=no deploy/deploy.sh root@${ip}:${remotePath}/deploy/
    
    # Step 4: 安装 Python 环境和依赖
    Write-Host "[4/5] 安装 Python 环境..." -ForegroundColor Cyan
    ssh -o StrictHostKeyChecking=no root@$ip @"
cd $remotePath
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv > /dev/null 2>&1
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo 'Python 环境就绪'
"@
    
    # Step 5: 创建 systemd 服务
    Write-Host "[5/5] 配置 systemd 服务..." -ForegroundColor Cyan
    ssh -o StrictHostKeyChecking=no root@$ip @"
cat > /etc/systemd/system/pouw-chain.service << 'EOF'
[Unit]
Description=POUW Multi-Sector Chain Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$remotePath
ExecStart=$remotePath/venv/bin/python main.py --config config.yaml --data-dir /opt/pouw-chain/data
Restart=always
RestartSec=10
StandardOutput=append:/opt/pouw-chain/logs/node.log
StandardError=append:/opt/pouw-chain/logs/node.err

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo 'systemd 服务已配置'
"@
    
    Write-Host "[$name] 部署完成!" -ForegroundColor Green
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  所有节点部署完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host $env:SSH_PASSWORD
Write-Host "下一步 - 按顺序启动节点:" -ForegroundColor Yellow
Write-Host "  1. ssh root@118.195.149.137 'systemctl start pouw-chain'"
Write-Host "  2. 等待 10 秒"
Write-Host "  3. ssh root@1.13.141.28 'systemctl start pouw-chain'"
Write-Host "  4. ssh root@175.27.156.47 'systemctl start pouw-chain'"
Write-Host $env:SSH_PASSWORD
Write-Host "查看日志:" -ForegroundColor Yellow
Write-Host "  ssh root@118.195.149.137 'tail -f /opt/pouw-chain/logs/node.log'"
Write-Host $env:SSH_PASSWORD
