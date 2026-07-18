# M336-041: Quality-Guide K512 Domain Is Exactly Infeasible

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `334c530`

## Problem

The restored-anchor TOP search needs both exact legality and manual-baseline
quality. The nearest promising guide,
`results/m336/assignment_hint_smoke/result.json`, has HPWL `17320.120203` and
a normalized HPWL/RSMT score upper bound of only `0.881078`. It also has seven
exact overlaps. `C601`, `FV601`, `FV604`, `FV607`, and `FV701` overlap fixed
`Q601`; `FV302` and `MHC8601` overlap fixed `EMI601`. A local legal repair
around this guide was therefore tested before attempting quality optimization.

## Exact Model

The validator-aligned PySAT prototype from M336-040 retained the nearest
fixed-obstacle-free 0.1 mm sites to each guide center for 30 controlled TOP
components. It used one Boolean per original double-precision site, sequential
exactly-one constraints, and pair exclusions only when exact intersection area
exceeded the production validator tolerance (`0.003999140885` transformed area
units). `FV604` retained only 12 sites and `L8607` retained 458; every other
component retained the requested limit.

| Domain restriction | Candidates | Conflict clauses | Status | Time (s) | Sufficient K256 core |
| --- | ---: | ---: | --- | ---: | --- |
| All K256 | 7,436 | 3,243,934 | `UNSAT` | 0.035 | n/a |
| K512, all assumed K256 | 14,806 | 14,667,016 | `UNSAT` | 0.207 | `C601 FV602` |
| Release 2 to K512 | 14,806 | 14,667,016 | `UNSAT` | 0.150 | `FV607 FV618` |
| Release 4 to K512 | 14,806 | 14,667,016 | `UNSAT` | 57.713 | 18 components |
| Release 22 to K512 | 14,806 | 14,667,016 | `UNSAT` | 216.967 | `C701 FV301 FV701` |
| All K512 | 14,806 | 14,667,016 | `UNSAT` | 299.875 | n/a |

The full K512 Glucose42 run completed an actual UNSAT proof before its
300-second interrupt. It accumulated 1,202,234 conflicts, 16,411,033 decisions,
and 579,581,341 propagations. The release sequence reports sufficient
assumption cores, not minimum cores and not evidence that every released
component must move.

The 18-component release-4 core was:

```text
C201 C202 C203 C301 C501 C604 C611 C612 C8653 FV601 FV617
L8606 L8607 L8626 L8630 R602 R604 RT201
```

Evidence JSON SHA-256 values are:

```text
K256:                 8962337c5ef85a3e4ed55af004951e15028dfd945d6f8e962f9c560bbabeca9d
K512/K256 core:       cfa4ce4b7ac0efd5c13395d98669b6ff8f08390175e016fe164f39b5aa6201fc
release 2:            f0db4f7074af26f3a899e78fcd485af2a5884c5179421c5557e14099e1c871a7
release 4:            bb1bb99fcc566b044fadebedeaf79e4c8c5319289f2c2743d9065e6c1dbc9259
release 22:           275721cc880af5163ec0d4a529122aadbc473b78cb42cf575e70347b2aca3216
full K512:            81b553495a304f36ab38e4589c7002d87831ca7c2f6f5bcb68182b67feafce2a
```

## Scope and Impact

This proves only that no exact legal TOP selection exists inside these
guide-centered K512 candidate sets. It does not prove the full 0.1 mm lattice,
a finer lattice, or continuous placement infeasible. No placement was produced,
so there is no legality or native RSMT improvement and the score gate remains
unmet.

The next search must widen or adapt domains rather than spend more solver time
on K512. Any survivor must be merged with the known legal BOTTOM placement,
validated with full-board Shapely geometry, replayed with one worker, and scored
with native HPWL/RSMT against the manual baseline (`>= 1.0`).
