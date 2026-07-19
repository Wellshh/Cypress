# M336-117: Page-4 Improvement Composes Sequentially

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `d0efef8`

## Finding

The independent page-4 improvement from M336-115 also composes after the
certified page7ab and page-86 U8601 changes. It was re-solved from the M336-116
certificate rather than merged into the placement.

## Search And Result

The exact K4096 model moved `B401`, `B402`, `C401`, `C402`, `C404`, `C405`, and
`L401`. It used the M336-116 certificate as source, hint, and required guide 0,
plus the EMI-only quality guide with `1,1` weights. The grid was `0.05 mm`, the
integer incumbent ceiling was `15637003647`, both sides remained constrained,
and the deterministic one-worker run used seed `1000`.

CP-SAT returned `OPTIMAL` with objective and bound `15635450376`. The same
seven effective one-grid-step moves from the parallel portfolio were selected.
Floating HPWL decreases by `1.553269972458`, from `15637.003639910120` to
`15635.450369937662`. The model used 28,765 candidates,
`5.804119165` deterministic-time units, and `21.773139453 s` solver wall time.

Selected-site objective replay, required-guide support, and exact
rectangle-equivalence audits pass. Exact legality remains 100/100 contained
with zero keep-in violations and overlaps.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`; objective and bound both
equal `15635450376`, maximum hint distance is zero, and candidate and
certificate placement files are byte-identical. Result, placement,
certification result, and certified placement SHA-256 values are:

- `130eb650c1fd9f51187bc3eb9581a03a9f8398c40bc271dacc88e101bf4fcd9c`;
- `56f5b266050762bf8041ec7948edc62b06c25180a521c08836c18ac7aaef4c44`;
- `73a151ba3b4e419479ca83601bfc7caf2ec5187e77cd22e4f6ab5bd67381f349`;
- `56f5b266050762bf8041ec7948edc62b06c25180a521c08836c18ac7aaef4c44`.

## Remaining Boundary

The normalized score upper bound is `0.9760108734141616`; the necessary
score-1 HPWL gap is `375.080798151030`. Promote this certificate as the sole
incumbent and refresh full-domain one-component closure before another pair or
higher-order search.
