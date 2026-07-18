# M336-016: Two Baseline Anchors Restore Exact-Site Quality Potential

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `f49d16e`

## Problem

The continuous result in `M336-015` did not prove that a score candidate exists
on an exact physical keep-in lattice. The shared CP-SAT model was extended to
use the same explicit fixed-endpoint policy as the interval and continuous
models while leaving default runtime behavior unchanged.

## Exact-Site Evidence

With only `EMI601` and `Q601` fixed net endpoints restored to their manual
coordinates, the deterministic model searched all 61 physically feasible
same-side subgroup-region options and 1,410,293 exact `0.05 mm` sites. It
ignored capacity and collision only for this necessary-condition run.

| Quantity | Value |
| --- | ---: |
| Status | `FEASIBLE` |
| Workers / seed | `1 / 1000` |
| Solver wall time | `300.125 s` |
| Objective/native HPWL | `14114.924193 / 14114.924192` |
| Score-1 HPWL limit | `15260.369572` |
| Necessary score upper bound | `1.081151` |
| Exact keep-in containment | `100/100` |
| Collision count | `310` |

The result hash is
`38222c83fa51870ad51e310a8776ffce1b89d1a7f9b6afdaa6d4763a9bc2c483`;
the selected assignment hash is
`f70ee796209044b2ce41af53e1deea1de08cfc9e49d768fc5c00428f7ba242f8`.

## Collision Search

Fixing that assignment reduces the site count to 692,815. A deterministic
convex-collision run exhausted its budget without a solution or proof:

| Quantity | Value |
| --- | ---: |
| Status | `UNKNOWN` |
| Deterministic-time limit | `300` |
| Solver wall time | `247.545 s` |
| Branches / conflicts | `788871 / 52995` |
| Best HPWL lower bound | `14018.664317` |

This does not establish infeasibility. The collision report hash is
`e0e236618e1757a172149543b6b1c42d19d54543b6a8376a0e0081b541a6ce91`.

## Collision Evidence Correction

`M336-017` subsequently proved that the legacy `convex` model rejects a known
zero-overlap placement because the convex hulls of `MHC8601` and `MHC8602`
cover legal concavities. The `UNKNOWN` result above remains a historical run
record but provides no evidence about exact physical packing feasibility. All
collision searches for this candidate must be repeated with
`--collision-mode decomposed`.

## Scope

The override currently changes fixed net endpoints only. `context.anchor_centers`
still holds source-geometry positions, so reported anchor distances and
projected targets are not valid for the proposed production policy. The
candidate also has no native RSMT score because it is not collision-free.

## Next Steps

1. Seed collision search from an explicit site assignment rather than only the
   manual coordinate hint.
2. Try a bounded multi-worker search, then reproduce any candidate with one
   worker and the candidate hint.
3. If the fixed assignment remains unresolved, couple collision constraints to
   region selection or use exact repair followed by score-constrained search.
4. Only then integrate a consistent warm-start anchor-center policy into E1-E4.

## Acceptance Criteria

- Exact validation reports `100/100` containment and zero overlaps.
- Native HPWL and RSMT produce normalized score at least `1.0`.
- A single-worker replay reproduces the accepted placement and metrics.
- Frozen anchor coordinates, anchor targets, and reports use one position
  source rather than the current endpoint-only diagnostic override.
