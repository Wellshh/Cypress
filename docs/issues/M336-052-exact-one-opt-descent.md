# M336-052: Remaining HPWL Gap Requires Coupled Site Moves

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `49585de`

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

## Coupled-Move Follow-up

A lexicographic sweep first moved 20 components toward the quality guide on
equal-HPWL sites. HPWL remained `15985.274443`; a subsequent global K64 solve
did not improve it and failed objective replay, so its response objective and
lower bound are quarantined under M336-051.

The local solver was then extended with exact blocker-aware two-component
descent. It considers pairs that share a net or can release a site blocked by
the other component, recomputes joint net extrema for every legal site pair,
and re-runs one-opt after each accepted pair. Three exact pair searches checked
2,867, 2,870, and 2,891 relevant pairs. They accepted:

| Components | HPWL change |
| --- | ---: |
| `C404`, `RT601` | -1.723930 |
| `C703`, `FV707` | -1.499785 |

The resulting HPWL is `15982.050728`, an additional `3.223715` improvement and
a cumulative `2088.642033` reduction from the first legal state. Exact
legality remains 100/100 containment with zero keep-in violations and overlaps.
The search stopped at an exact two-optimum over the current site domains.

An independent rerun from the same certified source reproduced all selected
sites, both pair moves, pair and combination counts, HPWL, stop reason, and
legality. After excluding output paths and elapsed-time diagnostics, the two
JSON results are byte-identical; the placement files are byte-identical with
SHA-256 `e21d5559efddbb8376b9aedcd4d94829cbf6c50d5a4a14213e546fa10c7d60b5`.

An all-fixed BOTH-side replay returned `OPTIMAL` at `1e-8` deterministic-time.
Response, solved-variable, and selected-site objectives all equal
`15982050739`; floating HPWL differs by `0.000011375007`, inside the declared
rounding allowance. The local result, placement, certification result, and
certified placement SHA-256 values are:

- `a0bbb77b378ce81945294a9cdb3f92021a344f8500bd91df808c57d65fa663b7`;
- `e21d5559efddbb8376b9aedcd4d94829cbf6c50d5a4a14213e546fa10c7d60b5`;
- `8bb158a032d6ee112768b4cc6de1aef766be52a9190b5c0b61aebe46fba75e23`;
- `e21d5559efddbb8376b9aedcd4d94829cbf6c50d5a4a14213e546fa10c7d60b5`.

## Finding And Next Action

The remaining necessary HPWL gap is `721.681156`. Neither one- nor
two-component improving moves can close it; progress now requires at least a
three-component coupled move, a temporary non-improving transition, or a
larger exact regional solve. Under identical `EMI601` endpoint semantics, the
quality guide replays exactly at `14700.901479`. Its ten largest per-net gaps
identify a 20-component regional neighborhood spanning page 7, page 86, and
the `R604`/`R605` pair. Optimize that neighborhood next, then certify and run
local descent. This local optimum is not evidence of global infeasibility.
