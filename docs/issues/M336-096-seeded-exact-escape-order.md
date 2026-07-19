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
- the NumPy version;
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

A real-board one-sweep integration records seed 1000, generator PCG64, NumPy
`2.4.3`, and one 100-refdes order in both result artifacts. It accepts 18
exact-legal plateau moves before the official result restores the source.
Final and escape placement SHA-256 values are respectively
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`
and `189df99d1cbdbfc902bfada76c502b4698ef5728e0abae96b9836dd98fdb3af6`.

## Real-Board Portfolio

The first real-board portfolio used source HPWL `15811.06557381333`, the
collision-relaxed quality guide, a `+100` HPWL envelope, at most 10 escape
sweeps, no pair moves, NumPy `2.4.3`, and seeds 1000-1007.

| Seed | Sweeps | Moves | Strict / plateau / uphill | Peak rise | Escaped HPWL | Result SHA-256 |
| ---: | ---: | ---: | --- | ---: | ---: | --- |
| 1000 | 3 | 35 | 0 / 23 / 12 | 98.115224 | 15909.180798 | `21d2471dad75103dafc3825c854a47f25ce3a840d34da58fe1134ee5470b05d5` |
| 1001 | 4 | 39 | 0 / 24 / 15 | 88.965139 | 15900.030712 | `eb9d619d60ed6528027368fcad2023d9afbd36127ee5d658246fbf309937b768` |
| 1002 | 3 | 36 | 0 / 23 / 13 | 92.115869 | 15903.181443 | `09be1a267707a590c2ee8459a49e01e810fb3d17cfd6ed9de259b6a2060f9bbc` |
| 1003 | 5 | 52 | 6 / 26 / 20 | 91.444185 | 15896.510403 | `f1a534944b549f13f7fc261cb6c84dd4fa850c9541a7053a33e5cec124d93893` |
| 1004 | 4 | 49 | 3 / 26 / 20 | 90.516814 | 15899.582603 | `765c9655d9615b63a396edce829f7735f4ba7228b6fddce47ecf5a3f21acd733` |
| 1005 | 4 | 37 | 0 / 24 / 13 | 98.116084 | 15909.181657 | `4d4168670703e5394684f4f4d667cd35f268f1c82418d3421db4d1ea0be27375` |
| 1006 | 3 | 37 | 0 / 24 / 13 | 98.115224 | 15909.180798 | `ce30735062580ef10790e457a1ae1d61c009a6a1c6480b1bdbfbef566b2e1ba6` |
| 1007 | 4 | 42 | 1 / 24 / 17 | 99.746719 | 15880.463023 | `6e387fce4f8916b2ad4e871f5eb67c1aef8dfe694e4ab98db74833045ea6fbb4` |

Every path stopped as `no_guided_candidate`; none improved the source after
ordinary exact one-site closure. All official results therefore restored the
source and reproduce its placement SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`.
Final reports remain 100/100 contained with zero keep-in violations and zero
overlaps.

The lowest escaped endpoint, seed 1007, was independently fixed-site
certified `OPTIMAL` at HPWL `15880.46302321452`; objective replay passes and
its placement SHA-256 is
`1653c7965a7f2da7e402fcdc38426ffd08249030d6e880961d9f68ce70356ecd`.
It remains a worse search guide, not an incumbent. Certification result
SHA-256 is
`2de0287ae45d474f55e15065ab96a28538974591fb1266dd39f69086046adc7b`.

An independent seed-1000 repeat produced identical sweep orders, move path,
HPWL fields, exact legality, and selected sites after removing only output
path and elapsed-time fields. Original and repeat official placements both
hash to the certified source; both escape placements hash to
`5c77764ae4820e6d796403dd46538f29dbe839b2f3f1ddfdc8cc7f4c77d6ccba`.
This validates deterministic replay while showing that order diversity alone
does not close the score gap.
