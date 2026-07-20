# M336-143: Objective Evaluation Mutates Placement State

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `09c560f`

## Problem

`PlaceObj.obj_fn()` calls the M336 region projector before evaluating its
objective. Objective evaluation therefore changes `pos` in place. Initial
learning-rate probes, repeated gradient calls, and Nesterov line-search trials
can observe different coordinates than their caller supplied, so the objective
is not a pure function of its input.

Projection handling is also split across four paths: objective entry,
iteration entry, Nesterov's `constraint_fn`, and post-step handling. This makes
the raw optimizer proposal unobservable and can hide which coordinates require
optimizer-state cleanup.

## Additional Finding

`zero_optimizer_state()` currently clears every optimizer group tensor whose
shape matches `pos`. That is appropriate for Adam/SGD momentum, but Nesterov's
group stores position histories (`u_k`, `v_k_1`, and `v_kp1`) in same-shaped
tensors. Zeroing those coordinates corrupts the line-search state rather than
resetting momentum after projection.

## Impact

- Repeated objective or gradient evaluation can depend on hidden projection.
- Learning-rate estimation does not measure the requested proposal.
- Logs cannot prove the required objective/backward/proposal/projection chain.
- A projected Nesterov step can retain inconsistent or zeroed history.

## Remediation

1. Remove all coordinate mutation from `PlaceObj.obj_fn()`.
2. Use one composite board/footprint projector before learning-rate estimation,
   at Nesterov trial boundaries, and after Adam/SGD proposals.
3. Capture raw proposal displacement before projection and record projection
   count, mean correction, and maximum correction.
4. Clear Adam/SGD momentum for changed coordinates; synchronize Nesterov
   position histories to projected `pos` while clearing gradient histories.
5. Log first-class evidence for `PlaceObj`, `backward()`, optimizer proposal,
   hard projection, and device.

## Acceptance Criteria

- Repeated objective calls leave `pos` byte-identical and return identical
  objective values and gradients.
- Learning-rate and Nesterov trial candidates are explicitly projected before
  objective evaluation.
- Adam and Nesterov state-reset tests pass for selected coordinates.
- A native GPU smoke log proves the complete objective/backward/step/projection
  sequence and reports finite proposal/projection metrics.

## Resolution Evidence

The projector call has been removed from `PlaceObj.obj_fn()`. One composite
projector now owns board and footprint projection for learning-rate candidates,
Nesterov trials, iteration preflight, and post-Adam/SGD proposals. Position
history is synchronized, while gradient and momentum history is cleared for
projected coordinates.

Focused objective, learning-rate, Nesterov, and state-reset tests pass. The
complete reproducibility suite passes 12/12 tests, and the anchor/keep-in suite
passes 17/17 tests. Source and installed Python files have identical hashes.

The seed-1000 10-iteration GPU smoke under
`results/m336/native-cypress/n1-projection-lifecycle-smoke/` records the full
native chain for E0, E2, and E3. Each run reports 13 backward calls, 10 optimizer
steps, and 10 steps with nonzero proposals on an H100. E2 and E3 record 56 and
55 accepted projected-node events; their maximum corrections are
`0.980587` and `0.980613` Cypress units. Native HPWL and FLUTE RSMT execute after
exact validation, and the execution summary is parsed into each run result.

This milestone fixes observability and projection correctness, not placement
quality. E3 still has a zero-gradient soft keep-in term and unbounded one-time
anchor weight, which remain active under M336-002 and the N2 roadmap item.
