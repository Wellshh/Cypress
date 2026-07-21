# M336-184: Exact Guard Revalidates Contact-Proven Coordinates

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `793d1d1`

## Problem

M336-183 reduces E2 GPU optimization from `2.609474063 s` to
`2.346527902 s`, but the fixed limit is `2.161724 s`. The remaining gap is
`0.184803902 s`.

The exact-contact and accepted-step boundaries currently validate the same
coordinates twice. `ExactContactProjector` obtains an exact report before
contact correction and another report after the selected correction converges.
`ExactAcceptedStepGuard` then independently validates its raw proposal and
accepted placement, even when those tensors are byte-identical to the two
contact-proven tensors.

The M336-183 E2 trace makes this duplication measurable:

```text
guard proposal validation       0.123220606 s
guard accepted validation       0.121327508 s
combined duplicate opportunity  0.244548114 s
current E2 runtime gap           0.184803902 s
```

For all ten steps, guard proposal and contact-initial overlap counts and exact
areas are identical. This is evidence of duplicate work, not permission to
skip validation based on matching aggregate metrics.

## Required Mechanism

Introduce a private, single-use exact-validation provenance cache. It must not
change any legality rule, public result schema, optimizer state, placement
coordinate, or failure policy.

1. `ExactContactProjector` retains the exact initial/final report together with
   detached coordinate snapshots from the validator calls that produced them.
2. `_CompositeProjector` consumes that cache immediately. It exposes a proposal
   report only when the raw optimizer proposal is tensor-identical to the
   contact input after board/region projection. It exposes an accepted report
   only when the final accepted tensor is identical to the contact-proven final
   snapshot.
3. `ExactAcceptedStepGuard` accepts a cached report only as a `(position,
   report)` pair after checking shape, dtype, device, and exact tensor equality.
   A partially supplied or mismatched cache is an internal contract error and
   must roll back and fail closed.
4. Cache state is cleared at every step and consumed once. It may never survive
   a retry, projector exception, or unrelated position.
5. Cached reports continue to populate the existing `proposal` and `projected`
   evidence fields. Add only cache-hit/provenance diagnostics; do not remove
   overlap rows or timings from the schema.

When board/region projection changes the raw proposal, proposal validation must
still run normally. When contact projection is absent, disabled, non-converged,
or lacks exact provenance, the historical guard path remains unchanged.

## Required Tests

1. Validator spies prove matching proposal and accepted caches remove exactly
   two duplicate calls without changing reports or coordinates.
2. Region-changed proposal bytes disable only the proposal cache; the accepted
   cache may still be used when independently matched.
3. Missing half-pairs, shape/dtype/device differences, and coordinate mismatch
   fail before acceptance and restore optimizer state.
4. A cached illegal report still rejects the step; cache provenance cannot turn
   an illegal result into a legal one.
5. Retry and exception paths cannot reuse a prior attempt's report.
6. CPU/GPU float32/float64 fixtures preserve exact report contents and stable
   result bytes outside timing/cache diagnostics.
7. Feature-off, no-contact, and historical contact modes retain their current
   validator-call behavior.

## Experiment Boundary

This is a strict runtime implementation change, not a quality mechanism. Its
`0.244548114 s` opportunity is an upper bound from one failed D1 trace, not a
runtime claim. Implement, install, test, commit, push, and pull without running
another M336 effect experiment. A fresh combined D1 remains unauthorized until
the user explicitly resets or approves it. Do not resume M336-183, run E3
alone, alter budgets, or introduce repair/fallback/CP-SAT assets.

## Acceptance Criteria

- Every reused report has exact tensor-level provenance.
- No exact validator result or legality decision changes.
- Cache mismatches fail closed and rollback transactionally.
- Default/no-contact behavior remains byte-compatible.
- A later authorized D1, if any, must still pass the fixed E2/E3 runtime,
  quality, legality, anchor, serialization, and determinism gates.
