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

Iteration-level exact evidence confirms that a preventive signal is required:
the scale-1 control crosses from zero to 11 overlap pairs on its first accepted
Adam step, then reaches 28 pairs and `0.108631 mm2` by step 10. The overlap area
increases at every observed step; waiting for a late, shallow legacy penalty is
not compatible with preserving the legal warm start.

## Impact

- Enabling `macro_overlap_flag` at its legacy defaults cannot satisfy M336-163.
- Exact overlap can grow before the objective produces a useful response.
- Larger native steps amplify collision closure rather than anchor progress.
- A successful E4 repair would conceal, not fix, the native optimizer defect.

## Remediation

Do not enable the legacy objective blindly. Controlled iteration-level exact
overlap diagnostics are now available. Implement a separate feature-gated,
side-local clearance/overlap signal with nonzero inward gradient at contact,
per-pair normalization, all constrained-to-constrained and
constrained-to-frozen obstacle pairs, bounded dynamic weighting, and no Shapely
or CPU transfer in `forward()`. Keep exact Shapely geometry outside autograd for
diagnostics and final gates.

## Acceptance Criteria

- A focused test proves finite nonzero separating gradients at first contact and
  shallow penetration.
- TOP/BOTTOM cross-side pairs contribute exactly zero.
- Frozen obstacles receive no accepted optimizer motion but repel active nodes.
- Feature-off behavior remains unchanged.
- A 10-step and 50-step checkpoint-warm contrast reduces exact overlap count and
  area without increasing keep-in violations or concealing collisions with E4.

## Mitigation Prototype

A default-off native barrier now builds conservative configuration-space signed
distance fields from the exact local footprints. Geometry normalization reduces
M336 to 48 footprint types and 487 same-side field types. One packed atlas then
covers all 4,930 pairs that contain at least one of the 100 active constrained
components, including active-to-frozen obstacle pairs. `forward()` performs only
GPU tensor indexing and bilinear interpolation; Shapely and SciPy are confined
to preprocessing. Frozen-coordinate gradients are still removed by the existing
post-backward mask.

The raster model uses the frozen `0.05 mm` grid and a conservative half-cell
footprint guard (`0.025 mm`). This is a preventive optimization signal, not the
exact legality predicate. Exact Shapely validation remains authoritative. The
atlas is 33,832,960 bytes and took `0.749687 s` to construct in the first M336
smoke run. Its runtime is reported separately as collision preprocessing.

Collision pressure uses the same bounded EMA controller structure as anchor
pressure, but starts on iteration zero to protect a legal warm start. The first
run used target gradient ratio `0.1`, margin `0 mm`, tau `0.025 mm`, and produced
raw/effective weight `0.0893451` from wirelength and collision gradient L1 norms
`5.83125` and `6.52667`. The weight was finite, matched the requested ratio, and
did not approach the `5000` ceiling.

## One-Step Smoke Evidence

The GPU 2 checkpoint-warm E3 smoke executed one Adam optimizer step through the
native objective and independent post-serialization scorer. Against the
instrumented feature-off step-1 control:

| Metric | Control | Barrier ratio `0.1` |
| --- | ---: | ---: |
| Exact overlap pairs | `11` | `10` |
| Exact overlap area (`mm2`) | `0.00991998` | `0.00803191` |
| Keep-in violations | `0` | `0` |

The area reduction is `19.03%`, but the output remains illegal and therefore is
not accepted as a Cypress quality improvement. Native serialized metrics were
HPWL `15633.896880` and RSMT `17331.998`; 10-step and 50-step controlled
contrasts remain required. Focused CPU/GPU tests cover contact and shallow
penetration gradients, cross-side exclusion, nonrectangular footprint voids,
CPU/GPU consistency, runner identity, and scorer isolation.

## Feature-Off Replay

A fresh GPU 2 E3 checkpoint-warm run with the collision feature explicitly
disabled reproduced the instrumented 10-step control exactly. It produced the
same placement SHA-256 (`a6445d6a98180ff4449afdffe37ad313f5215cd336153030c5637aaa10b94c5c`),
HPWL (`15632.686697721481`), RSMT (`17325.676`), anchor statistics, final exact
legality (`28` overlap pairs, `0.10863121417815015 mm2`, zero keep-in
violations), and every per-step overlap metric apart from elapsed time. The
native execution record also contains no collision weight updates. This proves
the new path is default-off and does not perturb the prior optimizer trajectory
when disabled; it does not resolve the open legality defect.
