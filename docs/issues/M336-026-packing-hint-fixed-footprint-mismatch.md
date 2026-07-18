# M336-026: Packing Hints Still Use Fixed Bounding Boxes

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `89b29ef`

## Problem

M336-017 changed CP collision constraints and exact validation to use transformed
manual footprints for fixed components, but `_build_packing_hint` retained
PlaceDB rectangles. Concave fixed footprints could therefore create the same
false collisions in the deterministic hint path that had already invalidated
the legacy convex CP model.

The solver script also duplicated only the greedy and forward-check portions
of the repository packing algorithm. It omitted deterministic min-conflicts
and bounded tail search, so behavior diverged from `anchor_keepin._pack_region`.

## Correction

Fixed obstacles in packing hints now use `_fixed_footprint_local(...,
"decomposed")`, translated by the same lower-left/center contract as CP-SAT.
The duplicated strategy loop was removed and the hint path now calls the shared
`_pack_region` implementation. Its `InfeasibleDomainError` is preserved as a
scoped diagnostic failure rather than silently changing geometry.

## Regression Evidence

With runtime anchors, the corrected grid01 hint used deterministic greedy
packing for all four side/region bins and produced:

- 100/100 exact containment and zero overlap;
- HPWL `23336.872601` and necessary score upper bound `0.653917`, improving
  over the prior known-legal HPWL `23399.649009`;
- single-worker CP fixed replay `OPTIMAL` in `0.267033 s`, zero branches; and
- matching hint/replay placement SHA-256
  `fbbbf6b3e3f81e84e578d16b3e01ba78f28ed67ae241065ac44146e20ba50cfe`.

All baseline, anchor/keep-in, and reproducibility suites passed 26/26, 15/15,
and 8/8 respectively.

## Restored-Anchor Evidence

The old simplified path exhausted TOP packing after `84.83 s`. The corrected
shared strategy progressed into min-conflicts but did not finish within a
300.02-second external bound. This is neither a legal candidate nor an
infeasibility proof; it shows that exact geometry correction alone does not
resolve restored `Q601` packing.

## Residual Risk

The shared min-conflicts loop has fixed restart/step counts and no caller-level
time budget or progress artifact. Exact polygon scoring is single-threaded and
expensive for TOP. M336-022 remains open until a global legal, score-gated
placement is replayed.

## Acceptance Criteria

- Fixed obstacles match CP and exact-validator footprint geometry.
- Packing hints use one shared deterministic strategy implementation.
- A known-legal scenario remains globally legal after fixed replay.
- Restored-anchor timeout is reported as inconclusive, not infeasible.
