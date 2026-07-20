# M336-158: Anchor EMA Gradient-Ratio Windup

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `91fb33c`

## Problem

The adaptive anchor controller applies EMA directly to matched weight. When the
wirelength gradient scale falls sharply, the stale large EMA weight remains in
effect even though a refreshed raw weight is much smaller. The configured
target ratio is bounded syntactically but not dynamically.

## Evidence

In the seed-1000, 10-iteration warm E4 smoke with target ratio `0.1`, the raw
matched weight changed from `15.4420` to `1.00946` at iteration 5. Weight EMA
remained `12.5555`; effective gradient ratio jumped to `0.4975` and reached
`0.9950` at iteration 9, almost ten times the target.

## Impact

- Ratio sweeps do not represent their configured control variable.
- Anchor pressure can dominate after a wirelength-gradient scale transition.
- Anchor, overlap, and quality comparisons become difficult to interpret.

## Remediation

Add downward anti-windup: retain EMA for gradual upward changes, but cap the
smoothed weight by the latest bounded matched weight before applying the ramp.
Serialize the controlled weight and test an abrupt gradient-scale transition.

## Acceptance Criteria

- With zero minimum weight, refreshed effective ratio does not exceed target
  ratio times the active ramp, within numerical tolerance.
- Upward weight changes remain EMA-smoothed.
- Every refresh logs raw, bounded, EMA, controlled, and effective values.
- A native diagnostic confirms no material target-ratio overshoot.

## Resolution

The controller now retains EMA smoothing for upward changes but caps the
controlled weight by the latest bounded match after a downward transition. It
serializes raw, bounded, EMA, controlled, and effective values. The abrupt-scale
unit test confirms the refreshed effective ratio remains at the configured
target. In the corrected `0.05 mm` warm E4 10-step diagnostic, the configured
target was `0.1`; the largest effective ratio was `0.08`, exactly the active
iteration-9 ramp, rather than the previous `0.995` overshoot.
