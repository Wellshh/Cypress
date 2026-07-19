# M336-052: Remaining HPWL Gap Requires Coupled Site Moves

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `fa3170d`

## Problem

The certified mixed-side incumbent has HPWL `15997.273154`, while score 1.0
requires HPWL no greater than `15260.369572`. Global CP-SAT searches are
expensive and their presolved response metadata requires separate
certification. A deterministic diagnostic was needed to identify whether
isolated component moves could still close the gap.

## Exact One-Opt Method

`greedy_exact_site_descent.py` enumerates every obstacle-free feasible-domain
site for each controlled component in sorted refdes order. For each candidate
it:

- checks exact same-side overlap using the acceptance area threshold;
- recomputes only nets incident to the moving component;
- applies a move only when independent PlaceDB HPWL strictly decreases;
- repeats full sweeps until no component can improve;
- runs the full exact keep-in and overlap report before writing output.

The run evaluated 133,174 candidate sites. Intermediate results set
`certification_required=true`; the native scorer rejects them until an
all-fixed CP-SAT replay passes objective audit.

## Result

Three moves were accepted over two improving sweeps:

| Component | HPWL change |
| --- | ---: |
| `FV703` | -7.999141 |
| `FV708` | -1.999785 |
| `FV707` | -1.999785 |

The third sweep found no improving single-component move. HPWL decreased by
`11.998711` to `15985.274443`; cumulative improvement from the initial legal
state is `2085.418318`. Exact legality is 100/100 containment with zero
keep-in violations and overlaps.

An all-fixed BOTH-side replay returned `OPTIMAL` at `1e-8`
deterministic-time. Response, solved-variable, and selected-site integer
objectives all equal `15985274454`; floating HPWL differs by only
`0.000011451199`. The greedy result, greedy placement, certification result,
and certified placement SHA-256 values are:

- `b117f33cf8f20e61d2e079ec67aca921ad60c947f060e62f3f748d30c4a9b3f6`;
- `6a8677032b22032a6c2dacc657e30e386c3a02aff9780cbae4fbb6ee41a4608b`;
- `4649aec35ebe85a37a6951224f2856d1f7e2ecbe2b0bac06df3258f03d2d23dc`;
- `6a8677032b22032a6c2dacc657e30e386c3a02aff9780cbae4fbb6ee41a4608b`.

## Finding And Next Action

The certified layout is now an exact one-optimum over all current feasible
sites. Its HPWL remains `724.904871` above the necessary threshold, so further
progress requires at least one coupled move, swap, or temporary non-improving
move. Rebuild global mixed-side neighborhoods around this incumbent and use
the one-opt sweep after each certified global improvement. Do not infer global
infeasibility from this local optimum.
