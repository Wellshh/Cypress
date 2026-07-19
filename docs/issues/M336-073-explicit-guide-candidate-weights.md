# M336-073: Candidate Guide Allocation Was Implicitly Equal

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `89bbc12`

## Problem

Multi-guide candidate construction used a hard-coded equal round robin. A K512
current/quality model therefore reserved approximately half of every movable
component's candidate budget near the current placement, even when the purpose
of a run was to widen exploration around the lower-HPWL quality guide. Earlier
manual/current/quality runs similarly spent one third of the budget around the
illegal manual score baseline. The allocation policy was neither configurable
nor recorded in result metadata.

This does not make prior runs nondeterministic, but it hides a material search
parameter and makes candidate-width comparisons easy to misinterpret.

## Fix

`probe_exact_site_cpsat.py` now accepts
`M336_CANDIDATE_GUIDE_WEIGHTS=<w1,w2,...>`. It applies deterministic weighted
round-robin selection over each guide's stable distance/index order, skips
duplicate sites without consuming a guide's quota, and records the effective
weights in `candidate_guide_weights`.

Validation fails closed when the number of weights differs from the number of
guides, or when a weight is non-integral or non-positive. An omitted value
defaults to one for every guide, exactly preserving the prior equal-round-robin
behavior. Keeping the current guide first with a positive weight retains its
nearest exact site before quality-biased candidates are added.

## Verification

Two unit tests cover strict parsing, defaults, weighted order, deterministic
tie order, and duplicate suppression. The M336 suite now passes 50/50 tests.
Python syntax compilation and `git diff --check` also pass.

An all-fixed two-guide smoke used weights `1,7` and returned `OPTIMAL` with
100 single-site domains. Objective and bound both equal `15812564724`, objective
replay passes, and exact validation reports 100/100 containment with zero
violations and overlaps. Its placement SHA-256
`6eb7430cabf278b8084b938fc42492b787881557fefd0beca14658524456d25b`
matches the certified source exactly.

## Next Action

Run controlled `1:1`, `1:3`, `1:7`, and `1:15` current/quality allocations
with fixed source, movable set, total candidate count, seed, and deterministic
budget. Report each effective weight and bound. Treat a better FEASIBLE
incumbent as a search result, then require all-fixed replay and exact local
closure before promotion.
