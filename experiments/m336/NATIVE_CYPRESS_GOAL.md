# M336 Native Cypress Recovery — Durable Goal

Repository: `Wellshh/Cypress`  
Branch: `experiment`  
Current implementation reference head: `3442dc6` (`M336-192`)
Primary board: `M336`

## Objective

Move the M336 project’s active optimization path from the offline exact-site
CP-SAT reference optimizer to Cypress/DREAMPlace’s native GPU global-placement
pipeline.

The task is successful only when actual runs execute:

```text
dreamplace/NonLinearPlace.py
  -> dreamplace/PlaceObj.py
  -> differentiable wirelength/density/anchor/keep-in/collision objectives
  -> CUDA/PyTorch backward
  -> optimizer updates
  -> explicit hard projection and accepted-step checks
  -> exact validation
  -> native HPWL and FLUTE RSMT scoring
```

The existing exact-site assets remain immutable diagnostic references, optional
warm starts, validators, and bounded E4 repair aids. They must not remain the
primary optimizer, must not be used as a fallback output when native placement
fails, and must not be presented as evidence that Cypress itself improved.

## Frozen factual baseline

- M336-118 remains the accepted exact-legal reference checkpoint.
- Repeated float-preserving native evaluation reports HPWL
  `15634.45047733283`, FLUTE RSMT `17333.037`, and normalized score
  `0.9278501538723687`.
- M336-140 is the final committed exact-site quality milestone; that search
  track remains paused.
- `experiments/m336/guides/M336-141/` is user-owned partial evidence. Preserve
  it exactly; do not delete, overwrite, commit, or resume its pair scan.
- Objective purity, explicit projection, differentiable keep-in margin,
  subgroup-balanced adaptive anchor control, irregular side-specific density,
  float64 native scoring, cold/warm tracks, bounded repair, and deterministic
  CuBLAS execution are implemented and retained.
- Before M336-171, a legal checkpoint-warm placement developed `66/71`
  same-side overlap pairs after 50 native E2/E3 steps. Unguarded learning-rate
  scale `2` increased 10-step overlaps from `28` to `42`. D2 may repeat scale
  `2` once under the new contact-projection and exact-guard contract; larger LR
  and anchor-ratio ladders remain prohibited.
- M336-171 passes the warm scale-1 D1 gate: E2/E3 each complete ten changing
  CUDA Adam steps with zero overlap after every accepted step. Candidate-side
  contact projection plus the exact guard costs `1.675x/1.535x` the matching
  feature-off GPU optimization path and stays within the `0.5%` HPWL/RSMT
  quality gate. This authorized exactly one D2 scale-2 probe.
- M336-172 stops D2 after its single authorized scale-2 run. Exact accepted
  positions remain legal and native quality improves slightly, but both E2/E3
  hit the global 32-node contact budget three times, finish at LR
  `0.00567269`, and E3 worsens anchor mean/p90 versus E2. D3 is blocked until
  broad crossing support is reduced without increasing the safety budget.
- M336-192 preserves a strict protected-authority, pairwise-factorized,
  HPWL-neutral native-FLUTE reference path with exact covered-region and
  provenance-bound incremental validation. Its quality and legality pass, but
  E2 remains above the unchanged `2x` runtime gate. The strict implementation
  is retained as evidence, not promoted by relaxing that gate.

## Required native-algorithm outcomes

1. Preserve the reproducible native GPU and native HPWL/RSMT scoring contract.
2. Keep `PlaceObj.obj_fn()` pure with projection only at explicit optimizer and
   line-search boundaries.
3. Retain the differentiable interior keep-in margin as a stabilization signal,
   with hard projection as the final region guarantee.
4. Keep anchor attraction subgroup-balanced, scheduled, bounded, and observable.
5. Keep TOP/BOTTOM density aware of conservative irregular usable capacity.
6. Prevent a legal native placement from developing same-side footprint
   overlaps during accepted optimizer steps.
7. Preserve legal warm starts and repair only small measured illegal/conflicting
   closures; never repack the full constrained placement by default.
8. Separate preprocessing, cache, initialization, GPU optimization, validation,
   repair, serialization, and native scoring in runtime reports.
9. Run the final cold/warm E0-E4 matrix only after the native overlap gate passes.

## Current architecture: option 1 production consensus

The human architecture decision in M336-193 replaces the experiment sequence
in the historical N6 section below. It does not weaken exact legality or the
fixed `2x` runtime threshold.

Every new M336 contact-protected run must select one named policy:

| Policy | Contract | Availability |
| --- | --- | --- |
| `strict_reference` | M336-192 protected proposal authority, pairwise-factorized enumeration, and HPWL-neutral native-FLUTE tie-break | Preserved and default off |
| `consensus_per_step` | M336-174 deterministic proposal-medoid/component-consensus at every optimizer step | Production Phase A |
| `consensus_plus_stage_micro` | Per-step consensus plus at most one bounded stage-end micro closure | Reserved and fail closed pending D3 evidence |

All policies retain board projection, footprint-aware irregular Keep-in
projection, the exact accepted-step guard, full Adam/Nesterov state rollback,
and bounded LR backoff. Every accepted optimizer position must have zero
positive-area same-side overlap. `strict_reference` tests, diagnostics, exact
audits, timing accounting, and source/install parity remain mandatory.

### Phase A: one production-policy D1

After the M336-193 specification and implementation are separately committed,
pushed, pulled, installed, and tested, run exactly one fresh checkpoint-warm
scale-1 E2/E3 comparison on physical GPU 2, seed `1000`, for ten iterations.
Use `consensus_per_step`; authority enumeration and FLUTE must be absent from
the optimizer hot loop.

Promotion requires both E2 and E3 to satisfy all of the following:

- ten changing CUDA Adam steps with objective, backward, and optimizer proof;
- zero overlap after every accepted step, `100/100` containment, and zero
  Keep-in violations;
- native HPWL and FLUTE RSMT regression no greater than `0.5%`;
- GPU optimization and end-to-end ratios no greater than `2x` under the fixed
  current comparison;
- non-negative E3 anchor direction versus E2.

Do not run D2, E4 repair, CP-SAT, fallback, broad legalization, a resume, or any
seed, LR, anchor, or collision ladder. Do not alter timing boundaries or the
baseline to pass the first comparison. Paired repeated timing on the same GPU
is required only after a passing candidate exists, with the same `2x` gate.

### Phase A result: passed at M336-193

Commit `42b2470` passes the single authorized checkpoint-warm scale-1 E2/E3
D1. Both arms execute ten changing CUDA Adam steps, accept every first
proposal, and remain `100/100` contained with zero Keep-in violations and zero
overlap after every accepted step. `consensus_per_step` records zero authority
states and zero topology tie-break records.

E2/E3 GPU ratios against the fixed M336-171 feature-off controls are
`1.553746x/1.286047x`; end-to-end ratios are `1.192412x/1.196838x`. HPWL and
RSMT regressions remain below `0.5%`, and E3 anchor mean/p90 both improve
slightly versus E2. The placement hashes and native scores exactly reproduce
M336-174. One 50-step scale-1 E2/E3 D3 is now authorized after this evidence
commit is pushed and pulled. D2 remains prohibited.

### Conditional D3

Only a complete Phase A pass authorizes one checkpoint-warm 50-step scale-1
E2/E3 D3. Skip scale-2 D2. D3 must preserve zero overlap for every accepted
step and must not depend on broad E4 repair.

Only if that D3 isolates a local discrete contact-topology or RSMT defect may
`consensus_plus_stage_micro` be implemented. The future call is limited to once
per GP stage, contact-touched closures, at most 16 active nodes per component,
and at most 32 active nodes total. It may not use broad packing, checkpoint
fallback, or full-domain CP-SAT. Selection is lexicographic: exact legality,
selected-net HPWL, HPWL-neutral FLUTE RSMT, native displacement, then anchor
distance. An illegal or regressing candidate is a no-op. Its runtime is
reported separately while end-to-end remains within `2x`.

## Historical N6 development contract

The following N6 design and D1-D5 sequence records the path through M336-192.
It is retained for audit context only. Where it calls for scale-2 D2, E4, or a
different promotion order, the M336-193 option-1 contract above supersedes it.

The next critical step is to solve M336-163 upstream. Increasing learning rate,
anchor weight, E4 repair scope, density bins, or CP-SAT effort before this gate
passes is out of scope.

### A. Add a differentiable pre-contact footprint barrier

Implement a default-off, side-specific collision objective for constrained
movable components. It must become nonzero before positive-area contact, so a
legal placement receives an avoidance gradient rather than waiting until two
footprints already overlap.

Preferred footprint-aware construction for the fixed-orientation M336 phase:

1. Rasterize each unique local footprint conservatively on an explicit
   `collision_grid_mm`, initially `0.05 mm`.
2. For each unique same-side footprint-pair class, build the relative-center
   configuration-space collision mask using binary mask correlation/convolution.
3. Convert that mask into a signed or outside-clearance distance field and cache
   it by footprint hashes, side, grid, margin, and orientation.
4. Build a conservative same-side broadphase pair list using expanded AABBs and
   a skin at least equal to collision margin plus the maximum allowed proposal
   distance. Refresh the list at explicit accepted-step boundaries.
5. In `forward()`, sample only PyTorch tensors on the active device, preferably
   with `grid_sample`, using the relative component-center vector. Do not call
   Shapely, NumPy geometry, `.cpu()`, or detached collision decisions in the
   autograd path.

For pair clearance `d_ij`, positive outside the collision configuration and
negative inside it, use a barrier of the form:

```text
L_collision = mean(softplus((collision_margin - d_ij) / tau)^2)
```

Requirements:

- Handle concave footprints and unequal component dimensions to the declared
  raster tolerance; an AABB-only objective is not sufficient as the final
  implementation.
- Use separate TOP and BOTTOM pair sets.
- Exclude frozen/fixed pairs from trainable pair-pair loss, while retaining them
  as fixed-obstacle barriers for movable components.
- Cache repeated footprint-pair fields; do not build O(N²) geometry during every
  objective call.
- Add bounded, accepted-iteration weight control with serialized raw gradient
  norms, effective weight, active pair count, minimum clearance, and loss.
- E2 and E3 must use identical collision settings; anchor loss remains their
  only behavioral difference.

### B. Add an exact accepted-step overlap guard

A differentiable approximation is not the final legality guarantee. After every
optimizer proposal and keep-in projection, run a bounded exact same-side
broadphase/narrowphase check outside autograd.

For a run whose accepted starting position has zero exact overlaps:

```text
an accepted step must also have zero positive-area same-side overlaps
```

If a candidate crosses the collision boundary:

1. reject the candidate;
2. restore the complete pre-step position;
3. restore the optimizer state, including Adam moments or Nesterov histories;
4. reduce the current learning rate by a configurable backoff, initially `0.5`;
5. retry the native step up to a small explicit limit, initially `4`;
6. fail closed with a structured artifact if no legal native step is found.

Do not clear only selected momentum entries after a rejected step; the rejected
optimizer transition must be rolled back consistently. The guard is a native
trust-region/acceptance mechanism, not a legalizer and not a checkpoint
fallback.

Serialize for every accepted or rejected attempt:

- step and retry index;
- requested/effective LR;
- exact overlap pair count and area before/proposal/accepted;
- first newly crossing pairs and their areas;
- collision-barrier value, minimum clearance, and gradient norm;
- proposal, accepted-path, and net displacement;
- rollback and optimizer-state restoration status.

### C. Tests required before GPU experiments

Add focused CPU tests and GPU tests where available:

1. configuration-space mask agrees with exact Shapely collision decisions on
   contact, separation, and penetration samples;
2. pair field is symmetric under component-order reversal;
3. gradient descent points toward increasing clearance near every tested side;
4. concave and unequal-footprint cases have no false-negative collision cells;
5. broadphase includes every pair within margin plus skin;
6. forward performs no runtime geometry calls or device transfers;
7. exact accepted-step guard rejects a crossing proposal;
8. Adam and Nesterov position/state rollback is byte-consistent;
9. feature-off objective, placement, and legacy benchmark metrics remain
   byte-identical to the `f0e4cb9` contract;
10. repeated deterministic CUDA runs retain identical hashes and native scores.

### D. Experiment sequence and promotion gates

Run only seed `1000` until every gate below passes.

#### D1 — warm 10-step collision smoke (passed at M336-171)

Run checkpoint-warm E2 and E3 with LR scale `1`:

```text
collision feature off
collision barrier only
collision barrier + exact step guard
```

Promotion requirements:

- `100/100` contained and zero keep-in violations;
- zero exact overlap after every accepted step for barrier+guard;
- finite objective and gradients;
- no broad E4 repair;
- native HPWL/RSMT regression no worse than `0.5%` versus the same-run
  feature-off control;
- per-step overhead reported and no more than `2x` before optimization work is
  expanded.

#### D2 — bounded motion recovery (blocked by M336-172)

Only after D1 passes, repeat warm E2/E3 at learning-rate scale `2`.

Promotion requirements:

- zero accepted-step overlaps;
- projection pressure does not exceed the scale-1 control materially;
- native score does not regress;
- constrained net displacement increases without handing a large closure to E4;
- anchor mean and p90 move in the intended direction.

Do not run scales `4/8/16/32` unless scale `2` passes all gates.

#### D3 — warm 50-step diagnostic

Run E2, E3, and E4 at the selected safe scale.

Promotion requirements:

- E2/E3 remain zero-overlap throughout accepted steps;
- E4 repair is a no-op or a measured local closure of at most `16` components;
- E4 exact legality is `100/100`, zero keep-in violations, zero overlaps;
- repair HPWL degradation is at most `0.5%` and replayed;
- warm E4 end-to-end runtime remains at most `2x` E0;
- native HPWL, FLUTE RSMT, score, hashes, and runtime stages are complete.

#### D4 — cold/source diagnostic

Only after warm D3 passes, run cold E2/E3/E4. Preserve fail-closed behavior and
emit a structured repair-failure artifact if cold E4 cannot remain within its
bounded closure.

#### D5 — final matrix

Only after D1-D4 pass, run E0-E4 for seeds `1000/1001/1002` on both declared
tracks with one frozen configuration and scoring contract.

## Stop conditions

Stop the current experiment and report evidence rather than weakening the
contract when:

- a configuration-space field has any exact-collision false negative;
- an accepted warm step has a positive-area overlap;
- rollback does not restore optimizer and position hashes;
- collision loss or gradients are non-finite;
- runtime geometry enters the autograd path;
- scale `2` again grows overlap pressure;
- E4 obtains legality through broad packing or checkpoint fallback;
- a result is scored before float64 serialization and exact replay;
- a native failure triggers resumed open-ended CP-SAT, one-opt, or pair search.

## Hard acceptance gates

- Feature-off behavior does not regress.
- Native GPU execution is proven by actual backward/optimizer evidence; fixed
  placement evaluation alone does not count.
- A legal warm start remains zero-overlap during native E2/E3 optimization.
- E4 ends with `100/100` constrained containment, zero keep-in violations, and
  zero same-side overlaps.
- Near-boundary keep-in and collision-margin tests have finite, inward, nonzero
  gradients.
- Repeated objective evaluation does not mutate `pos`.
- Final reports include native HPWL, native RSMT, normalized score, placement
  hash, exact legality, convergence, displacement, collision, and full runtime
  breakdown.
- Final E3/E4 target: mean anchor distance improves at least `25%` and p90 at
  least `15%` versus E2, or the report supplies the existing per-component
  geometric lower bounds plus an explicit acceptance decision.
- Warm-cache E4 runtime is at most `2x` E0 under the same run contract.
- No result may claim Cypress quality from CP-SAT, one-opt, pair-scan, broad
  packing, or checkpoint fallback output.

## Stretch gate

A native E4 placement reaches repeated normalized native HPWL/RSMT score
`>= 1.0` with identical input hashes and a reproducible placement. Failure to
reach the stretch gate is not permission to return to open-ended CP-SAT search;
the report must isolate the native algorithm’s remaining limitation.
