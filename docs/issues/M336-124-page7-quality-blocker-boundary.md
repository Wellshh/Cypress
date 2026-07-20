# M336-124: Page-7 Quality Topology Reaches A Frozen-Anchor Boundary

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `9501077`

## Finding

M336-123 closed both tested rank layers over the 18 page-7 components. To
change the search freedom without releasing unrelated groups, the tracked
page-7 quality hybrid was replayed over M336-118 and validated with the final
exact footprint-overlap and keep-in implementation.

The collision-relaxed hybrid has HPWL `15238.268912937441`, below the score-1
necessary HPWL threshold `15260.369571786632`, with zero keep-in violations.
It has 121 overlaps: 115 are internal to page 7, and the only external pairs
are:

| Outside component | Page-7 component | Overlap area | Movable policy |
| --- | --- | ---: | --- |
| B402 | FV710 | 105.277384 | controlled, releasable |
| B402 | R708 | 99.178694 | controlled, releasable |
| L401 | FV708 | 72.884343 | controlled, releasable |
| L401 | R709 | 26.394330 | controlled, releasable |
| MIC401 | FV710 | 32.770530 | physical anchor, frozen |
| MIC401 | R708 | 5.331073 | physical anchor, frozen |

Thus `B402` and `L401` are the complete movable one-hop blocker boundary.
Releasing any other controlled component at this stage would not be justified
by the exact overlap graph.

## Expanded Hybrid Audit

An expanded guide additionally assigns `B402/L401` their full quality-guide
coordinates. It is deterministically derived from tracked inputs and has
SHA-256
`b99db13fd585386965de03919145f5f0b39c455a8a58e3b4b438f20d123769d3`.
Its exact replay has HPWL `15252.267516800206`, zero keep-in violations, and
119 overlaps. No new movable external blocker appears. Its four external
collisions are `MIC401` with `B402`, `L401`, `FV710`, and `R708`, with overlap
areas `147.568299`, `147.568299`, `32.770530`, and `5.331073` respectively.

The expanded hybrid also remains below the necessary HPWL threshold by
`8.102055`. It is not a legal placement and is not a scoring candidate.
Moving `MIC401` would violate the frozen physical-anchor contract, so the
quality coordinates must be treated only as candidate centers around which
the exact solver searches for legal alternatives.

## Next Action

Expand the page-7 movable support from 18 to exactly 20 components by adding
`B402,L401`. Search the `0.05 mm` K4096 candidate domain with the expanded
hybrid as primary guide, M336-118 as independent hint and hard HPWL ceiling,
and exact BOTH-side collision constraints. Compare direct HPWL optimization
with minimum-rank topology discovery. Do not release `MIC401`; promote only a
strict all-fixed certified improvement.
