# M336-044: CP-SAT Timeout State Was Not Reproducible

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `52846e1`

## Problem

The exact-site CP-SAT probe fixed `num_search_workers=1` and the random seed,
but hard runs stopped only by wall-clock time. Machine load can therefore stop
two identical runs at different deterministic search states. Geometry
preprocessing also inherited BLAS/OMP thread counts from the shell, changing
resource use and wall time. Finally, hint-repair settings were implicit and
absent from result JSON. These gaps do not invalidate completed `INFEASIBLE`
proofs, but they make `UNKNOWN` boundaries and tuning comparisons difficult to
reproduce.

## Correction

`probe_exact_site_cpsat.py` now:

- sets BLAS, OMP, MKL, and NumExpr preprocessing threads from
  `M336_PREPROCESS_THREADS`, defaulting to one before importing NumPy;
- accepts `M336_DETERMINISTIC_TIME` as a deterministic search cap while
  retaining `M336_TIME` as a safety wall cap;
- exposes `M336_REPAIR_HINT` and `M336_HINT_CONFLICT_LIMIT` for explicit,
  isolated hint-repair experiments;
- records all budgets, seed, worker count, preprocessing threads, repair mode,
  and guide-rank objective state under `solver_parameters`.

Use one deterministic-time budget for comparisons. Changing repair mode,
conflict budget, seed, or objective creates a separate A/B run and must not be
combined with default-search evidence.

## Validation

The score-guide K256 smoke used one preprocessing thread, seed 1000,
`repair_hint=true`, conflict limit 1,000, deterministic cap 100, and wall cap
300. It retained the audited exact model and returned `INFEASIBLE` in presolve,
matching the prior CNF and CP-SAT boundary.

The exact K1024 A/B results are:

| Guide/search | Conflict budget | Stop | Conflicts | Branches |
| --- | ---: | --- | ---: | ---: |
| score, repair | 1,000,000 | wall 1,800 s; DT 997.19 | 383 | 16,023 |
| score, repair + rank objective | 1,000,000 | wall 1,800 s; DT 996.26 | 361 | 15,997 |
| one-overlap, repair | 1,000,000 | wall 900 s; DT 473.82 | 0 | 16,604 |
| score, repair | 1,000 | DT 500.00; wall 353.76 s | 805,323 | 16,850,999 |

All four runs returned `UNKNOWN`. A one-million-conflict repair budget stalls
inside hint exploitation and prevents normal conflict learning; adding the
guide-rank objective does not change that boundary. A 1,000-conflict budget
returns to regular search and hits the deterministic cap reproducibly, but has
not found a legal packing.

A separate default-search portfolio used seeds 1001 through 1004, one worker,
and deterministic cap 500 on the score-guide K1024 domain. All four runs were
`UNKNOWN`; they explored 14.37-16.14 million branches and 711,807-816,813
conflicts. Fixed seeds make each run repeatable, but seed diversity alone did
not expose a legal state.

Evidence SHA-256 values are:

```text
score repair 1m:      f0118952658b3c51c1c79e57fe27bbaf8fcb1ba0c4e06a3d9783fa80fe6854b0
score repair+rank 1m: 9436ab4ce6938bada3283b88131fda4d36ac058a6954977743a41d657bc3fb65
one-overlap repair 1m: 3858b41d23ce2d14aa0374dcc431030e2284889e1f9c6400fe3cd23b944e9f1a
score repair 1k:      dbfd777726a6e26e9ba0615cdefb2ac7c3d29c6f43bb0f76c051d248ec09146b
seed 1001: 12ee77b50f8d5276558a06c82877f4180a43f9d6715f4eae358d6ac17b1e2d80
seed 1002: 8f27f09feada02da41adbcc68dc8bff6af5e8164ba3004055cbef3504a495805
seed 1003: fc3aaca90bdd6224a1d74a06a82c7f481f68b91de8f0c0af8278ee5e63543dba
seed 1004: c3be6fbbaf058096e32b1b5b56c2a119ffd286979a2e1bd118ec90dddfad2785
```

## Remaining Risk

The deterministic cap is optional to preserve historical reproduction
commands. A run with only `M336_TIME` remains wall-bounded and its exact stop
state may vary. Completed SAT solutions still require exact validation, and
completed UNSAT claims require `candidate_domain_overlap_model_exact: true`.
