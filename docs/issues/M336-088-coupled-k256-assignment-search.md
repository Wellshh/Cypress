# M336-088: Coupled K256 Assignment Domains Are Score-Permitting but Stall

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `e6c8272`

## Problem

M336-087 proved that no single-subgroup K128 assignment domain can reach the
score-1 HPWL threshold. That result did not test coordinated region changes or
the larger site neighborhoods needed to resolve cross-group collisions and
capacity interactions.

## Method

Four coupled K256 searches released the most relevant nonempty BOTTOM groups:

- the two page-86 groups currently sharing `bottom_2`;
- the page-4/page-6 groups;
- both page-7 groups;
- all five nonempty page-86 groups with alternate regions.

Every other subgroup retained its certified hint region, while all component
coordinates remained movable. Runs used OR-Tools `9.15.6755`, a 0.1 mm
lattice, exact decomposed footprints, candidate neighborhoods around both the
certified placement and quality guide, one worker, seed 1000, 60 deterministic
seconds, a 360-second wall limit, and integer HPWL ceiling `15811065584`.
The exact-legal hint capacity floor and manual `EMI601` endpoint override were
enabled.

## Evidence

| Released subgroups | Candidates | Status | Incumbent HPWL | Valid bound | Result SHA-256 |
| --- | ---: | --- | ---: | ---: | --- |
| `ANT8604 + U8601` | 32,581 | `FEASIBLE` | 15811.065584 | 14862.801938 | `492cb24b06268f57549b97cf6acf21fdcded712f59734bfefa2c34d76b2a2377` |
| `MIC401 + J601` | 33,093 | `FEASIBLE` | 15811.065584 | 14940.859328 | `b27246a82e629ba4bcd21ca0a1b747cc6311975a4a38873c51ebfbbdc2158481` |
| `J701 + J702` | 34,629 | `FEASIBLE` | 15811.065584 | 14951.638308 | `8bc27b577497f9d5927a4295bc0f6595b785975adafc49604826b4d911c65c6a` |
| all five page-86 groups | 37,366 | `FEASIBLE` | 15811.065584 | 14863.239003 | `4d855edd0d79f6cd21b732a7acd3651ef4ccd7e612d37418d1cee269cd0c7672` |

Every emitted incumbent preserved the source region assignment and actual
HPWL `15811.06557381333`. Exact validation reports 100/100 containment, zero
keep-in violations, and zero overlaps. Thus the monotonic ceiling worked, but
no run improved the certified placement within its deterministic budget.

Unlike the single-group K128 bounds, all four bounds are below the necessary
score-1 HPWL threshold `15260.369571786632`, even after accounting for the
`0.000304` model rounding allowance. Coupling therefore changes the restricted
quality conclusion: these domains are score-permitting and cannot be closed as
non-scoring from the available bounds.

## Scope and Next Step

`FEASIBLE` does not mean the current placement is optimal, and a lower bound
below the score threshold does not prove a score-1 placement exists. These are
finite, candidate-limited models with fixed regions outside the released set.

The next experiment should impose the score-1 HPWL limit directly and run in
feasibility mode on the same four domains. This removes the already-known
source incumbent and spends the deterministic budget only on finding a
threshold-satisfying exact placement. Any `UNKNOWN` result must remain unknown;
only `INFEASIBLE` with a completed proof can close a restricted domain.

Follow-up M336-089 completed that experiment: all four K256 threshold models
are `INFEASIBLE`. This closes only those candidate-limited domains; K512 and
broader coupled domains remain untested.
