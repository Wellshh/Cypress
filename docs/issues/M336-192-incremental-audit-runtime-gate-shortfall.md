# M336-192: Incremental Audit Cannot Close the E2 Runtime Gate

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `cac825a`

## Finding

The generalized exact incremental audit from M336-191 is strictly equivalent
and materially faster, but its measured opportunity is too small to close the
fixed E2 runtime gate. No second D1 is authorized or executed.

## Implementation

`AnchorKeepInContext` now exposes one bound exact validator used by the contact
projector. The first proposal remains a full audit. A subsequent correction may
reuse the immediately preceding exact state only when a private validator token,
PlaceDB identity, constrained-template identity, fixed-geometry cache key,
epsilon, scale, dtype, and position layout all match. The previous state must
have zero Keep-in violations, but may retain complete exact overlap rows.

Changed node IDs are recomputed from the two coordinate tensors. The delta path
rebuilds changed footprints, rechecks their Keep-in and fixed interactions, and
recomputes every same-side pair incident to a changed node. Unchanged conflict
rows and their original internal-unit areas are retained. Candidate-pair order
is rebuilt with the same STRtree query order as the full audit, preserving
floating summation, public pair sorting, closure, and JSON bytes. Changes to
fixed physical nodes, more than 32 or at least half of constrained nodes,
Keep-in-illegal origins, stale tokens/templates, and reporting-context drift
all fail back to a full audit.

Diagnostics now separate full calls, delta attempts/hits/fallbacks, changed-node
totals, fallback reasons, and delta Keep-in/fixed/constrained timing. Contact
records also identify each validator call as `full`, `delta`, or
`full_fallback`.

## Parity Evidence

Focused tests cover chained overlap-illegal origins, retained unrelated rows,
fixed conflicts, changed/changed pairs, epsilon exterior areas `0`, `< epsilon`,
`= epsilon`, and `> epsilon`, plus illegal-origin, dense-change, fixed-change,
token, and template fallbacks. The existing full-report and contact-authority
tests remain unchanged in behavior.

A real M336 corpus starts from the preserved E2 placement
`44f62b5010c88550ef5927ba454ef9876f9143ef00da5b6f0af2d4ac75154dfd`.
It applies the observed 17-correction changed-count sequence
`8,12,14,17,1,16,3,17,3,19,6,16,3,18,2,21,1` three times. All `51` states are
Keep-in legal; `30` states per device/dtype track contain exact overlaps. Across
CPU/H100 and float32/float64, all `204/204` delta reports match full reports as
Python objects and sorted JSON, and every call takes the delta path. These are
deterministic perturbations of the saved final placement, not unavailable
proposal-coordinate replay.

All `269/269` applicable tests pass after installation: anchor/keep-in `64`,
exact contact `62`, exact guard `11`, reproducibility `22`, irregular density
`9`, and non-CP-SAT M336 baseline `101`. Five optional OR-Tools tests remain
explicitly excluded.

## Offline Runtime Evidence

Eleven H100 float32 samples compare the same 17 sparse states:

| Path | Median | Range |
| --- | ---: | ---: |
| Full audit, 17 calls | `0.016575098 s` | `0.016357983-0.019303290 s` |
| Incremental audit, 17 calls | `0.006642381 s` | `0.006531063-0.006730616 s` |
| Median saving | `0.009932717 s` | |

Applying that saving optimistically to M336-190 gives
`2.210201988 s`, still `0.048477988 s` above the fixed `2.161724 s` E2 limit.
The stronger production bound also remains decisive: deleting the complete
M336-189 audit (`0.038758447 s`) would leave `2.181376258 s`, still
`0.019652258 s` above the limit.

## Source Identity

Source and installed copies match:

```text
NonLinearPlace.py                 ab6c02bf371c19571daa2d6fe79a1c689859bbc83f71af2f5b62db26752f24ad
anchor_keepin.py                  6bf3859e9ab4e02d4ba44ba2571b3f11fbd0ed5e8dbb4440263bfb800ed37fd0
exact_contact_projection.py      e6ad7002d31c00d78106f3b73097f09d8ca7f2860b13be13fae06ad804a37c05
anchor_keepin_unittest.py        9d00a26923e7852ac1b3d3414821c116316ca6fe764182055fc51064a03152ef
exact_contact_projection test    a6c7344fb0e97727cb479d047f88ca3d29305bcf1625bd2aeeef33a48fe6f537
```

The tracked `DREAMPlace.log` and user-owned M336-141 aggregate retain SHA-256
`012235903d7fd4927e9f1f9ace79cdf20328870d7c34ba0d42d2edb89e74a92b` and
`4091eb8e0611a8042bbc0bf5bed6d15843909d2168a21a4a34655653607ff77d`,
respectively.

## Decision

Stop D1 audit micro-optimization. The covered-region fast path and exact delta
audit are implemented and exhausted; neither provides a stable full-counted-path
margin. A human architecture decision is now required before reducing
authority/FLUTE topology selection frequency or changing the runtime gate.
Collision behavior, anchor control, learning rate, and Legalization remain
frozen. Do not run D1 again, D2, D3, E4, repair, fallback, CP-SAT, or tuning
under this issue.
