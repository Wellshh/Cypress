# M336-025: Joint-Side Packing Hides Solvable Subproblems

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `8cde0fd`

## Problem

The restored-anchor grid01 fixed model combined 30 TOP and 70 BOTTOM
controlled components. Even without HPWL, its 215,749 sites and 3,500
convex-part pair constraints remained `UNKNOWN` after 300.707 seconds and used
4,625,328 KiB peak RSS. Collisions never cross board sides, so this joint model
obscured whether either geometric subproblem was already solvable.

## Correction

Diagnostic `--packing-side TOP|BOTTOM` now requires packing-only mode, a fixed
assignment, and one complete structured result hint. The CP model creates site
and collision variables only for the selected side. Unmodeled components are
restored from their exact region-local hint after solving, and the result emits
both global legality and `packing_side_legality`. Only the selected side gates
that intermediate stage; final promotion still requires global legality.

Unknown sides, incomplete hints, optimized assignment, and simultaneous
`--movable-refdes` usage fail before model construction.

## Contract Evidence

A known-legal TOP fixed replay modeled 30 components, 50,425 sites, and 626
convex-part constraints. It returned `OPTIMAL` in `0.054693 s` with zero
branches. Its placement SHA-256
`1551a2dacf7ebd4f935dc72c194f24a37c5140d875bc93c7fe4a41fc3c835103`
is byte-identical to the full known-legal replay; all 70 BOTTOM selected sites
were transmitted without CP variables.

## Restored-Anchor Evidence

The full TOP subproblem remained `UNKNOWN` after `300.190402 s`, 391,220
branches, and 12,134 conflicts. Its 50,425-site model peaked at 2,007,996 KiB,
reducing memory by 56.6% without establishing feasibility.

The dual-center BOTTOM model retained 69,321 sites and found `OPTIMAL` packing
after `75.221343 s`, 1,018,827 branches, and 64,205 conflicts. Exact BOTTOM
overlaps fell from 2 to 0; global overlaps fell from 14 to 12. HPWL also fell
from `21308.355340` to `20511.832890`, raising the necessary score upper bound
from `0.716168` to `0.743979`.

Single-worker fixed replay returned `OPTIMAL` in `0.185739 s`, zero branches,
and the same placement hash
`d01d0f170974ef1b937884556da2717933f06b94d84eb00f63b6ef580a361377`.

## Residual Risk

TOP packing around the restored `Q601` endpoint remains unresolved, and the
BOTTOM intermediate is not globally legal or score-acceptable. Side outputs
must be chained, globally exact-validated, score-gated, and replayed before
promotion.

## Acceptance Criteria

- A side model contains only that side's controlled site variables.
- Unmodeled selected sites survive fixed replay byte-for-byte.
- Side and global legality are reported separately.
- BOTTOM discovery is reproducible with one worker and fixed sites.
