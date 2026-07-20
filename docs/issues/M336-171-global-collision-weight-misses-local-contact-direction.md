# M336-171: Global Collision Weight Misses Local Contact Direction

**Severity:** Critical
**Status:** Resolved for D1; D2-D4 remain active under N6
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

## Pair-Local Diagnostic Evidence

A separate, default-off guard diagnostic now samples the pair field at the
accepted origin and the actual Adam proposal. It records both endpoints'
movable roles, clearance and SDF normal, base/collision/total raw normal drive,
preconditioned optimizer drive, actual relative displacement, and
proposal-side clearance/normal. Geometry remains outside autograd; the
diagnostic is tensor-only and runs only after a guarded proposal.

The checkpoint-warm E3 seed-`1000` ratio-`0.10` one-step replay examined 200
near pairs per retry, with 199 valid origin normals. Retry 0 crossed ten exact
pairs. Nine were driven into the origin SDF normal by approximately
`0.002307-0.002309 mm`; representative local drives are:

| Pair | Base raw | Collision raw | Adam proposal normal (`mm`) |
| --- | ---: | ---: | ---: |
| `C501/R704` | `-0.182024` | `+0.031130` | `-0.002307` |
| `C605/C606` | `-0.294550` | `+0.020458` | `-0.002307` |
| `C611/C612` | `-0.293086` | `+0.006562` | `-0.002307` |
| `FV703/R707` | `-0.311060` | `+0.039653` | `-0.002309` |

Positive collision drive is separating; negative base drive is penetrating.
The base objective therefore exceeds the local barrier by about `6x-45x` on
the observed crossing contacts, even though the global L1 ratio is satisfied.

`C8605/C8621` exposes a second, independent limitation. Its origin and proposal
SDF values are both `-0.025 mm` with normal `[1, 0]`; Adam moves the pair
`[0, +0.002309] mm`, so origin-normal displacement is exactly zero. The exact
validator nevertheless reports `0.000115445 mm2` positive overlap. A single
nearest-face SDF normal therefore cannot protect a nonsmooth edge/corner from
tangential entry. Per-pair scalar reweighting alone cannot solve this case.

The run fails closed after `10/10/10/10/9` overlap pairs across the five
backoffs; every position and optimizer rollback is exact. Evidence artifact:

```text
results/m336/native-cypress/m336-171-pair-diagnostics-v3-ratio-01-1/
  checkpoint_warm_start/E3/seed_1000/constraints/
  exact_step_guard_failure.json
SHA-256 0a8031e0f79d283c7c8706dcf5b9fdebe3cfcc30f4361897adf7b61b99e4d006
canonical pair-contact SHA-256
75eda9fb7fc389c9e1142e29ac70f36a0fa39fc747091ce6181921dc5d302ab6
```

The same run with `--no-collision-pair-diagnostics` produces no pair rows and
a `48,081`-byte artifact instead of `2,084,299` bytes. Its canonical exact
proposal/rollback SHA-256 is identical to the diagnostic run:
`1e2b94ab16a225be1f3fd3f0c1b54ffdc1f3eb73626f29adcbc96c89b4284354`.
Thus normal guard execution does not pay the extra autograd, SDF sampling, or
serialization cost.

Reproduce the diagnostic by adding the following flag to the bounded command
contract above:

```text
--collision-pair-diagnostics
```

This completes observability only. N6 remains open; no step was accepted and
no placement or quality improvement is claimed.

## Candidate-Side Contact Control

A default-off exact contact projector now runs between the normal hard
keep-in projection and guard acceptance. It does not create sites, search a
placement, or invoke repair. Starting from the actual Adam proposal, it:

1. asks the exact validator for newly crossing pairs;
2. builds their deterministic contact-component closure;
3. projects each active component onto one shared displacement, using an
   inactive endpoint's displacement as authoritative when present;
4. reapplies the normal hard constraints and repeats exact validation;
5. returns the candidate to the transactional guard, which remains the final
   authority and rolls back on any residual violation.

The operation is bounded at eight closure iterations and 32 contact nodes. A
limit, immutable crossing, or stalled closure remains illegal and is not
silently repaired. Seven focused tests cover four approach directions,
movable-to-frozen contact, a shared-node chain, iterative closure, node-limit
failure, legal no-op behavior, and byte-identical CPU/GPU coordinates.

The checkpoint-warm E3 seed-`1000` one-step run at ratio `0.10` and LR scale
`1` now accepts retry 0. Its raw Adam proposal has the same ten exact crossings
and `0.008031909 mm2` area as the prior failure. One bounded projection builds
seven components containing 17 active nodes, then returns zero overlaps and
zero keep-in violations. The guard accepts the candidate without backoff:

| Metric | Result |
| --- | ---: |
| Native backward calls / changing Adam steps | `4 / 1` |
| Proposal / accepted constrained movers | `100 / 98` |
| Contact correction mean / max | `0.025458 / 0.034393` Cypress units |
| Exact containment / keep-in / overlap | `100/100 / 0 / 0` |
| Native HPWL / FLUTE RSMT | `15633.827651 / 17332.127` |
| Normalized native score | `0.9278930424` |
| End-to-end / GPU optimization | `12.6702 / 1.06365 s` |
| Guard / contact-control time | `0.14961 / 0.03567 s` |

Relative to repeated M336-118 native scoring, HPWL improves by about `0.623`,
RSMT by `0.910`, and normalized score by `0.00004289`. E4 is disabled and no
checkpoint fallback is used. Placement SHA-256 is
`e7baf248073a5eb010db3c40d5fca6e22bb3a00a28c30aeb92ad9b78fc72c086`.

Evidence:

```text
results/m336/native-cypress/m336-171-contact-projection-e3-1/
summary.json
SHA-256 f238ed4b57c9c8c67f9dae002f96b0f470d345b06ce76a1511d1da735b4ac468

checkpoint_warm_start/E3/seed_1000/constraints/exact_step_guard.json
SHA-256 6b36507463be8a01aa19ad6a178104a465eea370f30393af808eb931e7d01ea2
```

```bash
env CUBLAS_WORKSPACE_CONFIG=:4096:8 CUDA_VISIBLE_DEVICES=2 \
  PYTHONPATH="$PWD/install:$PWD:/tmp/m336-ortools-py311" \
  python3.11 experiments/m336/scripts/run_matrix.py \
  --experiments E3 --seeds 1000 --iterations 1 \
  --learning-rate-scale 1 --gpu --irregular-density \
  --footprint-collision --collision-gradient-ratio 0.1 \
  --collision-margin-mm 0 --collision-tau-mm 0.025 \
  --exact-step-guard --exact-step-guard-backoff 0.5 \
  --exact-step-guard-max-retries 4 --collision-pair-diagnostics \
  --exact-contact-projection \
  --exact-contact-projection-max-iterations 8 \
  --exact-contact-projection-max-nodes 32 \
  --initialization-track checkpoint_warm_start \
  --output-dir results/m336/native-cypress/m336-171-contact-projection-e3-1
```

The matching `--no-exact-contact-projection` run still fails closed with the
unchanged canonical proposal/rollback SHA-256
`1e2b94ab16a225be1f3fd3f0c1b54ffdc1f3eb73626f29adcbc96c89b4284354`.
This is a one-step promotion signal only. N6 and D1 remain open until both warm
E2 and E3 retain exact legality for ten accepted native steps with bounded
quality and runtime.

## D1 Three-Arm Validation

Commit `bf67663` was evaluated on physical GPU 2 with deterministic CuBLAS,
checkpoint-warm initialization, seed `1000`, ten Adam steps, LR scale `1`, and
the same float64 scoring and exact post-serialization path. E2 and E3 differ
only by the anchor objective. The three D1 arms were feature-off, collision
barrier only, and barrier plus bounded contact projection plus exact guard.

| Arm | Run | Final pairs / area (`mm2`) | Native HPWL / RSMT | Score | GPU / end-to-end (`s`) |
| --- | --- | ---: | ---: | ---: | ---: |
| Feature off | E2 | `24 / 0.106247` | `15632.983130 / 17327.078` | `0.9280541970` | `1.08086 / 11.7539` |
| Barrier only | E2 | `33 / 0.095247` | `15633.117228 / 17327.220` | `0.9280464153` | `1.36448 / 12.2037` |
| Contact + guard | E2 | `0 / 0` | `15632.422267 / 17327.278` | `0.9280653090` | `1.81014 / 13.3712` |
| Feature off | E3 | `28 / 0.108631` | `15632.686698 / 17325.676` | `0.9281007795` | `1.34785 / 11.8590` |
| Barrier only | E3 | `33 / 0.098745` | `15632.979651 / 17326.097` | `0.9280807866` | `1.51287 / 12.6521` |
| Contact + guard | E3 | `0 / 0` | `15632.448100 / 17327.786` | `0.9280508327` | `2.06893 / 14.0294` |

The barrier-only arm reduces positive overlap area slightly but increases pair
count to 33 in both experiments. It is therefore not a legality mechanism.
The contact-control arm receives raw proposals containing `10-16` E2 and
`10-17` E3 overlap pairs, yet every accepted placement has zero overlap and
zero keep-in violations. Both runs execute 13 backward calls and ten changing
CUDA Adam steps; E4 and checkpoint fallback are disabled.

E2 accepts all ten first attempts. E3 rejects one iteration-6 attempt after a
32-node contact closure stalls on `C404/FV708` with residual area
`0.0000106471 mm2`. The transactional guard restores the complete position and
optimizer state, halves the LR from `0.02308556` to `0.01154278`, and accepts
the retry after closing 14 raw crossings. This is the intended fail-closed
backoff path, not repair.

Against the corresponding feature-off controls, E2 HPWL improves `0.00359%`
while RSMT regresses `0.00115%`; E3 HPWL improves `0.00153%` while RSMT
regresses `0.01218%`. GPU optimization ratios are `1.675x` and `1.535x`, and
end-to-end ratios are `1.138x` and `1.183x`. These pass the D1 `0.5%` quality
and `2x` runtime gates. The current-head feature-off E3 placement SHA-256 is
the byte-identical M336-169 value
`a6445d6a98180ff4449afdffe37ad313f5215cd336153030c5637aaa10b94c5c`.

The E3 anchor mean and p90 are `0.00179%` and `0.00478%` worse than E2. D1
validates safe native motion only; it does not satisfy the downstream anchor
quality gate. D2 must test LR scale `2` exactly once under the same contact
contract and stop if projection pressure, native score, or anchor direction
fails its declared gates.

The ignored evidence roots are:

```text
results/m336/native-cypress/m336-171-contact-projection-d1-feature-off-warm-10-1/
results/m336/native-cypress/m336-171-contact-projection-d1-barrier-only-warm-10-1/
results/m336/native-cypress/m336-171-contact-projection-d1-warm-10-1/
```

All arms use this common contract, with the arm flags and output path changed
as shown below:

```bash
env CUBLAS_WORKSPACE_CONFIG=:4096:8 CUDA_VISIBLE_DEVICES=2 \
  PYTHONPATH="$PWD/install:$PWD:/tmp/m336-ortools-py311" \
  python3.11 experiments/m336/scripts/run_matrix.py \
  --experiments E2 E3 --seeds 1000 --iterations 10 \
  --learning-rate-scale 1 --gpu --irregular-density \
  --initialization-track checkpoint_warm_start \
  <arm-flags> --output-dir <output-path>
```

```text
feature off:
  --no-footprint-collision
barrier only:
  --footprint-collision --collision-gradient-ratio 0.1
  --collision-margin-mm 0 --collision-tau-mm 0.025
  --no-collision-pair-diagnostics --no-exact-step-guard
  --no-exact-contact-projection
contact + guard:
  --footprint-collision --collision-gradient-ratio 0.1
  --collision-margin-mm 0 --collision-tau-mm 0.025
  --no-collision-pair-diagnostics --exact-step-guard
  --exact-step-guard-backoff 0.5 --exact-step-guard-max-retries 4
  --exact-contact-projection --exact-contact-projection-max-iterations 8
  --exact-contact-projection-max-nodes 32
```

Evidence hashes:

```text
contact + guard summary
cce933f66bd76cd7c3c70ec49e3b1dd82d5bd61dae8595dbb14f19fae8aea3d4
E2 exact guard
4a95f5f42c39fe4b710c53c793fa4b9dfa2e4db1b6602d21bca242720585f734
E3 exact guard
e2557247783b7c4d51c2756cca838ec4facb1e2a14e928cd2ce3c1ec133bb3e1
feature-off summary
54b7447e8e07a6de3c297c0a4e90ed5cf6ec56b7591f60b74dc2c35b1899b28d
barrier-only summary
ee9e71df180fa922d34777fa91edd908f803e24a03735acfb8245d3ae38ec9cc
```

M336-171 is resolved for its stated D1 acceptance criteria. N6 remains active
at D2; this resolution does not authorize larger LR, scalar-weight, seed, or
repair ladders.

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

## Impact At Discovery

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

The control must use more than one origin SDF normal at nonsmooth contacts. A
candidate-side active set, conservative contact cone, or exact-validator-derived
local separating cut is required for tangent-entry cases such as
`C8605/C8621`; blind pair-weight escalation is prohibited.

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
