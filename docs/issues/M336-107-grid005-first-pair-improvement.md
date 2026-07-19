# M336-107: 0.05 mm Pair Closure Finds A Strict Improvement

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `630df50`

## Problem

M336-106 stopped at a full-domain 0.05 mm one-optimum. A coordinated pair can
move into a site blocked by the other component or improve shared net extrema,
so the one-component result was not yet a two-optimum.

## Search

The blocker-aware exact pair scan used all 532,193 obstacle-free sites from the
certified one-opt source. It evaluated 2,891 relevant component pairs and
101,953,515 site combinations in `107.078654` seconds. The run was deliberately
limited to one accepted pair so the first strict change could be independently
certified before continuing.

`C8619` moved from `[853.908285,91.990120]` to
`[853.908285,97.989475]`, while `L8605` moved from
`[854.908177,99.989260]` to `[854.908177,89.990334]`. The pair has no shared
net; its benefit comes from coordinated physical-site release. Exact HPWL
decreased by `3.999570419313` to `15669.623686575602`.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL` with 100 single-site
domains. Response, modeled, and selected-site integer HPWL all equal
`15669623693`; exact validation remains 100/100 contained with zero keep-in
violations and overlaps. The pair result, pair placement, certification result,
and certified placement SHA-256 values are:

- `23f2fa5d54f232609541415e04c502de8ea3854fec1d82761fe7c2d17339ffc0`;
- `488fee8e60f9086f91262f1dc7dabe5f516f53565a6b5eab76fdfbee9a6fa101`;
- `9f01b76cbff99e236149fff5c0e2fa152978bb252d27bc56111a7df6738de7c7`;
- `488fee8e60f9086f91262f1dc7dabe5f516f53565a6b5eab76fdfbee9a6fa101`.

## Remaining Boundary

The normalized score upper bound is `0.9738823265334965`; score 1.0 still
requires another `409.254114788970` HPWL reduction. The stop reason
`max_pair_moves` is an experiment checkpoint, not a two-optimality claim.
Repeat one exact pair scan from this certified state and promote only another
strict independently certified result.
