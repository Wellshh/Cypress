# M336-051: CP-SAT Objective Does Not Match Selected-Site Replay

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `70d7802`

## Problem

A mixed-side expanded-domain CP-SAT run returned `FEASIBLE` and emitted an
exactly legal selected-site placement, but the solver objective does not match
the integer objective reconstructed from those selected sites. This invalidates
the run as optimization evidence even though its independent geometry report
is legal.

## Evidence

The last global K64 result is internally consistent:

- solver objective: `16005.772307`;
- selected-site integer replay: `16005.772307`;
- PlaceDB floating HPWL: `16005.772294645369`.

After expanding only `FV302` and `R708` from K64 to K1536, the result reports:

- solver objective: `15998.363492`;
- selected-site integer replay: `15997.273166`;
- PlaceDB floating HPWL: `15997.273153806742`;
- solver minus selected-site replay: `1.090326`;
- declared rounding allowance: `0.000304`;
- observed float-versus-integer rounding: `0.000012193259`;
- maximum per-net rounding delta: `0.000001592455` on `SPK_P`.

The mismatch is about 3,586 times the conservative rounding allowance and is
not a float-quantization effect. OR-Tools examples validate a returned
incumbent by recomputing its objective from `solver.value(...)`; both APIs read
the same `CpSolverResponse`, so the two values are expected to agree.

## Reproduction

With the transient source and guide artifacts retained:

```bash
PYTHONPATH="/tmp/m336-ortools-py311:$PWD/install:$PWD" \
M336_SOURCE_JSON=/tmp/m336_both_global_three_guides_k64_dt900.json \
M336_ASSIGNMENT_JSON=/tmp/m336_emi_only_grid01_assignment.json \
M336_OUTPUT_JSON=/tmp/m336_both_global_k64_expand_fv302_r708_k1536.json \
M336_PACKING_SIDE=BOTH \
M336_USE_BASELINE_GUIDE=1 \
M336_ADDITIONAL_GUIDE_JSONS=/tmp/m336_both_global_three_guides_k64_dt900.json,/tmp/m336_emi_only_grid01_no_collision.json \
M336_HINT_GUIDE_INDEX=1 \
M336_MANUAL_BASELINE_ENDPOINTS=EMI601 \
M336_CANDIDATE_LIMIT=64 \
M336_EXPANDED_CANDIDATE_LIMIT=1536 \
M336_EXPANDED_REFDES=FV302,R708 \
M336_OPTIMIZE_HPWL=1 \
M336_TIME=900 \
M336_DETERMINISTIC_TIME=500 \
M336_SEED=1000 \
python3.11 experiments/m336/scripts/probe_exact_site_cpsat.py
```

The result SHA-256 is
`80f3fcd6f9662d19264dd1d59607e9178b452bff38cc354e9722f58dabfccbcd`.
Status is `FEASIBLE`, not `UNKNOWN`; no infeasibility claim is made.

## Impact And Required Fix

Quarantine the apparent `8.499141` HPWL improvement and the reported
`14983.968188` lower bound. They must not drive acceptance or subsequent guide
selection until the mismatch is explained.

The probe must record and compare three quantities for every incumbent:

1. the objective reconstructed directly from solved max/min variables;
2. the integer objective replayed from solved candidate indices;
3. the independent PlaceDB floating HPWL with the existing rounding bound.

It must also verify that each solved candidate index maps to the solved integer
node coordinates. Any mismatch must be explicit in JSON and fail closed before
the result can be promoted. Add a regression that exercises heterogeneous K64
and K1536 candidate domains, then rerun this exact model deterministically.

## Safeguard Implemented

The probe now writes `objective_replay_audit` for every feasible HPWL solve.
It compares the response objective, the sum of solved per-net max/min
variables, the selected-site integer replay, candidate-index coordinate
mapping, and PlaceDB HPWL within the declared rounding allowance. A failed
audit still writes diagnostic JSON but exits with status 3. The native scorer
also rejects HPWL-optimized results whose audit is missing or failed.

Two regressions cover heterogeneous K64/K1536 candidate maps and integer
per-net replay. The M336 suite passes 37/37. A BOTH-side all-fixed integration
replay passed all checks with integer objective `16045831380`, selected-site
delta zero, float delta `0.000015724472`, 100/100 containment, zero keep-in
violations, and zero overlaps. Its result and placement SHA-256 values are
`ad75c39ff98b3f24fc6fa0bc9f367b486846c37624157b6ce583f35dba8f11e3`
and `3145a9dbde07d38e19d275d987067de358b58fc99d8d79d73371dd2163e2c3c8`.

This mitigation prevents silent promotion but does not explain the original
expanded-domain discrepancy. The issue remains open pending an audited rerun
of the exact heterogeneous model.
