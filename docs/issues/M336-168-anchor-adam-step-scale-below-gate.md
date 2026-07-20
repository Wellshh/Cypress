# M336-168: Native Adam Step Scale Cannot Reach the Anchor Gate

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `5ad8029`

## Problem

The native E3 objective has a valid anchor gradient, but the estimated Adam step
scale is too small to produce the required physical displacement within the
50-iteration diagnostic budget. Increasing the bounded anchor gradient ratio
changes direction and lambda, not the observed proposal-distance envelope.

## Evidence

All checkpoint-warm seed-1000 E3 runs at ratios `0.05`, `0.10`, `0.25`, and
`0.50` execute 50 changing Adam steps and report the same maximum single-step
proposal distance: `0.0439360403` Cypress units. With alignment scale
`19.9978521 units/mm`, even the impossible best case where every component moves
that maximum distance directly toward its anchor on every step has a cumulative
path bound of about `0.10985 mm`.

The mean acceptance gate requires reducing E2 from `6.515852 mm` to
`4.886889 mm`, a displacement of at least `1.628963 mm`. The required reduction
is therefore `14.83x` larger than the observed 50-step path upper bound. The p90
gate requires `1.804921 mm`. The ratio sweep's strongest actual mean reduction
is only `0.008886 mm`.

`NonLinearPlace` estimates learning rate before the first explicit
`update_anchor_weight()` call. Warm-up makes the initial anchor weight zero, and
Adam further normalizes gradient magnitude, explaining why a 10x ratio range
does not materially enlarge proposals.

Native instrumentation now serializes every learning-rate update and optimizer
step, plus cumulative proposal path, accepted path, and net displacement for all
movable and constrained nodes. The checkpoint-warm seed-1000 10-step E3 smoke
records requested/effective learning rates of `0.01/0.02308556`. Across the 100
constrained nodes, the mean accepted path is only `0.01194159 mm` and the mean
net displacement is `0.01157887 mm`; net/path is `96.96%`. The maximum accepted
path is `0.01625257 mm`. Direction cancellation is therefore minor at 10 steps;
the physical step scale is the dominant limitation.

The instrumentation is read-only: placement and replay retain SHA-256
`a6445d6a...`, HPWL/RSMT remain `15632.686697721481/17325.676`, and normalized
score remains `0.9281007794550066`. The run executes 13 backward calls and 10
changing Adam steps with 100/100 containment, zero keep-in violations, zero
projection events, and the same 28 unaccepted overlaps.

The unchanged committed 50-step control at `ae9db57` exactly reproduces the
earlier ratio-`0.10` placement SHA `954d1aa2...`, anchor metrics, HPWL/RSMT
`15632.495737791061/17356.65`, score `0.9272707812261448`, and 71 overlaps. Its
effective LR remains `0.02308556`. The constrained mean accepted path is
`0.05143600 mm` and mean net displacement is `0.05067488 mm`, for `98.52%`
net/path efficiency. The required `1.62896303 mm` mean anchor reduction is
`32.15x` the measured mean net displacement.

Only `0.00330937 mm`, or `6.53%` of mean net displacement, becomes mean physical
anchor-distance improvement. The optimizer therefore has both a scale deficit
and weak anchor-direction yield; increasing LR alone is not sufficient evidence
of progress.

## Impact

- The 25%/15% anchor gate is unattainable under the measured step envelope.
- Further ratio increases would be tuning without a displacement mechanism.
- E4 repair cannot legitimately supply the missing movement because that would
  replace native Cypress optimization with exact packing.

## Remediation

The required instrumentation and unchanged 50-step control are complete. Add a
feature-gated, bounded initial-LR scale and test `2/4/8/16/32` on seed 1000,
stopping on non-finite objectives, keep-in failure, or unacceptable overlap and
native-score regression. Candidate changes must remain inside
`NonLinearPlace -> PlaceObj -> backward -> optimizer.step`; no coordinate
teleport, checkpoint fallback, or exact-site closure may count as improvement.

## Acceptance Criteria

- Effective learning rate and per-step/cumulative/net displacement are serialized.
- A bounded policy makes the 50-step displacement envelope large enough for the
  requested mean reduction without non-finite objectives.
- E3 remains 100/100 contained and reduces overlap pressure rather than handing
  a larger conflict closure to E4.
- Native HPWL/RSMT and runtime are reported against unchanged E2.
