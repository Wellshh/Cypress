# M336-170: Exact Accepted-Step Overlap Guard Is Missing

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `bf5fe69`

## Problem

The native optimizer accepts a proposal after board and irregular keep-in
projection without first enforcing exact same-side footprint legality. The
existing `exact_overlap_diagnostic_interval` calls `exact_overlap_report()` only
after `optimizer.step()` has been recorded as accepted. It can describe a
crossing step, but it cannot reject that step or keep the next gradient
evaluation on the last legal placement.

The default-off footprint barrier from M336-169 is an approximate preventive
signal. Its one-step smoke reduced exact overlap area by `19.03%`, but still
accepted 10 overlap pairs. It therefore cannot be the final legality mechanism.

## Evidence

The checkpoint-warm scale-1 control starts with zero exact overlap, accepts 11
overlap pairs on Adam step 1, and reaches 28 pairs plus `0.108631214178 mm2` by
step 10. In `NonLinearPlace.one_descent_step()`, the current order is:

```text
optimizer.step()
-> hard projection
-> finish_step()
-> optimizer-state cleanup for projected coordinates
-> displacement and accepted-step accounting
-> optional exact overlap diagnostic
```

The exact result arrives after acceptance and cannot trigger rollback.

Rollback is not safely provided by the existing optimizer restart path. Adam
and SGD store moments in `optimizer.state`, while the custom Nesterov optimizer
stores `u_k`, `v_k`, `g_k`, `alpha_k`, line-search history, and counters inside
`param_groups`. Its `v_k` entry aliases the live placement parameter. A naive
deep copy and reload can lose that alias or restore only part of the transition.

## Impact

- A legal warm start can become illegal on the first native GPU step.
- Later objective and gradient evaluations operate on an already overlapping
  placement.
- E4 repair or checkpoint fallback would conceal an upstream optimizer defect.
- Barrier-only improvements cannot satisfy the native Cypress legality gate.

## Required Remediation

Add a default-off exact accepted-step guard at the optimizer boundary. For each
attempt it must snapshot the complete pre-step position and optimizer state,
execute the native step, retain the raw proposal, apply hard projection, and run
the exact side-local Shapely validator outside autograd. A candidate with any
positive-area same-side overlap or keep-in violation must be rejected.

On rejection, restore position and optimizer state byte-for-byte, verify both
restorations before changing control state, reduce the step size by a bounded
backoff (initially `0.5`), and retry from the same pre-step state up to four
times. Nesterov backoff must scale its active `alpha_k` line-search hint as well
as the nominal group learning rate. Exhaustion must write a structured failure
artifact and raise; it must not invoke packing, CP-SAT, E4, or a checkpoint
fallback.

Serialize every attempt with before/proposal/projected exact metrics, newly
crossing pairs and areas, requested and effective step size, barrier diagnostics,
displacement, rollback hashes, restoration status, elapsed time, and final
accept/reject reason. Reuse the accepted guard report for interval diagnostics
instead of performing a duplicate exact check.

## Acceptance Criteria

- A crossing proposal is rejected and the accepted position remains exact legal.
- Adam and custom Nesterov position/state rollback are byte-consistent before
  the intentional step-size backoff.
- A legal retry is accounted as one accepted optimizer step, not several steps.
- Retry exhaustion fails closed with a replayable structured artifact.
- Feature-off placement and metrics remain byte-identical.
- Warm E2 and E3 10-step barrier-plus-guard runs retain zero overlap and zero
  keep-in violations after every accepted step.
- Native HPWL/RSMT regression is at most `0.5%` and per-step overhead is at most
  `2x` versus the same-run feature-off control before expanding the experiment.

## Prototype Integration Evidence

The default-off transactional guard now snapshots parameter values and
gradients, ordinary optimizer state, and custom Nesterov group state while
preserving the `v_k` parameter alias. CPU Adam/Nesterov tests and a CUDA Adam
test restore identical position and optimizer SHA-256 values. A synthetic
crossing test rejects the first SGD proposal, restores both hashes, applies a
`0.5` backoff, and counts the legal retry as one accepted step. Retry exhaustion
also restores the original transition before failing.

A fresh feature-off M336 E3 10-step run reproduced the previous control exactly:
placement SHA-256 `a6445d6a98180ff4449afdffe37ad313f5215cd336153030c5637aaa10b94c5c`,
HPWL `15632.686697721481`, RSMT `17325.676`, all anchor statistics, and every
step-0 through step-10 exact overlap count and area. The guarded code path
therefore does not perturb disabled execution.

The first GPU 2 E3 barrier-plus-guard integration probe failed closed as
required. Starting legality was zero overlap and zero keep-in violation. All
five ratio-`0.1` Adam attempts crossed the same contact boundary:

| Retry | Effective step | Exact pairs | Exact area (`mm2`) | Rollback |
| ---: | ---: | ---: | ---: | --- |
| `0` | `0.02308556` | `10` | `0.008031909` | position/state exact |
| `1` | `0.01154278` | `10` | `0.004013190` | position/state exact |
| `2` | `0.005771390` | `10` | `0.002013371` | position/state exact |
| `3` | `0.002885695` | `10` | `0.001000254` | position/state exact |
| `4` | `0.001442848` | `9` | `0.000501145` | position/state exact |

Every projected candidate retained zero keep-in violations. The nearly linear
area reduction proves backoff shrinks the crossing but does not change its
direction. No optimizer step was accepted and no E4 or checkpoint fallback ran.
The durable failure artifact is
`results/m336/native-cypress/m336-170-guard-smoke-1/checkpoint_warm_start/E3/seed_1000/constraints/exact_step_guard_failure.json`.
M336-170 remains open until the preventive objective supplies a legal native
direction and the 10-step gate passes.

## Guard Confirmation Under Bounded Ratios

M336-171 repeats the one-step guard at collision ratios `0.25` and `0.5`. All
ten additional candidates are rejected with zero keep-in violations and exact
position/optimizer rollback. The ratio-`0.5` signal removes four final crossing
pairs relative to ratio `0.1`, but six remain and the run still fails closed.

This confirms that M336-170 now enforces its safety invariant; it does not claim
the D1 acceptance gate. The active blocker has moved to M336-171's pair-local
contact direction, while the guard remains required for every subsequent run.
