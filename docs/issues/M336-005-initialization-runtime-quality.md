# M336-005: Initialization Dominates Runtime and Loses Baseline Quality

**Severity:** High
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `b1f98f5` plus uncommitted baseline integration

## Problem

The baseline-aware E4 path is legal but its deterministic region packer spends
orders of magnitude longer than GPU optimization and relocates components far
enough to lose the manual board's routing quality.

## Evidence

A one-seed, one-iteration H100 smoke recorded:

| Stage or metric | Observed |
| --- | ---: |
| Feasible-domain construction | `7.674 s` |
| Non-linear initialization | `173.66 s` |
| Adam optimization | `0.528 s` |
| End-to-end E4 | `178.14 s` |
| Final keep-in violations / overlaps | `0 / 0` |
| HPWL / RSMT regression vs manual | `69.70% / 65.03%` |
| Normalized quality score | `0.5975` |

`BOTTOM/bottom_0` only succeeded at the late `largest_span/top_left` trial,
after repeated full candidate scans. Exact repair then moved all 100 constrained
components by about `0.139` Cypress units to remove one residual overlap.

## Impact

The `<=2x` runtime target and the manual score gate cannot pass. Short tuning
runs mostly measure Python geometry search, not CUDA placement quality.

## Update: Fast Rectangle Prefilter

Vectorized rectangle bounds and a baseline-preferred candidate pass reduced the
same one-seed E4 smoke from `178.14 s` to `30.021 s` (`83.1%` faster). The run
remained exact legal (`100/100` contained, zero overlaps), but HPWL/RSMT were
`23399.6484/24969.9570` and the normalized score was only `0.631877`.

Moving min-conflicts ahead of the directional greedy passes made the same run
exceed `210 s` without completing; it was terminated and the ordering was
reverted. This is a negative result: min-conflicts remains a bounded fallback,
not the default path. Candidate-limited forward checking is also explicitly
reported as heuristic exhaustion, never as a proof of packing infeasibility.

## Update: Preserved Warm Start and Cold Closure

The N4 warm seed-1000 10-step matrix now preserves all 100 M336-118 components
in `0.0180 s`. E4's bounded same-run restore takes `0.0628 s`; end-to-end E4 is
`13.8934 s` versus E0 `9.4035 s`, passing the applicable warm runtime gate at
`1.4775x` without destructive packing.

The float cold/source placement is structurally different: exact preflight
preserves only four constrained components and the illegal/conflict closure
contains the other 96. Initialization still takes `53.20–54.93 s`, compared
with `1.20–1.32 s` of GPU optimization. Cold E4 is exact legal but ends at
native HPWL/RSMT `19745.9814/21389.876` and score `0.743234`. This remains an
open cold-start performance and quality limitation; it is not the warm-cache
2x acceptance gate.

## Remediation

1. Profile each region/trial and cache candidate footprint conflict indices.
2. Use spatial indexing instead of scanning every occupied polygon per site.
3. Preserve already feasible baseline locations and optimize only illegal
   components; include incremental HPWL in initialization and repair cost.
4. Revisit fixed assignment where geometry proves the score gate infeasible.
5. Re-run E0-E4 for three seeds only after a single-seed quality gate passes.

## Acceptance Criteria

- Initialization timing is emitted per region and strategy.
- E4 is exact legal and no more than 2x E0 under equal inputs and iterations.
- HPWL and RSMT are each no worse than the manual reference for all final seeds.
- Repeated runs produce identical placements, strategy choices, and scores.
