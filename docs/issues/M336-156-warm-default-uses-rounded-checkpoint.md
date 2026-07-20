# M336-156: Warm Default Uses Rounded Checkpoint

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

The new checkpoint-warm track defaulted to M336-118 `placement.pl`, although
M336-142 already proved that this legacy three-decimal artifact is not an exact
post-serialization placement. The certified float64 reconstruction existed only
under ignored `results/`, so the correct warm source was not portable.

## Impact

- A fresh clone could not run the exact warm-start track.
- The default could trigger repair before Cypress optimization.
- Warm-start hashes and quality depended on a known lossy artifact.

## Remediation

Add `placement.float64.pl` beside the immutable legacy file, retain both hashes
in the checkpoint manifest, and make the native runner default to the float64
asset. The added file has the same coordinate rows as M336-142's certified
`ce1835...` replay; its tracked form adds a final newline and therefore has SHA
`3d3d3ef72bab1f279e9906ada249a724a451c8f415d777f98f84adfa1d93cdbc`.

## Acceptance Criteria

- The original `placement.pl` and its hash remain unchanged.
- The float64 asset is tracked, manifested, and selected by default.
- Its pre-initialization audit is 100/100 contained with zero overlaps.
- Repeated native serialization has zero coordinate drift.

## Resolution

The portable checkpoint now contains manifested `placement.float64.pl` with
SHA-256 `3d3d3ef72bab1f279e9906ada249a724a451c8f415d777f98f84adfa1d93cdbc`;
the legacy rounded file remains unchanged. The runner selects the float64 asset
by default. Repeated warm initialization preserves 100/100 constrained
components with zero overlaps, and post-serialization native replay reports
zero coordinate drift.
