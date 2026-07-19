# M336-089: Score-Gated Coupled K256 Domains Are Infeasible

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `174e8e2`

## Problem

The optimization bounds in M336-088 fell below the score-1 HPWL threshold but
did not produce an improved incumbent. A minimization lower bound below a
threshold only prevents an infeasibility claim; it does not establish that a
threshold-satisfying placement exists.

## Method

The same four coupled K256 assignment domains were rebuilt in first-feasible
mode with `--minimum-score 1 --feasibility-only`. The score gate imposed
integer HPWL limit `15260369875`, derived from necessary real-valued limit
`15260.369571786632` plus the conservative `0.000304` HPWL rounding allowance.
The requested incumbent ceiling `15811065584` was present but looser, so the
score-derived limit controlled every model.

All other conditions matched M336-088: OR-Tools `9.15.6755`, 0.1 mm lattice,
exact decomposed footprints, K256 current/quality neighborhoods, exact-legal
structured hint, no-regression capacity floor, manual `EMI601` endpoint, one
worker, seed 1000, and maximum 120 deterministic seconds.

## Evidence

| Released subgroups | Candidates | Collision constraints | Status | Branches | Conflicts | Wall seconds | Result SHA-256 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `ANT8604 + U8601` | 32,581 | 3,907 | `INFEASIBLE` | 378,004 | 74,348 | 59.042245 | `772de7371cbf6e3d320a9f32940087aa40e2c8044d278d216559ecb8f087275e` |
| `MIC401 + J601` | 33,093 | 3,699 | `INFEASIBLE` | 255,789 | 27,386 | 33.594078 | `5970a1407b7eee1b134bc4e5b93cc57978bbabf370d757964e452843ae34b09e` |
| `J701 + J702` | 34,629 | 4,008 | `INFEASIBLE` | 255,098 | 26,217 | 33.070246 | `ef14562325a0b865b9db388691cd93e6df54098e3874fe0d4bfbca0f9da0677a` |
| all five page-86 groups | 37,366 | 9,316 | `INFEASIBLE` | 372,620 | 44,657 | 58.432671 | `e4775510e3698380a679510e4155b9ba1b47f88b3923846fdfcfaf05ee5281c7` |

The script writes each structured failure report before returning a nonzero
process code. Every report records `objective_mode: first_feasible`,
`hpwl_gate_enabled: true`, the final integer limit, model dimensions, solver
parameters, and input hashes. These are completed `INFEASIBLE` proofs, not
budget-limited `UNKNOWN` results.

## Scope and Next Step

No score-1 placement exists in any of these four candidate-limited K256 models.
This does not establish global infeasibility: most exact sites are omitted,
and groups outside each released set retain their certified regions. The next
search must widen the current/quality neighborhoods to K512 and then release
cross-page groups together if the wider pair domains also close.

The certified legal incumbent remains HPWL `15811.06557381333`; native scoring
is still correctly blocked by the necessary HPWL gate.

Follow-up M336-090 widened the same models to K512. All four exhausted 300
deterministic seconds as `UNKNOWN`, so the K256 proofs do not extend to K512.
