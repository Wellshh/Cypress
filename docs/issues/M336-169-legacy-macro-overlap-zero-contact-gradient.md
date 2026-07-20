# M336-169: Legacy Macro Overlap Has Zero Contact Gradient

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `239b668`

## Problem

The existing `MacroOverlap` objective cannot prevent an exact-legal M336 warm
start from crossing into overlap. Its bell kernel and outer square both have
zero slope at first contact. The default weight then makes shallow-overlap
gradients negligible, while a fully coincident pair also has zero positional
gradient.

This is not an M336 node-coverage defect. The current database marks all 140
physical nodes as movable macros, the wrapper evaluates TOP and BOTTOM
separately, and the anchor/keep-in preconditioner freezes the 40 anchor/obstacle
coordinates. The failure is the objective's local geometry and scale.

## Evidence

For one axis, the overlap kernel near contact is proportional to squared
penetration. The operator then squares the sum over pairs, so an isolated
shallow collision has loss `O(penetration^4)` and gradient
`O(penetration^3)`. It therefore supplies no pre-contact barrier.

A float64 CPU probe with two 10 by 10 nodes produced:

| Penetration | Loss | Raw max gradient | Gradient at weight `8e-6` |
| ---: | ---: | ---: | ---: |
| `0.01` | `4e-12` | `1.6e-9` | `1.28e-14` |
| `0.10` | `4e-8` | `1.6e-6` | `1.28e-11` |
| `1.00` | `4e-4` | `1.6e-3` | `1.28e-8` |
| `5.00` | `0.25` | `0.2` | `1.6e-6` |
| `10.00` (coincident) | `1.0` | `0.0` | `0.0` |

The M336 native log reports wirelength gradient L1 norms of about `5.83` and
`0.38`, so the default collision contribution is not competitive. The weight
starts at `8e-6`, its multiplier defaults to `1`, and a legal initial placement
has zero overlap gradient, precluding ordinary initial gradient matching.

## Impact

- Enabling `macro_overlap_flag` at its legacy defaults cannot satisfy M336-163.
- Exact overlap can grow before the objective produces a useful response.
- Larger native steps amplify collision closure rather than anchor progress.
- A successful E4 repair would conceal, not fix, the native optimizer defect.

## Remediation

Do not enable the legacy objective blindly. First add controlled iteration-level
exact overlap diagnostics. Then implement a separate feature-gated, side-local
clearance/overlap signal with nonzero inward gradient at contact, per-pair
normalization, all constrained-to-constrained and constrained-to-frozen obstacle
pairs, bounded dynamic weighting, and no Shapely or CPU transfer in `forward()`.
Keep exact Shapely geometry outside autograd for diagnostics and final gates.

## Acceptance Criteria

- A focused test proves finite nonzero separating gradients at first contact and
  shallow penetration.
- TOP/BOTTOM cross-side pairs contribute exactly zero.
- Frozen obstacles receive no accepted optimizer motion but repel active nodes.
- Feature-off behavior remains unchanged.
- A 10-step and 50-step checkpoint-warm contrast reduces exact overlap count and
  area without increasing keep-in violations or concealing collisions with E4.
