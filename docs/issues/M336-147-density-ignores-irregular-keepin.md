# M336-147: Native Density Ignores Irregular Keep-in Capacity

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `91fb33c`

## Problem

M336 uses separate TOP/BOTTOM electric-density operators, but each operator
treats the complete rectangular board bounding box as usable capacity. Irregular
keep-in geometry is visible only to losses and hard projection. Density can
therefore push components into unavailable space and leave the projector to
undo the proposal.

## Remediation

Rasterize a conservative per-side usable-area map from the transformed keep-in
polygons. Convert each bin's unavailable area into static density occupancy and
merge it with the corresponding TOP/BOTTOM initial fixed-density map. Reuse the
same map in electric potential and overflow so capacity outside keep-in is zero
without changing CUDA kernels or merging side-specific fields.

## Acceptance Criteria

- The feature is default-off outside the M336 experiment contract.
- TOP and BOTTOM maps use only regions from their own side.
- Rasterized usable area never exceeds exact clipped polygon area.
- Fully outside bins have zero usable capacity and partial bins use their
  conservative polygon intersection.
- Potential and overflow consume the same static occupancy map.
- A focused field test shows an inward finite gradient near unavailable space.
- Native off/on runs report per-side usable area, overflow, projection pressure,
  exact legality, HPWL, and RSMT.
- No `virtual_macro.clamp(min=30)` behavior is introduced.

## Failed First Integration

The first seed-1000, 10-step E2 off/on comparison is retained under
`results/m336/native-cypress/n3-density-{off,on}-smoke-10/`. Both runs executed
13 backward calls and 10 coordinate-changing Adam steps. Enabling the initial
map left projection events unchanged at 4, increased maximum projection from
`0.143045` to `0.143396 mm`, increased overlaps from 22 to 27, and regressed
HPWL/RSMT from `24269.6035/25890.9492` to `24270.5840/25892.1133`.

This was an invalid capacity contract, not a successful ablation. The side
operators classified all 140 nodes as movable while irregular Keep-in applies
only to 100 constrained nodes. The other 40 frozen anchors/obstacles account
for `301247` square placement units. Treating their full area as movable inside
Keep-in made the field grossly infeasible. The corrected contract must use only
constrained nodes as irregular-density movables and subtract frozen footprints
from usable capacity as static obstacles. The failed result must not be cited
as Cypress improvement evidence.

## Corrected Integration

The corrected field contains only the 100 constrained components. The other
40 frozen anchors/obstacles are removed from side-specific usable geometry and
are not passed to the movable density operator. Potential and overflow consume
the same conservative static map. The legacy feature-off path retains its
original node ordering and is byte-identical across the refactor.

The seed-1000 10-step corrected comparison reduced projection events from `4`
to `0`, maximum projection distance from `0.143045` to `0 mm`, overlap pairs
from `22` to `17`, and overlap area from `0.059087` to `0.046361 mm2`. It
slightly regressed HPWL while improving RSMT, so it was treated only as an
engineering smoke signal.

## 50-step Diagnostic

Both E2 runs executed 53 backward calls and 50 coordinate-changing Adam steps
on the same H100 and seed:

| Metric | Feature off | Feature on |
| --- | ---: | ---: |
| Projection node events | 34 | 0 |
| Maximum projection distance (mm) | 0.698683 | 0 |
| Fully contained / keep-in violations | 100 / 0 | 100 / 0 |
| Overlap pairs | 65 | 66 |
| Overlap area (mm2) | 1.086227 | 0.612607 |
| Native HPWL | 24188.1875 | 24255.8145 |
| Native FLUTE RSMT | 25815.5762 | 25853.2383 |
| Normalized native score | 0.6112290 | 0.6099271 |
| Runtime (s) | 60.0967 | 59.7204 |

Placement SHA-256 changed from
`628e5d4dbf042e272643bd31cd6113cb81a4d37c49cc3bf6af6afe8ba1f247a2`
to `8eb1ea59171bba6f0458b8d505f2ab9d65dd74fbb234b8ce4fc34271877b2c54`.

This satisfies the N3 native-signal gate because projection pressure is
measurably eliminated and overlap area falls by about 44%. It does not satisfy
a placement-quality gate: overlap count increases by one and HPWL/RSMT both
regress. M336-149 separately records that the configured `0.7` target density
is below measured side utilization, so the high normalized overflow cannot be
treated as a convergence verdict.
