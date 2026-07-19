# M336-108: Second 0.05 mm Pair Scan Improves A Shared Net

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `5361d68`

## Search

The second full blocker-aware pair checkpoint started from the independently
certified M336-107 placement. It first confirmed no single-component strict
move, then evaluated 2,889 relevant pairs and 101,934,995 site combinations in
`108.085793` seconds over the same 532,193-site 0.05 mm domains.

The accepted pair moves `B402` by approximately +2 model units in y and `C405`
by approximately +2 in y. They share net 8. The coordinated move decreases
exact HPWL by `3.999570419313`, from `15669.623686575602` to
`15665.624116156288`, while retaining 100/100 containment with zero keep-in
violations and overlaps. The checkpoint again stopped at `max_pair_moves=1`;
it is not a two-optimality claim.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`. Response, modeled, and
selected-site integer HPWL all equal `15665624123`, and every replay audit
passes. The pair result, pair placement, certification result, and certified
placement SHA-256 values are:

- `c6b824c64c4719b12ba06e37efb7c8a0eca37dfcaab71c54f7a726f50c43c284`;
- `0705b7dc5a3c8df5b3b86ff2be61c98bfa4cd5a144713830593f618a2b9a5062`;
- `5fc3a8b2ce4df3e668ef3f6863dfddcf3a0eac1d5ae317ba6a8c6d3d72cc0731`;
- `0705b7dc5a3c8df5b3b86ff2be61c98bfa4cd5a144713830593f618a2b9a5062`.

## Remaining Boundary

The normalized score upper bound is `0.97413096718236`; the necessary score-1
HPWL gap is `405.254544369656`. Repeat the exact single-pair checkpoint from
this certified source until one scan returns `two_optimum`, certifying and
pushing every strict intermediate result.
