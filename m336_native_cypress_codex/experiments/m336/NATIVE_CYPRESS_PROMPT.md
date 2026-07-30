# Prompt for Codex Sol Ultra 5.6

Use `$m336-native-cypress-recovery`.

Work in `Wellshh/Cypress` on the existing `experiment` branch. The project is
pivoting away from open-ended exact-site CP-SAT quality search and back to
Cypress/DREAMPlace’s native GPU placement algorithm.

Read:

- `AGENTS.md`
- `CLAUDE.md`
- `BUILD.md`
- `.agents/skills/m336-native-cypress-recovery/SKILL.md`
- `experiments/m336/SPEC.md`
- `experiments/m336/NATIVE_CYPRESS_GOAL.md`
- `experiments/m336/NATIVE_CYPRESS_PLAN.md`
- `docs/issues/ACTIVE_ROADMAP.md`
- M336-002, M336-003, M336-005, M336-140
- the current implementations of `BasicPlace.py`, `NonLinearPlace.py`,
  `PlaceObj.py`, `constraints/anchor_keepin.py`,
  `constraints/region_projection.py`, `ops/anchor_keepin/anchor_keepin.py`,
  `params.json`, and `experiments/m336/scripts/run_matrix.py`.

Do not ask me to restate information already present in those files. Execute the
work in the current run as far as the environment permits.

## First actions

Run and record:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -10 --oneline
git diff --check
nvidia-smi
python3.11 --version
```

The expected committed baseline is at least `f0e4cb9` (`M336-140`). Pull/inspect
before editing. Do not create or switch branches.

`experiments/m336/guides/M336-141/` is untracked user-owned partial evidence.
Hash and record it, but do not delete, overwrite, commit, move, or resume its
pair scan. Do not run background processes.

Verify source/install parity. Rebuild installed Python/native extensions after
source changes; never edit only `install/` copies.

## Strategic constraint

This phase must produce evidence about Cypress itself.

Do not:

- extend exact-site K values;
- enumerate more CP-SAT no-good/rank layers;
- resume M336-141 pair scanning;
- build new residual CP-SAT portfolios;
- use M336-118 as a silent fallback result;
- claim a fixed-placement/native-score replay as a GPU placement result;
- weaken exact legality or scoring gates.

Existing CP-SAT/checkpoint tooling may only be used to score, validate, provide
a warm start, or perform explicitly bounded local E4 repair.

## Milestone 0 — native baseline and real score

Before modifying behavior:

1. Run the float-preserving native HPWL and FLUTE RSMT scorer twice on M336-118.
2. Require identical input hashes, placement coordinates, placement hash, HPWL,
   and RSMT, or report the exact nondeterminism.
3. Run current-branch native E0/E2/E3/E4 smoke on seed 1000 with a small fixed
   budget.
4. Prove from logs that `NonLinearPlace`, `PlaceObj`, backward, and optimizer
   steps ran.
5. Store this immutable baseline separately from post-change results.

Do not treat M336-118’s HPWL-only `0.9760733` upper bound as its native score.

## Milestone 1 — objective purity and projection lifecycle

Remove coordinate mutation from `PlaceObj.obj_fn()`.

Implement one explicit composite constraint function that applies board and
footprint-aware keep-in projection. Use it:

- before initial learning-rate estimation;
- before each ordinary objective evaluation as needed;
- as Nesterov’s `constraint_fn`;
- after every Adam/SGD optimizer proposal.

Capture pre-projection coordinates and report displacement. Clear optimizer
state for projected coordinates. Keep frozen anchors exact.

Add tests proving repeated `obj_fn` calls do not mutate `pos` and produce
identical objective/gradient.

## Milestone 2 — differentiable keep-in margin

Replace the current outside-only `SoftKeepInLoss` with a differentiable
footprint-center interior-margin barrier.

Requirements:

- precomputed inside/signed distance field from each feasible mask;
- differentiable PyTorch sampling on the active device;
- no Shapely, `.cpu()`, or detached geometry decisions in `forward()`;
- deep-interior zero/near-zero signal;
- nonzero inward gradient near the boundary;
- finite-difference and CPU/GPU tests;
- explicit `margin_mm` and `tau_mm`, default off;
- log loss, gradient norm, projection count, and proposal displacement.

Run a controlled margin ablation. Remove/disable the term if it shows no
measurable benefit.

## Milestone 3 — anchor objective control

Make anchor loss side-subgroup balanced. Exclude frozen anchors/fixed nodes.

Replace one-time unbounded matching with:

- warm-up/ramp;
- periodic EMA gradient-ratio updates;
- explicit clamps;
- serialized effective lambda and raw gradient norms.

Use a controlled target gradient-ratio sweep, not another blind scale ladder.
Preserve projected feasible anchor targets.

## Milestone 4 — irregular keep-in density for native GP

Audit and fix the actual two-side density path. Continuous placement must see
that space outside TOP/BOTTOM keep-ins has zero usable capacity.

Prefer a per-side static obstacle/fixed-density map or a per-bin usable-capacity
map. Do not merge TOP and BOTTOM fields, use the board bbox as capacity, or
reintroduce `virtual_macro.clamp(min=30)`.

Add tests and metrics for:

- conservative usable area;
- side isolation;
- inward density force;
- usable-area overflow;
- projection-pressure reduction.

## Milestone 5 — initialization and bounded repair

Create explicit modes:

```text
legacy_pack_all
preserve_legal
project_illegal
checkpoint_warm_start
```

Build/resolve the context after float initial placement is available, including
the current endpoint policy: manual EMI601 and runtime Q601.

In `preserve_legal`, do not repack already legal non-overlapping components.
Repair only illegal/conflicting closures. Add static feasible-domain caching and
spatial indexing. Report cold and warm-cache timing separately.

E4 repair must be local and bounded. It may not perform full-domain exact-site
optimization.

## Experimental cadence

Engineering loop:

- seed 1000;
- 10-iteration smoke after structural changes;
- 50-iteration diagnostic after each milestone;
- E0/E2/E3 first, then E4;
- cold/source and M336-118 warm-start tracks kept separate.

Final matrix, only after single-seed gates pass:

```text
E0, E1, E2, E3, E4
seeds 1000, 1001, 1002
same GPU
same input hashes
same final budget
cold and warm tracks
```

Score all final outputs through the same float-preserving PlaceDB/PinPos,
native HPWL, native FLUTE RSMT, exact polygon containment, overlap, and
post-serialization replay path.

## Required acceptance evidence

- feature-off existing benchmark regression;
- pure objective/no position mutation;
- nonzero inward margin gradient near boundary;
- bounded adaptive anchor lambda;
- exact E4 legality;
- E3/E4 anchor mean improvement >=25% and p90 >=15% versus E2, or explicit
  per-group geometric lower-bound diagnosis;
- warm-cache E4 runtime <=2x E0 under equal conditions, or profile-backed
  failure without changing the denominator;
- native HPWL/RSMT and normalized score for every final E4;
- repeated M336-118 native score;
- no fabricated GPU, solver, or timing results.

## Roadmap and reporting

Create/update a native Cypress phase specification and change
`docs/issues/ACTIVE_ROADMAP.md` so Cypress production integration is active and
the exact-site track is paused, while preserving the append-only ledger.

Write:

```text
results/m336/native-cypress/REPORT.md
results/m336/native-cypress/summary.json
```

Include actual commands, source/install hashes, GPU environment, objective
curves, gradient/weight/projection metrics, runtime breakdown, native scores,
exact legality, worst groups, unsuccessful ablations, and acceptance status.

Use small reviewable commits after validated milestones. Do not push unless I
explicitly ask.

## Final response

Return:

1. starting and ending SHA;
2. dirty/untracked state, explicitly including M336-141 preservation;
3. changed files and `git diff --stat`;
4. architecture and migration away from CP-SAT;
5. exact commands, builds, and tests;
6. repeated M336-118 native HPWL/RSMT score;
7. baseline and post-change native E0-E4 metrics;
8. cold/warm runtime breakdown;
9. exact legality and native score gates;
10. failed/unrun items and reasons;
11. acceptance checklist;
12. code review hotspots.
