# M336-058: Optimization Search Stalls While Tightening Lower Bounds

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `05e73eb`

## Problem

The exact-site probe can minimize HPWL or impose the final score-1 threshold,
but it cannot ask for the first modest improvement over a certified incumbent.
This creates two ineffective extremes: optimization spends most of a fixed
budget tightening the lower bound, while direct threshold feasibility must
cross the entire remaining gap in one solve.

## Evidence

From certified HPWL `15836.404447`, all-100 K64 and K128 searches returned the
same floating incumbent after 300 deterministic-time units:

| Domain | Candidates | Conflicts | Branches | Valid lower bound |
| --- | ---: | ---: | ---: | ---: |
| K64 | 6,380 | 330,493 | 3,191,366 | 15113.310818 |
| K128 | 12,657 | 445,382 | 6,114,405 | 14713.083825 |

Both bounds permit score 1.0, but neither run found a strict improvement. This
is an incumbent-search failure mode, not evidence of infeasibility and not an
OR-Tools correctness defect.

## Mitigation

`probe_exact_site_cpsat.py` now accepts an exact
`M336_INTEGER_HPWL_CEILING`. It constrains the same integer HPWL expression
used by response, variable, and selected-site replay, avoiding an ambiguous
floating conversion. When a score threshold is also active, the effective
limit is the stricter integer bound.

`M336_STOP_AFTER_FIRST_SOLUTION=1` maps to the OR-Tools CP-SAT parameter of the
same name. This allows a minimization model with a strict ceiling to return the
first qualifying placement instead of spending the remaining budget proving
or improving it. `repair_hint` and `hint_conflict_limit` remain explicit and
recorded; OR-Tools uses them to bound either fixed hint following or L1 hint
repair before regular search.

## Verification

The M336 pure-Python suite passes 41/41, including score-only, ceiling-only,
combined-limit, empty-limit, and invalid-ceiling cases. An all-fixed integration
replay used ceiling `15836404457` and stop-after-first mode. It returned
`OPTIMAL` at `1e-8` deterministic-time with all three integer objectives equal
to the ceiling, a passing floating replay, and exact 100/100 legality with zero
violations and overlaps.

## Next Action

Run all-100 K128 with a ceiling at least one HPWL unit below the incumbent,
`repair_hint=1`, a recorded conflict limit, and stop-after-first enabled.
Certify any returned placement before local closure. A budget-limited result
without a solution remains `UNKNOWN`, never infeasible.

## First Bounded Run

The all-100 K128 run used integer ceiling `15835404457`, exactly one HPWL unit
below the audited incumbent, L1 hint repair with a 10,000-conflict limit, and
stop-after-first mode. It returned `UNKNOWN` without an incumbent when the
600.008863-second wall limit expired. Deterministic time reached 286.208955,
with 1,143,608 conflicts and 3,859,927 branches. The valid lower bound was
`14809.784116`, still below the requested ceiling.

This result neither proves the K128 domain infeasible nor disproves bounded
search. It shows that global L1 repair is too expensive under the current wall
budget. Apply the same ceiling to the smaller score-bound-permitting physical
closure, or remove the optimization objective and audit the hard-constraint
HPWL expression as a pure feasibility model.

## Regional Bounded Improvement

The 42-component physical closure was retried at K128 with the same one-HPWL
ceiling. The model contained 5,434 candidates and fixed the other 58 controlled
sites. It returned `FEASIBLE` after 179.705625 wall seconds and 116.714367
deterministic-time, with 377,827 conflicts and 1,380,243 branches.

The first qualifying solution reduced floating HPWL by `1.059177` to
`15835.345270`. All response, variable, and selected-site objectives equal
`15835345279`; exact legality and floating replay pass. Its valid lower bound
is `15262.996062`, about 2.626 above the score-1 threshold. Therefore this
K128 physical closure can improve the incumbent but cannot reach score 1.0
while the other 58 sites remain fixed. That proof does not apply to K256 or to
the full board.

Full-domain local closure then moved `C607` for another `0.001074` reduction.
It scanned 2,893 relevant pairs and 1,444,835 site combinations without another
improvement. Final HPWL is `15835.344196`, normalized score upper bound is
`0.963690425`, and the remaining necessary HPWL gap is `574.974624`.

The bounded result, bounded placement, first certification, local result,
local placement, and final certification SHA-256 values are:

- `5d7d05f0694639f6936bc9d99e25494d88ee6f1773ed53066f95102e240145c7`;
- `5c0a3fb2ff3af216da5ce787397b7503da6182ee4c353790e64a480e07efbc7a`;
- `801279a9bc22e3ecea2c63d3c73855891ef85ffda5d9442f9ec17e44d4a6916d`;
- `5e2588bef04bd0ff4c72f8fbf29d1b5bf99768cea50cd905a2c424c1808d076c`;
- `a44942bee4ba8c1bf275ef08177ed359de588b8045907e2b3853d3f5a0a179c6`;
- `dd71614338568bfddac1aacf55d14e65a44512f199df7dc44a220c3295c585f2`.

The final all-fixed replay is `OPTIMAL` at `1e-8` deterministic-time. All
integer objectives equal `15835344206`, floating delta is `0.000010071333`,
and exact legality remains 100/100 with zero violations and overlaps. Continue
from this certified placement in the K256 physical domain, whose prior valid
bound remains below the score threshold.

## K256 Step Ablation

Two repair-off K256 runs tested larger bounded steps from the certified result.
Both exhausted 300 deterministic-time without an incumbent:

| Step | Ceiling | Status | Conflicts | Branches | Bound |
| --- | ---: | --- | ---: | ---: | ---: |
| -10 HPWL | 15825344206 | `UNKNOWN` | 789,525 | 2,520,337 | 15164.578912 |
| -5 HPWL | 15830344206 | `UNKNOWN` | 812,171 | 2,573,303 | 15162.579557 |

The -5 run used 362.096764 wall seconds and result SHA-256
`102f5d8d1db82b20e35c717d18a4dfe83d242f92b63824e5b039b078499597b0`.
Both valid bounds remain below their ceilings, so neither run proves the
requested step infeasible. Halving the step did not produce an incumbent;
further dense step sweeps would repeat the same optimization search. The next
model should retain the hard integer ceiling but remove the minimization
objective, then audit solved HPWL variables and selected-site replay directly.
