# M336-102: HPWL Constraints Dropped The Guide-Rank Objective

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `b64f073`

## Problem

`probe_exact_site_cpsat.py` allowed `M336_MINIMIZE_GUIDE_RANK=1` together with
an HPWL score gate or `M336_INTEGER_HPWL_CEILING`, but its objective construction
used `elif minimize_guide_rank` after `if enforce_hpwl`. Any HPWL constraint
therefore skipped `model.minimize(guide_rank_expression)` while result metadata
still declared `objective_mode: guide_rank`.

The HPWL replay had a second incompatible assumption: it compared every solver
response objective with modeled HPWL. After restoring the rank objective, that
comparison would reject the rank value as though it were HPWL.

## Impact

Combined monotonic-diversity searches were not valid guide-rank optimizations.
An exact B402 K8 reproducer with the current integer HPWL ceiling reported
`OPTIMAL`, response objective `0`, selected guide rank `2`, and current integer
HPWL `15811065584`; both replay audits failed and the process exited nonzero.
The fail-closed audits prevented this result from entering certification.
Earlier guide-rank-only experiments without an HPWL gate are unaffected.

## Fix

Objective construction now uses serialized `objective_mode` as its single
source of truth and applies the selected objective after all HPWL constraints
are built. HPWL replay records the response objective mode and compares the
response value with HPWL only in `hpwl` mode. In `guide_rank` mode it still
requires exact per-net/model/selected-site HPWL agreement and the hard ceiling;
the separate guide-rank audit verifies the response objective.

## Verification

Regression tests cover objective selection after HPWL model construction and
rank-objective HPWL replay. `py_compile`, `git diff --check`, and all 63 M336
tests pass.

The same real B402 K8 reproducer now exits zero and returns `OPTIMAL` with rank
objective and bound `0`. Both replay audits pass: selected-site and modeled
integer HPWL are `15811065584`, exactly at the declared ceiling, while selected
guide rank matches the response objective. Exact validation retains 100/100
containment with zero keep-in violations and zero overlaps. Result SHA-256 is
`f8bf81e655fe67d573a8b17febfc902057bb3d5f5552fb22e6b05f250e9f159a`.

The repaired objective exposes an equal-HPWL plateau that moves only `B402` by
approximately 2.0 model units. Its placement SHA-256 is
`41e49eaf7d1b76950f76e8df71775520c108367fa41c413e8cab52ffa738563f`,
different from the incumbent. It is a diversity seed, not a strict score
improvement, and requires independent fixed-site certification before reuse.
