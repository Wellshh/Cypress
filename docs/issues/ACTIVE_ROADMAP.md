# M336 Active Roadmap

**Updated:** 2026-07-21

**Evidence through:** `M336-188`

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
| N5 (blocked by N6) | Resolve the 50-step overlap, repair, determinism, and anchor-signal findings before the final matrix | M336-163 through M336-168 isolate accepted-step overlap growth as the upstream blocker; resume the remaining quality gates only after N6 passes |
| N6 (blocked by M336-188 E2 runtime) | Prevent native optimizer steps from crossing same-side footprint contacts | Preserve M336-188 legality/quality bytes and close the remaining `0.084045 s` E2 counted-path gap before another authorized D1 |

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
bounded-packing strategy rejects `MHC8602` (M336-165). Its CUDA logs also proved
that `deterministic_flag=1` was incomplete without an explicit
`CUBLAS_WORKSPACE_CONFIG` contract (M336-166).

M336-166 is resolved by freezing and recording
`CUBLAS_WORKSPACE_CONFIG=:4096:8` for every native subprocess. Two independent
10-step checkpoint-warm E3 seed-1000 runs on GPU 2 have identical placement and
replay SHA-256
`a6445d6a98180ff4449afdffe37ad313f5215cd336153030c5637aaa10b94c5c`,
HPWL `15632.686697721481`, FLUTE RSMT `17325.676`, legality metrics, and
normalized score `0.9281007794550066`; both execute 13 backward calls and 10
changing Adam steps without a CuBLAS determinism warning. Their 28 overlap pairs
remain unaccepted M336-163 evidence. The final three-seed matrix remains blocked
on M336-163 through M336-165 and M336-167; no checkpoint fallback or broad
repair output may be promoted as native Cypress evidence.

The M336-167 checkpoint-warm 50-step sweep tests the complete bounded ratio set
`0.05/0.10/0.25/0.50`. Effective lambda scales as requested and ratio `0.50`
gives the strongest response, but physical anchor mean/p90 improve only
`0.1364%/0.0997%` versus E2, far below `25%/15%`; projected-target mean/p90
improve only `0.4044%/0.1611%`. HPWL/RSMT improve by `3.987/16.836`, while exact
overlaps rise from 66 to 70. Larger ratios are not authorized by this evidence.
M336-167 now requires a serialized per-component feasible-domain lower bound to
separate unreachable anchors from optimizer displacement-scale failure.

M336-167 now emits that read-only lower bound in preflight and exact legality.
The independent footprint-aware floor is mean/p90 `4.402187/10.189970 mm`,
versus acceptance thresholds `4.886889/10.227884 mm`. The p90 gate therefore
has only `0.037914 mm` optimistic headroom before collisions. A 10-step replay
retains the exact M336-166 placement SHA, proving the diagnostic does not alter
the optimizer. The ratio ladder is closed and ratio `0.10` remains the default.

M336-168 records the next root cause. Across all four 50-step ratios, maximum
single-step proposal distance is `0.043936` Cypress units. Even summing that
maximum in a perfectly aligned direction yields only about `0.10985 mm`, while
the mean gate requires at least `1.628963 mm`, a `14.83x` deficit. Learning-rate
and cumulative/net displacement provenance must precede any bounded native
step-scale experiment. Exact repair cannot supply this displacement.

M336-168 now serializes that provenance without changing optimization. The
10-step control estimates LR `0.02308556` from configured `0.01`; constrained
mean accepted path/net displacement are only `0.01194159/0.01157887 mm`, a
`96.96%` net/path ratio. The byte-identical placement and native score rule out
instrumentation side effects and show that cancellation is not the immediate
cause. The committed 50-step control then measures constrained mean path/net at
only `0.05143600/0.05067488 mm` (`98.52%` efficiency), making the rigorous mean
displacement deficit `32.15x`. Only `6.53%` of net movement becomes anchor gain,
so bounded LR experiments must gate direction quality and overlap, not merely
produce larger steps.

The bounded runner control confirms scale `2` nearly doubles effective LR,
path, and net displacement and slightly improves native quality. It is rejected
because 10-step overlaps grow from 28 to 42 and projection events from zero to
three. Stop the `4/8/16/32` ladder and return to M336-163 footprint-scale
collision pressure; do not use E4 repair to conceal this regression.

M336-163 now has accepted-step exact observability. The unchanged scale-1
control crosses from 0 to 11 overlaps on step 1 and reaches 28 pairs,
`0.108631 mm2`, and a 45-component closure by step 10; overlap area rises at
every checkpoint while keep-in violations remain zero. The placement SHA is
unchanged, so the instrumentation is read-only. M336-169 proves the legacy
macro-overlap kernel cannot prevent this crossing; the next experiment must use
a nonzero-contact native collision signal, not a larger LR or E4 fallback.

M336-169 adds a default-off footprint-aware pre-contact barrier and preserves
the feature-off placement byte-for-byte. M336-170 adds a transactional exact
accepted-step guard that restores complete Adam/Nesterov state, applies bounded
learning-rate backoff, and fails closed without E4 or checkpoint fallback. Its
first ratio-`0.1` probe rejects all five step-1 attempts: overlap area falls from
`0.008031909` to `0.000501145 mm2`, but no positive step is legal. This proves
the guard works and isolates the remaining N6 defect to local collision-force
direction. Only bounded ratio checks at `0.25` and `0.5` are authorized before
replacing scalar global matching with pair-local contact-normal control.

M336-171 closes those bounded checks. Ratio `0.25` is effectively unchanged;
ratio `0.5` reduces the first/final crossing sets from 10/9 pairs to 7/6, but
all retries remain illegal and exactly rolled back. Global scalar matching is
now closed. N6 must instrument and control each local contact's predicted Adam
motion before repeating D1; LR, seed, scalar-ratio, and broad-repair ladders
remain prohibited.

M336-171 now has pair-local observability for the actual Adam proposal. At
ratio `0.1`, nine of ten retry-0 exact crossings move inward along the sampled
origin contact normal because the base objective exceeds local collision drive
by roughly `6x-45x`. `C8605/C8621` instead crosses under a tangential proposal:
its origin and proposal SDF clearance are unchanged and its origin-normal
displacement is zero. The next control must therefore handle shared-node
direction conflicts and nonsmooth contact cones; per-pair scalar escalation on
one nearest-face normal is insufficient. This diagnostic accepted no step and
does not close N6.

The pair trace is independently default-off. Disabling it preserves the exact
proposal/rollback canonical hash while reducing the one-step failure artifact
from `2,084,299` to `48,081` bytes; normal exact-guard runs therefore avoid the
extra gradient decomposition, field sampling, and pair JSON cost.

M336-171 now has a first bounded control result. A candidate-side exact contact
projector retains the actual Adam proposal but gives each newly crossing
contact component one shared displacement before guard acceptance. The first
checkpoint-warm E3 step closes ten crossings in seven components/17 nodes,
passes `100/100` containment with zero keep-in and overlap violations, and is
accepted without backoff. Native HPWL/RSMT improve from the M336-118 repeated
baseline `15634.450477/17333.037` to `15633.827651/17332.127`; normalized score
improves from `0.927850154` to `0.927893042`. The contact-off canonical failure
hash remains unchanged. This passes only the one-step signal: warm E2/E3 D1,
runtime, and repeated-hash gates remain open before N6 can close.

M336-171 now passes the complete warm scale-1 D1 three-arm gate on GPU 2. The
current-head feature-off arm reproduces the prior E3 placement byte-for-byte
and ends with 24/28 E2/E3 overlap pairs. Barrier-only ends with 33/33 pairs,
confirming that its lower overlap area is not exact legality. Candidate-side
contact projection plus the exact guard instead accepts ten native steps in
both E2 and E3 with 100/100 containment, zero keep-in violations, and zero
overlaps after every accepted step. E2 accepts all attempts; E3 rejects one
32-node stalled closure, restores position and Adam state, halves the LR, and
accepts the bounded retry. Native scores are `0.9280653090/0.9280508327`;
quality changes versus feature-off are within `0.013%` per HPWL/RSMT metric,
and GPU optimization costs are `1.675x/1.535x`, below the `2x` gate. E3 anchor
mean/p90 remain marginally worse than E2, so D2 is now the active boundary and
must stop after scale `2` if motion direction or pressure regresses.

M336-172 executes that single authorized scale-2 test and stops it before D3.
E2/E3 complete ten changing CUDA Adam steps with zero accepted overlap and
slightly better native HPWL/RSMT than D1. However, each run rejects three broad
contact candidates. Thirteen disconnected contact components contain 33/34
total nodes while no individual component exceeds five nodes, tripping the
global 32-node safety budget and backing LR from `0.04538150` down to
`0.00567269`. Hard keep-in projection rises from zero to two nodes and maximum
contact correction rises `1.968x`. Net displacement increases only
`0.190%/3.006%` for E2/E3, while E3 makes anchor mean/p90
`0.00211%/0.00436%` worse than same-run E2. D2 therefore fails pressure and
anchor-direction gates. Do not run D3, raise the node limit, or resume an LR,
ratio, seed, or E4-repair ladder; first reduce crossing support upstream under
an explicitly bounded local trust-region contract.

Code audit refines one part of M336-172: all six D2 limit failures contain
exactly 32 active nodes plus one or two inactive/frozen reference endpoints.
The projector changes only active nodes but previously charged inactive
authorities to the same cap. A default-off candidate now retains the global
32-active-node budget while reporting total/active and per-component scopes
separately. Focused CPU/GPU and existing guard, collision, baseline, and
reproducibility suites pass. This is an implementation signal only; one
post-fix D2 replay is required before N6 can advance, and a negative anchor
direction still stops D3 even if the false node-limit backoffs disappear.

The single post-fix D2 replay at `e99673f` confirms the implementation fix but
does not promote N6. A 33-total/32-active closure now converges and is accepted,
while later proposals expose the real boundary: E2 reaches 33/34 active nodes
and E3 reaches 33, so the unchanged 32-active-node cap correctly rejects eight
attempts. All accepted steps and final placements remain exact legal, and D1
HPWL/RSMT improve, but E3 still worsens anchor mean/p90 versus E2 by
`0.010171%/0.015043%`. Final accepted LR falls to `0.00283634/0.00141817` for
E2/E3. D2 therefore still fails active-scope and anchor-direction gates. Keep
D3 prohibited and do not raise the cap; reduce simultaneous native crossing
support or add a bounded deterministic local trust region before one further
D2 authorization.

M336-173 identifies a separate anchor-control defect in the same E3 evidence.
The default five-iteration refresh stores the iteration-0 wirelength gradient
of `5.831255`, although the current value falls to about `0.3809` from iteration
1 onward. When the ramp becomes nonzero at iterations 2-4, reported ratios of
`0.01/0.02/0.03` correspond to current ratio proxies of
`0.1531/0.3061/0.4592`; E3 begins its earlier active-scope failures in that
window. This is correlation, not yet an effect claim. Freeze D3 and all scalar
ladders; first make the M336 schedule explicit, refresh every accepted short-run
iteration, report gradient age honestly, and validate the controller before
requesting one further D2 replay.

The M336-173 implementation candidate keeps the generic interval-5 default but
explicitly serializes interval `1`, EMA `0.8`, warm-up `2`, ramp `10`, and the
existing bounds for M336 E1-E4. Controller evidence now carries gradient age
and an explicit current-versus-last-refresh ratio basis. A synthetic 15x norm
drop and installed-module anchor/config/reproducibility/contact/guard suites all
pass. This is not a promotion result: do not run another D2 until its gates are
authorized, and do not use the schedule fix to relax the genuine 32-active-node
boundary found by M336-172.

M336-174 separates broad native contact pressure from the actual bounded
consensus intervention. Current all-active components average and overwrite
every member proposal, so the 32-node endpoint pre-check also charges one node
that could remain at its native proposal in every disconnected component. In
the M336-172 artifact, active endpoint counts reach `34`, while a static
one-representative-per-component estimate reaches only `22`; this estimate is
not replay or promotion evidence. The proposed invariant retains the numeric
cap at 32 but applies it to the cumulative union of active IDs selected for
consensus writes across all closure iterations. Endpoint counts remain an
independent pressure metric, inactive-authority components charge every active
member, and cap checks occur before mutation. Implement and test this contract,
then requalify D1 before the one predeclared D2 replay. D3 remains prohibited.

The M336-174 implementation candidate now enforces that cumulative union before
mutation. Each all-active component retains a deterministic proposal-medoid;
inactive-authority components still charge every active member, and a later
component merge cannot reset previously corrected IDs. Separate endpoint,
selected, cumulative, consensus, and hard-projection metrics preserve the broad
pressure signal. Projector, guard, M336 baseline/config, reproducibility,
anchor/keep-in/collision, and irregular-density suites pass 203 focused tests,
including float32/float64 CPU/GPU identity and source/install parity. The
aggregate runner's independent ten-error/zero-exit defect is tracked as
TEST-001 and is not called a pass. This candidate has no effect evidence yet;
rerun D1 before any D2 attempt, and keep D3 prohibited.

The post-implementation M336-174 D1 replay at `0d2cae5` passes its declared
scale-1 gate. E2 and E3 each execute 13 backward calls and ten changing CUDA
Adam steps, accept all ten proposals without backoff, preserve the initial
`0.0230855606` learning rate, and finish 100/100 contained with zero keep-in
violations and overlaps. Maximum active endpoint pressure is `37/44`, while
the separately bounded cumulative correction scopes are only `24/26`; the cap
remains 32. Relative to the retained feature-off controls, HPWL regressions are
`0.000810%/0.002126%`, RSMT regressions are `0.007053%/0.014608%`, and GPU
runtime ratios are `1.686x/1.590x`, within the `0.5%` and `2x` gates. E3 also
has strictly lower anchor mean and p90 than E2, although only by
`0.001833%/0.000475%`. This authorizes exactly one predeclared scale-2 D2
replay; it does not promote N6 or authorize D3.

M336-175 records an independent evidence-routing defect exposed by that run.
`--output-dir` scopes per-arm artifacts but not the top-level summary/report;
without explicit path flags, the runner overwrites `results/m336/summary.json`
and `results/m336/REPORT.md`. The D1 files were verified against commit and
run IDs, then archived byte-identically under their run root. Until the default
is fixed, all future promoted commands must pass both `--summary-path` and
`--report-path`.

The single M336-174 scale-2 D2 replay at `d4fddbb` fails its conjunction of
predeclared gates, so D3 remains prohibited. E2/E3 each execute ten changing
CUDA Adam steps and finish exact legal, but one iteration-7 proposal per arm
has 51 active contact endpoints and requires 33 cumulative corrections. The
unchanged cap rejects it transactionally and halves LR from `0.0453815013` to
`0.0226907507`. Maximum applied correction is `0.00642050 mm`, below its `2x`
D1 ceiling, and net motion rises `69.81%/106.93%` over M336-171 D1. Per-step
anchor refresh is current and E3 improves anchor mean/p90 over E2, resolving
M336-173's stale-ratio defect. However, HPWL regresses from matching current D1
by `0.087139/0.086948` for E2/E3 even though RSMT improves. The true
correction-scope failure and HPWL failure keep M336-172/M336-174 open. Do not
run D3, raise the cap, or start another seed/LR/ratio/E4 ladder.

M336-176 isolates excess control inside the remaining bounded contact path.
Across all 20 D1 proposals, rigid representative consensus selects 333 initial
corrections while exact active vertex covers require at least 283; across all
22 D2 proposals, the corresponding counts are 471 and 392. Every proposal has
a positive reduction, and the rejected D2 proposal starts at `28 -> 23`.
These are graph intervention lower bounds, not legal replays: rolling back one
covered endpoint can leave or expose an exact footprint crossing. The next
default-off candidate must therefore restore a deterministic minimum cover to
the same step's accepted position, exact-validate iteratively, retain a
cumulative 32-ID union, and fail closed on bounded-search or closure failure.
No effect run is authorized before issue/implementation push-pull and focused
source/install tests. Then rerun only scale-1 E2/E3 D1; D2 and D3 remain blocked
until that complete conjunctive gate passes.

The M336-176 implementation candidate now provides that default-off bounded
rollback mode. Exact subset enumeration is capped at 16 nodes per current
component, rollback targets only the same step's accepted origin, every write
is followed by hard projection and exact validation, and the cumulative union
is checked against 32 before mutation. Runner configs, resume checks, run IDs,
reproduction commands, and summaries preserve the mode and bound. Installed
projector, guard, M336 config, reproducibility, anchor/collision, and density
suites pass 215 focused tests with zero source/install drift. The aggregate
runner repeats TEST-001's same ten independent errors across 244 tests and is
not called green. This remains implementation evidence: commit/push/pull it,
then run only the predeclared scale-1 E2/E3 D1.

The post-implementation M336-176 D1 replay at `8446b28` stops the candidate.
E2/E3 prove the native CUDA chain, ten changing Adam steps, exact legality, and
zero-drift float64 serialization. Every initial proposal uses a smaller cover
than rigid consensus (`114/134` E2 writes and `151/175` E3 writes), maximum
applied scope is `27/32`, largest component is four under the 16-node bound,
and maximum correction falls to `0.00163210 mm`. GPU and end-to-end ratios stay
below `2x`. The effect gate still fails: RSMT regresses from matching M336-174
D1 by `0.570/0.821`, while E3 anchor mean/p90 are `0.001386%/0.002038%` worse
than E2. Two E3 proposals also require `38` and `33` cumulative writes and are
transactionally rejected before a quarter-LR retry succeeds. First-pass graph
savings therefore do not survive closure as qualifying quality. Keep M336-176
open and do not run D2, D3, E4, CP-SAT, fallback, or parameter ladders.

M336-177 identifies the mechanism behind that failure. For accepted proposals,
minimum-cover rollback grows from `114 -> 233` E2 writes and `117 -> 244` E3
writes after exact closure; each final scope is larger than the matching
first-pass rigid scope. On the paired first proposal, eight origin rollbacks
leave the retained peer proposals overlapping, so closure restores the other
nine endpoints and discards all 17 native motions. The old rigid mode needs ten
writes because it preserves one optimizer-produced displacement authority per
component. The next default-off candidate must search only bounded assignments
of those current proposal authorities, exact-check each small component, retain
the cumulative 32-ID cap, and fail closed on component or state limits. No M336
effect run is authorized before issue/implementation push-pull and installed
tests; afterward run only the predeclared scale-1 D1.

The M336-177 implementation candidate now searches only dtype-preserved
displacements produced by the current native proposal. Each bounded component
assignment passes through the same footprint-aware `RegionProjector` domains on
scratch coordinates and exact pair geometry before selection; a runtime
projection mismatch restores the candidate and fails closed. Component and
state limits remain 16 and 4,096, the cumulative correction cap remains 32, and
the new state parameter is absent from old-mode configs and summaries. Paired
pre-change fixtures prove stable non-timing output and coordinate identity for
both historical modes. Installed projector, guard, M336 config,
reproducibility, anchor/collision, and density suites pass 231 focused tests
with source/install hash parity. The aggregate runner independently repeats
TEST-001's ten errors across 260 tests and is not green. This is implementation
evidence only: sign, commit, push, and pull it before running exactly the
predeclared scale-1 E2/E3 D1; D2, D3, E4, fallback, CP-SAT, and parameter
ladders remain prohibited.

The post-implementation M336-177 D1 replay at `48b5cdd` stops the candidate.
Both arms prove the complete native CUDA chain, ten changing Adam steps, exact
legality after every accepted step, and zero-drift float64 serialization. The
new search is effective at its narrow purpose: accepted correction writes fall
to `74/75` for E2/E3, versus matching rigid counterfactuals of `85/86` and the
separate M336-174 ceilings of `181/184`; real accepted components use multiple
proposal authorities, and maximum correction remains `0.003263852 mm`.
However, nine proposals per arm reach the eight-pass closure limit before a
bounded retry succeeds. GPU optimization rises to `3.872x/3.151x` the
M336-171 feature-off controls. E2/E3 HPWL regress from matching M336-174 D1 by
`0.122776/0.213276`, and RSMT by `1.310/1.373`. E3 anchor mean and p90 are
strictly lower than E2, but only by `0.0001312%/0.0000286%`. The conjunctive D1
gate therefore fails. Do not run D2, D3, E4, fallback, CP-SAT, cap changes, or
parameter ladders; a successor must first address bounded closure convergence,
runtime, and quality under a new reviewed contract.

M336-178 isolates the closure failure exactly. All `18/18` rejected M336-177
attempts alternate `C8608/C8619` and `C8619/U8601` until the eight-pass limit,
then retain `C8619/U8601` as the sole residual overlap. The implementation
records both edges in `protected_edges` but plans and validates only
`current_edges`, so restoring `C8619` to its zero-correction native proposal
deterministically reopens the prior inactive contact. The next default-off mode
must replan only protected components touched by a current edge while validating
all historical edges in that closure. The observed three-node expansion has at
most nine assignments and needs no cap increase. Commit/push/pull the issue and
implementation separately, preserve all old modes, and then run only the
predeclared scale-1 D1. No parameter ladder or larger experiment is authorized.

The M336-178 implementation candidate adds a separate default-off protected
authority mode without changing historical modes. Its append-only graph
replans only protected components touched by current residual contacts and
validates every historical edge in each affected closure; reopening any such
edge fails closed. Synthetic coverage now includes the original three-node
cycle, a bridge that merges two protected components without resetting
cumulative IDs, unrelated-component isolation, fail-before-write cap checks,
and CPU/GPU identity. Installed-tree suites pass `238/238` focused tests with
source/install parity. The aggregate entrypoint repeats TEST-001's ten known
errors across `267` tests and is not green. This remains implementation-only
evidence: commit, push, and pull it before the one authorized D1; all larger
runs and tuning remain prohibited.

The only authorized M336-178 D1 at `f56fb09` proves the closure correction but
fails the conjunctive promotion gate. E2/E3 each accept all ten first attempts,
remain exact legal through zero-drift serialization, and never reopen or repeat
a protected edge. Six closures per arm jointly validate the real
`C8608/C8619/U8601` chain. Writes are `155/158`, below matching rigid
`166/166` and M336-174 `181/184`; HPWL improves in both arms and E3 retains a
positive anchor direction. E2 nevertheless regresses M336-174 RSMT by `0.547`
and takes `2.414253x` the M336-171 feature-off GPU time. E3 passes those two
gates. Therefore no D2, D3, E4, fallback, CP-SAT, cap change, or parameter
ladder is authorized.

M336-179 isolates the runtime blocker. Protected search exactly tests 2,051 E2
authority states and consumes `1.257221 s` in contact projection, versus
`0.529680 s` for M336-174 rigid projection. Any optimization must preserve the
exhaustive winner byte-for-byte and distinguish logical, evaluated, and proven
pruned states. M336-180 isolates the quality blocker: offline native per-net
replay exactly reproduces the aggregate and attributes `+1.127` RSMT to the
84-pin `GND` net while its HPWL is unchanged. A reviewed native-Cypress design
must address this discrete topology signal without checkpoint fallback or
exact-site optimization. Wait for both candidates, then run one combined D1.

M336-181 and M336-182 now define those candidates without effect claims.
M336-181 factors the exact authority proof into node/authority projection and
protected-edge compatibility while requiring a final full validation and
byte-identical exhaustive winner. M336-182 rejects local C502, median-star, and
rectilinear-MST proxies after offline artifact replay. Its replacement is a
default-off global tie-break between at most two plans derived from the same
native proposal; high-degree HPWL is primary and native FLUTE breaks only an
HPWL-neutral topology tie. At that review point the implementations, installed
tests, and one combined D1 were pending. No larger run was authorized.

Both candidates are now implemented and installed without an M336 effect run.
M336-181 retains exhaustive search as the default and exposes an explicit
pairwise-factorized strategy whose random, cycle, protected-merge, inactive,
hard-projection, dtype, and CPU/GPU fixtures select the exhaustive winner
byte-for-byte. Direct `HEAD`/current replay across all four historical modes
passes 16/16 coordinate and non-timing comparisons. M336-182 compares no more
than two proposal-derived candidates and uses native FLUTE only after
selected-net HPWL ties. Native `PlaceDB` deduplicates GND from 114 raw pin rows
to runtime `net_id=6`, degree 84; with threshold 32 and ignore limit 100 it is
the only selected net. A real five-pin native fixture proves equal HPWL `8/8`
and distinct FLUTE `9/8` select the lower-RSMT candidate. Applicable installed
tests pass `247/247`; five optional OR-Tools tests remain unavailable and are
not reported green. The single combined scale-1 checkpoint-warm E2/E3 D1 is
the next and only authorized effect run after signed commit, push, and pull.

M336-183 records the first combined-D1 stop. E2 completed ten native CUDA
steps and exact validation, but its scoring-only config disabled contact
projection while retaining the dependent topology tie-break. `NonLinearPlace`
correctly failed closed during float64 replay, so E3 did not run and the
attempt is not promotable. The isolation fix resets all contact dependants for
scoring. Partial timing remains actionable but is not a D1 pass: factorization
reduced E2 GPU time from `2.609474063 s` to `2.346527902 s` (`10.08%`), still
`8.55%` above the fixed `2.161724 s` gate. Do not resume the aborted output; a
fresh effect run requires explicit authorization after the fix is pushed and
pulled.

The isolated fixed scorer replays identical float64 placement bytes with zero
coordinate error and reports HPWL `15632.948904753`, RSMT `17327.972`. Those
pass the M336-174 E2 quality sub-gates, so M336-180's direction is supported,
but the result remains diagnostic: it cannot supply missing E3 evidence or
override the failed E2 runtime gate.

M336-184 isolates the next runtime-only implementation candidate. The contact
projector already validates initial and converged coordinates, but the exact
step guard repeats proposal and accepted validation on identical bytes. In the
M336-183 trace those two guard stages cost `0.244548114 s`, larger than the
remaining `0.184803902 s` E2 gap. Any cache must carry exact tensor provenance,
be single-use, fail closed on mismatch, and preserve normal validation whenever
board/region projection changes the proposal. This is a design opportunity,
not authorization for another effect run.

That strict-equivalence candidate is now implemented for the M336-181
`pairwise_factorized` path only. Contact provenance is published only after
convergence, consumed once, and reused only after shape, dtype, device, and
exact tensor checks. A mismatched cache rolls back the full optimizer
transaction. Integrated fixtures reduce a matching guarded step from five
global validator calls to three and preserve fresh proposal validation after a
board/region coordinate change. Applicable installed/source tests pass
`257/257`; five optional OR-Tools tests were excluded and no CP-SAT solve was
run. This closes the implementation proof, not the runtime issue: no new D1 or
other M336 effect was run, and the fixed E2/E3 gates remain pending explicit
authorization.

M336-185 corrects the timing interpretation before another effect run. The
M336-183 raw optimization window is `2.635054652 s`; the reported
`2.346527902 s` GPU metric already subtracts `0.275603049 s` of guard overhead
and `0.012923701 s` of overlap diagnostics. M336-184's duplicated
`0.244548114 s` lies inside that excluded guard bucket, so it can improve
end-to-end time but cannot algebraically close the counted `0.184803902 s` E2
GPU gap. The counted profile is instead dominated by `1.047041154 s` of
optimizer attempts, including `0.943923393 s` of contact projection. Do not
reclassify timing or launch D1 based only on M336-184; first define and
parity-test a strict-equivalent optimization inside the counted path, or obtain
explicit authorization for a measurement-only replay.

The accounting implementation now emits raw wall, total exclusions, overlap
diagnostics, guard overhead, guarded optimizer attempts, contact projection,
and the fixed GPU metric from one fail-closed identity. A fixture using the
M336-183 constants reproduces `2.3465279024094343 s` exactly and rejects
impossible nesting. Applicable tests pass `258/258`; no timing work moved
outside the measured window and no M336 effect ran. Offline serialization of
the duplicated guard evidence costs only about `33 ms`, so compact logging is
not a credible substitute for the `184.8 ms` counted-path gap. The preserved
profile instead directs the next review to exact contact validation.

M336-186 identifies a strict-equivalent counted-path candidate. Each global
exact audit reads 100 constrained and 40 obstacle nodes through 280 individual
`detach().cpu()` scalar conversions. The M336-183 contact path calls that audit
27 times, accounting for 7,560 scalar synchronizations and
`0.332145968 s`. An isolated 140-node float32 probe measures `4.203 ms` per
scalar extraction versus `0.047 ms` for one batched H100 transfer (`88.9x`),
with an optimistic 27-call saving near `0.112 s`. Because that is only about
61% of the counted gap, the reviewed candidate also caches fixed footprints
and STRtrees under an exact coordinate/PlaceDB key while rebuilding all moving
constrained geometry. No approximation, timing reclassification, or effect run
is authorized.

That candidate is now implemented without effect evidence. One dtype-preserving
host snapshot replaces per-coordinate device synchronization; fixed footprints
and side-local STRtrees are reused only under a byte-exact key that retains and
identity-checks the PlaceDB, while all constrained geometry remains fresh.
Native diagnostics expose calls, snapshot time, cache hits/misses, and total
audit time without moving the M336-185 timing boundary. CPU/H100 float32/64
fixtures preserve sorted report bytes across legal, keep-in, constrained-pair,
and fixed-obstacle cases; fixed-coordinate invalidation matches a fresh
context. Applicable installed/source tests pass `260/260`, excluding five
optional OR-Tools tests. A combined scale-1 D1 remains unauthorized until the
user explicitly resets or approves it.

M336-187 profiles the residual exact-audit path before authorizing D1. On the
real fixed 100-constrained/40-obstacle M336-183 placement, M336-186 reduces the
old scalar/rebuild audit from `11.153275 ms` to `5.925002 ms` median (`1.88x`),
an optimistic `0.141163 s` over 27 calls but still short of the fixed GPU gap.
The residual cost is dominated by 100 scalar Shapely translations,
differences, and tree queries per audit. A read-only vectorized Shapely 2.1.2
prototype preserves serialized reports across legal, keep-in, constrained-pair,
and fixed-obstacle cases while reducing current audit time from `6.053330 ms`
to `2.209201 ms` (`2.74x`), an additional projected `0.103791 s`. This is a
material strict-equivalence candidate, not effect evidence. Commit/push/pull
the issue and implementation separately; a combined scale-1 D1 remains
unauthorized until the user explicitly resets or approves it.

The M336-187 production implementation now batches those exact GEOS operations
without caching any translated constrained geometry. Read-only local templates
remain byte-stable, fixed shape arrays stay under the M336-186 exact cache key,
and native diagnostics expose every batch phase. A 27-scenario synthetic
differential corpus and 204 real M336 CPU/H100 float32/64 comparisons match the
scalar report and repair closure exactly. The production fixed-placement
benchmark improves `6.095795 ms` to `2.156656 ms` per audit (`2.83x`), an
additional projected `0.106357 s` over 27 calls. Applicable tests pass
`263/263`, excluding five optional OR-Tools tests. This closes implementation
and offline performance evidence only; D1 and all larger effects remain
unauthorized until explicit user approval.

M336-188 records the explicitly authorized fresh combined scale-1 D1 at
`7c03b8c`. Both E2 and E3 execute 13 backward calls and ten changing CUDA Adam
steps, accept every proposal without retry, preserve every protected edge, and
finish 100/100 contained with zero keep-in violations and overlaps. Float64
replay has zero coordinate drift. E2 is byte-identical to M336-183 and passes
its HPWL/RSMT sub-gates; E3 improves HPWL/RSMT and has a strictly positive but
tiny anchor direction. M336-187 reduces E2 GPU time from `2.346527902 s` to
`2.245768752 s`, but the unchanged limit is `2.161724 s`; the conjunctive D1
therefore fails by `0.084044752 s` (`3.887858%`). The residual exact-audit
profile attributes `0.166264551 s` of its `0.198150292 s` to batched keep-in
difference/area work. Profile and parity-test a strict covered-by fast path
before requesting another D1. D2, D3, E4, reruns, tuning, fallback, repair, and
CP-SAT remain prohibited.

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
