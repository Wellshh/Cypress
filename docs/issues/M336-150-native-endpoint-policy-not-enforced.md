# M336-150: Native Endpoint Policy Is Not Enforced

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

The active contract requires manual `EMI601` and runtime `Q601`. Native
`AnchorKeepInContext.from_params()` is constructed before an initial placement
is loaded and derives every frozen anchor from the runtime geometry transform.
It has no serialized endpoint policy and no manual-position source. The later
initialization step overwrites all frozen anchors with those runtime values.

## Evidence

Both seed-1000 N3 E2 outputs freeze:

| Endpoint | Native output lower-left | Required lower-left |
| --- | --- | --- |
| `EMI601` | `(617.373779, 559.845581)` | manual `(632.196, 167.598)` |
| `Q601` | `(669.334534, 540.623718)` | runtime `(669.334534, 540.623718)` |

The preflight report records 25 frozen anchors but no endpoint policy. Thus the
native run uses runtime `EMI601` and runtime `Q601`, not the active comparable
contract.

## Impact

N1-N3 objective, gradient, optimizer, projection, and ablation signals remain
valid engineering evidence. Their E2-E4 placement quality and anchor-distance
values are not comparable to M336-118 under the active endpoint contract.

## Remediation

Load the initial position before context construction. Resolve all frozen
coordinates through one explicit position-source resolver with a serialized
default runtime policy and a manual `EMI601` override. Use the original
PlaceDB-aligned geometry as the runtime source and a separately hashed manual
PL as the manual source. The float runtime PL is an initial-position source and
identity audit, not authority to refit certified geometry. Record each endpoint,
policy, source path/hash, and resolved coordinate in preflight output.

## Acceptance Criteria

- Context construction occurs after initial placement loading.
- `EMI601` resolves exactly to the declared manual source.
- `Q601` resolves exactly to the original runtime source.
- A warm-start file cannot silently redefine runtime endpoints.
- Repeated preflight reports have identical policy, hashes, and coordinates.
- Tests fail closed on missing, duplicate, or unknown endpoint declarations.

## Resolution

Initial placement now loads before context construction. One fail-closed policy
resolver records the manual/runtime declarations, source paths and hashes, and
every resolved endpoint. Fresh cold and warm matrices resolve `EMI601` to
manual lower-left `(632.196, 167.598)` and `Q601` to runtime lower-left
`(669.3345033915735, 540.623738829674)`. Both tracks retain the certified
native geometry transform, and repeated preflight hashes are identical. Tests
cover missing, duplicate, overlapping, and unknown declarations and verify that
warm input coordinates cannot refit the runtime alignment.
