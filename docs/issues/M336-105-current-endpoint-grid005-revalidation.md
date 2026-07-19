# M336-105: Current Endpoint Policy Needed 0.05 mm Revalidation

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `e71c95b`

## Problem

M336-010 through M336-014 rejected score 1.0 on a 0.05 mm lattice under the
original runtime freeze policy. M336-015 later showed that preserving EMI601
at its manual-baseline endpoint restores continuous score potential, and the
current certified placement uses that endpoint policy. Reusing the older
0.05 mm conclusion without replaying the current contract would therefore be
an invalid cross-policy inference.

## Revalidation

An all-fixed K1 exact CP-SAT smoke regenerated feasible domains at
`M336_GRID_MM=0.05` using the current fixed assignment, EMI601 manual endpoint,
and certified placement as source, guide, and separate hint. It returned
`OPTIMAL` with 100 single-site fixed domains. The maximum hint-to-site distance
was `5.91e-12`, and the emitted placement SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`
is byte-identical to the 0.10 mm incumbent.

Integer HPWL objective and bound are `15811065584`; per-net and floating replay
pass. Exact validation reports 100/100 containment, zero keep-in violations,
and zero overlaps. Result SHA-256 is
`2ffcc19ee4eec8b7497b4f859390415c476a98bba0fed87a87b78febc3a057a9`.

## Scope And Next Step

This proves lattice compatibility only; it does not improve HPWL and does not
contradict the older proof under a different endpoint policy. The current
certified state can now be used as a fail-closed 0.05 mm hint. Search first for
sub-grid improvements with exact collisions and the current HPWL ceiling, then
independently certify any strict result before native scoring.
