# M336 anchor-guided irregular keep-in experiment specification

**Target:** `Wellshh/Cypress:experiment`  
**Experiment ID:** `m336_anchor_keepin_v1`  
**Status:** implementation-ready

This file is the normative index for the M336 experiment. Read all four specification parts, in order, before editing code:

1. [`spec/01_scope_and_data.md`](spec/01_scope_and_data.md) — objective, input contract, fixed/movable policy, side splitting, hypotheses and end-to-end flow.
2. [`spec/02_geometry_assignment_objective.md`](spec/02_geometry_assignment_objective.md) — coordinate transform, arc tessellation, place-bound footprints, feasible center domains, subgroup-region assignment, anchor-aware initialization, anchor loss and hard projection.
3. [`spec/03_integration_and_repair.md`](spec/03_integration_and_repair.md) — native Cypress fence-region reuse, narrow-region fixes, exact repair, code touchpoints and M336 Bookshelf generation.
4. [`spec/04_experiments_and_acceptance.md`](spec/04_experiments_and_acceptance.md) — E0–E4 ablations, metrics, outputs, tests, milestones, risks and Definition of Done.

The ready-to-paste execution instruction is [`CODEX_PROMPT.md`](CODEX_PROMPT.md). The machine-readable inputs are under [`data/`](data/).

## Normative experiment contract

The supplied clustering prose says **27 modules**, but the supplied table contains **25 module rows** totaling exactly **125 clustered components**. Preserve this warning in every report; use the 25 parsed rows as the experiment source of truth and do not invent two missing modules.

For the first controlled experiment:

- 25 anchor components remain fixed at source XY, layer and orientation;
- 15 unclustered named components remain fixed;
- 100 non-anchor clustered members are movable;
- six mixed TOP/BOTTOM modules are split into side-specific subgroups sharing the same physical anchor XY;
- rotation is disabled;
- fillers are disabled;
- TOP uses one irregular keep-in; BOTTOM uses three irregular keep-ins;
- E0–E4 use the identical fixed/movable set.

The large geometry file must be supplied at:

```text
artifacts/experiments/m336/pcb_geometry_keepin.json
```

It must match:

```text
size_bytes = 14091267
sha256 = a7c2c788a7df386db9f94df76bfe64a21d49f21beacb0e233ebedac75cc4ad8d
schema = pcb_geometry_lossless_v1
dbu_per_user_unit = 10000
```

Use `component_placeable_regions` and `PACKAGE GEOMETRY/PLACE_BOUND_TOP|BOTTOM`. Ignore six empty-refdes symbol records. Never substitute a `small-*` benchmark.

## Required algorithm

For each member `i` assigned to region `K_m`, build the fixed-orientation feasible **component-center** domain:

\[
F_{i,m}=K_m\ominus P_i^{eff}
\]

where `P_i_eff` is the source-orientation place-bound rectangle plus configured clearance. A member with an empty feasible domain cannot be placed in that region; the assignment must be repaired or the experiment must fail before optimization.

Project the fixed module anchor `a_g` into each member's feasible domain:

\[
q_i=\Pi_{F_{i,m}}(a_g)
\]

Use `q_i` for anchor-aware initialization and add:

\[
L_{anchor}=\sum_i w_i\,SmoothL1(c_i-q_i)
\]

with MVP weight `w_i = 1 + shared_non_gnd_net_count(anchor, i)`. Preserve Cypress wirelength, density and net-crossing terms. A soft loss is not a legality guarantee: execute an irregular keep-in hard projector after every optimizer step, then run deterministic exact candidate repair and exact polygon/footprint checks.

Reuse Cypress native multi-fence data structures where useful, but do not treat rectangle-union fence legality as the final authority. Under the new feature flag, preserve thin virtual-macro geometry rather than applying the existing `clamp(min=30)` distortion. Every new code path must be design-agnostic and disabled by default behind `anchor_keepin_flag`.

## Experiment matrix

- **E0:** controlled Cypress baseline, constraints disabled.
- **E1:** exact feasible domains plus hard keep-in projection.
- **E2:** E1 plus anchor-aware initialization.
- **E3:** E2 plus anchor loss; test weights `0.03`, `0.10`, `0.30` on seed 1000.
- **E4:** E3 plus exact repair and final legality check.
- **E5 optional:** SDF/geodesic anchor field and rotation-aware domains.

Run seeds `1000`, `1001`, `1002`, unless deterministic equivalence is demonstrated with hashes and identical metrics.

## Acceptance gates

E4 passes only when all of the following hold:

- exact keep-in violations: 0;
- movable–movable and movable–fixed overlaps: 0;
- anchor displacement: at most 1 DBU;
- weighted mean feasible-anchor distance improves at least 25% versus E0;
- P90 feasible-anchor distance improves at least 15% versus E0;
- total HPWL is no more than 10% worse than E0;
- `anchor_keepin_flag=false` has no regression;
- actual logs, configs, metrics, CSVs, placements and plots are present.

If the GPU or large input is unavailable, complete implementation, preprocessing, CPU/synthetic tests and report scaffolding, and state exactly what was not executed. Never invent measurements.
