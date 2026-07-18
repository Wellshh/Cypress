# M336-022: Local Restored-Anchor Domain Is Infeasible

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `4e1e21a`

## Problem

The restored manual-baseline endpoints for `EMI601` and `Q601` create seven
exact overlaps in the known legal `0.05 mm` runtime-anchor skeleton. Opening
alternate regions for the five nearby BOTTOM subgroups and allowing every
controlled component to move did not produce a legal repair in neighborhoods
centered on that skeleton.

## Evidence

Both runs used exact decomposed footprints, subgroup capacities, all 100
controlled components, score threshold `0.1`, eight workers, seed 1000, and
first-feasible search.

| Per component-region limit | 1,024 | 4,096 |
| --- | ---: | ---: |
| Assignment options | 40 | 40 |
| Retained sites | 143,409 | 499,857 |
| Encoded / skipped component pairs | 390 / 1,937 | 553 / 1,774 |
| Convex-part pair constraints | 8,099 | 9,139 |
| Status | `INFEASIBLE` | `INFEASIBLE` |
| Branches / conflicts | 0 / 0 | 1,167,515 / 79,613 |
| Solver wall time | `18.653983 s` | `157.447106 s` |

The 4,096 run required `234.04 s` end to end and peaked at 5,724,408 KiB RSS.
For comparison, the earlier all-subgroup 4,096 model retained 784,707 sites
and remained `UNKNOWN` after 302 seconds with zero branches. Assignment scoping
therefore changes an inconclusive run into a local infeasibility proof, but
does not solve the packing problem.

## Interpretation

This result proves only the encoded domains are infeasible. It does not prove
that the full `0.05 mm` lattice, another subgroup-region combination, or a
neighborhood around a different guide is infeasible. Increasing a single
hint-centered limit further is not practical with the current table encoding:
memory is already 5.72 GB and candidate growth is approximately linear.

## Required Improvement

- Identify additional subgroup-region choices from the collision and capacity
  structure rather than opening all 61 options blindly.
- Preserve multiple meaningful site centers, including known legal coordinates,
  instead of spending the entire candidate budget around one hint.
- If broader domains remain necessary, replace site enumeration with a compact
  coordinate-domain or hierarchical packing model.
- Replay any discovered candidate with one worker, fixed sites, exact geometry,
  and native HPWL/RSMT before acceptance.

## Acceptance Criteria

- Full containment and zero exact overlaps with the restored anchor contract.
- Deterministic fixed replay reproduces assignment and coordinates.
- Native normalized HPWL/RSMT score is at least the manual baseline score 1.0.
