# M336-082: Zero Score Threshold Divided by Zero

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `404ff71`

## Problem

Assignment exploration needs HPWL minimization without prematurely requiring
score 1.0. Passing `--minimum-score 0` reached `_score_hpwl_limit` and divided
by zero because one Boolean controlled both HPWL objective construction and the
score constraint. Using `--feasibility-only` avoided the crash but also removed
the HPWL objective, changing the intended experiment.

## Resolution

The model now separates two decisions:

- build HPWL variables when HPWL optimization or a positive score gate needs
  them;
- add the score inequality only when `minimum_score > 0`.

Negative, NaN, and infinite thresholds are rejected. `_score_hpwl_limit`
itself accepts only finite positive values, and reports now expose both
`hpwl_model_enabled` and `hpwl_gate_enabled`.

An all-fixed decomposed replay with `--minimum-score 0` and HPWL optimization
reported model enabled, gate disabled, and `OPTIMAL` integer objective and
bound `15811.065584`. Exact replay remained `15811.06557381333`, 100/100
contained, and zero-overlap. Result SHA-256 is
`4bba39d88c19041fd8aa3e85e545f742def610a2195a7feec21bdc0eb4e4067f`.

## Acceptance Impact

Unconstrained HPWL assignment searches now preserve their objective without
claiming that the manual-baseline score gate is satisfied. The current legal
incumbent is still below the required normalized score of 1.0.
