# Prompt to paste into Codex

Use `$m336-anchor-keepin-experiment`.

You are working in the `Wellshh/Cypress` repository. The target is the existing `experiment` branch. Implement and experimentally evaluate the M336 anchor-guided irregular keep-in placement specification.

Read all applicable instructions and context before editing:

- `AGENTS.md`
- `CLAUDE.md`
- `BUILD.md`
- `.agents/skills/m336-anchor-keepin-experiment/SKILL.md`
- `experiments/m336/SPEC.md`
- `experiments/m336/CODEX_GOAL.md`
- all files under `experiments/m336/input/`

Do not ask me to restate information already present in those files. Make a best-effort implementation in the current run.

## Required first actions

1. Record repository state:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
```

2. Confirm you are on `experiment`; do not create or switch branches.
3. Inspect existing M336 assets before creating a converter:

```bash
find . \( -iname '*m336*' -o -iname '*M336*' \) -print
```

4. Run:

```bash
python experiments/m336/scripts/validate_manifest.py
```

5. Trace the existing data and optimizer path through:
   - `dreamplace/PlaceDB.py`
   - `dreamplace/BasicPlace.py`
   - `dreamplace/PlaceObj.py`
   - `dreamplace/NonLinearPlace.py`
   - fence-region, move-boundary, electric-potential, and legality-check ops.

Then write a concise implementation plan and execute it.

## Non-negotiable behavior

- Feature flags default off; existing Cypress behavior must remain unchanged when disabled.
- Do not hardcode M336 refdes or absolute paths in core modules.
- Do not invent two missing clusters. The supplied text declares 27 modules, but the enumerated table contains 25 modules and exactly 125 members. Prefer a better machine-readable upstream mapping if present; otherwise use the supplied 25-row manifest and report the mismatch.
- Read placement regions from `component_placeable_regions`.
- Preserve TOP/BOTTOM separation. Split mixed-side clusters into side-specific subgroups.
- Freeze physical anchors by default and exclude them from anchor loss.
- First complete experiment keeps rotation disabled.
- Use component-footprint feasible domains \(F=K\ominus P\), not center-point containment.
- Fit and validate geometry-to-Cypress coordinate mapping; do not assume it.
- Never fall back to the board bounding rectangle.
- Exact source polygon containment and exact overlap checks are final truth.
- Remove/bypass the `virtual_macros_size_*.clamp(min=30)` expansion for the narrow-region path.
- Disable fillers inside constrained narrow regions for the first experiment.
- Apply hard region projection before objective evaluation and after optimizer updates.
- No fabricated results. If a GPU/native build cannot run, complete CPU-runnable work and explicitly report blockers.

## Implementation phases

### Phase A — input and baseline

- Reconcile/validate cluster and geometry inputs.
- Find or generate M336 Bookshelf/aux data.
- Implement coordinate alignment with residual report.
- Add resolved M336 config generation.
- Run a short E0 baseline if possible.

### Phase B — keep-in mechanics

- Build stable region catalog and side subgroups.
- Implement assignment preflight and use the provided seed only as a proposal.
- Implement per-component feasible-domain cache.
- Implement region-aware initialization.
- Implement hard projector and exact validator.
- Run E2 smoke and prove containment.

### Phase C — anchor objective

- Add projected-anchor targets.
- Add smooth, normalized anchor loss in `PlaceObj.obj_fn`.
- Initialize/sweep its weight using gradient-norm matching.
- Add optional soft keep-in SDF loss.
- Run E3 smoke and weight sweep.

### Phase D — final legality and experiments

- Add bounded greedy/backtracking or CP-SAT repair for remaining violations.
- Run E0–E4 for seeds 1000, 1001, 1002 as the environment permits.
- Run an existing small-board regression smoke.
- Generate `results/m336/REPORT.md` and `results/m336/summary.json`.

## Required tests

Create CPU-runnable tests for:

- manifest integrity;
- DBU/mm conversion;
- coordinate alignment;
- arc/polygon reconstruction;
- conservative region decomposition;
- non-overlapping region boxes;
- per-component feasible domains;
- projected anchor targets;
- hard projection;
- exact violation detection;
- anchor-loss value and gradient;
- feature-off no-op behavior.

Run all applicable tests and include commands and outputs in the final report.

## Acceptance

E4 must target:

- zero keep-in violations;
- zero constrained-component overlaps;
- 100% constrained components fully contained;
- mean anchor distance at least 25% lower than E2;
- p90 anchor distance at least 15% lower than E2;
- HPWL regression no worse than 10% versus baseline;
- no regression when the new feature is disabled.

Targets that cannot be achieved must be diagnosed per group; do not hide failures.

## Final response

Return:

1. starting and ending git SHA;
2. changed files and `git diff --stat`;
3. architecture and important decisions;
4. exact commands/tests run;
5. actual E0–E4 metrics;
6. acceptance checklist;
7. failed/unrun items with reasons;
8. worst per-group cases;
9. code areas requiring human review.

Do not push unless I explicitly ask.
