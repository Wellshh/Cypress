# M336-018: Anchor Relocation Requires Global Repacking

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `c08e0f2`

## Problem

Restoring fixed `EMI601` and `Q601` to their manual-baseline coordinates
recovers necessary HPWL potential, but it invalidates a placement packed around
their source coordinates. This is not repairable by moving only the directly
overlapping components or their first physical-neighbor ring.

The existing exact-legal `0.05 mm` skeleton has HPWL `19435.527800` under the
runtime endpoint contract. Restoring both anchors lowers HPWL to `17320.120203`
and raises the necessary score upper bound from `0.785179` to `0.881078`, but
creates seven exact overlaps:

| Anchor | Overlapping controlled components |
| --- | --- |
| `Q601` | `C601`, `FV601`, `FV604`, `FV607`, `FV701` |
| `EMI601` | `FV302`, `MHC8601` |

## Deterministic Mobility Proofs

The corrected `decomposed` model fixed a complete skeleton hint and released
explicit component sets. All runs used one worker, seed 1000, the fixed quality
assignment, complete exact `0.05 mm` domains, and a loose score `0.1` gate.

| Released sites | Fixed sites | Status | Branches | Wall time |
| ---: | ---: | --- | ---: | ---: |
| 7 direct conflicts | 93 | `INFEASIBLE` | 0 | `14.456664 s` |
| 17 direct + distance-1 neighbors | 83 | `INFEASIBLE` | 0 | `16.916226 s` |

Thus at least one component outside the measured first neighbor ring must move,
or the region assignment must change. Releasing all 100 components but limiting
each to the 4096 sites nearest the skeleton was also `INFEASIBLE` after
1,300,941 branches and `150.440901 s`. This only excludes that local site
subset, not each component's full feasible domain.

## Score-1 Search Boundary

Using the HPWL `14057.307686` no-collision candidate as a guide produced these
corrected-model results:

| Candidate subset | Status | Evidence |
| --- | --- | --- |
| 1024 nearest sites | `INFEASIBLE` | presolve, 101,680 total sites |
| 4096 nearest sites | `UNKNOWN` | 300.359 s, 906,641 branches |
| dual 4096 with legal skeleton | `UNKNOWN` | 300.350 s, 165,704 branches |

The two `UNKNOWN` runs do not establish infeasibility and used eight workers
for candidate discovery only.

## Diagnostic Correction

`solve_discrete_placement.py` now accepts repeatable `--movable-refdes` flags.
With a complete fixed-assignment site hint, every unlisted controlled component
is fixed by a model equality. The mode rejects unknown refdes, missing hints,
optimized assignments, and simultaneous `--fix-site-hint`. Reports include the
exact movable list and fixed-site count.

## Evidence Artifacts

Generated audit hashes are:

| Result | SHA-256 |
| --- | --- |
| fixed skeleton under restored anchors | `c5ee25c88073696c6cc252d332bfbf2237bb3587e22d19058645a315e246267a` |
| seven-component full-domain proof | `1f2d72afd685cd846b01a89fb1fd3f42649701b45d01e6e59f26aaaeb2c28555` |
| 17-component full-domain proof | `086a0c10e43b4e63d58a0353c0040c8a1d19cd33f5ae536d6b52ed4e7276e845` |
| all-component 4096-site proof | `b176d6ecc93fd977621cf0d9da294bac63c04c0672eedbde871c65cf5b1c818d` |

## Next Steps

1. Search complete domains with all controlled components released and a loose
   quality gate to establish a legal skeleton under the new anchor contract.
2. If the fixed assignment is infeasible, couple collision constraints to
   bottom-region assignment choices.
3. Only then optimize HPWL, replay with one worker, and obtain native RSMT.
4. Replace endpoint-only overrides with one consistent anchor position source
   for freezing, targets, reports, and net endpoints.

## Acceptance Criteria

- The restored-anchor contract has an exact zero-overlap placement.
- A single-worker replay reproduces its sites and metrics.
- Native HPWL/RSMT normalized score is at least `1.0`.
- Anchor coordinates and projected targets come from the same warm-start state.
