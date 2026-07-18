# M336-003: Initial Matrix Misses Quality and Runtime Targets

**Severity:** High
**Status:** Open
**Found:** 2026-07-17
**Affected commit:** `d9e7674`

## Problem

The first three-seed, 5-iteration E0-E4 matrix establishes that exact repair can
produce a legal E4, but it does not meet all quantitative acceptance targets.
These are smoke-run results, not final claims, and must not be presented as a
successful experiment.

## Evidence

| Metric | Observed | Required |
| --- | ---: | ---: |
| E3 mean anchor reduction vs E2 | 15.50% | at least 25% |
| E3 p90 anchor reduction vs E2 | 14.03% | at least 15% |
| E4 runtime / E0 runtime | 5.97x | no more than 2x |
| E4 keep-in violations | 0 | 0 |
| E4 constrained overlaps | 0 | 0 |

Mean runtime was `4.52 s` for E0 and `26.95 s` for E4. E4 mean anchor distance
was `9.1923 mm`, while E2 was `10.8553 mm`. The E4 HPWL comparison is not valid
against the manual board; see M336-001.

## Likely Contributors

- Region capacity and narrow feasible domains constrain achievable anchor
  distance, so aggregate weight changes have little effect.
- Python geometric projection and greedy exact repair dominate a short run.
- Repair currently moves nodes even when a legal warm start may require no
  changes.
- Five iterations are sufficient for smoke testing but not a final convergence
  comparison.

## Remediation

1. Diagnose the worst side-specific groups and report capacity lower bounds.
2. Preserve an already exact-legal manual warm start and repair only violations.
3. Profile projection, exact validation, and repair independently.
4. Cache static feasible geometry and batch projection candidates.
5. Re-run the fixed matrix for all three seeds at the final iteration budget;
   keep smoke and final results in separate directories.

## Acceptance Criteria

- Mean and p90 anchor targets pass or have a per-group geometric infeasibility
  proof with an explicit acceptance decision.
- E4 overhead is at most 2x E0 under the same device, input hashes, and budget,
  or the target is explicitly revised by a human reviewer.
- Final metrics use the manual baseline gate from M336-001.
