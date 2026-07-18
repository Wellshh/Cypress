# M336-046: Extra NoOverlap2D Propagation Regresses Search

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `bfac477`

## Problem

The exact TOP CP-SAT model relies on `NoOverlap2D` for 26 rectangles. OR-Tools
9.14 leaves timetabling, energetic, area-energetic, and try-edge reinforcement
disabled by default. These sound propagators do not change the feasible set,
but could have reduced the unresolved K1024 search.

## Deterministic A/B

Each K512 run used the score guide, 14,806 candidates, one worker, seed 1000,
and the same exact validator-aligned model. All modes proved `INFEASIBLE`.

| Mode | Deterministic time | Branches | Conflicts |
| --- | ---: | ---: | ---: |
| default | 55.680 | 1,631,125 | 78,925 |
| area | 57.858 | 1,700,335 | 77,945 |
| timetabling | 62.262 | 1,674,646 | 83,510 |
| energetic | 64.529 | 1,929,610 | 91,551 |
| try-edge | 65.139 | 1,783,335 | 83,782 |
| all four | 79.053 | 2,136,749 | 110,403 |

Default is best. Enabling all four increases deterministic time by 42.0%,
branches by 31.0%, and conflicts by 39.9%. A K1024 control gave each single
mode deterministic time 500. All four returned `UNKNOWN` without a placement;
branch counts ranged from 15,252,035 to 17,473,498. These timeouts are not
infeasibility proofs.

## Evidence

```text
K512 default:     c6800b706f0b811396d3605f0f073298ade867ff3a35569c11a686033a7ef65e
K512 all:         66421b0eab26038a9e3e85c24e33a07d9a81f4f7fbb50d6d1992988c62ed0ad4
K1024 timetable: ce2625b999e0832bbbf7b2f36d668a54d891671f16fabdb883fb80090ac4a32b
K1024 energetic: bf136f1457ba152ef8861afc1e1cb3580e83883c48a48b0e2854ea70c8ad4b82
K1024 area:      a2b110d81c342224ebe4a619091cf76915afad32f45dd30c3e48258c00f181f1
K1024 try-edge:  dd14875333a4278ab3bd69005f6bf712c3b8cca3c18f74f72d6828617c8483a8
```

## Resolution

The experimental parameter switch was removed before commit. The solver keeps
OR-Tools defaults. This issue is resolved as a rejected search strategy, not as
resolution of K1024 packing. No legality or score result improved.
