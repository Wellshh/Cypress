# M336-066: Staged Page-86 Search Is Budget-Limited And Score-Insufficient

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `7d126e5`

## Problem

The corrected 80-component residual boundary was too broad for one K128
search. To isolate search complexity, the 38 newly added page-86 and `Q601`
components were released while the prior 42-component legal closure and all
other controlled components remained fixed. This staged model must determine
whether the new boundary can first improve the certified incumbent on its own.

## Reproduction

The solve used the certified HPWL `15835.344195928667` placement as source and
hint, manual/current/collision-relaxed-quality candidate guides, K256 candidate
limiting, exact side-specific keep-in and overlap constraints, one worker,
seed 1000, repair off, and first-solution mode. The integer HPWL ceiling was
`15834344206` (`15834.344206`), 1.0 HPWL below the incumbent's audited integer
objective. Wall-clock and deterministic-time limits were 600 seconds and 300
units, respectively.

## Result

The 8,776-candidate model returned `UNKNOWN` without an incumbent:

- solver wall time: `441.100984` seconds;
- deterministic time: `300.000497`;
- conflicts: `852,642`;
- branches: `3,175,928`;
- valid HPWL lower bound: `15419.616316`;
- result SHA-256: `3c28278e107fdcc5c06442f0fa36550fa13e4f7709a0a0e0b7d502586fc2b389`.

Because no incumbent exists, placement legality and objective replay are
correctly absent. `UNKNOWN` does not prove that the requested 1.0-HPWL
improvement is infeasible.

## Finding

The valid lower bound is `159.246744` above the score-1 HPWL threshold
`15260.369572`. Consequently, this particular staged K256 candidate domain
cannot reach the manual-baseline score even at its optimum. It may still
improve the incumbent by as much as `415.727890` HPWL, so the result does not
justify fixing these components in a combined search.

## Next Action

Run deterministic optimization neighborhoods rather than another monolithic
hard-threshold search: solve the multi-component page-86 physical groups from
the feasible current hint, then combine any strict certified improvement with
the prior 42-component closure. Retain `UNKNOWN` as a budget-limited outcome
and certify every accepted placement through all-fixed objective replay and
the exact legality validator.
