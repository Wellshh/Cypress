# M336-021: Restored-Anchor Assignment Search Is Too Broad

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `d845191`

## Problem

The restored-anchor packing search enabled all 61 eligible subgroup-region
options. At `0.05 mm`, the unbounded model contained 1,410,293 sites and did
not enter search in 300 seconds. Restricting every component-region domain to
4,096 sites still left 784,707 sites and ended `UNKNOWN` after 302 seconds
without branching.

Only five BOTTOM subgroups can change region in the structured assignment
neighborhood relevant to the two restored anchors. Fixing every other
component coordinate, as `--movable-refdes` does, is unsafe: `M336-018` proved
that collision repair requires movement beyond the anchors' direct neighbors.

## Correction

The discrete solver now accepts repeatable `--movable-subgroup` arguments with
`--optimize-assignment` and exactly one structured `--site-hint-result`.
Listed subgroups retain all eligible regions. Every other nonempty subgroup is
restricted to its consistently hinted region, while all component site
variables remain movable. Empty template subgroups use their preferred input
region because they have no component from which to derive a hint.

The solver rejects unknown subgroup IDs, incomplete structured hints, and use
without optimized assignment before model construction. Reports identify the
`optimized_scoped` mode and the exact movable subgroup set.

## Evidence

A fixed-site contract smoke opened five BOTTOM subgroups and replayed the
restored-anchor skeleton:

| Quantity | Full assignment | Scoped assignment |
| --- | ---: | ---: |
| Region options | 61 | 40 |
| Retained sites at 128 per region | 28,544 | 18,048 |
| Solver status | `OPTIMAL` | `OPTIMAL` |
| Scoped wall time / branches | n/a | `0.010663 s / 0` |
| Exact overlaps | 7 | 7 |

The unchanged seven overlaps establish that scoping changes only assignment
freedom, not hinted coordinates or exact-validation semantics. Unit tests also
cover hinted, movable, fixed, empty, and unknown subgroups.

## Residual Risk

This is a search-space reduction, not a feasibility proof. A legal packing may
require a region change outside the selected subgroup set or sites outside a
limited neighborhood. Full containment, zero overlap, and score at least 1.0
remain mandatory; restored-anchor packing remains open under `M336-018`.

## Acceptance Criteria

- Unlisted subgroup assignments follow the structured result hint.
- Listed subgroups retain every eligible region.
- No component coordinate is frozen by assignment scoping.
- Empty subgroups and invalid input fail or resolve deterministically.
- Fixed replay preserves the input assignment, sites, and exact overlaps.
