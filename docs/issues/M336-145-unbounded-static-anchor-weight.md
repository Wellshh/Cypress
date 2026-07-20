# M336-145: Anchor Weight Is Global, Static, and Unbounded

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `f307b4c`

## Problem

The anchor objective averages every constrained component globally, so large
side-specific groups dominate smaller groups. Its weight is matched to the
wirelength gradient only once during objective construction and has no warm-up,
schedule, bound, or response to later density/projection changes. Historical
M336 runs produced lambda values from roughly `120,050` to `960,405` with
negligible anchor-distance improvement. The loss is also divided by the board
diagonal before a quadratic Smooth-L1 reduction, shrinking its gradient by the
diagonal squared and making a large numeric lambda necessary even for a modest
gradient ratio.

## Remediation

Average member loss within each side-specific subgroup and then average the
subgroups. Exclude anchor, fixed, and frozen coordinates. At explicit accepted
iteration boundaries, periodically match a target anchor/wirelength gradient
ratio, smooth the bounded target with an EMA, and apply a warm-up/ramp. Keep the
weight fixed during objective and line-search calls. Restore one factor of the
board diagonal after reduction so the loss remains board-normalized without
requiring a six-digit lambda solely because of its units.

## Acceptance Criteria

- Unequal subgroup sizes receive equal aggregate weight.
- Frozen, anchor, and fixed coordinates are absent from loss and norm support.
- Effective lambda is finite, bounded, ramped, and updated only at explicit
  iteration boundaries.
- Every update records raw gradient norms, raw/bounded/effective lambda, loss,
  and achieved gradient ratio.
- Target-ratio values `0.05`, `0.10`, `0.25`, and `0.50` run under one native
  E3 contract without falling back to exact-site output.

## Resolution Evidence

`AnchorKeepInLoss` now averages members within each side-specific subgroup and
then averages subgroups. Context construction excludes fixed and frozen nodes,
and gradient matching selects only the resulting coordinate support. The loss
restores one board-diagonal scale factor after normalized Smooth-L1 reduction,
so the adaptive controller no longer needs a six-digit lambda solely because
of units.

`AdaptiveAnchorWeight` refreshes raw wirelength/anchor gradient norms every five
accepted iterations, bounds the target at `5000`, applies an EMA and
warm-up/ramp, and serializes every update. Objective calls consume a fixed
tensor weight and do
not update controller state or placement coordinates. Focused source/install
tests cover subgroup balance, weighted normalization, fixed/frozen exclusion,
finite bounds, EMA/ramp behavior, and explicit update purity.

The final 10-iteration seed-1000 H100 sweep is under
`results/m336/native-cypress/n2-anchor-final-ratio-sweep-grid005/`. All four
runs use one input hash set, execute 13 backward calls and 10 Adam steps, and
remain 100/100 contained with zero keep-in violations:

| Target ratio | Effective ratio | Lambda | HPWL | Anchor mean mm |
|---:|---:|---:|---:|---:|
| 0.05 | 0.010408 | 26.857 | 24269.597656 | 9.133008 |
| 0.10 | 0.020816 | 53.714 | 24269.593750 | 9.132910 |
| 0.25 | 0.052040 | 134.287 | 24269.578125 | 9.132710 |
| 0.50 | 0.104080 | 268.579 | 24269.562500 | 9.132509 |

M336-146 removes the former E2/E3 margin confound. In the corrected 50-step
comparison under
`results/m336/native-cypress/n2-anchor-final-isolated-diagnostic-50/`,
ratio `0.10` improves E3 mean anchor distance by only `0.0934%` and p90 by
`0.00288%` versus E2. A ratio-`0.50` upper diagnostic under
`results/m336/native-cypress/n2-anchor-final-diagnostic-50-ratio05/` improves
them by only `0.1604%` and `0.0124%`. The controller is now bounded, adaptive,
observable, and directionally effective, but the `25%/15%` quality gate remains
unmet and
must not be claimed. Keep `0.10` as the conservative default while irregular
density is corrected.
