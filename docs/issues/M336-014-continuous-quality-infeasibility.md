# M336-014: Current Placement Contract Cannot Match The Manual Baseline

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `ebc786e`

## Problem

`M336-012` proved that no assignment passes score `1.0` on the `0.05 mm`
lattice, but a finer lattice or continuous placement could still have passed.
A continuous MILP now removes that ambiguity while retaining the placement
contract shared by the E1-E4 experiments.

## Deterministic Evidence

The model selects one same-side region for each of 31 subgroups and one shared
continuous x/y coordinate for each of 100 controlled components. It uses all
63 bounding-box-feasible assignment options and the native weighted pin/net
topology. The declared 25 anchors and 15 fixed components remain at their
runtime-frozen positions.

The model is strictly more permissive than an accepted placement: it replaces
each physical keep-in with a bounding interval, permits x/y combinations
outside the polygon, and ignores component overlap, area capacity, grid
quantization, and RSMT beyond the necessary `RSMT >= HPWL` inequality.

| Quantity | Value |
| --- | ---: |
| HiGHS status | `Optimal` |
| MIP gap | `0.0` |
| Relaxed HPWL lower bound | `15693.073693435226` |
| Score-1 HPWL limit | `15260.369571786630` |
| HPWL excess | `432.704121648596` |
| Normalized score upper bound | `0.972427063677806` |

An independent reconstruction from solved component coordinates produced
`15693.073693435228`, differing from the MILP objective by about `2e-12`.
Two single-threaded executions produced byte-identical JSON with SHA-256
`f14b1c31a8b0bb59baf1401579d260d830ce32e28839619f4468aad9fb74e8fb`.
Input hashes are assignment
`bb69ec27cfe48a428428eaecda0dd33f4e29192594bee04dae743cc95798365c`,
manual placement
`65ea89cfae831871fd115f61b50e528bcc77a0285d85ecbf4c4a97ba898ad595`,
and baseline result
`df8096d78fd3bff60bc2ad179fb83eda276da4566aeda1feafae7ffa9418ae2f`.

## Impact

No CUDA kernel change, seed search, hyperparameter tuning, finer grid, packing
heuristic, or collision repair can satisfy the requested score under the
current sides, subgroup-region rule, and runtime-fixed endpoints. Continuing
E0-E4 tuning before changing one of those contract terms would waste compute
and could only produce misleading claims.

## Required Decision

Quantify the bound under controlled relaxations, starting with keeping frozen
endpoints at their manual-baseline coordinates. If that is insufficient,
separately relax subgroup co-location, region eligibility, side assignment,
and anchor mobility. Adopt the smallest domain-authorized change whose relaxed
bound reaches `1.0`, then rerun exact legality and native HPWL/RSMT gates.

Follow-up `M336-015` completed the first isolation step. Preserving either
`EMI601` or `Q601` at its manual coordinate restores continuous score
potential above `1.0`; no region, side, or subgroup relaxation is currently
justified.

## Acceptance Criteria

- A documented contract variant has a rigorously computed score potential of
  at least `1.0`.
- Exact validation reports `100/100` contained components and zero overlaps.
- Native normalized HPWL/RSMT score is at least the manual baseline (`1.0`).
