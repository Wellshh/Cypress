# M336-080: Major Physical Groups Are Full-Site Exact Optima

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `70a7a06`

## Problem

Single physical groups were previously optimized only in current/quality
K1024 domains. Their `OPTIMAL` results could still hide a cooperative move at
a farther exact site, especially after M336-077 found target-only gains outside
the nearest local neighborhood.

## Full-Site Closure

Each major bottom-0 group was independently released over every
fixed-obstacle-free site (`candidate_limit=0`). Models used exact polygon
collisions, current/quality guides, an independent current hint, one worker,
and seed 1000:

| Physical group | Movable | Candidates | DT | Result |
| --- | ---: | ---: | ---: | --- |
| page-4/MIC401 bottom | 7 | 13,336 | 4.6178 | `OPTIMAL` at source |
| page-6 EMI601 + J601 bottom | 10 | 17,757 | 5.5007 | `OPTIMAL` at source |
| page-7/J701 bottom | 9 | 15,359 | 5.0954 | `OPTIMAL` at source |
| page-7/J702 bottom | 9 | 15,818 | 4.9125 | `OPTIMAL` at source |

Every response objective and bound equals integer HPWL `15811065584`. HPWL
and guide-rank replay audits pass, and exact validation reports 100/100
containment with zero violations and overlaps. Result SHA-256 values in table
order are:

- `c39f001b689edc83774845fd147483af9ca3c493a72b84604f1d7520a35a9802`;
- `ac11819ed808cb3252b3c03b27e265257fa6821daa49bbe25e9a780a93ccadf2`;
- `ea425e4d55b3b3ac331d283aa60a1fcd0f61b4ab66baef16edc3ac92200f1176`;
- `50d0eaf4ed289277482a8ffc302e062fb7396fba0b81ddd7589cc67ba65f3fe0`.

## Finding

Candidate truncation is not hiding a strict improvement inside any major
group. The current placement is an exact full-site group optimum for all four
fixed-surrounding domains. Together with the complete page-86 group proofs in
M336-067, progress requires cross-group coupling, a changed assignment, or a
different global topology.

This remains a family of restricted proofs. A component fixed outside one
group may need to move before that group can improve, so none of these results
is a global optimality or infeasibility claim.

## Next Action

Run the six pairwise unions of the four groups over all exact sites. Stop any
pair proved optimal; preserve valid bounds for budget-limited pairs and promote
only strict replayable improvements.
