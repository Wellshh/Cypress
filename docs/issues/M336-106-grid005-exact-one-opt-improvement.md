# M336-106: 0.05 mm One-Opt Unlocks A Certified Improvement

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `08cc2a1`

## Problem

The prior incumbent was an exact one/two-optimum only on the 0.10 mm lattice.
That proof does not cover the interleaved 0.05 mm sites. M336-105 established
that the current EMI601 endpoint policy replays exactly on the finer lattice,
so sub-grid local descent could be evaluated without changing legality or
endpoint semantics.

## Search

`greedy_exact_site_descent.py` enumerated all 532,193 obstacle-free feasible
sites for the fixed assignment at 0.05 mm. It used no quality/plateau guide and
accepted only strict PlaceDB HPWL decreases after exact same-side collision
checks. Pair moves were disabled for this phase.

Six sweeps accepted 61 moves and stopped at `one_optimum`. The three largest
individual reductions were `C8614` (`-27.996993`), `B402` (`-26.791432`), and
`C8609` (`-17.378243`). Many additional moves use one model-unit offsets that
the 0.10 mm lattice cannot represent.

## Certified Improvement

HPWL decreased from `15811.065573813308` to `15673.623256994915`, an
improvement of `137.442316818393`. The normalized score upper bound increased
from `0.9651702157924906` to `0.9736338127800888`. Exact validation reports
100/100 containment, zero keep-in violations, and zero overlaps.

An independent all-fixed K1 CP-SAT replay returned `OPTIMAL` at `1e-8`
deterministic time with 100 single-site domains. Response, modeled, and
selected-site integer HPWL all equal `15673623264`; floating replay differs by
only `0.000007005085`. The one-opt result, one-opt placement, certification
result, and certified placement SHA-256 values are:

- `906372a88a34e04e61e56d7e5f36eaccbd854e1008976bb624a73d99ac2240f1`;
- `c4495b612a9367acc786653e5c8a35a955e88005913454edf1f8c7e11bb81508`;
- `b8149c048c1fa5319ae16dc6e4965fb6aef671bb7e4229b0870e028cd1dd73f6`;
- `c4495b612a9367acc786653e5c8a35a955e88005913454edf1f8c7e11bb81508`.

## Remaining Boundary

Passing score 1.0 still requires HPWL at most `15260.369571786632`; the new
necessary gap is `413.253685208283`. Native RSMT scoring remains gated because
HPWL alone cannot yet pass. Use this certified state as the new source, run
exact two-component closure on the 0.05 mm domains, and certify every further
strict improvement before scoring.
