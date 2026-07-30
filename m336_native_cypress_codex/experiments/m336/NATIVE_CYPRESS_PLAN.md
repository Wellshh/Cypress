# M336 Native Cypress Recovery Plan

## 1. Decision

Pause the exact-site quality-search track after M336-140. Preserve M336-141 as
untracked user evidence, but do not resume its pair scan.

Activate the Cypress production-integration track. The exact optimizer is now:

```text
golden-reference generator
+ warm-start source
+ exact validator
+ bounded E4 repair aid
```

It is not the main optimizer for this phase.

## 2. Current native defects to address

### 2.1 Objective mutation and projection lifecycle

`PlaceObj.obj_fn()` currently invokes the region projector before calculating
the objective. This mutates the optimization variable during objective
evaluation and hides projection side effects inside learning-rate estimation,
gradient evaluation, and line search.

Required architecture:

```text
initial position
  -> explicit project_all_constraints()
  -> objective/gradient (pure; no coordinate mutation)
  -> optimizer proposal
  -> capture pre-projection proposal
  -> explicit project_all_constraints()
  -> clear optimizer state for projected coordinates
  -> metrics
```

For Nesterov, the same composite projector must be its `constraint_fn`. For
Adam/SGD, project before the first evaluation and after every step. Initial
learning-rate estimation must begin from a projected position.

Add tests proving:

- `obj_fn(pos)` does not change `pos`;
- two repeated calls give identical objective/gradient;
- Nesterov and Adam use the same constraint semantics;
- projected optimizer coordinates have momentum/history cleared.

### 2.2 Soft keep-in is architecturally zero

The current loss penalizes only outside-domain distance. Hard projection runs
before objective evaluation, so every evaluated feasible point has zero loss and
zero gradient.

Replace it with a feasible-domain interior-margin barrier:

\[
L_{\text{margin}}
=
\frac{1}{N}
\sum_i
\operatorname{softplus}
\left(
\frac{m-d_i^{inside}(c_i)}{\tau}
\right)^2
\]

where `d_inside` is positive inside the component-center feasible domain and
zero at its boundary.

Implementation requirements:

- precompute inside/signed distance maps from each footprint-aware feasible mask;
- sample on CPU and GPU with differentiable PyTorch operations, preferably
  `grid_sample`;
- no `.detach().cpu()` or Shapely calls in `forward()`;
- batch/cache identical domain classes;
- keep hard projection as the final legality guarantee;
- parameters default off and include explicit margin/tau in millimetres;
- report value and gradient norm independently of projection displacement.

Minimum tests:

- deep interior: approximately zero loss;
- near boundary: positive loss and inward gradient;
- outside proposal before projection: larger loss or explicit proposal metric;
- finite-difference agreement;
- CPU/GPU agreement within tolerance.

Run margin ablations such as `0`, `0.05`, `0.10`, and `0.20 mm`. Retain the term
only if it reduces projection pressure or improves final metrics.

### 2.3 Anchor objective and weighting

The current anchor loss averages all components globally and matches its gradient
to wirelength once. The observed initial weight can become extremely large and
does not adapt as density and projection change.

Required changes:

- aggregate member loss as a mean per side-specific subgroup, then average
  subgroups so large groups do not dominate;
- exclude anchors, fixed nodes, and frozen coordinates from both loss and
  gradient-norm matching;
- add a warm-up/ramp;
- update the gradient ratio periodically using an EMA;
- clamp the effective weight and log every update;
- serialize loss, raw gradient norms, effective lambda, and per-group metrics;
- keep projected feasible anchor targets;
- do not add an O(N²) all-pairs loss in the first implementation.

Recommended control variable:

```text
target anchor-gradient / wirelength-gradient ratio
```

Use a small controlled sweep, for example `0.05, 0.10, 0.25, 0.50`, rather than
blindly scaling an unbounded matched weight.

### 2.4 Density must understand irregular usable area

The current constraint context supplies projection and losses, but the native
TOP/BOTTOM electric-density path must be audited for irregular keep-in capacity.

Implement one of these, preferring the lowest-risk approach that preserves
separate TOP/BOTTOM fields:

1. per-side static obstacle/fixed-density maps for the space outside keep-in; or
2. per-bin usable-capacity maps consumed by the two-side density/overflow ops.

Requirements:

- keep TOP and BOTTOM density resources separate;
- conservative rasterization must not add placeable area outside physical
  polygons;
- do not use generic whole-board bbox capacity;
- do not reintroduce `virtual_macro.clamp(min=30)`;
- fixed obstacles and unusable space must exert continuous density pressure;
- overflow must be reported relative to usable area;
- compare projection count and boundary congestion with this feature off/on.

This work is central: projection alone cannot teach the continuous optimizer
where usable area exists.

### 2.5 Initialization and repair

Add explicit initialization modes:

```text
legacy_pack_all
preserve_legal
project_illegal
checkpoint_warm_start
```

`preserve_legal` must:

1. load float-preserving initial placement;
2. apply the explicit anchor endpoint policy;
3. run exact preflight;
4. leave already legal, non-overlapping constrained components unchanged;
5. repair only illegal nodes and their exact conflict closure.

Other requirements:

- create the anchor/keep-in context after the initial placement is loaded, or
  pass the loaded placement into endpoint resolution;
- support the current comparable endpoint policy:
  manual `EMI601`, runtime `Q601`;
- cache static feasible domains by hashes of geometry, assignment, grid,
  clearance, footprint, orientation, and endpoint policy;
- use spatial indexing for obstacle/conflict queries;
- report timing per region and strategy;
- never replace a failed native run with M336-118.

E4 repair must be bounded and local. Report moved count, affected closure,
displacement, runtime, and pre/post legality. Full-domain CP-SAT search is out of
scope.

## 3. Experimental program

### Stage A — immutable baseline

Before code changes:

1. record repository and environment state;
2. preserve and hash the untracked M336-141 directory without modifying it;
3. rebuild/install from source;
4. run repeated evaluate-only native HPWL/RSMT on M336-118;
5. run current native E0/E2/E3/E4 smoke for seed 1000;
6. store results under a baseline-labelled directory.

Do not call a fixed placement score a native-placement result. The report must
state whether `NonLinearPlace`, backward, and optimizer steps actually ran.

### Stage B — engineering loop

Use one GPU and seed 1000:

- 10-iteration smoke after each structural fix;
- 50-iteration diagnostic after each completed workstream;
- E0, E2, and E3 first; add E4 after pre-repair legality is measured;
- run warm-start and cold-start tracks separately.

### Stage C — final matrix

After the single-seed gates pass:

```text
Experiments: E0, E1, E2, E3, E4
Seeds:       1000, 1001, 1002
Tracks:      cold/source and M336-118 warm start
Budget:      one fixed final iteration/convergence contract
Device:      same GPU and deterministic settings
```

Score every final candidate through the same float-preserving PlaceDB/PinPos,
native HPWL, native FLUTE RSMT, exact polygon containment, overlap, and
post-serialization replay path.

## 4. Required metrics

Per iteration or sampled interval:

- wirelength, density, anchor, and margin objective values;
- raw and preconditioned gradient norms;
- effective anchor/margin weights;
- density overflow by side and usable region;
- projected node count, max distance, mean distance;
- pre-projection proposal displacement;
- objective and coordinate finiteness;
- learning rate and convergence reason.

Per run:

- native HPWL and RSMT;
- normalized quality score;
- exact legality before and after repair;
- physical/projected anchor distance mean, median, p90, max;
- per-group radius and worst groups;
- placement hash;
- input/config/source/install hashes;
- cold preprocessing, cache load, initialization, GPU optimization, validation,
  repair, serialization, and scoring times.

## 5. Acceptance sequence

Do not jump directly to the score-1 stretch target.

### Gate 1 — correctness

- objective is pure;
- feature-off no-op;
- finite gradients;
- correct endpoint policy;
- exact legality path works;
- M336-118 native score repeats.

### Gate 2 — useful native signal

- near-boundary margin gradient is nonzero and inward;
- anchor weight is bounded and adaptive;
- irregular-density mechanism measurably reduces projection pressure or improves
  final placement.

### Gate 3 — placement quality

- E3 beats E2 on anchor metrics;
- E4 is exact legal;
- warm-start HPWL/RSMT is not materially destroyed;
- runtime is attributable and bounded.

### Gate 4 — final evidence

- three-seed E0-E4 matrix;
- repeated native scoring;
- regression benchmark;
- full report with unsuccessful ablations included.

## 6. Stop conditions

Stop and report instead of silently weakening the contract when:

- M336-118 cannot be natively scored reproducibly;
- source and installed Python/CUDA code are out of sync;
- objective evaluation mutates position after the proposed fix;
- a configured loss has zero/non-finite gradient;
- coordinate alignment or endpoint policy is ambiguous;
- exact legality contradicts the native checker;
- GPU execution cannot be proven;
- runtime results mix cold preprocessing with warm placement without separate
  reporting.

Do not return to open-ended CP-SAT enumeration as a response to any of these
conditions.
