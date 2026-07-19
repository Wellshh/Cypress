# M336-068: Page-6 Physical Group Improves The Certified Incumbent

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `c4dac2e`

## Problem

The certified HPWL `15835.344195928667` placement is a complete one/two-optimum,
and broad bottom-0/page-7 solves have made little recent progress. Independent
physical-group optimization is needed to identify higher-order moves that are
hidden when all members of a group are not released together.

## Search

The eight controlled members of `page_6_J601__bottom` (`C605` through `C610`,
`FV603`, and `R601`) were released together. All other controlled components
remained fixed. The deterministic model used current and collision-relaxed
quality guides, K1024 candidate domains, exact side-specific keep-in and
overlap constraints, one worker, seed 1000, and repair off. The feasible
current placement was supplied as the hint; no hard improvement ceiling was
used.

## Improvement

CP-SAT returned `OPTIMAL` in 3.061334 deterministic-time units:

- HPWL decreased by `1.561647114287`, to `15833.782548814380`;
- normalized score upper bound increased to `0.963785471016799`;
- the model contained 8,284 candidates and each released member used a K1024
  truncated domain;
- solver objective and bound both equal `15833782559`;
- exact validation reports 100/100 containment and zero violations or
  overlaps;
- objective replay passes with zero coordinate or per-net mismatches.

The remaining score-1 HPWL gap is `573.412977027748`. This is a strict
certified improvement, but it does not yet satisfy the manual-baseline score
gate.

## Certification And Closure

An all-fixed replay returned `OPTIMAL` at `1e-8` deterministic-time with zero
conflicts and branches. Response, solved-variable, and selected-site
objectives all equal `15833782559`; floating replay differs by
`0.000010185619`, within the audited allowance. The search result, placement,
certification result, and certified placement SHA-256 values are:

- `083e037ca37743d2de2099c6d4eacd7d082022a4c43335da53488e1a9ead9b77`;
- `f2daf10e764ac7543a184fadfc23affb3adac9b15acdc4d4886bc529b57e7427`;
- `23ef0cc1e786900d7e5569f468e95253f898554722ef209fa85352c929b5196d`;
- `f2daf10e764ac7543a184fadfc23affb3adac9b15acdc4d4886bc529b57e7427`.

Full-domain deterministic local closure accepted no one- or two-component
move. It evaluated 2,882 pairs and 3,549,546 site combinations and stopped at
`two_optimum`. The closure result SHA-256 is
`c62e92596a3046d3c6b2147dbbb3c9c4a63c5527a9cac12b91f047c52f9a1469`;
its placement hash is unchanged from the all-fixed certification.

## Next Action

Use the all-fixed certified result as the next source. Recompute cross-group
neighborhoods because the changed page-6 topology can unlock previously closed
groups. Continue alternating deterministic physical-group or combined LNS
optimization with complete one/two-opt closure and all-fixed replay.
