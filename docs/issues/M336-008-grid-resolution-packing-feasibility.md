# M336-008: Constraint Grid Changes Packing Feasibility

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `cfbd7aa`

## Problem

The finalizer unconditionally excluded
`page_86_U8601__bottom -> bottom_2` after a `0.1 mm` joint-packing failure.
That conclusion was incorrectly reused for finer grids.

## Evidence

`bottom_2` receives 14 movable rectangular footprints around frozen U8601.
An optional OR-Tools `NoOverlap2D` diagnostic used integer coordinates and the
same candidate sites as the runtime domains.

| Grid | Candidate sites | CP-SAT result | Branches | Time |
| --- | ---: | --- | ---: | ---: |
| `0.10 mm` | `2,767` | `INFEASIBLE` | `98,825` | `1.353 s` |
| `0.05 mm` | `10,982` | Feasible | `60,837` | `0.516 s` |

At `0.05 mm`, the normal 61-option assignment MILP can select this candidate
and reaches relaxed HPWL `14675.1473`, versus manual `14627.8477`. Its score
upper bound is `1.039878`, but this is not proof of attainable quality. The
shared-coordinate diagnostic in `M336-010` rejects that fixed assignment.

OR-Tools `9.15.6755` was installed only under `/tmp/m336-ortools`; it is an
optional audit dependency, not a Cypress runtime dependency.

## Remediation

The exclusion now applies only to the directly proven `0.1 mm` grid, with a
regression test covering `0.05/0.10/0.20 mm`. It is not extrapolated to other
lattices whose origin or candidate set can differ. Runtime rectangle checks use
vectorized bounds, and expensive search remains bounded. Any permanent grid
change still requires a complete exact-legal, native-scored placement.

## Acceptance Criteria

- Grid-dependent exclusions have regression coverage.
- Candidate feasibility is produced from the same domains used at runtime.
- A complete placement has zero containment and overlap errors.
- Native HPWL/RSMT normalized score is at least `1.0`.
