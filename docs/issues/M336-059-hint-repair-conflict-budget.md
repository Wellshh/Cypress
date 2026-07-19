# M336-059: Hint Repair Conflict Limit Does Not Bound Repair Time

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `b68f0ee`

## Problem

`repair_hint=true` asks OR-Tools CP-SAT to minimize L1 distance from an
infeasible hint before regular search. The phase is limited by
`hint_conflict_limit`, but that is a conflict count, not a deterministic-time
or wall-time budget. A repair search that branches without conflicts can
consume the entire global budget and never reach normal objective search.

## Reproduction

The 42-component K256 physical closure started from certified integer HPWL
`15835344206` and imposed ceiling `15825344206`, requiring a 10-HPWL
improvement. It used one worker, seed 1000, `repair_hint=true`, a 10,000
conflict limit, stop-after-first mode, 300 deterministic-time, and 600 wall
seconds.

The 10,810-candidate model returned `UNKNOWN` after 481.970589 solver wall
seconds and 300.001092 deterministic-time:

- conflicts: 0;
- branches: 16,600;
- incumbent: none;
- valid lower bound: `14571.678022`;
- result SHA-256:
  `1d95ca3711364525e445ffd551ab043b9cbafc4ba4fdab1ce8849162c26206dc`.

The lower bound is below both the requested ceiling and score threshold. The
run therefore provides no infeasibility evidence. Its zero conflicts explain
why the 10,000-conflict repair cutoff never fired.

## Impact

Calling `hint_conflict_limit` a repair budget is misleading for reproducible
experiments. Two domain sizes can spend radically different fractions of the
same global deterministic-time in repair, even with identical limit, seed,
and worker count. This invalidates a naive comparison of repair-on incumbents.

## Required Action

Repeat the exact K256 ceiling model with `repair_hint=false` and the default
quick hint phase. Compare candidate count, ceiling, seed, worker count, status,
incumbent, conflicts, branches, and both time measures. Do not enable L1 repair
for production sweeps until it has a separately enforceable time budget or an
observed nonzero-conflict cutoff. Preserve `UNKNOWN` exactly.
