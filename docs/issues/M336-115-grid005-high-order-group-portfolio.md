# M336-115: Coupled Page-7 Search Improves The 0.05 mm Incumbent

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `639da34`

## Finding

The M336-114 pair chain was locally productive but too slow relative to the
remaining score gap. Eight blocker-aware, higher-order physical-group models
were therefore searched independently from the certified M336-114 endpoint.
The coupled page-7 model found a strict exact-legal improvement that neither
page-7 subgroup found alone.

## Search Contract

Every model used the certified M336-114 result as source, hint, and required
guide 0. Candidate generation used the current and EMI-only quality guides
with weights `1,1`, a `0.05 mm` grid, K4096, exact candidate collisions, one
worker, seed `1000`, a `1200 s` wall limit, and deterministic-time limit `300`.
HPWL was minimized under integer ceiling `15658624877`; packing covered both
sides and used the manual `EMI601` endpoint contract.

The movable sets were page 4 (7 components), page 6 bottom (8), page 6 top
(11), page 7a (9), page 7b (9), page 7a+b (18), page-86 U8601 (11), and page-86
U8602 (16). All eight outputs passed selected-site objective replay, required
guide support, exact rectangle-equivalence auditing, 100/100 keep-in
containment, and zero-overlap validation.

## Portfolio Results

| Model | Status | Integer objective | Integer bound | HPWL | Improvement |
| --- | --- | ---: | ---: | ---: | ---: |
| page4 | OPTIMAL | 15657071606 | 15657071606 | 15657.071597950033 | 1.553269972457 |
| page6b | OPTIMAL | 15658624877 | 15658624877 | 15658.624867922490 | 0 |
| page6t | OPTIMAL | 15658624877 | 15658624877 | 15658.624867922490 | 0 |
| page7a | OPTIMAL | 15658179809 | 15658179809 | 15658.179800768656 | 0.445067153834 |
| page7b | OPTIMAL | 15658624877 | 15658624877 | 15658.624867922490 | 0 |
| page7ab | FEASIBLE | 15646181097 | 15246999851 | 15646.181089510720 | 12.443778411770 |
| page86u1 | OPTIMAL | 15649447427 | 15649447427 | 15649.447418321894 | 9.177449600596 |
| page86u2 | FEASIBLE | 15658624877 | 15513523017 | 15658.624867922490 | 0 |

`FEASIBLE` is retained exactly for both budget-limited runs. The page7ab bound
is below the necessary score-1 threshold, so that restricted domain remains
open. The page86u2 bound is above the threshold and excludes score 1 only in
that finite K4096 model; it is not a global infeasibility claim.

## Promoted Endpoint And Certification

The page7ab solution moves 12 components and reduces HPWL from
`15658.624867922490` to `15646.181089510720`. Its normalized score upper bound
is `0.9753414896889607`; the necessary HPWL gap is now
`385.811517724088`.

An independent all-fixed K1 replay returned `OPTIMAL`. Its objective and bound
both equal `15646181097`, maximum hint distance is zero, and the candidate and
certificate placement files are byte-identical. Result, placement,
certification result, and certified placement SHA-256 values are:

- `69d5e85de31ccec77eb2ef9bf3e3826e56a5448d8a185d421e100dbc3669b794`;
- `f78f67f7f14616c7a8227c538a86e3edbb03843ad862c2678bea7ffa4cebce0a`;
- `342f42c139d3b98b1ac1c1134f12afb6141cb72af76310895454bb16027212d0`;
- `f78f67f7f14616c7a8227c538a86e3edbb03843ad862c2678bea7ffa4cebce0a`.

## Next Action

Use the certified page7ab endpoint as the only scoring incumbent. Re-run the
page-86 U8601 and page-4 closures sequentially from it, then refresh full
one-component and pair closure. Parallel portfolio results must not be merged
without a new exact all-fixed validation.
