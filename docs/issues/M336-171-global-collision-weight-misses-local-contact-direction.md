# M336-171: Global Collision Weight Misses Local Contact Direction

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `4569e23`

## Problem

The native footprint barrier is controlled by one global L1 gradient ratio.
That scalar reduces aggregate overlap pressure, but it does not guarantee that
every exact-contact pair receives a separating optimizer proposal. The exact
M336-170 guard consequently rejects every positive step from the legal
M336-118 warm start, even after bounded backoff.

This is not a guard failure. Every illegal candidate is rejected, complete
position and optimizer hashes are restored, and the run fails closed. The
remaining defect is the direction supplied by the differentiable objective.

## Bounded Evidence

GPU 2 ran checkpoint-warm E3, seed `1000`, one Adam iteration, LR scale `1`,
collision margin `0 mm`, tau `0.025 mm`, and exact backoff `0.5` for four
retries. Only the collision gradient ratio changed:

| Ratio | Effective weight | Retry-0 pairs / area (`mm2`) | Retry-4 pairs / area (`mm2`) |
| ---: | ---: | ---: | ---: |
| `0.10` | `0.0893451` | `10 / 0.008031909` | `9 / 0.000501145` |
| `0.25` | `0.223363` | `10 / 0.008026581` | `9 / 0.000501145` |
| `0.50` | `0.446725` | `7 / 0.005071385` | `6 / 0.000314339` |

All 15 attempts started from zero exact overlaps, retained zero keep-in
violations, and restored both position and optimizer state exactly. Ratio
`0.50` removes `C605/C606`, `FV703/R707`, and `FV704/R707` from the first
crossing set, but the following pairs still cross:

- `C501/R704`
- `C502/R704`
- `C611/C612`
- `C8606/C8613`
- `C8609/L8602`
- `RT601/FV703`
- `C8605/C8621` at all but the smallest retry

The nearly linear area reduction under step backoff proves that these pairs
have an inward first-order direction at the accepted start. No positive scalar
step on that direction can pass the exact guard.

The ratio-`0.25` and ratio-`0.50` failure artifacts are:

```text
results/m336/native-cypress/m336-170-guard-ratio-025-1/
  checkpoint_warm_start/E3/seed_1000/constraints/
  exact_step_guard_failure.json
SHA-256 0fd2d76be226faca721049ae9a7f6a6f7d61b5c26659cad67c5facb6bae0b81a

results/m336/native-cypress/m336-170-guard-ratio-05-1/
  checkpoint_warm_start/E3/seed_1000/constraints/
  exact_step_guard_failure.json
SHA-256 f431f6e2b01dea507cbc9d8693fb13b78405e38fe1b6d856f7405165b8bbe874
```

Both runs used this command contract, with `<ratio>` and `<tag>` set to
`0.25/025` and `0.5/05` respectively:

```bash
env CUBLAS_WORKSPACE_CONFIG=:4096:8 CUDA_VISIBLE_DEVICES=2 \
  PYTHONPATH="$PWD/install:$PWD:/tmp/m336-ortools-py311" \
  python3.11 experiments/m336/scripts/run_matrix.py \
  --experiments E3 --seeds 1000 --iterations 1 \
  --learning-rate-scale 1 --gpu --irregular-density \
  --footprint-collision --collision-gradient-ratio <ratio> \
  --collision-margin-mm 0 --collision-tau-mm 0.025 \
  --exact-step-guard --exact-step-guard-backoff 0.5 \
  --exact-step-guard-max-retries 4 \
  --initialization-track checkpoint_warm_start \
  --output-dir results/m336/native-cypress/m336-170-guard-ratio-<tag>-1
```

## Root Cause

The controller matches only the aggregate collision-gradient L1 norm to the
wirelength-gradient L1 norm over all active coordinates. It provides no lower
bound on the separating directional derivative of an individual contact.
Shared nodes can also receive competing pair forces.

Adam makes scalar tuning particularly weak at the first step: with zero
moments, its coordinate update is approximately the learning rate times the
sign of the combined gradient. Multiplying one global loss changes a coordinate
only when that loss overtakes all competing objective terms on that coordinate.
The `0.10` to `0.25` increase therefore changes almost no proposal geometry;
`0.50` changes some signs but still leaves six unavoidable crossings.

## Impact

- N6 D1 cannot advance to a 10-step run.
- Step backoff is a safety mechanism, not a cure for an inward direction.
- Further scalar ratio, LR, seed, or E4-repair sweeps would not answer the local
  control defect and are prohibited.
- The final E0-E4 matrix remains blocked upstream of repair and scoring.

## Required Remediation

Add default-off pair-local contact-normal observability and control at explicit
accepted-step boundaries:

1. For every near/contact pair, serialize clearance, differentiable SDF normal,
   movable/frozen roles, base-objective relative drive, collision contribution,
   and predicted proposal normal displacement.
2. Replace the single global guarantee with deterministic bounded per-pair or
   per-contact-component control. Every protected pair must have non-penetrating
   predicted relative motion before the exact guard is asked to accept it.
3. Account for the actual Adam proposal, not only raw aggregate gradient norms;
   resolve shared-node contact constraints deterministically.
4. Keep geometry preprocessing outside autograd and tensor-only evaluation on
   the active device. Exact Shapely validation remains outside autograd and
   authoritative.
5. Preserve full optimizer rollback, hard keep-in projection, default-off
   parity, and fail-closed behavior. Do not introduce packing, CP-SAT, or a
   checkpoint fallback.

## Acceptance Criteria

- Two-body tests cover all four approach directions, unequal and concave
  footprints, and movable-to-frozen obstacles.
- A multi-contact chain test proves one shared node cannot satisfy one pair by
  driving another pair inward.
- Per-pair diagnostics agree with finite differences and the actual Adam
  proposal direction on CPU and GPU.
- Feature-off objective, placement, and legacy benchmark evidence remain
  byte-identical.
- Checkpoint-warm E2 and E3 seed-1000 one-step runs accept an exact-legal native
  step at LR scale `1` without E4 or fallback.
- The subsequent D1 10-step runs retain zero exact overlap after every accepted
  step, regress native HPWL/RSMT by at most `0.5%`, and keep measured overhead
  within `2x` of the corresponding feature-off optimization path.
