# M336-157: Native Runner Grid Contract Drift

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

The active M336 contract fixes exact keep-in domains at `0.05 mm`, but
`run_matrix.py --grid-mm` defaults to `0.1 mm`. A run that omits the option is
therefore labelled as an M336-118 warm track while constructing a different
feasible lattice.

## Evidence

The seed-1000, 10-iteration warm E4 smoke under
`n4-warm-e4-smoke-10` serialized `constraint_grid_mm = 0.1`. It missed all 89
cached `0.05 mm` domains, spent `7.117 s` rebuilding domains, and cannot be
compared with M336-118 or earlier `0.05 mm` diagnostics.

## Impact

- Omitted CLI configuration silently changes legal candidate coordinates.
- Cold/warm timing includes avoidable cache rebuilds.
- Quality and repair evidence can be compared across incompatible domains.

## Remediation

Define one M336 runner constant for `0.05 mm`, use it as the CLI default, test
the value, and retain the resolved grid in every run identity and result.

## Acceptance Criteria

- A default run serializes `constraint_grid_mm = 0.05`.
- M336-118 warm preflight remains 100/100 contained with zero overlaps.
- Repeated warm runs hit the same feasible-domain cache.
- Final cold and warm matrices use one identical grid value and input hashes.

## Resolution

`run_matrix.py` now defines one `0.05 mm` M336 grid constant and uses it as the
CLI default. A unit test freezes that default. Two subsequent warm E4 runs both
serialized `constraint_grid_mm = 0.05`, loaded all 89 unique feasible domains
from cache with zero misses, and preserved all 100 constrained components with
zero pre-optimization overlaps or keep-in violations. The final matrix runner
also includes the resolved grid in every run result and run identity.
