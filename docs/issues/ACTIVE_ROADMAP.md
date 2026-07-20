# M336 Active Roadmap

**Updated:** 2026-07-20  
**Evidence through:** `M336-146`

**Active specification:**
[`experiments/m336/NATIVE_CYPRESS_GOAL.md`](../../experiments/m336/NATIVE_CYPRESS_GOAL.md)
and
[`experiments/m336/NATIVE_CYPRESS_PLAN.md`](../../experiments/m336/NATIVE_CYPRESS_PLAN.md)

**Paused reference specification:**
[`experiments/m336/EXACT_QUALITY_SPEC.md`](../../experiments/m336/EXACT_QUALITY_SPEC.md)

This file is the current decision index. The individual issue documents remain
an append-only audit trail. “Superseded” below limits a finding's applicability
to the endpoint/domain stated in that finding; it does not erase the evidence
or silently change its ledger status.

## Current Contract

Native Cypress evidence must execute the complete production path:

```text
NonLinearPlace -> PlaceObj -> differentiable objectives -> backward
-> GPU optimizer step -> hard projection -> exact validation
-> native HPWL/FLUTE RSMT
```

Fixed-placement scoring and exact-site optimization do not count as Cypress
improvements. Exact assets are limited to immutable references, optional warm
starts, exact validation, and strictly bounded local E4 repair.

The frozen exact-reference contract remains:

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
zero overlaps. The legacy rounded checkpoint PL SHA-256 is
`32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`;
its float-preserving native replay SHA-256 is
`ce1835c9b2b58a15ef5f27f143bc61b3446ddb06abd280b7e7f9ffcba90b47ab`.
M336-142 records the repeated native HPWL `15634.45047733283`, FLUTE RSMT
`17333.037`, and normalized score `0.9278501538723687`.

## Tracks

| Track | Scope | State | Superseded by / next authority |
| --- | --- | --- | --- |
| Input and geometry correctness | Parsing, coordinates, footprints, collision quantization, exact replay, portable dependency paths | Retained prerequisites | Original `SPEC.md` and resolved issue evidence through M336-132 |
| Historical Q601/two-anchor policy | `M336-012/014/016/018/022/028/030-045` and their declared finite domains | Historical; not an active score blocker | Current EMI601-only policy revalidated by `M336-105` |
| Current endpoint legality | Manual EMI601, runtime Q601, fixed assignment, 0.05 mm | Stable | M336-118 portable checkpoint and `M336-119` |
| Exact-site quality optimization | `M336-105` through `M336-140` | Paused at M336-140 | Immutable reference assets under `EXACT_QUALITY_SPEC.md` |
| Cypress production integration | Objective purity, differentiable keep-in, adaptive anchor, irregular density, warm-start cost, E0-E4 gates | **Active** | `NATIVE_CYPRESS_GOAL.md` and `NATIVE_CYPRESS_PLAN.md` |

Old infeasibility and lower-bound documents remain valid only for their exact
endpoint policy, movable support, candidate domain, grid, and collision model.
In particular, they cannot prove the current EMI601-only contract infeasible.

## Active Priorities

| Priority | Work | Exit criterion |
| --- | --- | --- |
| N0 (complete) | Rebuild, repeat the M336-118 native HPWL/RSMT score, and capture current E0/E2/E3/E4 seed-1000 smoke | Repeated score is identical; old logs prove GPU optimizer execution but lack an explicit backward marker, which N1 instrumentation must add |
| N1 (complete) | Make objective evaluation pure and projection lifecycle explicit | M336-143 tests and GPU smoke prove pure objective, explicit candidates, backward, optimizer updates, projection metrics, and state reset |
| N2 (complete) | Add a differentiable interior keep-in margin and bounded adaptive subgroup-balanced anchor control | M336-144 through M336-146 prove finite inward gradients, bounded serialized control, and an isolated E2/E3 contract; anchor quality remains below the final gate |
| N3 (active) | Make TOP/BOTTOM density respect conservative irregular usable capacity | Side-isolated tests and reduced projection pressure or improved final metrics |
| N4 | Preserve legal initial positions and bound E4 repair to illegal conflict closures | Exact preflight preserves legal coordinates; cold/warm timings and local-repair scope are reported |
| N5 | Run final cold/warm E0-E4 matrix for seeds 1000, 1001, and 1002 | Exact E4 legality, native HPWL/RSMT, runtime, anchor metrics, hashes, and acceptance report |

## Paused Exact-Site Priorities

| Priority | Work | Exit criterion |
| --- | --- | --- |
| P0 (complete) | Implement explicit incumbent Hamming exclusion and exact tuple no-goods | M336-128 tests and two distinct K16 legal replays |
| P1 (paused) | Run `d=2,4,6,8` and `Delta=0,1,2,5,10,20` topology generation, then independent HPWL closure | Five rank-11 tuples all collapse; resume after coverage or support changes |
| P2 (paused) | Build six residual-net-specific legal guides with candidate coverage diagnostics | M336-140 validates direct span optimization; further exact-site search requires an explicit phase decision |
| P3 | Expand support by exact physical/network closure only | Bound/solution evidence justifies each expansion |
| P4 | Re-run page-86, page-4, one-opt, and pair closure after page-7 changes | New portable incumbent checkpoint |
| P5 | Run native HPWL/RSMT gate after necessary HPWL threshold is crossed | Repeated normalized score `>= 1.0` with identical hash |

## Current Boundary

The active boundary is native Cypress recovery. M336-118 remains the immutable
legal reference and optional warm start; M336-140 closes the last committed
exact-site milestone. The untracked `experiments/m336/guides/M336-141/` is
user-owned partial evidence and must not be modified, committed, or resumed.

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
