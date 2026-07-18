# M336-007: Fixed Assignment Cannot Reach the Manual Quality Baseline

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `6cdfda4`

## Problem

The finalized region assignment was selected by anchor distance, seed
deviation, and area capacity, without net quality. Optimizer or CUDA tuning
cannot recover quality that the assignment geometry makes impossible.

## Corrected Evidence

`analyze_quality_bound.py` gives each controlled pin an independent position
inside its assigned feasible-domain x/y range and ignores overlap, shared
component coordinates, and discrete polygon coupling. The resulting HPWL is an
optimistic lower bound; RSMT is at least HPWL. Runtime-fixed endpoints use the
source positions required by the experiment, while other uncontrolled nodes
use the manual placement. See `M336-009` for the endpoint correction.

| Grid / assignment | Relaxed HPWL | Score upper bound | Result |
| --- | ---: | ---: | --- |
| `0.10 mm`, original | `17996.2459` | `0.847975` | Impossible |
| `0.10 mm`, MILP optimized | `15817.4414` | `0.964781` | Impossible |
| `0.05 mm`, original | `16943.9421` | `0.900639` | Impossible |
| `0.05 mm`, MILP optimized | `14675.1473` | `1.039878` | Survives only this relaxation |

The manual baseline is HPWL `14627.8477`, RSMT `15950.0654`, and score `1.0`.
The `0.05 mm` interval result is not a feasible placement: a stronger
shared-coordinate model also proves that fixed assignment cannot pass; see
`M336-010`.

The previously reported `18014.2736/0.847127` result is superseded because it
read uncontrolled endpoints from the loaded Cypress placement rather than the
declared runtime state.

## Reproduction

```bash
PYTHONPATH="$PWD/install:$PWD" python3.11 \
  experiments/m336/scripts/optimize_assignment.py \
  --assignment results/m336/quality_assignment/m336_region_assignment.grid005.template.json \
  --baseline-result results/m336/baseline_warmstart_smoke/baseline/baseline-result.json \
  --grid-mm 0.05
```

## Remediation

1. Keep interval MILP as a cheap rejection gate, not an acceptance test.
2. Search assignments with shared component coordinates and exact net spans.
3. Apply capacity and exact packing only to assignments that survive quality.
4. Run native HPWL/RSMT and exact legality before accepting any assignment.

## Acceptance Criteria

- Assignment and baseline input hashes are recorded.
- Deterministic assignment generation is independently checked.
- Shared-coordinate screening does not prove score `<1.0`.
- Exact legality is `100/100` contained with zero overlaps.
- Native normalized score is at least `1.0` for every accepted seed.
