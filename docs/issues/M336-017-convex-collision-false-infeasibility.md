# M336-017: Convex Collision Model Rejects Legal Concave Footprints

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-18
**Affected commits:** Through `a1686ff`

## Problem

The discrete CP-SAT solver used each nonrectangular footprint's convex hull and
used PlaceDB rectangles for fixed obstacles. The exact validator instead uses
the original polygons from `pcb_geometry.json`. Consequently, a legal
placement could be declared infeasible before search.

Fixing all 100 sites from the known legal E4 `0.1 mm` placement isolated the
contradiction. With collisions disabled, CP-SAT returned `OPTIMAL`; the legacy
`convex` mode returned `INFEASIBLE` in presolve with zero branches, although
exact validation reported `100/100` containment and zero overlaps.

| Mode | Status | Wall time | Branches |
| --- | --- | ---: | ---: |
| `none` | `OPTIMAL` | `0.070122771 s` | 0 |
| legacy `convex` | `INFEASIBLE` | `0.098377033 s` | 0 |

## Root Cause

All four false conflicts are on `BOTTOM` and involve a concave mounting-hole
component. Exact intersection area is zero; convex-hull intersection is
positive in Cypress coordinate units squared.

| First | Second | Exact area | Hull area |
| --- | --- | ---: | ---: |
| `C8606` | `MHC8602` | 0 | 3.835861631 |
| `C8613` | `MHC8602` | 0 | 0.048071688 |
| `FV705` | `MHC8601` | 0 | 0.767222142 |
| `MHC8602` | `R8603` | 0 | 8.729063801 |

Therefore, every earlier `convex` `UNKNOWN` or `INFEASIBLE` result is invalid
as evidence about physical packing feasibility.

## Correction

`decomposed` is now the default collision mode. It deterministically ear-clips
concave polygons into nonoverlapping convex parts, verifies that their union
equals the source footprint, and applies separating-axis constraints to every
relevant part pair. Fixed obstacles now use the same transformed manual
footprints as the exact validator. The legacy model remains available only as
explicit `--collision-mode convex` audit behavior.

The corrected known-legal replay used 172 controlled and 751 fixed convex
parts with 62,080 part-pair constraints. It returned `OPTIMAL` in `2.941956 s`,
zero branches, and zero conflicts. Its placement hash is
`1551a2dacf7ebd4f935dc72c194f24a37c5140d875bc93c7fe4a41fc3c835103`,
identical to the collision-disabled replay. Conversely, fixing a candidate
with 362 exact overlaps returned `INFEASIBLE` in `1.100035 s`.

## Evidence Artifacts

Generated results remain gitignored, but their paths and hashes preserve the
local audit trail:

| Result | SHA-256 |
| --- | --- |
| `result-grid01-known-legal-fixed-hint-no-collision.json` | `38be7f96f0e45a9c012c9a205535a086ee09e62a9ba715c4d9bdf8a80e172a14` |
| `result-grid01-known-legal-fixed-hint.json` | `28ff48734feedc8cdfa9650eb0480ee3cc5914a5e5f65b51c43fa8d4d14ba4a9` |
| `result-grid01-known-legal-fixed-hint-decomposed.json` | `cc10277aa9f02523f0376b8e4bbecda49e15e0d2afefd78c99b0ad56d266085a` |
| `result-grid01-known-illegal-fixed-hint-decomposed.json` | `0a9fe029131ef25514f8424bf282d4b33aabf46864b9637bcfb9bb67c5bd64ca` |

All are under `results/m336/discrete_collision_audit/`. The legal hint input
hash is `f82862807149d01ed4b01bcd82dc8f0286262ddc3e8b5830e58c3d2e709df65b`.

## Residual Risk

CP-SAT geometry is integerized at `1e6` units. Every promoted result must still
pass the Shapely exact validator; this fix does not establish a score-1 legal
placement or provide native RSMT evidence.

## Acceptance Criteria

- A legal concave-footprint hint is accepted and remains exact-validator legal.
- A fixed overlapping hint is rejected.
- Convex decomposition is deterministic, area preserving, and unit tested.
- Historical collision conclusions are explicitly withdrawn.
