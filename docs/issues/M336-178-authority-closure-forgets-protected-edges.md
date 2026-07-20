# M336-178: Authority Closure Forgets Protected Edges

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `48b5cdd`

## Problem

M336-177 records every observed overlap in an append-only `protected_edges`
set, but proposal-authority planning still builds components and validates
assignments from `current_edges` only. A later pass can therefore restore an
earlier corrected node to its native proposal whenever that proposal closes the
current edge, even if it reopens an already protected edge.

The full validator detects the reopened edge, so no illegal candidate is
accepted. The closure itself is not monotonic, however, and can alternate until
the iteration limit. This causes repeated backward/optimizer retries, loses the
qualifying M336-174 trajectory, and makes the GPU stage exceed its runtime gate.

## Evidence

The committed M336-177 D1 artifact is:

```text
results/m336/native-cypress/
  m336-177-authority-d1-warm-10-scale1/
summary SHA-256
61f5f7e1239c0a7633c926bb6227ebba7864c2df4c9f6c85c79876b7c62ce1a6
E2/E3 exact-guard SHA-256
81900b8eb017d34fe799e09f6e4bd5999eb2f197bd0b0927375f3832614792e9
2ce5248da0ac36123c2dd9b6dfac5bed2a4377567e6cc869b10d9fe891c47534
```

All `18/18` rejected E2/E3 attempts have the same eight-pass closure. After
the initial pass, their seven-edge tail is exactly:

```text
C8608/C8619
C8619/U8601
C8608/C8619
C8619/U8601
C8608/C8619
C8619/U8601
C8608/C8619
```

Every attempt then reaches `iteration_limit` with `C8619/U8601` as its sole
residual overlap. `C8608` (node 37) and `C8619` (node 44) are active;
`U8601` (node 138) is inactive. On the inactive contact, the only valid local
assignment gives `C8619` the `U8601` proposal authority. That exposes
`C8608/C8619`. On the next pass, planning only that current edge restores both
active nodes to their own native proposals with zero reported correction and
reopens `C8619/U8601`.

The source reflects this split directly: `protected_edges` is updated and
serialized, while authority mode calls `_contact_components(current_edges)`
and passes `current_edges` to `_proposal_authority_plans()`. No feasibility
check includes previously protected edges.

The exact guard eventually finds legal reduced-LR retries, but each arm rejects
nine attempts. Contact projection consumes about `2.72/2.69 s`, and GPU
optimization reaches `3.872x/3.151x` the matching M336-171 feature-off
controls. Native HPWL/RSMT also regress from M336-174 D1. Increasing the
iteration limit would repeat a deterministic two-cycle rather than fix it.

## Root Cause

The per-component authority solver is exact for the edge set it receives, but
the closure driver supplies a non-monotonic local constraint set. Its objective
correctly measures correction against the original native proposal; therefore
restoring `C8619` to that proposal has zero correction energy in the
`C8608/C8619` pass. Without the protected `C8619/U8601` constraint, this is the
deterministic optimum even though it undoes the previous pass.

This is a closure-liveness defect, not a state-cap, node-cap, seed, learning
rate, or collision-weight problem. Across all attempts, corrected scope peaks
at 15/32, component size at 4/16, and per-component authority states at
256/4096.

## Required Correction Contract

Add a default-off `protected_proposal_authority_search` mode. Preserve all
existing modes for historical replay.

1. Keep the original native proposal coordinates and authorities immutable for
   the complete projection attempt.
2. Maintain the append-only exact `protected_edges` set.
3. On each pass, form connected components over `protected_edges`, but replan
   only components that intersect an endpoint of a current overlap. Unrelated
   protected components and coordinates remain untouched.
4. Enumerate authorities for every active node in each affected protected
   component and validate every protected edge inside that component, not only
   the currently overlapping subset.
5. Keep the M336-177 deterministic objective unchanged: minimum new cumulative
   corrected IDs, then correction energy, then stable assignment order.
6. After applying a plan and the normal hard keep-in projector, run the full
   exact validator. Any residual protected edge is an invariant violation:
   fail closed as `protected_edge_reopened` rather than starting another cycle.
7. A non-legal pass must expose at least one genuinely new exact edge. Add it
   monotonically, expand only its affected protected closure, and continue.
8. Retain the global 32-ID cumulative cap, 16-node component cap, 4,096-state
   per-component cap, inactive-node immutability, and eight-pass limit. Check
   bounds before each real write; do not add a greedy, rigid, origin, checkpoint,
   repair, or exact-site fallback.
9. Serialize current, new, protected, and validated closure edges; affected and
   untouched component counts; state/test/time totals; selected authorities;
   cumulative correction IDs; and a monotonic-progress flag.

For the observed three-node closure, the protected component becomes
`{C8608, C8619, U8601}`. It has two active nodes, at most three distinct native
authorities, and at most nine assignments. A solution must satisfy both
`C8608/C8619` and `C8619/U8601` simultaneously.

## Rejected Alternatives

- Raising `max_iterations` preserves the proven two-cycle.
- Raising node, component, or state caps does not address a limit that was not
  reached.
- Validating every historical component on every pass wastes work; only the
  protected closure touched by a current edge can change.
- Returning to rigid consensus abandons the demonstrated `74/75` authority
  write reduction and repeats M336-174's scale-2 boundary.
- LR, seed, collision-ratio, E4, CP-SAT, and fallback ladders are prohibited by
  M336-177 and cannot repair this closure invariant.

## Required Tests

1. A three-body fixture reproduces the old `A/B <-> B/C` iteration-limit cycle;
   protected mode expands to `{A,B,C}`, satisfies both edges, and converges.
2. A protected edge can never reopen after a committed pass; an injected
   contradiction returns `protected_edge_reopened` with complete diagnostics.
3. A new edge merges two protected components without resetting cumulative IDs
   or omitting either component's historical edges.
4. Protected components unrelated to the current edge are neither enumerated
   nor moved.
5. Expanded component and authority-state limits fail with distinct reasons
   before that pass mutates real coordinates.
6. Inactive nodes remain byte-identical; hard-projection changes remain
   separate from authority changes and feed optimizer-state cleanup.
7. Stable ties match on CPU/GPU for float32/float64.
8. Feature-off, `component_consensus`, `minimum_cover_rollback`, and
   `proposal_authority_search` retain their existing coordinates and non-timing
   diagnostics.
9. Params, runner CLI, run ID, resume validation, reproduction command, summary,
   and report preserve the new mode without changing old-mode schemas.

## Implementation Evidence

The default-off `protected_proposal_authority_search` implementation is ready
for the predeclared D1. It retains one immutable native proposal per projection
attempt, accumulates exact protected edges monotonically, and replans only the
protected components touched by a current residual edge. Each affected plan is
validated against every protected edge in that component. A full-validator
residual that intersects the protected set now fails closed as
`protected_edge_reopened`; the result records current/new/protected/validated
edges, affected and untouched component counts, and monotonic progress.

The three-body regression reproduces the historical `A/B <-> B/C` cycle and
closes it in two passes with nine authority states. A separate four-body
fixture starts from two protected components, introduces a bridge edge, merges
them, validates all three historical edges, and grows the cumulative corrected
scope from two IDs to three without resetting it. Other tests cover unrelated
component isolation, reopened-edge failure, component/state caps before the
failing pass writes, optimizer-state cleanup, runner/resume serialization, and
float32/float64 CPU/GPU identity. Paired pre-change fixtures preserve
coordinates and recursively stripped non-timing diagnostics for all three old
modes.

Installed-tree verification on physical GPU 2 passes `45` projector, `19`
reproducibility, `6` exact-guard, `54` anchor/keep-in/collision, `9` irregular
density, and `105` M336 baseline/config tests: `238/238` focused tests. The
aggregate runner executes `267` tests and repeats TEST-001's ten known API
compatibility errors while returning zero; it is not a green suite. Python
compilation, params JSON parsing, and `git diff --check` pass. No C/CUDA file
changed, so `clang-format` is not applicable.

Source/install SHA-256 parity is:

```text
exact_contact_projection.py
5288253e6c67747dbdacd9020e37f263224d7122bd6714e7ac14fc56df7ebaa6
NonLinearPlace.py
91fbdf91977adbb006990c3830393a55eafb55b592b0f018b50d1fca68b25a59
params.json
51393c2e7c4d0c98283b0194bbaa495b12cf5a2c31497221f3ae7c6c24a70990
```

The protected M336-141 guide aggregate remains
`4091eb8e0611a8042bbc0bf5bed6d15843909d2168a21a4a34655653607ff77d`.
This is implementation evidence only. No D1, D2, D3, E4, fallback, CP-SAT,
cap change, or parameter sweep was run while the implementation was unpushed.

## Experiment Gates

No effect run is authorized until this issue and its implementation are
separately signed, committed, pushed, pulled, installed, and verified from the
installed tree. The first and only effect run is checkpoint-warm E2/E3, seed
`1000`, ten iterations, LR scale `1`, deterministic CuBLAS, physical GPU 2,
and explicit run-local output, summary, and report paths.

D1 passes only if:

- both arms prove `NonLinearPlace`, `PlaceObj`, backward, and ten changing CUDA
  Adam steps;
- every accepted step and float64 serialization replay is 100/100 contained
  with zero keep-in violations, overlaps, and coordinate drift;
- no attempt reports `protected_edge_reopened`, `iteration_limit`, or exceeds
  the unchanged correction/component/state bounds;
- a real closure expands through `C8608/C8619/U8601`, validates both protected
  edges together, and closes without repeating either edge;
- accepted correction writes are strictly below matching rigid counterfactuals
  and no higher than M336-174 D1 (`181/184`);
- maximum correction remains at most `0.00326420 mm`;
- native HPWL/RSMT do not regress from matching M336-174 D1;
- GPU and end-to-end runtime remain within `2x` of M336-171 feature-off; and
- E3 anchor mean and p90 are both strictly lower than same-run E2.

Stop and document any failed conjunct. D2, D3, E4, cap changes, fallback,
CP-SAT, and parameter ladders remain prohibited until a complete D1 pass is
pushed and pulled.

## Acceptance Criteria

- Closure feasibility is monotonic over an append-only exact edge set.
- Only components affected by a current residual edge are replanned.
- Every accepted coordinate derives solely from the current native proposal,
  normal hard projection, and bounded authority selection.
- The synthetic cycle and the real M336 closure terminate without weakening
  exact legality or bounds.
- The complete D1 conjunction passes before any larger native run.

## Scale-1 D1 Replay and Stop

The implementation was signed, committed, pushed, and pulled at
`f56fb09eb42fb7efcaeb26f6783ae8556e69a06a` before the only authorized effect
run. It used checkpoint-warm E2/E3, seed `1000`, ten iterations, LR scale `1`,
deterministic CuBLAS, physical GPU 2, and explicit run-local paths. No D2, D3,
E4, repair, fallback, CP-SAT, or parameter ladder ran.

```text
results/m336/native-cypress/
  m336-178-protected-authority-d1-warm-10-scale1/
summary SHA-256
ce275a8b3a315e04cfb90936c2a373be35dd505ea1252eabd8931cbb6ca933c2
report SHA-256
4c2797a81724660c5343f31409531db21f8dc9ea8184730f33db42fcc10df53c
E2/E3 exact-guard SHA-256
7e79d4073aace712865d716d93b724c62bdccfdb4e33c0c5ca5a814f58fd0569
e7d8a2f61e4e2cb3b87268f9dd6dc764b06164dc549abb7dc84d0f308ba7e97f
```

Both arms prove the complete native CUDA chain with 13 backward calls and ten
changing Adam steps. All `20/20` attempts are accepted on retry zero, every
accepted step is exact legal, and final plus serialized replay are 100/100
contained with zero keep-in violations, overlaps, or coordinate drift. Input
and replay placement hashes match.

The protected closure itself passes. No attempt reports
`protected_edge_reopened`, `iteration_limit`, a repeated current edge, or any
bound failure. Six real closures per arm expand through
`C8608/C8619/U8601`, validate `C8608/C8619` and `C8619/U8601` together, and
finish legal. Maximum component/state scope is `5/16` and `256/4096`.

| Gate | E2 | E3 | Result |
| --- | ---: | ---: | :---: |
| Accepted / rejected | `10 / 0` | `10 / 0` | pass |
| Writes vs matching rigid | `155 / 166` | `158 / 166` | pass |
| Writes vs M336-174 ceiling | `155 / 181` | `158 / 184` | pass |
| Maximum corrected IDs | `20 / 32` | `24 / 32` | pass |
| Maximum correction | `0.003264203 mm` | `0.003264203 mm` | pass; byte-identical to M336-174 maximum |
| Native HPWL | `15632.829467` | `15632.912493` | pass |
| FLUTE RSMT | `17328.847` | `17327.768` | **E2 fail** |
| Normalized score | `0.9280109609` | `0.9280376473` | reported |
| GPU ratio vs feature-off | **`2.414253x`** | `1.938453x` | **E2 fail** |
| End-to-end ratio | `1.197140x` | `1.167840x` | pass |

Against M336-174, HPWL improves by `0.280323/0.106598` and E3 RSMT improves
by `0.439`; E2 RSMT regresses by `0.547`. E3 remains strictly better than E2
in anchor mean/p90 by `0.001307%/0.000473%`. The exact correction maximum is
the same raw value and coordinate scale as M336-174; its displayed value is
not a new overrun of the rounded `0.00326420 mm` contract.

The conjunction fails on E2 RSMT and GPU runtime. M336-179 records exhaustive
authority-search cost, while M336-180 records the FLUTE topology regression.
N6 remains blocked. No larger run is authorized until both successors have a
reviewed implementation and pass one combined scale-1 D1.
