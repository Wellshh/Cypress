# M336-069: Current-Quality Domain Breadth Improves Bottom-0 Closure

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `32977a9`

## Problem

Prior regional searches divided each fixed candidate budget among manual,
current, and collision-relaxed quality guides. The manual placement is the
score baseline but is neither legal nor necessarily useful as a candidate
source near the certified incumbent. Candidate allocation must be separated
from movable-set breadth before increasing solve budgets again.

## Deterministic Ablation

Four single-worker, seed-1000 models used only current and quality candidate
guides, retained the current legal hint, optimized HPWL without a hard ceiling,
and enforced exact side-specific keep-in and overlap constraints:

| Movable domain | Candidate limit | Candidates | Status | HPWL | Valid lower bound |
| --- | ---: | ---: | --- | ---: | ---: |
| staged page-86/Q601 (38) | K256 | 8,776 | `FEASIBLE` | 15835.344196 | 15434.316398 |
| combined corrected boundary (80) | K128 | 10,176 | `FEASIBLE` | 15835.344196 | 14823.229445 |
| bottom-0/page-7 closure (42) | K256 | 10,810 | `FEASIBLE` | 15832.404447 | 15151.358202 |
| bottom-0/page-7 closure (42) | K512 | 21,435 | `FEASIBLE` | 15820.626362 | 15138.860136 |

The first three runs consumed approximately 300 deterministic-time units;
the 80-component run hit its 600-second wall limit at 298.050040 units. K512
used 300.697110 deterministic-time units. Every returned incumbent passes
objective replay and exact legality. The two broad corrected-boundary models
do not improve the source, while allocating more current/quality sites to the
42-component collision closure does.

## Certified Improvement

K512 changes 11 controlled components and decreases HPWL by
`14.717834162424`, from `15835.344195928667` to `15820.626361766243`.
Normalized score upper bound increases to `0.964586940038380`; the remaining
score-1 HPWL gap is `560.256789979610`.

The all-fixed replay returned `OPTIMAL` at `1e-8` deterministic-time with zero
conflicts and branches. Response, solved-variable, and selected-site
objectives all equal `15820626372`; floating replay differs by
`0.000010233758`. Exact validation reports 100/100 containment, zero keep-in
violations, and zero overlap pairs. The K512 result, placement, certification
result, and certified placement SHA-256 values are:

- `b0e72d877a26bbcaccd0d1e42537d48b22d29b7b2a97134ec2a8f901e75a1c77`;
- `87a7c52e558df154ed92ef5516e5834661d8280a5ffcc5d0e01bbd3dced3789c`;
- `206952a5e6b65c0d8d6ed2842e565485e31a8f0c3838baf59f243d376a2e1f9e`;
- `87a7c52e558df154ed92ef5516e5834661d8280a5ffcc5d0e01bbd3dced3789c`.

Full-domain one/two-opt closure accepted no move after evaluating 2,894 pairs
and 1,839,536 site combinations. It stopped at `two_optimum`; result SHA-256
is `742414f94aab397f43abc17a3e185f64153a4114b6fba8a1bc5eeac3415224ec`.

## Finding And Next Action

Manual-baseline candidate allocation was consuming useful regional width.
Current/quality K512 finds a materially better incumbent under the same
deterministic solve budget, but its lower bound still leaves a 681.766226 HPWL
floating-replay gap (`681.766236` in the integer model). Continue from the
all-fixed K512 result, refresh every physical
and cross-group neighborhood around its changed topology, and preserve the
manual placement strictly as the native score baseline rather than a default
candidate guide.
