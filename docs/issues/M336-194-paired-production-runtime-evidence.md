# M336-194: Paired Production Runtime Evidence

**Severity:** Critical
**Status:** Deferred
**Decision state:** `deferred_environment_unavailable`
**Found:** 2026-07-22
**Authorization:** Human N7 measurement decision
**Input milestone:** `87f1cc8` / M336-193 D3 complete

## Problem

M336-193 promotes the existing M336-174 component-consensus contact mechanism
as the production candidate and preserves M336-192 as `strict_reference`.
Its first fixed comparison passes the `2x` runtime gate, but a single timing
sample is insufficient for production promotion. N7 must measure paired
feature-off and `consensus_per_step` runs without changing either algorithm or
the established timing boundaries.

## Frozen Contract

Each arm uses physical GPU 2, deterministic CuBLAS, seed `1000`, 50 CUDA Adam
steps, scale `1`, checkpoint-warm M336-118 initialization and assignment,
manual `EMI601`, runtime `Q601`, the `0.05 mm` grid, irregular density, and the
same native float64 validation and HPWL/FLUTE scorer.

The feature-off arm disables the footprint barrier, exact accepted-step guard,
exact contact projection, pair diagnostics, and named contact policy. Its
overlaps are diagnostic and must not be repaired. The production arm enables
the unchanged ratio `0.1`, margin `0`, tau `0.025 mm`, guard backoff `0.5`,
four retries, `consensus_per_step`, eight contact iterations and 32 corrected
nodes. Authority enumeration, topology tie-break and stage micro remain off.

After removing run-local paths and the declared contact-stack fields, the two
placement configs must be byte-equivalent. Any other difference is contract
drift and stops N7.

## Paired Protocol

Run one unmeasured warm-up pair for E2 and one for E3. Then run five measured
pairs independently for E2 and E3. Every arm is a fresh runner/native
subprocess with a fresh output, summary and report path. Pair order alternates:

```text
1 feature_off -> consensus_per_step
2 consensus_per_step -> feature_off
3 feature_off -> consensus_per_step
4 consensus_per_step -> feature_off
5 feature_off -> consensus_per_step
```

Only the declared feasible-domain cache may be reused. Resume, reevaluation,
result reuse, D2, D3 reruns, E4, repair, fallback, legalization, CP-SAT and
parameter ladders are prohibited.

For GPU and end-to-end time, retain the raw paired values and deltas and report
all five ratios, median, minimum, maximum, arithmetic mean, geometric mean and
median absolute deviation. E2 and E3 each pass only when both median ratios are
at most `2.0`.

## Environmental Validity

Record physical index, UUID, driver/CUDA, temperature, P-state, SM/memory
clocks, power, memory and active compute processes before, during and after
every measured pair. Any foreign compute process, GPU identity change,
interruption, missing artifact or source/install/input drift invalidates that
attempt. Preserve it and allow at most one replacement. A second invalid
attempt stops N7 incomplete. Timing alone is never an invalidation reason.

## Correctness And Determinism

Every production run must prove `NonLinearPlace`, `PlaceObj`, 53 backward
calls, 50 changing Adam steps, exact legality at every accepted position,
`100/100` final containment, zero replay drift and finite native HPWL/RSMT.
Repair, fallback, authority states and topology records must remain absent.

All five production outputs per experiment must have identical placement and
replay hashes, HPWL, RSMT, normalized score, legality, accepted/rejected
sequence and final LR. Feature-off outputs must also repeat deterministically;
their positive overlaps do not invalidate the denominator. A correctness or
determinism failure stops the campaign immediately and is not a timing result.

## Implementation Gate

Measurement support may change only the M336 runner, focused tests, result
schemas and documents. It must test order, warm-up exclusion, config
equivalence, paired statistics, path isolation, resume rejection, provenance
drift, foreign-process invalidation, replacement limits, timing identity,
parameter immutability and deterministic aggregation. Applicable source and
installed tests must pass without claiming TEST-001's aggregate entrypoint is
green.

Commit, sign, push and pull the measurement implementation before the single
authorized N7 campaign. Generated bulk logs remain ignored; final evidence is
recorded append-only in this issue.

## Decision Gate

If all four median timing gates and every correctness/determinism gate pass,
close N7, promote `consensus_per_step` as the M336 production native
non-overlap policy and mark N6 engineering complete. Otherwise preserve the
complete distribution and request a human decision without tuning or changing
the `2x` contract.

No N7 effect has run while creating this issue.

## Measurement Implementation Evidence

The runner now has a measurement-only N7 parent mode and isolated child-arm
mode. It constructs the frozen feature-off and `consensus_per_step` commands,
rejects resume, verifies config equivalence after an explicit field whitelist,
checks source/install/static-input/cache provenance, samples GPU identity and
processes synchronously, preserves invalid attempts, and permits exactly one
environmental replacement. Statistics retain the existing timing identity:

```text
gpu_optimization_seconds = optimization_wall_seconds
                         - exact_step_guard_seconds
                         - exact_overlap_diagnostic_seconds
```

Generated manifests containing
run-local absolute paths are excluded from the paired input digest; all native
Bookshelf files, geometry, checkpoint and assignment hashes remain mandatory.

After `cmake --install build`, all `271/271` existing applicable tests and all
`15/15` focused N7 tests pass with the installation tree first. The existing
breakdown is anchor/keep-in `64`, exact contact `63`, exact guard `11`,
reproducibility `22`, irregular density `9`, and non-CP-SAT M336 baseline
`102`. Five OR-Tools tests were explicitly filtered and no CP-SAT solve ran.
The focused N7 suite also passes source-first. Direct source-first probes for
the three suites importing compiled operators cannot load `place_io_cpp`,
`move_boundary_cpp`, or `weighted_average_wirelength_cpp`; their installed
counterparts pass. The known TEST-001 aggregate entrypoint was not claimed
green.

Core source/install hashes remain byte-identical:

```text
NonLinearPlace.py              b7f01be5ae91d9f2913298b6cc70e118fdd346b0f543d641c9ab90127477f5a7
PlaceObj.py                    a3dbef9aa8f9956df8144d111b481252cda2990adfa0d4ae26c48c4b5cd83489
exact_contact_projection.py   ef7f3130b706cbe0694dba51a93403d4bc84531feedb0e426336a4c2771d8ccc
exact_step_guard.py            30bd8ed624bb5e8a691470e7f595d64bdcca87afbf238ad652fdd28429354d58
params.json                    19ca9b959653d4c27e58505fc4af7fe45d6231fa401b8cb159a656f16c16c509
```

The live monitor resolves physical GPU 2 as
`GPU-ab571afa-cbb6-542c-f2d2-1ccf5045d040`, driver `550.54.14`, CUDA `12.4`.
Three foreign compute processes currently occupy that GPU, so the N7 effect
remains frozen until a clean pre-pair sample exists. No warm-up or measured arm
has run during implementation.

## N7 Environment-Incomplete Attempt

The single authorized campaign started from signed, pushed and pulled commit
`6dfc60e` on physical GPU 2. The E2 warm-up preflight detected the same three
foreign CUDA contexts before either arm launched. Attempt 1 was preserved and
used the only permitted replacement; attempt 2 found the same condition and
stopped N7 incomplete as specified.

| Process | PID | GPU memory |
| --- | ---: | ---: |
| `muge-api` | `1996746` | `28558 MiB` |
| `VLLM::EngineCore` | `1814710` | `10430 MiB` |
| `/data/liuwenqi/yolov11/bin/python3.1` | `1272798` | `1292 MiB` |

Both attempts observed UUID `GPU-ab571afa-cbb6-542c-f2d2-1ccf5045d040`,
driver `550.54.14`, temperature `37 C`, P-state `P0`, SM/memory clocks
`1980/1593 MHz`, about `140 W`, `40310 MiB` resident memory, and zero sampled
SM/memory utilization. Idle utilization does not override the frozen foreign-
process rule.

```text
campaign status       environment_incomplete
decision              incomplete_human_decision_required
warm-up attempts      2 invalid / 0 valid
optimizer arms        0
measured pairs        0
timing gates          not evaluated
candidate determinism not evaluated
```

Artifacts remain under
`results/m336/native-cypress/n7-paired-timing/`:

```text
contract.json         7b781a34a8b7f572dd4268b57c8253d464a5c41cc477ac6ace79405004da2cb0
environment.json      a176d5492f795d53a1004564eeef71d34cb470ff4a922c5d04c4cbd6eca5710e
paired-summary.json   2025885b296f779eec9644ac0a399bc3c9e38899e54990a52b164a8401c2b5c5
REPORT.md              ec30e699a829e9024f5eafa00473b217a247af4375c189be92d7d5525d9bfcc0
attempt 1              de61311e3bd605c883a7c8553911c06b8d707a0ab62cda5beeb00edc8c763f4b
attempt 2              e3342402c4b3e7978eef18992fa45c640b737c137667ccfe016b91b5b7fc1140
```

Source/install parity, the read-only cache manifest, branch/HEAD, and all
preserved user-owned hashes remained unchanged. No NonLinearPlace arm, D2, D3
rerun, E4, stage micro, repair, fallback, CP-SAT, one-opt, pair scan or tuning
ran. N7 remains open. A human must either provide a clean physical GPU 2 and
authorize a fresh isolated campaign or explicitly revise the environmental
contract; the current artifacts must not be reused or deleted.

## Human Clean-GPU Decision And Inventory Block

The human decision on 2026-07-22 explicitly rejects treating `muge-api`,
`VLLM::EngineCore`, YOLO, or any other resident CUDA process as an approved
idle context. It supersedes only the physical-GPU-2 pin: a fresh N7 campaign
may use the first compatible GPU selected by ascending physical index when the
model is `NVIDIA H100` and its compute-process list is empty. The selected UUID
must then remain fixed for the complete fresh campaign. The original
`n7-paired-timing/` campaign remains immutable and excluded from all future
timing statistics.

The deterministic prelaunch scan at `2026-07-22 14:47:10` Asia/Hong_Kong found
driver `550.54.14`, CUDA `12.4`, and no clean GPU. Every physical device was the
correct H100 model but had at least one foreign compute process:

| Index | UUID | Memory MiB | Util. | Temp | P-state | SM/mem MHz | Power W | Processes | Decision |
| ---: | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | --- |
| 0 | `GPU-4bfe08ef-cfa9-efd2-52c8-9696d5e9c7a7` | 93334/97871 | 100% | 67 C | P0 | 1665/1593 | 481.10 | 9 | reject |
| 1 | `GPU-0cc1ecd3-1adb-ac2b-a041-b5052d935a69` | 91300/97871 | 100% | 60 C | P0 | 1695/1593 | 480.33 | 4 | reject |
| 2 | `GPU-ab571afa-cbb6-542c-f2d2-1ccf5045d040` | 40310/97871 | 0% | 36 C | P0 | 1980/1593 | 139.87 | 3 | reject |
| 3 | `GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e` | 70474/97871 | 0% | 52 C | P0 | 1980/1593 | 144.35 | 10 | reject |
| 4 | `GPU-03b2a421-fa18-3a6f-07ad-fc80d91a91ff` | 89201/97871 | 0% | 51 C | P0 | 1980/1593 | 125.42 | 2 | reject |
| 5 | `GPU-500c112e-cdd9-4e0d-d709-63de81493d96` | 95008/97871 | 0% | 35 C | P0 | 1980/1593 | 137.73 | 1 | reject |
| 6 | `GPU-82df78d9-35bf-e390-42af-8a26e043de9b` | 88063/97871 | 100% | 59 C | P0 | 1680/1593 | 483.47 | 2 | reject |
| 7 | `GPU-43b64459-dc96-a693-482f-0b423f7f4b74` | 83810/97871 | 100% | 65 C | P0 | 1770/1593 | 486.17 | 1 | reject |

The complete process inventory used for the decision was:

| GPU | PID | Process | Memory MiB |
| ---: | ---: | --- | ---: |
| 0 | 6264 | `/home/lizf/.conda/envs/py311v2/bin/python` | 674 |
| 0 | 29935 | `/home/wuwj/.conda/envs/lc/bin/python` | 840 |
| 0 | 4714 | `/home/xuxuhui/package_comparator/venv/bin/python3.11` | 520 |
| 0 | 2059631 | `/home/wuwj/.conda/envs/lc/bin/python` | 4358 |
| 0 | 257089 | `/home/hanchuanyi/.conda/envs/paddle/bin/python` | 778 |
| 0 | 115737 | `python` | 902 |
| 0 | 1272798 | `/data/liuwenqi/yolov11/bin/python3.1` | 520 |
| 0 | 1273737 | `/data/liuwenqi/yolov11/bin/python3.1` | 520 |
| 0 | 127656 | `VLLM::Worker_TP0` | 84136 |
| 1 | 257089 | `/home/hanchuanyi/.conda/envs/paddle/bin/python` | 1188 |
| 1 | 1806419 | `tritonserver` | 580 |
| 1 | 1806905 | `/opt/tritonserver/backends/python/triton_python_backend_stub` | 5338 |
| 1 | 127957 | `VLLM::Worker_TP1` | 84136 |
| 2 | 1996746 | `muge-api` | 28558 |
| 2 | 1814710 | `VLLM::EngineCore` | 10430 |
| 2 | 1272798 | `/data/liuwenqi/yolov11/bin/python3.1` | 1292 |
| 3 | 1115322 | `/home/lizf/.conda/envs/py311v2/bin/python` | 1598 |
| 3 | 3298512 | `/home/lizf/.conda/envs/py311v2/bin/python` | 1598 |
| 3 | 121859 | `/data/liuwenqi/yolo_api/../yolo8.1/bin/python` | 748 |
| 3 | 3629722 | `/home/mujingyin/.conda/envs/audio-beats/bin/python` | 1482 |
| 3 | 825126 | `VLLM::EngineCore` | 48240 |
| 3 | 1220022 | `/home/lizf/.conda/envs/py311v2/bin/python` | 1598 |
| 3 | 3853107 | `python` | 10194 |
| 3 | 1945357 | `/home/lizf/.conda/envs/py311v2/bin/python` | 1598 |
| 3 | 1273184 | `/data/liuwenqi/yolov11/bin/python3.1` | 2024 |
| 3 | 1273737 | `/data/liuwenqi/yolov11/bin/python3.1` | 1292 |
| 4 | 103731 | `/home/lizf/.conda/envs/py311v2/bin/python` | 88348 |
| 4 | 133520 | `/home/wuwj/.conda/envs/lc/bin/python` | 838 |
| 5 | 3351777 | `VLLM::EngineCore` | 94994 |
| 6 | 1859508 | `/data/yangyizhu/envs/comfyui/bin/python` | 4242 |
| 6 | 128319 | `VLLM::Worker_TP2` | 83770 |
| 7 | 128581 | `VLLM::Worker_TP3` | 83770 |

Selection therefore returned no candidate and stopped before creating a fresh
campaign directory or launching any warm-up or measured arm. No runner,
Cypress algorithm, policy, parameter, scoring path, or timing bucket changed.
N7 remains open, with all four timing gates and determinism still unevaluated.

## Human Waiver And Deferment Decision

The human decision on 2026-07-22 stops runtime micro-optimization and removes
N7 from the production-promotion critical path. This is an append-only policy
decision; it does not reinterpret or remove either environment-incomplete
attempt above.

The resulting production state is:

- promote `consensus_per_step` as the M336 production native non-overlap
  policy;
- retain `strict_reference` intact, default off, with all M336-192 tests,
  diagnostics, exact legality, and source/install parity obligations;
- keep `consensus_plus_stage_micro` reserved and fail closed;
- mark N6 native non-overlap engineering complete;
- mark N7 `deferred_environment_unavailable`, neither passed nor failed.

The acceptance basis is the M336-193 production evidence, not N7. Phase A
passed its original single-run GPU and end-to-end `2x` comparisons. Its
checkpoint-warm D3 then completed 50 changing CUDA Adam steps in both E2 and
E3, with every accepted step zero-overlap and Keep-in legal. Both final
placements were `100/100` contained with zero overlaps. No E4, repair,
fallback, Legalization, CP-SAT, authority enumeration, or FLUTE hot-loop
selection contributed to those results.

N7 did not statistically verify the repeated paired `2x` gate. All four paired
median gates, paired distributions, and repeated-run determinism checks remain
unevaluated. A future N7 campaign on one isolated compatible GPU remains a
non-blocking infrastructure audit. Its process-isolation rule, timing buckets,
and `2x` definitions remain frozen; no workload may be relabeled clean and no
runtime boundary may be changed to manufacture a pass.

The incomplete campaign remains byte-preserved with the hashes already listed
above. Subsequent native runs must continue reporting unchanged runtime buckets
as observed metrics, but this decision prohibits further Cypress changes whose
purpose is merely recovering tens of milliseconds.

The next active milestone is N8 native quality and robustness. It must use
`consensus_per_step`, preserve exact legality and deterministic hashes as hard
production gates, separate cold/source and checkpoint-warm evidence, and
diagnose the negligible E3 anchor improvement and approximately `0.928`
normalized native score. Stage micro, strict-reference hot-loop work, LR or
collision tuning, CP-SAT, repair, and fallback remain out of scope.
