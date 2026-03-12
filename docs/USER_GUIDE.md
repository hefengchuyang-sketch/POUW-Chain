# POUW Chain User Guide

> **POUW Chain** — A decentralized computing network that turns real computation into mining

---

## Table of Contents

- [What is POUW Chain](#what-is-pouw-chain)
- [Core Concepts](#core-concepts)
- [Quick Start](#quick-start)
- [Wallet & Account](#wallet--account)
- [Mining Guide](#mining-guide)
- [Compute Market — Buying Compute Power](#compute-market--buying-compute-power)
- [Pricing Mechanism](#pricing-mechanism)
- [Tokens & Exchange](#tokens--exchange)
- [Fee Structure](#fee-structure)
- [Security](#security)
- [Governance & Voting](#governance--voting)
- [FAQ](#faq)

---

## What is POUW Chain

POUW Chain is a decentralized compute-sharing platform. Traditional blockchains (like Bitcoin) have miners performing meaningless hash computations. POUW lets miners **execute real computation tasks** (AI inference, video rendering, scientific computing, etc.) to earn block rewards.

**In one sentence**: You connect your GPU to the network → the system automatically assigns paid computation tasks from other users to you → you complete tasks and earn tokens.

### Comparison with Traditional Platforms

| | Bitcoin | Traditional Cloud | **POUW Chain** |
|------|---------|-------------------|---------------|
| Compute Usage | Meaningless hashing | Manual purchase | **Real tasks = Mining** |
| Pricing | None | Platform-set | **Supply-demand dynamic pricing** |
| Trust Model | Proof of Work | Trust the platform | **Blind dispatch + trap verification** |
| Revenue Split | Block reward | Platform takes cut | **90% goes to miners** |

---

## Core Concepts

### Dual-Token System

POUW Chain has two types of tokens:

| Token | Description | How to Obtain |
|-------|-------------|---------------|
| **Sector Coins** (e.g., H100_COIN, RTX4090_COIN) | Tokens mined directly | Connect GPU and mine |
| **MAIN** (primary token) | Universal network currency for trading and buying compute | Exchange sector coins |

> **Key Point**: MAIN cannot be mined directly — it can only be obtained by exchanging sector coins. This ensures MAIN's value is backed by real compute power.

### Sectors

The network is divided into sectors by GPU model, each operating independently:

| Sector | Use Case | Block Reward | Base Exchange Rate to MAIN | Supported GPUs |
|--------|----------|-------------|---------------------------|----------------|
| H100 | Large AI model training | 10 H100_COIN | 1:0.5 | H100, A100, A6000, A40, L40 |
| RTX4090 | AI inference, rendering | 5 RTX4090_COIN | 1:0.5 | RTX 4090, 4080, 3090 Ti, 3090 |
| RTX3080 | Medium compute | 2.5 RTX3080_COIN | 1:0.5 | RTX 3080, 3070, 3060, 4070, 4060 |
| CPU | Light compute | 1 CPU_COIN | 1:0.5 | No discrete GPU / CPU only |
| GENERAL | General purpose | 1 GENERAL_COIN | 1:0.5 | Unrecognized devices |

Each sector halves independently (every 210,000 blocks), with each sector coin capped at 21 million.

### Blind Dispatch

This is POUW's core innovation. Miners **don't know** whether they're executing a paid task or a free verification task:

```
User submits compute task → System wraps it as a "mining challenge" → Randomly assigned to miner → Miner completes → Auto-settlement
```

Benefits: Miners have no incentive to cheat (they don't know which task is paid). The system mixes in **trap tasks** (verification tasks with known answers) to detect honesty.

---

## Quick Start

### Requirements

- Python 3.9 or higher
- 8 GB+ RAM
- 10 GB+ disk space
- (For miners) NVIDIA GPU with CUDA drivers installed

### Installation

```bash
# Download the code
git clone https://github.com/pouwchain/maincoin.git
cd maincoin

# Install dependencies
pip install -r requirements.txt
```

### Start a Node

```bash
# Start a full node
python main.py

# Default RPC port: 8545 (HTTPS, self-signed TLS certificate)
# Default P2P port: 9333 (TLS encrypted)
```

### Docker (Recommended)

```bash
docker-compose up -d
```

---

## Wallet & Account

### Create a Wallet

The system generates a **24-word** HD wallet (BIP-39 standard), returning a wallet address and mnemonic phrase.

```
RPC Method: wallet_create
Parameters: password (wallet encryption password)
```

On success, returns:
- **Wallet address** (format: `MAIN_` + public key hash)
- **Mnemonic phrase** (24 English words — **back up offline immediately**)

### Import a Wallet

If you have an existing mnemonic backup, you can restore it on a new device:

```
RPC Method: wallet_import
Parameters: mnemonic (24 words, space-separated), password (new password)
```

### Unlock Wallet

Before performing sensitive operations (transfers, mining, etc.), you must unlock the wallet (valid for **1 hour**, auto-locks after timeout):

```
RPC Method: wallet_unlock
Parameters: password (password)
```

### Check Balance

```
RPC Method: account_getBalance
Parameters: address (wallet address)
Returns: MAIN balance + all sector coin balances
```

### Keystore Export/Import

Keystore is an encrypted wallet file for migrating between devices:

```
Export: wallet_exportKeystore (requires password)
Import: wallet_importKeystore (requires Keystore file + password)
```

### Security Best Practices

| ✅ Do | ❌ Don't |
|-------|---------|
| Write down mnemonic on paper, store in a safe | Screenshot or photograph it |
| Keep multiple backups in separate locations | Send via messaging apps or email |
| Engrave on metal plate (fire/water resistant) | Store in cloud drives |
| Regularly verify backups are usable | Share with anyone |

- If the mnemonic is lost, assets are **permanently unrecoverable**
- For large holdings, use multi-sig wallets (requires 3/5 signature confirmations)
- Wallet files use AES-256-GCM encryption, PBKDF2 with 600,000 iterations for key derivation (OWASP recommended standard)

---

## Mining Guide

### Who Can Mine

Anyone with a GPU can participate in mining. Your GPU is automatically assigned to the corresponding sector:

- Own an H100 → Automatically joins the H100 sector
- Own an RTX 4090 → Automatically joins the RTX4090 sector
- And so on

### Mining Flow

```
1. Start the miner node and register your GPU
         ↓
2. System confirms you're online via heartbeat detection
         ↓
3. When tasks are available, the system auto-assigns them to you (blind dispatch)
         ↓
4. Your GPU automatically executes the computation
         ↓
5. Upon completion, you receive sector coin rewards
         ↓
6. You can exchange sector coins for MAIN
```

### Mining Revenue

Your revenue depends on:

1. **GPU model**: Higher compute power = higher base reward
2. **Trust score**: Consistently completing tasks correctly → higher trust score → more task assignments
3. **Task completion rate**: Trap task pass rate must be > 80% to continue receiving tasks
4. **Online time**: Going offline for more than 60 seconds marks you as unavailable

#### Revenue Sources

| Revenue Type | Source | Description |
|-------------|--------|-------------|
| Block Reward | Mining blocks | Independent rewards per sector, halving every 210,000 blocks; 97% to miner, 3% to DAO treasury |
| Task Income | Executing paid tasks | 90% of settlement goes to miner |
| Transaction Fees | Packaging transactions | 0.3% of fees go to the block-producing miner |

> **Tip**: Revenue from paid tasks is much higher than idle mining (idle blocks only yield 20% of base reward, and consecutive idle blocks decay further).

> **Note**: Mined tokens require **100 block confirmations** (~50 minutes) before they become spendable (shown as "immature balance"). This is a standard blockchain security mechanism, consistent with Bitcoin.

### Trust Mechanism

The system mixes **trap tasks** (test tasks with known correct answers) into regular tasks to verify your honesty:

- **New miners**: 30% of tasks are traps
- **Trusted miners**: 5% of tasks are traps
- **Suspicious miners**: 50% of tasks are traps
- **3 consecutive trap failures → banned**

Trap tasks come in three difficulty levels:
- Easy: Hash prefix computation
- Medium: Matrix multiplication
- Hard: Gradient descent

You don't need to worry about these details — your GPU handles all computations automatically.

---

## Compute Market — Buying Compute Power

### How to Place an Order

If you need compute power (run AI models, render videos, etc.), follow these steps:

```
1. Hold sufficient MAIN tokens
         ↓
2. Submit a compute task (specify GPU type, estimated duration)
         ↓
3. Choose a pricing strategy (immediate/standard/economy/off-peak/flexible)
         ↓
4. System locks your budget (estimated at worst case)
         ↓
5. Task auto-assigned to miners for execution
         ↓
6. Settlement on completion, refund for overpayment
```

### Pricing Strategies

Choose different strategies when ordering to balance price and speed:

| Strategy | Price Multiplier | Max Wait | Use Case |
|----------|-----------------|----------|----------|
| **Immediate** | ×1.5 (+50%) | 1 minute | Urgent tasks |
| **Standard** | ×1.0 | 10 minutes | Daily use |
| **Economy** | ×0.8 (-20%) | 1 hour | Non-urgent tasks |
| **Off-Peak** | ×0.6 (-40%) | 24 hours | Can wait until late night |
| **Flexible** | ×0.9 (-10%) | 2 hours | Let system schedule smartly |

### Budget Protection

- When ordering, the system locks your MAIN at **worst case** (max market coefficient × peak hours × strategy coefficient × 1.1 safety margin)
- Billed per minute; after task completion, the excess locked amount is **automatically refunded**
- You will **never be overcharged**

---

## Pricing Mechanism

The final compute price is determined by 4 factors:

$$\text{Unit Price} = \text{Base Price} \times \text{Supply-Demand Coefficient} \times \text{Time Period Coefficient} \times \text{Strategy Coefficient}$$

### 1. Base Price (per hour / MAIN)

| GPU | Price | | GPU | Price |
|-----|-------|-|-----|-------|
| CPU | 1.0 | | RTX 4070 | 12.0 |
| RTX 3060 | 5.0 | | RTX 4080 | 18.0 |
| RTX 3070 | 7.0 | | RTX 4090 | 25.0 |
| RTX 3080 | 10.0 | | A100 | 40.0 |
| RTX 3090 | 15.0 | | H100 | 60.0 |
| | | | H200 | 80.0 |

> Base prices can be modified through community governance voting.

### 2. Supply-Demand Coefficient (0.5x ~ 3.0x)

- Many miners, few tasks → oversupply → coefficient drops → **cheaper prices**
- Few miners, many tasks → undersupply → coefficient rises → **higher prices**
- The system uses logarithmic smoothing to prevent sharp price fluctuations

### 3. Time Period Coefficient

| Period | Hours | Coefficient |
|--------|-------|-------------|
| Peak | 9:00–12:00, 14:00–18:00 | ×1.3 (+30%) |
| Normal | Other hours | ×1.0 |
| Off-Peak | 0:00–6:00 | ×0.7 (-30%) |

### 4. Strategy Coefficient

Determined by the strategy you choose when ordering (see "Pricing Strategies" table above).

### Pricing Examples

> 3 PM (peak hours), using RTX 4090, standard strategy, balanced supply-demand:

$$25.0 \times 1.0 \times 1.3 \times 1.0 = 32.5 \text{ MAIN/hour}$$

> 3 AM (off-peak), same RTX 4090, off-peak strategy:

$$25.0 \times 1.0 \times 0.7 \times 0.6 = 10.5 \text{ MAIN/hour}$$

Same compute power, off-peak price is only **1/3** of peak price.

---

## Tokens & Exchange

### Sector Coins → MAIN

Miners earn sector coins, which must be exchanged for MAIN to use across the network. Exchange flow:

```
Your sector coins → Submit exchange request → At least 2 sector witnesses confirm → Burn sector coins → Mint equivalent MAIN
```

Large exchanges (≥1000 MAIN) require 3 witness confirmations.

### Base Exchange Rate

The default base rate for all sectors is **0.5**:

| Sector Coin | Exchange Ratio | Example |
|-------------|---------------|---------|
| 1 H100_COIN | = 0.5 MAIN | 100 H100_COIN → 50 MAIN |
| 1 RTX4090_COIN | = 0.5 MAIN | 100 RTX4090_COIN → 50 MAIN |
| 1 RTX3080_COIN | = 0.5 MAIN | 100 RTX3080_COIN → 50 MAIN |
| 1 CPU_COIN | = 0.5 MAIN | 100 CPU_COIN → 50 MAIN |
| 1 GENERAL_COIN | = 0.5 MAIN | 100 GENERAL_COIN → 50 MAIN |

Exchange rates can be adjusted through DAO governance voting. Dynamically added sectors default to a 0.5 rate.

### Rules

- Sector coins **cannot be exchanged directly** between sectors — they must first be converted to MAIN
- During exchange, sector coins are permanently burned and MAIN is newly minted
- Dual-witness confirmation ensures security (requires confirmation from miners in at least 2 independent sectors)

---

## Fee Structure

POUW Chain has two types of fees — please distinguish between them:

### 1. On-Chain Transaction Fee (charged per transfer)

**1% fee on every on-chain transaction**, with fixed and immutable allocation:

| Destination | Ratio | Description |
|------------|-------|-------------|
| 🔥 Permanent Burn | 0.5% | Deflationary mechanism — supply decreases over time |
| ⛏️ Miner Incentive | 0.3% | Rewards the block-producing miner |
| 🏛️ Protocol Fee Pool | 0.2% | Network infrastructure maintenance |

Example: You transfer 1000 MAIN → 10 MAIN fee deducted (5 burned + 3 miner + 2 protocol pool) → recipient receives 990 MAIN.

### 2. Compute Market Settlement Fee (charged on task completion)

When you purchase compute power and the task settles, the settlement amount is distributed proportionally:

| Destination | Ratio | Description |
|------------|-------|-------------|
| ⛏️ Miner | 90% | Compute provider gets the majority |
| 🏛️ Platform Operations | 5% | Network maintenance fee |
| 🏦 DAO Treasury | 5% | Community governance public fund |

Example: Your compute order settles at 100 MAIN → miner gets 90, platform operations gets 5, treasury gets 5.

### Deflation

0.5% of every on-chain transaction is **permanently burned** — these tokens disappear from circulation forever. As network transaction volume increases, the burn rate accelerates, and the total MAIN supply continuously decreases.

---

## Security

### Transaction Security

| Mechanism | Description |
|-----------|-------------|
| ECDSA Signatures | Every transaction is signed with secp256k1 elliptic curve |
| Dual Witness | MAIN transfers require 2+ independent sector confirmations |
| Nonce Anti-Double-Spend | Account transaction sequence numbers are strictly incrementing |
| Transaction Confirmations | Standard transactions are irreversible after 6 confirmations |
| Mining Maturity Period | Mining outputs spendable after 100 blocks |
| HTTPS RPC | RPC service uses TLS encryption (self-signed certificate) |
| P2P Encryption | Node-to-node communication uses TLS encryption |
| Key Derivation | PBKDF2 with 600,000 iterations (OWASP recommended) |

### Compute Task Security

| Security Level | Protection | Performance Overhead | Use Case |
|---------------|------------|---------------------|----------|
| Standard Mode | Container isolation + end-to-end encryption | ~8% | General compute tasks |
| Enhanced Mode | Task sharding + redundant verification | ~12% | Sensitive data processing |
| Confidential Mode | TEE hardware isolation (planned) | ~30% | Top secret |

### Miner Behavior Monitoring

- AI anomaly detection: Automatically identifies suspicious behavior patterns
- Trap verification: Mixes in tasks with known answers to test miner honesty
- Credit scoring: Continuously tracks miner performance, affects task dispatch priority
- Banning mechanism: Serious violations result in automatic bans

---

## Governance & Voting

### DAO Governance

POUW Chain is governed collectively by the community. Major decisions require voting:

**Votable matters:**
- Compute market fee adjustments (platform fee 0%–10%, miner share 80%–95%, treasury 0%–10%)
- GPU base price modifications
- Treasury fund expenditures
- System upgrade proposals
- …

**Proposal types:**

| Type | Description |
|------|-------------|
| `PARAMETER_CHANGE` | Modify system parameters (difficulty, block time, etc.) |
| `FEE_ADJUSTMENT` | Adjust fee ratios |
| `TREASURY_SPEND` | Disburse from treasury |
| `UPGRADE` | System upgrade |
| `GOVERNANCE` | Governance rule changes |
| `SIGNER_ROTATION` | Rotate multi-sig signers |
| `SECTOR_ADD` | **Add new sector** (e.g., future RTX5090) |
| `SECTOR_DEACTIVATE` | **Deactivate sector** (requires all sector coins to be fully mined) |
| `EMERGENCY` | Emergency proposal (voting period shortened to 24 hours) |

**Voting rules:**

| Parameter | Standard Proposal | Emergency Proposal |
|-----------|-------------------|-------------------|
| Proposal Threshold | Stake 1000 MAIN | Stake 1000 MAIN |
| Voting Threshold | Stake 100 MAIN | Stake 100 MAIN |
| Voting Period | 7 days | 24 hours |
| Quorum | 10% | 20% |
| Approval Threshold | >50% | >66% |
| Minimum Voters | 3 | 5 |
| Execution Delay | 2 days | Immediate |

**Staking operations:**

```
Stake:    staking_stake    Parameters: amount (MAIN quantity)
Unstake:  staking_unstake  Parameters: amount (MAIN quantity)
Query:    staking_getRecords
```

**Sector management:**

Add sector — Submit a `sector_add` proposal specifying sector name, base reward, exchange rate, max supply, and supported GPU models. Takes effect after community vote approval.

Deactivate sector — Prerequisite: all sector coins must be **fully mined** (minted amount ≥ max supply of 21,000,000). Submit a `sector_deactivate` proposal. After vote approval, the sector stops accepting new miners and tasks, but historical data and balances are preserved.

### Treasury Funds

Treasury funds come from transaction fees (0.2%) and compute market settlement fees (5%), with strictly limited usage:

**Permitted uses:**
- Network infrastructure (node servers, DNS, IPFS gateways)
- Security audits
- Bug bounty programs
- Ecosystem incentives (requires voting approval)

**Prohibited actions (hardcoded):**
- ❌ Cannot interfere with task scheduling
- ❌ Cannot freeze anyone's account
- ❌ Cannot modify completed settlements
- ❌ Cannot unilaterally modify fee rates
- ❌ Cannot access user funds

Treasury expenditures require 3/5 multi-sig confirmation + DAO vote approval. Multi-sig seats: Foundation 1 seat + Dev team 1 seat + Community 3 seats (community holds 60% majority). Signers can be rotated through governance voting.

---

## FAQ

### General

**Q: What's the difference between POUW Chain and Bitcoin?**

Bitcoin "mining" performs meaningless hash computations. POUW lets miners execute real, useful computation tasks (AI inference, rendering, scientific computing), creating actual value while securing the blockchain.

**Q: What's the total supply of MAIN?**

MAIN is not directly produced — it's minted through sector coin exchange. Each sector coin is capped at 21 million, plus the 0.5% permanent burn per transaction makes MAIN deflationary.

**Q: What if I lose my private key?**

It cannot be recovered. Blockchain decentralization means there's no "forgot password" feature. Please safeguard your private keys carefully.

---

### Mining

**Q: My GPU isn't very powerful — is it worth mining?**

Yes. The system divides miners into sectors by GPU model, so your GPU only competes with the same model. Even RTX 3080 or CPU have their own sectors and rewards.

**Q: I don't know what tasks I'm executing — is my data safe?**

The task data you execute is end-to-end encrypted. You can only see an encrypted "mining challenge" and cannot see the actual content. In enhanced mode, tasks are also sharded — you only process a portion and cannot reconstruct the complete data.

**Q: Do I need to stay online all the time for mining?**

It's recommended to stay online. Going offline for more than 60 seconds marks you as unavailable and stops task assignments. Coming back online automatically restores your status.

**Q: What if there are no tasks for a long time?**

When there are no paid tasks, the system generates "idle blocks." Idle blocks still earn rewards, but only 20% of the base reward, and consecutive idle blocks decay further (-10% per consecutive idle block, minimum 5%).

---

### Fees

**Q: How much do I actually pay when buying compute power?**

You only pay the 1% on-chain transaction fee. The 10% compute market split (5% platform + 5% treasury) is deducted from what you pay the miner — it's not an extra charge to you.

**Q: How can I save money?**

- Choose the **off-peak strategy** (run during late night hours) — prices can be as low as 1/3 of peak
- Choose the **economy strategy** — 20% cheaper but requires queuing
- Avoid peak hours (9–12 AM, 2–6 PM) — 30% more expensive
- Watch the supply-demand coefficient: prices are cheaper when more miners are available

**Q: The locked budget is much more than my actual spending — is this normal?**

Yes. The system locks budget at worst case (max price × peak hours × 1.1 safety margin) to ensure the task can definitely complete. After settlement, the excess is automatically refunded to your account.

---

### Security

**Q: Can miners spy on my data?**

In standard mode, data is end-to-end encrypted — miners can only see ciphertext. In enhanced mode, tasks are sharded — individual miners only get partial data and cannot reconstruct it. Confidential mode (planned) will use TEE hardware isolation.

**Q: Can miners cheat and return fake results?**

Very difficult. The system randomly mixes in trap tasks (verification tasks with known correct answers) — miners don't know which tasks are traps. 3 consecutive trap failures result in a ban.

**Q: What if someone tries to control the network?**

The dual-witness mechanism requires every MAIN transaction to be confirmed by miners from at least 2 independent sectors. An attacker would need to simultaneously control more than 51% of compute power across multiple sectors — an extremely costly attack.

---

## Appendix: RPC Method Reference

### Wallet & Account

| Method | Function | Requires Unlock |
|--------|----------|----------------|
| `wallet_create` | Create wallet (returns mnemonic) | No |
| `wallet_import` | Import mnemonic wallet | No |
| `wallet_unlock` | Unlock wallet (valid for 1 hour) | No |
| `wallet_lock` | Lock wallet | No |
| `wallet_exportKeystore` | Export encrypted wallet file | Yes |
| `wallet_importKeystore` | Import encrypted wallet file | No |
| `account_getBalance` | Query balance (MAIN + sector coins) | No |
| `account_getNonce` | Query transaction nonce | No |
| `account_getTransactions` | Query transaction history | No |
| `account_getSubAddresses` | Query sub-address list | No |
| `account_createSubAddress` | Create sub-address | Yes |

### Transfers & Transactions

| Method | Function | Requires Unlock |
|--------|----------|----------------|
| `tx_send` | Send transaction | Yes |
| `tx_get` | Query transaction details | No |
| `tx_getByAddress` | Query transactions by address | No |
| `mempool_getInfo` | Mempool overview | No |
| `mempool_getPending` | Pending transaction list | No |

### Mining

| Method | Function | Requires Unlock |
|--------|----------|----------------|
| `mining_start` | Start mining | Yes |
| `mining_stop` | Stop mining | No |
| `mining_getStatus` | Mining status | No |
| `mining_getRewards` | Cumulative rewards | No |
| `mining_setMode` | Switch mode (mining_only/task_only/mining_and_task) | Yes |
| `mining_getScore` | POUW score | No |

### Sector Coins & Exchange

| Method | Function | Requires Unlock |
|--------|----------|----------------|
| `sector_getExchangeRates` | Query all sector exchange rates | No |
| `sector_requestExchange` | Initiate sector coin → MAIN exchange | Yes |
| `sector_getExchangeHistory` | Exchange history | No |
| `sector_cancelExchange` | Cancel pending exchange | Yes |
| `witness_request` | Request witness | Yes |
| `witness_getStatus` | Query witness status | No |

### Compute Market

| Method | Function | Requires Unlock |
|--------|----------|----------------|
| `task_create` | Publish compute task | Yes |
| `task_getList` | Task list | No |
| `task_getInfo` | Task details | No |
| `task_cancel` | Cancel task | Yes |
| `task_acceptResult` | Accept result and rate | Yes |
| `compute_submitOrder` | Submit compute order | Yes |
| `compute_getOrder` | Order details | No |
| `compute_getMarket` | Market overview | No |
| `pricing_getRealTimePrice` | Real-time compute price | No |
| `pricing_getStrategies` | Available strategy list | No |
| `pricing_getPriceForecast` | Price forecast | No |
| `budget_deposit` | Deposit to budget | Yes |
| `budget_getBalance` | Budget balance | No |
| `settlement_getRecord` | Settlement records | No |
| `settlement_getDetailedBill` | Detailed bill | No |

### DAO Governance

| Method | Function | Requires Unlock |
|--------|----------|----------------|
| `governance_createProposal` | Create proposal (requires stake ≥1000) | Yes |
| `governance_vote` | Vote (requires stake ≥100) | Yes |
| `governance_getProposals` | Proposal list | No |
| `governance_getProposal` | Proposal details | No |
| `staking_stake` | Stake MAIN | Yes |
| `staking_unstake` | Unstake | Yes |
| `staking_getRecords` | Staking records | No |
| `sector_add` | Add sector proposal | Yes |
| `sector_deactivate` | Deactivate sector proposal | Yes |

### Blockchain Queries

| Method | Function |
|--------|----------|
| `chain_getInfo` | Chain basic info |
| `chain_getHeight` | Current block height |
| `block_getLatest` | Latest block |
| `block_getByHeight` | Query block by height |
| `block_getByHash` | Query block by hash |
| `blockchain_getLatestBlocks` | Latest N blocks |

### Monitoring & Statistics

| Method | Function |
|--------|----------|
| `dashboard_getStats` | Dashboard statistics |
| `stats_getNetwork` | Network statistics |
| `stats_getBlocks` | Block statistics |
| `stats_getTasks` | Task statistics |
| `market_getDashboard` | Market dashboard |
| `rpc_listMethods` | List all available RPC methods |

## RPC Quick Reference

The node provides a JSON-RPC interface at `https://127.0.0.1:8545` by default (HTTPS, self-signed TLS certificate).

### Common Endpoints

```bash
# View node info (-k to skip self-signed cert verification)
curl -k -X POST https://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"node_getInfo","params":{},"id":1}'

# View chain info (including block height)
curl -k -X POST https://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"chain_getInfo","params":{},"id":1}'

# Check MAIN balance
curl -k -X POST https://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"wallet_getBalance","params":{"address":"YOUR_ADDRESS"},"id":1}'

# Check mining status
curl -k -X POST https://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"mining_getStatus","params":{},"id":1}'

# List all registered methods
curl -k -X POST https://127.0.0.1:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"rpc_listMethods","params":{},"id":1}'
```

---

## Technical Parameters Quick Reference

| Parameter | Value |
|-----------|-------|
| Chain ID | 9333 |
| Block Time | 30 seconds |
| Halving Cycle | 210,000 blocks (~73 days) |
| Base Block Reward | 50.0 (97% miner + 3% DAO treasury) |
| Transaction Fee | 1% (0.5% burn + 0.3% miner + 0.2% protocol pool) |
| Confirmation Count | 6 |
| Mining Maturity | 100 blocks (Coinbase Maturity) |
| Dual Witness Count | 2 (3 for large amounts) |
| Witness Timeout | 60 seconds |
| P2P Port | 9333 (TLS encrypted) |
| RPC Port | 8545 (HTTPS, self-signed TLS) |
| Signature Algorithm | ECDSA secp256k1 |
| Key Derivation | PBKDF2 600,000 iterations |
| Max Block Size | 1 MB |
| Max Transactions per Block | 2000 |
| POUW Proofs | 4 per block (difficulty 2) |

---

*This document is based on POUW Chain v2.0.0, last updated: 2026-03-08*
