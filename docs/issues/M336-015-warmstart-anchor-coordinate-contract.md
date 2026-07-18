# M336-015: Runtime Freeze Overwrites Materially Moved Baseline Anchors

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `4c44b40`

## Problem

`BasicPlace` constructs `AnchorKeepInContext` before loading the manual
`initial_placement_file`. The context derives physical anchor positions from
the source geometry. After the manual warm start is loaded,
`initialize_positions` freezes anchors back at those source-aligned positions.
This is consistent with the original M336 specification but conflicts with the
new requirement to match the score of the manually placed board.

Most source and manual anchor positions agree within alignment residual. Two
do not: runtime freezing moves `EMI601` by `19.6285 mm` and `Q601` by
`16.3164 mm`. All other frozen components move by at most `0.00347 mm`.

## Controlled Evidence

The continuous no-collision MILP from `M336-014` was rerun without changing
sides, keep-ins, subgroup co-location, fixed components, or net topology. Each
variant changes only the listed fixed net endpoint to its manual coordinate.

| Manual endpoint override | HPWL lower bound | Score upper bound |
| --- | ---: | ---: |
| None, current runtime | `15693.073693` | `0.972427` |
| `EMI601` | `14492.064838` | `1.053016` |
| `Q601` | `14685.982912` | `1.039111` |
| `EMI601`, `Q601` | `13484.974056` | `1.131657` |
| All 40 frozen endpoints | `13486.352636` | `1.131542` |

Either outlier alone removes the mathematical impossibility. Preserving both
provides substantially more margin and differs negligibly from overriding all
40 endpoints, proving that unrelated fixed components need not be relaxed.

## Impact

The current E1-E4 warm start is not the placement that is subsequently scored:
two high-impact anchor endpoints are silently replaced before optimization.
CUDA tuning cannot recover the resulting `432.7041` HPWL proof deficit. Reports
that describe the run as manual-baseline warm-started are incomplete unless
they expose this override.

## Proposed Resolution

Add an explicit, feature-gated anchor position policy. Keep `geometry` as the
default for original-spec runs. For manual-baseline comparison runs, capture
selected anchor centers from the loaded initial placement, freeze those same
coordinates, and use them consistently for projected-anchor targets and
reporting. Initially scope the policy to `EMI601` and `Q601`; do not move the 15
unclustered fixed components.

Before production integration, run the exact `0.05 mm` shared-coordinate model
with these two endpoint overrides. A continuous upper bound is only a
necessary condition and is not an accepted placement.

`M336-016` completed this exact-site gate: the two-anchor diagnostic found a
`0.05 mm` candidate with HPWL `14114.9242` and score potential `1.08115`.
Collision-free feasibility and native RSMT remain unresolved.

## Acceptance Criteria

- Initialization reports the configured position source for every anchor.
- Frozen lower-left coordinates and physical anchor centers describe the same
  position after loading a warm start.
- Default `geometry` behavior remains unchanged and covered by tests.
- Exact legality reports `100/100`, zero overlaps, and native normalized score
  at least `1.0` for the accepted policy.
