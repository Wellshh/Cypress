# M336-134: Two No-Goods Reveal A Third Rank-11 d6 Topology

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `ddd7a79`

## Search Contract

The M336-131 and M336-133 rank-11 site tuples were both excluded from the
unchanged M336-122 `d=6,Delta=20` model. M336-130 d6 remained the independent
feasible hint. Source, diversity reference, assignment, five weighted guides,
18-component support, K4096 allocation, 73,810 candidates, integer HPWL
ceiling, seed 8408, one worker, and all solver budgets were unchanged.

Both excluded certificates mapped at zero maximum site distance. Diversity
replay recorded two excluded tuples, no matched tuple, exactly six changed
sites, and a passed no-good audit.

## Third Rank-11 Optimum

The model returned `OPTIMAL` after 25.158 solver wall seconds and 14.329
deterministic-time units. Objective and bound are both rank 11. The topology
has HPWL `15650.448759010082` and changes:

```text
C703,FV707,FV708,FV710,R707,R708
```

The three known rank-11 optima share `C703,FV707,FV708,R707` and select each
two-element combination of `FV705,FV710,R708`:

| Topology | Additional endpoints | HPWL | Rank |
| --- | --- | ---: | ---: |
| M336-131 | `FV705,FV710` | 15649.948866 | 11 |
| M336-133 | `FV705,R708` | 15651.948652 | 11 |
| M336-134 | `FV710,R708` | 15650.448759 | 11 |

The raw result and placement SHA-256 values are respectively:

- `5a5b7d2d67bb942c27ec7f3e1a0aa17b56598fd071cd031f759ef02478978cdf`;
- `b8b1b9842257118fdf49b68bb0b6c277bca29d64c7bdc27f446a063735e48e62`.

Guide-rank, diversity/no-good, candidate-coordinate, HPWL envelope, per-net,
and exact legality replays pass. The solution is 100/100 contained with zero
keep-in violations and zero overlaps.

## Certification And Portability

An independent all-fixed K1 replay returned `OPTIMAL` with 100 candidates,
zero hint distance, and objective and bound `15650448765`. Objective, per-net,
candidate-collision equivalence, and exact legality audits pass. The portable
entry point is
`experiments/m336/guides/M336-134/d6-rank11-nogood2/certificate.json`.
Starting only from that tracked entry point and assignment while the process
working directory was `/tmp` produced a second `OPTIMAL` K1 replay with the
same integer objective and byte-identical placement. This confirms that the
artifact does not depend on the original temporary search-result chain.

| Artifact | SHA-256 |
| --- | --- |
| Portable certificate | `8d45037a8976944b3b08f18865c8d97b223f54c05b61a29a89880a3462f91359` |
| Original K1 certificate | `706a254c1447c68c672f8c40115b345e48ab4a7c9c79042803eb7762b53920b6` |
| Placement | `b8b1b9842257118fdf49b68bb0b6c277bca29d64c7bdc27f446a063735e48e62` |
| Assignment | `e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87` |
| Manifest | `71fbb1138e5a87e92d4e797150f5b83a9372c3e93b889e353b919fe9e41fc823` |
| Canonical selected sites | `6a673122fe8fa17a1d557b18f111eeb6eb4a54e671c933f8274a87a218e46c9d` |

## Closure And Hash Memoization

Full one-opt accepted four moves and reduced HPWL by `3.999570419310` to
`15646.449188590772`. The resulting placement SHA-256 is
`47e65c62fe82959c717235152fb5244355a530c805a1847ad17cd976c32cc97c`,
byte-identical to the M336-131 and M336-133 one-opt states.

M336-133 independently scanned all 2,874 component pairs and 103,003,718 site
combinations from these exact bytes. That scan reaches the M336-129 equal-HPWL
swap plateau at `15634.450477332834`, placement SHA-256
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`.
The pair scan was not repeated for M336-134 because its complete input
placement is byte-identical, not merely equal in HPWL. This memoization is
invalid whenever the placement bytes, candidate-domain contract, or closure
implementation changes.

## Interpretation And Next Action

Rank 11 contains at least three exact d6 tuples, and all three map through
one-opt to one identical state. This strengthens the many-to-one basin result
but does not prove the rank layer exhausted. M336-118 remains the only scoring
incumbent.

Add M336-131, M336-133, and M336-134 as exact no-goods and enumerate once more
with the M336-130 d6 hint. If another rank-11 topology maps to the known
one-opt SHA, reuse the certified pair closure by exact hash. In parallel,
prioritize residual-specific candidate coverage and physical-support expansion
rather than seed, weight, or runtime ladders.
