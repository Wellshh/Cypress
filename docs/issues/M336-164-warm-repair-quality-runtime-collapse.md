# M336-164: Warm E4 Repair Collapses Quality and Runtime

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `cc05a44`

## Problem

M336-159 resolves small 10-step closures through same-run legal restoration,
but the 50-step warm closure exceeds its 64-component bound. E4 then falls back
to deterministic packing of nearly the entire constrained placement. The output
is exact legal but no longer a bounded local repair of the native result.

## Evidence

The seed-1000 warm E4 state before repair has 71 overlap pairs and an
83-component conflict closure. Same-run restoration proposes 86 components,
leaves six conflicts, and stops with `restore_component_limit`. The fallback:

- packs and moves all 83 closure components;
- takes `21.1286 s`;
- has mean/max displacement `30.1300 / 149.1160` Cypress units;
- changes HPWL from `15632.4961` to `17118.0820`, a `+1485.5859` regression;
- reduces normalized native score from the pre-repair E3 neighborhood
  (`0.927271`) to `0.850668`;
- makes warm E4 take `34.9469 s`, or `3.3963x` E0.

## Impact

Legality is obtained by replacing the native topology with a broad packed
topology. This fails both the quality and warm runtime gates and cannot count as
Cypress improvement evidence.

## Remediation

Fix the upstream overlap growth under M336-163 so restoration remains local.
Fail closed rather than promote a broad fallback that violates an explicit HPWL
or scope ceiling. Serialize the restoration limit, proposed closure, residual
conflicts, packing scope, and quality delta. Increasing the component cap to
restore the whole exact checkpoint is not an acceptable fix.

## Acceptance Criteria

- Warm E4 ends exact legal without broad checkpoint restoration.
- Repair scope stays within the declared local bound.
- Repair HPWL/RSMT degradation is explicitly bounded and replayed.
- Warm E4 end-to-end runtime is at most `2x` E0 under the same contract.
- Exact checkpoint coordinates are not emitted as a failure fallback.
