# M336-007: Fixed Assignment Cannot Reach the Manual Quality Baseline

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `6cdfda4`

## Problem

The final region assignment was selected by subgroup-to-anchor distance, seed
deviation, and area capacity. It does not model net quality. A relaxed lower
bound proves that no placement retaining this assignment can satisfy the manual
baseline score gate, regardless of optimizer tuning or packing quality.

## Evidence

For each constrained pin, `analyze_quality_bound.py` permits an independent
choice anywhere in the x/y interval enclosing its assigned feasible domain.
It ignores overlap, capacity, shared component coordinates, discrete grid
coupling, and polygon coupling. These relaxations can only improve the bound.
For every net, the minimum x span plus minimum y span is an HPWL lower bound;
RSMT is bounded below by the same value.

| Quantity | Fixed assignment | Any same-side region |
| --- | ---: | ---: |
| Relaxed HPWL lower bound | `18014.2736` | `12713.4401` |
| HPWL ratio vs baseline | `1.2315054` | `0.8691258` |
| RSMT lower-bound ratio | `1.1294169` | `0.7970776` |
| Quality-score upper bound | `0.8471266` | `1.2003336` |

The required score is `>=1.0`. The same-side relaxation exceeds that threshold,
so the keep-in geometry is not the proven blocker; the fixed assignment is.
Large forced regressions include `N31799771` (`519.5537` vs `58.3560` manual),
`DM` (`460.0` vs `51.8980`), and `VCHARGE_11P0` (`686.0` vs `340.0280`).

Input hashes are:

- Assignment: `fb76b18685b4c66f0af62dd25dc81af161535cfb25c30ed26c279ec49907afde`
- Baseline placement: `65ea89cfae831871fd115f61b50e528bcc77a0285d85ecbf4c4a97ba898ad595`
- Baseline result: `df8096d78fd3bff60bc2ad179fb83eda276da4566aeda1feafae7ffa9418ae2f`

Reproduce after preparing the manual baseline:

```bash
PYTHONPATH="$PWD/install" python3.11 \
  experiments/m336/scripts/analyze_quality_bound.py \
  --bookshelf-dir results/m336/baseline_warmstart_smoke/bookshelf \
  --baseline-result results/m336/baseline_warmstart_smoke/baseline/baseline-result.json \
  --output-dir results/m336/quality_diagnostics/reproducible_bound
```

## Impact

Further optimizer or CUDA tuning against this assignment cannot pass the user
quality gate and would consume roughly three minutes per one-iteration E4 run
without changing the conclusion.

## Remediation

1. Add deterministic net-quality costs to subgroup-region assignment instead
   of optimizing only anchor distance and seed adherence.
2. Search feasible same-side assignments under capacity and packing constraints.
3. Reject assignments whose relaxed score upper bound is below `1.0` before E4.
4. Run exact packing and native HPWL/RSMT scoring only for surviving candidates.

## Acceptance Criteria

- The generated assignment and all inputs have recorded hashes.
- Assignment generation is deterministic and reviewable.
- The relaxed bound no longer proves the score gate impossible.
- Exact validation reports `100/100` contained and zero same-side overlaps.
- Final E4 score is at least the manual baseline for every accepted seed.
