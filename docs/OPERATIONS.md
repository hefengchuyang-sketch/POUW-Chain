# POUW Chain Operations Manual

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Quick Start](#2-quick-start)
3. [Node Operations](#3-node-operations)
4. [Mining Operations](#4-mining-operations)
5. [Compute Market](#5-compute-market)
6. [Common Commands](#6-common-commands)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Environment Setup

### 1.1 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| Python | 3.9+ | 3.11 |
| Memory | 4GB | 8GB+ |
| Storage | 10GB | 50GB+ SSD |
| Network | 1Mbps | 10Mbps+ |

### 1.2 Install Dependencies

```bash
# Clone the project
git clone https://github.com/your-org/maincoin.git
cd maincoin

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Production environment must install crypto libraries
pip install ecdsa mnemonic
```

### 1.3 Configuration File

Main configuration file `config.yaml`:

```yaml
node:
  host: "127.0.0.1"
  rpc_port: 8545
  p2p_port: 30303

network:
  type: "mainnet"  # mainnet / testnet
  bootstrap_nodes:
    - "node1.pouwchain.io:30303"
    - "node2.pouwchain.io:30303"

mining:
  enabled: true
  wallet: "YOUR_WALLET_ADDRESS"
  sectors: ["H100", "RTX4090"]

security:
  signature_required: true
  mock_mode: false  # Must be false in production
```

---

## 2. Quick Start

### 2.1 One-Click Start (Windows)

```batch
# Start all services
start_all.bat

# Or start separately
start_node.bat    # Start node
start_webui.bat   # Start Web UI
```

### 2.2 Command Line Start

```bash
# Start full node
python node_launcher.py

# Start Web UI (port 8521)
python -m streamlit run web_ui_v2.py --server.port 8521

# Start mining client
python miner_client.py --wallet YOUR_WALLET_ADDRESS
```

### 2.3 Docker Start

```bash
# Build image
docker build -t pouw-chain .

# Start container
docker-compose up -d

# View logs
docker-compose logs -f
```

---

## 3. Node Operations

### 3.1 Node Status Check

```bash
# View node info
curl http://localhost:8545 -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"getinfo","params":[],"id":1}'

# View block height
curl http://localhost:8545 -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"getblockcount","params":[],"id":1}'

# View mempool
curl http://localhost:8545 -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"getmempoolinfo","params":[],"id":1}'
```

### 3.2 Data Directory Structure

```
data/
|-- blockchain.db       # Blockchain data
|-- mempool.db          # Mempool
|-- transactions.db     # Transaction records
|-- users.db            # User data
|-- sector_coins.db     # Sector coin ledger
|-- compute_market.db   # Compute market
|-- governance.db       # Governance voting
|-- mining.db           # Mining data
|-- sessions.db         # Session management
```

### 3.3 Data Backup and Restore

```bash
# Backup
cp -r data/ backup/data_$(date +%Y%m%d)/

# Restore
rm -rf data/
cp -r backup/data_20260128/ data/
```

### 3.4 Data Cleanup (Reset)

```powershell
# Windows PowerShell
Remove-Item data\*.db -ErrorAction SilentlyContinue

# Linux/Mac
rm -f data/*.db
```

---

## 4. Mining Operations

### 4.1 Start Mining

```bash
# Auto mode (recommended)
python miner_client.py --wallet MAIN_YOUR_ADDRESS --yes

# Interactive mode
python miner_client.py --wallet MAIN_YOUR_ADDRESS
```

### 4.2 Mining Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--wallet` | Miner wallet address | Required |
| `--sectors` | Sectors to participate in | All sectors |
| `--yes` | Skip confirmation prompts | False |

### 4.3 View Mining Earnings

```bash
# Check sector coin balance
curl http://localhost:8545 -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"getsectorbalance","params":["YOUR_ADDRESS"],"id":1}'

# Check MAIN balance
curl http://localhost:8545 -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"getbalance","params":["YOUR_ADDRESS"],"id":1}'
```

### 4.4 Exchange Sector Coins for MAIN

Exchanging sector coins for MAIN requires the dual-witness mechanism:

1. Initiate exchange request
2. Wait for 2 sector confirmations (witnesses)
3. Sector coins burned, MAIN minted

```python
# Via Web UI or API
# POST /exchange
{
    "from_sector": "H100",
    "amount": 100.0,
    "signature": "YOUR_SIGNATURE"
}
```

---

## 5. Compute Market

### 5.1 Publish Computing Power

```python
# Publish computing resources via API
# POST /compute/offer
{
    "provider": "YOUR_ADDRESS",
    "gpu_type": "H100",
    "gpu_count": 4,
    "price_per_hour": 10.0,
    "available_hours": 24
}
```

### 5.2 Purchase Computing Power

```python
# Purchase computing power via API
# POST /compute/order
{
    "buyer": "YOUR_ADDRESS",
    "gpu_hours": 10,
    "max_price": 15.0,
    "task_hash": "sha256_of_your_task"
}
```

### 5.3 View Market

Access the Web UI at `http://localhost:8521`, navigate to the "Compute Market" tab.

---

## 6. Common Commands

### 6.1 Wallet Operations

```bash
# Generate new wallet
python -c "from core.crypto import generate_keypair; print(generate_keypair())"

# Check balance
curl -X POST http://localhost:8545 \
  -d '{"method":"getbalance","params":["ADDRESS"]}'
```

### 6.2 Transaction Operations

```bash
# Send MAIN (requires dual-witness)
curl -X POST http://localhost:8545 \
  -d '{"method":"sendmain","params":["FROM","TO",100,"SIGNATURE"]}'

# Check transaction status
curl -X POST http://localhost:8545 \
  -d '{"method":"gettransaction","params":["TXID"]}'
```

### 6.3 Governance Operations

```bash
# Create proposal
curl -X POST http://localhost:8545 \
  -d '{"method":"createproposal","params":["TITLE","DESCRIPTION","CREATOR"]}'

# Vote
curl -X POST http://localhost:8545 \
  -d '{"method":"vote","params":["PROPOSAL_ID","VOTER","approve"]}'
```

---

## 7. Troubleshooting

### 7.1 Common Issues

#### Node Fails to Start

```bash
# Check port occupation
netstat -an | findstr 8545  # Windows
lsof -i :8545               # Linux

# Kill occupying process
taskkill /F /PID <PID>      # Windows
kill -9 <PID>               # Linux
```

#### Signature Verification Failed

```bash
# Ensure ecdsa library is installed
pip install ecdsa

# Check if mock_mode is false in config
# config.yaml -> security.mock_mode: false
```

#### Transaction Stuck in Mempool

```bash
# Check mempool status
curl -X POST http://localhost:8545 \
  -d '{"method":"getmempoolinfo"}'

# Expired transactions are cleaned automatically
# The system automatically cleans expired transactions from the mempool
```

#### Dual-Witness Timeout

Dual-witness timeout (60 seconds) is usually caused by:
- Network connectivity issues
- Insufficient witness nodes
- Witnesses not online

Solutions:
1. Check network connectivity
2. Ensure multiple sector nodes are online
3. Increase witness timeout (requires modifying `main_transfer.py`)

### 7.2 Log Locations

| Log | Location | Description |
|-----|----------|-------------|
| Node log | Console output | Real-time log |
| RPC log | `data/rpc.log` | RPC request log |
| Error log | `data/error.log` | Exception records |

### 7.3 Performance Tuning

```yaml
# config.yaml
performance:
  mempool_size: 10000      # Mempool size
  block_interval: 10       # Block interval (seconds)
  max_connections: 50      # Max P2P connections
  db_cache_size: 256       # Database cache (MB)
```

---

## Appendix

### A. RPC Method List

| Method | Parameters | Description |
|--------|-----------|-------------|
| `getinfo` | - | Node information |
| `getblockcount` | - | Block height |
| `getblock` | height | Get block |
| `getbalance` | address | MAIN balance |
| `getsectorbalance` | address | Sector coin balance |
| `sendmain` | from, to, amount, sig | Send MAIN |
| `getmempoolinfo` | - | Mempool info |
| `getmininginfo` | - | Mining info |

### B. Sector Codes

| Code | GPU Type | Base Reward |
|------|----------|-------------|
| H100 | NVIDIA H100 | 50 H100_COIN |
| A100 | NVIDIA A100 | 40 A100_COIN |
| RTX4090 | NVIDIA RTX 4090 | 30 RTX4090_COIN |
| RTX4080 | NVIDIA RTX 4080 | 25 RTX4080_COIN |
| RTX3090 | NVIDIA RTX 3090 | 20 RTX3090_COIN |

### C. Fee Structure

| Fee Type | Ratio | Purpose |
|----------|-------|---------|
| Burn | 0.5% | Deflation mechanism |
| Miner | 0.3% | Validation incentive |
| Foundation | 0.2% | Ecosystem development |

---

*Last Updated: 2026-01-28*
