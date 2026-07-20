# M336-174: Contact Consensus Overwrites Every Active Proposal

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commits:** `bf67663` through `9b4f164`

## Problem

The exact contact projector declares that its node budget limits active
coordinates that may be corrected, but an all-active contact component spends
one budget unit for every endpoint and rewrites every native proposal. When a
component has no inactive authority, `_component_displacement()` averages all
member proposal displacements and `_apply_consensus()` copies that mean back to
every active member.

This is exact-safe but broader than required. A component with `k` active
members can preserve one native proposal displacement and correct only the
other `k-1` members to the same rigid motion. The current implementation instead
corrects all `k` members and rejects before projection whenever the union of
contact endpoints exceeds 32. It therefore conflates two distinct quantities:

- active endpoints participating in candidate crossings, which measures native
  contact pressure; and
- active coordinates selected for consensus correction, which is the declared
  bounded intervention.

The distinction is not permission to increase the numerical limit, partition
an unbounded repair, or hide broad crossing support. Both scopes must remain
visible and the correction scope must be cumulative across closure iterations.

## Evidence

The source artifact is the pushed M336-172 post-fix D2 run:

```text
results/m336/native-cypress/
  m336-172-active-budget-d2-warm-10-scale2/
summary SHA-256
048e13819208f650b0965ee2b77d3765cda9af2a6620cc2606344f320c255fd7
E2 exact-guard SHA-256
901f1577eacbac4288ca9b57c01569ff9dfc18963dd6b60de6058210cf00c746
E3 exact-guard SHA-256
4c2cdfb0761ee2271f1f5a101c0739f685aee2f6ef35a254a2846d6f6c089d0b
```

Across its candidate attempts, current consensus changes every active endpoint
when it runs. A static final-component estimate was computed by charging all
active members for components with an inactive authority and `k-1` members for
an all-active component:

| Arm | Maximum active endpoints | Maximum components | Largest active component | Maximum current consensus changes | Maximum representative-plan estimate |
| --- | ---: | ---: | ---: | ---: | ---: |
| E2 | `34` | `15` | `4` | `32` | `22` |
| E3 | `33` | `16` | `4` | `32` | `21` |

For the first accepted attempt in both arms, seven disconnected components
contain 17 active endpoints. Current consensus rewrites all 17; preserving one
native motion per all-active component would select only 10 corrections.

The estimate is not a replay result and does not prove convergence. In
particular, later exact validation can add edges, merge components, change the
representative, or invoke hard keep-in projection. The implementation must
therefore enforce a cumulative union of selected correction IDs, rather than
recomputing a smaller final count after each iteration.

## Root Cause

The projector uses one structure for three responsibilities:

1. `protected_edges` accumulates every exact overlap edge found during closure;
2. the active endpoint union is checked against `max_contact_nodes` before a
   correction is planned; and
3. every active endpoint in each connected component receives a shared mean
   displacement.

The pre-check was conservative when every active endpoint was rewritten, but it
also made the implementation's stated "coordinates corrected" contract
equivalent to endpoint count. Averaging all active proposals removes every
component's native optimizer motion even though one member motion is sufficient
to restore the component's origin-relative geometry.

Inactive endpoints are a separate case. They are not optimizer-controlled and
their displacement remains authoritative. Every active member joined to such a
component may need correction, so no active representative exemption applies.

## Required Correction Contract

Keep the feature default off and retain the unchanged numeric limit of 32. The
new invariant is:

```text
contact budget = cumulative union of active node IDs selected for
                 contact-consensus writes during one optimizer proposal
```

For each protected connected component:

1. If it contains inactive endpoints, use their existing authoritative mean
   displacement and select every active member for correction.
2. If it is all-active, select one deterministic native representative. Choose
   the member proposal displacement minimizing the sum of squared displacement
   differences to the other active proposals; break exact ties by node ID.
3. Leave that representative at its post-hard-projection native proposal and
   select the remaining active members to share its displacement.
4. Form the union with every active node selected by earlier closure iterations.
   Check the union against 32 before mutating coordinates.
5. Fail closed with `contact_node_limit` when the required cumulative union is
   larger than 32. Do not raise the cap, reset the union after component merges,
   or process disconnected components outside the global budget.
6. Run the hard footprint-aware keep-in projector and exact validator exactly as
   before. The transactional accepted-step guard remains final authority and
   restores the complete optimizer transition on failure.

The result schema must report at least:

- total and active contact endpoint counts;
- cumulative selected/corrected active IDs and count;
- required cumulative count when a limit is hit;
- authority kind and representative for each component;
- consensus-only and subsequent hard-projection correction statistics;
- maximum total, active, and corrected component sizes;
- `contact_node_limit_basis = cumulative_corrected_active_nodes`.

Endpoint pressure must never be relabeled as correction pressure. Existing
proposal, accepted-path, hard-projection, exact-overlap, rollback, and optimizer
state hashes remain mandatory.

## Required Tests

1. An all-active component selects the minimum-squared-distance native
   representative and leaves its proposal bytes unchanged.
2. Equal-cost representatives use the smallest node ID on CPU and GPU.
3. A three-node all-active chain succeeds at a correction cap of two, while a
   four-node chain fails closed at the same cap without partial mutation.
4. Multiple disconnected all-active pairs may have more active endpoints than
   the cap only when their cumulative selected correction union remains within
   the cap.
5. Components with inactive authorities charge every active member and never
   move the inactive endpoints.
6. An iterative closure that merges components cannot forget IDs corrected in
   an earlier iteration or evade the global cap by choosing a new representative.
7. Consensus and hard keep-in projection metrics are separated and their union
   agrees with the existing overall projection statistics.
8. Legal/no-op candidates remain byte-identical; exact guard rollback remains
   byte-consistent for Adam and Nesterov; feature-off behavior is unchanged.
9. CPU/GPU projection coordinates, representatives, scope IDs, and reason codes
   are identical for the same binary64 input.

## Experiment Gates

No effect run is authorized until the issue and implementation are separately
committed, pushed, pulled, installed, and covered by the focused and regression
suites. Because consensus semantics change, rerun the warm seed-1000 scale-1 D1
E2/E3 contract before D2.

One further scale-2 D2 replay is allowed only if D1 remains exact legal and
within its existing `0.5%` quality and `2x` optimization-runtime gates. D2 must
stop unless all of these predeclared criteria pass:

- every accepted step has zero exact overlap and keep-in violations;
- no attempt exceeds the cumulative 32-correction scope;
- active endpoint pressure remains separately reported;
- final accepted LR is at least half the initial scale-2 LR;
- maximum contact correction is no more than `2x` the matching D1 value;
- constrained net displacement is at least `10%` above the matching M336-171 D1
  values (`0.0101054133 mm` for E2 and `0.0083100503 mm` for E3);
- E3 anchor mean and p90 are both strictly lower than same-run E2;
- native HPWL and RSMT do not regress from the matching D1 arm;
- no E4 repair, CP-SAT placement, exact-site fallback, seed ladder, LR ladder,
  or scalar-weight ladder is used.

D3 remains prohibited until this D2 contract passes. A lower correction count
alone is implementation evidence, not a Cypress quality promotion.

## Acceptance Criteria

- The cumulative correction invariant and every required diagnostic are covered
  by focused tests and installed-source parity checks.
- The unchanged cap measures actual bounded consensus control while preserving
  endpoint pressure as an independent failure signal.
- Exact legality remains the post-serialization source of truth.
- D1 passes after the semantic change.
- The single authorized D2 replay passes every declared gate above.
- M336-172 and M336-173 remain open until their active-scope and anchor-direction
  effect failures are independently resolved.

## Implementation Candidate

The default-off projector now implements the cumulative correction contract
without changing `max_contact_nodes = 32`:

- proposal displacements are frozen after the ordinary hard projector and
  before contact closure;
- an all-active component chooses the proposal medoid by minimum summed squared
  displacement difference, with node ID as the exact tie-break;
- the representative remains at its native proposal while the other active
  members receive its rigid displacement;
- inactive-authority components continue to select every active endpoint;
- the union of selected active IDs across every closure iteration is checked
  before coordinate mutation and never shrinks after component merges;
- a representative previously changed by an earlier closure is charged if it
  must be restored to its native proposal;
- consensus-only, subsequent hard-projection, and combined correction metrics
  are serialized independently;
- endpoint, active-endpoint, corrected, and required-correction scopes remain
  separate in every iteration and final result.

`NonLinearPlace` records the new
`cumulative_corrected_active_nodes` basis only when exact contact projection is
enabled. The generic flag remains disabled, the runner's numeric defaults and
D2 collision/guard settings are unchanged, and the transactional exact guard
still owns final acceptance and optimizer rollback.

Focused source and installed-tree validation on physical GPU 2 passes:

```text
exact contact projector       14/14
exact accepted-step guard      6/6
M336 baseline/config         105/105
reproducibility               17/17
anchor/keep-in/collision      52/52
irregular density              9/9
Python compile / JSON / diff   pass
source/install projector       byte-identical
source/install NonLinearPlace  byte-identical
source/install params          byte-identical
```

The projector suite covers float32 and float64 CPU/GPU coordinate identity,
deterministic representatives, inactive authorities, disconnected components,
pre-mutation limits, iterative cumulative limits, hard-projection accounting,
and JSON serialization. Two initial regression commands used nonexistent test
filenames, and one source-first `PYTHONPATH` hid the installed native extension;
the canonical source test paths with `install:$PWD` were then run and passed.

The repository aggregate runner executed 232 tests and printed ten unrelated
legacy compatibility/API errors while returning shell status zero. `TEST-001`
records that independent infrastructure defect; the aggregate run is not
reported as passing and is not used to weaken the focused evidence above.

This remains implementation evidence only. D1 must be rerun after this semantic
change, committed, pushed, and pulled before the single predeclared D2 effect
test. No M336 GPU placement experiment, E4 repair, CP-SAT path, fallback, or
parameter ladder has run for this candidate.

## Post-Implementation D1 Replay

Commit `0d2cae5d2994e3a982214deed0a84e4f1aec317c` was signed,
pushed, pulled, installed, and then evaluated on physical GPU 2. The run keeps
the M336-171 scale-1 contract unchanged: checkpoint-warm E2/E3, seed `1000`,
ten iterations, deterministic CuBLAS, irregular density, collision ratio
`0.1`, zero collision margin, exact accepted-step guard, and the unchanged
eight-iteration/32-correction contact bound. E4, CP-SAT placement, repair,
fallback, and parameter ladders were disabled.

```text
results/m336/native-cypress/
  m336-174-representative-d1-warm-10-scale1/
summary SHA-256
2d61a48d8284f126e43832dd09ed58dceaf2c55726255203ff74ef8bcac646e4
E2 exact-guard SHA-256
6cbacf6aa0184a2da853b9584e396f88b4c4d7eee7d36c8e61fc5e94f5144725
E3 exact-guard SHA-256
648362f8c21a2006a1944732e5f24121264b3bc5c08d3fa3df7a88f51abbe037
```

Both arms execute `NonLinearPlace`, `PlaceObj`, 13 backward calls, and ten
changing CUDA Adam steps. Every proposal is accepted at retry zero; every
accepted-step exact report and both post-serialization reports have 100/100
containment, zero keep-in violations, and zero overlaps. Float64 scoring
replays each serialized placement with zero coordinate error and an identical
input/replay placement hash.

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Accepted / rejected attempts | `10 / 0` | `10 / 0` |
| Initial / final LR | `0.0230855606 / 0.0230855606` | `0.0230855606 / 0.0230855606` |
| Maximum active contact endpoints | `37` | `44` |
| Maximum cumulative corrected scope | `24` | `26` |
| Maximum component active/corrected scope | `4 / 4` | `4 / 4` |
| Maximum contact correction (`mm`) | `0.00326420` | `0.00326420` |
| Native HPWL | `15633.109790` | `15633.019091` |
| FLUTE RSMT | `17328.300` | `17328.207` |
| Normalized native score | `0.9280174763` | `0.9280226571` |
| Anchor mean / p90 (`mm`) | `6.524105003 / 12.047651992` | `6.523985389 / 12.047594765` |
| Constrained path / net displacement (`mm`) | `0.011246011 / 0.010669671` | `0.011314802 / 0.010724053` |
| GPU optimization / end-to-end (`s`) | `1.82268 / 13.4417` | `2.14319 / 13.4405` |

The new distinction is active in real proposals rather than only unit tests.
Endpoint pressure exceeds 32 in both arms, but the actual cumulative correction
union remains below the unchanged cap. No proposal uses broad correction or
backoff. Relative to the retained M336-171 feature-off controls:

| Gate | E2 | E3 | Limit |
| --- | ---: | ---: | ---: |
| HPWL regression | `0.000810%` | `0.002126%` | `<= 0.5%` |
| RSMT regression | `0.007053%` | `0.014608%` | `<= 0.5%` |
| GPU optimization ratio | `1.686x` | `1.590x` | `<= 2x` |
| End-to-end ratio | `1.144x` | `1.133x` | `<= 2x` |

E3 is also strictly better than E2 by `0.001833%` in anchor mean and
`0.000475%` in p90; HPWL/RSMT improve by `0.090698/0.093`, respectively.
These changes are small and are not a final anchor-quality promotion, but the
predeclared D1 safety gate passes.

The original command omitted explicit summary/report paths. As documented in
M336-175, the runner wrote those two files to mutable global defaults; after
verifying their commit, run IDs, timestamps, and artifact roots, they were
copied byte-for-byte into this run directory. This archival correction did not
rerun either arm or alter any metric. Future commands must set both paths.

One scale-2 D2 replay is now authorized after this evidence commit is pushed
and pulled. Its matching D1 correction limit is `0.00326420 mm`, so the
predeclared `2x` ceiling is `0.00652841 mm`. D3 remains prohibited unless D2
passes every M336-174 gate.
