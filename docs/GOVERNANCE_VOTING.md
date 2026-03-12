# Contribution-Weighted Governance Voting Mechanism

> This platform adopts a weighted governance voting mechanism based on real computing power and usage contributions. Voting is only used for system-level rule adjustments and does not participate in specific task scheduling. All voting results take effect with a delay through on-chain rules, ensuring a balance between decentralization, security, and system stability.

## Core Principles

### Voting Purpose
-  **System-Level Toggle**: Voting only affects the rules themselves
-  **No Scheduling Involvement**: Not used for specific task allocation

### Scope

| Can Be Voted On  | Cannot Be Voted On  |
|--------------------|----------------------|
| Circuit breaker parameter adjustment | Individual task allocation |
| Compute sector enable/disable | Forced order snatching |
| Protocol fee ratio adjustment | Instant penalties |
| Foundation fund direction | Temporary scheduling strategies |
| Security policy updates | |

## Voting Rights Design

### Voting Roles

| Role | Voting Rights | Description |
|------|---------------|-------------|
| Regular User |  | Rents compute power with MAIN |
| Miner |  | Provides GPU compute power |
| Foundation |  | Execute only, no voting |

### Governance Weight Calculation

```
Governance Weight = Compute Contribution Weight + Usage Contribution Weight + Staking Weight
```

#### 1 Compute Contribution Weight (Miners)
- Based on valid compute power successfully executed in the past 90 days
- Unit: GPUhours
- Decay mechanism: half-life of 90 days

```python
Power_miner = Σ (GPU_hours  decay(t))
```

#### 2 Usage Contribution Weight (Users)
- Based on actual MAIN paid
- Only counts "successfully completed tasks"
- Anti-abuse: failed/cancelled tasks are excluded

```python
Power_user = Σ (MAIN_paid  decay(t))
```

#### 3 Staking Weight
- Users or miners voluntarily lock MAIN
- Longer lock period = higher weight

```python
Power_stake = locked_MAIN  lock_factor
```

| Lock Period | Weight Factor |
|-------------|---------------|
| 30 days | 1.0x |
| 90 days | 1.5x |
| 180 days | 2.0x |
| 365 days | 3.0x |

### Weight Cap (Anti-Whale)

```
Single address governance weight  5% of total network
Excess is truncated and not counted
```

Prevents:
- Large miners monopolizing governance
- Capital controlling protocol rules

## Proposal Mechanism

### Proposal Types

| Type | Example | Risk Level | Deposit |
|------|---------|------------|---------|
| Parameter | Fee rates, thresholds |  Low | 100 MAIN |
| Feature Toggle | Circuit breaker on/off |  Medium | 500 MAIN |
| Structural | New sectors/new rules |  High | 2000 MAIN |

### Deposit Rules

-  Passed  Deposit refunded
-  Rejected  50% of deposit burned
-  Malicious proposal  Fully burned

### Proposal Structure

```json
{
  "proposal_id": "P-2026-001",
  "proposal_type": "param_change",
  "target_param": "CIRCUIT_BREAKER_THRESHOLD",
  "old_value": 0.85,
  "new_value": 0.92,
  "risk_level": "medium",
  "voting_period": "7_days",
  "quorum": "15%"
}
```

## Voting Process

### Phase 1: Proposal Submission (T0)
- Proposal enters `PENDING` state
- **Cooling Period**: 24 hours
- Anyone can review & raise objections

### Phase 2: Formal Voting (T1~T2)

| Option | Meaning |
|--------|---------|
|  Support | Approve the proposal |
|  Oppose | Reject the proposal |
|  Abstain | Counted for participation rate, not approval rate |

### Passing Conditions (Dual Threshold)

**Both** must be met:

| Threshold | Condition |
|-----------|-----------|
| Participation Rate |  15% of total network weight |
| Approval Rate (Normal) |  66% |
| Approval Rate (Structural) |  75% |

### Phase 3: Delayed Execution (Timelock)
- After passing, enters `QUEUED` state
- **48-hour delay**
- Purpose: discover vulnerabilities, emergency consensus rollback

## Execution Mechanism

> Key Design: Vote  Direct System Modification

| Change Type | Execution Method |
|-------------|-----------------|
| Parameter | On-chain rules auto-apply |
| Feature Toggle | Protocol state bit |
| Structural | Requires new protocol version |

**Foundation Role**:
- Can only execute approved results
- No veto power
- All operations are auditable

## Relationship with Circuit Breaker

###  Correct Design

Voting decides:
- Whether to enable circuit breaker
- Circuit breaker threshold
- Recovery strategy

Actual triggering is **automatically executed by on-chain rules**

###  Wrong Design (Never Do This)

- Voting to decide "should we trigger circuit breaker now"
- Manual intervention in scheduling

## Security Design

### Anti-Governance Attack
- Weight cap at 5%
- Time-based weight decay
- Deposit system

### Anti-Sybil Attack
- Weight based on historical contributions
- New addresses have no governance rights

### Anti-Short-Term Manipulation
- Voting snapshot
- Weights non-transferable during voting period

## RPC Interfaces

### Proposal-Related

| Method | Permission | Description |
|--------|-----------|-------------|
| `contrib_createProposal` | USER | Create a proposal |
| `contrib_getProposals` | PUBLIC | Get proposal list |
| `contrib_getProposal` | PUBLIC | Get proposal details |
| `contrib_finalizeProposal` | PUBLIC | Finalize a proposal |
| `contrib_executeProposal` | PUBLIC | Execute a proposal |

### Voting-Related

| Method | Permission | Description |
|--------|-----------|-------------|
| `contrib_vote` | USER | Cast a vote |
| `contrib_getVoterPower` | PUBLIC | Get voting power |
| `contrib_simulateVote` | PUBLIC | Simulate vote impact |

### Staking-Related

| Method | Permission | Description |
|--------|-----------|-------------|
| `contrib_stake` | USER | Lock tokens for staking |
| `contrib_unstake` | USER | Unlock staked tokens |

### Statistics

| Method | Permission | Description |
|--------|-----------|-------------|
| `contrib_getStats` | PUBLIC | Get governance statistics |

## Code Examples

### Create a Proposal

```python
from core.contribution_governance import (
    ContributionGovernance,
    ProposalType,
)

gov = ContributionGovernance()

proposal, msg = gov.create_proposal(
    proposer="user_address",
    proposal_type=ProposalType.CIRCUIT_BREAKER,
    title="Adjust circuit breaker threshold from 85% to 92%",
    description="Current threshold is too sensitive",
    target_param="CIRCUIT_BREAKER_THRESHOLD",
    old_value=0.85,
    new_value=0.92,
    current_block=1000
)
```

### Vote

```python
from core.contribution_governance import VoteChoice

ok, msg = gov.vote(
    proposal_id=proposal.proposal_id,
    voter="voter_address",
    choice=VoteChoice.SUPPORT,
    current_block=1100
)
```

### Simulate Vote Impact

```python
impact = gov.simulate_vote_impact(
    proposal_id=proposal.proposal_id,
    voter="new_voter",
    choice=VoteChoice.OPPOSE
)

print(f"Would pass before voting: {impact['before']['would_pass']}")
print(f"Would pass after voting: {impact['after']['would_pass']}")
```

## Configuration Parameters

```python
class GovernanceConfig:
    MAX_WEIGHT_PERCENT = 5.0      # Max 5% per address
    DECAY_HALF_LIFE_DAYS = 90     # Half-life decay of 90 days
    
    BOND_PARAM = 100              # Parameter proposal deposit
    BOND_FEATURE = 500            # Feature toggle deposit
    BOND_STRUCTURAL = 2000        # Structural proposal deposit
    
    COOLDOWN_HOURS = 24           # Cooling period
    VOTING_PERIOD_DAYS = 7        # Voting period
    TIMELOCK_HOURS = 48           # Execution delay
    
    QUORUM_PERCENT = 15.0         # Participation threshold
    APPROVAL_THRESHOLD = 66.0     # Normal approval rate
    STRUCTURAL_THRESHOLD = 75.0   # Structural approval rate
    
    LOCK_FACTORS = {
        30: 1.0,
        90: 1.5,
        180: 2.0,
        365: 3.0,
    }
```

## File Structure

```
core/
 contribution_governance.py   # Contribution-weighted governance module
 governance_enhanced.py       # Enhanced governance module (staking voting + timelock)
 dao_treasury.py              # DAO treasury governance
```

## Testing

Run governance voting tests:

```bash
python test_governance_voting.py
```

Run all tests:

```bash
python test_all.py
```
