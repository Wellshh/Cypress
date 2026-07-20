# M336-137: Candidate Coverage Audit Exposes DATA2 Target Gaps

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `f380526`

## Problem

The M336-122 page-7 portfolio always contains 73,810 model candidates. Adding
guides redistributes the fixed K4096 budget rather than increasing it, but the
probe did not report which selected sites each guide admitted, whether a guide
target was representable, or how a changed portfolio differed from its
predecessor. Repeated solver stalls therefore could not distinguish an
unproductive search from missing endpoint coverage.

## Audit Contract

`probe_exact_site_cpsat.py` now has a default-off audit enabled by
`M336_AUDIT_CANDIDATE_COVERAGE=1`. It records:

- exact selected region indices, count, and SHA-256 per component;
- a full obstacle-pruned domain fingerprint over region identity and centers;
- the guide that first admitted each unique selected site;
- exact-target presence and nearest distance in model units and millimetres;
- scoped coverage for named residual-net endpoints;
- exact candidate-set Jaccard against a portable reference.

Reference comparison fails closed on scope, domain, count, or site-hash
mismatch. Configuring coverage nets or a reference while the audit is disabled
also fails closed. With the feature off, candidate generation remains
unchanged and the result contains only an `enabled: false` marker.

`candidate_coverage_checkpoint.py` exports immutable, repository-relative
references with dependency hashes and atomic `0644` output.

## M336-122 Baseline

The unchanged five-guide, `2,2,1,1,2` portfolio was audited over the 18 movable
page-7 components. The model had 73,810 candidates; the audit scope had
73,728 selected candidates (`18 * 4096`). It returned `OPTIMAL` with no
objective after 18.673 solve seconds and 8.074 deterministic-time units. The
result exactly retained M336-118:

```text
HPWL:       15634.450477332834
placement:  32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7
legality:   100/100 contained, zero keep-in, zero overlap
```

| Guide | First-admitted sites | Exact targets |
| --- | ---: | ---: |
| M336-118 | 18,432 | 18/18 |
| M336-121 seed 3001 | 18,432 | 18/18 |
| M336-121 seed 3000 | 9,216 | 18/18 |
| M336-121 seed 3003 | 9,216 | 18/18 |
| Page-7 quality hybrid | 18,432 | 16/18 |

Attribution describes the weighted round-robin guide that first inserted a
site; it is not a claim that the site appears in no other guide ordering.

## Finding

The quality-hybrid guide has zero exact candidate coverage for both
`PSIM2_DATA2` endpoints. Its nearest site for `FV710` is 58.687819 model units
(`2.934706 mm`) away; `R708` is one lattice step (`0.05 mm`) away. All other
listed residual-net endpoints have their exact quality-hybrid target in the
K4096 domain. Thus a guide can receive 25% of the page-7 candidates while its
most important DATA2 target remains unrepresentable.

This does not prove that the domain lacks an improving placement. It proves
that allocation totals alone are insufficient evidence of target coverage.

## Reproducibility And Decision

The portable baseline is
`experiments/m336/coverage/M336-137/m122-page7-k4096.json` (SHA-256
`de03e8caaa401f7d79c29b35d92eb94428fe96392677b89ba1177215c1a2470e`).
All eight dependencies match their recorded hashes, and a strict self-compare
gives intersection/union `73728/73728`, Jaccard `1.0`. A feature-off K1 replay
was `OPTIMAL` at integer HPWL `15634450483` and produced byte-identical
M336-118 placement output. Seventy-nine focused tests pass.

Use this checkpoint as the M336-138 reference for the six M336-130 residual
targets. Compare coverage before allocating a new optimization budget, then
generate direct net-span guides for endpoints still absent. M336-118 remains
the scoring incumbent.
