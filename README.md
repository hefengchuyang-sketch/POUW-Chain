# POUW Chain

**Proof of Useful Work — Multi-Sector Heterogeneous Computing Blockchain**

An innovative decentralized blockchain platform that transforms real computation tasks (AI inference, video rendering, scientific computing) into a consensus mechanism.

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/pouwchain/maincoin)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## Table of Contents

- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Core Mechanisms](#core-mechanisms)
- [API Documentation](#api-documentation)
- [Development Guide](#development-guide)
- [License](#license)

---

## Key Features

### POUW Consensus
- Earn block rewards by executing real, useful computation tasks
- Real workloads: AI inference, numerical optimization, hash computation, etc.
- Scoring weights: Completion rate 30% + Latency 25% + Online stability 25% + Block participation 20%

### S-Box PoUW — Cryptographic Proof of Useful Work
- Each block produces a verified **S-Box** (256-byte substitution box, fundamental to AES-class ciphers)
- Quality scored by: **Nonlinearity** (Walsh-Hadamard) + **Differential Uniformity** + **Avalanche Effect**
- Mined S-Boxes feed directly into P2P encryption — zero waste consensus
- Multi-sector VRF selection: all sectors mine independently, one winner per block
- Chain data compression: compact mode stores only S-Box hash (~250 bytes vs ~700 bytes/block)

### Hybrid Consensus Mode (POUW + S-Box PoUW)
- Built-in mixed mode supports both POUW and SBOX_POUW in the same network
- `consensus.mode` controls strategy: `mixed`, `sbox_only`, `pouw_only`
- `consensus.sbox_ratio` controls SBOX_POUW target share in mixed mode (0.0 - 1.0)
- Automatic fallback keeps liveness: S-Box unavailable -> POUW, both unavailable -> PoW fallback

### Multi-Sector Architecture
- Sectors divided by hardware type: H100, RTX4090, RTX3080, CPU, GENERAL
- Each sector produces blocks and halves independently
- Sector coins are separate from the MAIN token
- Community can add/remove sectors via DAO voting

### Dual-Token Economic Model
| Token | Description |
|-------|-------------|
| **MAIN** | Primary token, cannot be mined, only obtained by exchanging sector coins. Max supply: 100 million |
| **Sector Coins** | H100_COIN, RTX4090_COIN, etc. Mined directly, each sector capped at 21 million |

### Security

#### Transaction-Level Security
- ECDSA secp256k1 signature verification
- Dual-witness mechanism (MAIN transfers require 2+ sector confirmations)
- Account nonce for double-spend prevention
- BIP-39 mnemonic wallet + AES-256-GCM encrypted storage

#### Compute Task Security
- **Standard Mode** ★★★☆☆: Container isolation + end-to-end encryption (~8% overhead)
- **Enhanced Mode** ★★★★☆: Task sharding + redundant verification + S-Box SubBytes (~12% overhead)
- **Confidential Mode** ★★★★★: TEE hardware isolation (roadmap, ~30% overhead)

#### P2P Encryption
- ECDH (X25519) key agreement → AES-256-GCM + S-Box SubBytes stacking
- Ephemeral session keys: one-time use, forward secrecy guaranteed
- S-Box snapshot-locked per session: no mid-task cipher switching
- Fixed-address operations (wallet transfers): pure AES-256-GCM, no S-Box needed

> **Details**: See [Security Architecture](docs/SECURITY_ARCHITECTURE.md)  
> **Threat Model**: Standard mode defends against semi-honest miners; TEE mode defends against malicious root administrators

### 💸 Decentralized Fees
- 0.5% burned (deflationary)
- 0.3% miner incentive
- 0.2% foundation (multi-sig)

### 🏦 Block Reward Distribution
- 97% to block-producing miner
- 3% auto-transferred to DAO treasury (MAIN_TREASURY)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      POUW Chain                              │
├─────────────┬─────────────┬─────────────┬─────────────┬─────┤
│   H100      │    A100     │  RTX4090    │  RTX4080    │ ... │
│   Sector    │   Sector    │   Sector    │   Sector    │     │
├─────────────┴─────────────┴─────────────┴─────────────┴─────┤
│                 Dual-Witness Layer (Multi-Witness)           │
├─────────────────────────────────────────────────────────────┤
│              S-Box PoUW Layer (Cryptographic Output)         │
├─────────────────────────────────────────────────────────────┤
│                    MAIN Chain Ledger                         │
├─────────────────────────────────────────────────────────────┤
│  Compute    │  Governance │ Sector Coin  │  Nonce            │
│  Market     │  System     │  Exchange    │  Manager          │
└─────────────────────────────────────────────────────────────┘
```

### Core Flow

```
Mining → S-Box Generation + POUW Task → Sector Coin Reward → Dual-Witness Exchange → MAIN Token
                  ↓                                  ↓
       S-Box Library (Encryption)         Burn Sector Coin + Mint MAIN
```

---

## Quick Start

### Requirements

- Python 3.9+
- 8GB RAM (recommended)
- 10GB+ disk space

### Installation

```bash
# Clone the repository
git clone https://github.com/pouwchain/maincoin.git
cd maincoin

# Install dependencies
pip install -r requirements.txt

# Required for production
pip install ecdsa mnemonic
```

### Start a Node

```bash
# Default start
python main.py

# Start with mainnet configuration
python main.py --config config.mainnet.yaml

# Start with mining enabled
python main.py --config config.mainnet.yaml --mining

# Windows quick start
.\start.ps1
```

### Docker Deployment

```bash
docker-compose up -d
```

---

## Project Structure

```
maincoin/
├── main.py                  # Node entry point
├── config.yaml              # Default/dev configuration
├── config.mainnet.yaml      # Mainnet production config
├── genesis.mainnet.json     # Genesis block config
├── requirements.txt         # Python dependencies
├── docker-compose.yml       # Docker orchestration
├── Dockerfile               # Docker build
├── start.ps1 / stop.ps1     # Windows start/stop scripts
├── core/                    # Core modules
│   ├── consensus.py         #   Consensus mechanism (POUW + S-Box PoUW)
│   ├── unified_consensus.py #   Unified consensus engine
│   ├── pouw.py              #   POUW task types & verification
│   ├── pouw_scoring.py      #   POUW scoring system
│   ├── sbox_engine.py       #   S-Box evaluation & genetic optimization
│   ├── sbox_miner.py        #   Multi-sector S-Box mining & VRF
│   ├── sbox_crypto.py       #   S-Box encryption layers (STANDARD/ENHANCED/MAXIMUM)
│   ├── blockchain.py        #   Blockchain main logic
│   ├── block.py             #   Block data structure
│   ├── transaction.py       #   Transaction management
│   ├── main_transfer.py     #   MAIN transfer + dual witness
│   ├── dual_witness_exchange.py  # Sector coin exchange
│   ├── sector_coin.py       #   Sector coin ledger + registry
│   ├── dao_treasury.py      #   DAO governance + treasury
│   ├── fee_config.py        #   Fee configuration (immutable)
│   ├── protocol_fee_pool.py #   Protocol fee pool
│   ├── blind_task_engine.py #   Blind dispatch + trap verification
│   ├── compute_scheduler.py #   Compute scheduling
│   ├── dynamic_pricing.py   #   Dynamic pricing engine
│   ├── rpc_service.py       #   RPC service entry
│   ├── rpc_handlers/        #   RPC handler modules
│   ├── security.py          #   Security infrastructure
│   ├── crypto.py            #   Cryptographic utilities
│   ├── wallet.py            #   Wallet management
│   ├── network.py           #   P2P network
│   └── ...                  #   And 60+ other modules
├── tests/                   # Test suite (202 tests)
├── docs/                    # Documentation
│   ├── USER_GUIDE.md        #   User guide
│   ├── CONSENSUS.md         #   Consensus whitepaper
│   ├── API.md               #   API reference
│   ├── FEE_MECHANISM.md     #   Fee mechanism
│   ├── SECURITY_ARCHITECTURE.md  # Security architecture
│   ├── GOVERNANCE_VOTING.md #   Governance & voting
│   └── ...                  #   And other audit/report docs
├── frontend/                # Frontend (Vue + Vite)
├── scripts/                 # Deployment/ops scripts
├── deploy/                  # Multi-node deployment configs
├── data/                    # Runtime data (not committed)
└── wallets/                 # Wallet files (not committed)
```

---

## Core Mechanisms

### 1. MAIN Cannot Be Mined (DR-1)

The MAIN token can only be obtained by exchanging sector coins — it cannot be mined directly:

```python
# blockchain_service.py
def get_block_reward(sector: str) -> Tuple[float, str]:
    if sector == "MAIN":
        return 0, "MAIN"  # MAIN produces no reward
    return SECTOR_BASE_REWARDS.get(sector, (0, sector))
```

### 2. Dual-Witness Mechanism (DR-5/DR-6)

All MAIN-related operations require multi-sector confirmation:

```python
# main_transfer.py
class MainTransferEngine:
    MIN_WITNESSES = 2           # Standard transfers need 2 witnesses
    LARGE_TRANSFER_WITNESSES = 3  # Large transfers (≥1000) need 3 witnesses
    WITNESS_TIMEOUT = 60        # 60-second timeout
```

### 3. Sector Coin Exchange (DR-9)

Sector coin → MAIN uses a burn-and-mint model:

```python
# dual_witness_exchange.py
def execute_exchange(request):
    # 1. Burn sector coins
    sector_ledger.burn(request.from_address, request.amount)
    
    # 2. Wait for dual witness
    witnesses = collect_witnesses(request, min_count=2)
    
    # 3. Mint MAIN
    main_ledger.mint(request.to_address, main_amount)
```

### 4. Double-Spend Prevention (Nonce)

Each account maintains an incrementing nonce:

```python
# transaction_v2.py
class AccountNonceManager:
    def validate_nonce(self, address, nonce, txid):
        current = self.get_nonce(address)
        if nonce < current:
            return False, f"Nonce too low: {nonce} < {current}"
        return True, "OK"
```

### 5. Fee Distribution

1% transaction fee distributed in a decentralized manner:

| Ratio | Purpose | Implementation |
|-------|---------|----------------|
| 0.5% | Burn | `BURN_ADDRESS` |
| 0.3% | Miner | Block-producing miner address |
| 0.2% | Foundation | Multi-sig address |

### 6. Hybrid Consensus Policy

`consensus.mode` and `consensus.sbox_ratio` let operators tune production behavior:

- `mixed`: deterministic ratio-based mix of POUW and SBOX_POUW
- `sbox_only`: prioritize SBOX_POUW, fallback to POUW when unavailable
- `pouw_only`: run classic POUW path only

Example:

```yaml
consensus:
    mode: mixed
    sbox_ratio: 0.65
    sbox_enabled: true
```

---

## API Documentation

### RPC Endpoint

Default port: `8545`

### Common Methods

| Method | Description |
|--------|-------------|
| `wallet_create` | Create wallet |
| `wallet_unlock` | Unlock wallet |
| `account_getBalance` | Query balance |
| `tx_send` | Send transaction |
| `mining_start` / `mining_stop` | Start/stop mining |
| `mining_getStatus` | Mining status |
| `sector_getExchangeRates` | Sector coin exchange rates |
| `sector_requestExchange` | Sector coin → MAIN exchange |
| `task_create` | Publish compute task |
| `governance_createProposal` | Create governance proposal |
| `governance_vote` | Vote |
| `staking_stake` / `staking_unstake` | Stake / Unstake |
| `chain_getInfo` | Chain status |
| `rpc_listMethods` | List all RPC methods |

`chain_getInfo` now includes mixed-consensus observability fields:

- `consensusMode`: `mixed` / `sbox_only` / `pouw_only`
- `consensusSboxRatio`: configured SBOX_POUW target ratio
- `consensusSelectedDistribution`: rolling window stats for selected consensus type
- `consensusMinedDistribution`: rolling window stats for successfully mined consensus type

### Examples

```bash
# View chain info (-k to skip self-signed cert verification)
curl -k -X POST https://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"chain_getInfo","params":{},"id":1}'

# Check balance
curl -k -X POST https://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"account_getBalance","params":{"address":"MAIN_xxx"},"id":1}'
```

For the full RPC reference, see [docs/API.md](docs/API.md) and [docs/USER_GUIDE.md](docs/USER_GUIDE.md) appendix

---

## Development Guide

## Demo Package (One-Click)

The repository now includes a complete runnable demo package in `Demo/`.

- One-click start: `Demo/start-demo.bat`
- One-click stop and cleanup: `Demo/stop-demo.bat`
- Demo script: `Demo/demo_runner.py`
- Docker setup: `Demo/docker-compose.demo.yml`

The demo validates:

- Two-account workflow (Order Account + Mining Account)
- Free order placement (`0 MAIN`)
- Mining account visibility of accepted orders and running programs
- Order completion and result return to the order account
- Additional feature checks (`chain_getInfo`, `blockchain_getHeight`, `orderbook_submitBid`)

### Running Tests

```bash
python -m pytest tests/ --tb=short
```

### Code Standards

- Python 3.9+ type annotations
- English variable names

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/xxx`)
3. Commit your changes (`git commit -m 'Add xxx'`)
4. Push the branch (`git push origin feature/xxx`)
5. Create a Pull Request

### Documentation

- [User Guide](docs/USER_GUIDE.md) — Complete user tutorial
- [Consensus Whitepaper](docs/CONSENSUS.md) — POUW + S-Box PoUW technical details ⭐
- [Security Architecture](docs/SECURITY_ARCHITECTURE.md) — Security levels & threat model
- [API Reference](docs/API.md) — RPC interface documentation
- [Contract System](docs/CONTRACT_SYSTEM.md) — Compute contracts, futures & settlement
- [Fee Mechanism](docs/FEE_MECHANISM.md) — Fee distribution details
- [Governance & Voting](docs/GOVERNANCE_VOTING.md) — DAO governance mechanism
- [Operations Manual](docs/OPERATIONS.md) — Deployment & operations guide
- [Dynamic Pricing](docs/DYNAMIC_PRICING_IMPLEMENTATION.md) — Compute market pricing
- [Security Audit](docs/SECURITY_AUDIT.md) — Security vulnerability fix records

---

## Competitive Landscape

| Dimension | **POUW Chain** | Bitcoin | Ethereum (PoS) | Filecoin | Golem/Render |
|-----------|---------------|---------|----------------|----------|--------------|
| Consensus work is useful? | **Yes** (S-Box + compute) | No | N/A (staking) | Partial (storage) | No own chain |
| Cryptographic output? | **Yes** (S-Box primitives) | No | No | No | No |
| Hardware fair? | **Yes** (multi-sector) | No (ASIC) | No (whale) | No (storage) | Partial |
| Built-in compute market? | **Yes** | No | Via contracts | Storage only | **Yes** |
| Anti-fraud mechanism? | **Blind task + traps** | N/A | Slashing | Fault proofs | Reputation |
| Dual-token deflation? | **Yes** | No | No | Partial | No |

> For detailed comparison and project outlook, see [Consensus Whitepaper §13](docs/CONSENSUS.md#13-system-advantages-limitations-and-outlook)

---

## License

MIT License

Copyright (c) 2026 POUW Chain

---

## Contact

- GitHub Issues: [Submit an issue](https://github.com/hefengchuyang-sketch/maincoin/issues/new/choose)
- Email: yuhanliu050128@gmail.com

---

*Last updated: 2026-04-07*
