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

## Implementation Evidence

The strict-equivalent implementation is complete; the issue remains open until
an explicitly authorized combined D1 measures the fixed gate.

- A lazy read-only template stores only local footprints, flattened local
  coordinates and geometry indices, assigned regions, node IDs, dimensions,
  side indices, and names. Every NumPy array is marked non-writeable.
- Each audit computes fresh centers from the current host snapshot, copies the
  local geometry array, and uses one `set_coordinates()` batch. No translated
  footprint or constrained STRtree is retained after the call.
- Keep-in differences, fixed-tree queries, constrained-tree queries,
  intersections, and areas use Shapely array operations. The historical side,
  input-node, tree-result, positive-area, epsilon, and report order are
  unchanged.
- Fixed shape arrays live only inside M336-186's PlaceDB-identity and exact-byte
  cache. A fixed-coordinate or PlaceDB change still rebuilds rows, shapes, and
  side trees.
- Native diagnostics now separate coordinate snapshot, footprint translation,
  keep-in, fixed overlap, constrained overlap, and total audit time without
  changing the M336-185 accounting boundary.

The committed synthetic differential corpus contains concave and unequal
footprints, both sides, legal, touching-only, epsilon-boundary, keep-in,
fixed-overlap, constrained-overlap, multi-contact, and 20 seeded randomized
positions. Its complete reports and repair-ID sets match the scalar oracle on
CPU/H100 float32/float64. It also proves local WKB and coordinate templates are
unchanged and covers zero constrained components.

An additional real M336 corpus compares 51 positions on both devices and both
dtypes, for `204/204` exact matches. It includes 188 cases with keep-in
violations, 192 with fixed overlaps, and 200 with constrained overlaps; counts,
areas, list order, closure, and repair IDs all match.

The final production fixture measures:

| Path | Median per audit |
| --- | ---: |
| M336-186 scalar Shapely oracle | `6.095795 ms` |
| M336-187 vectorized production | `2.156656 ms` |

This is a `2.83x` speedup and `3.939139 ms` saving per audit. Projected across
the preserved 27 calls, the additional opportunity is `0.106357 s`. This
validator-only projection is not a native runtime claim.

After `cmake --install build`, all `263/263` applicable tests pass: anchor and
keep-in `59`, exact guard `11`, exact contact projection `61`, reproducibility
`22`, irregular density `9`, and non-CP-SAT M336 baseline `101`. Five optional
OR-Tools tests were explicitly excluded. Source/install hashes match. No M336
placement, objective, backward pass, optimizer, score, repair, fallback,
CP-SAT solve, parameter change, or M336-141 work was run.

## Authorized Effect Evidence

M336-188 runs the one explicitly authorized combined scale-1 D1. E2 remains
byte-identical to M336-183 while GPU optimization falls from `2.346527902 s`
to `2.245768752 s` and contact projection falls from `0.943923393 s` to
`0.774890117 s`. Both E2/E3 remain exact legal and satisfy the declared quality
direction. The strict-equivalent vectorization is therefore effective, but E2
still misses its unchanged `2.161724 s` gate by `0.084044752 s`. This issue
remains open; M336-188 owns the residual keep-in-audit profile and stop
condition.
