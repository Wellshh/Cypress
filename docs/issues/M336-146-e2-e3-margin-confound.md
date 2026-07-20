# M336-146: E2/E3 Comparison Confounds Anchor and Keep-in Margin

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `f307b4c`

## Problem

The experiment matrix defines E2 as hard projection without the differentiable
keep-in margin, while E3 enables both the margin and anchor loss. Consequently,
an E3-versus-E2 result cannot attribute changes in anchor distance, projection
pressure, overlap, or quality to the anchor objective. This became observable
in the 50-iteration M336-145 diagnostic: E3 reduced projection events and
overlap area substantially, but the active margin was absent from E2.

## Remediation

Treat the interior margin as part of the keep-in objective. Enable the same hard
projection and margin settings in E2 and E3, with anchor loss as their only
behavioral difference. Add a contract test that fails if another feature flag
diverges between the two experiments.

## Acceptance Criteria

- E2 and E3 share projection, margin, initialization, frozen-anchor, repair,
  and integrated-context settings.
- Their only behavioral feature difference is anchor loss.
- A same-input, same-seed E2/E3 diagnostic reports native backward and optimizer
  evidence for both runs.
- Historical confounded results remain preserved but are not cited as anchor
  effectiveness evidence.

## Resolution Evidence

E2 now enables the same differentiable margin as E3. A contract unit test
compares every experiment field and permits only `name` and `anchor_loss` to
differ. The corrected seed-1000, 50-iteration H100 comparison is stored under
`results/m336/native-cypress/n2-anchor-final-isolated-diagnostic-50/`; both runs
execute 53 backward calls and 50 optimizer steps, use identical input hashes,
and finish 100/100 contained with zero keep-in violations.

The corrected result attributes only `0.0934%` mean and `0.00288%` p90 anchor
improvement to ratio-`0.10` anchor control. Earlier hard-only E2 comparisons are
retained as margin ablations, not anchor-effectiveness evidence.
