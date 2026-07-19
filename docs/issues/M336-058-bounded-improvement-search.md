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
