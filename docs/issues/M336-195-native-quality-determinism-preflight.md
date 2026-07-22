# M336-195: Native Quality Determinism Preflight

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-22
**Authorization:** Human request to begin the next N8 stage
**Input milestone:** `4cbae5c` / N6 complete, N7 deferred

## Objective

Execute N8-A before the final native matrix. The evidence must determine whether
the production `consensus_per_step` path repeats exactly across cold/source and
M336-118 checkpoint-warm initialization while preserving native execution and
exact legality. This is a quality and robustness preflight, not runtime tuning.

## Frozen Effect Contract

Run seed `1000`, 50 CUDA Adam steps, scale `1`, E2 and E3, with two fresh
repeats on each initialization track. The eight subprocesses run in this order:

```text
1 checkpoint_warm_start E2 repeat_01
2 checkpoint_warm_start E2 repeat_02
3 checkpoint_warm_start E3 repeat_01
4 checkpoint_warm_start E3 repeat_02
5 cold_source          E2 repeat_01
6 cold_source          E2 repeat_02
7 cold_source          E3 repeat_01
8 cold_source          E3 repeat_02
```

Use the complete M336-193 production configuration: GPU execution, irregular
density, footprint collision ratio `0.1`, margin `0 mm`, tau `0.025 mm`, exact
guard backoff `0.5` with four retries, exact contact projection with
`consensus_per_step`, eight contact iterations, 32 corrected nodes, no pair
diagnostics, grid `0.05 mm`, Keep-in margin `0.1 mm`, and margin tau `0.05 mm`.
Use M336-118 placement and assignment, manual `EMI601`, runtime `Q601`, and
`CUBLAS_WORKSPACE_CONFIG=:4096:8`. Every arm gets isolated output, summary,
report, and validation paths below
`results/m336/native-cypress/n8-a-quality-determinism-preflight/`.

## Environment Classification

Select the first physical-index H100 with sampled utilization `0%` and at least
`32 GiB` free memory. The preflight selects physical GPU 2,
`GPU-ab571afa-cbb6-542c-f2d2-1ccf5045d040`, driver `550.54.14`, CUDA `12.4`.
It has three foreign contexts: `muge-api`, `VLLM::EngineCore`, and YOLO. The
campaign is therefore explicitly `shared_environment`; timing is observational
and cannot count as clean N7 or repeated paired `2x` evidence. GPU identity must
remain fixed. Each arm has a 30-minute infrastructure timeout.

## Hard Gates

Every E2/E3 run must prove `NonLinearPlace`, `PlaceObj`, 53 backward calls, 50
changing optimizer steps, zero positive-area overlap and zero Keep-in violations
at every accepted checkpoint, `100/100` final containment, zero replay drift,
finite native HPWL/RSMT, and no repair, fallback, Legalization, CP-SAT,
authority enumeration, FLUTE hot-loop selection, or stage micro.

The two repeats for each experiment/track must match placement and replay
hashes, HPWL, FLUTE RSMT, normalized score, exact legality, accepted/rejected
attempt sequence, and final effective LR. Stop before remaining arms on any
hard-gate or provenance failure. Do not tune LR, anchor, collision, density, or
Keep-in settings in response.

## Required Diagnosis

Compare E3 against E2 independently for each track. Report anchor mean and p90
by side and subgroup, gradient ratios, effective lambda, accepted displacement,
projection, rollback, and contact pressure. Report per-net HPWL/RSMT deltas
against M336-118 and the manual baseline to explain the approximately `0.928`
normalized native score. N8-B remains blocked until this issue records a passing
N8-A decision in a signed, pushed, and pulled evidence commit.

No effect ran while creating this issue.
