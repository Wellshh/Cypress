# M336-078: Complete Bottom-0 K1024 Search Remains Budget-Limited

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `d89195a`

## Problem

M336-075 proves that every tested three-group bottom-0 K1024 domain has a
lower bound above the score-1 threshold. Releasing the fourth physical group
is therefore necessary to restore a score-permitting restricted model, but the
larger search can fail to move away from a complete legal incumbent.

## Unbounded Optimization

Two current/quality K1024 models used exact legality, one worker, seed 1000,
and 300 deterministic-time units:

| Movable closure | Components | Candidates | HPWL | Valid lower bound |
| --- | ---: | ---: | ---: | ---: |
| four major bottom-0 groups | 35 | 35,905 | 15811.065574 | 15217.075045 |
| complete prior bottom-0/page-7 closure | 42 | 42,427 | 15811.065574 | 15142.859706 |

Both are `FEASIBLE`, retain the certified source exactly, pass integer HPWL
replay, and report 100/100 containment with zero violations and overlaps.
Result SHA-256 values are
`4454ce19cf4dd837436b4d49bf12e90ca83ace2116a57aebbec33f93c69cdf77`
and
`b8cdc6ae783b5b875d9e3d830650d5ee12152a8fdd9b0c31b6ea7f18c69f145a`.

## Strict-Improvement Feasibility

The same domains were rerun with integer HPWL ceiling `15811065583`, exactly
one integer unit below the incumbent, and stop-after-first-solution enabled.
This excludes the source as an incumbent without changing any legality rule.

| Movable closure | Status | Incumbent | Valid lower bound | Conflicts | Branches |
| --- | --- | --- | ---: | ---: | ---: |
| four major groups | `UNKNOWN` | none | 15219.074830 | 505,988 | 2,438,538 |
| complete 42 | `UNKNOWN` | none | 15138.860136 | 349,125 | 2,569,389 |

Both exhausted approximately 300 deterministic-time units. With no incumbent,
legality and objective replay are correctly absent. Their result SHA-256 values
are `0344d744ddde111309891029c99b2db7ed7aa404abc775514ad674543ad70b27`
and `62a7503d1925b7120f0f74338f51b437605fafe317c2425b162466a1d104f4b0`.

## Finding

All four lower bounds are below the score-1 HPWL threshold `15260.369572`.
Adding the fourth group therefore restores a score-permitting K1024 model, but
neither optimization mode finds any strict improvement within budget.
`UNKNOWN` is not infeasible, and differing bounds between runs reflect search
trajectories rather than contradictory proofs.

These results cover only their current/quality K1024 candidate domains and
fixed assignment. They do not cover all exact sites, alternate assignments,
or the full 100-component placement.

## Next Action

Do not repeat these exact model/budget combinations. Explore full-site small
ejection closures, materially different candidate construction, or a changed
incumbent topology before refreshing the complete bottom-0 solve.
