# POUW-Chain Tech Spec v2.0 Implementation Notes

This document maps Tech Spec v2.0 requirements to current runnable implementation.

## Scope

Primary implementation is integrated into `core/compute_scheduler.py` with backward compatibility defaults.

## Layer Mapping

1. Task Layer
- Extended `ComputeTask` fields:
  - `payload`
  - `security_tier`
  - `verification_mode`
  - `random_seed`
  - `compute_required`
  - `memory_required`
  - `deadline`
  - `execution_results`
- Added tier profile and guardrail enforcement:
  - high-value task minimum tier
  - low-reputation user minimum tier
  - security tier normalization to `[0,3]`

2. Scheduling Layer
- Extended `MinerNode` fields for heterogeneous scheduling:
  - `bandwidth`, `latency`, `stake`
  - beta reputation state: `rep_alpha`, `rep_beta`
- Added `match_score` weighting:
  - compute capability
  - memory capability
  - reliability (`mean - 1.5 * uncertainty`)
  - latency penalty
- Added public runtime APIs:
  - `monitor_execution(task_id)`
  - `reassign(task_id)`

3. Execution Layer
- Added `ExecutionResult` dataclass:
  - `task_id`, `node_id`, `output`, `timestamp`, `partial_hash`
- Result metadata now persisted per miner in `task.execution_results`.

4. Verification Layer
- Verification modes:
  - `none`
  - `consensus`
  - `sampling`
- Consensus verification uses discrete consistency variance.
- Sampling verification uses seeded random index generation.
- Dispute resolution fallback:
  - select extra node by score
  - deterministic arbitration tie-break path
  - unresolved disputes trigger reschedule

5. Reputation Layer
- Added beta reputation model `Reputation(alpha, beta)`.
- Added update and decay mechanisms:
  - success/failure update
  - periodic decay in watchdog loop
- Added node-level derived scores:
  - `reputation_mean`
  - `reputation_uncertainty`
  - `reputation_score`

6. Incentive Layer
- Added fee multiplier API:
  - `compute_fee(base_fee, tier)`
- Settlement supports v2 reward policy in redundancy scenario:
  - `k=1`: single executor full distributable reward
  - `k>=2`: executor/verifier split logic via scheme metadata
- Added slash API:
  - `slash(miner_id, amount)`
- Verification failure can trigger slash (default ratio 30% of stake).

## Security Principles Applied

- High-value tasks cannot stay in non-verified mode.
- Verification participants are reward-addressable through settlement scheme metadata.
- Sampling randomness uses unpredictable seed initialization when absent.
- Reputation has mandatory decay path.
- Failed verification has direct economic penalty path.

## Attack Model Mapping

| Attack | Defense in Current Code |
|---|---|
| Sybil Attack | stake field + slash path + weighted reliability scheduling |
| Lazy Compute | redundancy + verification modes + dispute fallback |
| Fake Output | consensus/sampling verification + dispute resolution |
| Replay Attack | per-task random seed + task hash integrity checks |
| Collusion | randomized sampling indices and non-deterministic seed initialization |

## Compatibility Notes

- Existing task creation and legacy mode behavior remain available.
- Blind mode remains single-node by default for tier 0.
- For higher tiers in blind scheduler mode, system falls back to legacy multi-node verification path.

## Operational Validation Performed

- `py -3 -m py_compile core/compute_scheduler.py` passed.
- `py -3 -m core.compute_scheduler` runnable as package module.
