# M336-101: Candidate Guides Did Not Direct Regular Search

**Severity:** High
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `2c7e765`

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

## Required Experiment

Compare automatic, partial-fixed, and fixed guide-delta modes on an identical
support-closed exact model. Retain one worker, current hint, incumbent ceiling,
seed, deterministic budget, guide weights, and K value. Independently certify
any strict improvement; report `UNKNOWN` without converting it to infeasible.
