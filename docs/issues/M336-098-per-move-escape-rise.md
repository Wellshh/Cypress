# M336-098: One Large Escape Move Consumes the Path Envelope

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `b430015`

## Problem

The guided escape had one hard HPWL envelope relative to its source but no
limit on an individual move. In the seeded M336-096 portfolio, several paths
accepted `C8612` with HPWL delta `+66.994415`. A nominal `+100` long-path
budget could therefore be consumed mostly by one component before other
low-cost legal moves changed the blocker topology.

This is distinct from the total envelope. Reducing the total budget to 20
also rejects the large jump, but prevents a long sequence of individually
small moves whose cumulative rise exceeds 20.

## Mitigation

`greedy_exact_site_descent.py` now accepts optional
`--max-escape-move-rise <HPWL>`. A candidate must satisfy both:

- total HPWL no greater than source plus `--escape-hpwl-budget`;
- candidate HPWL no greater than current HPWL plus the per-move limit.

Downhill and plateau moves remain admissible. Omitting the option preserves
the prior unbounded per-move behavior. Both limits and each accepted move
delta are recorded, while feasible-domain membership, exact collision tests,
and PlaceDB objective replay remain unchanged.

## Verification

`py_compile` passes and the M336 suite remains 58/58. A selector regression
uses current HPWL 10.0 and total ceiling 11.0: a guided `+0.5` move is rejected
when the per-move limit is 0.4 and deterministically accepted when it is 0.5.
Existing calls that omit the limit retain their prior result.

## Board Effect

A 16-run board portfolio retained the M336-096 `+100`, 10-sweep configuration
and seeds 1000-1007 while testing per-move limits 5 and 10. Every official
result returned to the certified source at HPWL `15811.06557381333` with
100/100 containment, zero violations, and zero overlaps. The escape phase
nevertheless produced 13 distinct placements:

- limit 5: 34-37 moves and endpoint HPWL `15836.887714695178` to
  `15838.887499904835`;
- limit 10: 36-45 moves and endpoint HPWL `15854.167147462149` to
  `15867.66521434906`.

Exact pair closure returned 12 distinct endpoints to the source. Limit 10,
seed 1003 instead reached a second exact-legal basin at HPWL
`15814.564714651957`, only `3.499140838627` above the source. Independent
all-fixed certification was `OPTIMAL`, with result SHA-256
`d921d6539ade34bd64c878a19b72b5b916be6b59e7dfc7119eb080d55dcf72ad`
and placement SHA-256
`403dc96e38b426504e72167cc48c99bde60e3e54d135fc261c917997ee22d584`.

The mitigation therefore improves reproducible topology diversity, not the
accepted score. The certified source remains the incumbent and the alternate
placement is guide-only evidence.
