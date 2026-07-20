# M336-149: Target Density Is Below Side Utilization

**Severity:** High
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `91fb33c` plus uncommitted M336-147 work

## Problem

The M336 native matrix fixes `target_density` at `0.7`. After exact
side-specific Keep-in rasterization and frozen-obstacle subtraction, constrained
movable area consumes `80.5984%` of TOP usable area and `70.6933%` of BOTTOM
usable area. Both exceed the configured target. Even a perfectly uniform
placement therefore has unavoidable aggregate density overflow, especially on
TOP.

The 50-step irregular-density E2 diagnostic reports normalized overflow
`0.799250` on TOP and `1.586573` on BOTTOM. Those values include local
congestion, but they cannot be interpreted against a zero-overflow expectation
while the average-capacity contract is infeasible.

## Impact

- Density convergence and `stop_overflow` decisions can be misinterpreted.
- Weight or iteration sweeps may optimize an impossible target.
- Automatically raising density would make off/on comparisons incomparable and
  would hide a contract change.

## Remediation

Choose and serialize one explicit policy before the final matrix: either use
side-specific targets no lower than measured utilization plus a declared
headroom, or define irregular capacity at physical density `1.0` and keep
whitespace pressure as a separate objective. Apply the same declared policy to
all comparable ablations. Fail closed, or emit a prominent diagnostic, when a
configured target is below a side's aggregate utilization.

## Acceptance Criteria

- Every run records target density, usable area, movable area, and side
  utilization.
- The chosen policy is deterministic and identical across comparable E0-E4
  runs.
- A focused test rejects or warns on an infeasible target.
- Overflow and stopping thresholds are documented in the same normalization.
- No result is relabeled by silently changing target density after execution.
