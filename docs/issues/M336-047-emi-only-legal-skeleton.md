# M336-047: EMI-Only Override Preserves a Legal Skeleton

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `bfac477`

## Problem

Continuous bounds show that restoring either `EMI601` or `Q601` to its manual
coordinate can restore score potential above 1.0. Subsequent packing work
selected `Q601`. That choice invalidates 12 sites in the known legal TOP
placement and forces near-global repacking; the simpler `EMI601`-only contract
had not been tested end to end.

## Exact Replay

The legal runtime TOP placement was combined with the restored-anchor legal
BOTTOM placement. Fixed endpoints then used manual `EMI601` and runtime
`Q601`. All 30 TOP components were fixed to their nearest K64 guide site; every
guide displacement was exactly zero.

| Metric | Result |
| --- | ---: |
| CP-SAT status | `OPTIMAL` |
| Exact containment | 100/100 |
| Keep-in violations / overlaps | 0 / 0 |
| HPWL | 21,493.113773 |
| Normalized HPWL/RSMT upper bound | 0.710012 |
| Deterministic time / branches / conflicts | 0.256175 / 2,780 / 0 |

The model audited 1,331,200 rectangle candidate pairs with zero false
positives and zero false negatives, and encoded 37,754 exact nonrectangle
conflicts. Two independent runs reproduced selected-site SHA-256
`1960148f87e57be5b068939d4d880aba6a831e5c21543b0be2de6bdd09749b52`
and identical legality, HPWL, deterministic time, and branch count.

## EMI-Only Quality Guide

A one-worker, 300 deterministic-time assignment/site optimization on the 0.1
mm lattice omitted collisions but retained shared coordinates, exact keep-in
sites, and the necessary score gate. It found HPWL `14700.901479` and a
normalized score upper bound of `1.038057`. This proves discrete quality
potential remains, but the guide has 383 exact overlaps: 112 TOP and 271
BOTTOM. Its result SHA-256 is
`64634cd629a516a2efc7c47e8beb5cd9443f83caed4eb3b3671269f71b506081`.

Using its TOP coordinates as the exact-site guide gives a sharp domain
boundary:

| Domain | Candidates | Status | Solve time | Branches |
| --- | ---: | --- | ---: | ---: |
| K256 | 7,493 | `INFEASIBLE` | 11.239 s | 102,409 |
| K512 | 14,917 | `OPTIMAL` | 33.731 s | 155,219 |

The K512 result is a full-board exact legal placement when merged with the
existing legal BOTTOM result: 100/100 containment, zero keep-in violations,
and zero overlaps. It audits 79,526,400 rectangle candidate pairs with zero
classification errors and encodes 1,834,266 exact nonrectangle conflicts.
Selected-site SHA-256 is
`9776d88420f73b1693b0d0f5f213cc3152e6c146382cc75781c273cbe8f433b8`.

This is a large feasibility improvement over restored Q601, whose score-guide
K512 domain is exactly infeasible. However, retaining the old low-quality
BOTTOM placement yields HPWL `21228.741381` and score upper bound `0.718854`.
The TOP closure therefore does not pass the quality gate by itself.

## Implementation

`probe_exact_site_cpsat.py` now accepts
`M336_MANUAL_BASELINE_ENDPOINTS=EMI601`; the default remains `Q601` for
historical experiment compatibility. The selected endpoint list is included
in every result.

## Acceptance Impact

This removes the restored-Q601 packing blocker and provides a deterministic
legal warm start plus an exact high-quality TOP packing, but the combined score
is far below the manual baseline. It is not an accepted result. Repack BOTTOM
around the EMI-only quality guide, merge both exact sides, then run native
HPWL/RSMT replay. Acceptance still requires exact zero-overlap legality and
normalized score `>= 1.0`.
