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

Accepted-step exact diagnostics now localize the failure. The unchanged
checkpoint-warm E3 10-step control starts with zero overlaps, then reports pair
counts `11, 14, 16, 17, 18, 20, 23, 24, 28, 28`. Exact overlap area grows every
step from `0.009920` to `0.108631 mm2`, while the conflict closure grows from 19
to 45 constrained components. Constrained-to-frozen-obstacle collisions first
appear at step 4 and reach two pairs. All checkpoints retain zero keep-in
violations.

The diagnostics are read-only: the final placement SHA remains
`a6445d6a9818...`, identical to the committed scale-1 control, and the final
checkpoint exactly matches the independent validator's 28 pairs and
`0.1086312142 mm2`. Eleven checkpoints cost `0.134818 s` total and are reported
separately from GPU optimization. The first post-serialization replay exposed a
diagnostic-flag leak into the context-free scorer; the scorer now explicitly
sets the interval to zero and the complete workflow succeeds.

## Impact

- Native placement is not exact legal before E4 repair.
- The conflict closure grows from zero to most constrained components.
- Repair cost and quality loss hide the behavior of the differentiable path.
- Zero keep-in projection events cannot be interpreted as complete constraint
  success.

## Remediation

Exact overlap count/area instrumentation is complete. Audit the usable-capacity
force at finer, footprint-relevant bin resolutions and its normalization against
usable area. If density alone cannot separate footprints, add a feature-gated
differentiable same-side overlap signal using the existing Cypress objective
lifecycle. Do not replace native optimization with an exact checkpoint fallback
or unbounded discrete legalization.

The M336-169 audit rejects enabling the legacy `MacroOverlap` objective as that
signal: although it covers all 140 M336 physical nodes and separates sides, its
gradient is zero at contact, cubic in shallow penetration after the aggregate
square, negligible at the default weight, and zero again for coincident centers.
A replacement must use the native objective lifecycle but not inherit that
zero-contact kernel.

## Acceptance Criteria

- A legal warm start does not grow a board-wide collision closure at 50 steps.
- E2/E3 report iteration-level overlap pressure alongside density overflow.
- E4 repair remains local and bounded because the native state is near legal.
- Feature-off Cypress behavior remains byte-identical to `f0e4cb9`.
- The selected density/overlap change has focused CPU and GPU gradient tests.
