# M336-053: Threshold Feasibility Searches Exhaust Budget as UNKNOWN

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `49585de`

## Problem

Direct global K64 feasibility searches for the score threshold have not found
an incumbent or proved infeasibility. Two runs with CP-SAT hint repair spend
their full deterministic budget in the repair path without entering ordinary
conflict search. A fixed-hint run performs substantial search but also ends
without a conclusion. Every result is `UNKNOWN`; none may be reported as
infeasible.

## Evidence

All runs use one worker, seed 1000, deterministic preprocessing, exact BOTH-side
collision constraints, and the `EMI601` manual-baseline endpoint override.

| Gate | Hint mode | DT | Conflicts | Branches | Status |
| --- | --- | ---: | ---: | ---: | --- |
| score `>=1.0` | quality, repair | 300.009404 | 0 | 20,916 | `UNKNOWN` |
| HPWL `<=15900` | current, repair | 150.001151 | 0 | 20,916 | `UNKNOWN` |
| HPWL `<=15950` | current, fixed | 100.000037 | 501,983 | 1,511,361 | `UNKNOWN` |

The identical zero-conflict branch count in both repair runs shows that
increasing the threshold does not reach general search before timeout. The
fixed-hint control confirms that disabling repair changes the search regime,
but its smaller budget still produces no incumbent or proof.

A separate 300-DT global optimization retained the certified incumbent at
HPWL `15985.274443` and passed objective replay. Its valid lower bound is
`15058.024431`, which is below the score-1 necessary HPWL threshold
`15260.369572`; therefore it cannot rule out an acceptable layout. A later
plateau-guided run also found no improvement, but its response objective was
`15993.510225` while selected-site replay was `15985.275097`. That run exited
3 and its `14862.250597` bound is quarantined under M336-051.

## Impact

Treating budget exhaustion as infeasibility would create a false experimental
conclusion and could prematurely stop the only search path whose valid lower
bound still permits score 1.0. Hint repair is also a poor default for a guide
that violates the active HPWL gate because it can monopolize the complete
deterministic budget.

## Required Follow-up

- Preserve the exact `OPTIMAL`/`FEASIBLE`/`INFEASIBLE`/`UNKNOWN` distinction in
  every report and issue.
- Prefer bounded regional optimization from a certified legal incumbent over
  direct global threshold feasibility.
- Run repair and ordinary search as separately budgeted phases if repair is
  used; never assume CP-SAT will fall back within one invocation.
- Certify every promoted placement with all sites fixed and require objective
  replay audit to pass.
- Do not close this issue until a score-feasible certified placement or a valid
  global lower-bound proof is produced.
