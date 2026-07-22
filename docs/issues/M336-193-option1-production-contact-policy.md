# M336-193: Option 1 Production Contact Policy

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-22
**Decision authority:** Human architecture decision
**Affected evidence:** `M336-174` through `M336-192`

## Decision

Adopt architecture option 1 without changing the fixed `2x` runtime gate and
without freezing native Cypress development. The M336-192 protected-authority,
pairwise-factorized, native-FLUTE path remains intact as a default-off
`strict_reference` implementation. Production optimizer steps return to the
already implemented M336-174 proposal-medoid/component-consensus path.

This is a policy change, not a new collision heuristic. The production path
must retain the exact accepted-step guard, complete optimizer-state rollback,
learning-rate backoff, board projection, irregular Keep-in projection, and
zero positive-area overlap for every accepted position.

## Policy Contract

| Policy | Per-step contact action | Authority/FLUTE in hot loop | State |
| --- | --- | --- | --- |
| `strict_reference` | M336-192 protected proposal authority | Pairwise-factorized enumeration and HPWL-neutral FLUTE tie-break enabled | Preserved, default off |
| `consensus_per_step` | M336-174 deterministic proposal medoid and component consensus | Disabled | Production Phase A |
| `consensus_plus_stage_micro` | Same per-step consensus, plus one bounded stage-end closure | Disabled per step | Reserved; fail closed until D3 evidence authorizes implementation |

The runner and native execution report must serialize the selected policy.
Policy resolution must reject contradictory low-level mode, authority, or
topology settings. Historical configurations without a policy remain
replayable through their explicit low-level fields, but all new M336 runs must
select a named policy.

## Preserved Reference

`strict_reference` must continue to select:

```text
mode: protected_proposal_authority_search
authority search: pairwise_factorized
topology tie-break: native FLUTE, minimum net degree 32
exact audit: M336-192 covered-region and provenance-bound incremental paths
```

Its unit tests, diagnostics, exact legality, timing accounting, and
source/install byte parity remain mandatory. No code may delete, weaken, or
silently redirect this path merely because it is no longer the production
default.

## Phase A Authorization

After the issue, goal, roadmap, implementation, install, and focused tests are
committed, pushed, and pulled, run exactly one fresh current-head checkpoint-
warm scale-1 E2/E3 D1 on physical GPU 2, seed `1000`, ten iterations. Use
`consensus_per_step`; do not resume an old output.

The candidate passes only when both arms satisfy every gate:

- ten changing CUDA Adam steps and native objective/backward evidence;
- zero exact overlap after every accepted step;
- `100/100` containment and zero Keep-in violations;
- native HPWL and FLUTE RSMT regression no greater than `0.5%`;
- E2 and E3 GPU optimization and end-to-end ratios no greater than `2x` under
  the existing fixed comparison;
- non-negative E3 anchor direction versus E2;
- no D2, E4 repair, CP-SAT, fallback, resume, seed/LR/weight ladder, or broad
  legalization.

For the first comparison, do not redefine timing boundaries or baseline
values. If Phase A passes, gather paired repeated timing later on the same GPU
while retaining the same `2x` threshold.

## Conditional D3

Only a complete Phase A pass authorizes one checkpoint-warm 50-step scale-1
E2/E3 D3. Skip scale-2 D2. Every accepted D3 step must remain exact legal, and
the result must not rely on broad E4 repair.

Implement `consensus_plus_stage_micro` only if that D3 exposes a local discrete
contact-topology or RSMT defect. Its future contract is at most one stage-end
call, contact-touched closures only, at most 16 active nodes per component and
32 total, and no broad packing, checkpoint fallback, or full-domain CP-SAT.
The acceptance order is exact legality, selected-net HPWL, HPWL-neutral FLUTE
RSMT, native displacement, then anchor distance. An illegal or regressing
candidate is a no-op. Runtime is reported separately and end-to-end remains
within `2x`.

## Acceptance Criteria

- Named policies are deterministic, reported, and fail closed on conflicts.
- `consensus_per_step` reuses M336-174 behavior without authority enumeration
  or FLUTE calls in the optimizer hot loop.
- `strict_reference` tests and source/install parity remain green.
- The single Phase A run is recorded with complete gate evidence.
- D3 and stage micro remain blocked unless their preceding evidence gate passes.

## Implementation Evidence

The named policy layer now resolves directly to the existing projector modes;
it does not add or modify collision geometry. The M336 runner defaults to
`consensus_per_step` whenever exact contact projection is selected, serializes
the policy in config, run ID, result, summary, reproduction command, and native
execution evidence, and rejects contradictory low-level overrides.

`strict_reference` selects protected proposal authority,
`pairwise_factorized`, native topology tie-break, and minimum net degree `32`.
`consensus_per_step` selects `component_consensus`, exhaustive authority setting
only as an inert default, and no topology tie-break. Consequently the latter
does not construct authority component validators or a FLUTE evaluator in the
optimizer loop. `consensus_plus_stage_micro` is recognized but exits before any
placement work with a D3-authorization error.

Historical policy-free config files continue through their original low-level
fields. New named-policy configs are also validated inside `NonLinearPlace`, so
directly invoking `Placer.py` cannot bypass the runner contract. Scoring-only
float64 replay explicitly clears the policy together with all contact features.

After `cmake --install build`, all `271/271` applicable tests pass:

```text
anchor/keep-in                  64
exact contact                   63
exact accepted-step guard       11
reproducibility                 22
irregular density                9
non-CP-SAT M336 baseline       102
```

Five optional OR-Tools tests remain excluded; no OR-Tools solve was run.
Source/install SHA-256 pairs are identical:

```text
NonLinearPlace                 b7f01be5ae91d9f2913298b6cc70e118fdd346b0f543d641c9ab90127477f5a7
exact_contact_projection       ef7f3130b706cbe0694dba51a93403d4bc84531feedb0e426336a4c2771d8ccc
params.json                    19ca9b959653d4c27e58505fc4af7fe45d6231fa401b8cb159a656f16c16c509
exact contact tests            83fe77f4e13b3d1bb8847d527d8aa74ab3f00d12245541f4ae13188a2e3d9799
M336 baseline tests            7575423640a79a574f5f0122dca22e83d6ccdd18abb9c3d93df7a730189acbeb
```

This is implementation evidence only. No M336 optimizer effect, D1, D2, D3,
E4, repair, fallback, legalization, CP-SAT, or parameter ladder ran while
producing it. The one Phase A D1 remains the next authorized effect after this
implementation commit is pushed and pulled.

## Phase A Effect Evidence

The single authorized D1 ran at signed, pushed, and pulled commit `42b2470` on
physical GPU 2. It used one fresh checkpoint-warm output, seed `1000`, ten
iterations, learning-rate scale `1`, E2/E3 only, and policy
`consensus_per_step`. D2, E4, repair, fallback, legalization, CP-SAT, resume,
and parameter ladders did not run.

```text
results/m336/native-cypress/
  m336-193-option1-consensus-phase-a-d1-warm-10-scale1/
summary SHA-256
2607171fe66ed6bc4c2013be998931357dbcbe2b60b2bdbac10f2fa51d2e3af2
E2 exact-guard SHA-256
5c93d823e9a1db3311f5fa3f06c70f37ed28965875221a59ad3604d9b95b1ebe
E3 exact-guard SHA-256
e11372ce6e0b8996d9d3c1825cd1fdb6656e09ab329ad5c9316c243cf116d7f2
```

Both arms execute `NonLinearPlace`, `PlaceObj`, 13 backward calls, and ten
changing CUDA Adam steps. All 20 first proposals are accepted. Every accepted-
step checkpoint and both float64 post-serialization reports have `100/100`
containment, zero Keep-in violations, and zero overlap. Serialization replay
has zero coordinate error and identical input/replay hashes.

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Accepted / rejected attempts | `10 / 0` | `10 / 0` |
| Authority states / topology records | `0 / 0` | `0 / 0` |
| Native HPWL | `15633.109789610` | `15633.019091368` |
| FLUTE RSMT | `17328.300` | `17328.207` |
| Placement SHA-256 | `dbaffb7e4c6bda1e70079ddb2d89d8c3a4f6fdda8214371932d5590a310e5914` | `9156add8cb98964d9930c95871fedfe8704ad72f794bbad8d84ae3da9d9326c8` |
| GPU optimization | `1.679384 s` | `1.733401 s` |
| Ratio to fixed feature-off control | `1.553746x` | `1.286047x` |
| End-to-end | `14.015480 s` | `14.193262 s` |
| Ratio to fixed feature-off control | `1.192412x` | `1.196838x` |

The fixed controls remain `1.080861809/1.347852359 s` GPU and
`11.753892059/11.858962068 s` end-to-end. No timing boundary or denominator was
changed. HPWL regression is `0.000810%/0.002126%`; RSMT regression is
`0.007053%/0.014608%`, all below `0.5%`.

E3 improves anchor mean by `0.000119614 mm` (`0.001833%`) and p90 by
`0.000057227 mm` (`0.000475%`) versus E2, so the required direction is
non-negative. The placements, scores, and hashes exactly reproduce M336-174,
confirming that the policy reuses the historical mechanism rather than a new
heuristic.

Phase A therefore passes every predeclared gate and authorizes exactly one
checkpoint-warm 50-step scale-1 E2/E3 D3 after this evidence is committed,
pushed, and pulled. The normalized native scores remain only
`0.928017476/0.928022657`, below the manual score-1 baseline; Phase A is a
safety/runtime promotion, not final placement-quality acceptance. Paired
repeated timing remains required after the diagnostic candidate and must retain
the same `2x` threshold. Stage micro remains unimplemented and unauthorized
unless D3 isolates a local discrete topology/RSMT defect.

## D3 Effect Evidence

The single authorized D3 ran at pushed and pulled commit `5d58a5e` on physical
GPU 2. It used a fresh checkpoint-warm output, seed `1000`, 50 iterations,
learning-rate scale `1`, E2/E3 only, and `consensus_per_step`. D2, E4, repair,
fallback, legalization, CP-SAT, resume, and parameter ladders did not run.

```text
results/m336/native-cypress/
  m336-193-option1-consensus-d3-warm-50-scale1/
summary SHA-256
31cefc895e32a74612f68c0abecea7a93b7c7cbf87ce8a21f5cfea4d6acc2586
E2 exact-guard SHA-256
58d19e607a60e95f855ebeabc491ec0807331b9a388f99718283387d479afd7b
E3 exact-guard SHA-256
adf5c84b9f81c983340e434ae6d0aa4f61200d9b8b23d8741d3e16eb943bc2c8
```

Both arms prove `NonLinearPlace`, `PlaceObj`, 53 backward calls, and 50
changing CUDA Adam steps. E2 accepts 50 attempts and rejects eight; E3 accepts
50 and rejects six. Complete rollback and `0.5` LR backoff recover every
rejected proposal. All 100 accepted steps and both accepted origins have zero
positive-area overlap and zero Keep-in violations. Both serialized placements
are `100/100` contained with zero overlap, zero coordinate replay error, and no
repair.
Authority enumeration and topology tie-break records remain zero.

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Native HPWL | `15634.399744749` | `15633.964617491` |
| FLUTE RSMT | `17326.965` | `17327.178` |
| Normalized score | `0.928015545` | `0.928022603` |
| Placement SHA-256 | `d6242e54cc034f4cecb6bc315140398c81bc899b64bf6349ebd093291fe9e4eb` | `9f601023292b957242c31bdcc941eaa94472d98e27862eca06d4ba496c2ce61d` |
| GPU optimization | `6.159659 s` | `6.602546 s` |
| End-to-end | `18.492517 s` | `19.415604 s` |
| Final effective LR | `0.000090178` | `0.000360712` |
| Anchor mean / p90 | `6.522158 / 12.044242 mm` | `6.521884 / 12.044463 mm` |

E3 improves HPWL by `0.435127` and normalized score by about `0.00000706`
versus E2, while FLUTE RSMT regresses by `0.213`. Anchor mean improves only
`0.00420%`, and p90 regresses by `0.00184%`. This passes the authorized D3
legality/no-broad-repair condition, but does not satisfy the final anchor or
manual score-1 quality gates.

## D3 Locality Finding

The 14 rejected first proposals are all `contact_node_limit` outcomes. E2
rejected states require 33-35 corrected nodes across 22-23 contact components;
E3 requires 33 nodes across 19-21 components. Maximum active contact scope is
`56/52`, and the LR consequently falls to `1/256` and `1/64` of its initial
value. Across the stage, contact-touched unions contain `68/63` components;
even the final ten attempts touch `57/50`.

Independent per-net attribution finds 65 changed nets. The E3 RSMT increase is
dominated by `GND`: HPWL changes by `+0.032166` and RSMT by `+0.769`. This net
has 114 pins on 84 unique components; 67 of those components move between E2
and E3, and 44/41 appear in the respective stage contact unions. The evidence
therefore does not isolate an HPWL-neutral, contact-local topology defect. It
shows broad trust-region pressure plus a global high-degree-net response.

`consensus_plus_stage_micro` is not authorized or implemented. Selecting it
continues to fail closed. A 32-node stage-end solve would either omit measured
support or silently broaden the declared contract, and neither is allowed.
`consensus_per_step` remains the production candidate; `strict_reference`
remains preserved and default off.

The next evidence is paired repeated timing on the same GPU under a
predeclared identical run contract. It must retain the existing timing
boundaries and `2x` threshold. No D2, E4, stage micro, collision/anchor/LR
tuning, legalization, repair, fallback, or CP-SAT run is authorized by this
finding.
