# M336-131: A Feasible d6 Hint Closes The M336-122 Rank Search

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `e11149e`

## Problem

M336-130 certified a legal six-site topology, but the earlier exact M336-122
`d=6,Delta=20` rank run remained `UNKNOWN`. That run used a four-site hint,
which violated its own minimum-distance constraint. The remaining question was
whether a feasible d6 hint would only establish an incumbent or would let the
same finite model close its rank objective.

## Controlled Rerun

The rerun preserved the M336-122 model: M336-118 source and diversity
reference, fixed assignment, exact BOTH-side collisions, 18 page-7 movable
components, five guides weighted `2,2,1,1,2`, K4096, 73,810 candidates,
integer HPWL ceiling `15654450483`, minimum six changed sites, seed 8408, and
one worker. Only `M336_HINT_JSON` changed to the portable M336-130 d6
certificate.

| Hint | Status | Build | Solve / DT | Rank result | Incumbent HPWL |
| --- | --- | ---: | ---: | ---: | ---: |
| Previous d4 | `UNKNOWN` | 121.751 s | 289.085 s / 307.706 | bound 6 | none |
| Certified d6 | `OPTIMAL` | 88.781 s | 24.411 s / 14.332 | optimum 11 | 15649.948866 |

Build time is reported for audit, not as a performance comparison. Candidate
count, guide weights, movable scope, required-guide support, endpoint policy,
and integer envelope all match. Every hint-site distance is exactly zero, so
the d6 hint is represented without projection in the original candidate
domain.

The optimal rank-11 result changes exactly:

```text
C703,FV705,FV707,FV708,FV710,R707
```

Its floating HPWL is `15649.948866405257`, replay integer HPWL is
`15649948871`, and diversity replay reports six changed sites. Guide-rank,
selected-site, per-net, candidate-coordinate, and integer-envelope audits all
pass. Exact legality is 100/100 containment, zero keep-in violations, and zero
overlaps. The rank result and placement SHA-256 values are respectively:

- `1abfd9e78f534686ec4920b9bc82a01481ecf1584d4d68b02a64773b05824ab1`;
- `e40bc866e04f736f580caa39043581206051cc8b5da9dbc2e4dc966a0b950dd5`.

## Certification And Portability

An independent all-fixed K1 replay returned `OPTIMAL` with 100 candidates,
zero hint distance, objective and bound `15649948871`, complete objective and
per-net replay, and exact legality. The portable entry point is
`experiments/m336/guides/M336-131/d6-rank11/certificate.json`.

| Artifact | SHA-256 |
| --- | --- |
| Portable certificate | `1d129d4b02fc77371ac9fcfa66ebe8373c48ba6cf2867e30ad3b267d6cb2fddf` |
| Original K1 certificate | `d71c4fd5ef35fb789dfae07a86feff2724ea23ddc1e5a1dd95aa19ea36f52bbb` |
| Placement | `e40bc866e04f736f580caa39043581206051cc8b5da9dbc2e4dc966a0b950dd5` |
| Assignment | `e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87` |
| Manifest | `2e95c43282f4507f7a8e1f4fcfd052edc1d999ba880cc3603d74c20f5a857607` |
| Canonical selected sites | `a497b88afa52ea47b0abe8cb783e3138bbb8be13d461ba239b201aed8eaa3f6a` |

The first export attempt also exposed a reproducibility defect: because this
run passed the assignment as a repository-relative environment path while its
result lived in `/tmp`, the result serialized a path later interpreted as
`/tmp/experiments/...`. The exporter failed closed; rerunning it with explicit
`--assignment` produced the portable artifact. The result producer still needs
a path-normalization fix before relative environment inputs are trustworthy.

## Independent HPWL Closure

Full one-opt accepted four moves and reduced the d6 topology to HPWL
`15646.449188590772`, retaining only `C703,FV707`. A full exact pair scan then
evaluated 2,874 pairs and 103,003,718 site combinations in 107.389 seconds. The
`C703/FV707` pair reduced HPWL by `11.998711257938` to
`15634.450477332834`.

The final placement SHA-256 is
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`,
byte-identical to the M336-129 equal-HPWL swap plateau. This is not a strict
scoring improvement, so M336-118 remains the incumbent.

## Interpretation And Next Action

The original M336-122 d6 domain was not geometrically blocked. Its prior
`UNKNOWN` was caused by search starting without a feasible d6 incumbent; a
certified hint converts the same model to a proof of rank optimum in 14.332 DT.
This validates the two-stage topology-generation workflow and rejects further
seed/runtime ladders with infeasible hints.

Rank 11 is only the best guide-rank layer under this d6/Delta20 model. It does
not prove that every other legal d6 topology closes to the same HPWL basin.
Add the rank-11 site tuple as a full no-good, retain M336-130 d6 as the feasible
hint, enumerate the next d6 optimum, and independently close each result. No
promotion is allowed without strict floating and integer HPWL improvement plus
fresh all-fixed certification.
