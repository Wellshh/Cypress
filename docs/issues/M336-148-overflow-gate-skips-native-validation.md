# M336-148: Overflow Gate Skips Native Validation

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `91fb33c` plus uncommitted M336-147 work

## Problem

`NonLinearPlace` returns infinite HPWL/RSMT immediately when final overflow is
above `stop_overflow`. That return occurs before anchor/keep-in exact validation
and native scoring. In the corrected M336-147 seed-1000 E2 smoke, the native
path completed 13 backward calls and 10 coordinate-changing Adam steps and
reduced projection events from 4 to 0, but usable-capacity-normalized overflow
was `1.583530`. The early return suppressed `legality.json`, HPWL, and RSMT.

`Placer.py` then logged `placement failed` but exited with status zero. The M336
runner rejected the run only because the required legality artifact was absent.

## Remediation

Keep the existing production divergence behavior by default. Add an explicit,
default-off diagnostic flag that permits an integrated anchor/keep-in run with
finite objective and finite coordinates to continue through exact validation,
serialization, native HPWL, and FLUTE RSMT despite high overflow. NaN or
infinite objectives must still fail immediately. The runner must continue to
require legality and finite native scores, so a zero process exit cannot turn a
failed placement into evidence.

## Acceptance Criteria

- Feature-off and ordinary production runs retain the existing overflow gate.
- The M336 diagnostic contract records that high-overflow continuation is on.
- NaN/infinite objectives still stop before scoring.
- High-overflow M336 runs emit exact legality and finite native HPWL/RSMT.
- A missing legality report or non-finite score remains a runner failure.

## Validation

The continuation flag is default-off and is honored only when an integrated
anchor/keep-in context exists. Non-finite objectives retain the original early
failure path. The M336 runner enables the flag explicitly and independently
rejects missing legality or non-finite HPWL/RSMT.

The corrected M336-147 E2 diagnostics reached exact post-serialization
validation despite final normalized overflow above `1.58`. The 10-step run
reported 100/100 containment, zero keep-in violations, finite HPWL
`24279.9531`, and finite RSMT `25881.6719`. The 50-step run again reported
100/100 containment and finite HPWL/RSMT `24255.8145/25853.2383`. This closes
the evidence gap without weakening ordinary production divergence handling.
