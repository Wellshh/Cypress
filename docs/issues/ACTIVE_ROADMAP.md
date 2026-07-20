# M336 Active Roadmap

**Updated:** 2026-07-20  
**Evidence through:** `M336-167`

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
| N3 (complete) | Make TOP/BOTTOM density respect conservative irregular usable capacity | M336-147 reduces 50-step projection events from 34 to 0; quality regresses and remains explicitly unaccepted |
| N4 (complete) | Preserve legal initial positions and bound E4 repair to illegal conflict closures | Warm preflight preserves 100/100; cold/warm 10-step matrices report every stage; bounded same-run E4 restore is exact legal |
| N5 (active) | Resolve the 50-step overlap, repair, determinism, and anchor-signal findings before the final matrix | M336-163 through M336-167 acceptance evidence, then exact E4 legality, native HPWL/RSMT, runtime, anchor metrics, hashes, and acceptance report |

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

M336-147 adds conservative TOP/BOTTOM capacity maps and a corrected density
partition containing only the 100 constrained movables while subtracting 40
frozen anchors/obstacles. In the seed-1000 50-step E2 diagnostic, projection
events fall from 34 to zero and overlap area falls by about 44%, but overlap
pairs increase from 65 to 66 and normalized native score falls from `0.611229`
to `0.609927`. This passes only the N3 projection-pressure signal gate. M336-148
allows explicitly finite high-overflow diagnostics to continue through exact
validation and native scoring while preserving production defaults. M336-149
resolves the infeasible `target_density=0.7` contract by freezing one explicit
`0.85` target across all E0-E4 tracks and failing closed if either conservative
side map remains infeasible. Fresh E4 evidence reports zero unavoidable
overflow floor on both sides.

M336-150 invalidates quality comparisons from existing native E2-E4 runs under
the active endpoint contract: those runs freeze both `EMI601` and `Q601` at
runtime coordinates. Their structural objective/backward/projection evidence
remains valid. M336-151 additionally records that the runner always loads the
artificial manual-baseline PL, so it has not yet executed either a true
cold/source track or an M336-118 checkpoint-warm track. N4 must close both
contracts before any new placement-quality acceptance decision.

M336-152 records that the native Bookshelf reader rounds source coordinates to
integer database units during global placement. A cold/source run must therefore
explicitly load the hashed float `m336.pl`; the raw PlaceDB is retained only as
a bounded quantization audit and must never redefine runtime `Q601`.

M336-153 closes a runner evidence gap: in-memory legality and `Final PPA` are
pre-serialization diagnostics only. Every promoted run must independently
reparse the emitted PL in float64, validate exact geometry, replay native
HPWL/FLUTE without coordinate drift, and include both replay costs in runtime.

M336-154 separates two previously conflated sources. The float `m336.pl` is the
cold initial placement, while native PlaceDB-aligned geometry remains the
authority for certified domains and runtime endpoints. Re-fitting geometry to
the float PL invalidated 64 warm-start components and is prohibited.

M336-155 identifies a second warm-start contract drift: the former runner
default differs from M336-118 in four page-7/page-86 subgroup assignments and
invalidates 45 otherwise certified components. All active native tracks now use
the assignment bundled with the checkpoint unless explicitly marked diagnostic.

M336-156 promotes the already certified float64 M336-118 reconstruction into
the portable checkpoint without overwriting the legacy rounded PL. Native warm
runs default to the manifested float64 asset; the rounded file remains audit
history only.

M336-150 through M336-156 are now resolved by fresh seed-1000 cold and warm
10-step E0-E4 matrices. They enforce manual `EMI601` plus runtime `Q601`, retain
the certified native alignment, use assignment SHA
`e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87`,
load the float64 checkpoint for warm runs, and independently validate and score
every serialized PL. Warm initialization preserves all 100 constrained
components; cold/source preserves four and repairs the measured 96-component
illegal/conflict closure.

M336-157 through M336-160 close the remaining N4 contract drift. The runner
defaults to the frozen `0.05 mm` grid with 89/89 cache hits; adaptive-anchor
downward anti-windup keeps the effective gradient ratio within its active ramp;
E4 restores a bounded same-run conflict closure rather than repacking it; and
the 2x runtime gate is evaluated only for checkpoint-warm summaries. In the
warm 10-step matrix, E4 executes 13 backward calls and 10 changing Adam steps,
ends 100/100 contained with zero overlaps, scores native HPWL/RSMT
`15632.260310/17328.977` (`0.928024` normalized), and takes `1.4775x` E0
end-to-end runtime. Anchor mean/p90 improve only `0.0071%/0.0026%` in E3 versus
E2, so N5 must diagnose the quality gate at the full 50-step budget before the
three-seed final matrix.

M336-161 and M336-162 close two feature-off regressions found by comparing the
native recovery branch directly with `f0e4cb9`. Side overflow again excludes
fillers exactly as legacy Cypress did, and M336-only Nesterov bootstrap/state
handling no longer affects ordinary runs. A deterministic 100-step CPU smoke
has byte-identical metric records after timing removal and identical placement
SHA-256 on both revisions. Both revisions retain the benchmark's pre-existing
high-overflow failure; this evidence proves no regression rather than a
successful tuned placement.

The first N5 seed-1000 50-step checkpoint-warm matrix exposes four active
algorithm gaps. E2/E3 remain fully contained with zero keep-in projections but
grow to 66/71 exact overlap pairs (M336-163). E3 improves anchor mean/p90 only
`0.0508%/0.0215%` over E2 despite 50 changing Adam steps and a controlled ratio
of `0.1` (M336-167). E4's 83-component closure exceeds the restore bound and
falls back to broad packing: HPWL rises by `1485.5859`, normalized score falls
to `0.850668`, and runtime reaches `3.3963x` E0 (M336-164).

The matching cold/source run completes E0/E2/E3, with E2/E3 scores near
`0.745`, but E4 fails closed before serialization when every deterministic
bounded-packing strategy rejects `MHC8602` (M336-165). Its CUDA logs also prove
that `deterministic_flag=1` is incomplete without an explicit
`CUBLAS_WORKSPACE_CONFIG` contract (M336-166). The final three-seed matrix is
blocked on these active findings; no checkpoint fallback or broad repair output
may be promoted as native Cypress evidence.

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
