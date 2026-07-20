# M336-125: Exact Page-7 Blocker Release Retains M336-118

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `b88bd39`

## Search Contract

M336-124 identified `B402,L401` as the complete movable one-hop blocker
boundary of the page-7 quality hybrid. They were added to the 18 page-7
BOTTOM components without releasing the frozen `MIC401` anchor. The expanded
quality hybrid was candidate guide 0, followed by certified escape seeds
3001/3000/3003 and M336-118 with weights `4,2,1,1,2`.

All models used M336-118 as source and independent hint, exact BOTH-side
collisions, the `0.05 mm` grid, K4096, 82,000 candidates, one worker, and hard
integer HPWL ceiling `15634450483`. Every guide passed required support
closure over the exact 20-component movable set.

## Rank Result

Automatic and partial-fixed minimum-rank probes both returned `OPTIMAL` at
rank and bound 86. Both reproduced M336-118 at HPWL
`15634.450477332834`. Result hashes are
`63f58a2237997e6e04a8bccb305b2f5aed7003df955d6170358cae8d33bb1702`
and `6c7b1e0d3092acb336e31bcc92dbe4406a7b99c6f23c43605cbf86bbde26b601`.
Thus the expanded domain still has no monotonic quality-directed topology
under the no-regression envelope.

## HPWL Portfolio

| Branching | Seed | Status | Bound | Branches | Conflicts | Result SHA-256 |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| automatic | 7000 | FEASIBLE | 15234769345 | 2085705 | 79659 | `3e8cf57e83140e51110b77b915e0a3c8f3528826c307dfc13189f424d174a8cb` |
| automatic | 7001 | FEASIBLE | 15234769345 | 2434565 | 81225 | `3cc7fd0a2b93d5cad1abf0adc0ed9ef49ddc9be47b57cd2b6b1f5d921f5faf2e` |
| automatic | 7002 | FEASIBLE | 15234769345 | 2074563 | 81797 | `ba5a4b5b99a027f28ae93b94ecd10d60084d618869dbd4bdb99ef33cd3671d33` |
| automatic | 7003 | FEASIBLE | 15234769345 | 1991867 | 77437 | `910c5d873f97e6959787bde25ee4b3c768811bdb0689c7631a9f51ed2bc8976e` |
| partial-fixed | 7000 | FEASIBLE | 15234769345 | 246076 | 74129 | `967d14bfe26edd3f2068d0d7d0c813be046538433b68fd4d712f4057a05192bf` |
| partial-fixed | 7001 | FEASIBLE | 15234769345 | 248289 | 79185 | `36d7967ac254c3477637c21af6aa5aa9da2af5d73de32777433531f325ed3eab` |

Every run exhausted approximately 300 deterministic-time units and retained
integer objective `15634450483`. All eight placements have the M336-118
SHA-256 `32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`.
HPWL/rank replay, exact collision equivalence, guide support, 100/100
containment, zero keep-in violations, and zero overlaps all passed.

## Interpretation And Next Action

The common HPWL bound is `15234.769345`, below the score-1 necessary threshold
`15260.369572`. The 20-component finite domain therefore remains open; the
six `FEASIBLE` statuses are not optimality or infeasibility proofs. Stop this
direct seed ladder. Run deterministic exact guided escape toward the expanded
hybrid under explicit total and per-move HPWL rise limits. Preserve and
certify only genuinely new legal topologies involving the released boundary,
then use them as independent guides for a new hard-ceiling HPWL closure.
