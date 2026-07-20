# M336 Native Cypress Recovery — Durable Goal

Repository: `Wellshh/Cypress`
Branch: `experiment`
Reference head at task creation: `f0e4cb9` (`M336-140`)
Primary board: `M336`

## Objective

Move the M336 project’s active optimization path back from the offline exact-site
CP-SAT reference optimizer to Cypress/DREAMPlace’s native GPU global-placement
pipeline.

The task is successful only when actual runs execute:

```text
dreamplace/NonLinearPlace.py
  -> dreamplace/PlaceObj.py
  -> differentiable wirelength/density/anchor/keep-in objectives
  -> CUDA/PyTorch backward
  -> optimizer updates
  -> exact validation
  -> native HPWL and FLUTE RSMT scoring
```

The existing exact-site assets remain immutable diagnostic references, optional
warm starts, validators, and bounded E4 repair aids. They must not remain the
primary optimizer, must not be used as a fallback output when native placement
fails, and must not be presented as evidence that Cypress itself improved.

## Frozen factual baseline

- M336-118 remains the accepted exact-legal reference checkpoint.
- Its HPWL-only score upper bound is approximately `0.9760733`.
- A final repeated native RSMT gate has not yet been run for that checkpoint.
- M336-140 is committed at `f0e4cb9`.
- `experiments/m336/guides/M336-141/` is user-owned, untracked partial evidence.
  Preserve it exactly; do not delete, overwrite, commit, or resume its pair scan.
- Current exact-site work may be paused in the roadmap, but its append-only issue
  history and portable checkpoints must remain intact.

## Required native-algorithm outcomes

1. Establish a reproducible native GPU baseline and repeated native HPWL/RSMT
   score for M336-118 before claiming any algorithmic improvement.
2. Make `PlaceObj.obj_fn()` pure with respect to placement coordinates; projection
   must occur only at explicit optimizer/line-search boundaries.
3. Replace the current outside-only soft keep-in no-op with a differentiable
   interior-margin signal, or remove the term if a controlled ablation shows no
   benefit.
4. Make anchor attraction group-balanced, scheduled, bounded, and observable
   instead of relying on one unbounded, initialization-only gradient match.
5. Make TOP/BOTTOM density aware of irregular usable placement capacity so the
   continuous optimizer receives an inward force before hard projection.
6. Preserve legal warm starts and repair only illegal/conflicting closures; do
   not repack every constrained component by default.
7. Separate cold preprocessing, warm-cache initialization, GPU optimization,
   validation, repair, and native scoring in runtime reports.
8. Re-run E0-E4 with three seeds using the same input hashes, device, iteration
   budget, and scoring path.

## Hard acceptance gates

- Feature-off behavior does not regress.
- Native GPU execution is proven by actual backward/optimizer evidence; fixed
  placement evaluation alone does not count.
- E4 ends with `100/100` constrained containment, zero keep-in violations, and
  zero same-side overlaps.
- Near-boundary keep-in margin tests have finite, inward, nonzero gradients.
- Repeated objective evaluation does not mutate `pos`.
- Projection metrics include pre-projection displacement, projected count, and
  maximum projection distance.
- Final reports include native HPWL, native RSMT, normalized score, placement
  hash, exact legality, convergence, and full runtime breakdown.
- Final E3/E4 target: mean anchor distance improves at least 25% and p90 at least
  15% versus E2, or the report supplies a per-group geometric lower-bound
  diagnosis and an explicit acceptance decision.
- Warm-cache E4 runtime is at most 2x E0 under the same run contract, or the
  failure is profiled and reported without redefining the denominator.
- No result may claim Cypress quality from CP-SAT/one-opt/pair-scan output.

## Stretch gate

A native E4 placement reaches repeated normalized native HPWL/RSMT score
`>= 1.0` with identical input hashes and a reproducible placement. Failure to
reach the stretch gate is not permission to return to open-ended CP-SAT search;
the report must isolate the native algorithm’s remaining limitation.
