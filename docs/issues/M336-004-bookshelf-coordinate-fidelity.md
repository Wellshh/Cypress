# M336-004: Bookshelf Coordinate Paths Changed the Scored Problem

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `d9e7674`

## Problem

Bookshelf pin offsets are expressed in the unmirrored `N` orientation. PlaceIO
mirrors the x offset for `FN` BOTTOM nodes, but the M336 generator previously
wrote the already mirrored board-space offset. BOTTOM pins were therefore
mirrored twice. Separately, `evaluate_pl=1` reads node positions through a C++
integer path, changing a floating-point manual placement before scoring.

## Evidence

- The source has 378 connected symbol pins. PlaceIO retains 308 internal pins
  after removing 70 same-node/same-net duplicates.
- Pre-flipping BOTTOM x offsets before writing `.nets` reconstructs all source
  pins with maximum pre-quantization residual below `1.5e-14 mm`.
- PlaceIO quantizes offsets to integer sites, so a `0.05 mm` site can still
  introduce up to roughly `0.0354 mm` two-axis pin error.
- The floating placement path scores the manual board at HPWL `14627.84765625`
  and RSMT `15950.0654296875`; `evaluate_pl=1` instead produced `14642/15967`.

## Impact

The original matrix optimized a different net geometry and cannot support a
quality conclusion. Integer placement loading also makes scores depend on the
evaluation mode rather than only on the supplied placement.

## Remediation

The generator now writes N-orientation offsets, baseline preparation validates
round-trip pin coordinates, and scoring uses `global_place_flag=0` with
`evaluate_pl=0`. A strict float-preserving initial-placement loader is covered
by regression tests. The runner regenerates Bookshelf assets before each matrix.

## Acceptance Criteria

- TOP and BOTTOM pin round-trip tests pass and reject the old sign convention.
- Baseline and candidates use one hashed `.nodes/.nets/.scl` database.
- Float placement coordinates are preserved without hidden integer conversion.
- Native pin deduplication and site quantization remain explicit in reports.
