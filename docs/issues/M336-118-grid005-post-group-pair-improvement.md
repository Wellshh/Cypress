# M336-118: Post-Group Pair Closure Finds Another Strict Move

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `7525ef3`

## Search And Improvement

A full-domain `0.05 mm` one-component refresh from the M336-117 certificate
scanned all 532,193 obstacle-free sites and stopped after one sweep at
`one_optimum` with no move. A subsequent blocker-aware pair checkpoint
evaluated 2,893 relevant pairs and 103,962,955 site combinations in
`110.424489` seconds.

The accepted TOP pair `C8653/L8630` shares net 18. Moving both components by
one additional lattice step decreases HPWL by `0.999892604828`, from
`15635.450369937662` to `15634.450477332834`. No follow-up one-component move
was unlocked. Exact validation remains 100/100 contained with zero keep-in
violations and overlaps.

## Certification

An independent all-fixed K1 CP-SAT replay returned `OPTIMAL`. Response,
modeled, and selected-site integer HPWL all equal `15634450483`; maximum hint
distance is zero and the candidate and certificate placement files are
byte-identical. The descent result, placement, certification result, and
certified placement SHA-256 values are:

- `803acefe7c8a39df6a2a9e07eaacd6858b0fb1f71dc6f01cfeb65b8a927bd022`;
- `32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`;
- `4c1dd7ca647877873133c6aa9d2da99d4b0b51d9b5cf07eb03b6bd805fdc39fb`;
- `32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`.

## Remaining Boundary

The normalized score upper bound is `0.9760732936479889`; the necessary
score-1 HPWL gap is `374.080905546202`. The local pair chain remains open, but
one-unit gains cannot close the main gap efficiently. Preserve this certified
checkpoint and prioritize a refreshed coupled-domain search before another
full pair scan.
