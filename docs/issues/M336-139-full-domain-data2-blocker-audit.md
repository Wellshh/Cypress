# M336-139: Full-Domain Audit Identifies Frozen DATA2 Blocker

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `f0fab78`

## Problem

M336-137/138 measured guide targets only against the selected K4096 set. The
unchanged DATA2 distance strongly suggested a geometric obstruction, but it
could not distinguish an off-lattice target, keep-in exclusion, fixed-obstacle
pruning, or candidate-budget truncation. Increasing K or changing weights
without this classification would spend solver budget without changing the
underlying feasible domain.

## Implementation

The default-off candidate audit now records three target layers for every
guide/component pair:

- continuous footprint containment in the assigned keep-in;
- nearest exact keep-in lattice site and canonical region index;
- nearest complete obstacle-pruned site and canonical region index.

It also records every overlapping uncontrolled fixed obstacle by refdes and
exact area in model units and mm2. Per-guide and per-net summaries separately
count continuous, exact-lattice, exact-obstacle-free, and blocked targets.
These diagnostics do not enter candidate ordering or the CP-SAT model.

The portable exporter validates distance scaling, exactness flags, canonical
indices, blocker identities/areas, and component/net aggregate counts. It
continues to validate the M336-137 and M336-138 references without migration;
partially present full-domain fields fail closed. Eighty focused tests pass.

## Exact DATA2 Classification

The M336-138 seven-guide portfolio was replayed unchanged against the portable
M336-138 reference. Candidate comparison is exactly 73,728/73,728 with
Jaccard `1.0`, so the new instrumentation does not alter site selection.

| Endpoint | Continuous keep-in | Exact lattice | Keep-in sites | Obstacle-free sites | Frozen blocker | Overlap mm2 | Nearest obstacle-free site |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| `FV710` | yes | yes | 10,818 | 6,088 | `MIC401` | 0.081943924 | 2.934706 mm |
| `R708` | yes | yes | 11,643 | 7,048 | `MIC401` | 0.013330545 | 0.050000 mm |

`FV710`'s exact target center is `[469.949524,145.984320]`; its nearest
obstacle-free center is `[523.943725,168.981850]`. `R708` moves from exact
target `[469.949524,147.984106]` to adjacent center
`[468.949632,147.984106]`.

Both collision-relaxed targets are therefore valid exact keep-in lattice
sites, not off-grid approximations. They are absent from the complete
uncontrolled-obstacle-free domain because each overlaps frozen `MIC401`.
M336-124 also records controlled/releasable `B402` collisions at these target
coordinates, but releasing `B402` cannot remove the `MIC401` obstruction.

All five other dedicated residual guides have exact obstacle-free coverage for
their own listed endpoints and no uncontrolled fixed blocker.

## Reproducibility

The no-objective replay returned `OPTIMAL` with HPWL
`15634.450477332834`, 100/100 containment, zero keep-in violations, zero
overlaps, and byte-identical M336-118 placement. Build/solve time was
95.085/23.771 seconds and deterministic time was 8.073.

The portable reference is
`experiments/m336/coverage/M336-139/m130-target-domain.json` (SHA-256
`d21a6dc381038efc918e0e2384fae4b82e43a5857dc002ee09714c7d77df89c0`).
All 11 dependencies match and strict self-Jaccard is `1.0`. A feature-off K1
run remained `OPTIMAL` at integer HPWL `15634450483` and produced the exact
M336-118 placement SHA-256.

## Decision

Do not increase K or DATA2 guide weight to recover the collision-relaxed
coordinates: they do not exist in the complete obstacle-pruned domain. Keep
`MIC401` frozen. Instead, optimize `PSIM2_DATA2` span directly over exact
feasible sites, initially releasing `FV710,R708,B402` plus measured physical
partners, under a global HPWL rise envelope. Certify the resulting legal
alternative before using it as a topology guide. M336-118 remains the scoring
incumbent.
