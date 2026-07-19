# M336-101: Candidate Guides Did Not Direct Regular Search

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `2c7e765`
**Fixed commit:** `1010cb1`

## Problem

M336-097 showed that one complete CP-SAT hint cannot both preserve the current
incumbent and encode a worse escape topology. Candidate guides select and
order domain values but, under automatic search, do not require regular search
to branch toward those values. Alternate-first 80- and 89-component K256
portfolios therefore retained the incumbent without testing a declared
guide-first branching policy.

## Implementation

`probe_exact_site_cpsat.py` now accepts `M336_SEARCH_BRANCHING`:

- `automatic` preserves the prior default;
- `partial_fixed_guide_delta` combines user-first site decisions with CP-SAT's
  default SAT fallback and restart policy;
- `fixed_guide_delta` uses the fixed-search chain and SAT fallback without
  default restarts.

Guided modes include every multi-site `site_var`. Components are ordered by
decreasing center distance between candidate guide 0 and the fixed hint, with
lexical tie-breaking. `CHOOSE_FIRST` and `SELECT_MIN_VALUE` then visit the
primary guide's earliest candidates first. The complete current hint remains
separate and is attempted before regular search. Results record the exact mode,
component order, guide deltas, candidate counts, and decision heuristics.

This differs from rejected M336-036: that experiment used eight workers and a
partial coordinate strategy ordered only four nonrectangles by collision
degree. The new experiment uses one worker, site variables, physical guide
deltas, a complete incumbent hint, and both partial/fixed controlled modes.

## Verification

`py_compile`, `git diff --check`, and all 62 M336 tests pass. Real-board K8
smokes with only `B402` movable and current included as a second candidate
guide returned `OPTIMAL` for both guided modes at the current HPWL. Objective
replay passed with 100/100 containment, zero violations, and zero overlaps.
An intentionally incomplete primary-only K8 smoke was correctly `INFEASIBLE`
inside that restricted domain; it is not used as a board feasibility claim.

## Controlled Experiment

The required A/B used the same 89-component support-closed K256 model for all
three modes. It used one worker, seeds 1000--1003, 300 deterministic seconds,
the certified current placement as a separate hint, integer HPWL ceiling
`15811065584`, and alternate/current/quality guide weights `4:1:2`. Candidate
guide 0 passed the required-support gate. Every result passed objective replay
and exact validation with 100/100 containment, zero keep-in violations, and
zero overlaps.

| Mode | Seed | Status | HPWL | Best bound | Branches | Conflicts | Wall s |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| automatic | 1000 | FEASIBLE | 15811.065574 | 14703.824099 | 2106949 | 471875 | 419.0 |
| automatic | 1001 | FEASIBLE | 15811.065574 | 14676.007241 | 2100703 | 451134 | 438.3 |
| automatic | 1002 | FEASIBLE | 15811.065574 | 14703.824099 | 2136459 | 456690 | 427.4 |
| automatic | 1003 | FEASIBLE | 15811.065574 | 14703.323669 | 2470575 | 588739 | 460.1 |
| partial-fixed | 1000 | FEASIBLE | 15811.065574 | 14667.827965 | 2067857 | 674678 | 332.7 |
| partial-fixed | 1001 | FEASIBLE | 15811.065574 | 14667.827965 | 2192208 | 702001 | 334.5 |
| partial-fixed | 1002 | FEASIBLE | 15811.065574 | 14667.827965 | 2040512 | 618289 | 333.6 |
| partial-fixed | 1003 | FEASIBLE | 15811.065574 | 14667.827965 | 1579294 | 703492 | 349.7 |
| fixed | 1000 | FEASIBLE | 15811.065574 | 14667.827965 | 1737267 | 1139977 | 422.2 |
| fixed | 1001 | FEASIBLE | 15811.065574 | 14667.827965 | 1858467 | 1207874 | 413.0 |
| fixed | 1002 | FEASIBLE | 15811.065574 | 14667.827965 | 1896298 | 1359339 | 408.9 |
| fixed | 1003 | FEASIBLE | 15811.065574 | 14667.827965 | 1881523 | 1146810 | 422.6 |

All 12 placements have SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`,
identical to the certified incumbent. The guided modes therefore changed the
search trajectory and produced a lower, seed-stable restricted-domain bound,
but did not produce a better feasible placement. The bound is not a global
board bound and is not a score; no new incumbent was sent to certification.

## Resolution

The missing controlled branching mechanism is implemented, serialized, tested,
and evaluated against automatic search. The score gap remains open elsewhere,
but M336-101 is resolved because candidate-guide direction can now be selected
without replacing the independently preserved incumbent hint.
