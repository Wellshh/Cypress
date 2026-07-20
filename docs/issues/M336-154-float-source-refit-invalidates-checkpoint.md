# M336-154: Float Source Refit Invalidates Checkpoint

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

The first checkpoint-warm N4 smoke used float `m336.pl` coordinates to refit the
geometry transform. That produced scale `20.0000000194` and translation Y
`1606.0000008103`, while the M336-118 certificate was built with native PlaceDB
scale `19.9978520966` and translation Y `1605.8657950428`. The seemingly small
change altered every feasible footprint and keep-in boundary.

## Evidence

The M336-118 warm input was then reported with 45 keep-in failures and 24 exact
overlaps. Initialization repaired a 64-component conflict closure, preserved
only 36/100 constrained components, displaced one component by up to
`424.838266` Cypress units, and consumed `54.932 s`. This contradicts the
checkpoint's certified 100/100 containment and zero-overlap replay.

## Impact

- The warm track was no longer evaluating the M336-118 certified domain.
- Preserve-legal initialization became another broad repacker.
- Endpoint-policy cleanup silently changed region and footprint geometry.
- Warm runtime and quality evidence from that smoke are invalid.

## Remediation

Separate initial-placement sourcing from geometry/endpoint sourcing. Load the
float PL for cold coordinates, but fit geometry to the original native PlaceDB
positions exactly as the checkpoint generator did. Resolve runtime anchors and
fixed obstacles from that frozen transform; apply only the declared manual
`EMI601` override. Keep the float PL as a bounded identity/quantization audit.

## Acceptance Criteria

- Alignment parameters match the M336-118 certified context reproducibly.
- Runtime `Q601` resolves to the original transformed geometry coordinate.
- The exact float checkpoint replays with 100/100 containment and zero overlap.
- Warm initialization repairs no legal constrained component.
- A test prevents a float initial-position file from refitting geometry.

## Resolution

Context alignment now uses an untouched native PlaceDB snapshot, independent of
the selected initial PL. Fresh warm preflight reproduces scale
`19.997852096565094`, translation X `669.0030093505111`, and translation Y
`1605.8657950428246`. The float64 M336-118 checkpoint is 100/100 contained with
zero overlaps before optimization; initialization preserves all 100 constrained
components and repairs none. A focused test verifies alignment targets come
only from the native snapshot.
