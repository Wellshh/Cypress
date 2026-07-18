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
