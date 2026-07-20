# M336-135: Three No-Goods Find A Fourth Rank-11 d6 Site Tuple

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `c3275b8`

## Search Contract

M336-131, M336-133, and M336-134 were added as three exact forbidden site
tuples to the unchanged M336-122 `d=6,Delta=20` model. M336-130 d6 remained the
independent feasible hint. Source, diversity reference, assignment, five
weighted guides, 18-component support, K4096 allocation, 73,810 candidates,
integer HPWL ceiling, seed 8408, one worker, and solver budgets were unchanged.

All three no-goods and the M336-118 diversity reference mapped at zero maximum
site distance. Replay reports exactly six changed sites, no matched excluded
tuple, and passed diversity, no-good, guide-rank, candidate-coordinate, HPWL
envelope, and per-net audits.

## Fourth Rank-11 Optimum

The model returned `OPTIMAL` after 24.632 solver wall seconds and 14.334
deterministic-time units. Objective and bound are both rank 11. The topology
has HPWL `15651.948651614910` and changes:

```text
C703,FV707,FV708,FV710,R707,R708
```

M336-134 and M336-135 therefore have the same changed-refdes support but
different exact sites:

| Topology | `FV710` site | `R708` site | HPWL | Placement SHA prefix |
| --- | ---: | ---: | ---: | --- |
| M336-134 | 3 | 1 | 15650.448759 | `b8b1b984` |
| M336-135 | 2 | 2 | 15651.948652 | `cb348282` |

M336-135 also has the same floating HPWL as M336-133 while its changed-refdes
set and placement bytes differ. Neither HPWL nor changed-refdes support is a
valid topology identity; enumeration must use the complete canonical site
tuple.

The raw result and placement SHA-256 values are respectively:

- `1f4559629fcc7ced55e82fc903bdfe92eae19196a5ced50fcd1a386d82d9a489`;
- `cb348282d008963449d0d1376dd114b800028e2af0a100153771b8a3a72f97ae`.

Exact legality is 100/100 containment with zero keep-in violations and zero
overlaps.

## Certification And Portability

An independent all-fixed K1 replay returned `OPTIMAL` with 100 candidates,
zero hint distance, and objective and bound `15651948656`. Objective, per-net,
candidate-collision equivalence, and exact legality audits pass. The portable
entry point is
`experiments/m336/guides/M336-135/d6-rank11-nogood3/certificate.json`.

A second K1 replay launched from `/tmp` using only the tracked portable
certificate and assignment returned the same integer objective and
byte-identical placement. The artifact is independent of the original
temporary search-result chain.

| Artifact | SHA-256 |
| --- | --- |
| Portable certificate | `1f24a02f1f2c22e5ab54d67cbab8df68dd5c696b7da61e700f12ba7d784cd8b8` |
| Original K1 certificate | `bd542bcdbc99877a647bd8a974d711ca70e1efee3c0df9e0b8e4a86a2868f137` |
| Placement | `cb348282d008963449d0d1376dd114b800028e2af0a100153771b8a3a72f97ae` |
| Assignment | `e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87` |
| Manifest | `21b6a398efb12fad42d9988d276881b3eb34e1035fcd04362a9f5a66f4a779fb` |
| Canonical selected sites | `5c78f070eb9679b71f8ad6b1a351fa85afd7afee9ec61c34a596588fecdd1c19` |

## Independent Closure

Full one-opt accepted four moves in two completed sweeps and reduced HPWL by
`5.499463024138` to `15646.449188590772`. Its placement SHA-256 is
`47e65c62fe82959c717235152fb5244355a530c805a1847ad17cd976c32cc97c`,
byte-identical to the M336-131, M336-133, and M336-134 one-opt states.

The M336-133 full pair scan from these exact bytes evaluates 2,874 component
pairs and 103,003,718 site combinations and reaches the M336-129 equal-HPWL
swap plateau at `15634.450477332834`, placement SHA-256
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`.
The pair scan is reused only because the complete one-opt placement bytes and
closure contract match. There is no scoring improvement.

## Interpretation And Next Action

Rank 11 contains at least four exact d6 tuples. Multiple tuples can share a
changed-refdes set or HPWL, and all four currently map through one-opt to one
identical state. This is stronger many-to-one basin evidence, not rank-layer
exhaustion. M336-118 remains the scoring incumbent.

Add all four certified rank-11 tuples as exact no-goods and enumerate again
with the M336-130 d6 hint. If the layer continues, use canonical tuples for
identity and exact one-opt SHA for closure memoization. The repeated collapse
also raises the priority of residual-specific candidate coverage and physical
support expansion over further seed, weight, or runtime ladders.
