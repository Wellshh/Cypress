# M336-034: Incremental Collision Cuts Stall Before Exact Closure

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `7a16377`

## Problem

The restored-Q601 TOP packing model has 110 candidate-overlapping controlled
pairs involving four nonrectangles. Enforcing all 110 pairs directly remained
`UNKNOWN`, while the shape-class relaxations in M336-033 returned candidates
with exact-geometry overlaps. A reproducible middle ground was needed to
identify whether a small conflict set could converge to exact feasibility.

## Implemented Diagnostic

Repeatable `--controlled-collision-pair FIRST SECOND` arguments now enforce
only listed nonrectangle-related controlled pairs. Rectangle `NoOverlap2D`,
fixed-obstacle pruning, keep-in domains, and exact post-solve validation remain
active. Unlisted pairs are reported as relaxed, so a relaxed result can never
silently pass acceptance.

Inputs fail fast for unknown refdes, cross-side pairs, rectangle pairs already
covered by `NoOverlap2D`, and incompatible model modes. Canonicalization removes
duplicate/reversed pairs. A requested pair whose restricted candidate domains
are disjoint is instead reported as an inactive cut: it is redundant in that
model and must not abort replay.

## Cut Lineage

Each successful round was warm-started from its predecessor. Exact validator
overlaps became the next cumulative cuts:

```text
01: C502/L8630 FV301/L8607 FV607/L8626 FV607/L8630
    FV618/L8626 FV618/L8630 L8626/L8630 L8626/R604 L8630/R604
02: C204/L8607 C501/L8626 C8653/R602 FV601/L8607 FV617/L8630
    L8606/L8607 L8626/R704
03: C201/L8626 C201/L8630 C202/C8653 C501/L8630 C601/L8607
    C604/L8607 C612/L8607 FV604/L8626 FV701/L8607 L8630/R704
04: C301/L8630 C611/L8626 C701/L8626 FV602/L8607 FV604/L8607
    FV604/L8630 L8607/R605 L8626/RT201
05: C604/L8630 C8653/FV301 FV602/L8626 FV602/L8630 L8607/R602
    L8626/R605
06: C202/L8607 C604/L8626 C612/L8630 C8653/FV601 FV701/L8626
    L8606/L8630
07: C202/L8630 C204/L8630 C601/L8626 C612/L8626 C8653/L8606
    FV601/L8630
08: C202/L8626 C204/L8626 C8653/L8607 C8653/L8630 FV601/L8626
    L8607/L8630
09: C204/C8653 C601/C8653 FV301/L8630 L8607/L8626 L8630/R602
10: C601/L8630 C604/C8653 C8653/FV701 FV301/L8626 L8606/L8626
    L8626/R602
11: C502/L8607 C8653/FV602 FV607/L8607 FV618/L8607 L8607/R604
12: C201/L8607 C203/L8626 C301/L8626 C701/C8653 C701/L8630
    C8653/FV604 FV617/L8607
13: C201/C8653 C203/L8630 C301/L8607 C501/L8607 C611/L8630
    C8653/R604 C8653/R704 FV617/L8626 L8607/R704 L8607/RT201
14: C203/L8607 C301/C8653 C502/C8653 C502/L8626 C611/L8607
    C701/L8607 C8653/L8626 L8630/R605 L8630/RT201
```

## Evidence

Rounds 01-10 minimized hint L1 displacement; rounds 11-14 requested the first
feasible solution. Times are CP-SAT wall times with eight workers and seed
1000, so they are search diagnostics rather than deterministic acceptance.

| Round | Exact / relaxed | Status | Time (s) | Branches | Conflicts | HPWL | Exact overlaps |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 01 | 9 / 101 | OPTIMAL | 2.700 | 14,600 | 0 | 23,380.342 | 7 |
| 02 | 16 / 94 | OPTIMAL | 3.229 | 15,443 | 50 | 23,251.357 | 10 |
| 03 | 26 / 84 | OPTIMAL | 4.138 | 22,450 | 50 | 23,201.866 | 8 |
| 04 | 34 / 76 | OPTIMAL | 5.410 | 22,373 | 50 | 22,986.886 | 6 |
| 05 | 40 / 70 | OPTIMAL | 5.760 | 14,858 | 3 | 22,942.391 | 6 |
| 06 | 46 / 64 | OPTIMAL | 10.005 | 16,621 | 50 | 22,918.394 | 6 |
| 07 | 52 / 58 | OPTIMAL | 3.965 | 23,574 | 51 | 22,883.397 | 6 |
| 08 | 58 / 52 | OPTIMAL | 7.236 | 23,260 | 51 | 22,955.890 | 5 |
| 09 | 63 / 47 | OPTIMAL | 6.768 | 33,999 | 53 | 23,029.382 | 6 |
| 10 | 69 / 41 | OPTIMAL | 76.538 | 24,666 | 51 | 23,413.844 | 5 |
| 11 | 74 / 36 | OPTIMAL | 3.719 | 144,537 | 1,307 | 22,975.715 | 7 |
| 12 | 81 / 29 | OPTIMAL | 3.748 | 149,557 | 2,722 | 23,664.150 | 10 |
| 13 | 91 / 19 | OPTIMAL | 4.136 | 163,260 | 3,826 | 23,548.772 | 9 |
| 14 | 100 / 10 | UNKNOWN | 120.089 | 2,207,665 | 726,935 | n/a | n/a |

Round-14 result SHA-256 is
`301832c148d7471a983b234fdc41e3f0fe32a0a534c0e7bd32497bd8cb73c221`.

Restricting each component-region to sites nearest the round-13 hint produced:

| Domain | Candidates | Active / inactive cuts | Status | Time (s) | Branches |
| --- | ---: | ---: | --- | ---: | ---: |
| 512 | 14,806 | 91 / 9 | INFEASIBLE | 1.194 | 53,447 |
| 1,024 | 26,590 | 100 / 0 | UNKNOWN | 120.075 | 1,407,803 |
| 1,024 + repair | 26,590 | 100 / 0 | UNKNOWN | 120.076 | 13,296 |

The three result hashes are respectively
`c47bebb6b2566d07a665ff364bd23147a5c40a43399dbfc0ed598526113316fc`,
`0a1012f0cb1daaaf1bef8f6cf455765a17f2b299adf614cd7da1ff2331369634`,
and `945073147a377bdeec8c513725b8a9c0a3e1a97d52224df2b668b1e454d2566b`.
The repair run used `repair_hint=true` and `hint_conflict_limit=100000`; zero
conflicts and far fewer branches show that it stalled in hint repair rather
than improving regular search.

## Acceptance Impact

No round is accepted. Rounds 01-13 retain exact overlaps, and round 14 has no
candidate. The best observed score upper bound in this lineage is only
`0.666875`, below the manual baseline requirement of `1.0` even before RSMT.

## Required Improvement

- Make cumulative cut manifests directly replayable without a 300-token CLI.
- Explore a solver decomposition that couples nonrectangles and rectangles
  without serially fixing either class.
- Accept TOP only after zero-overlap validation and a one-worker replay with all
  110 pairs exact.
- Merge with the legal BOTTOM packing, then run native HPWL/RSMT scoring against
  `pcb_geometry.json`; feasibility alone cannot satisfy the quality gate.
