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
