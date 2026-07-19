# M336-054: Hotspot Regional Domain Cannot Close the Score Gap

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `7dfd537`

## Problem

Exact one- and two-component descent stalled at HPWL `15982.050728`. A larger
regional solve was required to cross that local optimum, but the selected
regional domain must also be tested for whether it can reach score 1.0. A good
incumbent alone is not evidence that the restricted model can close the full
gap.

## Neighborhood Selection

The certified incumbent and quality guide were replayed with identical runtime
fixed endpoints and the `EMI601` manual-baseline override. The guide replayed
exactly at its recorded HPWL `14700.901479`. The ten largest per-net incumbent
penalties define 20 controlled components across page 7, page 86, and the
`R604`/`R605` pair. The solve kept the other 80 controlled components fixed,
used K512 candidate domains, retained manual/current/quality guides, and ran
one worker with seed 1000 for 300 deterministic-time units.

## Result

The model contained 9,650 candidates and returned `FEASIBLE` after
343.242 seconds wall time:

- HPWL improved by `27.435187`, from `15982.050728` to `15954.615541`;
- normalized score upper bound improved to `0.956486199`;
- 14 of the 20 movable components changed sites;
- exact legality is 100/100 containment with zero keep-in violations and
  overlaps;
- response, solved-variable, and selected-site objectives all equal
  `15954615548`;
- floating replay differs by `0.000007173045`, within the rounding allowance;
- the valid solver lower bound is `15605.810908`.

An all-fixed replay returned `OPTIMAL` at `1e-8` deterministic-time with zero
conflicts and branches and the same objective, HPWL, placement, and legality.
The regional result, placement, certification result, and certified placement
SHA-256 values are:

- `466a7bfe10e87deeeef88bd340b64ee11bebc72b20d2ef5ebbb50dba9578c0ea`;
- `106b00ac88217dae53cd00082b268f68e54c584710836673d557adbfbad931ac`;
- `f2ee1d79175fc8dfa421a475bab78cce5d05a997756f55284a34a50e18e8d4d7`;
- `106b00ac88217dae53cd00082b268f68e54c584710836673d557adbfbad931ac`.

## Boundary-Release Follow-up

Full-domain exact one/two-opt descent from the certified regional result found
one additional blocker-release swap. `B401`, which was fixed outside the
regional model, and movable `R705` exchanged their occupied sites. They share
no net; the move is only available when each component releases the other's
blocked site. The swap reduced HPWL by `40.495489` to `15914.120051`, after
which a second complete pair search found no improving pair.

An all-fixed replay again returned `OPTIMAL` at `1e-8` deterministic-time.
Response, solved-variable, and selected-site objectives all equal
`15914120059`; floating replay differs by `0.000007575833`. Exact legality
remains 100/100 with zero violations and overlaps. The local result, placement,
certification result, and certified placement SHA-256 values are:

- `49372b1e585b1e633ce125ba9d64883d2a17b186d7771ab8291cd8a0322728a0`;
- `c4b0d173cf57d190f569fca7cb194b52c544d91bb6d130a62777cd30a366dc8e`;
- `88e437b6dff091e588e1b981403172d40a8a6268bbc60698ebdf2419ecada776`;
- `c4b0d173cf57d190f569fca7cb194b52c544d91bb6d130a62777cd30a366dc8e`.

## Finding And Next Action

The certified post-swap incumbent remains `653.750480` above the necessary
score-1 HPWL threshold. The restricted regional model's valid lower bound is
`345.441336` above that threshold. Therefore no placement with these 80 fixed
sites and the tested K512 domains can reach score 1.0, even though the solve
successfully crossed the prior two-optimum. The later `B401`/`R705` swap is
outside that model and demonstrates why the conclusion applies only to the
restricted domain, not the full placement problem.

Recompute residual per-net penalties from the certified incumbent. Expand the
movable set by connected boundary components and selectively widen high-impact
domains to K1536. Require objective replay and all-fixed certification after
every improvement; preserve `UNKNOWN` for budget-limited global searches.

## Domain-Breadth Ablation

Residual penalties were recomputed after the boundary swap. Two deterministic
models with similar total candidate counts were run in parallel from that
certified source:

| Model | Candidates | Status | DT | HPWL |
| --- | ---: | --- | ---: | ---: |
| top-10 nets, 20 components, K512 | 9,650 | `OPTIMAL` | 290.065877 | 15914.120051 |
| top-15 nets, 31 components, K256 | 7,847 | `OPTIMAL` | 67.902321 | 15909.178850 |

The wider K512 site domains cannot improve the source at all, while expanding
the movable boundary at K256 improves HPWL by `4.941201`. This isolates movable
component breadth, rather than per-component candidate width, as the useful
dimension at this stage. Both response audits pass; neither result is a
budget-limited `UNKNOWN`.

The top-15 result changes 14 components and has normalized score upper bound
`0.959217928`. Its all-fixed replay is `OPTIMAL` at `1e-8`
deterministic-time, with all integer objectives equal `15909178856`, floating
delta `0.000005503485`, and exact zero-violation legality. The top-10 result,
top-15 result, top-15 placement, certification result, and certified placement
SHA-256 values are:

- `a10d4867ca94ecdb1f41b88958efb410b8ba98cab8109797f56c648b50f161cf`;
- `1bff15bd3427113391a4aca0d7541ddd378e2495f2cb60da850cf3ec91ba7594`;
- `cd88332b347b89ca1a318f89f9548d883d4cc829feeccc5973df8ff8b3dab653`;
- `f9ae5a7f695d74bd1eff6360550f26299314e03a427f61157253f06a41d8738e`;
- `cd88332b347b89ca1a318f89f9548d883d4cc829feeccc5973df8ff8b3dab653`.

The new certified incumbent is `648.809279` above the score-1 threshold. The
next solve should expand the connected movable boundary again; simply raising
K512 for the old 20-component neighborhood is now exactly proven ineffective.
