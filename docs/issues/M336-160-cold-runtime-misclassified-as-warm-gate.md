# M336-160: Cold Runtime Is Misclassified as Warm Gate

**Severity:** Medium
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c` plus uncommitted N4 runner work

## Problem

The native acceptance report applies `E4 runtime <= 2x E0` to every
initialization track. The governing contract defines that gate only for the
M336-118 warm-cache track because cold/source E4 includes exact initialization
repair that E0 does not execute.

## Evidence

The seed-1000 cold/source 10-step matrix reports E0 end-to-end runtime
`9.8588 s` and E4 `67.4227 s`, a ratio of `6.8388x`. E4 includes `54.9302 s`
of initialization for a 96-component illegal/conflict closure. The generated
summary labels `runtime_at_most_2x = false`, even though this is not the
specified warm-cache acceptance comparison. The separate warm matrix reports
E0 `9.4035 s`, E4 `13.8934 s`, and the applicable ratio `1.4775x`.

## Impact

- The report presents a false hard-gate failure for the cold diagnostic track.
- Reviewers may compare unequal runtime denominators.
- The real cold initialization bottleneck is obscured by the wrong gate label.

## Remediation

Keep E4/E0 runtime ratio in every track as a diagnostic. Evaluate the 2x gate
only when all summarized runs are `checkpoint_warm_start`; serialize `null` and
report it as not applicable for cold/source or mixed tracks. Continue reporting
cold initialization performance under M336-005.

## Acceptance Criteria

- Warm summaries evaluate the 2x gate normally.
- Cold summaries retain the ratio but mark the gate not applicable.
- A focused test covers both track semantics.
- Reports do not remove cold preprocessing or initialization time.

## Resolution

Acceptance aggregation now evaluates the 2x gate only when every summarized
run is `checkpoint_warm_start`. Cold and mixed summaries retain the measured
ratio but serialize the gate as `null`; the Markdown report labels it
`NOT APPLICABLE` without removing any timing stage. A focused test covers warm
pass/fail and cold not-applicable behavior. Regenerating the cold summary keeps
its `6.8388x` diagnostic ratio while clearing the false hard-gate failure.
