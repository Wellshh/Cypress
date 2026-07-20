# M336-127: Joint Rank Escape Needs More Than A 200-HPWL Envelope

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `8fe53b3`

## Problem

M336-126 established that sequential legal moves cannot involve the released
`B402,L401` blockers. Joint CP-SAT rank optimization was therefore tested
under controlled HPWL regression envelopes to allow simultaneous topology
changes without weakening exact collision or keep-in constraints.

## Method

All eight models reused the M336-125 20-component, 82,000-candidate K4096
domain. The expanded quality hybrid was primary guide; certified seeds
3001/3000/3003 and M336-118 completed the `4,2,1,1,2` allocation. Seed 3001
was an independent feasible hint. Automatic and partial-fixed branching were
run at each integer HPWL ceiling corresponding to +20, +50, +100, and +200
above M336-118. Candidate rank was the only objective.

## Results

Every run returned `OPTIMAL` at rank and bound 72 and emitted HPWL
`15649.948866405257`. Every placement SHA-256 is
`14b534af7e58bd277ff1fcfd4045636756bbb3a9de4386f3c307f021ddec2ed5`,
byte-identical to certified seed 3001. Thus neither `B402` nor `L401` moves at
the exact minimum rank within any tested envelope.

| Rise | Automatic result SHA-256 | Partial-fixed result SHA-256 |
| ---: | --- | --- |
| 20 | `cde684d688fc2631de5f6808dd79c577a004b45f6f8b162c63fe20f22eb72adc` | `4642cbd034d2bf7cc35d6e2c928b03aca02d896f6f8e3b878e7189c7727f988d` |
| 50 | `c28836b8354425b73ec1ba45d29bf01f338a6959ec529c2af729ebd61c55add3` | `456df03b9e41e1ea2a979cb7d685906aeae9e4e04d8d66b0add2a2050435a31f` |
| 100 | `55c94b99f8fbf3ec18dc0951eaf23f365099150adc9e0cd86e0074419c9f8a39` | `fe2982c5a23203c00ffcf40d858533bf720f66986043caf0d9e140e98242ae73` |
| 200 | `c1123f10dc50d99f3429a3e750f935b40ef151a90c47a81e990eaac389729284` | `31a5d72f5f052fcf280d04c05a08f4e8353daab3846523d2b1aaf3ce27bac6da` |

Automatic runs used 11.38--11.52 deterministic seconds and partial-fixed runs
8.28--8.36, far below the budget. All HPWL/rank replay, exact candidate
collision equivalence, guide support, 100/100 containment, zero keep-in
violations, and zero overlaps checks passed.

## Interpretation And Next Action

The result is an exact finite-domain rank proof under each listed ceiling; it
does not prove that a better HPWL placement is absent. The stable result across
a tenfold envelope range shows that another finite rise step is not
informative. Remove the HPWL model and solve the exact candidate domain for its
global minimum legal rank. Treat that placement only as a topology-cost
measurement and non-scoring guide. If it is distinct, independently certify
it, then recover HPWL with M336-118 retained as the scoring incumbent and hard
ceiling.
