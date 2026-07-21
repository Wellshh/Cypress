# M336-189: Strict Covered Keep-in Audit Fast Path

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `7065941`

## Finding

M336-188 passes the D1 legality and quality contracts but misses the fixed E2
GPU-optimization limit by `0.084044752 s` (`3.887858%`). Its 31 exact position
audits consume `0.198150292 s`; vectorized keep-in `difference` plus `area`
accounts for `0.166264551 s`. Every accepted state is 100/100 contained, so
constructing 100 difference geometries on every audit is avoidable proof work.

This is a runtime-only implementation issue. Collision behavior, anchor
control, learning rate, Legalization, repair, and placement objectives must not
change.

## Strict Semantic Contract

The existing authority is:

```text
outside_area = area(footprint - assigned_region)
invalid = outside_area > epsilon
```

A topological predicate cannot replace that rule. A footprint may fail
`covers` while its outside area is positive but no greater than `epsilon`; the
old rule still accepts it. The only equivalent short circuit is:

```text
covers(assigned_region, footprint) == true
    -> outside_area is exactly zero; accept
covers(assigned_region, footprint) == false
    -> run the original difference/area/epsilon test
```

Use `covers(region, footprint)`, not `covered_by(footprint, region)`, so the
static first argument can use a prepared geometry. Group constraints by
`region_id`, prepare one independent WKB-identical copy per region, and retain
the existing per-component region array only for exact fallback. Preparing a
copy must not mutate shared `self.regions`.

Local API verification uses Shapely `2.1.2`: `shapely.prepare()` mutates the
copy in place and returns `None`; a scalar prepared first argument broadcasts
over a footprint array. Boundary contact is covered, while any true exterior
point enters fallback.

## Required Diagnostics

Retain `batched_keepin_seconds` for report compatibility and add cumulative:

```text
keepin_predicate_seconds
keepin_fallback_seconds
keepin_covered_count
keepin_fallback_count
keepin_invalid_count
```

For M336's legal D1 path, `covered_count` should approach 100 per audit and
`fallback_count` should approach zero. A large fallback count is a projection
lifecycle finding, not permission to weaken validation.

## Parity Tests

The fast path must preserve the complete scalar-oracle report and repair-ID
set, including list/JSON order and overlap-area floats. Reuse the M336-187
27-scenario synthetic corpus and 204 real CPU/H100 float32/float64 comparisons.
Add focused cases for outside area equal to zero, strictly between zero and
epsilon, equal to epsilon, and greater than epsilon. Cover boundary contact,
holes, concave regions, unequal/concave footprints, both sides, prepared and
unprepared predicates, and mixed covered/fallback batches.

Parity includes `keepin_invalid_refdes`, fixed conflicts, constrained pair
conflicts, repair IDs, final contact-authority winner, and final placement
hash. The optimization is unconditional only after this differential evidence
passes; it is not a configurable approximation.

## Offline Performance Gate

Do not launch D1 immediately after implementation. First run the same audit
call count on preserved M336-188 final positions and deterministic real M336
perturbations. Promotion requires either:

```text
keep-in stage saving >= 0.12 s at the same call count
or
total position-audit time <= 0.075 s
```

The M336-188 artifacts preserve final E2/E3 placements and per-step hashes,
displacement summaries, reports, and contact decisions, but not complete
proposal coordinate tensors. Therefore the offline benchmark may truthfully
replay final positions and deterministic real-position corpora; it must not
claim byte-for-byte proposal replay. This artifact gap does not authorize a
native optimizer rerun to regenerate a benchmark corpus.

## Effect Gate

Only after parity and the offline performance gate pass may one unchanged,
combined, scale-1 D1 run execute. It must reproduce:

| Arm | Placement SHA-256 | HPWL | FLUTE RSMT | GPU limit |
| --- | --- | ---: | ---: | ---: |
| E2 | `44f62b5010c88550ef5927ba454ef9876f9143ef00da5b6f0af2d4ac75154dfd` | `15632.948904753` | `17327.972` | `2.161724 s` |
| E3 | `59c410852bc298e67f8e9a5038260bf5ea1b46e3070296b828d51d3653cb6c27` | `15632.785998106` | `17327.737` | `2.695705 s` |

Every accepted step must remain 100/100 contained with zero positive-area
overlap. Before that gate, D2, D3, E4, learning-rate scale 2, anchor-ratio
sweeps, Legalization, repair, fallback, CP-SAT, and any collision-policy change
remain prohibited.

If this strict fast path misses the offline gate, stop and evaluate an exact
delta audit as a separate issue. It must require a legal origin report with
matching tensor provenance and revalidate only changed nodes; otherwise it
must fall back to the full audit. No delta implementation is authorized by
this issue.

## Implementation and Offline Evidence

The strict fast path is implemented without a feature flag or altered timing
boundary. `_position_audit_constrained_templates()` now stores read-only index
arrays grouped by `region_id` and one prepared WKB-identical region copy per
group. The original regions retain their prior prepared/unprepared state. Each
audit evaluates grouped `covers` first and sends only predicate misses through
the original vectorized `difference`, `area`, and strict `> epsilon` test.

The focused epsilon corpus proves all four required outcomes:

| Exterior area | Predicate | Existing area rule | Result |
| ---: | --- | --- | --- |
| `0` | covered | valid | fast-path valid |
| `0.125 < 0.25` | not covered | valid | fallback valid |
| `0.25 = 0.25` | not covered | valid | fallback valid |
| `0.5 > 0.25` | not covered | invalid | fallback invalid |

The 27-scenario committed synthetic corpus still compares complete reports and
repair sets across CPU/H100 and float32/float64. New focused cases add region
holes, concave boundaries, boundary contact, concave/unequal footprints, both
sides, mixed fast/fallback batches, prepared/unprepared predicate equivalence,
and source-region state isolation.

The previous real 51-position corpus was described in M336-187 but its position
vectors were not persisted. M336-189 therefore starts from the preserved E2
placement and constructs a new deterministic 51-position real-geometry stress
corpus with keep-in, fixed, and same-side constrained conflicts. All `204/204`
CPU/H100 float32/float64 comparisons match the scalar oracle for the complete
report object, serialized sorted JSON, floating overlap areas, and repair-ID
set. Each conflict category is exercised in 200 comparisons. This is new
differential evidence, not a false claim that missing M336-187 vectors were
replayed.

The performance fixture reparses the unchanged M336-188 placements and runs 31
full audits per sample, including one template/fixed-cache miss and 30 fixed
cache hits. Seven independent E2 samples report:

| Metric | M336-188 | M336-189 median | M336-189 range |
| --- | ---: | ---: | ---: |
| Total position audit | `0.198150292 s` | `0.029331116 s` | `0.029033430-0.030636644 s` |
| Keep-in stage | `0.166264551 s` | `0.003576316 s` | `0.003539344-0.003710980 s` |
| Covers predicate | not split | `0.003381714 s` | `0.003345454-0.003464051 s` |
| Exact fallback | not split | `0.000158258 s` | `0.000156408-0.000197632 s` |

Every E2 sample records 31 calls, `3100` covered footprints, zero fallback,
zero keep-in invalids, and byte-identical reports. Keep-in saves
`0.162688235 s`, exceeding the `0.12 s` gate; total audit is also
`0.045668884 s` below the `0.075 s` gate. Three E3 samples independently give
`0.028731458 s` median total audit and `0.003547076 s` median keep-in with the
same 3100/0 covered/fallback split.

Input identity remains exact:

```text
E2 placement  44f62b5010c88550ef5927ba454ef9876f9143ef00da5b6f0af2d4ac75154dfd
E3 placement  59c410852bc298e67f8e9a5038260bf5ea1b46e3070296b828d51d3653cb6c27
source/install 6c7f35cc3fb46deab9aa67fd4d1bc1ef0a9133fa286dcbdba7d4d39a4c826b9f
```

After `cmake --install build`, all 265 applicable tests pass: anchor/keep-in
61, exact guard 11, exact contact projection and authority selection 61,
reproducibility 22, irregular density 9, and non-CP-SAT M336 baseline 101. Five
optional OR-Tools tests are excluded exactly as in M336-187. The tracked
`DREAMPlace.log` and user-owned M336-141 aggregate retain SHA-256
`012235903d7fd4927e9f1f9ace79cdf20328870d7c34ba0d42d2edb89e74a92b` and
`4091eb8e0611a8042bbc0bf5bed6d15843909d2168a21a4a34655653607ff77d`.

Both offline promotion alternatives pass. Exactly one unchanged combined
scale-1 D1 is now authorized by this issue. No optimizer, objective, repair,
fallback, Legalization, scorer, CP-SAT solve, D2, D3, or E4 was run while
producing this implementation evidence.
