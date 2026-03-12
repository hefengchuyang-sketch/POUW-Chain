# POUW Chain Production Deployment Guide

## Pre-Deployment Preparation

### 1. Server Requirements

| Configuration | Minimum | Recommended |
|---------------|---------|-------------|
| CPU | 4 cores | 8 cores+ |
| Memory | 8GB | 16GB+ |
| Disk | 100GB SSD | 500GB+ NVMe |
| Network | 100Mbps | 1Gbps |
| OS | Ubuntu 20.04+ / Windows Server 2019+ | Ubuntu 22.04 LTS |

### 2. Port Configuration

```bash
# Required ports
9333  - P2P communication (TCP/UDP)
8545  - RPC API (recommended: internal access only or via Nginx proxy)
8546  - WebSocket (optional)
3002  - Frontend (if public access needed)
```

---

## Deployment Steps

### Option A: Docker Deployment (Recommended)

#### Step 1: Install Docker
```bash
# Ubuntu
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Re-login to take effect
```

#### Step 2: Configure Production Environment
```bash
# Copy production config
cp config.mainnet.yaml config.yaml

# Edit config - modify the following key items:
# 1. bootstrap_nodes: Enter your node addresses
# 2. cors_origins: Enter your frontend domain
# 3. api.admin_key: Set admin key
```

#### Step 3: Start Services
```bash
# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

#### Step 4: Verify Operation
```bash
# Check node status
curl http://localhost:8545 -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"chain_getStatus","params":[],"id":1}'
```

---

### Option B: Direct Deployment

#### Step 1: Install Dependencies
```bash
# Ubuntu
sudo apt update
sudo apt install -y python3.11 python3-pip nodejs npm

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && npm run build && cd ..
```

#### Step 2: Manage with Systemd (Linux)

Create service file `/etc/systemd/system/pouw-node.service`:
```ini
[Unit]
Description=POUW Chain Node
After=network.target

[Service]
Type=simple
User=pouw
WorkingDirectory=/opt/pouw
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pouw-node
sudo systemctl start pouw-node
sudo systemctl status pouw-node
```

#### Step 3: Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/pouw
server {
    listen 80;
    server_name your-domain.com;
    
    # Frontend static files
    location / {
        root /opt/pouw/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # RPC API proxy
    location /rpc {
        proxy_pass http://127.0.0.1:8545;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
    
    # WebSocket proxy
    location /ws {
        proxy_pass http://127.0.0.1:8546;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable configuration:
```bash
sudo ln -s /etc/nginx/sites-available/pouw /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Security Configuration

### 1. Modify config.yaml Security Items

```yaml
network:
  rpc:
    # Restrict allowed RPC methods (optional)
    allowed_methods:
      - "chain_*"
      - "wallet_getBalance"
      - "p2pTask_*"
      # Do not expose sensitive methods like wallet_export
    
    # Restrict CORS
    cors_origins:
      - "https://your-domain.com"

api:
  # Must set admin key
  admin_key: "your-secure-random-key-here"
```

### 2. Firewall Configuration
```bash
# Ubuntu UFW
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 9333/tcp    # P2P
sudo ufw enable
```

### 3. Backup Wallets
```bash
# Backup wallet directory
cp -r wallets/ /backup/wallets-$(date +%Y%m%d)/

# Record mnemonic phrase in a secure location (store offline)
```

---

## Pre-Launch Checklist

### Must Complete
- [ ] Configure `network.type: mainnet`
- [ ] Configure at least 2 `bootstrap_nodes`
- [ ] Set `api.admin_key`
- [ ] Restrict `cors_origins` to actual domains
- [ ] Backup wallet mnemonic phrase
- [ ] Open firewall port 9333

### Recommended
- [ ] Configure HTTPS (using Let's Encrypt)
- [ ] Set up log rotation
- [ ] Configure monitoring alerts
- [ ] Set up automatic backup script

---

## Operations Commands

```bash
# Check node status
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"chain_getStatus","params":[],"id":1}'

# Check connected peers count
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"network_getPeers","params":[],"id":1}'

# Check block height
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"chain_getHeight","params":[],"id":1}'

# Docker logs
docker-compose logs -f --tail=100

# Restart service
docker-compose restart
```

---

## FAQ

**Q: Node cannot connect to other nodes?**
- Check if firewall port 9333 is open
- Check if bootstrap_nodes configuration is correct
- Confirm network type (mainnet/testnet) matches

**Q: RPC not accessible?**
- Check if rpc.host is set to "0.0.0.0"
- Check if firewall port 8545 is open
- Check CORS configuration

**Q: How to upgrade version?**
```bash
# Docker
docker-compose down
git pull
docker-compose up -d --build

# Direct deployment
sudo systemctl stop pouw-node
git pull
pip install -r requirements.txt
sudo systemctl start pouw-node
```
