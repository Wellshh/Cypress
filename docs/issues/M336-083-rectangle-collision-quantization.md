# M336-083: Rectangle Quantization Rejected an Accepted Placement

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `404ff71`

## Problem

The current exact-site placement passed full Shapely validation, but fixing the
same 100 sites in `solve_discrete_placement.py --collision-mode decomposed`
returned `INFEASIBLE`. Disabling collisions returned `OPTIMAL`, proving the
failure was in collision encoding rather than assignment, capacity, or site
mapping.

An independent pair audit found no acceptance-level overlap and one integer
false positive: BOTTOM rectangles `C302/R606` intersect by only
`7.616200096377985e-13`, below the acceptance epsilon
`0.0039991408847609294` in Cypress coordinate units. The old composed
quantization ended `C302` at integer x `629432395` but started `R606` at
`629432394`; direct quantization of the exact `R606` footprint edge gives
`629432395`, which is boundary contact. Audit SHA-256 is
`a858caa211d6efecbbbcb7be1eab16a53688b42ecd90855e41ddc52d6484de4c`.

## Resolution

Rectangle starts now quantize `center + footprint_local.min` once instead of
adding two independently rounded values. Collision intervals contract inward
by one integer unit. Swept-domain pruning uses separate outward
`floor(min)/ceil(max)` bounds, so the contraction cannot suppress a candidate
pair. The model computes a conservative maximum missed-overlap area and fails
before solving if it exceeds the validator threshold.

For this model the bound is `0.0012806224525598355`, below the acceptance
epsilon. Both element and coordinate-table fixed-site replays are `OPTIMAL`
with zero branches, zero site remaps, 100/100 containment, and zero overlaps.
Their result SHA-256 values are
`4bba39d88c19041fd8aa3e85e545f742def610a2195a7feec21bdc0eb4e4067f`
and `ea8ca067b95b9b434e7aaae85d5bc8c5466ce8b7fefcfd527e34a520f257bbd8`.

## Residual Risk

This closes rectangle double-rounding. M336-039 remains open for general
integer convex decomposition equivalence involving nonrectangular footprints;
all promoted placements still require exact final validation.
