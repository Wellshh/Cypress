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

The optional shared-coordinate audit requires OR-Tools but does not add it as a
production dependency:

```bash
PYTHONPATH="$PWD/install:$PWD" python3.11 \
  experiments/m336/scripts/solve_discrete_placement.py \
  --assignment results/m336/quality_assignment/m336_region_assignment.grid005.runtime-fixed.quality.json \
  --baseline-result results/m336/baseline_warmstart_smoke/baseline/baseline-result.json \
  --grid-mm 0.05 --collision-mode none --minimum-score 1.0
```
