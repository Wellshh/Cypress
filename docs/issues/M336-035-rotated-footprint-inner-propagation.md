# M336-035: Inner Rectangles Do Not Close Rotated-Footprint Packing

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `d8355ab`

## Problem

The final restored-Q601 TOP model contains 26 axis-aligned rectangles and four
convex rotated rectangles: `C8653`, `L8607`, `L8626`, and `L8630`. Exact
separating-axis constraints model the rotated pairs, but those four components
were absent from the global `NoOverlap2D` propagator. The 100-cut model remained
`UNKNOWN` with 26,590 local candidates.

## Diagnostic Correction

`--nonrectangle-inner-slices N` now partitions each convex nonrectangle into
horizontal bands. Each band uses the narrowest polygon cross-section at its
ends and every intervening vertex. Continuous rectangles are inset, converted
to integer units with inward `ceil`/`floor`, then checked again with exact
polygon `covers` before being added to `NoOverlap2D`.

These rectangles are strict subsets of the original footprint, so their
non-overlap is a necessary constraint and cannot remove an exactly legal
placement. Existing separating-axis constraints and final exact validation
remain active. The feature defaults to zero and is reported per refdes.

An initial implementation sliced every convex part of a concave footprint. It
created 634 intervals for `MHC8601` and `MHC8602`, which was safe but defeated
the intended model reduction. Concave footprints are now explicitly skipped
with `skip_reason=nonconvex`; no convex-hull substitution is allowed.

## Safety Evidence

A 16-slice, single-worker fixed replay of the known legal runtime-anchor result
was `OPTIMAL` in `0.106780 s`, with zero branches, 100/100 exact containment,
and zero overlaps. It reproduced PL SHA-256
`fbbbf6b3e3f81e84e578d16b3e01ba78f28ed67ae241065ac44146e20ba50cfe`.
Four rotated footprints generated 56 integer rectangles; each retained about
86.8%-87.4% of its source area. The result SHA-256 is
`d11936790580a0bb15e8d67f017f865b881b5644ab5341edb015b63a93aabc8a`.

Unit tests verify continuous and integer containment, positive-area
disjointness, inward loss of sub-DBU tip slices, and rejection of concave input.

## Search A/B

All 100-cut runs used the round-13 hint, 1,024 nearest sites per
component-region, 26,590 candidates, seed 1000, eight workers, and 120 seconds.

| Slices | Inner intervals | Area coverage | Status | Time (s) | Branches | Conflicts |
| ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 0 | 0 | 0% | UNKNOWN | 120.075 | 1,407,803 | 19,962 |
| 16 | 56 | 86.8%-87.4% | UNKNOWN | 120.142 | 1,117,098 | 16,743 |
| 32 | 120 | 93.38%-93.60% | UNKNOWN | 120.798 | 1,082,725 | 13,014 |

The 16- and 32-slice result hashes are
`fbec1afb4ee41bb996ca323346a054532ff8f33491f5ee336bbdf2be22c9511f`
and `52fe2c06c37e3ed1a0ee1330ee06d9dcd1d7dea552f60b0318dcc83a76ca4bf2`.
Fewer conflicts indicate stronger propagation, but neither run found an
incumbent.

A final strict model restored all 110 controlled pairs while retaining 32
slices. It also remained `UNKNOWN` after `120.426361 s`, with 1,340,388 branches
and 316,692 conflicts. Its result SHA-256 is
`eef73d2de7247e6018b9f5284dd150b22348b767dacb34ccaa97a34a2ce3ac5f`.

## Acceptance Impact

No new placement was produced, so this change does not improve HPWL, RSMT, or
the normalized score. It is retained only as an exact-safe, default-off
propagation option. M336-034 remains open, and no slice count may be described
as solving the final endpoint.

## Required Improvement

- Replace repeated long pair arguments with a versioned cut-manifest input.
- Test a search decomposition that branches on the four rotated components
  before solving the axis-aligned rectangle packing.
- Require zero-overlap exact validation and one-worker strict replay before any
  result proceeds to native baseline scoring.
