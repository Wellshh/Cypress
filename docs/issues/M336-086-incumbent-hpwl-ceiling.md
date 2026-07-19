# M336-086: Finite Search Returned a Worse Incumbent Than Its Hint

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `cec8bb7`

## Problem

Scoped K128 searches included every current exact site and supplied the current
placement as a complete CP-SAT hint. Nevertheless, the
`page_86_J8601__bottom` run returned a legal HPWL `15819.064499861614`, worse
than the certified hint `15811.06557381333`. CP-SAT hints guide search but do
not guarantee that the hinted assignment is assembled as an incumbent before
a deterministic budget expires. Comparing unconstrained finite-budget outputs
could therefore make an optimization pipeline regress nondeterministically.

The worse result is `FEASIBLE`, not optimal, with SHA-256
`f6a21d98e53b362016d85290cfcd1eaaeb5274a79fd102040e2c6e926d7f501d`.

## Resolution

`solve_discrete_placement.py` now accepts `--integer-hpwl-ceiling`. The scaled
HPWL expression receives a hard inequality using the stricter of this ceiling
and any score-derived limit. Reports distinguish:

- `score_hpwl_limit_integer`;
- `integer_hpwl_ceiling`;
- final `integer_hpwl_limit`.

A ceiling also enables HPWL variables during feasibility-only search. Invalid
nonpositive values fail before model construction, and packing-only mode
rejects the option because it deliberately omits HPWL.

## Evidence

An all-fixed replay with ceiling `15811065584` is `OPTIMAL` with objective and
bound exactly `15811065584`, zero branches, 100/100 containment, and zero
overlaps. Result SHA-256 is
`87c9113a4d81038029dcff3332c388082a4d2dcd250daf324e8af1ec94b758b2`.

Repeating the J8601 K128 search with the same ceiling returns `FEASIBLE` at the
certified source HPWL rather than the worse placement. Its valid bound remains
`15471.681587`, so no optimality claim is made. Result SHA-256 is
`90d0bbdad8d55883d98b077e461110ddca6e4875b8c48982361d9a9853e0ab38`.

## Acceptance Impact

Continuation searches are now monotonic with respect to the promoted integer
incumbent. This does not improve the normalized score, which remains
`0.9651702157924906`; it prevents finite search from silently regressing it.
