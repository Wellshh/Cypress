# M336-186: Global Exact Validator Performs Scalar Device Synchronization

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `db750d0`

## Finding

The counted exact-contact path calls
`AnchorKeepInContext.exact_overlap_report()`, whose `_position_audit()` reads
every lower-left coordinate through `_position_value()`:

```python
float(value.detach().cpu())
```

M336 has 100 constrained components and 40 validated obstacle components. Each
global audit therefore performs 280 scalar position reads. The preserved
M336-183 E2 contact trace makes 27 global validator calls, producing 7,560
scalar device-to-host synchronizations inside the fixed GPU timing domain.

Those 27 calls consume `0.332145968 s`, or `12.3017 ms` per call. This is
distinct from M336-184's excluded guard validation and is a valid counted-path
optimization target.

## Independent Transfer Probe

A standalone coordinate-extraction fixture used the same 140-node,
concatenated float32 tensor shape. It did not construct a placement, optimizer,
or M336 result.

| Device | 280 scalar reads | One batched read | Median speedup |
| --- | ---: | ---: | ---: |
| CPU | `0.629817 ms` | `0.024938 ms` | `25.26x` |
| NVIDIA H100 | `4.202676 ms` | `0.047267 ms` | `88.91x` |

Across 27 global contact validations, coordinate extraction alone has an
optimistic reduction of about `0.112 s`, approximately 61% of the remaining
`0.184803902 s` E2 GPU gap. It is material but insufficient by itself. A
complete candidate must also avoid rebuilding provably unchanged fixed
geometry while preserving every exact predicate.

## Required Mechanism

1. Transfer the concatenated physical-node coordinates to host exactly once per
   global audit. Preserve source dtype values; do not quantize, round, or move
   coordinates.
2. Rebuild every constrained footprint and side-local constrained STRtree from
   the current snapshot because all constrained nodes may move.
3. Cache fixed-obstacle footprints and side-local STRtrees only under a complete
   key containing the PlaceDB identity, fixed node order, and exact lower-left
   coordinate tuple. Any fixed-coordinate change invalidates the cache before
   query.
4. Preserve the current physical local footprints, side split, keep-in
   difference, Shapely intersection, area epsilon, pair ordering, and conflict
   closure exactly. No approximate geometry or relaxed broadphase is allowed.
5. Emit audit call, batched-transfer, fixed-cache hit/miss, and elapsed-time
   diagnostics so a later D1 can attribute the counted reduction.
6. Keep the mechanism internal and unconditional-equivalent; do not add an M336
   tuning parameter or change feature-off placement behavior.

## Required Tests

- Reference and optimized reports are byte-identical for legal, keep-in
  violation, constrained-constrained, and constrained-fixed cases.
- CPU/GPU float32/float64 coordinates produce identical report contents.
- Moving any fixed obstacle invalidates the cache and changes the report exactly
  as a fresh rebuild would.
- Repeated unchanged audits hit the fixed cache without retaining stale
  constrained footprints.
- Source/install hashes match and existing anchor, contact, guard,
  reproducibility, density, and non-CP-SAT M336 suites remain green.

## Experiment Boundary

The finding uses source inspection, the preserved M336-183 timing artifact, and
an isolated tensor-transfer probe. No M336 placement, optimizer, scorer,
repair, fallback, CP-SAT solve, parameter change, or M336-141 work was run.
Commit, push, pull, implement, and parity-test this issue before requesting any
effect run. D2, D3, E4, and ladders remain prohibited.

## Acceptance Criteria

- Every global audit uses one batched coordinate snapshot.
- Fixed geometry is reused only under an exact complete cache key.
- Exact reports and accepted coordinates remain byte-identical to the scalar
  reference path.
- A later authorized combined D1 reports lower counted contact and GPU time and
  still passes all legality, quality, determinism, and end-to-end gates.

## Implementation Evidence

The strict-equivalent implementation is complete; the issue remains open until
an explicitly authorized combined D1 measures the unchanged fixed gate.

- Every audit copies the flat tensor to a dtype-preserving host snapshot once.
  All subsequent scalar reads use that host array.
- The fixed cache key includes the live PlaceDB object identity, fixed-node
  order, names, side flags, dimensions, source dtype, and exact coordinate
  bytes. The cache retains the PlaceDB object and also checks it with `is`, so
  Python object-ID reuse cannot create a false hit.
- Fixed footprints and TOP/BOTTOM STRtrees are reused only on an exact key hit.
  Constrained footprints and their side-local STRtrees are rebuilt on every
  audit from the current snapshot.
- Native execution evidence now records audit calls, batched snapshot count and
  time, fixed-cache hits/misses, cached fixed-node count, and total audit time.
  These diagnostics do not change the M336-185 timing-domain formula.

Reference fixtures compare sorted JSON report bytes for legal, keep-in-invalid,
constrained-constrained, and constrained-fixed placements. CPU/H100 float32 and
float64 results are identical. A second fixture proves unchanged constrained
coordinates hit the fixed cache, moving a constrained node never reuses its
footprint, and moving a fixed node misses the cache and matches a fresh context.

After `cmake --install build`, all `260/260` applicable tests pass: anchor and
keep-in `56`, exact guard `11`, exact contact projection `61`, reproducibility
`22`, irregular density `9`, and non-CP-SAT M336 baseline `101`. Five optional
OR-Tools tests were explicitly excluded. Source/install hashes match for both
changed production modules. No M336 placement, optimizer, score, repair,
fallback, CP-SAT solve, parameter change, or M336-141 work was run.
