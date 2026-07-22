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
