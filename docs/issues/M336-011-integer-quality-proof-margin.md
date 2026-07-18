# M336-011: Integer Scaling Could Overstate Quality Infeasibility

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `cfbd7aa`

## Problem

The first discrete quality model rounded each component lower-left coordinate
and each pin offset separately to `1e-6` Cypress units, then constrained the
integer HPWL objective to `floor(real_limit * scale)`. The rounded objective
can be slightly larger than the corresponding real HPWL, so that threshold
could exclude a real placement exactly at the quality boundary. An infeasible
result from the over-restricted model was not a fully rigorous proof.

## Error Bound

Each pin coordinate is the sum of two rounded terms and has at most one scaled
integer unit of error. For one net, `max - min` can therefore grow by at most
two units per axis, or four units for x plus y. With non-negative integral net
weights, a conservative global allowance is:

```text
4 * sum(populated net weights)
```

M336 has total populated net weight `76`, so the model adds `304` integer units,
equivalent to `0.000304` HPWL. This is deliberately permissive: it can admit a
near-boundary false candidate, but cannot falsely reject one due to rounding.

## Resolution

`solve_discrete_placement.py` now validates non-negative integral weights,
adds the allowance to the integer quality threshold, and records both the real
limit and scaled allowance in every success or failure report. The focused
unit test covers the formula and rejects fractional weights.

The deterministic one-worker, collision-free `0.05 mm` search remains
`INFEASIBLE` with the allowance, preserving the `M336-010` conclusion.

## Acceptance Criteria

- Integer scaling has a documented conservative error bound.
- Reports expose the real threshold, integer threshold, and allowance.
- The corrected model reproduces the fixed-assignment infeasibility result.
