# M336-140: Direct DATA2 Span Optimization Proves A Finite-Domain Plateau

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `ea3bd0f`

## Problem

M336-139 proved that the collision-relaxed `PSIM2_DATA2` targets for `FV710`
and `R708` are exact keep-in lattice sites but overlap frozen `MIC401`. Candidate
weighting cannot recover those coordinates. The exact-site probe therefore
needed to optimize a legal target-net span without conflating that objective
with the global HPWL safety envelope.

## Safeguard Implemented

`M336_OPTIMIZE_NET_SPANS=PSIM2_DATA2` adds a default-off objective mode. Net
names must be unique and resolve to one PlaceDB net. The mode is mutually
exclusive with HPWL and guide-rank objectives and requires an explicit
`M336_INTEGER_HPWL_CEILING`. All global net spans remain modeled for the hard
ceiling. Replay independently compares:

- the solver response against the named-net span expression;
- selected-site and variable target-span totals;
- selected-site and variable global HPWL totals;
- per-net spans, candidate coordinates, floating HPWL, and the ceiling.

Checkpoint export and scoring now fail closed when a target-net result lacks a
passing objective replay audit.

## Search Contract

The first direct solve used M336-118 as source, assignment, and hint; M336-118,
the M336-130 DATA2 coordinate target, and its certified legal family as guides
weighted `2,1,1`. The 20-component page-7/blocker support was retained. Base
allocation was K512, with `B402,FV710,R708` expanded to K4096, for 21,072 total
candidates. `MIC401` remained frozen. The global ceiling was M336-118 plus 20
(`15654450483`), with exact BOTH-side collisions, 0.05 mm sites, one worker,
seed 8408, 120 wall seconds, and 100 deterministic-time units.

The solve was `OPTIMAL` in 12.110 deterministic-time units:

| Metric | M336-118 | Direct DATA2 topology |
| --- | ---: | ---: |
| DATA2 integer span | 272367284 | 260868573 |
| Floating HPWL | 15634.450477 | 15654.448329 |
| Global integer HPWL | 15634450483 | 15654448336 |

The target span improved by `11.498711`, while global HPWL rose by
`19.997852`. The exact legal topology changes
`C703,FV707,FV708,FV710,R708`. All target/global objective, per-net,
coordinate, ceiling, and exact-legality audits passed.

## Certification And Portability

An independent all-fixed K1 solve returned `OPTIMAL`, with objective and bound
`15654448336`, 100/100 containment, zero keep-in violations, zero overlaps,
and complete replay. A second K1 launch from `/tmp` using only the portable
certificate and assignment produced byte-identical placement.

| Artifact | SHA-256 |
| --- | --- |
| Portable certificate | `9005ff16fddafa29d861581afec40860398a48b79aa1a43fa2676a3d1e5ff621` |
| Original K1 certificate | `75303ad172c4c5c8c7f8738c8d3d13400c604febac5d01adc5d85d26d816bb6f` |
| Direct result / quality guide | `b9398505dab1076520ef2170dfe2b3d740fbc4cb1658e7f128a777f7550be844` |
| Placement | `884c0d2973454418e60cb8a36176697cd112a1fd7548ea1d809e577c7c261c96` |
| Manifest | `2532f90622602856954d84c9226b9d35794e05bcf940075d0bc71a6ac0343585` |
| Canonical selected sites | `7923c8b0622f5fd0ee083e8b454b0eab4e6e0b51f95197dc51c3a6cde9c622b2` |

The portable entry point is
`experiments/m336/guides/M336-140/data2-direct-d20/certificate.json`.

## Independent Closure

Full one-opt accepted `FV707` and `FV708` moves and reached a new one-optimum
at HPWL `15642.94961817146`, placement SHA
`06e4717f60d03de6c50db8421cc38b61bf03c46f0b50ecaf20e5d81816b819f9`.
A complete pair scan then evaluated 2,892 component pairs and 130,718,237 site
combinations in 117.200 seconds. Moving `FV710/R708` recovered HPWL
`15634.450477332834`, but the resulting placement SHA is exactly the existing
M336-129 swap plateau:
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`.

A separate CP-SAT Solve B replaced the third candidate guide with the portable
M336-140 topology, used that topology only as the independent hint, restored
the global HPWL objective, and imposed the M336-118 integer hard ceiling. The
same 20-component K512/K4096 allocation had 21,072 candidates. It proved
`OPTIMAL` after 44.117 deterministic-time units, with objective and bound both
`15634450483`. This is a rigorous proof that this declared finite candidate
domain has no strict HPWL improvement; it does not apply to other guides,
allocations, or support.

The CP-SAT optimum is a third equal-HPWL plateau, distinct from both M336-118
and M336-129. It swaps `C703/FV707` and `FV703/FV704`; placement SHA-256 is
`279005fe88212da93942307d6733b24d5b3a2c7b0969fe4948b96287beae09b6`.
An all-fixed K1 solve and a portable replay from `/tmp` both reproduced the
same integer objective and placement bytes. Its portable entry point is
`experiments/m336/guides/M336-140/data2-cpsat-plateau/certificate.json`.

| Plateau artifact | SHA-256 |
| --- | --- |
| Portable certificate | `77f29067fcc2dfc7c1aeabbc9d9c6ca1f5ab7b340072da14ac7b697ef78b67a9` |
| Original K1 certificate | `918aeea112397bcef1e30cf3ff5c044fc577cf74fee463e0910cc29457750493` |
| CP-SAT closure result | `42bfc7a75f955acc8fa15c9a93d91c3adc50fc5e151b7d97d0965ebb55b1d0ef` |
| Manifest | `8a3bcca58ca32262c475a6bee32b81c39dccf46f63218feacde9f8207d3e091a` |
| Canonical selected sites | `7a9c937299874b4b8d46b152aea9e4efa293e2fb5dac3ace439e9537ebf8a303` |

## Decision Boundary

Direct residual optimization is operational and produces a topology outside
the previous one-opt closure state, but this first DATA2 topology does not
improve the scoring incumbent after either closure path. M336-118 remains the
incumbent. The CP-SAT result closes only its declared finite candidate domain;
it does not prove that expanded support or another portfolio cannot improve.
Do not repeat seed, weight, or runtime ladders for this same model. Continue P2
by directly optimizing the other residual nets and combining certified legal
families; revisit DATA2 only with an exact no-good or materially expanded
physical support. Preserve the new plateau as a no-good/candidate guide.
