# M336-024: Packing Feasibility Cannot Be Isolated from HPWL

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `dff48bb`

## Problem

`--feasibility-only` still constructed all net-span variables and imposed an
HPWL limit. Even a loose score threshold coupled TOP and BOTTOM coordinates,
so a failed run could not distinguish geometric packing cost from unnecessary
wirelength model cost.

## Correction

`--packing-only --feasibility-only` now omits HPWL variables, objective, and
score constraint. It remains diagnostic: the solver computes actual HPWL and
score only after finding a placement, and reports:

- `objective_mode: packing_only`;
- `hpwl_gate_enabled: false`; and
- null integer and floating HPWL limits.

The final score check is skipped only in this explicit mode. Calling
`--packing-only` without `--feasibility-only` fails argument validation.

## Contract Evidence

The known legal grid01 artifact has score `0.652162`, below a requested
minimum of 1.0. Its fixed packing-only replay returned `OPTIMAL`, zero branches,
100/100 containment, and zero overlap. The ordinary control with the same
minimum score returned `INFEASIBLE`, proving the production gate remains active.

## A/B Evidence

The restored-anchor full fixed grid01 lattice contains 215,749 sites and 3,500
convex-part pair constraints:

| Model | Status | Solver seconds | Branches | Conflicts | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| HPWL gate, score 0.1 | `UNKNOWN` | 300.468 | 3,029,708 | 522,045 | 4,461,588 KiB |
| packing only | `UNKNOWN` | 300.707 | 2,864,555 | 599,503 | 4,625,328 KiB |

Removing HPWL does not produce a legal candidate or materially reduce the
full-domain cost. The dominant unresolved problem is therefore exact packing,
not the loose HPWL gate.

## Residual Risk

A packing-only placement is never evidence for score acceptance. Multi-worker
discovery also remains exploratory until one-worker fixed replay reproduces
the assignment and sites. Restored-anchor feasibility remains open under
`M336-022`.

## Acceptance Criteria

- Packing-only mode contains no HPWL variables, objective, or gate.
- Reports make the missing score contract machine-readable.
- Actual post-solve metrics and exact legality are still emitted.
- Ordinary mode continues to reject a below-threshold fixed placement.
