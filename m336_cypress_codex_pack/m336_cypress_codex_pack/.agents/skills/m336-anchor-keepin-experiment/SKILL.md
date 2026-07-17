---
name: m336-anchor-keepin-experiment
description: Implement, debug, or evaluate the Cypress M336 experiment for anchor-guided clustering inside side-specific irregular PCB keep-in regions. Use for M336 geometry ingestion, cluster-to-region assignment, anchor loss, feasible-domain projection, exact keep-in validation, ablations, and reports. Do not use for unrelated Cypress builds or general VLSI placement work.
---

# M336 anchor + irregular keep-in experiment

## Required context

Read, in order:

1. `AGENTS.md`
2. `CLAUDE.md`
3. `experiments/m336/SPEC.md`
4. `experiments/m336/input/m336_clusters.json`
5. `experiments/m336/input/m336_geometry_summary.json`
6. `experiments/m336/input/m336_region_assignment.seed.json`

Treat `experiments/m336/SPEC.md` as the acceptance contract.

## Workflow

### 1. Establish repository state

Run:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
find . -iname '*m336*' -o -iname '*M336*'
```

Work on `experiment`. Preserve existing build/benchmark work.

### 2. Validate inputs before coding

Run:

```bash
python experiments/m336/scripts/validate_manifest.py
```

Resolve the declared 27-module versus enumerated 25-module mismatch without inventing data. If no better machine-readable upstream mapping exists, use the 25 enumerated rows and report the mismatch.

### 3. Reconnaissance before design

Trace these paths:

- `dreamplace/PlaceDB.py`
- `dreamplace/BasicPlace.py`
- `dreamplace/PlaceObj.py`
- `dreamplace/NonLinearPlace.py`
- `dreamplace/ops/fence_region/`
- `dreamplace/ops/legality_check/`
- `dreamplace/params.json`

Identify exact extension points and write a short plan before changing code.

### 4. Implement in phases

Phase A: input loading, coordinate alignment, baseline.

Phase B: side-specific regions, feasible domains, hard projection, exact validation.

Phase C: anchor targets and anchor loss with normalized weight.

Phase D: repair, E0–E4 experiment matrix, regression smoke, report.

Keep all new behavior feature-gated and default off.

### 5. Geometry rules

- Read placement regions from `component_placeable_regions`, not `keepin_place`.
- Preserve line/arc/void geometry for final legality.
- Fit and validate source-to-Cypress coordinate transformation.
- Split mixed-side groups into TOP/BOTTOM subgroups.
- Use per-component feasible domains \(K \ominus P\); point-in-polygon alone is insufficient.
- Never fall back to the board bbox.
- Remove or bypass `virtual_macro.clamp(min=30)` for narrow-region experiments.
- Disable region fillers initially.
- Keep rotation disabled in the first complete experiment.

### 6. Optimization rules

- Freeze anchors by default.
- Exclude anchors from anchor loss.
- Target each member at the nearest feasible point to its physical anchor.
- Add anchor loss in `PlaceObj.obj_fn`.
- Add soft keep-in distance only as a stabilizer.
- Apply hard projection before objective evaluation and after `optimizer.step`.
- Record projection counts and distances.
- Preserve no-op behavior when flags are disabled.

### 7. Validation and evidence

Create CPU-runnable tests for parsing, alignment, feasible domains, projected targets, loss gradients, projection, and exact legality.

Run E0–E4 as far as the environment permits. Never report unrun metrics as actual.

Produce:

```text
results/m336/REPORT.md
results/m336/summary.json
```

The report must include commands, git SHA, configs, seeds, hard legality, anchor-distance statistics, HPWL, runtime, failures, and acceptance-criteria comparison.

## Stop conditions

Stop and report, rather than silently weakening constraints, when:

- geometry alignment residual exceeds tolerance;
- a required refdes cannot be mapped;
- a component has no feasible location in its assigned region;
- region capacity is infeasible;
- exact validation contradicts the approximate validator;
- the native build/GPU environment prevents an experiment.

Continue with all pure-Python and static checks that remain possible.

## Final response

Return:

- files changed;
- design summary;
- commands/tests run;
- actual M336 metrics;
- acceptance checklist;
- unresolved issues;
- review hotspots;
- `git diff --stat`.
