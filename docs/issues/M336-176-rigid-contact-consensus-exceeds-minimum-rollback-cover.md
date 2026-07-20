# M336-176: Rigid Consensus Exceeds Minimum Rollback Cover

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commits:** `0d2cae5` through `c77a978`

## Problem

M336-174 correctly changed the contact budget from all crossing endpoints to
the cumulative active coordinates actually written by contact projection. Its
all-active correction is still stronger than exact legality requires: every
connected contact component is forced onto one rigid proposal displacement.
For a component with `k` active members, this always preserves one proposal and
rewrites the other `k-1`, even when rolling back a smaller vertex cover of the
actual crossing graph would break every current overlap edge.

This excess control matters at the current boundary. The only M336-174 D2
rejection starts with 28 crossing pairs and 28 consensus-selected coordinates.
Closure later selects a cumulative 32 coordinates, then a residual
`FV705/R709` crossing requires `FV705` as coordinate 33. The exact guard
correctly rejects and restores the complete Adam transition, but the proposal
cannot answer whether a smaller bounded rollback could retain more native
optimizer motion.

The accepted position at the start of the optimizer step is exact legal. It can
therefore be used as a per-step trust-region authority: restore a deterministic
active vertex cover to that accepted position, validate the resulting geometry,
and repeat on any residual or newly created exact crossing. This is proposal
rollback inside native Cypress, not placement by an exact-site optimizer and
not a checkpoint fallback.

## Evidence

The source artifacts are the pushed M336-174 D1 and D2 guards:

```text
D1 summary SHA-256
2d61a48d8284f126e43832dd09ed58dceaf2c55726255203ff74ef8bcac646e4
D1 E2/E3 guard SHA-256
6cbacf6aa0184a2da853b9584e396f88b4c4d7eee7d36c8e61fc5e94f5144725
648362f8c21a2006a1944732e5f24121264b3bc5c08d3fa3df7a88f51abbe037

D2 summary SHA-256
8126ab17063f3c183a85566cfe4fa07409ea541e6e9591d0c00653fe16eef8d7
D2 E2/E3 guard SHA-256
92345bcefbe1ae608b0703570596e6c3db8b0a46c1b9abfb84733de3fd8de999
647ccc7efbd9c8ec0f36fa9bdd1525efb6f3a9b036e718e27813be72b473e67e
```

An offline, read-only audit recomputed an exact minimum active vertex cover for
the initial overlap graph of every recorded proposal. Active endpoints joined
to inactive endpoints were mandatory; inactive endpoints were never selectable.

| Run / arm | Proposals | Consensus selections | Cover lower bound | Reduction | Positive reductions |
| --- | ---: | ---: | ---: | ---: | ---: |
| D1 E2 | `10` | `164` | `141` | `23` (`14.0%`) | `10/10` |
| D1 E3 | `10` | `169` | `142` | `27` (`16.0%`) | `10/10` |
| D2 E2 | `11` | `234` | `195` | `39` (`16.7%`) | `11/11` |
| D2 E3 | `11` | `237` | `197` | `40` (`16.9%`) | `11/11` |

The rejected D2 proposal is `28 -> 23` at its first exact report. Five
corrections are avoided by choosing one endpoint cover for the components
`C501/C502/R704`, `C601/FV602/FV604/FV607`,
`C8603/C8606/C8613`, `FV702/L401/R703`, and
`FV703/FV704/R707/RT601` rather than rigidly rewriting every non-representative.

These counts are intervention lower bounds only. Restoring one endpoint of an
overlap edge to its accepted coordinate does not necessarily make that edge
legal while the other endpoint remains at its proposal. It can also expose a
new crossing. No count above is a replay, feasibility proof, quality result, or
authorization to bypass exact closure.

## Root Cause

The current projector solves a stronger geometric problem than the guard asks:

1. exact validation returns a graph of crossing footprint pairs;
2. connected components are formed over the append-only protected edge set;
3. one displacement authority is chosen for every component; and
4. every other active member is rewritten to preserve all origin-relative
   geometry in that component.

Rigid component motion is sufficient for legality, but is not necessary. A
vertex cover selects at least one active endpoint of each current crossing. A
rollback cover therefore provides the smallest possible first intervention
under a fixed graph, while the existing exact validator remains responsible
for proving whether that intervention actually closes the geometry.

## Required Correction Contract

Add a default-off `minimum_cover_rollback` mode without changing the existing
`component_consensus` mode or the numeric 32-coordinate budget.

For each optimizer proposal:

1. Freeze the exact-legal accepted position as `origin`, then run the ordinary
   board and footprint-aware keep-in projection on the native CUDA proposal.
2. Exact-validate that proposal. Preserve every observed edge in append-only
   diagnostics, but solve only the current crossing graph on each closure pass.
3. An active endpoint whose current coordinates differ from `origin` is
   selectable. An inactive endpoint and an already-restored no-op endpoint are
   not selectable for a current edge. If only one endpoint is selectable, it is
   mandatory. If neither endpoint is selectable, fail closed.
4. Compute an exact minimum selectable vertex cover independently for each
   connected component. The deterministic objective is:

   ```text
   minimum newly selected cumulative IDs
   -> minimum squared proposal motion removed
   -> lexicographically smallest selected node-ID tuple
   ```

5. Bound exact enumeration explicitly. A current component larger than the
   configured search bound must fail closed with a distinct reason; it must not
   silently use a greedy cover. The first candidate bound is 16 component
   nodes, versus a measured maximum of five in the failed D2 proposal.
6. Check the union of newly selected IDs and every ID selected by earlier
   closure passes against 32 before mutation. The cumulative union cannot
   shrink when edges disappear or components merge.
7. Restore selected active coordinates to this step's `origin`, never to
   M336-118 or another checkpoint. Apply the standard hard projector, run the
   exact validator again, and repeat for residual/new crossings.
8. A residual edge may force the previously unselected endpoint on a later
   pass. Exact legality, not first-pass cover size, determines convergence.
9. On a node limit, component bound, immutable/no-op overlap, iteration limit,
   or exact illegality, leave final acceptance to the transactional step guard.
   It must restore position, optimizer state, and LR semantics exactly as now.

The result schema must record the mode, current and protected edge counts,
search component/state bounds, mandatory/selectable IDs, per-pass minimum-cover
size, newly selected IDs, cumulative selected IDs, rollback-only and subsequent
hard-projection distances, validator calls, and exact fail reason. Active
endpoint pressure remains separate from bounded correction scope.

## Rejected Alternatives

- Raising `max_contact_nodes` would hide the measured safety boundary.
- A greedy cover would make boundedness and deterministic optimality ambiguous.
- Treating the first cover as legal without replay would confuse a graph lower
  bound with exact footprint geometry.
- Restoring the whole M336-118 placement would be a prohibited fallback output.
- CP-SAT, one-opt, pair scan, E4 repair, and seed/LR/weight ladders do not test
  this native proposal-control hypothesis.

## Required Tests

1. A three-node active path selects its one-node center cover instead of the
   two writes required by rigid consensus when that rollback is exact legal.
2. Disconnected paths and stars produce exact minimum covers with deterministic
   node-ID tie breaks on CPU and GPU, for binary32 and binary64 positions.
3. Active-to-inactive crossings make the active endpoint mandatory and never
   move or charge the inactive endpoint.
4. A current edge cannot be covered by an endpoint already byte-identical to
   `origin`; the effective opposite endpoint is selected instead.
5. If a first cover leaves a residual crossing, closure selects the additional
   endpoint, retains the first ID in the cumulative union, and reaches legality
   only after a fresh exact validation.
6. A newly exposed crossing and a component merge cannot reset the cumulative
   budget or forget a protected edge.
7. Node-cap and component-search-bound failures occur before the failing pass
   mutates coordinates and report distinct stable reason codes.
8. Rollback and hard-projection statistics are separate and reconcile with the
   composite projector's changed-node accounting.
9. Adam and Nesterov guard rejection restores position and optimizer hashes;
   accepted corrected coordinates have their optimizer state cleared.
10. Legal/no-op candidates, the default `component_consensus` mode, and the
    generic feature-off path remain byte-identical to current behavior.

## Experiment Gates

No M336 effect run is authorized until this issue and the implementation are
separately committed with sign-off, pushed, pulled, installed, and covered by
focused source/installed tests. The first and only initial effect run is the
existing checkpoint-warm seed-1000, ten-step, scale-1 E2/E3 D1 contract with
`minimum_cover_rollback` explicitly enabled. It must use physical GPU 2,
deterministic CuBLAS, and explicit run-local output, summary, and report paths.

D1 passes only if:

- every accepted step and post-serialization replay is 100/100 contained with
  zero keep-in violations and zero overlaps;
- every arm proves `NonLinearPlace`, `PlaceObj`, backward, and ten changing CUDA
  Adam steps;
- no attempt exceeds 32 cumulative rollback IDs or the component-search bound;
- at least one real proposal selects fewer coordinates than matching rigid
  consensus, with both scopes serialized;
- maximum correction is no worse than the M336-174 D1 value
  `0.00326420 mm`;
- native HPWL and RSMT do not regress from matching M336-174 D1 values;
- GPU optimization and end-to-end runtime remain within `2x` of retained
  M336-171 feature-off controls; and
- E3 anchor mean and p90 are both strictly lower than same-run E2.

Stop and document any failed conjunct. One scale-2 D2 replay may be proposed
only after a passing D1 result is committed, pushed, and pulled with new
predeclared D2 hashes and thresholds. D3, E4, cap increases, fallback, CP-SAT,
and all parameter ladders remain prohibited.

## Acceptance Criteria

- The mode is bounded, deterministic, default off, and source/install identical.
- Graph-cover diagnostics never claim exact feasibility without validator proof.
- The cumulative 32-coordinate invariant and transactional rollback remain the
  final proposal safety boundary.
- D1 passes every predeclared correctness, quality, anchor, and runtime gate.
- Any later D2 is separately authorized and passes before N6 can advance.
- The final promoted placement still comes only from the native Cypress chain.

## Implementation Candidate

The new implementation keeps `component_consensus` as the default and adds an
explicit `minimum_cover_rollback` mode. Each closure pass constructs connected
components from the current exact overlap graph, marks only active coordinates
that differ byte-for-byte from the accepted step origin as selectable, and
enumerates every subset of at most 16 component nodes. Its stable objective is
new cumulative ID count, removed squared proposal motion, then node-ID tuple.

Selected coordinates are restored only to the same optimizer step's accepted
origin. The ordinary hard projector and full exact validator run after every
write. Residual and newly exposed edges create another pass, while the selected
ID union remains cumulative and is checked against 32 before mutation. Distinct
`cover_component_limit`, `unresolvable_overlap`, `contact_node_limit`, and
existing closure reasons fail closed through the transactional guard. No
checkpoint, CP-SAT, E4, or serialized fallback path is reachable from this
mode.

The runner now carries mode and component bound through generated configs,
resume-contract checks, reproduction commands, run IDs, per-run results, and
top-level summaries. It also hashes `install/dreamplace/params.json`, closing a
source/install identity omission for the new options. The implementation emits
current/protected graph scopes, exact enumeration states, selectable/mandatory
and selected IDs, rigid-consensus comparison scope, cumulative budget, and
separate rollback/hard-projection distances.

Installed-tree validation on physical GPU 2 passes:

```text
exact contact projection          25/25
transactional exact step guard      6/6
M336 baseline and runner config    105/105
reproducibility and state reset     18/18
anchor/keep-in/collision            52/52
irregular density                    9/9
focused total                      215/215
Python compile / JSON / CLI help      pass
source/install implementation drift      0
```

The aggregate runner discovers 244 tests and repeats the same ten independent
legacy compatibility/API errors tracked by TEST-001 while still returning
shell status zero. No new error category appears. This result is not called a
pass and does not weaken the 215 focused checks.

This section is implementation evidence only. No M336 placement, native score,
E4 repair, exact-site optimization, fallback, or parameter ladder has run for
the candidate. Commit, push, pull, and then execute only the predeclared D1.
