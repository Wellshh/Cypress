# M336-161: Feature-Off Overflow Includes Side Fillers

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

The M336-147 side-density refactor reused one side-layout descriptor for both
electric potential and overflow. The legacy Cypress potential includes side
fillers, but its TOP/BOTTOM `ElectricOverflow` operators explicitly set
`num_filler_nodes=0`. The refactor passed the actual side filler count to both
operators even when `irregular_density_flag=false`.

## Evidence

A deterministic CPU `test_small` comparison used the same seed, one thread,
100 iterations, and disabled all anchor/keep-in features. At `f0e4cb9`,
iteration-zero HPWL/objective/overflow were
`2263.076 / 13.03307 / 0.4315246`. The current branch reproduced the HPWL and
objective but reported overflow `0.9916955`. By iteration 99, the reference
overflow/objective were `0.2942742 / 31.28787`, while the current values were
`0.9849733 / 0.9145136`.

The divergence begins in metric evaluation: including fillers inflates
two-side overflow, which then changes gamma, density-weight updates, and the
optimization trajectory. Both runs eventually hit the benchmark's existing
overflow failure gate, so process exit status and serialized placement bytes
cannot detect this regression.

## Remediation

Restore the legacy side-overflow contract when irregular density is disabled:
potential retains side fillers, while `ElectricOverflow` receives zero filler
nodes. Irregular-density layouts already contain only constrained movable
nodes and therefore also require zero fillers. Add a constructor-contract unit
test and repeat the deterministic reference/current comparison.

## Acceptance Criteria

- Feature-off side overflow constructs TOP/BOTTOM operators with zero fillers.
- The deterministic current run matches `f0e4cb9` iteration-zero and final
  objective, HPWL, overflow, and placement bytes.
- Irregular-density unit tests and the M336 native smoke remain green.
- No M336 context, capacity map, anchor loss, or keep-in loss is created when
  feature flags are off.

## Resolution

Side overflow now always preserves the original zero-filler contract; the
electric-potential objective continues to consume the side filler layout.
`irregular_density_unittest.py` directly audits the constructor argument and
passes all nine CPU/CUDA tests. After the independent Nesterov lifecycle fix in
M336-162, the deterministic current and `f0e4cb9` runs have identical 100-step
objective, HPWL, overflow, and max-density records. No M336 context or irregular
capacity diagnostics appear in the feature-off log.
