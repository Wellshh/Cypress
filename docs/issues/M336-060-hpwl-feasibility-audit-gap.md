# M336-060: HPWL Feasibility Results Bypass Replay Audit

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `b138922`

## Problem

The exact-site probe constructs integer HPWL variables when
`M336_MINIMUM_SCORE` or `M336_INTEGER_HPWL_CEILING` is set, even if HPWL is not
the optimization objective. Those runs were labeled `objective_mode=none` and
did not execute objective replay. The native scorer required replay only for
`objective_mode=hpwl`, so a feasible hard-constraint result could bypass the
variable-to-site consistency gate.

During review, a second issue was found: per-net solver-versus-replay
mismatches were recorded but were not included in the audit's `passed`
condition. Equal and opposite per-net errors could leave the total unchanged
and pass.

## Impact

Geometry and floating HPWL were independently recomputed, but the hard integer
ceiling itself was not proven to apply to emitted selected sites. This is the
same trust boundary affected by postsolve response metadata under M336-051.
Threshold evidence therefore needed an explicit fail-closed feasibility audit.

## Mitigation

Hard HPWL models without an objective now use
`objective_mode=hpwl_feasibility`. Their replay audit does not require a
response objective; it requires solved max/min totals to equal selected-site
integer replay, every per-net value to match, candidate coordinates to match,
floating HPWL to remain within the rounding allowance, and selected-site HPWL
to satisfy the effective integer limit. Missing or failed audits are rejected
by `score_exact_site_result.py` for both HPWL modes.

## Verification

The M336 suite passes 44/44. Tests cover no-response-objective replay,
ceiling violation, canceling per-net mismatches, and scorer rejection of
missing or failed feasibility audits.

An all-fixed integration replay used ceiling `15835344206` without an
optimization objective. It returned `OPTIMAL` with mode `hpwl_feasibility`;
solved-variable and selected-site HPWL equal the ceiling, all per-net values
match, floating delta is `0.000010071333`, and exact legality is 100/100 with
zero violations and overlaps. Result and placement SHA-256 values are:

- `7bcdd9f463803fb28ca7add077d31bc8afb89b8fd508dc957ca13ccecc088c8c`;
- `a44942bee4ba8c1bf275ef08177ed359de588b8045907e2b3853d3f5a0a179c6`.

## Next Action

Run the K256 physical closure as pure feasibility with the previously tested
-5 HPWL ceiling, repair disabled, one worker, and seed 1000. Any returned
placement must pass the new audit and all-fixed certification. Keep a
budget-limited no-incumbent result as `UNKNOWN`.

## K256 Feasibility Result

The 10,810-candidate K256 physical model was run at ceiling `15830344206`
without an optimization objective. It returned `UNKNOWN` without an incumbent
after 327.415580 wall seconds and 300.000092 deterministic-time, with 729,297
conflicts and 1,288,806 branches. Response objective and best bound are
correctly absent in `hpwl_feasibility` mode. Result SHA-256 is
`9e1ebc124db230104b840382345b4f703c614a1c62152768e64d4a4a06702f1b`.

The matched optimization run also returned `UNKNOWN`, using 362.096764 wall
seconds, 812,171 conflicts, and 2,573,303 branches. Pure feasibility removes
34.681184 wall seconds and roughly half the branches but does not find the -5
step. This remains a budget-limited search result, not a restricted-domain
proof. Change guide ordering or search strategy before repeating the model.
