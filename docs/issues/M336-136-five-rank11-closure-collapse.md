# M336-136: Five Rank-11 Tuples Collapse To One Closure State

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `104da75`

## Search Contract

M336-131, M336-133, M336-134, and M336-135 were added as four exact forbidden
site tuples to the unchanged M336-122 `d=6,Delta=20` model. M336-130 d6 remained
the separate feasible hint. Source, diversity reference, assignment, five
weighted guides, 18-component support, K4096 allocation, 73,810 candidates,
integer HPWL ceiling, seed 8408, one worker, and solver budgets were unchanged.

All four exclusions and the M336-118 diversity reference mapped at zero
maximum site distance. Replay reports exactly six changed sites, no matched
excluded tuple, and passed diversity/no-good, guide-rank, candidate-coordinate,
HPWL envelope, per-net, and exact-legality audits.

## Fifth Rank-11 Optimum

The model returned `OPTIMAL` after 25.471 solver wall seconds and 14.339
deterministic-time units. Objective and bound are both rank 11. The topology
has HPWL `15650.448759010085` and changes:

```text
C703,FV705,FV707,FV710,R707,R708
```

This is the first enumerated rank-11 tuple that moves `FV705`, `FV710`, and
`R708` together while leaving `FV708` at the M336-118 site. It therefore adds
a changed-support pattern, not only another site variant of M336-134/135.

The raw result and placement SHA-256 values are respectively:

- `61c9cf6ad56ab376b4d499c0223abf204ef8ae89db76805aa2a15e0a5cf39b18`;
- `367bcdd979202ecc10a8042c81fc2d6821eb808370676c74ede2d975b0d11ad8`.

Exact legality is 100/100 containment with zero keep-in violations and zero
overlaps.

## Certification And Portability

An independent all-fixed K1 replay returned `OPTIMAL` with 100 candidates,
zero hint distance, and objective and bound `15650448764`. Objective, per-net,
candidate-collision equivalence, and exact legality audits pass. The portable
entry point is
`experiments/m336/guides/M336-136/d6-rank11-nogood4/certificate.json`.

A second K1 replay launched from `/tmp` using only the tracked portable
certificate and assignment returned the same integer objective and
byte-identical placement.

| Artifact | SHA-256 |
| --- | --- |
| Portable certificate | `3cccb5bf59db185f905c5eea69ee45b2ac3d35b1a63e23f8b413ce3e4ea93609` |
| Original K1 certificate | `7d39adf0b0e9948cd5a61065eef0cd5f9354af91eeca6dbda28d9d016e2388a3` |
| Placement | `367bcdd979202ecc10a8042c81fc2d6821eb808370676c74ede2d975b0d11ad8` |
| Assignment | `e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87` |
| Manifest | `7ef625d1578ae35a5005920b3cc544c1473c961de9f95a0a3c1b46f3b4041fee` |
| Canonical selected sites | `535a822ca149893642bc23e59d98621baa05206029c8b186a879a742254e774a` |

## Independent Closure

Full one-opt accepted four moves in three completed sweeps and reduced HPWL by
`3.999570419313` to `15646.449188590772`. Its placement SHA-256 is
`47e65c62fe82959c717235152fb5244355a530c805a1847ad17cd976c32cc97c`,
byte-identical to every M336-131/133/134/135 one-opt result.

The independently certified M336-133 pair scan from these exact bytes reaches
the M336-129 equal-HPWL swap plateau at `15634.450477332834`, placement SHA-256
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`.
There is no scoring improvement.

## Decision Boundary

The unchanged rank-11 domain contains at least five exact tuples, including
different changed-refdes supports and site variants, but every independently
executed one-opt closure maps to one byte-identical state. This is not a proof
that rank 11 is exhausted or that the domain has no improving topology.

However, another consecutive no-good now has low information value relative
to the documented gap in residual endpoint and blocker coverage. Pause this
same-domain enumeration batch and make P2 residual-specific guide generation
and candidate coverage diagnostics active. Preserve all five portable tuples
as future no-good references. Resume enumeration only after guide coverage,
candidate allocation, or physical support changes create a materially
different search topology. M336-118 remains the scoring incumbent.
