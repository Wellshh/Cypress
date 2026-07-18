# M336-045: Known-Legal Fixed-Site Core Chain

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `8206175`

## Problem

The previously legal TOP placement is not directly reusable after restoring
the manual-baseline `Q601` endpoint. Fixed-obstacle pruning removes its original
site for 12 of 30 controlled TOP components. Their nearest K1024 sites move by
1.9998-25.9972 mm, so treating this result as an exact warm start silently
changes the placement. The unconstrained known-legal K1024 search was already
`UNKNOWN`; the required repair scope was not quantified.

## Exact Core Experiment

`probe_exact_site_cpsat.py` can fix each component to candidate site zero under
a named CP-SAT assumption. Rectangle equivalence audits cover 258,239,716
candidate pairs with zero false positives and zero false negatives; the four
nonrectangles use validator-thresholded forbidden tables. Every proof below is
therefore exact only within the enumerated K1024 domain.

The nonzero nearest-site displacements are `C203` 3.9996, `C204` 22.3583,
`C301` 3.9996, `C502` 19.9979, `C601` 25.9972, `C604` 7.9991, `C701` 1.9998,
`C8653` 25.9972, `FV618` 7.9991, `L8630` 18.8659, `R605` 19.9979, and `R704`
9.9989 mm.

| Fixed count | Result | Sufficient core |
| ---: | --- | --- |
| 30 | `INFEASIBLE` | `C604` |
| 29 | `INFEASIBLE` | `C8653` |
| 28 | `INFEASIBLE` | `L8630` |
| 27 | `INFEASIBLE` | `C601,C612` |
| 25 | `INFEASIBLE` | `FV601,FV618` |
| 23 | `INFEASIBLE` | `C501,R704` |
| 21 | `INFEASIBLE` | `C301,C611` |
| 19 | `INFEASIBLE` | `R604,R605` |
| 17 | `INFEASIBLE` | `C203,C204` |
| 15 | `INFEASIBLE` | `C201,C502,C701,FV301,FV602,FV604,FV607,FV617,FV701,L8606,L8607,L8626` |
| 3 | `UNKNOWN` | none; deterministic time 100 exhausted |

The final fixed components are `C202`, `R602`, and `RT201`. Six chain proofs
took 364.2 seconds; the final unresolved search took 103.1 seconds and reached
1,977,822 branches and 76,782 conflicts. A sufficient core is not guaranteed
minimum and does not prove each member independently necessary. `UNKNOWN` is
not evidence of feasibility or infeasibility.

## Reliability Guard

OR-Tools enforcement literals are half-reified. Clearing an assumption alone
leaves its Boolean free and can accidentally reactivate the fixed-site
constraint. Core-chain mode therefore forces every released literal false,
uses a fresh one-worker solver per step, writes an atomic progress checkpoint,
and records independent wall and deterministic times.

A two-step K1024 replay reproduced both cores, all branch/conflict counts, and
deterministic times exactly. Wall time changed with host load, as expected. Its
result SHA-256 is
`c45fb674026ae2e9025461491e2e7d723568ea6c5c6b17a6c33fc99dbdd1efc9`.

## Reproduction

```bash
PYTHONPATH="/tmp/m336-ortools:$PWD/install:$PWD" \
M336_GUIDE_JSON="$PWD/results/m336/discrete_collision_audit/result-grid01-known-legal-fixed-hint-decomposed.json" \
M336_CANDIDATE_LIMIT=1024 M336_FIX_GUIDE=1 \
M336_MOVABLE_REFDES=C601,C604,C612,C8653,L8630 \
M336_CORE_CHAIN=1 M336_DETERMINISTIC_TIME=100 M336_TIME=300 \
M336_OUTPUT_JSON=/tmp/m336-knownlegal-core-chain.json \
python3.11 experiments/m336/scripts/probe_exact_site_cpsat.py
```

Final evidence SHA-256 is
`067ce3882eda90434ae6aad812886808badb6f375992e64e85ade9fbf1f773d4`.

## Acceptance Impact

No placement was produced, so exact legality and the required normalized
HPWL/RSMT score `>= 1.0` remain unmet. Continue from the three-fixed boundary
with a larger deterministic budget, then test score-guide mixing. Any survivor
still requires full-board exact validation and deterministic native replay.
