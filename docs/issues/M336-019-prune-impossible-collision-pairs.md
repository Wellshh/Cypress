# M336-019: Exact Collision Model Encodes Impossible Pairs

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `3372094`

## Problem

The corrected `decomposed` collision model was geometrically sound but emitted
constraints for every same-side controlled/fixed pair and every nonrectangular
controlled pair. Many components can never approach one another anywhere in
their candidate domains. Their redundant convex-part disjunctions dominated
presolve and search.

The known legal `0.1 mm` fixed-hint audit generated 62,080 convex-part pair
constraints and required `2.941956 s`, despite all site variables being fixed.
Full-domain restored-anchor feasibility then remained `UNKNOWN` after
`301.358881 s`, 3,812,268 branches, and 202,802 conflicts.

## Correction

Each model shape now records the axis-aligned swept footprint bounds over all
of its candidate sites. An explicit pair is omitted only when one swept bound
ends at or before the other on x or y. Such footprints cannot have positive
intersection area at any modeled site, so the test is independent of the hint
and preserves exact-validator semantics. Candidate x/y correlation is ignored,
making the bound conservative rather than unsafe.

The global `NoOverlap2D` constraint for controlled rectangles is unchanged.
Reports now separate encoded component pairs, skipped component pairs, and
expanded convex-part pair constraints.

## A/B Evidence

| Fixed hint | Before | After | Result |
| --- | ---: | ---: | --- |
| known legal | 62,080 parts, `2.941956 s` | 3,383 parts, `0.282624 s` | `OPTIMAL`, 0 branches |
| 362 exact overlaps | 62,080 parts, `1.100035 s` | 3,500 parts, `0.191123 s` | `INFEASIBLE`, 0 branches |

The legal run encoded 355 component pairs and safely skipped 1,972. Its
placement hash remained
`1551a2dacf7ebd4f935dc72c194f24a37c5140d875bc93c7fe4a41fc3c835103`,
byte-identical to both the unpruned and collision-disabled placements.

Generated result hashes are:

- Legal: `e59e3b5bc293310cea70501bc0cfe4b26b063e5ec6638ad3985fb24450e0b6f6`
- Illegal: `42b20d7632e23c0bcff53fe23ffcee9cf57e3faa471e9524ee4ef499850128ab`

## Residual Risk

Swept boxes may overlap even when correlated candidate sites cannot, so some
redundant pairs remain. Further pruning must remain a one-way impossibility
proof; heuristic distance cutoffs are not acceptable. Full restored-anchor
packing and score-1 feasibility remain open under `M336-018`.

## Acceptance Criteria

- Touching or disjoint swept boxes are skipped; overlapping boxes are retained.
- Known legal and illegal fixed-hint outcomes remain unchanged.
- The legal placement output is byte-identical before and after pruning.
- Pair counts are emitted in every solver report.
