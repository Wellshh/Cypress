# M336-039: Discrete Packing Stalls at One Exact Overlap

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `122f018`

## Problem

After fixed-obstacle hard pruning, restored-Q601 TOP packing still had no legal
incumbent. The full 33,215-site geometric CP-SAT model and min-conflicts repair
both spent most effort rediscovering equivalent local states. Better propagation
was needed without weakening exact footprints or the 0.1 mm candidate lattice.

## Encoding Experiments

A prototype encoded every nonrectangle-related component pair by forbidden
relative candidate displacement. It produced 110 tables with 112,501 forbidden
displacements. With eight workers it reached `UNKNOWN` after 300.528 s,
3,713,014 branches, and 800,440 conflicts.

Expanding those relations into direct `(site_i, site_j)` tables strengthened
domain propagation but required 12,912,513 forbidden pairs and about 4.2 GB
resident memory. It still reached `UNKNOWN` after 311.752 s, 12,765,127
branches, and 369,486 conflicts. Neither encoding is retained in production.

## Exact Heuristic Improvement

An initial weighted-breakout prototype incorrectly classified exact boundary
contact `C611/C612` as overlap because it rounded centers to 1e-6 mm before
testing. Using original double-precision domain centers and 12-decimal relative
displacements removed the false conflict: its guide conflict set then exactly
matched Shapely (`FV604/FV618` and `FV604/L8607`).

Every one of `FV604`'s 12 fixed-obstacle-free sites was blocked by both
`FV618` and `L8607` in that guide. Highest-degree variable selection therefore
moved only `FV604` and could never improve. Uniform conflict-endpoint selection
reduced the exact result to one overlap, `FV601/FV604`, at step 97,751 of a
100,000-step deterministic run. Exact full-board validation reported zero
keep-in violations and one overlap. The state has HPWL `23908.717531` and only
a `0.638276` normalized HPWL/RSMT score upper bound. Eight 200,000-step
continuations did not close the final overlap.

## Fixed-Site Closure

Using the one-overlap state as a hint produced this assumption-core sequence:

| Movable sites | Fixed sites | Status | Time (s) | Sufficient core |
| ---: | ---: | --- | ---: | --- |
| 2 | 28 | INFEASIBLE | 7.179 | 10 sites |
| 12 | 18 | INFEASIBLE | 11.295 | 11 sites |
| 23 | 7 | UNKNOWN | 120.022 | None |

The remaining fixed sites are `C202`, `C204`, `C501`, `C611`, `C612`, `R602`,
and `R704`. An eight-worker model with eight inner slices reported
`INFEASIBLE` in 199.095 s, while 0/16/32-slice portfolios remained `UNKNOWN`.
This is evidence about the integer prototype only, not an exact-geometry proof:
relative displacement keys and interval endpoints are quantized, so their
equivalence to double-precision boundary contact must be audited first.

Result SHA-256 values are:

```text
relative displacement, 300 s: c98701feccf64748b2bb0426c33294ef49d4d4a1f26890c8674bedc1dc5efaeb
direct candidate, 300 s:       dcef8577b3011882bf43bc88aa4b9b7faadfe4a3d1d92c1acbacc0f2afb6b0e7
one exact overlap:             8580be049caf2bbe4382d6697905da4055d43360bd29872c4e3e69b515f15470
2-site core:                   4d4df95766fd3d82637d18f34510342a7013d9eb1728ac493d9dc7491e7fe548
12-site core:                  4040a0eef7e2d259ffa09d9213dc22e0916af34687ce2089bb1b69770ada92e5
23-site boundary:              feaf864cb8e8f4bfd5047b53d84c9772f6da3d7fbdf3f239428249a1f3a68271
integer inner-8 result:        4b4f8dd5ccb7c2afa6323658d625e08d4f72acb6edb6f3a82dcecd6d35a32920
```

## Acceptance Impact

The exact overlap count improved from two to one, but no legal TOP result
exists and the quality bound is far below the manual baseline. Acceptance is
unchanged. The next implementation must encode exact site-pair conflicts from
original centers, audit touching pairs against Shapely, obtain an independently
replayable zero-overlap candidate, and only then optimize native HPWL/RSMT to a
normalized score of at least `1.0`.
