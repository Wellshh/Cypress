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

## Controlled Ablation

The 80-component K256 comparison fixed source, candidate count 19,486, seed,
and 300 deterministic-time units:

| Current:quality | HPWL | Valid lower bound | Placement outcome |
| --- | ---: | ---: | --- |
| `1:1` | 15811.065574 | 14712.286843 | promoted M336-074 platform |
| `1:3` | 15811.065574 | 14713.314744 | same promoted placement |
| `1:7` | 15812.564715 | 14733.611976 | retained source platform |
| `1:15` | 15811.065574 | 14712.286414 | distinct equal-HPWL platform |

All statuses are `FEASIBLE`; objective replay and exact legality pass. The
`1:15` result differs from the promoted platform at `B402`, `C402`, `C8602`,
and `R605`. Its all-fixed replay is `OPTIMAL`, all integer objectives equal
`15811065584`, and placement SHA-256 is
`4ef1f91d4650aae34196453dbba0b82603b38616cfe6186f9c3fab3112b425c6`.
Full-domain one/two-opt closure accepted no move after 2,871 pairs and
5,195,812 combinations. Certification and closure result SHA-256 values are
`f1fa7a9c122cfaa34dae6158a054f78e0320a89058cf4ec77d4cae9908cadf41`
and `85f20c6638f0dd0123f3fc1c6ba83dafbdc12b8a9107f83c4bfec8427b5b43ed`.

Follow-up K256 weights `1:63` and `1:255`, plus K512 weights `1:3`, `1:7`,
and `1:15`, all retained the M336-074 source. Candidate quality bias therefore
changes deterministic search trajectory and plateau identity, but is not a
monotonic quality control. A wider or more quality-dominant allocation cannot
be ranked from FEASIBLE incumbents alone.

## Next Action

Retain `1:15` as a certified diverse search platform, not a superior
incumbent. Use guide weights only in controlled comparisons with recorded
source, order, total candidate count, seed, and deterministic budget. Explore
two-phase quality-rank seeds separately, and require HPWL replay before any
rank-objective output enters the certification path.
