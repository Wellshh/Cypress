# M336-061: Current-First Quality Domain Search Stalls

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `0e00c2d`

## Problem

The K256 regional search remained unresolved after removing manual-baseline
candidates and ordering every component domain from the current certified legal
placement first. The alternate quality guide is also misleadingly named
`m336_emi_only_grid01_no_collision.json`: exact validation reports 383 overlap
pairs with total area `32170.854629`. It is a collision-relaxed coordinate
guide, not a legal placement or acceptable score result.

## Controlled Experiment

The 42-component physical closure used 10,810 candidates, interleaving about
128 nearest sites from the current legal placement with 128 from the quality
guide. The current placement was hint index 0. Fifty-eight components remained
fixed. CP-SAT used one worker, seed 1000, repair disabled, first-solution mode,
and 300 deterministic seconds. The pure-feasibility ceiling was
`15830344206`, exactly 5.0 HPWL below the current integer value.

The run returned `UNKNOWN` without an incumbent after 362.875659 wall seconds
and 300.000953 deterministic seconds, with 703,903 conflicts and 1,056,162
branches. Result SHA-256 is
`b922b62ec66586bc7e05d7268d24190eb2e2e3e4c31ba15a820b8ab9062b2390`.

The matched three-guide run, which included manual-baseline candidates, also
returned `UNKNOWN`: 327.415580 wall seconds, 300.000092 deterministic seconds,
729,297 conflicts, and 1,288,806 branches. Its result SHA-256 is
`9e1ebc124db230104b840382345b4f703c614a1c62152768e64d4a4a06702f1b`.

## Interpretation

Candidate ordering alone does not explain the stall. The current placement is
an exact one- and two-component local optimum, so the remaining 574.974624
HPWL gap likely requires a coordinated move of at least three components or a
temporary worsening step. Neither run proves the restricted domain infeasible;
both exhausted a search budget and must remain `UNKNOWN`.

## Next Action

Do not repeat this model with only a new seed. Add a deterministic higher-order
neighborhood or bounded uphill/tabu phase that preserves exact keep-in and
collision checks at every accepted state. Certify every improved state with
the all-fixed CP-SAT replay audit before treating it as a new incumbent.

