# M336-109: Third 0.05 mm Pair Scan Improves Coupled Top Nets

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `861fedc`

## Search And Improvement

The third exact single-pair checkpoint started from the M336-108 certificate,
confirmed its one-optimum, and evaluated 2,889 relevant pairs plus 101,812,175
site combinations in `107.504539` seconds. It accepted one TOP-side pair:
`C203` and `RT201`, which share nets 3 and 6, each moved by approximately one
model unit in x.

HPWL decreased by `0.999892604828`, from `15665.624116156288` to
`15664.624223551460`. Exact validation remained 100/100 contained with zero
keep-in violations and overlaps. The checkpoint stop reason is
`max_pair_moves`, not `two_optimum`.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`; response, modeled, and
selected-site integer HPWL all equal `15664624230`, and all audits pass. The
pair result, pair placement, certification result, and certified placement
SHA-256 values are:

- `a0f04dfb30eae41d7fad1d17f01c6aefefc6ac81cc510f48f4d964f2c5bf7bdd`;
- `c5f7727fabe5ded9121ffb5be6699b282ee0bb5da7d2ed784fdfc55cda4a8bdf`;
- `5746ce1597a496074a1322e9ec952600e4c9cb98c3e24e903d9e66743394f712`;
- `c5f7727fabe5ded9121ffb5be6699b282ee0bb5da7d2ed784fdfc55cda4a8bdf`.

## Remaining Boundary

The normalized score upper bound is `0.9741931471833815`; the necessary score-1
HPWL gap is `404.254651764828`. Continue exact pair checkpoints from this
certificate until the full scan returns `two_optimum`.
