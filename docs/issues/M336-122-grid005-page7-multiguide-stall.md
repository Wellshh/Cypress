# M336-122: Certified Page-7 Multiguide Search Stalls

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `163ab42`

## Problem

M336-121 produced three exact-legal page-7 escape topologies, but it remained
unknown whether adding all three to the finite candidate domain would let
CP-SAT cross the M336-118 local boundary. Repeating an ordinary seed ladder
would not answer this because the escape sites were absent from that domain.

## Controlled Search

Eight runs used M336-118 as source, independent hint, required guide 0, and
hard integer HPWL ceiling `15634450483`. Candidate generation combined the
current, certified seeds 3001/3000/3003, and page-7 quality-hybrid guides with
weights `2,2,1,1,2`. The 18 page-7 BOTTOM components were movable on the
`0.05 mm` grid with K4096; all other sites were fixed. Each exact BOTH-side
model had 73,810 candidates, one preprocessing/solver thread, a 1,200-second
wall limit, and 300 deterministic-time units.

## Evidence

| Seed | Status | Bound | Branches | Conflicts | Result SHA-256 |
| ---: | --- | ---: | ---: | ---: | --- |
| 5000 | FEASIBLE | 15235269237 | 2176502 | 84398 | `cf0563a7576be2cfd1e155718676cae9b35b8f916664b98da3274873542f30f0` |
| 5001 | FEASIBLE | 15235269237 | 2001355 | 83834 | `6274adbec3ed9f1b3aa12c41c0e4c1f4e693420510faf87b1b0b745cc6ca397f` |
| 5002 | FEASIBLE | 15235269237 | 2364550 | 83505 | `66b9e6ad29bd75900ae515f6bbc1cf7715a68cb9ca57144ab773746ef906932f` |
| 5003 | FEASIBLE | 15235269237 | 2204741 | 83255 | `85e824c2b1734e60bae655278bf191f200d30a62e21dc861d42e7307ac3b382b` |
| 5004 | FEASIBLE | 15235269237 | 2117295 | 83471 | `eaa0177a164ef1a6b306b11fd105027601ab4f641de83421e0d3931b62bacf68` |
| 5005 | FEASIBLE | 15235269237 | 2093474 | 82336 | `5e72e17623568e0c39f6d3e412918e65ddcc81f93fdd0676c317d5fd8a98fb45` |
| 5006 | FEASIBLE | 15235269237 | 1990953 | 80485 | `40776aed8faf3fe661c92a6e0fad957a69b1e191e37c92ae1397c41b7a1f8956` |
| 5007 | FEASIBLE | 15235269237 | 1984269 | 80842 | `3f764d9115abab677932a921c5d05378b6be86001742f77a5573dfbf996dd87f` |

Every run retained HPWL `15634.450477332834`, integer objective
`15634450483`, normalized score upper bound `0.9760732936479889`, and the
M336-118 placement SHA-256
`32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`.
All objective/rank replays and required-guide support audits passed. The
candidate collision model was exact; final validation reported 100/100
contained, zero keep-in violations, and zero overlaps.

## Interpretation And Next Action

The common bound is HPWL `15235.269237`, below the score-1 necessary threshold
`15260.369572`. These budget-limited `FEASIBLE` runs therefore neither prove
optimality nor exclude a score-1 placement in the finite domain. Stop this
multiguide seed ladder. Use the same guide-defined domain with HPWL as a hard
envelope and minimize stable guide rank to obtain a genuinely different legal
topology; then run an independent HPWL closure and promote only a strict,
all-fixed certified improvement.
