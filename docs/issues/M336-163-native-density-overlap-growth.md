# M336-163: Native Density Allows Global Overlap Growth

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `cc05a44`

## Problem

The irregular TOP/BOTTOM density model keeps constrained footprints inside the
usable keep-in capacity, but it does not prevent a legal warm start from
developing widespread same-side overlaps. Hard keep-in projection therefore
reports no pressure while the exact collision graph grows throughout native
optimization.

## Evidence

The seed-1000, 50-step checkpoint-warm diagnostic starts from the exact-legal
M336-118 placement. E2 ends with 100/100 containment and zero projection events,
but has 66 overlap pairs. E3 adds anchor loss and ends with 71 overlap pairs.
Their BOTTOM normalized overflows are `1.534427` and `1.535063`, with maximum
densities above `3.51`.

At the current `64 x 32` grid, every keep-in bin carrying capacity is partial:
TOP has 53 partial and zero fully usable bins; BOTTOM has 105 partial and zero
fully usable bins. This representation supplies a region-scale field but is too
coarse to demonstrate footprint-scale separation. E0 independently ends with
65 overlaps and 41 keep-in violations.

## Impact

- Native placement is not exact legal before E4 repair.
- The conflict closure grows from zero to most constrained components.
- Repair cost and quality loss hide the behavior of the differentiable path.
- Zero keep-in projection events cannot be interpreted as complete constraint
  success.

## Remediation

Instrument exact overlap count/area at controlled iteration checkpoints. Audit
the usable-capacity force at finer, footprint-relevant bin resolutions and its
normalization against usable area. If density alone cannot separate footprints,
add a feature-gated differentiable same-side overlap signal using the existing
Cypress objective lifecycle. Do not replace native optimization with an exact
checkpoint fallback or unbounded discrete legalization.

## Acceptance Criteria

- A legal warm start does not grow a board-wide collision closure at 50 steps.
- E2/E3 report iteration-level overlap pressure alongside density overflow.
- E4 repair remains local and bounded because the native state is near legal.
- Feature-off Cypress behavior remains byte-identical to `f0e4cb9`.
- The selected density/overlap change has focused CPU and GPU gradient tests.
