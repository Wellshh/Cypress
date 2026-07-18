# M336-032: Fixed Obstacle Collisions Remained Search Decisions

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `dbb901d`

## Problem

The exact discrete model retained every keep-in-valid site even when a
controlled footprint necessarily overlapped a fixed same-side component at
that site. CP-SAT then received separating-axis Boolean disjunctions for these
static collisions. This enlarged both candidate tables and the search graph
despite the obstacle coordinates never changing.

## Correction

`--prune-fixed-obstacle-sites` performs exact positive-area intersection tests
before candidate limiting in `decomposed` collision mode. It preserves original
region-local site indices, keeps boundary-touching sites, and evaluates concave
footprints rather than their bounding boxes. Fixed hints must survive pruning;
an infeasible non-fixed hint is remapped to the nearest retained site in the
same region and the remap is reported.

Because every retained site is already clear of every fixed obstacle, the
corresponding controlled/fixed separating-axis constraints are omitted. The
option is explicit and default-off while endpoint evidence is gathered.

## Evidence

The known legal `0.1 mm` runtime-anchor placement retained 157,014 of 215,749
sites, removing 58,735 static-collision candidates. It eliminated 180 modeled
component pairs and reduced convex-part collision constraints from 3,383 to
2,548. Single-worker fixed replay remained `OPTIMAL` with zero branches,
100/100 containment, zero overlaps, and unchanged placement SHA-256
`fbbbf6b3e3f81e84e578d16b3e01ba78f28ed67ae241065ac44146e20ba50cfe`.
Solver time decreased from `0.267033 s` to `0.104806 s`; the new run used
599,716 KiB peak RSS and 13.98 seconds end to end including geometry loading
and site filtering.

Unit tests cover deterministic limiting over filtered original indices,
concave-obstacle voids, positive-area overlap removal, and legal boundary
contact. The M336, anchor/keep-in, and reproducibility suites pass 30/30,
15/15, and 8/8 tests.

At the exact restored `Q601` endpoint, preprocessing removed 17,210 of 50,425
full-domain TOP sites and retained 33,215 candidates. It eliminated 84 static
component pairs and reduced convex-part collision constraints from 620 to 110.
Six sites from the 93.75% continuation hint were no longer legal against fixed
obstacles; their nearest same-region remaps moved as far as `23.406886 mm`.

Despite the smaller model, the eight-worker search remained `UNKNOWN` after
`300.176078 s`, 5,197,905 branches, and 1,677,948 conflicts, with 1,044,364 KiB
peak RSS. The unpruned comparison had 49,682 retained candidates, 620 part
constraints, and also timed out. Static pruning is therefore validated, but
independently remapping invalid hint sites does not recover a coherent packing.
Neither timeout is evidence of endpoint infeasibility.

## Remaining Work

- Build a coherent intermediate packing instead of remapping each invalid hint
  independently.
- Require exact validation and deterministic fixed replay for any candidate.
- Do not interpret a timed-out pruned model as endpoint infeasibility.
