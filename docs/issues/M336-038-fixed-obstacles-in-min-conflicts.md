# M336-038: Fixed Obstacles in Min-Conflicts Repair

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `48f9643`

## Problem

The deterministic repair path treated fixed-obstacle intersections as a soft
part of the min-conflicts score. A controlled component could therefore remain
on an intrinsically invalid site while moves of unrelated controlled
components were explored. In the restored-Q601 TOP search, the best state
stalled with only `FV604/Q601` overlapping. Inspection showed that `FV604` had
12 fixed-obstacle-free sites, but its selected site intersected fixed `Q601` by
982.111 mm2. No rearrangement of other controlled components could legalize
that site.

A separate API defect used `preferred_center or target_center`; passing a NumPy
array raised an ambiguous-truth-value exception. Exact polygon scoring also
performed one Shapely call per candidate and made guided repair unnecessarily
slow.

## Correction

Min-conflicts now computes each component's exact fixed-obstacle-free candidate
set once. Initialization and every move are restricted to that set; boundary
touching remains legal because only positive-area intersection is rejected. A
component with an empty set fails immediately with its refdes in the report.

Candidate intersections use Shapely 2 vectorized operations after a bounding-
box prefilter, with a scalar fallback for the repository's supported Shapely 1
versions. The repair also excludes its current site from alternatives, accepts
NumPy preferred centers, and records the best candidate snapshot and exact
conflict pairs for every exhausted restart. Escape probabilities remain zero
by default and consume no additional random numbers in the default path.

## Evidence

A 64-candidate by 47-obstacle exact-scoring microbenchmark improved from
0.03575 s to 0.01194 s (2.993x), with identical counts and areas. With hard
obstacle pruning, `FV604` retained 12 candidates and every reported best state
had zero fixed-obstacle conflicts.

| Random walk | Best nodes | Incidents | Incident area | Best step | Result |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.00 | 6 | 8 | 1217.148 | 724 | Exhausted |
| 0.01 | 5 | 6 | 1592.186 | 424 | Exhausted |
| 0.03 | 6 | 8 | 1221.855 | 2210 | Exhausted |
| 0.05 | 6 | 6 | 754.268 | 1982 | Exhausted |
| 0.10 | 3 | 4 | 1595.117 | 369 | Exhausted |

The 0.10 state had only `FV604/FV618` and `FV604/L8607` conflicts. Fixing each
of the 12 `FV604` sites independently still exhausted 3,000-step repairs, so
random walk is not enabled in production. Probe SHA-256 values in table order:

```text
509de7f8814f8c4e85372cbded199981d5664b66340e0136377077ec87365c25
a478ccb0657b1b33080e67b48f5db628c699a2edfc66c0ba08a7974b4833d275
ff786eaba97f0d3b0036807a444af63e71fcbd70c15618610a9c0d5d7a8fc475
d8459e2aba1dda96b9b5a15c96dea2092bd8ac2e93c21a665cfef80e1f55aa33
ede91a2896f6949959a407f9bb473c5a5aad7fac069a90cf5325b02ca2a7370c
```

## Acceptance Impact

This removes an invalid repair state but does not produce a legal TOP
placement. There is no new HPWL or RSMT, and the manual-baseline score gate
remains unmet. The next search must use the reported small conflict closure in
an exact discrete model and independently replay any candidate.
