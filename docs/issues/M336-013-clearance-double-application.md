# M336-013: Alternate-Region Search Applied Clearance Twice

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `c76f9ee`

## Problem

The runtime context builds each feasible domain with the configured clearance
and stores the already buffered `footprint_local`. Assignment search reused
that effective footprint for alternate regions but passed the same nonzero
clearance to `FeasibleDomain.build` again. A requested `0.2 mm` margin therefore
behaved like approximately `0.4 mm` during reassignment.

## Impact

Clearance sweeps above zero could falsely remove region candidates, inflate
capacity pressure, and report quality or packing infeasibility that the runtime
configuration did not actually impose. Existing `0.0 mm` evidence is
unaffected.

## Resolution

Alternate-region construction now verifies that the loaded context clearance
matches the requested search clearance, then passes `clearance=0.0` while
reusing the context's effective footprint. This preserves exactly one buffer
operation and fails closed if contexts are mixed.

A focused regression builds a `1.0`-clearance source domain and verifies that
alternate-region search preserves its footprint bounds instead of buffering a
second time.

## Acceptance Criteria

- Runtime and assignment search use the same effective footprint.
- Nonzero clearance has focused regression coverage.
- Context/search clearance mismatch fails explicitly.
