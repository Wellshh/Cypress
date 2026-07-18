# M336-040: Exact-Site CNF Exposes a 24-Component Repacking Core

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
double-precision centers: axis-aligned rectangles use strict interval overlap,
and other footprints use the production convex decomposition and separating
axes. Touching is allowed. Every future SAT result must still pass the
independent Shapely full-board validator; the prototype is not a production
dependency.

The local domains are ordered by distance from the one-overlap guide:

| Domain | Candidates | Conflict clauses | Status | Solve time |
| --- | ---: | ---: | --- | ---: |
| K256 | 7,436 | 3,315,109 | `UNSAT` | 1.232 s |
| K512 | 14,806 | 13,481,902 | `UNKNOWN` | 300 s |

Four K512 CDCL runs (`glucose42`, `glucose3`, `maplesat`, and `minisat22`)
all timed out at 300 seconds. Kissat and CaDiCaL variants produced no result
within 600 seconds. These timeouts are not infeasibility evidence.

Constraining each K512 domain to its first 256 sites through assumptions was
`UNSAT` in 8.439 seconds. Its sufficient 18-component core was:

```text
C202 C502 C601 C604 C611 C612 FV601 FV602 FV617 FV701
L8606 L8607 L8626 L8630 R602 R605 R704 RT201
```

Releasing any one of six sampled core components, or any of six sampled pairs,
remained `UNSAT`. Releasing all 18 at once was `UNKNOWN` after 180 seconds.

## Fixed-Site Core Chain

Guide fixing gives a stronger decomposition because all unfixed components
retain K512 domains. The following deterministic core-union path reuses exact
candidate-pair clauses:

| Movable | Fixed | Status | Time | Next sufficient fixed core |
| ---: | ---: | --- | ---: | --- |
| 0 | 30 | `UNSAT` | 0.121 s | `FV601` |
| 1 | 29 | `UNSAT` | 0.126 s | `C201 C202 C601 C604 C612 FV602 FV617 L8607` |
| 9 | 21 | `UNSAT` | 0.163 s | `C203 C502 C611 FV301 FV604 FV701 L8626 L8630 RT201` |
| 18 | 12 | `UNSAT` | 39.766 s | `C204 FV607 L8606 R602 R605 R704` |
| 24 | 6 | `UNSAT` | 158.229 s | `C301 C701 C8653 FV618 R604` |

The next union leaves 29 components movable and only `C501` fixed. The 24/6
solve used Glucose42 and accumulated 535,668 conflicts, 6,071,065 decisions,
and 231,248,529 propagations. This is a sufficient release path, not a proof
that 29 is the minimum. An incremental breadth-first audit queried 100,000
alternative movable sets, reaching size 10 without a SAT result. A minimum-
hitting-set audit queried another 1,000 size-six candidates; all were `UNSAT`.

Artifact SHA-256 values are:

```text
K512 with K256 assumptions: 957ea95986c47394087aaea68ccf6e24545db124858e90be75430f5e78c9ccbf
fixed 30:                  437779f8bd57ddb5174f12066149b27ed3ccbd581da5c542dbd9fafd9868e662
movable 1:                 a58f83ebb272b9be04eb668f551064c15f575e2c906c26d0c43c8e6a9ed635db
movable 9:                 e27c0da3dc86ca1b28af013d27b8e3b1a993412e884836fc330a8cbbd5ffe6b6
movable 18:                e705bd7581ba8475205fefb1091b366f72f825e7185a32a72e7eb12b485bf790
movable 24:                e3bf87f6b62a783ae4f43c84d2415cbec2044f6364b3d87757cc84cc3b1d3464
100k BFS audit:            446815eb4c9a8515b7e75732f4dd63aa9ee77c0d5af4e4df6bcbe9fbc59e1fc4
Hitman audit:              f70c9b170527969a8359ecf38817440e25a8ea0f024ec71661d9463473b64537
```

## Acceptance Impact

K256 is closed for this guide, but K512 remains unresolved. No zero-overlap
TOP placement or score improvement has been produced. Before promoting a CNF
result, audit candidate-pair classifications against Shapely, obtain zero
keep-in and overlap counts, replay with one worker, combine the known legal
BOTTOM placement, and verify native HPWL/RSMT score `>= 1.0`.
