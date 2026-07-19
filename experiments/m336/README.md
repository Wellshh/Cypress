# M336 experiment workspace

See:

- `SPEC.md`
- `CODEX_GOAL.md`
- `CODEX_PROMPT.md`

Inputs are immutable source material. Generated configs, plots, placements, and reports should go to a gitignored or selectively committed results directory. Do not modify the source geometry to make a run pass.

The seed assignment is a proposal based only on same-side distance from each physical anchor to the source keep-in polygon. It must be validated against per-component feasible domains and region capacity before use.

Screen a finalized assignment against the native net topology before running
GPU placement:

```bash
PYTHONPATH="$PWD/install" python3.11 \
  experiments/m336/scripts/optimize_assignment.py \
  --assignment results/m336/quality_assignment/m336_region_assignment.grid005.template.json \
  --baseline-result results/m336/baseline_warmstart_smoke/baseline/baseline-result.json \
  --grid-mm 0.05
```

The reported quality value is an optimistic interval bound. It is the first of
three gates: interval assignment, shared-coordinate discrete placement, then
exact collision validation plus native HPWL/RSMT. A value above `1.0` at the
first gate is not an accepted result.

Replay a feasible exact-site result through the same native HPWL/FLUTE RSMT
operators used for the manual baseline:

```bash
PYTHONPATH="$PWD/install:$PWD/experiments/m336/scripts:$PWD" python3.11 \
  experiments/m336/scripts/score_exact_site_result.py \
  --result /tmp/m336_exact_site_cpsat.json \
  --output-dir /tmp/m336_native_score
```

The scorer independently rebuilds and validates all 100 controlled sites,
checks the serialized `.pl`, and proves that native evaluation did not move
any component. It exits `0` only for exact-zero-overlap results whose native
normalized HPWL/RSMT score is at least `1.0`; a score miss exits `2` after
writing `result.json`.

Before increasing grid resolution, run the continuous shared-coordinate box
relaxation. It searches every bounding-box-feasible same-side region while
ignoring exact polygons, overlap, and capacity, so a score bound below `1.0`
proves that no finer grid or collision strategy can pass under the same
runtime-fixed endpoint contract:

```bash
PYTHONPATH="$PWD/install:$PWD" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  python3.11 \
  experiments/m336/scripts/analyze_shared_box_bound.py \
  --assignment results/m336/quality_assignment/m336_region_assignment.grid005.runtime-fixed.quality.json \
  --baseline-result results/m336/baseline_warmstart_smoke/baseline/baseline-result.json \
  --grid-mm 0.05 --ignore-area-capacity --minimum-score-potential 1.0
```

The command intentionally exits nonzero after writing its report when the
upper bound misses the requested score.

Use `--manual-baseline-endpoint <REFDES>` only for contract isolation. For
example, overriding `EMI601` and `Q601` tests whether preserving those
runtime-frozen anchors at their warm-start positions restores score potential;
it does not change the production placement policy.

The optional shared-coordinate audit requires OR-Tools but does not add it as a
production dependency:

```bash
PYTHONPATH="$PWD/install:$PWD" python3.11 \
  experiments/m336/scripts/solve_discrete_placement.py \
  --assignment results/m336/quality_assignment/m336_region_assignment.grid005.runtime-fixed.quality.json \
  --baseline-result results/m336/baseline_warmstart_smoke/baseline/baseline-result.json \
  --grid-mm 0.05 --collision-mode none --minimum-score 1.0
```

Add `--optimize-assignment` to couple all eligible subgroup-region choices to
the component sites. `--ignore-area-capacity` is a diagnostic relaxation only;
its output cannot be promoted as a legal assignment.

The discrete audit accepts the same diagnostic endpoint flags as the
continuous bound. `--manual-baseline-endpoint EMI601
--manual-baseline-endpoint Q601` changes fixed net endpoints only; it does not
yet update projected-anchor targets and therefore cannot be promoted directly
to an E1-E4 result.

The default `--collision-mode decomposed` preserves concave manual footprints
through deterministic convex decomposition and uses the manual footprints for
fixed obstacles. Do not use `--collision-mode convex` for feasibility claims:
it is retained only to reproduce the historical over-conservative model from
`M336-017`. `--collision-mode none` also remains a necessary-condition lower
bound and never produces an acceptable placement. In every mode, promote a
result only after its emitted exact report shows full containment and zero
overlaps.

To audit how far a complete placement must move, provide a full site hint and
repeat `--movable-refdes <REFDES>`. Every controlled component not listed is
fixed to its hinted site by an explicit model equality. This mode is diagnostic
and requires a fixed assignment; the result records both the movable list and
fixed-site count. See `M336-018` for the anchor-relocation mobility proofs.

Collision reports also expose encoded and safely skipped component-pair counts.
The skip test uses swept bounds over every candidate site, never a heuristic
distance cutoff; see `M336-019` for the semantic A/B validation.

Optimized-assignment search may consume `--site-hint-result`; each selected
site supplies an explicit region and region-local index. Candidate limiting
retains a neighborhood in every eligible region, so the hint guides rather
than fixes assignment. Raw placement hints remain fixed-assignment only. See
`M336-020` for the validated hint contract.

To limit alternate-region search without preventing global coordinate repair,
repeat `--movable-subgroup <GROUP_ID>` with `--optimize-assignment` and one
`--site-hint-result`. Listed subgroups retain all eligible regions; every other
subgroup uses its hinted region, but every component site remains movable.
This differs deliberately from `--movable-refdes`, which fixes unlisted sites.
The result reports `assignment_mode: optimized_scoped`; see `M336-021`.

`--candidate-guide-placement <PL>` adds a second physical-coordinate center to
each component's limited site domain. The guide is projected independently in
every eligible region, so it is safe with optimized or scoped assignment. It
does not alter the structured result hint or fix any site.

Use `--packing-only --feasibility-only` only to isolate keep-in, capacity, and
collision feasibility. This diagnostic mode omits all HPWL variables and the
score gate; it still reports actual HPWL after finding a candidate, but its
placement cannot be accepted until a later score-gated solve passes.

`--packing-side TOP|BOTTOM` additionally restricts a packing-only fixed-
assignment solve to one side. It requires a complete structured result hint;
the other side is copied unchanged, and `packing_side_legality` controls only
that stage. Chain both sides and require final global legality before reuse.

`probe_exact_site_cpsat.py` derives its generated context directory from
`M336_OUTPUT_JSON`, so distinct parallel outputs are isolated. Set
`M336_CONTEXT_DIR` only for an intentional override; never share one override
between concurrent probes with different assignments or geometry settings.

`greedy_exact_site_descent.py --escape-order-seed <SEED>` samples a fresh,
deterministic component order for each guided escape sweep. Omit the option to
preserve the original sorted order. Seeded runs record the PCG64 generator and
NumPy version plus every realized refdes order; compare only runs with
identical escape budgets, sweep limits, guides, and source hashes. This changes
search order only: exact site containment, collision checks, and the HPWL
envelope remain mandatory.

`--max-escape-move-rise <HPWL>` optionally limits the positive HPWL increase
of one guided move relative to its current state. It is separate from the
total `--escape-hpwl-budget` envelope and defaults to no per-move limit. Use it
to prevent one large guide-directed jump from consuming a long-path budget;
both limits and every accepted move delta are recorded in the result.
