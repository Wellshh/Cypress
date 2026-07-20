# M336-159: Bounded Repair Discards Legal Start

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

E4 correctly limits repair to the exact conflict closure, but repacks every
component in that closure from the feasible-site domain. It ignores that the
same native run began from an exact-legal placement. Tiny optimizer-induced
overlaps can therefore trigger a large discrete rearrangement.

## Evidence

The corrected `0.05 mm` seed-1000, 10-iteration warm E4 run found 28 overlaps
across a 45-component closure. Repair moved all 45 components, with mean
displacement `18.3902` and maximum displacement `147.5662` Cypress units. It
removed all overlaps but changed in-memory HPWL from `15632.6875` to
`16064.5684` (`+431.8809`) and consumed `9.420 s`. Serialized native score fell
to `0.903330`.

## Impact

- Exact legality is achieved by materially destroying native placement quality.
- Repair dominates warm runtime and risks failing the `E4 <= 2x E0` gate.
- A small continuous proposal is converted into a much larger topology change.

## Remediation

Capture the exact-legal constrained coordinates after initialization. During
E4, first restore only the detected conflict closure to those same-run legal
coordinates and audit the result. Use the existing bounded packer only if that
local restore cannot close legality. Never restore all coordinates silently;
serialize the selected strategy, scope, displacement, and HPWL delta.

## Acceptance Criteria

- E4 still ends with 100/100 containment and zero overlaps.
- Restore touches only the reported conflict closure.
- A successful restore does not invoke the packing fallback.
- Repair strategy and fallback reason are serialized.
- Warm E4 repair no longer materially degrades M336-118 HPWL/RSMT.

## Resolution

Initialization now captures the same run's exact-legal constrained centers.
E4 first restores the detected conflict closure to those centers, re-audits
exact geometry, and expands only to newly induced conflict nodes. The restore
is bounded to 64 components and four rounds; a failed restore rolls the proposal
back before the existing bounded pack fallback. Tests cover direct restore,
closure expansion, and fail-closed component-limit rollback.

The corrected seed-1000 warm E4 10-step run began with 28 overlap pairs across
a 45-component closure. Restore added only `C608`, `R601`, and `R702`, ending in
two rounds with 48 components. It took `0.0584 s`, did not invoke packing, and
reduced in-memory HPWL from `15632.6875` to `15632.2598`. Post-serialization
validation reported 100/100 containment and zero overlaps; native HPWL/RSMT
were `15632.260310` and `17328.977`, for normalized score `0.928024`.
