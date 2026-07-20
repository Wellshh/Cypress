# M336 Active Roadmap

**Updated:** 2026-07-20  
**Evidence through:** `M336-140`

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
| Exact-site quality optimization | `M336-105` through `M336-140` | **Active** | `EXACT_QUALITY_SPEC.md` |
| Cypress production integration | Soft margin gradient, warm-start cost, E3/E4 anchor/runtime gates | Open, deferred | Resume after a score-1 exact-site reference exists |

Old infeasibility and lower-bound documents remain valid only for their exact
endpoint policy, movable support, candidate domain, grid, and collision model.
In particular, they cannot prove the current EMI601-only contract infeasible.

## Active Priorities

| Priority | Work | Exit criterion |
| --- | --- | --- |
| P0 (complete) | Implement explicit incumbent Hamming exclusion and exact tuple no-goods | M336-128 tests and two distinct K16 legal replays |
| P1 (paused) | Run `d=2,4,6,8` and `Delta=0,1,2,5,10,20` topology generation, then independent HPWL closure | Five rank-11 tuples all collapse; resume after coverage or support changes |
| P2 (active) | Build six residual-net-specific legal guides with candidate coverage diagnostics | M336-140 validates direct span optimization; optimize remaining residual nets and combine certified families |
| P3 | Expand support by exact physical/network closure only | Bound/solution evidence justifies each expansion |
| P4 | Re-run page-86, page-4, one-opt, and pair closure after page-7 changes | New portable incumbent checkpoint |
| P5 | Run native HPWL/RSMT gate after necessary HPWL threshold is crossed | Repeated normalized score `>= 1.0` with identical hash |

## Current Boundary

M336-140 adds a fail-closed target-net-span objective while independently
hard-bounding and replaying global HPWL. The first direct `PSIM2_DATA2` solve
is `OPTIMAL` in its K512/K4096, 20-component, Delta20 domain: target span falls
by `11.498711`, and the five-component legal topology has HPWL
`15654.448329429399`. It is K1-certified and portable. Independent one-opt
reaches a new SHA at `15642.94961817146`, but a complete 2,892-pair,
130,718,237-combination scan returns exactly the M336-129 equal-HPWL swap
plateau. A separate hard-ceiling CP-SAT closure proves its 21,072-candidate
finite domain `OPTIMAL` at integer HPWL `15634450483` and returns a portable
third plateau that swaps both `C703/FV707` and `FV703/FV704`. This is a valid P2
guide and finite-domain negative result, not a global infeasibility proof.
Preserve both guides; do not rerun their seed/weight ladder. Continue direct
objectives for the remaining residual nets, and revisit DATA2 only with a
no-good or materially expanded support.

M336-139 classifies the persistent DATA2 gap over the complete domains. Both
`FV710` and `R708` targets are continuously contained and exact 0.05 mm
keep-in lattice sites, but each overlaps frozen `MIC401` by `0.081943924 mm2`
and `0.013330545 mm2`. Obstacle pruning moves their nearest exact sites by
`2.934706 mm` and `0.05 mm`. The candidate set remains byte-identical to
M336-138 (Jaccard `1.0`), while all five other dedicated residual guides have
exact obstacle-free endpoint coverage. Increasing K, seed, or DATA2 weight
cannot restore coordinates absent from the complete obstacle-free domain.
P2 now requires direct `PSIM2_DATA2` span optimization over legal alternatives,
with `MIC401` frozen and controlled blocker `B402` plus measured partners in
the movable closure.

M336-138 remains the evidence that the six-guide portfolio materially changes
the M336-122 candidate topology by 2,499 sites without repairing DATA2.

M336-137 remains the identity-safe audit and portable M336-122 reference. Its
default-off implementation is a production prerequisite for every subsequent
portfolio comparison.

M336-136 remains the enumeration boundary. Its fifth rank-11 topology and the
previous four all become byte-identical after one-opt and share the certified
M336-133 pair closure to the M336-129 equal-HPWL swap plateau. Rank 11 is not
proved exhausted, but consecutive enumeration remains paused. Preserve all
five tuples as future no-goods. M336-118 remains the scoring incumbent. Seed,
guide-weight, or runtime ladders remain out of scope.

M336-132 resolves the independent result-metadata path defect found during the
M336-131 export. Relative launch inputs are now serialized canonically, so
future portable checkpoint promotion does not require an undocumented path
override.
