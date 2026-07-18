# M336-002: Soft Keep-In Has Zero Gradient After Projection

**Severity:** High
**Status:** Open
**Found:** 2026-07-17
**Affected commit:** `d9e7674`

## Problem

The optimizer hard-projects constrained footprints into their feasible domains
before objective evaluation. The current soft keep-in term penalizes only
outside-domain distance, so its value and gradient are zero at every evaluated
feasible point. The configured term is therefore not an optimization signal.

## Evidence

The following sweep ran E3 for seeds 1000, 1001, and 1002 with 5 iterations:

```bash
CUDA_VISIBLE_DEVICES=3 PYTHONPATH="$PWD/install" python3.11 \
  experiments/m336/scripts/run_matrix.py --experiments E3 \
  --seeds 1000 1001 1002 --iterations 5 --gpu \
  --anchor-weight-sweep 0.25 0.5 1.0 2.0
```

All 12 runs recorded soft keep-in gradient norm `0`. Anchor lambda scaled from
approximately `120050.7` to `960405.2`, but mean anchor distance only moved from
`9.17595 mm` to `9.17137 mm`; p90 remained approximately `16.9911 mm`. Initial
anchor loss was identical (`0.001716386`). Those absolute placement metrics are
not final evidence because of M336-004, but the zero-gradient diagnosis is
architectural. The corrected manual-warm-start E4 independently recorded soft
loss `0`, gradient L1 `0`, and matched weight `1.0`.

## Impact

- The option appears active but cannot guide a feasible iterate away from a
  narrow boundary or reduce projector work.
- Weight tuning cannot fix the architectural ordering issue.
- Runtime is paid for evaluating a term that contributes no gradient.

## Remediation Options

1. Prefer a differentiable interior-margin barrier that is zero only beyond a
   configurable safety margin, while retaining exact hard projection.
2. Alternatively penalize the pre-projection proposal displacement and make
   the relationship to the optimizer state explicit.
3. If neither signal improves acceptance metrics, remove the misleading term
   from the first experiment rather than retaining a no-op parameter.

## Acceptance Criteria

- Unit tests cover deep-interior zero loss, near-boundary nonzero gradient, and
  outside-domain monotonicity using finite differences.
- Runtime logs separately report pre-projection displacement and soft loss.
- A controlled ablation demonstrates either measurable benefit or justified
  removal; no result may claim soft keep-in guidance while its gradient is zero.
