# M336-173: Anchor Gradient Ratio Is Stale During Ramp

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `d69b582`

## Problem

The adaptive anchor controller reports a bounded ramped gradient ratio, but its
default five-iteration refresh interval can reuse an obsolete wirelength norm
during the most sensitive early Adam steps. In the post-fix D2 E3 run, the
wirelength gradient falls by about `15.3x` after iteration 0. The anchor ramp
starts at iteration 2 while still using the iteration-0 match, so the effective
anchor pressure is much larger than the reported ratio until iteration 5.

This breaks the intended control contract and weakens causal interpretation of
E2 versus E3. It does not invalidate exact legality: the transactional guard
still rejects every illegal candidate and restores position and optimizer
state. It does mean the E3 objective is not executing the declared
`0.01/0.02/0.03` early-ramp ratios.

## Evidence

The source is the pushed post-fix D2 artifact:

```text
results/m336/native-cypress/
  m336-172-active-budget-d2-warm-10-scale2/summary.json
SHA-256
048e13819208f650b0965ee2b77d3765cda9af2a6620cc2606344f320c255fd7
```

Anchor control refreshes at iterations 0 and 5. Collision control refreshes on
every iteration and records the current wirelength L1 norm over the same 100
active constrained nodes. Combining those independent records gives this
ratio proxy:

```text
anchor effective weight * last anchor-gradient norm
----------------------------------------------------
current collision-recorded wirelength-gradient norm
```

| Iteration | Anchor refresh | Current WL L1 | Logged ratio | Current ratio proxy |
| ---: | :---: | ---: | ---: | ---: |
| 0 | yes | `5.831255` | `0.000` | `0.000` |
| 1 | no | `0.380855` | `0.000` | `0.000` |
| 2 | no | `0.380946` | `0.010` | `0.153073` |
| 3 | no | `0.380968` | `0.020` | `0.306129` |
| 4 | no | `0.380950` | `0.030` | `0.459214` |
| 5 | yes | `0.380922` | `0.040` | `0.040000` |
| 6 | no | `0.380901` | `0.050` | `0.050003` |
| 7 | no | `0.380890` | `0.060` | `0.060005` |
| 8 | no | `0.380877` | `0.070` | `0.070008` |
| 9 | no | `0.380866` | `0.080` | `0.080012` |

The anchor norm itself changes only from `0.0380148` at iteration 0 to
`0.0379803` at iteration 5, so wirelength drift dominates the discrepancy.
At iteration 5, the raw matched weight drops from `15.3394` to `1.00295`; the
existing downward anti-windup correctly applies the lower value immediately,
but it cannot correct iterations 2-4 retroactively.

The timing aligns with the contact failure without proving causality. E2 has no
anchor objective and accepts iterations 0-4 at full LR. E3 first exceeds the
32-active contact budget at iteration 3, exactly inside the stale overweight
window, then backs off at iterations 3, 4, and 5. E3 ultimately worsens anchor
mean/p90 versus E2 by `0.010171%/0.015043%`.

## Root Cause

`PlaceObj.update_anchor_weight()` computes current gradient norms only when
`AdaptiveAnchorWeight.needs_gradient_refresh()` returns true. Between refreshes,
`AdaptiveAnchorWeight.step()` multiplies the stored match by the current ramp
but calculates `effective_ratio` from the same stored norms. The field therefore
means "ratio against the last refresh" rather than ratio against the objective
used for the current optimizer proposal.

The generic default is `anchor_weight_update_interval = 5`, and the M336 runner
does not explicitly serialize the interval, warm-up, ramp, or EMA settings into
its generated config. A short ten-step diagnostic can therefore spend three of
its eight nonzero-anchor iterations under a badly stale match while its report
appears correctly bounded.

## Impact

- The M336-172 anchor-direction result remains a valid failed outcome, but it
  cannot distinguish a well-controlled `0.1` target from stale early overweight.
- D3 remains prohibited; this issue is not authorization for another seed,
  ratio, LR, or iteration ladder.
- The contact projector and 32-active-node guard must not be weakened to absorb
  candidates produced under a misreported anchor ratio.
- Feature-off and E2 behavior are unaffected because anchor loss is disabled.

## Required Remediation

1. Make the M336 experiment config explicitly record anchor refresh interval,
   EMA decay, warm-up, and ramp parameters.
2. Refresh the M336 anchor and wirelength norms every accepted iteration during
   the short native diagnostics; keep the target ratio, warm-up, ramp, and
   weight bounds unchanged.
3. Serialize gradient age and distinguish the ratio against refreshed norms
   from a current ratio. Never label a stale estimate as current.
4. Add controller and integration tests with a sharply changing wirelength norm
   to prove that a ramp cannot amplify a stale match unnoticed.
5. Preserve objective purity, CUDA backward, Adam proposal generation, exact
   rollback, hard projection, default-off behavior, and all existing hashes
   where anchor control is disabled.

## Acceptance Criteria

- Every nonzero-anchor M336 iteration refreshes both norms and reports
  `gradient_age = 0`.
- Effective ratio equals `target_ratio * ramp` within floating-point tolerance
  when neither weight bound is active.
- A unit test reproduces the `15x` norm drop and fails under the old interval-5
  behavior but passes under the explicit M336 interval-1 contract.
- Generated configs and summary evidence include all anchor schedule values.
- Focused anchor, objective-purity, baseline/config, and reproducibility suites
  pass from the installed tree.
- A further D2 run occurs only after explicit authorization and predeclared
  scope, anchor-direction, quality, and runtime gates.
