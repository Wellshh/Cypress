# M336-162: Feature-Off Nesterov State Is Cleared After Board Projection

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `002977b`

## Problem

The explicit projection lifecycle applies M336-specific optimizer-state cleanup
to every placement, including feature-off Nesterov runs. It also projects the
Nesterov bootstrap state before its first gradient evaluation. Legacy Cypress
only used `move_boundary_op` for accepted Nesterov candidates and did not reset
Nesterov history after board clamping.

## Evidence

After fixing M336-161, a deterministic CPU comparison matches `f0e4cb9` exactly
through iteration 7. The first current step reports four board corrections with
maximum displacement `3.4e-10`; generic state cleanup then modifies Nesterov's
internal tensors. From iteration 8 onward the current optimizer proposes zero
coordinate changes and remains at HPWL `2262.637`, overflow `0.4315246`, and
objective `237.6783`. The reference continues optimizing and reaches HPWL
`352.4681`, overflow `0.2942742`, and objective `31.28787` at iteration 99.

This is not an anchor/keep-in effect: all M336 flags are false and no constraint
context exists.

## Remediation

Preserve the original Nesterov lifecycle when no anchor/keep-in context exists.
Keep the same board constraint function used by legacy Cypress, but enable the
new bootstrap projection and post-projection state synchronization only for an
active composite M336 context. Continue collecting proposal/projection evidence
without mutating feature-off optimizer state.

## Acceptance Criteria

- Feature-off Nesterov does not clear or synchronize optimizer history.
- Feature-off Nesterov retains the legacy bootstrap evaluation order.
- The deterministic 100-step current trajectory and placement bytes match
  `f0e4cb9` after runtime fields are excluded.
- Active M336 Nesterov and Adam tests still prove explicit projection and state
  cleanup semantics.

## Resolution

`NesterovAcceleratedGradientOptimizer` now exposes a default-false
`project_initial_state` switch. `NonLinearPlace` enables it only when an active
anchor/keep-in context requires the composite constraint lifecycle. Generic
feature-off runs continue to project accepted Nesterov candidates but do not
alter bootstrap evaluation order or clear optimizer history after board-only
projection.

The reproducibility suite passes 15/15 tests, including both legacy and active
bootstrap contracts. A repeated 100-step CPU comparison has no metric-line
diff after timing fields are removed. Both runs end at objective `31.2878666`,
HPWL `352.4681`, overflow `0.29427424`, and max density `2.3875594`; both
serialized placements have SHA-256
`eb30233fc80f1a4386fc921b0a6ba746749719c5b257a14aa5b9683ab2186102`.
The benchmark's pre-existing high-overflow failure is unchanged.
