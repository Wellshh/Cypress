# M336-033: Staged Collision Relaxation Does Not Yet Close Exactly

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `1b92768`

## Problem

After exact fixed-obstacle site pruning, the final-endpoint TOP model still has
33,215 candidates and 110 convex-part constraints involving four controlled
nonrectangles. The complete model remained `UNKNOWN` after `300.375451 s`
even when seeded by a rectangle-legal placement. It explored 4,967,223 branches
and 1,675,343 conflicts.

## Diagnostic Correction

`--controlled-collision-relaxation` now exposes two packing-only stages:

- `all-nonrectangle` retains rectangle `NoOverlap2D` but omits every controlled
  pair involving a nonrectangle.
- `mixed-nonrectangle` additionally restores exact collisions among the four
  controlled nonrectangles while omitting only mixed pairs.

Reports list the nonrectangle refdes, relaxation mode, and omitted pair count.
Fixed obstacles remain exact, and exact post-solve validation still rejects
every relaxed candidate with positive-area overlap.

## Evidence

The first `all-nonrectangle` stage solved in `1.870488 s` but had seven TOP
overlaps. `mixed-nonrectangle` retained six part constraints, omitted 104 mixed
pairs, and solved in `1.477940 s`; all nonrectangles were mutually legal, but
six mixed overlaps remained.

Exact local repair of the nine overlap-closure components was `INFEASIBLE` in
`0.313618 s`. Expanding to a deterministic 19-component, 1 mm physical
neighborhood was also `INFEASIBLE` in `1.899624 s` after 41,933 branches.

A two-level L1 sequence proved an `all-nonrectangle` displacement optimum of
`383.958761 mm`, then a `mixed-nonrectangle` incremental optimum of
`13.998496 mm`. Fixing those four nonrectangle sites and releasing all 26 TOP
rectangles was nevertheless `INFEASIBLE` in `2.756229 s`, after 96,225 branches.
Two other fixed-nonrectangle master solutions were also strictly infeasible.

## Interpretation

The relaxation is useful for producing coherent incumbents and small conflict
sets, but serially fixing either shape class loses necessary coupling. None of
the relaxed `OPTIMAL` statuses establishes exact feasibility, and the full
model timeout is not an infeasibility proof.

## Required Improvement

- Add exact controlled collision pairs incrementally from validator findings.
- Retain all previous cuts and warm-start each iteration from its predecessor.
- Accept only zero-overlap output followed by single-worker full-model replay.
- Optimize native HPWL/RSMT only after exact endpoint feasibility is closed.
