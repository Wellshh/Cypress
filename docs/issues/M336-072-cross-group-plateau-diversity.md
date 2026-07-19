# M336-072: Cross-Group Closure Produces Diverse Equal-Objective Plateaus

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `2c91023`

## Problem

The M336-071 placement is a full one/two-optimum, but physical groups sharing
bottom-0 can require higher-order exchanges. Pairwise unions of page-4,
combined page-6, and the two page-7 bottom groups provide interpretable LNS
models without reopening the full 42/80-component boundary.

## Cross-Group Ablation

Six K1024 models used the same certified source, current/quality guides, exact
legality, one worker, seed 1000, repair off, and a feasible current hint:

| Groups | Candidates | Status | HPWL |
| --- | ---: | --- | ---: |
| page-4 + page-6 | 17,491 | `OPTIMAL` | 15812.564715 |
| page-4 + page-7/J701 | 16,468 | `OPTIMAL` | 15812.627221 |
| page-4 + page-7/J702 | 16,468 | `OPTIMAL` | 15812.627221 |
| page-6 + page-7/J701 | 19,537 | `OPTIMAL` | 15812.564715 |
| page-6 + page-7/J702 | 19,537 | `OPTIMAL` | 15812.564715 |
| both page-7 groups | 18,514 | `FEASIBLE` | 15812.627221 |

Every model passes objective replay and exact validation. The three models
containing page-6 converge to the same integer objective `15812564724` but
produce three different placement hashes:

- page-4/page-6: `6eb7430cabf278b8084b938fc42492b787881557fefd0beca14658524456d25b`;
- page-6/J701: `b1e5ee13326ca63423cb6269f66829a485489894d9ef4a4143091a4bc146d72f`;
- page-6/J702: `547498f1e12c5c3d1db2ef32351a12faf179286665913aaecadb709726462f00`.

Each plateau state independently completed full-domain one/two-opt closure
without a move. Equal HPWL therefore does not imply an equivalent future
candidate neighborhood or search state.

## Certified Improvement

The smallest page-4/page-6 model changes ten components and decreases HPWL by
`0.062506275659`, to `15812.564714651957`. Normalized score upper bound is
`0.965078710959920`; the remaining score-1 HPWL gap is
`552.195142865325`.

All-fixed replay returned `OPTIMAL` at `1e-8` deterministic-time with zero
conflicts and branches. All integer objectives equal `15812564724`; floating
replay differs by `0.000009348043`. Exact validation remains 100/100 with zero
violations and overlaps. Search result, placement, certification result, and
local-closure SHA-256 values are:

- `f19f3d713e3983b65a3832a00f7756006a882baabfcb2c435a27c10027a06f6f`;
- `6eb7430cabf278b8084b938fc42492b787881557fefd0beca14658524456d25b`;
- `bd0966f5e735171e3484c6e33d35e957813f551203c858816ebc6923a5bbed3b`;
- `f8a15432e7ecc9016c9e260ff61970c0928b28e0208c3e6865680b24014f4c9e`.

The promoted local closure evaluated 2,882 pairs and 4,918,274 site
combinations before stopping at `two_optimum`.

## Next Action

Retain all three equal-objective placements as deterministic search guides,
but promote only the all-fixed certified page-4/page-6 result. Run refreshed
80-component and residual-ranked neighborhoods from these distinct plateaus;
compare semantic outcomes and placement hashes rather than HPWL alone.
