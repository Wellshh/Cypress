# M336-129: Incumbent Exclusion Finds An Equal-HPWL Swap Plateau

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `49e734a`

## Search Contract

The M336-122 18-component page-7 domain was reconstructed exactly: current,
seed 3001/3000/3003, and page-7 quality-hybrid guides weighted `2,2,1,1,2`,
K4096, 73,810 candidates, fixed M336-118 assignment, manual EMI601 endpoint,
exact BOTH-side collisions, and one worker. M336-118 was the independent
diversity reference. Candidate count and all required-guide support audits
match M336-122.

## Topology Generation

| Distance/envelope | No-good | Status | Rank | HPWL | Changed refdes |
| --- | --- | --- | ---: | ---: | --- |
| `d=2`, `Delta=0` | none | UNKNOWN | bound 2 | none | none |
| `d=2`, `Delta=20` | none | OPTIMAL | 3 | 15635.950370 | `FV710,R707` |
| `d=4`, `Delta=20` | none | OPTIMAL | 7 | 15649.948866 | M336-121 seed 3001 |
| `d=4`, `Delta=20` | seed 3001 | OPTIMAL | 7 | 15648.448974 | `C703,FV705,FV707,R707` |

The `d=2,Delta=0` run exhausted 300 deterministic-time units without an
incumbent; it is inconclusive, not infeasible. The first d2 state passed an
all-fixed K1 replay, but greedy closure reverted `FV710/R707` exactly to
M336-118. CP-SAT closure with that above-ceiling hint returned `UNKNOWN` with
bound `15239.993382`, reproducing the single-infeasible-hint behavior in
M336-097.

The d4 no-good result is a new family and reaches both `VSIM2` and `SIM_DET1`
support. One-opt closure reduced it to HPWL `15646.449188590772`, retaining
only `C703,FV707` at a distinct one-optimum. A full exact pair scan then
evaluated 2,874 pairs and 103,003,718 site combinations in 110.916 seconds.
It swapped `C703` and `FV707` between the two M336-118 sites and recovered
HPWL exactly to `15634.450477332834`.

## Certified Plateau

The swap placement SHA-256 is
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`,
distinct from M336-118 while having the same integer objective `15634450483`.
An independent all-fixed K1 replay returned `OPTIMAL`, zero hint distance,
100/100 containment, zero keep-in violations, zero overlaps, and complete
objective/per-net replay.

Using the certified swap as a feasible independent hint, a fresh M336-122 HPWL
closure retained the swap at the same objective after 300 deterministic-time
units. Its valid bound is `15235.269237`, below the score-1 threshold, so the
finite domain remains search-open. This is not a strict scoring improvement.

The certified non-scoring guide is portable at
`experiments/m336/guides/M336-129/swap-plateau/certificate.json`. Its portable
certificate, original certificate, placement, assignment, and manifest
SHA-256 values are respectively:

- `a0020dafef9de14ef16ecb8b43714de781e4aa7fe04b4b242e0e549a444cbf0a`;
- `d20423745db403afc070387faee18b9d11e931855ee1e5193f4e9487e76609e8`;
- `c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`;
- `e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87`;
- `549ffdd8c958b4f649ce2cc17eceee9023effab6c3b75d4020b7be9e2eb1bc00`.

## Interpretation And Next Action

Explicit exclusion answers the intended question: the M336-122 domain does
contain legal topologies distinct from M336-118, including a distinct topology
at the incumbent HPWL ceiling. The first such basin does not improve HPWL
within the tested closure budget. Continue d4 enumeration by adding no-goods
for seed 3001 and the new family while using remaining certified families as
feasible hints, then increase to d6/d8. Preserve the swap plateau as a candidate
guide and feasible hard-ceiling hint; promote nothing until HPWL is strictly
below M336-118 and all-fixed certification passes.
