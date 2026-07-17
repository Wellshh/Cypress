---
name: m336-anchor-keepin
description: Implement, run, and evaluate the Cypress M336 experiment for anchor-guided clustering inside irregular TOP/BOTTOM keep-in regions. Use for M336, anchor attraction, component_placeable_regions, keep-in projection, side-specific group assignment, or related placement ablations; do not use for unrelated Cypress benchmarks.
---

# M336 anchor-guided irregular keep-in experiment

Follow this workflow exactly. The authoritative design document is `docs/experiments/m336_anchor_keepin/SPEC.md`.

## Inputs

- Cluster contract: `docs/experiments/m336_anchor_keepin/data/m336_clusters.json`
- Provisional subgroup-to-region mapping: `docs/experiments/m336_anchor_keepin/data/m336_assignment_seed.json`
- Geometry manifest: `docs/experiments/m336_anchor_keepin/data/m336_geometry_manifest.json`
- Required large input: `artifacts/experiments/m336/pcb_geometry_keepin.json`
- Example configuration: `docs/experiments/m336_anchor_keepin/config/m336_anchor_keepin.example.json`

Verify the geometry SHA-256 before any experiment. Validate all 140 named refdes and surface the 27-declared-versus-25-parsed module discrepancy.

## Operating rules

- Work from the `experiment` branch and keep the implementation behind `anchor_keepin_flag`.
- Do not hard-code M336 identifiers in `dreamplace/`; load manifests.
- For the first experiment, keep orientation optimization disabled.
- Fix all anchor components at source XY/layer/orientation.
- Fix the 15 unclustered components to remove confounding.
- Split six mixed-side modules into independent TOP/BOTTOM subgroups sharing the anchor XY.
- Use `component_placeable_regions`, not the empty or unrelated keep-in keys.
- Use `PACKAGE GEOMETRY/PLACE_BOUND_TOP/BOTTOM` as the component footprint source; never use the full symbol bbox.
- Ignore six empty-refdes symbol records.
- Fail if an active member has no feasible center domain in its assigned region.

## Required implementation sequence

1. Add deterministic M336 input preparation and round-trip coordinate tests.
2. Parse/tessellate the four side-specific keep-in polygons, including arcs.
3. Build component-center feasible domains by rasterizing each region and eroding it by each fixed-orientation place-bound rectangle.
4. Validate or repair the provisional region assignment under exact feasibility and capacity.
5. Generate the M336 Bookshelf benchmark if no valid `.aux` exists. Use the same fixed/movable set for every ablation.
6. Add anchor-aware initialization.
7. Add a differentiable anchor loss to each member's projected legal anchor target.
8. Add a hard region projection after each optimizer step.
9. Add exact post-run candidate repair and exact geometry checks.
10. Run the experiment matrix and produce machine-readable and visual reports.

Implement the MVP in Python/PyTorch first. Do not add a custom CUDA kernel unless profiling proves the Python/PyTorch implementation is the bottleneck.

## Objective

For each non-anchor member `i` in subgroup `g`, define the target `q_i` as the projection of the fixed anchor XY onto that component's feasible center domain. Add:

`L_anchor = sum_i w_i * smooth_l1(center_i - q_i)`

where `w_i = 1 + shared_non_gnd_net_count(anchor, i)` for the MVP. Keep Cypress wirelength, density, and net-crossing terms intact.

Hard containment is enforced by projecting the component center into its exact feasible domain; the soft loss is not a legality guarantee.

## Ablations

Run at least:

- E0: baseline Cypress with identical fixed/movable set, new constraints disabled.
- E1: keep-in parsing and hard projection only.
- E2: E1 plus anchor-aware initialization.
- E3: E2 plus anchor loss.
- E4: E3 plus exact repair and final legality check.
- E5 optional: signed-distance/geodesic anchor field and/or rotation-aware feasible domains.

Use seeds 1000, 1001, and 1002 unless deterministic equivalence is explicitly demonstrated.

## Required outputs

Under `results/m336_anchor_keepin/<variant>/<seed>/` write:

- final `.pl`
- run log and effective config
- `metrics.json`
- `components.csv`
- `groups.csv`
- `region_loads.json`
- before/after placement plot with keep-in outlines, anchors, and group colors
- violation plot if any constraint fails

Write `results/m336_anchor_keepin/REPORT.md` comparing all variants.

## Acceptance gates

- Zero exact keep-in violations after E4.
- Zero movable-movable and movable-fixed overlap after E4.
- Anchors unchanged to one DBU.
- Weighted mean feasible-anchor distance improves at least 25% versus E0; P90 improves at least 15%.
- Global HPWL degradation is no more than 10% versus E0.
- No regression when `anchor_keepin_flag=false`.
- All tests and commands are quoted in the final response with actual results.

If full GPU execution is unavailable, complete the implementation and CPU/synthetic tests, then state exactly which GPU experiments remain unexecuted. Never invent metrics.
