# POUW Chain Consensus Mechanism Whitepaper

> **Proof of Useful Work**
>
> Version 1.0  2026-03

---

## Abstract

POUW (Proof of Useful Work) is a novel blockchain consensus mechanism that allows miners to execute **real useful computation tasks**  AI inference, numerical optimization, hash computation, etc.  while maintaining blockchain security. Unlike Bitcoin's SHA-256 brute-force approach, POUW converts the computing power required for consensus into actual productivity, eliminating the energy waste problem of traditional PoW without sacrificing decentralization and security.

This document defines the consensus rules, block structure, economic model, security mechanisms, and governance framework of POUW Chain.

---

## Table of Contents

1. [Design Goals](#1-design-goals)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [POUW Consensus Mechanism](#3-pouw-consensus-mechanism)
4. [Block Structure and Validation](#4-block-structure-and-validation)
5. [Difficulty Adjustment Algorithm](#5-difficulty-adjustment-algorithm)
6. [Multi-Sector Architecture](#6-multi-sector-architecture)
7. [Dual-Witness Mechanism](#7-dual-witness-mechanism)
8. [Economic Model](#8-economic-model)
9. [Blind Task Engine and Anti-Fraud](#9-blind-task-engine-and-anti-fraud)
10. [DAO Governance](#10-dao-governance)
11. [Security Analysis](#11-security-analysis)
12. [Parameter Summary](#12-parameter-summary)

---

## 1. Design Goals

POUW Chain's design revolves around five core objectives:

| Goal | Implementation |
|------|---------------|
| **Usefulness** | Consensus process executes real computation tasks, not meaningless hashes |
| **Fairness** | Hardware-based sector competition, blind dispatch prevents manipulation |
| **Security** | Dual-witness cross-sector confirmation, trap tasks for anti-fraud |
| **Decentralization** | DAO governance, immutable protocol fees, multi-sig treasury |
| **Sustainability** | Deflationary economic model, halving mechanism, effective energy utilization |

---

## 2. System Architecture Overview

```
+----------------------------------------------------------------+
|                        POUW Chain                              |
+----------+----------+----------+----------+----------+---------+
|  H100    | RTX4090  | RTX3080  |   CPU    | GENERAL  | Dynamic.|
|  Sector  |  Sector  |  Sector  |  Sector  |  Sector  | Sector  |
| (10/blk) | (5/blk)  |(2.5/blk) | (1/blk)  | (1/blk)  |         |
+----------+----------+----------+----------+----------+---------+
|                    Dual-Witness Layer                           |
|         (Cross-sector independent verification                 |
|          - prevents single-point collusion)                    |
+----------------------------------------------------------------+
|                    MAIN Chain Ledger                            |
|    (Cannot be mined directly - only minted via sector          |
|     coin exchange)                                             |
+----------------------------------------------------------------+
| Blind Task Engine | Compute Market | DAO Gov | Sector Exchange |
+----------------------------------------------------------------+
```

**Core Data Flow**:

```
Miner produces block -> Receives sector coin reward -> Initiates exchange request -> Dual-witness verification -> Burns sector coin + Mints MAIN
```

---

## 3. POUW Consensus Mechanism

### 3.1 Core Concept

Traditional PoW requires miners to repeatedly compute meaningless hashes until finding a nonce that satisfies the condition. POUW retains PoW's competitive block production model but replaces the "work" with **real computation tasks**.

Each block must contain a POUW proof (Proof of Useful Work Proof), demonstrating that the miner completed valuable computation during the block production process.

### 3.2 Task Types

The system supports three POUW task types, defined by the `TaskType` enum:

| Task Type | Identifier | Typical Scenarios |
|-----------|-----------|-------------------|
| **AI Inference** | `AI_INFERENCE` | Neural network forward inference, model evaluation |
| **Numerical Optimization** | `NUMERICAL_OPTIMIZATION` | Matrix operations, gradient descent, linear programming |
| **Hash Computation** | `HASH_COMPUTATION` | Cryptographic hashing, Merkle tree construction |

### 3.3 POUW Scoring System

Miner POUW proofs are scored through a multi-dimensional scoring system:

**Objective Metrics Weight** (70% of composite score):

| Metric | Weight | Description |
|--------|--------|-------------|
| Task Completion Rate | 30% | Proportion of successfully completed tasks |
| Response Latency | 25% | Optimal latency 100ms, max acceptable 5000ms |
| Uptime Stability | 25% | Continuous online time and heartbeat response |
| Block Participation | 20% | Active participation in block validation |

**User Feedback Weight** (30% of composite score):

- Users can rate task results: 0 to 5 stars (0.5 increments)
- Minimum 5 feedback entries required before score takes effect

**Composite Score Formula**:

$S = 0.70 \times S_{\text{objective}} + 0.30 \times S_{\text{feedback}}$

**Minimum Passing Score**: 70% (POUW proofs below this score are invalid and the block is rejected).

### 3.4 Block Production Flow

```
1. Miner obtains POUW tasks from the task pool (or system-assigned)
         |
2. Executes computation (AI inference / numerical optimization / hash computation)
         |
3. Generates POUW proof (includes computation result, execution time, resource consumption)
         |
4. Constructs block: block header + transaction list + POUW proof list
         |
5. Validates: difficulty satisfied + POUW score >= 70%
         |
6. Broadcasts block to network
         |
7. Other nodes verify and accept into chain
```

### 3.5 Task Execution Constraints

| Parameter | Value |
|-----------|-------|
| Max execution time | 300 seconds |
| Max memory usage | 4096 MB |
| Max CPU cores | 4.0 |
| Max concurrent tasks | 3 |

### 3.6 S-Box PoUW — Cryptographic Proof of Useful Work

In addition to the task-based POUW scoring, POUW Chain introduces a cryptographic layer of useful work: **S-Box PoUW**. Each block's mining process simultaneously generates a high-quality **S-Box** (Substitution Box), a fundamental building block of modern symmetric ciphers (AES, Camellia, etc.).

#### 3.6.1 What is S-Box PoUW?

An S-Box is a bijective mapping $f: \{0,1\}^8 \to \{0,1\}^8$ (a permutation of 256 values). The quality of an S-Box determines the cryptographic strength of any cipher that uses it.

POUW Chain requires miners not only to find a valid nonce (hash difficulty), but also to produce an S-Box that meets minimum quality thresholds:

| Quality Metric | Description | Measurement |
|----------------|-------------|-------------|
| **Nonlinearity** | Resistance to linear cryptanalysis | Walsh-Hadamard Transform: $NL = 128 - \frac{1}{2} \max_{a \neq 0} \lvert W_f(a) \rvert$ |
| **Differential Uniformity** | Resistance to differential cryptanalysis | $\delta = \max_{a \neq 0, b} \lvert \{x : f(x \oplus a) \oplus f(x) = b\} \rvert$ |
| **Avalanche Effect** | Single-bit input change → ~50% output change | $AV = \frac{1}{8 \times 256} \sum \text{Hamming}(f(x), f(x \oplus e_i))$ |

**Scoring Formula**:

$$S_{\text{sbox}} = w_1 \cdot \frac{NL}{112} + w_2 \cdot \frac{4}{\delta} + w_3 \cdot \frac{AV}{0.5}$$

Default weights: $w_1 = 0.4$ (nonlinearity), $w_2 = 0.3$ (differential uniformity), $w_3 = 0.3$ (avalanche).

#### 3.6.2 Mining Flow

```
1. Each sector independently generates candidate S-Boxes
         |
2. Genetic optimization (crossover + mutation, 5-10 generations)
         |
3. Score evaluation: nonlinearity + differential uniformity + avalanche
         |
4. Score >= threshold? (dynamically adjusted per-epoch)
         |
5. VRF sector selection: SHA256(prev_hash + height + all_sbox_hashes)
         |
6. Winner's S-Box embedded in block → becomes current network S-Box
         |
7. S-Box Library updated → available for encryption layer
```

#### 3.6.3 Multi-Sector VRF Selection

When multiple sectors mine concurrently, each produces a candidate S-Box. A deterministic VRF (Verifiable Random Function) selects the winner:

$$\text{selector} = \text{SHA256}(\text{prev\_hash} \| \text{height} \| \text{sbox\_hash}_1 \| \dots \| \text{sbox\_hash}_n)$$

$$\text{winner} = \text{sectors}[\text{selector} \mod n]$$

Any node can re-derive the same result — fully verifiable, no trusted party needed.

#### 3.6.4 Dual Difficulty Adjustment

S-Box PoUW uses a dual difficulty system that adjusts every epoch:

| Parameter | Adjustment | Range |
|-----------|-----------|-------|
| Hash difficulty | ±1 per epoch | 2 ~ 32 leading zeros |
| Score threshold | ×0.9 ~ ×1.1 per epoch | 0.3 ~ 0.95 |
| Weight drift | ±3% per epoch | Prevents gaming fixed weights |

#### 3.6.5 Chain Data Compression

Each S-Box is a 256-byte permutation. To minimize chain bloat, POUW supports two serialization modes:

| Mode | Storage per Block | Method |
|------|------------------|--------|
| **Full** (default for local DB) | ~700 bytes | Full S-Box hex (512 chars) + metrics |
| **Compact** (network sync) | ~250 bytes | SHA-256 hash reference (64 chars) + metrics |

In compact mode, the full S-Box is stored in the **S-Box Library** (local node database), and only its 32-byte hash is embedded in the block. Receiving nodes look up the full S-Box from their library, or request it from peers via RPC if missing.

**Annual chain overhead** (assuming 30s block time, ~1M blocks/year):
- Full mode: ~700 bytes × 1M = **~700 MB/year**
- Compact mode: ~250 bytes × 1M = **~250 MB/year**
- For comparison: Bitcoin's base chain grows ~60 GB/year

#### 3.6.6 S-Box Encryption Integration

Mined S-Boxes are not wasted — they feed directly into the encryption layer:

| Scenario | Encryption Level | Description |
|----------|-----------------|-------------|
| **P2P data tunnels** (ephemeral keys) | ENHANCED | AES-256-GCM + S-Box SubBytes substitution |
| **Task input/output** | ENHANCED | S-Box applied before AES encryption |
| **Wallet / on-chain transfer** | STANDARD | Pure AES-256-GCM (no S-Box needed) |

**Design principle**: S-Box stacking is used for **one-time key** scenarios (P2P tunnel sessions, task data). For **fixed address** operations (wallet transfers, persistent keys), pure AES is sufficient — no need for dynamic substitution.

**Session locking**: Once a P2P session or task begins, the S-Box is **snapshot-locked** at creation time. Even if a new block produces a new S-Box, the in-flight session continues using the original S-Box until completion. This prevents mid-task decryption failures.

---

## 4. Block Structure and Validation

### 4.1 Block Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Target block time | **30 seconds** | Difficulty dynamically adjusted around this target |
| Min block time | 10 seconds | Prevents too-fast block production |
| Max block time | 120 seconds | Prevents too-slow block production |
| Max block size | **1 MB** (1,048,576 bytes) | Includes header + transactions + POUW |
| Max block header size | 1,024 bytes | |
| Max transactions per block | **2,000** | |
| Max POUW proofs per block | **50** | |
| Base block reward | 50.0 (independent per sector) | Subject to halving |

### 4.2 Block Hash Algorithm

The block hash is computed by concatenating the following fields and calculating SHA-256:

```
hash = SHA256(
    height + prev_hash + merkle_root + timestamp + difficulty +
    nonce + miner_id + consensus_type + block_reward + total_fees +
    sector + miner_address + block_type
)
```

`miner_address` and `block_type` are included in the hash to prevent attackers from tampering with the miner's receiving address or block type without affecting the block hash.

### 4.3 Block Validation Rules

A block must satisfy all of the following conditions to be accepted by the network:

1. **Structural validity**: Block size <= 1MB, transactions <= 2000, POUW proofs <= 50
2. **Forward linking**: `prev_hash` points to the current chain tip block
3. **Difficulty met**: Number of leading zeros in block hash >= current difficulty
4. **Reasonable timestamp**: Greater than the previous block and no more than 120 seconds in the future
5. **POUW qualified**: At least 1 POUW proof with score >= 70%
6. **Valid transactions**: All transaction signatures valid, sufficient balance, correct nonce
7. **Correct fees**: Fees distributed at 0.5% burn + 0.3% miner + 0.2% foundation ratio
8. **Consistent miner address**: `miner_address` in block header participates in hash calculation and cannot be tampered with

### 4.4 Block Reward Distribution

```
Block Reward (Sector Coin)
+-- 97%  ->  Block Miner
+--  3%  ->  DAO Treasury (MAIN_TREASURY, auto-converted to MAIN)
```

This distribution is automatically executed by the consensus layer at block production time and cannot be modified. For example, with a base reward of 50.0, the miner actually receives 48.5, and the treasury receives 1.5.

---

## 5. Difficulty Adjustment Algorithm

### 5.1 Adjustment Cycle

Difficulty is adjusted every **10 blocks**.

### 5.2 Adjustment Logic

```
actual_time  = Actual total time for the last 10 blocks
expected_time = 10 x 30 = 300 seconds
ratio = expected_time / actual_time

if ratio > 1    ->  Blocks too slow  ->  Decrease difficulty
if ratio < 1    ->  Blocks too fast  ->  Increase difficulty
```

Adjustment magnitude is limited by a smoothing factor to prevent drastic difficulty fluctuations.

### 5.3 Difficulty Range

| Parameter | Value |
|-----------|-------|
| Min difficulty | 2 (leading zeros) |
| Max difficulty | 32 |
| Initial difficulty | 4 |

---

## 6. Multi-Sector Architecture

### 6.1 Design Rationale

Different GPUs have vastly different computing power (H100 vs RTX 3060 can differ by 10x or more). If all miners compete in the same pool for block production, low-power devices would have virtually no chance of earning rewards.

POUW Chain assigns miners to different **Sectors** based on hardware type, with each sector producing blocks independently, ensuring fair mining opportunities for all hardware types.

### 6.2 Initial Sectors

| Sector | Compatible GPU Models | Base Block Reward | Max Supply |
|--------|-----------------------|-------------------|------------|
| **H100** | H100, A100, A6000, A40, L40 | 10.0/block | 21,000,000 |
| **RTX4090** | RTX 4090, 4080, 3090 Ti, 3090 | 5.0/block | 21,000,000 |
| **RTX3080** | RTX 3080, 3070, 3060, 4070, 4060 | 2.5/block | 21,000,000 |
| **CPU** | No dedicated GPU / CPU only | 1.0/block | 21,000,000 |
| **GENERAL** | Unrecognized devices / General | 1.0/block | 21,000,000 |

The system automatically detects the miner's GPU model and assigns them to the corresponding sector. Miners cannot choose their sector.

### 6.3 Dynamic Sector Management

The sector list is not hardcoded. Through the `SectorRegistry`, the community can:

- **Add sectors**: Via DAO proposal voting (e.g., future RTX 5090 sector)
- **Deactivate sectors**: When a sector's coins are fully mined (minted amount >= max supply of 21,000,000), it can be deactivated through voting

Default parameters for new sectors:
- Exchange rate: 0.5
- Max supply: 21,000,000
- Halving cycle: 210,000 blocks

### 6.4 Cross-Sector Rules

- Coins from different sectors **cannot be directly exchanged** (H100_COIN <-> RTX4090_COIN is prohibited)
- Must first exchange sector coins for MAIN, then use MAIN to operate in another sector
- Exchange requires **dual-witness** cross-sector confirmation

---

## 7. Dual-Witness Mechanism

### 7.1 Design Goal

In traditional blockchains, transactions only need to be included by the block-producing miner for confirmation. POUW Chain requires all MAIN transfers and sector coin exchanges to go through **at least 2 witness nodes from different sectors** for independent verification, fundamentally preventing intra-sector collusion.

### 7.2 Witness Flow

```
Sender signs transaction
        |
System randomly selects 2 witness nodes from different sectors
        |
Witness A (Sector X) independently verifies:
  - Sender has sufficient balance
  - Signature valid (ECDSA secp256k1)
  - Nonce correct (anti-double-spend)
  - Transaction format valid
        |
Witness B (Sector Y, Y != X) independently verifies (same checks)
        |
Both witness signatures collected
        |
Transaction marked as confirmed (irreversible)
```

### 7.3 Large Transaction Enhancement

| Transfer Amount | Required Witnesses | Sector Diversity Requirement |
|----------------|--------------------|-----------------------------|
| < 1,000 MAIN | 2 | From 2 different sectors |
| >= 1,000 MAIN | **3** | From 3 different sectors |

### 7.4 Witness Timeout

If insufficient signatures are received within **60 seconds** after the witness request is sent, the transaction times out and is returned.

### 7.5 Security Analysis

If an attacker wants to forge a regular MAIN transfer, they would need to simultaneously control:
- At least 1 node each in 2 **different sectors**
- These nodes must be randomly selected by the system as witnesses

Attack cost = controlling multiple sectors x probability of being randomly selected, far higher than a traditional single-chain 51% attack.

---

## 8. Economic Model

### 8.1 Dual-Token System

| Token | Production Method | Purpose | Total Supply |
|-------|------------------|---------|--------------|
| **Sector Coin** | Mining output | Intra-sector settlement | 21,000,000 per sector |
| **MAIN** | Minted via sector coin exchange | Cross-sector settlement, governance, compute market | 100,000,000 (100M) |

**Core Rule**: MAIN cannot be mined directly; it can only be obtained through sector coin exchange. This ensures every MAIN token is backed by real computing power contributions.

### 8.2 Exchange Mechanism

All sectors share a default base exchange rate of **0.5**:

$$\text{MAIN received} = \text{Sector coin amount} \times 0.5UTF8

Example: 200 H100_COIN -> 100 MAIN

During exchange, sector coins are **permanently burned** and MAIN is **newly minted**  this is a one-way irreversible process.

### 8.3 Halving Mechanism

Drawing from Bitcoin's halving model, each sector halves independently:

| Parameter | Value |
|-----------|-------|
| Halving cycle | **210,000 blocks** (approx. 73 days at 30 sec/block) |
| Initial reward (H100 as example) | 10.0 H100_COIN/block |
| After 1st halving | 5.0 |
| After 2nd halving | 2.5 |
| After Nth halving | $10.0 \times 2^{-N}$ |

When block rewards approach 0 and the total minted amount reaches the 21,000,000 cap, the sector stops producing new coins.

### 8.4 Fee System

#### 8.4.1 On-Chain Transaction Fees (Immutable)

Each on-chain transaction is charged a **1%** fee, with distribution ratios hardcoded in the protocol:

| Destination | Ratio | Mechanism |
|-------------|-------|-----------|
| **Burn** | 0.5% | Permanently reduces circulating supply (deflationary) |
| **Block Miner** | 0.3% | Incentivizes miners to include transactions |
| **Protocol Fund Pool** | 0.2% | Multi-sig managed, used for infrastructure |

#### 8.4.2 Compute Market Settlement Fees (Adjustable via DAO)

| Destination | Ratio | Description |
|-------------|-------|-------------|
| **Miner** | 90% | Compute provider receives the majority |
| **Platform Operations** | 5% | Network maintenance |
| **DAO Treasury** | 5% | Public fund |

### 8.5 Deflation Mechanism

MAIN achieves net deflation through the following mechanisms:

1. **Transaction burn**: 0.5% of each transaction permanently burned
2. **Sector coin burn**: Sector coins permanently destroyed during exchange
3. **Halving**: Block rewards halve periodically, decreasing new coin minting rate
4. **Supply cap**: MAIN hard cap of 100 million

Initially, minting rate > burn rate (circulating supply increases). As transaction volume grows and halving progresses, burn rate will eventually exceed minting rate, achieving net deflation.

### 8.6 Treasury

| Parameter | Value |
|-----------|-------|
| Genesis seed fund | 1,000 MAIN |
| Funding sources | 3% block rewards + 5% compute market fees + 0.2% transaction fees |
| Multi-sig requirement | 3/5 multi-sig confirmation |
| Daily auto-compensation cap | 100 MAIN |
| Per-miner daily limit | 20 MAIN |

---

## 9. Blind Task Engine and Anti-Fraud

### 9.1 Blind Dispatch Mechanism

In traditional compute markets, miners know which tasks are paid, giving them incentive to cheat on paid tasks (returning fake results to collect payment).

POUW's **Blind Task Engine** solves this problem:

1. All tasks (paid + verification traps) are uniformly packaged and appear identical
2. Miners **cannot distinguish** which is a real paid task and which is a trap
3. The system dynamically adjusts trap task ratios based on miner trust scores
4. Trap camouflage keys differ each run (`CAMOUFLAGE_SECRET = os.urandom(32)`)

### 9.2 Trap Task Ratios

| Miner Trust Level | Trust Score | Trap Ratio |
|-------------------|-------------|------------|
| New miner | Initial value | **30%** |
| High-trust miner | >= 0.90 | **5%** |
| Suspicious miner | <= 0.50 | **50%** |

### 9.3 Trust Scoring and Penalties

| Event | Impact |
|-------|--------|
| Trap task passed | Trust score + (normal incentive) |
| Trap task failed | Trust score **-20%** |
| Consecutive failures | Trust score **-50%** |
| 3 consecutive trap failures | **Automatic mining ban** |

### 9.4 Anti-Manipulation Mechanism

- Compute tasks **cannot specify a miner**  the system assigns randomly
- Miner assignment uses weighted random algorithm: weight = compute score x trust score x online status
- Block packaging miners are also randomly selected (not purely computing power competition)

---

## 10. DAO Governance

### 10.1 Governance Principles

POUW Chain's core economic parameters (transaction fee ratios, burn ratios) **cannot be modified through governance** and are hardcoded in the protocol. The scope of governance is clearly defined:

**Immutable (Hardcoded)**:
- On-chain transaction fee 1% (0.5% burn + 0.3% miner + 0.2% foundation)
- MAIN max supply 100 million
- Each sector coin max supply 21 million
- Halving cycle 210,000 blocks

**Modifiable via DAO Governance**:
- Compute market fee rates (miner/platform/treasury split)
- GPU base pricing
- Sector exchange rates
- Add / deactivate sectors
- Treasury fund expenditure
- System upgrades

### 10.2 Proposal Types

| Type | Description |
|------|-------------|
| `PARAMETER_CHANGE` | Modify adjustable system parameters |
| `FEE_ADJUSTMENT` | Adjust compute market fee rates |
| `TREASURY_SPEND` | Allocate funds from treasury |
| `UPGRADE` | System upgrade |
| `GOVERNANCE` | Governance rule changes |
| `SIGNER_ROTATION` | Replace multi-sig signers |
| `SECTOR_ADD` | Add a new sector |
| `SECTOR_DEACTIVATE` | Deactivate a sector (requires sector coins to be fully mined) |
| `EMERGENCY` | Emergency proposal |

### 10.3 Voting Rules

| Parameter | Normal Proposal | Emergency Proposal |
|-----------|----------------|-------------------|
| Proposal stake threshold | 1,000 MAIN | 1,000 MAIN |
| Voting stake threshold | 100 MAIN | 100 MAIN |
| Voting weight | 1 MAIN = 1 vote | 1 MAIN = 1 vote |
| Voting period | **7 days** | **24 hours** |
| Quorum | **10%** | **20%** |
| Approval threshold | **50%** | **66%** |
| Minimum voters | **3** | **5** |
| Execution delay | **2 days** | Immediate |

### 10.4 Proposal Lifecycle

```
CREATED (Created, stake locked)
     |
VOTING (Voting period begins)
     |  <- Community votes (for / against / abstain)
     |
PASSED / REJECTED (Threshold met -> Passed / Not met -> Rejected)
     | [Passed only]
EXECUTION_DELAY (Wait 2-day safety delay)
     |
EXECUTED (Takes effect)
```

### 10.5 Treasury Governance

Treasury expenditures require dual safeguards:
1. DAO vote passed
2. 3/5 multi-sig confirmation

**Prohibited Treasury Actions (Code-Level Guarantees)**:
- No interfering with task scheduling
- No freezing or confiscating user assets
- No modifying completed settlement records
- No unilaterally modifying fee rates
- No bypassing voting for direct execution

---

## 11. Security Analysis

### 11.1 Consensus Security

| Attack Type | Defense Mechanism |
|-------------|-------------------|
| **51% Attack** | Multi-sector architecture distributes hash power; attacker must control multiple sectors |
| **Double Spend** | Dual-witness cross-sector confirmation + Nonce increment |
| **Selfish Mining** | Random miner selection + POUW task binding |
| **Long-Range Attack** | Checkpoint mechanism + difficulty adjustment |
| **Sybil Attack** | Miners require real computing power contribution + trust scoring system |

### 11.2 Compute Market Security

| Attack Type | Defense Mechanism |
|-------------|-------------------|
| **Fake Computation Results** | Trap task detection + consecutive failure ban |
| **Wash Trading (Self-dealing)** | Blind dispatch + no miner specification allowed |
| **Miner Collusion** | Cross-sector dual-witness + random assignment |
| **Denial of Service** | Rate limiting (200 requests/min/IP) |
| **Data Theft** | AES-256-GCM end-to-end encryption + task sharding |

### 11.3 Cryptographic Foundation

| Component | Algorithm/Standard |
|-----------|--------------------|
| Signature | ECDSA (secp256k1) |
| Wallet Encryption | AES-256-GCM |
| Key Derivation | PBKDF2-SHA256, 600,000 iterations |
| Mnemonic | BIP-39 (24 words) |
| HD Wallet | BIP-32 |
| Hash | SHA-256 |
| P2P Tunnel | ECDH (X25519) + AES-256-GCM + S-Box SubBytes |
| S-Box Quality | Walsh-Hadamard NL + Differential Uniformity + Avalanche |
| Task Encryption | RSA-2048 (OAEP+SHA256) + AES-256-GCM + S-Box |

---

## 12. Parameter Summary

### Blockchain Parameters

| Parameter | Value |
|-----------|-------|
| Target block time | 30 seconds |
| Difficulty adjustment cycle | Every 10 blocks |
| Difficulty range | 2 ~ 32 |
| Initial difficulty | 4 |
| Max block size | 1 MB |
| Max transactions per block | 2,000 |
| Max POUW proofs per block | 50 |
| Witness timeout | 60 seconds |

### Economic Parameters

| Parameter | Value |
|-----------|-------|
| MAIN max supply | 100,000,000 |
| Sector coin max supply | 21,000,000 (per sector) |
| Halving cycle | 210,000 blocks (approx. 73 days) |
| Default exchange rate | 0.5 |
| Transaction fee | 1% (0.5% burn + 0.3% miner + 0.2% foundation) |
| Compute market fee | 90% miner + 5% platform + 5% treasury |
| Treasury block reward extraction | 3% (auto-deducted per block, transferred to MAIN_TREASURY) |
| Genesis seed fund | 1,000 MAIN |

### Governance Parameters

| Parameter | Normal Proposal | Emergency Proposal |
|-----------|----------------|-------------------|
| Proposal stake | 1,000 MAIN | 1,000 MAIN |
| Voting stake | 100 MAIN | 100 MAIN |
| Voting period | 7 days | 24 hours |
| Quorum | 10% | 20% |
| Approval threshold | 50% | 66% |
| Minimum voters | 3 | 5 |
| Execution delay | 2 days | 0 |

### POUW Scoring Parameters

| Parameter | Value |
|-----------|-------|
| Objective metrics weight | 70% |
| User feedback weight | 30% |
| Completion rate weight | 30% |
| Latency weight | 25% |
| Uptime stability weight | 25% |
| Block participation weight | 20% |
| Minimum passing score | 70% |
| Optimal latency | 100 ms |
| Max acceptable latency | 5,000 ms |

### Blind Task Engine Parameters

| Parameter | Value |
|-----------|-------|
| New miner trap ratio | 30% |
| High-trust miner trap ratio | 5% |
| Suspicious miner trap ratio | 50% |
| High trust threshold | 0.90 |
| Low trust threshold | 0.50 |
| Trap failure penalty | -20% |
| Consecutive failure penalty | -50% |
| Consecutive failure ban threshold | 3 times |

### Sector Base Rewards

| Sector | Base Reward/Block | Exchange Rate |
|--------|-------------------|---------------|
| H100 | 10.0 | 0.5 |
| RTX4090 | 5.0 | 0.5 |
| RTX3080 | 2.5 | 0.5 |
| CPU | 1.0 | 0.5 |
| GENERAL | 1.0 | 0.5 |

### S-Box PoUW Parameters

| Parameter | Value |
|-----------|-------|
| S-Box size | 256 bytes (8-bit bijective permutation) |
| Minimum nonlinearity | Dynamic (threshold × 112) |
| Target differential uniformity | ≤ 6 (optimal = 4) |
| Target avalanche effect | ≥ 0.45 (optimal = 0.50) |
| Score weight: nonlinearity | 40% (default, driftable ±3%/epoch) |
| Score weight: diff. uniformity | 30% |
| Score weight: avalanche | 30% |
| Genetic optimization generations | 5-10 |
| Population size | 20 |
| Score threshold range | 0.30 ~ 0.95 |
| Hash difficulty range | 2 ~ 32 |
| VRF selection | SHA-256 deterministic |
| Compact storage overhead | ~250 bytes/block |
| Full storage overhead | ~700 bytes/block |
| Session cipher max messages | 1,000,000 per session key |

---

## 13. System Advantages, Limitations, and Outlook

### 13.1 Core Advantages

| Advantage | Description |
|-----------|-------------|
| **Useful work, not waste** | Every block produces a cryptographically verified S-Box — which is directly used for network encryption. No energy is wasted on meaningless hash grinding. |
| **Dual-layer security** | AES-256-GCM + S-Box SubBytes substitution provides algorithm-level diversity. Even if AES were theoretically broken, the S-Box layer remains an independent barrier. |
| **Multi-sector fairness** | Hardware-separated sectors (H100, RTX4090, CPU…) prevent GPU whales from monopolizing all rewards. Each class of hardware competes within its own tier. |
| **Real compute market** | Unlike pure PoW chains, miners earn from real AI/compute tasks AND from block production simultaneously. Dual revenue streams attract more participants. |
| **Cryptographic output** | S-Boxes generated on-chain are usable in real-world cipher construction — a tangible byproduct of consensus. Researchers and security teams can leverage the S-Box Library. |
| **Forward secrecy** | P2P tunnels use ECDH ephemeral keys + S-Box stacking. Each session has a unique key derived from X25519 + HKDF, then wrapped with the current block's S-Box. Compromising one session reveals nothing about others. |
| **Deflationary economics** | 0.5% burn per transaction + halving rewards. Net deflation as adoption grows — tokenomics naturally reward long-term holders. |

### 13.2 Current Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **S-Box scoring cost** | Walsh-Hadamard Transform is O(n·2^n) per component function (~500ms per evaluation on CPU) | Only computed once per mining attempt; can be GPU-accelerated in future |
| **Chain data growth** | ~250 bytes extra per S-Box block in compact mode (~250 MB/year) | Compact hash-reference mode + pruning old S-Box entries |
| **Weight gaming risk** | If scoring weights are static, miners may optimize for a single metric | Weight drift ±3% per epoch randomizes targets |
| **Genetic algorithm variance** | S-Box quality varies between miners due to random initialization | Score threshold ensures minimum quality; low-quality S-Boxes are rejected |
| **Python performance** | Core is written in Python, which limits throughput vs. C/Rust blockchains | Critical paths (Walsh-Hadamard, nonce search) can be ported to C extensions |
| **Early-stage network** | Small validator set makes 51% attacks cheaper in absolute terms | Multi-sector architecture + dual-witness raise the barrier significantly |
| **No hardware TEE yet** | Confidential computing mode is on roadmap, not yet implemented | Container isolation + S-Box encryption currently provides Standard+Enhanced security |

### 13.3 Comparison with Existing Projects

| Feature | **POUW Chain** | **Bitcoin** | **Ethereum** | **Filecoin** | **Golem/Render** |
|---------|---------------|-------------|-------------|--------------|-----------------|
| Consensus | PoUW (compute tasks + S-Box) | PoW (SHA-256) | PoS (validators) | PoRep + PoSt (storage proofs) | No own chain (Ethereum L2) |
| Work is useful? | **Yes** — S-Box + real compute | No — pure hash grinding | N/A (staking) | Partially — stores real data | Yes — renders real tasks |
| Own blockchain? | **Yes** | Yes | Yes | Yes | No (tokens on Ethereum) |
| Dual-token model? | **Yes** (MAIN + sector coins) | No (BTC only) | No (ETH only) | Partially (FIL + deals) | No (GLM/RNDR only) |
| Hardware fair? | **Yes** (multi-sector) | No (ASIC-dominated) | No (whale-dominated) | No (storage-dominated) | Partially |
| Encryption output? | **Yes** (S-Box crypto primitives) | No | No | No | No |
| P2P data tunnels? | **Yes** (ECDH + S-Box + AES) | No | No | Yes (retrieval) | Yes (task data) |
| Compute market? | **Built-in** | No | Via contracts | Storage market | **Built-in** |
| Anti-fraud? | **Blind task engine + trap tasks** | N/A | Slashing | Fault proofs | Reputation |
| Governance | **DAO + sector voting** | BIP process | EIP + on-chain | FIP process | Off-chain |

**Key differentiators**:
1. **vs. Bitcoin**: POUW replaces wasteful hash grinding with S-Box generation + real compute, achieving useful work while maintaining PoW-level decentralization.
2. **vs. Ethereum (PoS)**: POUW doesn't require large capital lockup. Any GPU owner can mine — no 32 ETH barrier. Hardware-metered fairness.
3. **vs. Filecoin**: Filecoin proves storage; POUW proves computation. Different verticals — storage vs. compute. POUW also produces cryptographic artifacts (S-Boxes) that Filecoin does not.
4. **vs. Golem/Render**: They lack sovereign blockchains and depend on Ethereum for settlement. POUW has its own chain with built-in consensus and dual-token economics.

### 13.4 Outlook and Prospects

**Strong prospects in the following dimensions**:

1. **AI/GPU compute demand is exploding** — The global GPU cloud market is projected to grow 30%+ annually. POUW positions miners as compute providers, tapping directly into this demand.

2. **Regulatory tailwinds** — ESG pressure on energy-wasting PoW is increasing. POUW's "useful work" narrative addresses this concern head-on.

3. **Cryptographic research value** — Autonomous, blockchain-mined S-Box libraries are unprecedented. Security researchers gain a verifiable, open-source supply of tested cipher components — funded by consensus, not grants.

4. **Multi-sector scalability** — Adding new GPU generations (RTX 5090, B100) is a DAO vote, not a hard fork. The architecture scales with hardware evolution.

5. **Dual-token deflationary model** — Sector coins → burn → mint MAIN creates a natural economic flywheel. As more sectors are added, more mining occurs, but MAIN supply remains hard-capped.

**Key risks**: Network effect bootstrap (cold-start problem), Python performance ceiling at scale, regulatory uncertainty around token classification.

**Roadmap milestones**:
- TEE confidential computing (hardware-level task isolation)
- GPU-accelerated Walsh-Hadamard scoring (10x faster)
- Cross-chain bridges (POUW ↔ Ethereum/Polygon)
- S-Box marketplace (trade/license high-quality cipher components)

---

## Appendix A: Miner Modes

| Mode | Description |
|------|-------------|
| `MINING_ONLY` | Pure consensus block production, does not accept compute market tasks |
| `TASK_ONLY` | Only accepts paid compute tasks, does not participate in block production |
| `MINING_AND_TASK` | Block production + task acceptance hybrid mode (recommended) |

## Appendix B: Task Distribution Modes

| Mode | Description |
|------|-------------|
| `SINGLE` | Single miner execution (efficiency priority) |
| `DISTRIBUTED` | Multi-miner execution + cross-verification (security priority) |

---

*POUW Chain  Making Every Computation Count*
