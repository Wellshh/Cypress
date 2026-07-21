# M336-190: Covered Fast Path Leaves the E2 Runtime Gate Open

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `d17a243`

## Finding

The single M336-189-authorized combined scale-1 D1 preserves exact legality,
placement bytes, native quality, and every native optimizer signal. It still
misses the fixed E2 GPU-optimization limit:

```text
E2 measured GPU optimization  2.220134705305100 s
E2 fixed limit                2.161724000000000 s
remaining gap                 0.058410705305100 s (2.702%)
```

E3 passes its independent `2.695705 s` limit at `2.211762167513371 s`.
The combined D1 therefore remains failed and N6 stays open. No D2, D3, E4,
repair, fallback, Legalization, CP-SAT, learning-rate change, or parameter
sweep ran.

## Reproduction Contract

The run used commit `d17a243c3ef495add593bd3b833b749e6a532bd5`, seed
`1000`, ten iterations, learning-rate scale `1`, deterministic CuBLAS
`:4096:8`, and physical GPU 2. Its command is the M336-188 command with only
the output, summary, and report paths changed to:

```text
results/m336/native-cypress/
  m336-189-covered-keepin-combined-d1-warm-10-scale1/
```

Source/install implementation hashes match. The modified implementation hash
is `6c7f35cc3fb46deab9aa67fd4d1bc1ef0a9133fa286dcbdba7d4d39a4c826b9f`.
Input hashes and the manual-EMI601/runtime-Q601 endpoint contract are unchanged.

## Native and Quality Parity

Both arms execute `NonLinearPlace`, `PlaceObj`, 13 backward calls, and ten
changing CUDA Adam steps. All ten proposals are accepted on retry index zero.
Every before/projected/accepted checkpoint has zero keep-in violations and
zero positive-area overlaps; final float64 replay is 100/100 contained with
zero coordinate drift.

| Arm | Placement SHA-256 | HPWL | FLUTE RSMT | Normalized score |
| --- | --- | ---: | ---: | ---: |
| E2 | `44f62b5010c88550ef5927ba454ef9876f9143ef00da5b6f0af2d4ac75154dfd` | `15632.948904752731` | `17327.972` | `0.9280310677092565` |
| E3 | `59c410852bc298e67f8e9a5038260bf5ea1b46e3070296b828d51d3653cb6c27` | `15632.785998106003` | `17327.737` | `0.9280422081026970` |

Both hashes and scores exactly match M336-188. This run is also the second
independent native-optimizer E3 execution with the same serialized placement
hash. E3 retains the same small positive mean/p90 anchor direction,
`0.001812986%/0.000473979%`; it does not satisfy the final 25%/15% gate.

## Fast-path Effect

The new counters prove that all constrained footprints take the intended fast
path in both arms:

| Exact-audit metric, 31 calls | E2 | E3 |
| --- | ---: | ---: |
| Covered footprints | `3100` | `3100` |
| Fallback footprints | `0` | `0` |
| Keep-in invalids | `0` | `0` |
| Predicate time | `0.004072741 s` | `0.004032550 s` |
| Fallback bookkeeping | `0.000391152 s` | `0.000364311 s` |
| Total keep-in stage | `0.004519233 s` | `0.004452577 s` |
| Total position audit | `0.038758447 s` | `0.037645176 s` |

Against M336-188, E2 keep-in saves `0.161745317 s`, total audit saves
`0.159391845 s`, and exact contact projection saves `0.131417384 s`. E2 GPU
optimization improves by only `0.025634047 s`; E3 improves by `0.121363508 s`.
The placement bytes prove this is timing behavior, not a different search path.

The non-contact remainder of the counted E2 GPU metric increases from
`1.470878635 s` (`2.245768752 - 0.774890117`) to `1.576661972 s`
(`2.220134705 - 0.643472733`), an offsetting `0.105783337 s`. A 37-sample
one-second GPU monitor records five short active samples, maximum SM utilization
`25%`, and no sustained compute activity. Three external processes held GPU
memory before the run; this sampling cannot exclude subsecond contention or
ordinary host/runtime variance.

## Exact Delta Audit Bound

The user-designated second candidate is an exact delta audit. The required
contract remains:

```text
if origin_report.is_exact_legal and provenance_matches(origin):
    audit changed nodes against keep-in, fixed obstacles, and same-side nodes
    merge into a deterministically sorted complete report
else:
    audit_full()
```

Unchanged/unchanged pairs may be reused only from a legal origin report bound
to exact position bytes, PlaceDB identity, geometry/templates, epsilon, and
side assignment. Any missing/mismatched provenance must fail back to the full
audit. Changed/changed pairs must be emitted once, overlap floats and JSON order
must match the full scalar oracle, and the merged report must retain complete
repair closure.

However, the current E2 full position-audit total is only `0.038758447 s`.
Even deleting it entirely from the measured GPU metric would yield
`2.181376258 s`, still `0.019652258 s` above the fixed gate. Therefore a delta
audit alone cannot deterministically close this specific measured shortfall.
Before another D1, offline evidence must identify additional coupled counted
work or demonstrate sufficient repeated fixture margin; implementation must not
be justified by audit savings alone.

If strict delta parity and full-counted-path profiling still cannot provide a
stable margin, stop D1 micro-optimization. The next decision is architectural:
human approval is required before reducing authority/FLUTE topology-selection
frequency into a bounded micro-legalization boundary or changing the runtime
gate. Collision policy, anchor, LR, and Legalization remain frozen.

M336-191 subsequently measures the required changed-node scope. Every proposal
changes all 100 constrained nodes relative to its legal origin, so that narrow
contract cannot accelerate the validator. Only post-correction deltas relative
to an immediately preceding exact but overlap-illegal report are sparse; any
implementation must retain and merge those unchanged conflict rows exactly.
M336-192 implements that generalized contract and measures only
`0.009932717 s` median saving over all 17 sparse correction calls. The runtime
gate remains mathematically unreachable by audit elimination alone, so the
required next action is now the human architecture decision, not another D1.

## Artifact Identity

```text
summary.json  7d0b23439e0121299902c8b5216b86e278881db4df16cae32828d458b8f0496b
REPORT.md     6b152ccd108b83ce396b343615f7cb5ce5ee05064ca43e38f874ee9acbe816c7
gpu2-dmon.log 482347d907b0e0dacc1ffe837a5446b5ee4ba59b0a0605d458cedf59c8730617
```

Input manifest validation passes with the known 27-declared/25-enumerated
warning. The tracked `DREAMPlace.log` and user-owned M336-141 aggregate retain
their prior SHA-256 values.
