# M336-194: Paired Production Runtime Evidence

**Severity:** Critical
**Status:** Open
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
