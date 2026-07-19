# M336-065: Corrected Residual Boundary Is Too Broad For One K128 Step

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `bb2dfd1`

## Problem

After correcting legacy endpoint replay, the certified incumbent exceeds the
collision-relaxed quality guide by 1134.442717 HPWL. The existing 42-component
closure already contains the dominant page-7 and bottom-0 endpoints, but leaves
page-86 groups and the `R604/R605` pair fixed. Releasing every corrected
boundary at once may improve model completeness while regressing search.

## Expanded Domain

The existing 42 components were unioned with every controlled member of
`page_6_Q601` and all page-86 subgroups from the selected assignment. Sorting
and deduplication produced 80 movable and 20 fixed components. The K128 model
used manual/current/quality guides, retained the certified current hint, and
imposed integer HPWL ceiling `15834344206`, exactly 1.0 below the incumbent.
It used one worker, seed 1000, repair off, first-solution mode, and 300
deterministic-time units.

## Result

The model built 10,176 candidates and returned `UNKNOWN` without an incumbent:

- solver wall time: 560.168233 seconds;
- deterministic time: 300.000470;
- conflicts: 972,666;
- branches: 3,678,202;
- valid HPWL lower bound: 14855.574671.

The bound is below both the requested one-step ceiling and the score-1
threshold. It proves neither request infeasible. With no incumbent, legality
and objective replay are correctly absent. Result SHA-256 is
`2d7f6754263b14b36a9b9ba9e94a286aedd3e27b6cd12343379b9860799701ed`.

## Finding

Increasing movable breadth from 42 to 80 restores relevant boundary degrees of
freedom but makes a single bounded solve less effective. This is a
budget-limited search failure, not evidence against the expanded domain.

## Next Action

Stage the expansion. Optimize only the 38 newly added page-86 and Q601
components at K256 while the certified bottom-0/page-7 state remains fixed.
Then run exact local closure and, only after a strict certified improvement,
retry the combined boundary from the changed topology.

