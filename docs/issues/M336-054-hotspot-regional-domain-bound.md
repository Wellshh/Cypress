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

## Finding And Next Action

The new incumbent remains `694.245969` above the necessary score-1 HPWL
threshold. More importantly, this restricted model's valid lower bound is
`345.441336` above that threshold. Therefore no placement with these 80 fixed
sites and the tested K512 domains can reach score 1.0, even though the solve
successfully crossed the two-optimum. This conclusion applies only to the
restricted regional model, not the full placement problem.

Recompute residual per-net penalties from the certified incumbent. Expand the
movable set by connected boundary components and selectively widen high-impact
domains to K1536. Require objective replay and all-fixed certification after
every improvement; preserve `UNKNOWN` for budget-limited global searches.
