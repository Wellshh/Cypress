# M336-036: Nonrectangle-First Search Regresses Conflict Learning

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `f5e4be3`

## Problem

M336-035 identified four rotated TOP footprints outside the original rectangle
`NoOverlap2D` set. A plausible decomposition was to branch on those four x/y
domains first, then let CP-SAT place the 26 axis-aligned rectangles. This needed
measurement because a fixed partial search can also suppress the solver's
portfolio heuristics.

## Experiment

A temporary `PARTIAL_FIXED_SEARCH` strategy used `CHOOSE_FIRST` and
`SELECT_LOWER_HALF`. It covered only the four rotated-component coordinates;
the solver remained responsible for all other variables. Both runs used the
same round-13 hint, 100 cuts, 1,024-site neighborhoods, 32 inner slices, 26,590
candidates, seed 1000, eight workers, and a 120-second limit.

The first ordering used the swept-domain graph. Every rotated component had
degree 29, so lexical tie-breaking produced `C8653`, `L8607`, `L8626`,
`L8630`. The second ordering used only enforced cuts and produced:

```text
L8607: 29
L8626: 29
L8630: 28
C8653: 20
```

## Evidence

| Search | Status | Time (s) | Branches | Conflicts |
| --- | --- | ---: | ---: | ---: |
| Automatic portfolio | UNKNOWN | 120.798 | 1,082,725 | 13,014 |
| Swept-degree partial fixed | UNKNOWN | 120.227 | 1,172,143 | 494,620 |
| Enforced-degree partial fixed | UNKNOWN | 120.643 | 1,063,406 | 661,029 |

The two temporary result SHA-256 values are
`bdd745df4ebc92022a7701b9d2e066724745e24b44557fd36d02cda77603b223`
and `851169543f4c1b7d436c7f9e8fdac1a2596327ea3f746a3bc577bbd5a431e947`.
Neither strategy found an incumbent. Correcting the graph reduced branches but
increased conflicts to more than 50 times the automatic-search count.

## Resolution

The strategy, CLI option, report fields, and unit test were removed before
commit. Automatic OR-Tools search remains unchanged. This issue is resolved as
a rejected approach, not as endpoint feasibility: M336-034 remains open.

Future search decomposition must preserve portfolio diversity or operate on a
smaller exact subproblem with a demonstrated interface. Collision degree alone
does not capture which rotated placement enables the rectangle packing.
