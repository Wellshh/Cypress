# M336-067: Page-86 Physical Groups Are Exact Local Optima

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `310996b`

## Problem

M336-066 showed that releasing all 38 newly added page-86 and `Q601`
components at once is too difficult for a bounded K256 solve. The staged set
must be decomposed without mistaking a search timeout for evidence that its
constituent physical groups cannot improve the incumbent.

## Method

The three physical groups containing more than two controlled components were
optimized independently: `page_86_ANT8604__bottom` (3),
`page_86_U8601__bottom` (11), and `page_86_U8602__bottom` (16). Every other
controlled component remained fixed at the certified incumbent. Each model
used the current and collision-relaxed quality guides, K1024 limiting, one
worker, seed 1000, repair off, and exact side-specific keep-in and overlap
constraints. No hard improvement ceiling was imposed, so the current legal
hint remained an available incumbent.

## Result

All three solves returned `OPTIMAL` at the incumbent's audited integer HPWL
`15835344206` and floating replay `15835.344195928667`:

| Group | Candidates | Deterministic time | Conflicts | Branches | Result SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| `ANT8604` | 614 | 0.050883 | 3 | 169 | `867909fff7d74c008c0b350235cb233b3a2e123928207df14a66ab02ff7f7656` |
| `U8601` | 2,432 | 1.012407 | 651 | 24,875 | `826bad3fc6892a92b4feb6d1e63b3e41487ba96ee81b141f6a16324698086492` |
| `U8602` | 11,535 | 96.858623 | 149,277 | 697,914 | `0d3bfb35d8d3a8f66cbabd4b8999b899626401f58d12d8258bab119301dfc864` |

Every movable component had fewer than 1,024 fixed-obstacle-free candidates,
so candidate limiting did not truncate these group domains. Response,
solved-variable, and selected-site objectives match; floating replay is within
the audited rounding allowance. Exact validation reports 100/100 containment,
zero keep-in violations, and zero overlap pairs for every result.

The remaining staged physical groups have at most two controlled members and
are covered by the incumbent's complete full-domain one/two-opt closure.

## Finding

No newly added physical group can improve the incumbent independently while
all other sites stay fixed. Therefore the lower potential exposed by the
38-component staged model requires a cross-group move, not more budget on any
single page-86 group. This is a restricted decomposition result, not a global
or combined-domain infeasibility claim.

## Next Action

Search cross-group neighborhoods together with the bottom-0/page-7 closure.
Prioritize deterministic current/quality candidate domains with a feasible
current hint, and require a strict all-fixed replay before promotion. Do not
repeat isolated page-86 group optimization unless their fixed surroundings
change.
