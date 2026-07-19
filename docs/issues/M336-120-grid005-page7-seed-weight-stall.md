# M336-120: Refreshed Page-7 Seed And Weight Portfolio Stalls

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `db7cb4f`

## Problem

The coupled page7ab K4096 model produced M336-115, but it was budget-limited
and retained a score-permitting lower bound. After the page-86, page-4, and
pair improvements, the refreshed topology needed a controlled seed and guide
allocation test before spending more budget on the same search family.

## Method

Eight exact models used the portable M336-118 checkpoint as source, hint, and
required guide 0. All moved the same 18 page-7 BOTTOM components on the
`0.05 mm` grid, used K4096, exact BOTH-side collision constraints, integer
incumbent ceiling `15634450483`, one worker, and 300 deterministic-time units.
Four runs used current/quality weights `1:1`; two used `3:1`; two used `1:3`.

## Evidence

| Weights | Seed | Status | Bound | Branches | Conflicts | Result SHA-256 |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| 1:1 | 1000 | FEASIBLE | 15235269237 | 2036762 | 83995 | `723f9864eb4560123a4369e35545af5f24be3a19aecc4233fd57fc54d6fb6416` |
| 1:1 | 1001 | FEASIBLE | 15235269237 | 2033254 | 84117 | `7f38d7745ceba5f5d89cf265483e99477ad0a26030bc99d6623a8c5188ba3fdf` |
| 1:1 | 1002 | FEASIBLE | 15235269237 | 2158142 | 82134 | `74126ce21c91ffa65c045120a47324dc1c30439c121316d02e420b2292452aa3` |
| 1:1 | 1003 | FEASIBLE | 15235269237 | 2205839 | 83672 | `6f18fc9c94413f6ea71c3d9f49336642bba7b4f1bb6a453b2175b4ca1589ed7a` |
| 3:1 | 1100 | FEASIBLE | 15235269237 | 2161276 | 81953 | `0aacc3c3f2ff7f8328ceedff67a7f8cd8cbdbe995dadbd2b5e9483665c2340ba` |
| 3:1 | 1101 | FEASIBLE | 15235269237 | 2279227 | 83446 | `4125fd40fb77e130945c492abb655ca1ecd0a471d55e4a49bedcbaba5541fb65` |
| 1:3 | 1200 | FEASIBLE | 15235269237 | 1922479 | 78965 | `6b36ee220b9f2723538e1eb4da6a8be9a9bb5a0bc294f69ef9ca3a92c40e8a4f` |
| 1:3 | 1201 | FEASIBLE | 15235269237 | 1975470 | 79118 | `ced268ae009b36ee3201401de74b4a021997060f8ebb4d052d7aaef2945d7cac` |

Every run used 73,810 candidates, exhausted its deterministic budget, passed
objective replay and guide-support audits, and retained 100/100 containment
with zero violations or overlaps. All placements are byte-identical to the
M336-118 incumbent with SHA-256
`32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`.

The common bound is HPWL `15235.269237`, below the necessary score-1 threshold
`15260.369572`. The finite domain is therefore still score-permitting; budget
exhaustion is not optimality or infeasibility.

## Refreshed Residual Diagnosis

Independent PlaceDB replay gives current HPWL `15634.450477332834` and
collision-relaxed quality-guide HPWL `14700.901479300053`. The six leading
positive residuals remain page-7 nets:

| Net | Residual HPWL | Controlled refdes |
| --- | ---: | --- |
| VSIM2 | 105.487757 | C703,FV707,R707 |
| SIM_DET1 | 92.990012 | FV705,R703 |
| PSIM2_DATA2 | 86.990657 | FV710,R708 |
| NFC_SWP | 78.716197 | FV706 |
| PSIM2_SRST2 | 76.672372 | FV708,R709 |
| PSIM2_SCLK2 | 73.992053 | FV709,R710 |

Their gross residual is `514.849048`, larger than the current necessary gap
`374.080906`. This is only an optimistic localization signal because the guide
is collision-relaxed and per-net gains are not additive.

## Next Action

Stop this seed and weight ladder. Generate exact-legal page-7 escape states
toward the quality guide, certify those states as non-scoring search guides,
and use them to alter candidate topology while preserving the M336-118
checkpoint as the independent incumbent hint and hard ceiling.
