# Ready-to-paste Codex prompt

Use the **GPT-5.6 Sol** model with **Extra High** reasoning. Select repository `Wellshh/Cypress` and branch `experiment`, then paste the prompt below.

---

Use the `$m336-anchor-keepin` skill.

You are working in `Wellshh/Cypress` on the selected `experiment` branch. Implement and run the M336 anchor-guided irregular keep-in placement experiment defined in:

- `AGENTS.md`
- `docs/experiments/m336_anchor_keepin/SPEC.md`
- `docs/experiments/m336_anchor_keepin/data/m336_clusters.json`
- `docs/experiments/m336_anchor_keepin/data/m336_assignment_seed.json`
- `docs/experiments/m336_anchor_keepin/data/m336_geometry_manifest.json`

The required large input must exist at:

`artifacts/experiments/m336/pcb_geometry_keepin.json`

First verify its SHA-256 against the manifest. Never substitute another board or the `small-*` benchmarks.

## Goal

Build a reproducible Cypress experiment in which the 100 non-anchor members of the supplied M336 modules are placed:

1. completely inside their assigned side-specific irregular keep-in region;
2. as close as reasonably possible to their fixed module anchor;
3. compact with their same-network/module peers;
4. without overlap;
5. with no more than 10% total HPWL degradation versus a controlled Cypress baseline.

The first controlled experiment must keep:

- 25 supplied anchors fixed at source XY/layer/orientation;
- 15 unclustered components fixed;
- 100 non-anchor clustered components movable;
- rotation disabled;
- fillers disabled.

Split mixed TOP/BOTTOM modules into side-specific subgroups sharing the same physical anchor XY. Preserve and report the source inconsistency: the prose says 27 modules, while the provided table contains 25 modules totaling 125 components.

## Implementation constraints

- Keep all new behavior behind `anchor_keepin_flag`; flag-off behavior must not regress.
- Do not hard-code M336 refdes, coordinates, region IDs, or file paths in core `dreamplace/` code.
- Use `component_placeable_regions`.
- Parse line and arc boundaries from integer DBU geometry.
- Use `PACKAGE GEOMETRY/PLACE_BOUND_TOP/BOTTOM`, not symbol bbox.
- Build fixed-orientation feasible component-center domains by rasterization and rectangular-footprint erosion.
- Validate or repair the provisional subgroup-region assignment before placement.
- Add anchor-aware initialization.
- Add `L_anchor = sum_i w_i * smooth_l1(center_i - projected_legal_anchor_i)`, with `w_i = 1 + shared non-GND net count` for the MVP.
- Add a hard keep-in projector after every optimizer step.
- Under the M336 flag, remove the `clamp(min=30)` distortion from fence-region virtual macros without changing old default behavior.
- Add deterministic post-placement candidate repair and exact final geometry checks.
- Implement the correct Python/PyTorch version first; do not add CUDA unless profiling proves it is necessary.
- Do not claim runs passed without actual logs and result files.

## Required experiment matrix

Run seeds 1000, 1001, and 1002 for:

- E0: controlled baseline, new constraints disabled;
- E1: hard keep-in only;
- E2: E1 plus anchor-aware initialization;
- E3: E2 plus anchor loss;
- E4: E3 plus exact candidate repair and final legality check.

Test anchor loss weights 0.03, 0.10, and 0.30 at least on seed 1000; use the best valid setting for the three-seed E3/E4 comparison.

## Required tests

Add CPU tests for:

- DBU/Bookshelf coordinate round trip;
- arc tessellation;
- L/U/narrow-corridor keep-in parsing;
- fixed-orientation feasible-domain erosion;
- anchor projection when anchor is outside the region;
- hard projector;
- subgroup side splitting;
- assignment feasibility and capacity;
- anchor-loss gradient;
- flag-off regression.

Run focused existing tests that touch modified Cypress code. Run an M336 preprocessing smoke test before a full GPU run.

## Required outputs

Write per-run artifacts under:

`results/m336_anchor_keepin/<variant>/<seed>/`

including:

- effective config;
- resolved assignment;
- logs;
- initial, pre-repair, and final placement;
- `metrics.json`;
- `components.csv`;
- `groups.csv`;
- `region_loads.json`;
- before/after plots with exact keep-in outlines, anchors, groups, and violations.

Write:

- `results/m336_anchor_keepin/REPORT.md`
- `results/m336_anchor_keepin/summary.csv`
- `results/m336_anchor_keepin/summary.json`

The report must compare keep-in violations, overlap, raw and feasible anchor distance mean/P50/P90/max, group compactness, constrained and total HPWL, density overflow, runtime, projection statistics, and repair displacement.

## Acceptance gates

E4 must have:

- zero exact keep-in violations;
- zero movable overlap;
- anchor displacement no more than 1 DBU;
- weighted mean feasible-anchor distance at least 25% better than E0;
- P90 feasible-anchor distance at least 15% better than E0;
- total HPWL no more than 10% worse than E0;
- no flag-off regression.

## Working method

Inspect the repository before editing. Make incremental, reviewable commits by milestone. Do not edit `main`. If the GPU environment or required large input is unavailable, still complete the implementation, preprocessing, synthetic tests, and report scaffolding; then state exactly which experiment commands could not be run and why. Never invent measurements.

At completion, provide:

1. a concise implementation summary;
2. files changed;
3. exact commands run;
4. actual test results;
5. actual experiment metrics;
6. acceptance-gate status;
7. known limitations and the next most valuable experiment.
