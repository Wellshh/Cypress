# M336-133: The First d6 No-Good Reveals A Degenerate Rank-11 Layer

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `214aeae`

## Search Contract

The M336-131 rank-11 site tuple was added as one exact forbidden assignment to
the unchanged M336-122 d6/Delta20 model. M336-130 d6 remained the separate
feasible hint. Source, diversity reference, assignment, five weighted guides,
18-component support, K4096 candidate allocation, integer HPWL ceiling, seed
8408, and one-worker search were unchanged.

The excluded certificate mapped at zero maximum site distance. Diversity
replay recorded one excluded tuple, no matched excluded index in the returned
solution, exactly six changed sites, and a passed no-good audit.

## Second Rank-11 Optimum

The 73,810-candidate model returned `OPTIMAL` after 24.539 wall seconds and
14.330 deterministic-time units. Objective and bound are both rank 11. The new
topology has HPWL `15651.948651614910` and changes:

```text
C703,FV705,FV707,FV708,R707,R708
```

M336-131 and M336-133 therefore occupy the same optimal rank layer but differ
at one residual endpoint choice:

| Topology | Distinct sixth endpoint | HPWL | Rank |
| --- | --- | ---: | ---: |
| M336-131 | `FV710` | 15649.948866 | 11 |
| M336-133 | `R708` | 15651.948652 | 11 |

The result and placement SHA-256 values are respectively:

- `65e79b7e8b10fb6c2466df63042565ff9cf5725bd3cc551719ef35f256f9688e`;
- `92d3a8c9cb6a384e88e48f08b8caaf4db8ef502f8da85bf123fd842927ae2d36`.

Guide-rank, diversity/no-good, candidate-coordinate, HPWL envelope, per-net,
and exact legality replays all pass. The solution is 100/100 contained with
zero keep-in violations and zero overlaps.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL` with 100 candidates,
zero hint distance, objective and bound `15651948656`, exact objective/per-net
replay, and exact legality. M336-132 path canonicalization allowed export with
no dependency override. The portable entry point is
`experiments/m336/guides/M336-133/d6-rank11-nogood1/certificate.json`.

| Artifact | SHA-256 |
| --- | --- |
| Portable certificate | `4b06079382078eadcfa14878b4bacb1457598d37a487590604dc644103c50a95` |
| Original K1 certificate | `6578bbd89d26cab27bc584c5e8b21210d18c402506bbed1746397bfd3999e226` |
| Placement | `92d3a8c9cb6a384e88e48f08b8caaf4db8ef502f8da85bf123fd842927ae2d36` |
| Assignment | `e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87` |
| Manifest | `6a1e212c1ef3aa9686ad5864ea469556a001fbaff127d30ed30c305999ba524b` |
| Canonical selected sites | `507b997f63746b176b41558c989832045d405c734a3b353901b21bb51fa9eab4` |

## Independent Closure

Full one-opt reduced the second topology by `5.499463024138` to
`15646.449188590772`. Its resulting placement SHA-256 is
`47e65c62fe82959c717235152fb5244355a530c805a1847ad17cd976c32cc97c`,
byte-identical to the M336-131 one-opt result.

An independent exact pair scan still evaluated 2,874 component pairs and
103,003,718 site combinations in 108.180 seconds. It reduced the same
`C703/FV707` pair by `11.998711257938` to HPWL `15634.450477332834`. The final
placement SHA-256 is
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`,
identical to the M336-129 equal-HPWL swap plateau. There is no scoring
improvement.

## Interpretation And Next Action

A single no-good does not leave rank 11; the optimal guide-rank layer is
degenerate. Two distinct d6 topologies also map through one-opt to identical
bytes, giving direct many-to-one basin evidence. This is useful negative
evidence but not layer exhaustion.

Add both M336-131 and M336-133 tuples as exact no-goods, keep M336-130 d6 as the
feasible hint, and enumerate again. If repeated rank-11 solutions continue to
collapse to the same one-opt hash, record the hash equivalence and prioritize
new residual/support guides rather than rerunning pair closure from identical
intermediate bytes. M336-118 remains the only scoring incumbent.
