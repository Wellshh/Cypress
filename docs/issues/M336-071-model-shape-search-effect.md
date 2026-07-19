# M336-071: Movable Breadth Changes Search Without Changing Final Support

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `22a6966`

## Problem

After M336-069, deterministic continuation of the 42-component
bottom-0/page-7 closure did not improve its source at either K512 or K1024.
The corrected 80-component model did improve, but the final component support
must be inspected before attributing that gain to page-86 cross-group motion.

## Controlled Comparison

All runs used the same certified source, current/quality guides, one worker,
seed 1000, repair off, exact legality, and approximately 300 deterministic-time
units:

| Movable set | Domain | Candidates | HPWL | Valid lower bound |
| --- | ---: | ---: | ---: | ---: |
| bottom-0/page-7 (42) | K512 | 21,435 | 15820.626362 | 15138.860136 |
| bottom-0/page-7 (42) | K1024 | 42,427 | 15820.626362 | 15138.860136 |
| corrected boundary (80) | K256 | 19,486 | 15812.627221 | 14754.685451 |

Every status is `FEASIBLE`, not `OPTIMAL`. Every incumbent passes selected-site
objective replay and exact validation.

## Search-Shape Finding

The 80-component result changes only six components: `C703`, `FV302`, `FV705`,
`FV706`, `FV707`, and `FV709`. All six belong to the original 42-component
closure. None of the additional 38 page-86/Q601 variables changes its source
site. The improved assignment is therefore also inside the K512/K1024
42-component domains, but those deterministic runs did not discover it.

This is a CP-SAT search-trajectory effect caused by model shape and propagation,
not evidence that the extra components are required by the final placement.
Consequently, FEASIBLE incumbent comparisons cannot be used to rank domain
quality or infer physical causality. The runs remain individually specified
and deterministic; an identical 80/K256 replay is in progress to audit
selected-site reproducibility.

## Certified Improvement

HPWL decreases by `7.999140838627` from the common source and by
`7.936634562968` from the M336-070 incumbent, reaching
`15812.627220927616`. Normalized score upper bound is `0.965074896067234`, and
the remaining score-1 HPWL gap is `552.257649140984`.

The all-fixed replay returned `OPTIMAL` at `1e-8` deterministic-time with zero
conflicts and branches. All integer objectives equal `15812627230`; floating
replay differs by `0.000009072384`. Exact validation reports 100/100
containment and zero violations or overlaps. Result, placement, certification,
and local-closure SHA-256 values are:

- `3fc29c45c789be0042b76ce8eec36d79c55a966031aa2cafed77f15f6832d1b6`;
- `a4747d8a5f4dbebe989d739fb20412ac65afe11e621bda5d1bda7ebf1ee82e4f`;
- `dc110214941810b92aae743f9f3c39427a2f97004d3582fb42658ff84da3fcc8`;
- `0b17072317022dfaa9167a9666d48813894c96ca74197c6ec15dd42ed0130e2d`.

Full-domain local closure accepted no move after evaluating 2,884 pairs and
1,422,320 site combinations; the placement hash remains unchanged.

## Next Action

Use the certified 80/K256 incumbent as the next source. Continue deterministic
seed portfolios and topology refresh, but report each model's bound, seed,
candidate construction, and exact changed support. Promote only all-fixed
certified placements, and never interpret a better FEASIBLE incumbent as proof
that a wider domain is intrinsically better.
