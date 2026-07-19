# M336-085: Capacity Preflight Excluded a Known-Legal Incumbent

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `6dcd67a`

## Problem

The first structured K128 subgroup search returned `INFEASIBLE` in presolve,
although its candidate domain explicitly retained the current exact-legal
placement. The failure was not geometric. The current assignment was created
by a shared-coordinate diagnostic with `ignore_area_capacity=True`, which moved
`page_86_ANT8604__bottom` into `bottom_2`. Its controlled area increased the
region load from `3.2100` to `4.3170 mm2`, above the configured 50% preflight
capacity `3.548999 mm2` but still exactly packable.

The selected assignment also copied stale `capacity_diagnostics` from its
template, so it continued reporting the old `3.2100` load after changing
regions. The failed scoped result SHA-256 is
`ac0273385e406398ebf86c4550c2867eae52b63ca4b763f2e713fdf0d9a4029c`.
This is evidence of a model-contract contradiction, not assignment
infeasibility.

## Resolution

When a complete structured hint has already passed exact containment and
zero-overlap validation, assignment capacity now uses a no-regression floor:

```text
effective capacity = max(configured capacity, exact-legal hint occupancy)
```

An illegal or incomplete hint receives no floor. The result records configured
units, hint occupancy, effective units, and every override. New assignments
therefore cannot worsen current regional load while the known legal incumbent
remains representable. Exact keep-in and collision constraints are unchanged.

Assignment output now records model group areas and recomputes all regional
capacity diagnostics after selected regions change.

## Evidence

The same `page_3_J301__bottom` K128 search now reaches actual search and returns
`FEASIBLE` at the source placement after 60 deterministic seconds. The only
override is `bottom_2`: configured `3548999`, hinted/effective `4317002` units.
The regenerated assignment correctly reports `4.317000 mm2` and 60.82% of
free-after-anchor area. Exact validation remains 100/100 contained with zero
overlaps; HPWL remains `15811.06557381333`.

Result SHA-256 is
`d04eb6bbda56dcdf73656d1ec0dbd1cc82b0d194f52b674c2e11190ab2dbc758`;
assignment SHA-256 is
`c0f7fe96b5189708d20e3f4e4755c47b1e4f7d7293187e01d812afdac61ba210`.

## Acceptance Impact

Capacity remains a conservative search-pressure constraint, but it can no
longer manufacture infeasibility against a certified exact placement. The
smoke search did not improve quality; normalized score remains
`0.9651702157924906`.
