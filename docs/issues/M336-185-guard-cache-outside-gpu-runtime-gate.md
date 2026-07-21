# M336-185: Guard Cache Is Outside the GPU Runtime Gate

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `305e9d4`

## Finding

M336-184 removes duplicate exact validation from the accepted-step guard, but
that work is explicitly excluded from the fixed `gpu_optimization_seconds`
metric. It can improve end-to-end runtime; it cannot by itself close the E2 GPU
gate used by M336-179.

`NonLinearPlace` computes the metric as:

```text
optimization wall time
- exact overlap diagnostics
- exact step guard overhead
= gpu_optimization_seconds
```

The preserved M336-183 E2 artifact reports:

| Timing domain | Seconds |
| --- | ---: |
| Raw optimization window | `2.635054652` |
| Exact overlap diagnostics, excluded | `0.012923701` |
| Exact guard overhead, excluded | `0.275603049` |
| GPU optimization metric | `2.346527902` |
| Fixed E2 limit | `2.161724000` |
| Remaining counted-path gap | `0.184803902` |

The duplicate proposal and accepted validations total `0.244548114 s`, but
both are included in `exact_step_guard_overhead_seconds`. Removing them reduces
the raw window and the excluded guard term by approximately the same amount.
The gate therefore remains approximately unchanged before considering cache
bookkeeping. Provenance capture itself runs inside contact projection and is
counted, so no favorable GPU-stage effect may be assumed without measurement.

## Counted-Path Profile

The same artifact attributes `1.047041154 s` to guarded optimizer attempts,
including `0.943923393 s` of exact contact projection. Nested contact timing
includes:

| Contact substage | Seconds |
| --- | ---: |
| Global exact validator | `0.332145968` |
| Authority projection | `0.039624536` |
| Authority exact validator | `0.194631828` |
| Topology tie-break, 34 score calls | `0.147202069` |

These nested values are profile guidance, not independent additive savings.
Any runtime successor must reduce work in the counted optimizer/contact path or
another included stage while preserving exact coordinates and every quality
gate.

## Required Correction

1. Retain M336-184 as a strict end-to-end optimization and exact provenance
   mechanism; do not mislabel it as an E2 GPU-gate fix.
2. Preserve the fixed M336-179 timing definition and denominator. Moving work
   between timing buckets is not an optimization.
3. Add regression coverage for the runtime-accounting identity before changing
   timing code or making another runtime claim.
4. Report raw optimization, excluded guard/diagnostic time, counted optimizer
   attempt time, contact time, and final GPU metric separately in the next D1.
5. Do not authorize a fresh combined D1 solely because M336-184's excluded
   opportunity exceeds the counted-path gap. A counted-path candidate or an
   explicit measurement-only authorization is required first.

## Experiment Boundary

This finding comes entirely from committed code and the preserved M336-183
artifact. No optimizer, scorer, CP-SAT solve, repair, fallback, parameter
change, or M336 effect run was executed. D2, D3, E4, seed ladders, and resumed
M336-141 work remain prohibited.

## Acceptance Criteria

- Runtime reports prove the accounting identity from raw stage timings.
- No excluded guard saving is claimed against the fixed GPU-stage limit.
- A strict-equivalent counted-path candidate has direct parity tests before an
  effect run.
- A later authorized D1 passes both the unchanged GPU and end-to-end gates.
