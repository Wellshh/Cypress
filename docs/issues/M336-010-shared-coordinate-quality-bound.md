# M336-010: Interval Assignment Bound Produces a False Quality Candidate

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `cfbd7aa`

## Problem

The assignment MILP lets each pin choose an independent coordinate in each
net-axis interval. A physical component has one shared x/y coordinate across
all of its pins and nets, so an interval score upper bound above `1.0` is only a
screening result, not evidence that the assignment can pass.

## Proof For The Current `0.05 mm` Assignment

`solve_discrete_placement.py` couples x and y through one exact feasible-domain
site variable per controlled component and models exact native net HPWL spans.
For a normalized score of `1.0`, the fact that `RSMT >= HPWL` imposes the
necessary condition:

```text
HPWL <= 15260.369571786632
```

CP-SAT was run with all collision constraints disabled, making the model more
permissive than any legal placement. It still proved `INFEASIBLE`:

| Quantity | Value |
| --- | ---: |
| Grid candidates | `776,613` |
| Controlled / runtime-fixed nodes | `100 / 40` |
| Branches / conflicts | `6,937 / 0` |
| Wall time | `31.886 s` |
| Workers / seed | `1 / 1000` |

The integer constraint adds a conservative `0.000304` HPWL allowance for
separately rounded component coordinates and pin offsets; see `M336-011`.

This is a mathematical rejection of the fixed assignment on the `0.05 mm`
grid, even before overlap constraints. It does not prove that every same-side
assignment is impossible. The one-worker result reproduces the earlier
eight-worker proof with the same `6,937` branches.

Input SHA-256 hashes are:

- assignment: `bb69ec27cfe48a428428eaecda0dd33f4e29192594bee04dae743cc95798365c`;
- manual placement: `65ea89cfae831871fd115f61b50e528bcc77a0285d85ecbf4c4a97ba898ad595`;
- manual score result: `df8096d78fd3bff60bc2ad179fb83eda276da4566aeda1feafae7ffa9418ae2f`.

Reproduce after installing optional OR-Tools outside the project environment:

```bash
PYTHONPATH="/tmp/m336-ortools:$PWD/install:$PWD" python3.11 \
  experiments/m336/scripts/solve_discrete_placement.py \
  --assignment results/m336/quality_assignment/m336_region_assignment.grid005.runtime-fixed.quality.json \
  --baseline-result results/m336/baseline_warmstart_smoke/baseline/baseline-result.json \
  --grid-mm 0.05 --collision-mode none --minimum-score 1.0 \
  --workers 1 --seed 1000
```

## Additional Feasibility Evidence

With a loose quality threshold, a collision-constrained search produced a
placement that exact validation accepted (`100/100`, zero overlaps), with HPWL
`19435.5278` and score upper bound `0.785179`. Thus geometry is packable, but
the current assignment remains far from the quality target.

## Remediation

1. Couple region selection and shared component site coordinates in one model.
2. First search without collisions to reject globally impossible assignments.
3. Add exact collision constraints only for surviving assignments.
4. Confirm survivors with native RSMT and exact geometry validation.

## Acceptance Criteria

- A deterministic one-worker run reproduces the fixed-assignment proof. Met.
- Cross-assignment search finds a candidate not rejected by shared coordinates.
- The selected placement is exact legal and has native score `>=1.0`.
