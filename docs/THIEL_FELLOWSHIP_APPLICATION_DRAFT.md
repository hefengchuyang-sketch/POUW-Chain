# Thiel Fellowship Application Draft (Founder Version)

## 1) Core Statement
I am building POUW-Chain to make outsourced compute trustworthy for small teams.

Today, people can buy compute easily, but they cannot easily verify whether the work was actually done well, on time, and by the agreed party. I want to make delivery proof and settlement rules part of the protocol itself.

## 2) Why This Problem Matters
In practice, buying external compute still feels like buying a black box.

Three things keep breaking:
- You receive a result, but you cannot confidently verify execution quality.
- When work fails, responsibility is unclear and resolution is slow.
- Smaller teams have no leverage and absorb most of the risk.

This is not only a pricing problem. It is a trust and accountability problem.

## 3) What I Actually Built
I am not applying with a concept. I have a working system and a repeatable demo flow.

Current implementation includes:
- Public open-source codebase on GitHub with active iteration history.
- Buyer and miner as separate identities in one end-to-end flow.
- Task lifecycle from create -> accept -> execute -> return output -> settle.
- Owner-only output access so sensitive results are visible only to the requesting user.
- Runtime output returned through result.json with structured result fields.
- File upload/download path that handles larger task artifacts.
- Dispute and compensation primitives to handle failed delivery.

The repository is publicly accessible, which allows reviewers to inspect implementation details, commit cadence, and architecture decisions directly.

Open-source evidence snapshot (as of 2026-04-08):
- Repository: https://github.com/hefengchuyang-sketch/POUW-Chain
- Total commits: 21
- Commits in the last 90 days: 21
- Core Python modules: 78 files under core/
- Test assets: 48 files under tests/

I built this under tight resource limits, which forced me to prioritize what actually breaks in real usage.

## 4) What I Believe (Contrarian View)
Most marketplaces compete on matching speed and lower price.

I think long-term defensibility comes from delivery reliability:
- verifiable execution evidence,
- predictable dispute handling,
- and transparent settlement that users can audit.

If these are weak, scale makes the system worse, not better.

## 5) Why Fellowship Support Is Critical Now
My bottleneck is not building speed. It is validation at realistic scale.

Right now I am constrained by:
- sustained GPU access for repeated reliability testing,
- access to real pilot workloads,
- and runway for instrumentation, iteration, and failure analysis.

Fellowship support would let me turn engineering momentum into evidence that outside users can trust.

## 6) 12-Month Execution Plan
### Months 0-3: Reliability First
- Harden the runtime evidence pipeline.
- Run controlled workload suites across mixed environments.
- Publish baseline metrics: completion rate, latency, failure classes.

### Months 4-8: Pilot With Real Users
- Bring in 2-3 pilot teams.
- Run recurring workloads through the full protocol flow.
- Track fulfillment, disputes, and resolution speed per pilot.

### Months 9-12: Convert Usage Into Durable Signal
- Turn pilot usage into repeat behavior (paid or committed).
- Tighten operational controls and economic guardrails.
- Produce a public validation report with honest failure data, not only success data.

## 7) How I Will Measure Progress
Primary:
- Active pilot teams running real workloads.
- Task completion rate and p95 completion time.
- Dispute rate and median resolution time.
- Repeat usage ratio.

Secondary:
- Correctness of owner-only output access.
- Runtime evidence integrity pass rate.
- Settlement reconciliation accuracy.

## 8) Why Me
I work as a builder-operator, not only as a planner.

I write protocol logic, ship product behavior, and debug the entire loop myself. When something breaks in demo or user flow, I patch quickly and re-test immediately. My advantage is execution continuity under constraints.

## 9) Long-Term Direction
POUW-Chain should become infrastructure for trustworthy external compute, especially for teams that cannot pre-buy dedicated hardware.

I do not want to build another marketplace interface. I want to build the trust and settlement layer that those marketplaces are missing.

## 10) 60-Second Interview Version
I am building POUW-Chain, a protocol for verifiable outsourced compute.

The current market has a trust gap: you can buy compute, but you cannot reliably verify delivery quality or resolve failures quickly. I already built an end-to-end working flow with separate buyer/miner identities, owner-only output visibility, runtime result return, and settlement primitives.

The next milestone is external validation with real workloads. Fellowship support would let me run pilots, collect reliability and dispute metrics, and prove whether this can become durable infrastructure.

My thesis is simple: in compute markets, trustable delivery matters more than cheaper matching.

---

## Suggested Attachments
- 2-4 minute uninterrupted demo video.
- Public GitHub repository link (plus one short note on current modules and roadmap).
- One-page open-source evidence sheet (commit timeline + module/test coverage snapshot).
- One-page architecture snapshot.
- Weekly validation scoreboard.
- Failure log with fixes (shows engineering maturity).

## Final Editing Notes
- Replace placeholder metrics with real numbers before submission.
- Keep claims factual and testable.
- In interviews, use short and direct sentences.
