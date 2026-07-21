# M336-188: Vectorized Exact Audit Leaves the E2 Runtime Gate Open

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `7c03b8c`

## Finding

The explicitly authorized post-M336-187 combined D1 completed both
checkpoint-warm E2 and E3 arms on physical GPU 2. The run proves the complete
native CUDA path, exact legality, float64 serialization, and the intended
quality direction. It does not promote N6 because E2 GPU optimization still
exceeds its fixed M336-179 limit:

```text
E2 measured GPU optimization  2.245768751949072 s
E2 fixed limit                2.161724000000000 s
remaining gap                 0.084044751949072 s (3.887858%)
```

E3 passes its independent `2.695705 s` limit at `2.333125675097108 s`.
No D2, D3, E4, repair, fallback, CP-SAT, or parameter ladder was run.

## Reproduction Contract

The fresh atomic run used commit
`7c03b8cfe9147c5f435ae1999ac45677000ac85a`, seed `1000`, ten iterations,
learning-rate scale `1`, deterministic CuBLAS `:4096:8`, and physical GPU 2.
Its fixed inputs were:

```text
M336-118 float64 placement  3d3d3ef72bab1f279e9906ada249a724a451c8f415d777f98f84adfa1d93cdbc
M336-118 assignment         e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87
pcb_geometry.json           af2f270e520104a0cafbddd7c36ef942a1086fe5e995fd60d7dae705336c6b98
```

The exact runner arguments were unchanged from M336-183 except for the fresh
run-local paths:

```text
--experiments E2 E3 --seeds 1000 --iterations 10
--learning-rate-scale 1 --gpu --irregular-density
--footprint-collision --collision-gradient-ratio 0.1
--collision-margin-mm 0 --collision-tau-mm 0.025
--exact-step-guard --exact-step-guard-backoff 0.5
--exact-step-guard-max-retries 4 --no-collision-pair-diagnostics
--exact-contact-projection --exact-contact-projection-max-iterations 8
--exact-contact-projection-mode protected_proposal_authority_search
--exact-contact-projection-max-nodes 32
--exact-contact-projection-max-cover-component-nodes 16
--exact-contact-projection-max-authority-states 4096
--exact-contact-projection-authority-search-strategy pairwise_factorized
--exact-contact-topology-tiebreak --exact-contact-topology-min-net-degree 32
--initialization-track checkpoint_warm_start
--checkpoint-placement experiments/m336/checkpoints/M336-118/placement.float64.pl
--feasible-domain-cache-dir results/m336/native-cypress/cache/feasible-domains
--grid-mm 0.05 --clearance-mm 0 --keepin-margin-mm 0.1
--keepin-margin-tau-mm 0.05 --site-mm 0.05
--assignment experiments/m336/checkpoints/M336-118/assignment.json
--baseline-geometry pcb_geometry.json --bookshelf-dir results/m336/bookshelf
--baseline-output-dir results/m336/baseline
--placer install/dreamplace/Placer.py --anchor-gradient-ratio 0.1
--output-dir results/m336/native-cypress/m336-188-vectorized-audit-combined-d1-warm-10-scale1
--summary-path results/m336/native-cypress/m336-188-vectorized-audit-combined-d1-warm-10-scale1/summary.json
--report-path results/m336/native-cypress/m336-188-vectorized-audit-combined-d1-warm-10-scale1/REPORT.md
```

Source/install implementation hashes matched. The pre-existing tracked
`DREAMPlace.log` SHA-256 remained
`012235903d7fd4927e9f1f9ace79cdf20328870d7c34ba0d42d2edb89e74a92b`, and the
user-owned M336-141 aggregate remained
`4091eb8e0611a8042bbc0bf5bed6d15843909d2168a21a4a34655653607ff77d`.

## Native Execution and Legality

Both arms report `NonLinearPlace` and `PlaceObj` execution, 13 backward calls,
ten changing CUDA Adam steps, and ten accepted first attempts at the unchanged
`0.023085560649633408` learning rate. Every accepted-step checkpoint and both
post-serialization reports have `100/100` containment, zero keep-in
violations, and zero overlaps.

The contact contract also remains bounded:

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Maximum active contact pressure | 38 | 45 |
| Maximum cumulative corrected nodes | 22 | 26 |
| Maximum component nodes | 5 | 5 |
| Logical authority states | 2,158 | 1,987 |
| Node / pair / full exact tests | 758 / 1,116 / 141 | 765 / 1,129 / 141 |
| Protected edges reopened | 0 | 0 |
| Topology score calls | 34 | 34 |
| Authority / consensus selections | 10 / 7 | 10 / 7 |

Active pressure remains an independent diagnostic; the enforced 32-node limit
applies to cumulative corrected nodes. Proposal and accepted validation each
reuse exact tensor provenance on all ten steps. GND remains the only topology
tie-break net (`net_id=6`, degree 84).

Float64 replay has zero coordinate error and identical input/replay hashes:

```text
E2  44f62b5010c88550ef5927ba454ef9876f9143ef00da5b6f0af2d4ac75154dfd
E3  59c410852bc298e67f8e9a5038260bf5ea1b46e3070296b828d51d3653cb6c27
```

The E2 hash is byte-identical to the quarantined M336-183 E2 placement. This
directly proves that M336-184 through M336-187 preserve that arm's coordinates.
The single authorized run does not provide a second native-optimizer E3 hash;
its serialization replay is exact but is not an independent optimizer repeat.

## Quality Evidence

| Arm | Native HPWL | Native FLUTE RSMT | Normalized score |
| --- | ---: | ---: | ---: |
| E2 | `15632.948904752731` | `17327.972` | `0.9280310677092565` |
| E3 | `15632.785998106003` | `17327.737` | `0.9280422081026970` |

E2 passes the M336-174 HPWL/RSMT sub-gates (`15633.109790` and `17328.300`).
E3 improves HPWL by `0.162906647` and RSMT by `0.235`. Its anchor mean and p90
improve over E2 by only `0.001812986%` and `0.000473979%`, respectively. This
is the strictly positive D1 direction, not the final 25%/15% anchor gate.

## Runtime Evidence

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Optimization wall | `2.271519810 s` | `2.356532950 s` |
| Excluded guard/diagnostic | `0.025751058 s` | `0.023407275 s` |
| Fixed GPU metric | `2.245768752 s` | `2.333125675 s` |
| Exact contact projection | `0.774890117 s` | `0.802827392 s` |
| End to end | `15.381547434 s` | `15.219518039 s` |
| Feature-off end-to-end ratio | `1.308634x` | `1.283377x` |

Relative to M336-183, E2 GPU time improves by `0.100759150 s` (`4.293968%`)
and contact projection improves by `0.169033276 s` (`17.907521%`) while the
placement remains byte-identical. M336-184 also reduces excluded guard work;
that saving is not misapplied to the fixed GPU metric.

The new exact-audit counters expose the residual E2 work over 31 calls:

| Exact-audit phase | E2 seconds |
| --- | ---: |
| Coordinate snapshot | `0.001025179` |
| Footprint translation | `0.003685700` |
| Keep-in difference/area | `0.166264551` |
| Fixed overlap | `0.002711009` |
| Constrained overlap | `0.019826274` |
| Total audit | `0.198150292` |

The fixed cache records 30 hits and one miss. Keep-in evaluation is `83.9%` of
the measured audit total and exceeds the remaining `0.084045 s` gate gap, but
these nested values are not additive guarantees. A 69-sample GPU monitor saw
five short compute-active samples, aligned with the two native arms, and no
sustained external GPU activity; one-second sampling cannot exclude all
subsecond contention, so the declared run remains the authority.

## Decision and Next Mechanism

The combined D1 fails its conjunctive E2 runtime gate. N6, M336-179, M336-181,
M336-184, M336-185, M336-186, and M336-187 remain open. Do not run D2, D3, E4,
another D1, a seed/LR/ratio ladder, repair, fallback, or CP-SAT.

Before any further effect authorization, profile a strict-equivalent keep-in
audit fast path on the preserved M336-188 coordinates. A candidate may batch
an exact `covered_by` test and skip `difference` only for footprints proved
fully covered; every non-covered footprint must retain the same GEOS
`difference` and epsilon-area path. It must preserve report bytes on the full
M336-187 scalar/vector corpus, add covered/fallback counters, pass installed
CPU/GPU float32/64 tests, and show actual fixed-fixture benefit. No timing
reclassification or legality approximation is acceptable.

M336-189 is the successor contract. It requires prepared
`covers(region, footprint)` only as a zero-exterior-area short circuit and
retains the original difference/area epsilon rule for every predicate miss.
It also freezes the offline performance gate and the conditions for exactly one
unchanged combined D1; this issue's measured placement and runtime remain the
comparison authority.

## Artifact Identity

The diagnostic artifacts remain under the ignored run root and are not a
portable promotion checkpoint:

```text
summary.json  9a1c3ff802450221ed597160aec8ab1e2e200cce49f8b5028bb71333119d192e
REPORT.md     19446c200c8533608d76ca8423064eabd6868d07fccde12815318f7b7088cb65
gpu2-dmon.log 959a145e9fa0a9d34187b0852084f50eaaa736279162c1f99f533e15a722b618
```
