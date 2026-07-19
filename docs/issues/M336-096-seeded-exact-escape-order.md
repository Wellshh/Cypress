# M336-096: Exact Escape Explored Only One Component Order

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `d92fa13`

## Problem

`greedy_exact_site_descent.py` visited constraints in one sorted refdes order
during every guided escape sweep. The search was deterministic, but its result
represented only that single greedy path. Once an early component occupied a
site, later components saw a different exact blocker topology; repeating more
sweeps or widening the HPWL budget did not remove this ordering bias.

The current certified placement has 3,493 legal non-current single-site moves
over all fixed-obstacle-free sites. Of these, 383 cost at most 1 HPWL, 490 cost
at most 5, 623 cost at most 10, and 932 cost at most 20. The page-7-directed
sorted escape in M336-095 nevertheless selected only `C703` and `FV707`.
Therefore that path cannot stand in for the broader exact-legal neighborhood.

## Mitigation

The descent CLI now accepts optional `--escape-order-seed <SEED>`. A seeded
run uses NumPy `default_rng` with PCG64 to sample one component permutation per
escape sweep. The result and pre-closure escape seed record:

- the non-negative seed;
- the generator contract `numpy.default_rng/PCG64`;
- every realized refdes order for exact replay.

Omitting the option preserves the original sorted order and consumes no random
numbers. Ordering is the only changed search input. Candidate sites remain in
the assigned feasible domain, every move must pass exact same-side collision
checks and PlaceDB HPWL replay, and the declared HPWL envelope remains hard.
Failed searches still restore the certified source rather than emitting a
worse acceptance candidate.

## Verification

`py_compile` passes for the changed script and test module. The M336 suite
passes 58/58, including tests that the default order is unchanged, equal seeds
produce equal multi-sweep orders, input ordering is not mutated, and a seeded
portfolio does not silently use the sorted path.

The first real-board portfolio uses source HPWL `15811.06557381333`, the
collision-relaxed quality guide, a `+100` HPWL envelope, 10 escape sweeps, and
seeds 1000-1007. Its runs are intentionally not reported in this change while
they are in progress. Any strict improvement requires independent all-fixed
CP-SAT certification before promotion; non-improving diversity is search
evidence only.
