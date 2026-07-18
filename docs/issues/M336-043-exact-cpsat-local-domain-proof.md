# M336-043: Exact CP-SAT Closes Two K512 Local Domains

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `6b1cea4`

## Problem

The validator-aligned binary CNF establishes several small-domain boundaries,
but full K512 runs around both the score-feasible collision-relaxed guide and
the manual PCB baseline remained `UNKNOWN` after 900 seconds. Pairwise site
conflicts produce roughly 13 million clauses, obscuring whether these timeouts
represent difficult feasible packings or genuinely infeasible neighborhoods.

## Exact CP-SAT Model

`experiments/m336/scripts/probe_exact_site_cpsat.py` retains the same exact
keep-in sites and fixed-obstacle pruning. Each of the 30 controlled TOP
components selects one site through an allowed-coordinate table. The 26
axis-aligned rectangles use `NoOverlap2D`; `C8653`, `L8607`, `L8626`, and
`L8630` use validator-thresholded forbidden-site tables from their true
polygons. The solver uses one worker and seed 1000.

An initial integer scale of `1e6` produced 842 false-positive rectangle
conflicts at K256 because numerical edge contacts became one integer unit.
Symmetrically insetting intervals by one scaled unit removes this artifact.
The script now audits every rectangle candidate pair against overlap area
`> 0.0039991408847609294` before labeling the model exact. K512 audits
78,796,800 site pairs across 325 rectangle-component pairs with zero false
positives and zero false negatives.

## Results

| Guide/domain | Candidates | Nonrect conflicts | Result | Solve time (s) |
| --- | ---: | ---: | --- | ---: |
| score guide K256 | 7,436 | 818,614 | `INFEASIBLE` | 0.009 |
| score guide K512 | 14,806 | 3,421,121 | `INFEASIBLE` | 56.399 |
| manual baseline K512 | 14,806 | 3,643,993 | `INFEASIBLE` | 53.415 |

These are exact proofs only for the enumerated local domains, not for the full
placement lattice. They explain the CNF timeouts without weakening legality.

Selective CNF expansion does not yet close the next boundary. Expanding only
`RT201` to K1024 is `UNKNOWN` after 900.031 seconds. Under that domain, fixing
`R605` at its guide site is `UNSAT` after 432.344 seconds with the singleton
core `R605`. Expanding both `R605` and `RT201` to K1024 is again `UNKNOWN`
after 900.578 seconds.

For the manual guide, Hitman tested 12,793 fixed-site release sets: 12,792 were
`UNSAT`, then one depth-18 node timed out. This sampled search is not a global
proof and must not be reported as one.

## Reproduction

Install optional OR-Tools outside the production environment, then run:

```bash
PYTHONPATH="/tmp/m336-ortools:$PWD/install:$PWD" \
M336_CANDIDATE_LIMIT=512 M336_TIME=300 \
M336_OUTPUT_JSON=/tmp/m336-cpsat-score-k512.json \
python3.11 experiments/m336/scripts/probe_exact_site_cpsat.py
```

Set `M336_USE_BASELINE_GUIDE=1` for the manual-baseline domain. Evidence files
must report `candidate_domain_overlap_model_exact: true`; otherwise an
`INFEASIBLE` result is only conservative.

Final evidence SHA-256 values are:

```text
score K256: 30ed946709f1d0e7f879e3c727d22ca9e3b8ebf5eba9b211b1540a2753c791ff
score K512: b64f7c44a0f087dbfcc20df2a75d7898cf84cd0931da5461842990be93eb2095
manual K512: b7653d596017088e3d74dcc3effebe797bd8b33bef8ee86b4cea586fedd7c652
```

## Acceptance Impact

No legal placement or native score was produced, so the required normalized
HPWL/RSMT score `>= 1.0` remains unmet. Continue with exact K1024 or selective
domain expansion, then merge any TOP survivor with the known legal BOTTOM
placement and run full-board exact validation plus one-worker native replay.
