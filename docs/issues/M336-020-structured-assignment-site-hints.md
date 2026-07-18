# M336-020: Assignment Search Cannot Consume Site Hints

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `725e33f`

## Problem

`--optimize-assignment` originally rejected every external site hint. The
unseeded `0.05 mm` model contained 1,410,293 sites and remained `UNKNOWN` after
300 seconds without entering search. A `0.1 mm` run reduced the model to
348,066 sites and reached 1,467,138 branches, but still found no legal packing.

An integer site index alone is ambiguous when one component has candidate
sites in several regions. Reusing a region-local index as a concatenated model
index would silently hint the wrong coordinate or subgroup assignment.

## Correction

All internal site hints now carry both `region_id` and region-local
`site_index`. Result hints are accepted by optimized-assignment models only
after validating that:

- every region is eligible for the component's subgroup;
- all members of one subgroup hint the same region;
- every site index exists in that component-region domain; and
- exact hint reporting uses the hinted domains rather than the input assignment.

The subgroup assignment variable and concatenated site variable receive
consistent hints. When `--candidate-limit-per-region` is active, the hinted
region retains the exact site; every alternate region retains sites nearest to
the same physical hint coordinate. Thus alternate assignments remain possible.
Raw placement and generated packing hints still require a fixed assignment;
only result artifacts provide an explicit cross-region contract.

## Contract Smoke

A fixed replay used the restored-anchor skeleton result with all 61 region
options enabled and 128 candidates per component-region:

| Quantity | Value |
| --- | ---: |
| Total retained sites | 28,544 |
| Solver status | `OPTIMAL` |
| Workers / branches / conflicts | `1 / 0 / 0` |
| Solver wall time | `0.014011 s` |
| Exact overlaps | 7, matching the input hint |

The result hash is
`d13626e141a0c286e63355c4a2dcabd07d6262fee3e2028e8334303f8bc69183`;
the emitted assignment hash is
`4bf26cca05627056a6e660985dcbf33a5d078d83b057e627566c631d88be501e`.

## Residual Risk

A hint guides search but does not prove that its neighborhood contains a legal
or score-1 packing. Multi-worker discovery remains exploratory; any accepted
assignment and sites require fixed single-worker replay and exact validation.

## Acceptance Criteria

- Region-local indices cannot be interpreted without an explicit region.
- Split subgroup hints and ineligible regions fail before model construction.
- Alternate region candidates remain available under candidate limiting.
- Fixed optimized-assignment replay reproduces the hinted sites and regions.
