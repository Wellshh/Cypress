# M336-074: Alternating Group Closure And Regional Refresh Keeps Improving

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `2e6fa47`

## Problem

M336-072 moved the placement onto three distinct equal-HPWL cross-group
plateaus. Regional optimality and physical-group closure are topology-dependent,
so the 80-component corrected boundary must be refreshed from each changed
platform rather than treated as closed after M336-071.

## Refresh Results

All runs used current/quality guides, exact legality, one worker, seed 1000,
repair off, and 300 deterministic-time units:

| Source plateau | Domain | HPWL | Valid lower bound |
| --- | ---: | ---: | ---: |
| certified page-4/page-6 | K256 | 15811.065574 | 14712.286843 |
| certified page-4/page-6 | K512 | 15812.564715 | 14725.567578 |
| page-6/page-7-J701 | K256 | 15811.065574 | 14730.716375 |
| page-6/page-7-J702 | K256 | 15812.564715 | 14718.144320 |

Every status is `FEASIBLE`, every objective replay passes, and every incumbent
is exactly legal. K512's wider domain does not produce a better incumbent in
the fixed budget; this is a search result, not a domain-quality ordering.

## Certified Improvement

The promoted K256 result changes `C607`, `C608`, `MHC8601`, `R601`, and `R606`.
HPWL decreases by `1.499140838627`, to `15811.065573813330`; normalized score
upper bound increases to `0.965170215792491`. The remaining score-1 HPWL gap is
`550.696002026698`.

All-fixed replay returned `OPTIMAL` at `1e-8` deterministic-time with zero
conflicts and branches. All integer objectives equal `15811065584`; floating
replay differs by `0.000010186670`. Exact validation reports 100/100
containment and zero violations or overlaps. Search result, placement,
certification result, and local-closure SHA-256 values are:

- `c3ded6e8f788c2479bc667e9bd15233dc6b8453a56992deef966cd59252d76ad`;
- `e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`;
- `d6025549fecc83161d5df3164e48b5a36f8daa303d7e22344d9e64a395f079a0`;
- `54361f3c93ff84a4da296ba969fdff2f8fae4ff8c15d772f34948d49b2341641`.

Full-domain local closure accepted no move after evaluating 2,871 pairs and
5,199,580 site combinations. It stopped at `two_optimum`; the placement hash
remains identical to the all-fixed replay.

## Finding And Next Action

Alternating regional search with physical-group/cross-group closure continues
to cross barriers that either phase alone misses. Plateau identity also matters:
two equal-objective sources lead to different K256 outcomes. Continue the
alternating loop from the certified result, while separately evaluating the
explicit candidate-guide weights added by M336-073. Promote only strict,
all-fixed certified improvements.
