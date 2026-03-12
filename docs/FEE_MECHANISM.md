# Decentralized Fee Distribution Mechanism

## Design Principles

MainCoin adopts a fully decentralized fee distribution mechanism with **no traditional centralized treasury**.

All fee distributions are automatically executed according to fixed rules, transparent and traceable on-chain.

---

## Fee Structure

### Total Fee Rate: 1.0%

| Purpose | Ratio | Description |
|---------|-------|-------------|
|  **Burn** | 0.5% | Permanently removed from circulation, deflationary |
|  **Miner Incentive** | 0.3% | Distributed to block miners, incentivizing hash power |
|  **Foundation Operations** | 0.2% | Controlled by multi-sig wallet, transparent on-chain |

### Block Reward Distribution

In addition to transaction fees, each block reward has a fixed allocation:

| Purpose | Ratio | Description |
|---------|-------|-------------|
|  **Block Miner** | 97% | Actual reward received by the miner |
|  **DAO Treasury** | 3% | Automatically transferred to MAIN_TREASURY |

Example: With a base reward of 50.0, the miner receives 48.5 and the treasury receives 1.5.

---

## Comparison with Traditional Treasury

| Feature | Traditional Treasury | MainCoin Approach |
|---------|---------------------|-------------------|
| Control | Centralized entity | **No central control** |
| Fund Destination | Opaque | **Verifiable on-chain** |
| Spending Decisions | Few individuals | **Multi-sig 3/5** |
| Deflation Effect | None | **0.5% burn** |

---

## Burn Mechanism (0.5%)

```
Each transaction  0.5% sent to black hole address  Permanently destroyed
```

- Black hole address: No one owns the private key
- Burn records are verifiable on-chain
- Reduces total supply, long-term deflation

---

## Miner Incentive (0.3%)

```
Each transaction  0.3% allocated to block miner
```

- Incentivizes miners to participate in block production
- Supplements income after block reward halving
- Enhances network security

---

## Foundation Operations (0.2%)

### Multi-Sig Wallet Control

```
Foundation multi-sig address: MAIN_FOUNDATION_MULTISIG_001
Signature requirement: 3/5 multi-sig
```

### Multi-Sig Members (Initial Configuration)
1. Foundation representative (`signer_foundation`)
2. Development team representative (`signer_dev_team`)
3. Community representatives 3 (`signer_community_1/2/3`)

> Community holds 3 out of 5 signing seats (60%), ensuring majority community control. Signers can be rotated via `SIGNER_ROTATION` governance proposal voting.

### Fund Usage (Requires 3/5 Signatures)
- Protocol upgrade development
- Security vulnerability bounties
- Ecosystem incentive programs
- Infrastructure operations

### Transparency Guarantees
- All expenditures are public on-chain
- Regular fund usage reports published
- Community can audit all transactions

---

## Code Implementation

### Fee Rate Configuration

```python
# core/treasury.py
class Treasury:
    BURN_RATIO = 0.005           # 0.5% burn
    MINER_RATIO = 0.003          # 0.3% miner incentive
    FOUNDATION_RATIO = 0.002     # 0.2% foundation operations
    TOTAL_FEE_RATIO = 0.01       # 1.0% total fee rate
```

### Fee Distribution Logic

```python
def collect_from_settlement(self, order_id, total_amount):
    # Distribute by ratio
    burn_amount = total_amount * 0.005       # 0.5% burn
    miner_amount = total_amount * 0.003      # 0.3% miner
    foundation_amount = total_amount * 0.002 # 0.2% foundation
    
    # Update statistics
    self.total_burned += burn_amount
    self.total_miner_rewards += miner_amount
    self.foundation_balance += foundation_amount
```

---

## Governance-Adjustable Parameters

The following parameters can be modified through on-chain governance voting:

| Parameter | Current Value | Adjustment Range | Voting Requirement |
|-----------|---------------|------------------|-------------------|
| Total Fee Rate | 1.0% | 0.5% - 2.0% | Supermajority (75%) |
| Burn Ratio | 0.5% | 0% - 1.0% | Supermajority (75%) |
| Miner Ratio | 0.3% | 0.1% - 0.5% | Simple Majority (51%) |
| Foundation Ratio | 0.2% | 0.1% - 0.5% | Supermajority (75%) |

---

## Fee Application Scenarios

| Scenario | Applicable Fee Rate |
|----------|-------------------|
| Compute Trade Settlement | 1.0% |
| MAIN Token Transfer | 1.0% |
| Sector Coin Exchange | 0.1% |
| Cross-Sector Transaction | 1.0% + 10% premium |

---

## Why This Design?

### 1. Decentralization First
- No single entity can control funds independently
- Burned tokens cannot be recovered by anyone

### 2. Economic Sustainability
- Deflation mechanism protects token value
- Miner incentives ensure security
- Foundation ensures development

### 3. Full Transparency
- All fee distributions are verifiable on-chain
- Anyone can verify distribution correctness
- Foundation spending requires multi-sig + public disclosure

---

## Comparison with Other Projects

| Project | Fee Rate | Burn | Governance |
|---------|----------|------|-----------|
| Bitcoin | Miner fee |  |  |
| Ethereum | EIP-1559 |  Partial |  |
| BNB | 0.1% |  Quarterly | Centralized |
| **MainCoin** | **1.0%** | ** 0.5%** | **Multi-sig + On-chain** |

---

## Changelog

- **2026-03-08**: Added block reward 3% treasury allocation details
  - 3% of each block reward is automatically transferred to the DAO treasury (MAIN_TREASURY)
  - 97% goes to the block miner
  - This allocation is automatically executed by the consensus layer and cannot be modified
- **2026-01-28**: Reduced from 2% treasury to 1% decentralized distribution
  - Removed traditional treasury concept
  - Implemented 0.5% burn + 0.3% miner + 0.2% foundation
  - Foundation switched to multi-sig wallet control
