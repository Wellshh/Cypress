# M336-187: Exact Audit Repeats Scalar Shapely Operations

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `346e5fa`

## Finding

M336-186 removes per-coordinate CUDA synchronization and safely reuses fixed
geometry, but the global exact audit still executes the constrained-geometry
path one object at a time. Every call performs 100 scalar
`affinity.translate()` operations, 100 scalar keep-in differences, one fixed
STRtree query per constrained component, and one constrained STRtree query per
component.

This work is inside `exact_contact_projection_seconds` and therefore inside the
fixed M336-185 GPU timing domain. It is not the excluded accepted-step guard
work addressed by M336-184.

## Fixed-Placement Benchmark

The benchmark reparsed the preserved M336-183 serialized E2 placement on
physical GPU 2 and called only `exact_overlap_report()`. It constructed no
`NonLinearPlace`, objective, backward pass, optimizer, repair, or scorer. The
fixture contains the real 100 constrained and 40 obstacle components and is
exact legal.

Across 101 calls, all four modes returned identical reports:

| Mode | Median per audit |
| --- | ---: |
| Scalar coordinates, fixed geometry rebuilt | `11.153275 ms` |
| Batched coordinates, fixed geometry rebuilt | `6.794363 ms` |
| Scalar coordinates, fixed geometry cached | `10.263590 ms` |
| M336-186 batched coordinates and fixed cache | `5.925002 ms` |

M336-186 therefore saves `5.228274 ms` per audit (`1.88x`), or an optimistic
`0.141163 s` across the 27 M336-183 global validator calls. This is material
but still leaves approximately `0.043641 s` of the fixed E2 GPU gap before
accounting for run-to-run effects.

Profiling 201 current audits identifies the remaining scalar work:

| Scalar Shapely path | Profiled cumulative time |
| --- | ---: |
| Constrained footprint translation | `0.653 s` |
| Keep-in difference | `0.442 s` |
| STRtree query wrappers | `0.308 s` |
| Candidate intersection | `0.173 s` |

Profile instrumentation inflates absolute time; these values identify call
structure and must not be substituted for the fixed runtime gate.

## Vectorized Prototype

A read-only Shapely 2.1.2 prototype retained the same local footprints, GEOS
difference/intersection operations, area epsilon, side split, fixed trees, and
pair ordering. It changed only Python call granularity:

1. translate all local footprints with one fresh `set_coordinates()` batch;
2. evaluate all footprint/region differences as one vector operation;
3. query each side-local STRtree with a geometry array;
4. evaluate candidate intersections and areas as arrays.

On 201 unprofiled calls, current M336-186 measured `6.053330 ms` median and the
prototype measured `2.209201 ms`, a `2.74x` speedup and `3.844129 ms` additional
saving per audit. The 27-call projection is `0.103791 s`, larger than the
remaining offline gap, but it is not proof that a native D1 passes.

Sorted report JSON was byte-identical for the preserved legal placement, one
keep-in violation, one constrained-constrained overlap, and one
constrained-fixed overlap. Areas, pair order, closure, and counts matched
exactly.

## Required Mechanism

1. Precompute only immutable constrained templates: local geometry array,
   flattened local coordinates and geometry indices, region array, node IDs,
   dimensions, side indices, and report names.
2. Build a fresh translated constrained geometry array from every audit's host
   snapshot. Never cache translated constrained footprints or their STRtrees.
3. Use vectorized Shapely difference, area, STRtree query, intersection, and
   area operations without changing GEOS precision, predicates, epsilon, or
   positive-area semantics.
4. Preserve historical report ordering. Bulk query pairs must be consumed in
   the same side, constrained-node, and tree-result order as scalar queries.
5. Keep M336-186's exact fixed-cache key and invalidation behavior. Fixed shape
   arrays may be stored only inside that already identity- and byte-keyed cache.
6. Prove `set_coordinates()` never mutates the immutable local templates.
7. Add per-phase batch translation, keep-in, fixed-query, constrained-query,
   and total audit diagnostics. Do not move any timing boundary.
8. Keep the optimization internal and unconditional-equivalent; add no M336
   parameter, fallback, approximate broadphase, or feature-dependent legality.

## Required Tests

- Differential scalar/vector reports for legal, keep-in-invalid,
  constrained-constrained, and constrained-fixed placements.
- Concave, unequal, multi-contact, TOP/BOTTOM, touching-only, and
  epsilon-boundary geometry cases with identical list ordering and areas.
- Seeded randomized differential cases on CPU/GPU float32/float64.
- Repeated calls prove immutable local templates and fresh constrained
  footprints; moving any fixed coordinate still invalidates the fixed cache.
- Bulk STRtree pair order is explicitly compared with the scalar loop order.
- Source/install hashes match and anchor, contact, guard, reproducibility,
  density, and non-CP-SAT M336 suites remain green.

## Experiment Boundary

All evidence is fixed-placement validation and an in-process prototype. No M336
placement, objective, backward pass, optimizer step, score, repair, fallback,
CP-SAT solve, parameter change, or M336-141 work was run. Commit, push, pull,
implement, and parity-test this issue before requesting an effect run. D2, D3,
E4, seed ladders, and a resumed M336-183 output remain prohibited.

## Acceptance Criteria

- The vectorized path returns byte-identical exact reports to the scalar
  reference over the required deterministic corpus.
- No translated constrained geometry survives an audit call.
- The fixed validator-only fixture materially reduces median audit time.
- A later explicitly authorized combined scale-1 D1 passes unchanged legality,
  quality, determinism, GPU runtime, and end-to-end gates.
