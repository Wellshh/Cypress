# M336-070: Topology Refresh Unlocks A Second Page-6 Improvement

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `ff64add`

## Problem

M336-069 changed 11 sites in the bottom-0/page-7 closure. Physical-group
optima established before that change are stale because newly occupied and
released sites can alter collision blockers even when a group's netlist is
unchanged.

## Refreshed Neighborhoods

Four deterministic K1024 models refreshed page-4, combined page-6, and both
page-7 bottom groups from the M336-069 certified placement. Each used current
and quality guides, one worker, seed 1000, repair off, a feasible current hint,
and exact keep-in and overlap constraints. Page-4 and both page-7 groups
returned `OPTIMAL` at the source objective.

The combined ten-component page-6 neighborhood returned `OPTIMAL` after
4.544599 deterministic-time units. Six components (`C607`, `C608`, `C609`,
`C610`, `FV603`, and `R601`) changed sites. HPWL decreased by
`0.062506275659`, from `15820.626361766243` to `15820.563855490584`;
normalized score upper bound increased to `0.964590751074303`.

## Certification

The all-fixed replay returned `OPTIMAL` at `1e-8` deterministic-time with zero
conflicts and branches. Response, solved-variable, and selected-site
objectives all equal `15820563866`; floating replay differs by
`0.000010509417`. Exact validation reports 100/100 containment, zero keep-in
violations, and zero overlap pairs. The search result, placement,
certification result, and certified placement SHA-256 values are:

- `bda87ea4aa2ed476d7d124d320cdf76fbdc30a5af1d7bb1f9c8e8a5efad3ed50`;
- `1fbadce721fe0e27e47af23bb2819f3dd380584c20aa5db7a04b020f8f8721e0`;
- `9a5afd508849e241b082dc0346fc5f0acefdaa66373869091385d055ecd8f291`;
- `1fbadce721fe0e27e47af23bb2819f3dd380584c20aa5db7a04b020f8f8721e0`.

Full-domain local closure accepted no move after evaluating 2,894 pairs and
2,367,223 site combinations. It stopped at `two_optimum`; result SHA-256 is
`67c43f0fe3a6f6f26d879b7832549a265b16cc08167dad39b20c02690bbdac35`.
The remaining score-1 HPWL gap is `560.194283703952`.

## Finding And Next Action

Physical-group closure is topology-dependent and must be refreshed after every
regional change. The improvement is far above numerical replay tolerance and
is independently certified, so it is not tuning noise. Continue alternating
combined regional search and deterministic group refresh; do not reuse stale
group-optimality claims after any blocker in the shared side/region moves.
