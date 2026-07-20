---
name: m336-native-cypress-recovery
description: Restore and improve the native Cypress/DREAMPlace GPU placement path for M336. Use for NonLinearPlace, PlaceObj, differentiable anchor/keep-in objectives, irregular density capacity, projection lifecycle, initialization, E0-E4, and native HPWL/RSMT evidence. Do not use for open-ended CP-SAT exact-site topology enumeration.
---

# M336 native Cypress recovery

## Read first

1. `AGENTS.md`
2. `CLAUDE.md`
3. `BUILD.md`
4. `experiments/m336/SPEC.md`
5. `experiments/m336/NATIVE_CYPRESS_GOAL.md`
6. `experiments/m336/NATIVE_CYPRESS_PLAN.md`
7. `docs/issues/ACTIVE_ROADMAP.md`
8. `docs/issues/M336-002-soft-keepin-zero-gradient.md`
9. `docs/issues/M336-003-acceptance-shortfalls.md`
10. `docs/issues/M336-005-initialization-runtime-quality.md`
11. `docs/issues/M336-140-target-net-span-data2-closure-collapse.md`

The native goal and plan govern this task when they conflict with the deferred
exact-site priority in the current roadmap.

## Scope discipline

- Primary optimizer: `NonLinearPlace` and `PlaceObj`.
- Exact-site artifacts: immutable references, warm starts, validators, and
  bounded repair aids only.
- Do not extend candidate K, no-good ladders, residual CP-SAT portfolios,
  one-opt chains, or pair scans.
- Preserve untracked `experiments/m336/guides/M336-141/`.
- Never claim Cypress improvement from a fixed/exact-site result.

## Workflow

1. Establish branch, head, dirty state, build/install parity, GPU environment,
   and M336-141 preservation.
2. Reproduce native score and current native E0-E4 baseline.
3. Fix objective purity and projection lifecycle.
4. Implement differentiable interior keep-in margin.
5. implement group-balanced adaptive anchor weighting.
6. make two-side density aware of irregular usable capacity.
7. preserve legal warm starts and localize repair.
8. run staged native experiments and final three-seed matrix.
9. update roadmap/report with actual evidence.

## Evidence standard

A run counts as native placement only when logs and metrics prove:

- `NonLinearPlace` executed;
- objective/backward executed;
- an optimizer step changed or evaluated trainable placement coordinates;
- CUDA/PyTorch device and deterministic settings are recorded;
- output was independently scored with native HPWL/RSMT;
- exact legality was checked after serialization.

## Final response

Return changed files, architecture, commands, build information, tests, native
E0-E4 metrics, runtime breakdown, failed ablations, exact legality, native
scores, acceptance checklist, uncommitted-state summary, and review hotspots.
Do not push unless explicitly instructed.
