# M336-040: Exact-Site CNF Exposes a Global Repacking Boundary

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `062a8b3`

## Problem

The restored-Q601 TOP search reached one exact overlap, `FV601/FV604`, but
neither min-conflicts nor the integer CP-SAT encodings could close it. The
integer models also quantized relative displacements, so their fixed-site cores
were not sufficient evidence about original double-precision grid centers.

## Exact-Center CNF Prototype

A temporary PySAT prototype assigns one Boolean variable to every retained
site and uses sequential-counter exactly-one constraints. Fixed-obstacle sites
are removed first. Controlled-component conflicts are generated from original
double-precision centers. Axis-aligned rectangles use exact intersection area;
other footprints use production convex decomposition to identify positive
intersection, followed by Shapely area evaluation. Touching and areas no larger
than the validator's `1e-5 mm2` tolerance are allowed. Every future SAT result
must still pass the independent full-board validator; the prototype is not a
production dependency.

The local domains are ordered by distance from the one-overlap guide:

| Domain | Candidates | Conflict clauses | Status | Solve time |
| --- | ---: | ---: | --- | ---: |
| K256 | 7,436 | 3,311,118 | `UNSAT` | 1.283 s |
| K512 | 14,806 | 13,468,796 | unresolved | - |

An initial strict-positive-area prototype emitted 3,991 extra K256 clauses and
13,106 extra K512 clauses. Four K512 CDCL runs timed out at 300 seconds, and
Kissat/CaDiCaL produced no result within 600 seconds. Those runs are retained
only as search diagnostics because their collision threshold was stricter than
acceptance.

## Validator Threshold Audit

The validator tolerance is `0.003999140885` in transformed area units. Rectangle
conflict counts were unchanged after applying it. Across all 110 K256 pairs
involving the four rotated footprints, an exhaustive audit checked 16,601
unique positive-overlap displacements against Shapely. Sixty-two displacements
were within tolerance; the minimum area was `1.300819e-5` transformed units.
Filtering every affected candidate pair removed the 3,991 clauses above.
K256 remained `UNSAT`, so that boundary survives the correction.

In the superseded strict-positive model, constraining each K512 domain to its
first 256 sites through assumptions was `UNSAT` in 8.439 seconds. Its sufficient
18-component diagnostic core was:

```text
C202 C502 C601 C604 C611 C612 FV601 FV602 FV617 FV701
L8606 L8607 L8626 L8630 R602 R605 R704 RT201
```

Releasing any one of six sampled core components, or any of six sampled pairs,
remained `UNSAT`. Releasing all 18 at once was `UNKNOWN` after 180 seconds.
These domain-assumption runs have not yet been repeated with the corrected
threshold and are not acceptance proofs.

## Fixed-Site Core Chain

Guide fixing gives a stronger decomposition because all unfixed components
retain K512 domains. The following deterministic core-union path reuses exact
candidate-pair clauses:

| Movable | Fixed | Status | Time | Next sufficient fixed core |
| ---: | ---: | --- | ---: | --- |
| 0 | 30 | `UNSAT` | 0.125 s | `FV601` |
| 1 | 29 | `UNSAT` | 0.121 s | `C201 C202 C601 C604 C612 FV602 FV617 L8607` |
| 9 | 21 | `UNSAT` | 0.182 s | `C203 C502 C611 FV301 FV604 FV701 L8626 L8630 RT201` |
| 18 | 12 | `UNSAT` | 31.657 s | `C204 FV607 L8606 R602 R605 R704` |
| 24 | 6 | `UNSAT` | 116.148 s | `C301 C701 C8653 FV618 R604` |

The next union leaves 29 components movable and only `C501` fixed. The 24/6
solve used Glucose42 and accumulated 425,545 conflicts, 5,461,407 decisions,
and 200,850,791 propagations. This is a sufficient release path, not a proof
that 29 is the minimum. An incremental breadth-first audit queried 100,000
alternative movable sets, reaching size 10 without a SAT result. A minimum-
hitting-set audit queried another 1,000 size-six candidates; all were `UNSAT`.

Acceptance-threshold artifact SHA-256 values are:

```text
K256:              38678d2dcb33e0817b41eab05b4eb4eee7e785b88a73d787af9aad1292f2efc2
area audit:         d237979c86e09ff87238327580a40fca005e1f5612f93bb7d205f5ba5f00bcbe
fixed 30:           f90aca737d97bbd58657d601c8c31b751490ac33cc8fcb71b66357e1c3ea2151
movable 1:          a13dac317713f9a7dddc6374e1d979307d31c67d003e41e5114a9a8696397f5c
movable 9:          67a04922f8b3533ed82c6cdf488af04a02025d0e3e48dd2408215c8ceee8d505
movable 18:         1535dbc02d592e489dd3dbacf0da34d61e3956fb21800ca17fccae781cf2f253
movable 24:         a9f5e2ecb4d8ab37c7fa60587d5a655b04078d8dcc9a11612cb00ecb4007a419
```

The earlier strict-positive hashes remain recoverable from commit `38cb9cc`
and must not be mixed with these corrected results.

## Acceptance Impact

K256 is closed for this guide, but K512 remains unresolved. No zero-overlap
TOP placement or score improvement has been produced. Before promoting a CNF
result, obtain zero keep-in and overlap counts from full-board Shapely
validation, replay with one worker, combine the known legal BOTTOM placement,
and verify native HPWL/RSMT score `>= 1.0`.
