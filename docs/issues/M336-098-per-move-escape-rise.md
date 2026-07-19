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

The first board experiment will retain the M336-096 `+100`, 10-sweep,
seeded-order configuration while setting the new per-move limit to 5. Any
strict result must still pass independent all-fixed certification; a diverse
worse escape endpoint remains guide-only evidence.
