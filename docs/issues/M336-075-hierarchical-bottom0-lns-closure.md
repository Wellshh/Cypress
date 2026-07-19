# M336-075: Every Three-Group Bottom-0 LNS Domain Is Score-Insufficient

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `d89195a`

## Problem

M336-074 is a full one/two-optimum. Single physical groups and pairwise group
unions can still miss three-stage ejection chains, but reopening the entire
42/80-component model obscures which collision boundary is required.

## Hierarchical LNS

Page-4, combined page-6, page-7/J701-bottom, and page-7/J702-bottom define four
major controlled groups in shared bottom-0 space. From the certified M336-074
source, each single group and each previously effective page-6 pair was first
optimized at K1024. All returned `OPTIMAL` at source HPWL
`15811.065573813330`.

The next level released every three-group union. Models used current/quality
guides, exact legality, one worker, seed 1000, repair off, and approximately
300 deterministic-time units:

| Released groups | Candidates | Status | Valid HPWL lower bound |
| --- | ---: | --- | ---: |
| page-4 + page-6 + J701 | 26,698 | `FEASIBLE` | 15396.996759 |
| page-4 + page-6 + J702 | 26,698 | `FEASIBLE` | 15557.733318 |
| page-4 + J701 + J702 | 25,675 | `FEASIBLE` | 15299.533374 |
| page-6 + J701 + J702 | 28,744 | `FEASIBLE` | 15291.543392 |

Every incumbent is exactly the certified source placement; objective replay
passes and exact validation reports zero violations or overlaps. `FEASIBLE`
does not establish optimality, but each solver lower bound is valid for its
restricted model.

## Finding

All four lower bounds exceed the score-1 HPWL threshold `15260.369572`.
Therefore none of these K1024 three-group domains can reach the manual-baseline
score, even at its optimum. This is not a global infeasibility result and does
not cover candidate sites outside K1024.

The closest restricted bound, page-6 plus both page-7 groups, remains
`31.173820` HPWL above the threshold. At least the fourth bottom-0 group,
additional boundary components, or a materially different candidate domain is
required to retain score feasibility.

## Next Action

Stop repeating single-, pair-, and three-group K1024 models until surrounding
topology changes. Focus on the complete bottom-0 collision closure, the
corrected 80-component boundary, quality-rank escape seeds, or explicit
candidate reallocations. Continue distinguishing valid restricted bounds from
FEASIBLE incumbent quality.
