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

## Impact

- The 25%/15% anchor gate is unattainable under the measured step envelope.
- Further ratio increases would be tuning without a displacement mechanism.
- E4 repair cannot legitimately supply the missing movement because that would
  replace native Cypress optimization with exact packing.

## Remediation

Record the effective estimated learning rate and cumulative/net displacement per
run. Then test a bounded native step-scale policy on seed 1000, with projection,
overlap, HPWL/RSMT, and objective stability gates. Candidate changes must remain
inside `NonLinearPlace -> PlaceObj -> backward -> optimizer.step`; no coordinate
teleport, checkpoint fallback, or exact-site closure may count as improvement.

## Acceptance Criteria

- Effective learning rate and per-step/cumulative/net displacement are serialized.
- A bounded policy makes the 50-step displacement envelope large enough for the
  requested mean reduction without non-finite objectives.
- E3 remains 100/100 contained and reduces overlap pressure rather than handing
  a larger conflict closure to E4.
- Native HPWL/RSMT and runtime are reported against unchanged E2.
