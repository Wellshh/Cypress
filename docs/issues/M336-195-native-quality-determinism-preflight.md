# M336-195: Native Quality Determinism Preflight

**Severity:** Critical
**Status:** Resolved
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

## N8-A Effect Evidence

The eight authorized arms ran at pushed and pulled commit `60ea9d6` on physical
GPU 2 (`GPU-ab571afa-cbb6-542c-f2d2-1ccf5045d040`, H100, driver `550.54.14`,
CUDA `12.4`). The GPU retained foreign contexts, so the environment is
`shared_environment`: runtime below is observational and is not N7 evidence.
Source/install parity was exact and all arms used the same input hashes.

| Track | Arm | Placement/replay SHA-256 | HPWL | RSMT | Score | GPU / E2E seconds |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| warm | E2 r1/r2 | `d6242e54...9e4eb` | 15634.399745 | 17326.965 | 0.928015545 | 6.557/18.907, 6.241/18.407 |
| warm | E3 r1/r2 | `9f601023...ce61d` | 15633.964617 | 17327.178 | 0.928022603 | 6.385/18.993, 6.349/19.056 |
| cold | E2 r1/r2 | `382243e5...f2e88` | 19734.497741 | 21376.008 | 0.743691330 | 6.828/72.696, 6.756/72.889 |
| cold | E3 r1/r2 | `510f4472...279f5` | 19734.292189 | 21376.312 | 0.743689945 | 6.197/71.558, 6.383/72.337 |

Each repeat pair is identical in placement/replay hash, HPWL, RSMT, score,
legality, accepted/rejected sequence, and final effective LR. The corresponding
sequence hashes are `8402378d...5408`, `02ea14fc...d4a`,
`8a31c6f5...c97`, and `7b5644ce...ad9`. Every run records 53 backward calls,
50 changing CUDA Adam steps, 50 accepted steps, and 51 exact checkpoints with
zero overlap and zero Keep-in violations. Final legality is `100/100`, zero
overlap, and zero float64 replay error. E2/E3 rejection counts are `8/6` warm
and `12/8` cold; every rejected candidate fails closed and retries from the
same position with optimizer rollback plus LR backoff. No repair, fallback,
Legalization, CP-SAT, authority enumeration, FLUTE hot-loop selection, or stage
micro ran.

## Quality Diagnosis

The E3 controller is active rather than silently ineffective. Its final
anchor-to-wirelength gradient ratio is exactly `0.1`; final effective lambda is
`1.001761` warm and `0.808891` cold. Anchor loss falls only `0.996735 ->
0.991113` warm and `2.221087 -> 2.215366` cold. Constrained-node net movement
is only `0.017823 mm` mean warm and `0.014304 mm` mean cold.

Consequently, E3 changes anchor mean by only `-0.000274 mm` warm and
`-0.000278 mm` cold. Overall p90 changes by `+0.000222 mm` and `+0.000119 mm`,
respectively. Warm TOP/BOTTOM means both improve (`-0.000513/-0.000172 mm`),
but their p90 values worsen slightly. Cold side-specific p90 values improve,
while the combined p90 worsens because cross-side percentile membership
changes. Subgroup changes are mixed, confirming that the global mean signal
does not create a material cluster relocation in 50 steps.

The manual native baseline is HPWL `14627.847656` and RSMT `15950.065430`.
Warm E3 remains `6.878%` worse in HPWL and `8.634%` worse in RSMT. Its largest
native per-net HPWL gaps are `N31799771 +491.938`, `N31376589 +403.941`,
`VCHARGE_11P0 +346.147`, `ANT_GND +273.262`, `GND +259.071`, and
`N31799783 +233.340`. E3-versus-E2 changes are tiny: the largest absolute net
change is `N31831544 -0.192`; the total HPWL gain is only `0.435`. This explains
the stable score near `0.928`: legal continuous steps preserve the M336-118
topology and cannot close the dominant long-net gaps. Warm E3 slightly improves
M336-118 HPWL by `0.486` and RSMT by `5.859`; cold initialization instead lands
near score `0.744`, about `34%` worse than the manual baseline in both metrics.

The native scorer exposes total FLUTE RSMT but no per-net RSMT ledger. N8-A did
not alter scoring to invent that attribution; per-net diagnosis therefore uses
native HPWL, with total native RSMT reported separately.

## Decision

N8-A passes every predeclared correctness, determinism, provenance, and replay
gate. It diagnoses two distinct quality limits: checkpoint-warm optimization is
trapped in the M336-118 local topology, while cold/source initialization starts
from a reproducible but substantially poorer basin. N8-B is now authorized by
the committed plan but was not run in this node. Its purpose is cross-seed
robustness evidence, not parameter tuning.

The eight-arm artifact tree SHA-256 before adding aggregate files is
`8e05c74a5042e9d704385b88849d190974609471e687247e827ed793e2a68ea1`.
All artifacts remain under
`results/m336/native-cypress/n8-a-quality-determinism-preflight/`.
