# M336-177: Origin Rollback Recaptures Contact Scope

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `8446b28`

## Problem

M336-176 minimizes a graph vertex cover, then restores those coordinates to the
accepted step origin. Covering an overlap edge does not make that rollback
geometrically legal against the peer's retained native proposal. Exact closure
therefore selects the opposite endpoint on a later pass and often restores the
entire contact component.

The implementation is bounded and exact-safe, but its optimization target is
the first write set rather than the final exact correction. It discards more
native optimizer motion than the older rigid proposal-consensus mode and fails
the D1 RSMT and anchor-direction gates.

## Evidence

The pushed M336-176 D1 artifact is:

```text
results/m336/native-cypress/
  m336-176-minimum-cover-d1-warm-10-scale1/
summary SHA-256
cb39619e21a8bd361c380b966a41e3f883a641c0e1a98003c4b36a8ecffeb5dd
E2/E3 exact-guard SHA-256
bca4d7f84d74a07599c0b932c590693b960b2b11d2f8710d99236b08291edf31
e98f09bd4bb66afadba9041dab34df0cd485b320ab6837d7674ff531687b9032
```

For accepted proposals, the first graph cover is smaller than matching rigid
consensus, but exact closure more than consumes the saving:

| Arm | Accepted proposals | First cover | First rigid scope | Final rollback scope | Correction passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| E2 | `10` | `114` | `134` | `233` | `21` |
| E3 | `10` | `117` | `137` | `244` | `22` |

Every accepted E2/E3 proposal ends with a larger cumulative rollback scope than
its own first-pass rigid comparison. Relative to the separate M336-174 rigid
D1 trajectories, final writes rise from `181 -> 233` in E2 (`+28.7%`) and
`184 -> 244` in E3 (`+32.6%`). Those aggregate trajectories diverge after the
first step, so they are supporting evidence rather than a paired replay.

The first proposal is paired and decisive. Both modes start from the same
M336-118 position and native Adam proposal containing ten overlaps in seven
components. Rigid consensus copies an existing proposal displacement to ten
nodes and is exact legal in one pass. Minimum cover first restores these eight
nodes to origin:

```text
C605 C611 C8605 C8606 C8609 FV703 FV704 R704
```

The retained peer proposals still cross them. Closure then restores the other
nine nodes, so all 17 active endpoints lose their native proposal:

```text
C501 C502 C606 C612 C8613 C8621 L8602 R707 RT601
```

E3 later requires 38 cumulative origin rollbacks at full LR and 33 at half LR;
both attempts fail closed at the unchanged cap of 32. The quarter-LR retry is
legal, but E3 anchor mean/p90 are `0.001386%/0.002038%` worse than E2 and RSMT
regresses from M336-174 D1 by `0.821`.

## Root Cause

The graph-cover model treats a selected endpoint as if restoring it to origin
removed an overlap edge. That implication is false. If the unselected endpoint
moves into the selected endpoint's accepted footprint, one origin rollback
still overlaps. The next pass makes the peer mandatory, and the append-only
budget correctly charges both writes.

Rigid consensus succeeds because it retains one displacement produced by the
native optimizer and assigns that same displacement to the other members. This
preserves their accepted relative geometry. Its weakness is forcing an entire
connected component to one authority even when several compatible proposal
authorities could satisfy all exact pair constraints.

## Required Correction Contract

Add a default-off `proposal_authority_search` mode. It is a bounded hard
projection of a native optimizer proposal, not an objective, placement search,
repair pass, or checkpoint fallback.

1. Freeze the exact-legal accepted position and the post-keep-in native proposal
   displacement of every physical node.
2. Build current exact-overlap components. Inactive coordinates are immutable;
   active nodes may retain their own proposal displacement or adopt a proposal
   displacement already produced for another member of that component.
3. Enumerate authority assignments only inside each current component. Deduplicate
   byte-identical authorities and use stable node IDs as labels.
4. Evaluate an assignment on scratch coordinates. Apply the normal hard keep-in
   projector, then use exact pair geometry to require every current component
   edge to be non-overlapping. A full exact validator remains mandatory after
   the selected component plans are applied.
5. Choose deterministically by:

   ```text
   minimum newly corrected cumulative node IDs
   -> minimum squared correction from the native proposal
   -> lexicographically smallest (node ID, authority ID) assignment
   ```

6. Count every coordinate that differs from its native proposal in the
   append-only per-attempt union. Check the unchanged global cap of 32 before
   mutating the real candidate.
7. Bound both component size and enumerated authority states explicitly. Fail
   closed with distinct stable reasons before mutation; never use an unbounded
   search, greedy hidden fallback, cap increase, or origin/checkpoint restore.
8. Reapply hard constraints and exact validation after every committed pass.
   Residual or newly exposed edges form another bounded closure pass without
   forgetting earlier corrected IDs.
9. Preserve `component_consensus` and `minimum_cover_rollback` byte-for-byte for
   historical replay. The generic feature remains default off.

Diagnostics must include current/protected edges, available authorities,
enumerated and exact-tested state counts, selected authority per active node,
new/cumulative corrected IDs, correction energy, hard-projection changes,
counterfactual rigid scope, validator time, and exact failure reason.

## Rejected Alternatives

- Choosing a different origin vertex cover still lacks a geometric guarantee.
- Raising the 32-node cap hides broad intervention rather than preserving native
  motion.
- Returning to rigid consensus alone reproduces the scale-2 limitation and does
  not answer whether multiple proposal authorities are compatible.
- Scalar collision-weight, LR, seed, and E4 ladders are already closed by
  M336-169 through M336-176.
- CP-SAT, one-opt, pair scan, and M336-118 fallback are not Cypress evidence.

## Required Tests

1. A two-body contact keeps one native authority and corrects only the peer;
   origin rollback of that peer remains overlapping in the same fixture.
2. A three-node component finds a mixed two-authority assignment with fewer
   writes than rigid consensus and passes exact pair validation.
3. Tangential corner entry, unequal footprints, concave footprints, and all four
   approach directions are exact legal after projection.
4. Active-to-inactive contact never moves the inactive node and uses only an
   available immutable authority.
5. Exact ties use stable node/authority IDs on CPU and GPU for float32/float64.
6. Component and state limits fail before real-position mutation with distinct
   reason codes and complete required-scope diagnostics.
7. A new edge or component merge cannot reset the cumulative union or evade the
   global cap.
8. Hard-projection and authority corrections are reported separately and their
   union matches optimizer-state cleanup IDs.
9. Adam and Nesterov guard rejection restores position and optimizer state;
   legal/no-op, old modes, and feature-off behavior remain unchanged.

## Implementation Candidate

The default-off `proposal_authority_search` mode now implements the bounded
contract without introducing an exact-site placement path. For each current
exact contact component it freezes the post-keep-in native proposal, deduplicates
proposal displacements by dtype-preserving bytes, and enumerates only those
authorities. Every scratch assignment is quantized to the runtime dtype, passed
through the same `RegionProjector` feasible domains without changing projector
state, and checked with exact footprint geometry before it can be selected.

Selection minimizes newly corrected IDs, squared final correction, and stable
node/authority IDs in that order. The existing 32-ID cumulative cap is checked
before a real write; component size remains capped at 16 and authority states at
4,096. A second runtime hard projection and full exact validator remain
mandatory. Any disagreement between scratch and runtime projection restores the
candidate byte-for-byte and returns `authority_projection_mismatch` rather than
silently expanding correction scope. Diagnostics now preserve current/protected
edges, authority assignments, exact state counts and time, scratch projection,
counterfactual rigid scope, cumulative IDs, and the final exact reason.

The runner, params schema, resume contract, reproduction command, and summaries
carry the state bound only in authority mode. `component_consensus` and
`minimum_cover_rollback` were compared against the pre-change module on paired
fixtures; coordinates and every non-timing result field are identical.

Installed-tree verification on physical GPU 2 completed as follows:

```text
exact contact projection   38/38
anchor / keep-in           54/54
exact accepted-step guard   6/6
reproducibility            19/19
irregular density           9/9
M336 baseline/config      105/105
focused total             231/231
```

Source and installed hashes match for all runtime files:

```text
NonLinearPlace.py                 0698b83e281bfc5e9908828c2645de22f68d56027c56c0e041b50428e2c3d05a
anchor_keepin.py                  040dd54d8af6eaeb16b711714b199f6796b7fc4bbfceca701f87f0928376a1aa
exact_contact_projection.py      4491a213e0c4c43021d19fd4e89cbc1ac3ef3824e39fbc83eba7d72f7a790e22
region_projection.py             822b2427504445ccef1689b76cf9a7b98e842de59b10244e204b985c629df6cb
params.json                      d7c8c3ca2ac8879b8707376acf2f73f23f9c1f31f3c10982c1e69bb96abce99e
```

The aggregate runner still reports TEST-001's same 10 unrelated API-drift
errors across 260 tests while returning status zero; it is not a passing suite.
No native C/CUDA source changed, so `clang-format` is not applicable. The
protected M336-141 aggregate remains
`4091eb8e0611a8042bbc0bf5bed6d15843909d2168a21a4a34655653607ff77d`.
This is implementation evidence only: D1 remains unauthorized until this
candidate is signed, committed, pushed, and pulled.

## Experiment Gates

No M336 effect run is authorized until this issue and implementation are
separately signed, committed, pushed, pulled, installed, and validated from the
installed tree. The first effect run is only checkpoint-warm E2/E3, seed
`1000`, ten iterations, LR scale `1`, physical GPU 2, deterministic CuBLAS,
and explicit run-local output/summary/report paths.

D1 passes only if:

- every accepted step and serialization replay is 100/100 contained with zero
  keep-in violations, overlaps, and coordinate drift;
- both arms prove `NonLinearPlace`, `PlaceObj`, backward, and ten changing CUDA
  Adam steps;
- no attempt exceeds 32 cumulative corrected IDs or either exact-search bound;
- a real proposal uses multiple native authorities and strictly fewer final
  writes than matching rigid consensus, with both scopes serialized;
- total accepted correction writes do not exceed the M336-174 D1 values
  (`181` E2 and `184` E3);
- maximum correction is at most `0.00326420 mm`;
- native HPWL/RSMT do not regress from M336-174 D1;
- GPU and end-to-end runtime remain within `2x` of M336-171 feature-off; and
- E3 anchor mean and p90 are both strictly lower than same-run E2.

Stop and document any failed conjunct. D2, D3, E4, cap changes, fallback, CP-SAT,
and all parameter ladders remain prohibited until a complete D1 pass is pushed
and pulled.

## Scale-1 D1 Replay and Stop

The implementation was signed, committed, pushed, and pulled at
`48b5cdd4f05f9d8248258dc6f3591044ee6a7cee` before the only authorized effect
run. The replay used checkpoint-warm E2/E3, seed `1000`, ten iterations, LR
scale `1`, deterministic CuBLAS, physical GPU 2 (`NVIDIA H100`, driver
`550.54.14`), and explicit run-local output, summary, and report paths. It did
not run E4, repair, fallback, CP-SAT, or a parameter ladder.

```text
results/m336/native-cypress/
  m336-177-authority-d1-warm-10-scale1/
summary SHA-256
61f5f7e1239c0a7633c926bb6227ebba7864c2df4c9f6c85c79876b7c62ce1a6
report SHA-256
deb84786cc300401505b824e7db7995d0f3c1ec16009ac79610fb397130d4ab2
E2/E3 exact-guard SHA-256
81900b8eb017d34fe799e09f6e4bd5999eb2f197bd0b0927375f3832614792e9
2ce5248da0ac36123c2dd9b6dfac5bed2a4377567e6cc869b10d9fe891c47534
```

Both arms prove `NonLinearPlace`, `PlaceObj`, 13 backward calls, and ten
changing CUDA Adam steps. All ten accepted steps per arm are exact legal. Both
serialized float64 replays are 100/100 contained with zero keep-in violations,
zero overlaps, zero coordinate drift, and matching input/replay placement
hashes.

The authority mechanism is active on real proposals and substantially reduces
intervention. Six accepted proposals per arm use fewer final writes than their
matching rigid counterfactual; the first is `8 < 10`. Eight accepted component
plans per arm use multiple native authorities. Across all accepted proposals,
authority writes are `74 < 85` for E2 and `75 < 86` for E3 versus matching
rigid counterfactuals. They are also below the separate M336-174 trajectories
of `181/184` writes.

| Gate | E2 | E3 | Result |
| --- | ---: | ---: | :---: |
| Accepted / rejected attempts | `10 / 9` | `10 / 9` | reported |
| Maximum corrected IDs, all attempts | `15 / 32` | `15 / 32` | pass |
| Maximum component nodes | `4 / 16` | `4 / 16` | pass |
| Maximum per-component authority states | `256 / 4096` | `256 / 4096` | pass |
| Accepted writes vs matching rigid | `74 / 85` | `75 / 86` | pass |
| Accepted writes vs M336-174 ceiling | `74 / 181` | `75 / 184` | pass |
| Maximum correction (`mm`) | `0.003263852` | `0.003263852` | pass |
| Native HPWL | `15633.232566` | `15633.232367` | **fail** |
| FLUTE RSMT | `17329.610` | `17329.580` | **fail** |
| Normalized native score | `0.9279784973` | `0.9279793130` | reported |
| Anchor mean / p90 (`mm`) | `6.525443185 / 12.050416826` | `6.525434624 / 12.050413384` | pass |
| GPU optimization / end-to-end (`s`) | `4.18548 / 15.91143` | `4.24706 / 16.09262` | **fail / pass** |

Against matching M336-174 D1, E2 HPWL/RSMT regress by
`+0.122776/+1.310`, and E3 regress by `+0.213276/+1.373`. Against the
M336-171 feature-off controls, GPU optimization costs are `3.872x/3.151x`,
above the `2x` limit, although end-to-end ratios remain `1.354x/1.357x`.
E3 does retain the required same-run anchor direction: mean and p90 improve
over E2 by `0.0001312%` and `0.0000286%`, respectively.

Nine proposals per arm hit the eight-pass contact-closure limit with one
residual overlap and are transactionally rejected; bounded LR retries
eventually produce all ten legal accepted steps. No attempt approaches the
32-ID, 16-node, or 4,096-state limits, so increasing those bounds is not
supported. The observed runtime failure is instead dominated by repeated
bounded authority enumeration and exact validation. The quality regressions
show that lower correction scope alone does not preserve the qualifying rigid
D1 trajectory.

The conjunction therefore fails. M336-177 remains open, N6 remains blocked,
and D2, D3, E4, cap changes, fallback, CP-SAT, and parameter ladders were not
run and remain prohibited. Any successor needs a separately reviewed contract
that addresses closure convergence and cost while retaining the demonstrated
multi-authority write reduction and exact safety.

## Successor

M336-178 identifies the deterministic closure cycle: authority planning records
but does not validate previously protected edges. Its separately gated
`protected_proposal_authority_search` contract must be implemented and
qualified before another effect run.

## Acceptance Criteria

- Search consumes only displacements produced by the current native optimizer
  proposal and remains bounded, deterministic, default off, and exact-validated.
- Proposal authority is preserved wherever exact geometry permits; no accepted
  coordinate comes from an exact-site optimizer or checkpoint fallback.
- The D1 gate passes without weakening legality, quality, runtime, or scope.
- Only then may one separately predeclared larger-motion diagnostic be proposed.
