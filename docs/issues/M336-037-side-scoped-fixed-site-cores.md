# M336-037: Side-Scoped Fixed-Site Core Diagnosis

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `01d8c02`

## Problem

The round-13 TOP placement has nine exact overlaps. Fixing its 26 rectangular
components and releasing only the four rotated components was `INFEASIBLE` in
`0.257076 s` with zero branches. Releasing the seven rectangles in the
round-14 overlap closure as well was still `INFEASIBLE` in `0.833621 s` with
1,224 branches and 11 conflicts. These proofs showed that a useful exact
subproblem needs a principled way to identify additional stale fixed sites.

Side-scoped partial fixing was initially blocked by an unconditional
`packing_side`/`movable_refdes` mutual-exclusion check. The modeled constraints
already filter by side, unknown or opposite-side refdes fail validation, and a
complete structured result hint supplies the opposite side. The check had no
remaining technical purpose and was removed.

## Diagnostic Correction

`--diagnose-fixed-hint-core` creates one Boolean assumption per fixed hinted
component and guards its site, or coordinate-pair, equality. It requires one
worker because OR-Tools assumption solving is not compatible with parallel
search. A core is read only after `INFEASIBLE` and is reported as sufficient,
never minimal.

The first implementation still reduced every fixed component's candidate
domain to its single hinted site before adding the guarded equality. Disabling
an assumption therefore restored no freedom and returned an empty core. The
corrected path retains each diagnosed component's complete legal candidate
domain; assumptions alone impose the original fixed sites. Normal partial-fix
runs retain the previous one-candidate representation.

## Evidence

All runs use the restored-Q601 fixed assignment, 0.1 mm grid, exact decomposed
footprints, fixed-obstacle pruning, 32 inner slices, all 110 nonrectangle-related
collision pairs, seed 1000, and the round-13 structured hint.

| Run | Fixed sites | Candidates | Workers | Status | Time (s) | Branches | Conflicts |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| Four rotated movable | 26 | 3,446 | 8 | INFEASIBLE | 0.257 | 0 | 0 |
| Round-14 closure movable | 19 | 13,844 | 8 | INFEASIBLE | 0.834 | 1,224 | 11 |
| Closure assumption diagnosis | 19 | 33,215 | 1 | INFEASIBLE | 5.505 | 16,803 | 197 |
| First core released | 7 | 25,854 | 8 | INFEASIBLE | 38.126 | 859,039 | 51,026 |
| Seven-site assumption diagnosis | 7 | 33,215 | 1 | UNKNOWN | 120.005 | 736,912 | 377,560 |

The first sufficient core contains:

```text
C201 C202 C204 C601 C604 C612
FV601 FV602 FV607 FV617 FV618 FV701
```

After releasing those 12 sites, the remaining fixed set is `C501`, `FV301`,
`FV604`, `L8606`, `R602`, `R604`, and `R704`. Its parallel fixed-site model is
proven infeasible, while the full-domain assumption model reaches `UNKNOWN`;
an empty core in the latter result has no infeasibility meaning.

Result SHA-256 values, in table order, are:

```text
continuation_q601_final_cuts13_rectangles_fixed_nonrect4: d52077c021918073677d69523804bfe03c379d8e40e84205bda27bc3b157852f
continuation_q601_final_cuts13_closure11:                  f7f1d1738e28f42b1796e60f30fdb88f9f7b770f0c631669ffc37b94a9bd2db6
continuation_q601_final_cuts13_closure11_core:             d622d2308b4b8b503e092b69809a6f1ce2ca396dffe41484d7de08b0ae1dc65a
continuation_q601_final_cuts13_core12_released:            44e96aa593bb9c5639d4f744888ccbef498898790a629a18729afbfcda2f2a3e
continuation_q601_final_cuts13_core7_diagnosis:            24e076238c5a265c179de1a7eb41a785c734516dc4d987af7e506d09d8625c80
```

## Acceptance Impact

No run produced a placement. There is no new HPWL, RSMT, or normalized score,
and the manual-baseline gate remains unmet. These runs must not be presented as
evidence that the unrestricted 33,215-candidate TOP model is infeasible.

## Required Improvement

- Persist replayable partial-fix manifests instead of long repeated CLI lists.
- Determine whether releasing some or all of the remaining seven sites yields
  a strict incumbent without sacrificing solver portfolio diversity.
- Require a one-worker strict replay and exact zero-overlap validation before
  merging TOP with the legal BOTTOM result.
- Score the merged placement with native HPWL and RSMT; acceptance still
  requires a normalized score of at least `1.0` against `pcb_geometry.json`.
