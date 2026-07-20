# M336-123: Page-7 Rank Layers Are Exact Barriers

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `d7d1d28`

## Problem

M336-122 showed that direct HPWL optimization retains the incumbent even when
three certified escape topologies are included. The prior page-7 monotonic
rank proof in M336-104 covered only the old `0.10 mm` K256 domain and could not
exclude a topology change in the current `0.05 mm` K4096 multiguide domain.

## Exact Rank Experiment

The quality hybrid was candidate guide 0, followed by certified seeds
3001/3000/3003 and M336-118 with weights `4,2,1,1,2`. All five guides passed
required-support closure over the same 18 page-7 BOTTOM movable components.
M336-118 remained the source. Every run used exact BOTH-side collisions, one
worker, K4096, and candidate-rank minimization.

Two hard HPWL envelopes were tested with automatic and partial-fixed branching
at seeds 6000 and 6001:

| Envelope and hint | Status | Optimal rank | HPWL | Placement SHA-256 |
| --- | --- | ---: | ---: | --- |
| M336-118, no regression | OPTIMAL (4/4) | 82 | 15634.450477332834 | `32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7` |
| certified seed 3001 | OPTIMAL (4/4) | 68 | 15649.948866405257 | `14b534af7e58bd277ff1fcfd4045636756bbb3a9de4386f3c307f021ddec2ed5` |

The eight result SHA-256 values, in current-auto 6000/6001,
current-partial 6000/6001, escape-auto 6000/6001, and escape-partial
6000/6001 order, are:

- `350563dbf077f7f8b475300097e52190ab939c31d4d325439870cedd812ebf0d`;
- `3ee8381ae3b8647f5cab70fed9266142b12710004676a5a5fdd256c13cd3970d`;
- `d5216350760728b3563142d5926f3efdb5b83ec0544dac92f418fcd2fbff5362`;
- `66e44a168a7fcbda513de385ab9fcf65d4a7da72e87b8168ddf62654e2ad279b`;
- `57f583306206bd05c97be1dee737b69bce1788aac17f867e3229a3ab2e1c84ad`;
- `9b9837dfac5dde4a6b51e8d28d882c3ac65e8ea887aeb894041bcb321cfb3bc8`;
- `493337cc3323656f8909d540b2ec9183f47a3422587b9d4ae56dd5caf1018855`;
- `152fd87b8ee708f6edbc5639c9091fafae0960020a38954d83b10fbcec71b39f`.

## Minimum-Layer HPWL Closure

Independent automatic and partial-fixed solves changed the objective back to
HPWL and imposed rank ceilings 82 and 68 respectively. All four were
`OPTIMAL`: the rank-82 objective/bound was `15634450483`, and rank-68 was
`15649948871`. They reproduced the same two placement hashes. Result hashes
were `d3a9fcc000e9933f0d7723a19e9abc431585f9e1f2ad9327c34db293fd6c61b8`,
`f00a637881cdfacd9146e0f40d24577d9ec1e83fd94742cb676083b78e161f49`,
`2de406c770f420bd4bde6221a836a20141ba9e7e94eeca2b82618db2b94c219b`,
and `190d846d07b11efb66be833de0e51a35f52b0cb51e85857acfdf7e42e8defc22`.

Every run passed HPWL/rank replay, exact candidate-collision equivalence,
required-guide support, 100/100 containment, zero keep-in violations, and zero
overlaps.

## Conclusion And Next Action

Within this finite domain, the no-regression minimum-rank layer contains no
strict HPWL improvement, and the best certified escape minimum-rank layer
cannot recover any of its 15.498389 HPWL rise. These are exact restricted-layer
proofs, not a global board bound. Stop rank seeds and rank-ceiling ladders.
Audit the quality hybrid's exact overlap graph and expand the movable set only
with external blockers that prevent page-7 topology changes; retain M336-118
as the scoring incumbent and certify every strict improvement independently.
