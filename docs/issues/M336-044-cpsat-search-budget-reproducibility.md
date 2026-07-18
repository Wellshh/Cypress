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

## Remaining Risk

The deterministic cap is optional to preserve historical reproduction
commands. A run with only `M336_TIME` remains wall-bounded and its exact stop
state may vary. Completed SAT solutions still require exact validation, and
completed UNSAT claims require `candidate_domain_overlap_model_exact: true`.
