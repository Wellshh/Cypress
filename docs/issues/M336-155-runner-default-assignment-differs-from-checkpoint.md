# M336-155: Runner Assignment Differs From Checkpoint

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

The native runner defaulted to
`experiments/m336/configs/m336_region_assignment.final.json`, while the active
contract requires the assignment bundled with M336-118. The files are not
equivalent despite sharing most subgroup rows.

## Evidence

| Subgroup | Old runner default | M336-118 |
| --- | --- | --- |
| `page_7_J701__bottom` | `bottom_1` | `bottom_0` |
| `page_7_J702__bottom` | `bottom_1` | `bottom_0` |
| `page_86_U8601__bottom` | `bottom_0` | `bottom_2` |
| `page_86_U8602__bottom` | `bottom_0` | `bottom_1` |

After restoring the certified geometry transform, an exact float M336-118 warm
start still reported 45 keep-in failures, all concentrated in the affected
page-7/page-86 regions. This isolated assignment drift from M336-154 alignment
drift.

## Impact

- The runner mislabeled a different domain as an M336-118 warm start.
- Preserve-legal initialization moved 45 certified components.
- Cold/warm quality and runtime were not comparable to the exact reference.

## Remediation

Make `experiments/m336/checkpoints/M336-118/assignment.json` the default for all
native tracks and include its hash in every run identity. Keep explicit CLI
override support for diagnostics, but never label an override as the frozen
M336-118 contract.

## Acceptance Criteria

- The default path and key page-7/page-86 rows have regression tests.
- Preflight assignment SHA equals the M336-118 checkpoint SHA.
- Exact float M336-118 has zero pre-initialization keep-in failures.
- Final matrices use one identical assignment hash across all tracks/runs.

## Resolution

The runner default is now the assignment bundled with M336-118, protected by
regression tests for the affected page-7/page-86 rows. Every warm and cold
10-step result records assignment SHA-256
`e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87`.
Under this assignment the exact float checkpoint has zero pre-initialization
keep-in failures and zero overlaps.
