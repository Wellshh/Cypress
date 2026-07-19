# M336-104: Page-7 Guide Has A Monotonic Rank Barrier

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `e1f452a`

## Problem

M336-092 attributes `536.846685` of optimistic current-to-quality net residual
to page 7, but prior automatic K256 and page-7 K1024 searches retained the
current incumbent. It remained unclear whether an exact legal topology could
move monotonically toward the page-7 quality hybrid without HPWL regression.

## Method

The primary guide replaced the 18 page-7 BOTTOM members with quality-guide
coordinates; 17 coordinates actually differ from the incumbent. Current,
certified alternate plateau, and collision-relaxed quality guides completed a
`4:1:2:1` K256 candidate portfolio. The support-closed 89-component model used
the current placement as a separate hint, exact BOTH-side collisions, integer
HPWL ceiling `15811065584`, one worker, seeds 1000--1003, and automatic or
partial-fixed branching. Candidate guide rank was the only objective.

## Evidence

All eight runs returned `OPTIMAL` at rank and bound `68` in 10.54--11.22
deterministic seconds. Both replay audits and required guide support passed;
exact validation reports 100/100 containment, zero keep-in violations, and
zero overlaps. Every emitted placement has SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`,
byte-identical to the certified incumbent at HPWL `15811.06557381333` and
normalized score upper bound `0.9651702157924906`.

## Conclusion

Within this fixed 89-component K256 candidate domain, no solution satisfying
the current HPWL ceiling has page-7 guide rank below 68. Unlike M336-103, the
monotonic objective exposes no alternate non-regressing topology. This is a
restricted-domain rank proof, not a global HPWL or feasibility claim.

Next optimize HPWL with rank capped at 68 to close the minimum-rank layer. If
that layer is exact at the incumbent, stop this page-7 K256 route and change
the candidate lattice/domain rather than adding seeds.

## Rank-68 HPWL Closure

Automatic and partial-fixed HPWL solves at seed 1000 retained the identical
model and imposed rank at most 68. Both returned `OPTIMAL` with zero branches
and conflicts, HPWL objective and bound `15811.065584`, and the current
placement hash. Both replay audits and exact legality passed.

Thus, within this candidate domain, no strict HPWL improvement exists at rank
68 or below; any improving solution must have page-7 guide rank at least 69.
The result closes only the minimum-rank layer. Stop this K256 route and change
the candidate domain or 0.10 mm lattice before further page-7 search.
