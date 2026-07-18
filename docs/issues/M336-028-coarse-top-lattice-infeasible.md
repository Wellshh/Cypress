# M336-028: Restored-Anchor TOP Packing Is Infeasible at 0.2 mm

**Severity:** High
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `604057f`

## Problem

A coarse-to-fine strategy attempted to obtain a legal TOP guide on a `0.2 mm`
lattice before projecting it into the `0.1 mm` production search. The coarse
lattice cannot pack the selected TOP assignment after restoring `Q601` and
`EMI601` to their manual-baseline endpoints.

## Evidence

The side-decomposed, packing-only model used exact decomposed footprints, the
fixed quality assignment, seed 1000, and eight workers. It contained 30 TOP
controlled nodes, 12,627 candidate sites, 197 encoded component pairs, and 656
convex-part constraints. CP-SAT returned `INFEASIBLE` in 7.280733 solver
seconds after 154,895 branches and 13,370 conflicts.

The snapped coarse skeleton is not evidence of feasibility: it had 88 exact
overlap pairs. Its HPWL `20514.832461` and score upper bound `0.743870` are
diagnostic only.

## Interpretation

This is a proof only for the exact `0.2 mm` lattice origin, fixed subgroup
assignment, restored endpoints, and footprint model used by the run. It does
not prove that `0.1 mm`, a shifted lattice, a different assignment, or
continuous coordinates are infeasible. Extending this result to those domains
would repeat the grid-resolution error documented in M336-008.

## Required Improvement

- Use a finer or shifted intermediate lattice, or repair collision components
  directly on `0.1 mm`.
- Keep unmodeled-side coordinates as hints only and require global exact
  validation after both sides are merged.
- Fixed-replay any discovered guide before running native HPWL/RSMT scoring.

## Acceptance Criteria

- 100/100 exact keep-in containment and zero overlap pairs.
- Single-worker fixed replay reproduces the placement hash.
- Native normalized HPWL/RSMT score is at least `1.0`.
