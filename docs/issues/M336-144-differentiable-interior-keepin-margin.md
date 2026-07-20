# M336-144: Soft Keep-In Cannot Produce an Interior Gradient

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `002977b`

## Problem

The soft keep-in objective performs detached CPU geometry queries in every
forward call and penalizes only points outside a feasible domain. Explicit hard
projection now makes every objective iterate feasible, so this term remains
exactly zero and cannot reduce pressure on the projector near irregular region
boundaries.

## Remediation

Build a conservative interior signal from each footprint-aware feasible
mask. Cache identical domain classes, sample their distance fields with PyTorch
operations on the placement device, and optimize
`softplus((margin - inside_distance) / tau)^2`. Keep Shapely restricted to the
one-time domain construction and exact-validation paths.

## Acceptance Criteria

- Forward evaluation performs no detached CPU or Shapely geometry query.
- Deep-interior loss is negligible and near-boundary gradients are finite,
  nonzero, and point inward under gradient descent.
- Autograd agrees with finite differences and CPU/GPU results agree.
- Margin values `0`, `0.05`, `0.10`, and `0.20 mm` run under one native E3
  contract and report projection pressure and native quality.
- The term is removed if the controlled ablation shows no useful signal.

## Resolution Evidence

`FeasibleDomain` now builds a padded, conservative interior distance transform
once per cached footprint/region class. `SoftKeepInLoss.forward()` uses only
PyTorch `grid_sample` and tensor operations. The focused suite verifies deep,
boundary, and outside behavior, inward finite gradients, finite differences,
absence of runtime geometry calls, and CPU/H100 agreement.

The seed-1000, 10-iteration E3 sweep under
`results/m336/native-cypress/n2-margin-sweep-grid005/` used one H100, a
`0.05 mm` feasible grid, identical input hashes, and identical initialization
hash `3c8ed4cf...`. All four margins executed 13 backward calls and 10 Adam
steps:

| Margin mm | Gradient L1 | Projection events | Max projection | Native score |
|---:|---:|---:|---:|---:|
| 0.00 | 0.115061 | 5 | 0.122430 | 0.609442 |
| 0.05 | 0.402578 | 5 | 0.125375 | 0.609459 |
| 0.10 | 0.974135 | 5 | 0.131115 | 0.609490 |
| 0.20 | 2.720044 | 6 | 0.142393 | 0.609574 |

Against the same-grid N1 zero-gradient E3, the `0.10 mm` setting reduces
projected-node events from `55` to `5`, maximum correction from `0.980613` to
`0.131115` Cypress units, and overlap pairs from `70` to `27`. Native score
drops from `0.611492` to `0.609490`, so this is stabilization evidence, not a
quality improvement. Retain `0.10 mm` as the diagnostic default while anchor
weighting and irregular density are corrected; reassess it in the final E2/E3
ablation.

The 50-iteration hard-only E2 run under
`results/m336/native-cypress/n2-anchor-rescaled-diagnostic-50/` and corrected
margin-enabled E2 under
`results/m336/native-cypress/n2-anchor-final-isolated-diagnostic-50/` provide the
longer follow-up. Margin reduces projection events from `361` to `34`, maximum
projection from `1.104043` to `0.698683`, overlap pairs from `85` to `65`, and
overlap area from `8.581592` to `1.086227 mm2`. HPWL rises from `23781.199219`
to `24188.187500` and RSMT from `25362.308594` to `25815.576172`. Retaining the
term is justified by substantially lower projection and collision pressure,
not by native quality; this tradeoff remains a final-matrix review item.
