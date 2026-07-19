# M336-116: Page-86 U8601 Improvement Composes After Page 7

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `ceafbd3`

## Finding

The page-86 U8601 result from the M336-115 parallel portfolio could not be
promoted by directly merging placement files. Re-solving its complete K4096
physical-group model from the certified page7ab endpoint proves that the two
improvements compose under the full exact collision model.

## Search And Result

The run used the certified M336-115 endpoint as source, hint, and required
guide 0. It retained the EMI-only quality guide, `1,1` candidate weights, a
`0.05 mm` grid, K4096, exact candidate collisions, both packing sides, seed
`1000`, one worker, and integer incumbent ceiling `15646181097`.

The 11-component movable set was `C8608`, `C8609`, `C8619`, `C8620`, `C8622`,
`L8601`, `L8602`, `L8603`, `L8604`, `L8605`, and `L8625`. CP-SAT returned
`OPTIMAL` with objective and bound `15637003647`. It selected the same five
effective moves previously seen in the independent portfolio run, but against
the new page-7 topology.

Floating HPWL decreases by `9.177449600600`, from `15646.181089510720` to
`15637.003639910120`. The run used 9,310 candidates, `7.432763960`
deterministic-time units, and `4.802103484 s` solver wall time. Objective replay,
required-guide support, and rectangle-equivalence audits pass; exact legality
is 100/100 contained with zero keep-in violations and overlaps.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`. Objective and bound both
equal `15637003647`, maximum hint distance is zero, and the candidate and
certificate placement files are byte-identical. Result, placement,
certification result, and certified placement SHA-256 values are:

- `ff16623aa302735db3d3c21079313bd272f29842670d8e886d659a099be8f341`;
- `f4fcf8a999a05ab0511882f890c827ad7cb23a2728f510dc766dba1d2b798cfd`;
- `5c29d183ff5224000e5fed7f6ebcaa02f54e24b29e46ceca0a1f058ef1b9ecbc`;
- `f4fcf8a999a05ab0511882f890c827ad7cb23a2728f510dc766dba1d2b798cfd`.

## Remaining Boundary

The normalized score upper bound is `0.9759139233579118`; the necessary
score-1 HPWL gap is `376.634068123488`. Promote this certificate as the sole
incumbent and sequentially refresh page 4 before one- and two-component
closure.
