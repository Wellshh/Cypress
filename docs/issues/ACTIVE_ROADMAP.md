# M336 Active Roadmap

**Updated:** 2026-07-20  
**Evidence through:** `M336-133`

**Active specification:**
[`experiments/m336/EXACT_QUALITY_SPEC.md`](../../experiments/m336/EXACT_QUALITY_SPEC.md)

This file is the current decision index. The individual issue documents remain
an append-only audit trail. “Superseded” below limits a finding's applicability
to the endpoint/domain stated in that finding; it does not erase the evidence
or silently change its ledger status.

## Current Contract

```text
source/checkpoint: experiments/m336/checkpoints/M336-118/
endpoint policy:   manual EMI601, runtime Q601
grid:              0.05 mm
assignment:        fixed M336-118 assignment
collisions:        exact BOTH sides
incumbent HPWL:    15634.450477332834
score-1 threshold: 15260.369571786632
final gate:        exact legality + native HPWL/RSMT score >= 1.0
```

The current placement is 100/100 contained with zero keep-in violations and
zero overlaps. Its placement SHA-256 is
`32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`.

## Tracks

| Track | Scope | State | Superseded by / next authority |
| --- | --- | --- | --- |
| Input and geometry correctness | Parsing, coordinates, footprints, collision quantization, exact replay, portable dependency paths | Retained prerequisites | Original `SPEC.md` and resolved issue evidence through M336-132 |
| Historical Q601/two-anchor policy | `M336-012/014/016/018/022/028/030-045` and their declared finite domains | Historical; not an active score blocker | Current EMI601-only policy revalidated by `M336-105` |
| Current endpoint legality | Manual EMI601, runtime Q601, fixed assignment, 0.05 mm | Stable | M336-118 portable checkpoint and `M336-119` |
| Exact-site quality optimization | `M336-105` through `M336-133` | **Active** | `EXACT_QUALITY_SPEC.md` |
| Cypress production integration | Soft margin gradient, warm-start cost, E3/E4 anchor/runtime gates | Open, deferred | Resume after a score-1 exact-site reference exists |

Old infeasibility and lower-bound documents remain valid only for their exact
endpoint policy, movable support, candidate domain, grid, and collision model.
In particular, they cannot prove the current EMI601-only contract infeasible.

## Active Priorities

| Priority | Work | Exit criterion |
| --- | --- | --- |
| P0 (complete) | Implement explicit incumbent Hamming exclusion and exact tuple no-goods | M336-128 tests and two distinct K16 legal replays |
| P1 | Run `d=2,4,6,8` and `Delta=0,1,2,5,10,20` topology generation, then independent HPWL closure | M336-133 proves rank-11 degeneracy; exclude both tuples and continue enumeration |
| P2 | Build six residual-net-specific legal guides with candidate coverage diagnostics | M336-130 first portfolio exists; guides must still cover every listed endpoint |
| P3 | Expand support by exact physical/network closure only | Bound/solution evidence justifies each expansion |
| P4 | Re-run page-86, page-4, one-opt, and pair closure after page-7 changes | New portable incumbent checkpoint |
| P5 | Run native HPWL/RSMT gate after necessary HPWL threshold is crossed | Repeated normalized score `>= 1.0` with identical hash |

## Current Boundary

M336-133 excluded the first rank-11 d6 tuple and found a second rank-11 optimum
in 14.330 DT. It changes `R708` where M336-131 changes `FV710`; both independent
closures become byte-identical after one-opt and end at the M336-129 equal-HPWL
swap plateau. M336-118 remains the scoring incumbent. Exclude both rank-11
tuples and continue enumeration; if further solutions map to the same one-opt
hash, reuse that certified closure evidence and prioritize new residual/support
guides. Seed, guide-weight, or runtime ladders without feasible topology or
explicit exclusion remain out of scope.

M336-132 resolves the independent result-metadata path defect found during the
M336-131 export. Relative launch inputs are now serialized canonically, so
future portable checkpoint promotion does not require an undocumented path
override.
