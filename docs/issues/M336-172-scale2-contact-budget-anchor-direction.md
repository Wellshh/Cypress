# M336-172: Scale-2 Contact Budget Masks Anchor Direction

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `f837019`

## Problem

The single authorized N6 D2 checkpoint-warm test remains exact legal, but it
does not pass the promotion contract. LR scale `2` creates contact support
wider than the bounded 32-node candidate projector, so the transactional guard
backs both E2 and E3 down to an LR below the D1 scale-1 value. The resulting E3
placement is marginally farther from anchors than E2 despite executing the
adaptive anchor objective.

This is not an exact-guard failure. Every illegal candidate is rejected and
rolled back, all ten accepted steps are legal, and no E4 repair or checkpoint
fallback runs. It is a native motion-control failure: the larger proposal does
not remain both bounded and anchor-directed.

## Reproduction Contract

The run uses physical GPU 2, deterministic CuBLAS, seed `1000`, ten Adam
steps, the M336-118 float64 warm start, LR scale `2`, collision ratio `0.1`,
zero collision margin, tau `0.025 mm`, four `0.5` backoffs, and the bounded
eight-iteration/32-node contact projector:

```bash
env CUBLAS_WORKSPACE_CONFIG=:4096:8 CUDA_VISIBLE_DEVICES=2 \
  PYTHONPATH="$PWD/install:$PWD:/tmp/m336-ortools-py311" \
  python3.11 experiments/m336/scripts/run_matrix.py \
  --experiments E2 E3 --seeds 1000 --iterations 10 \
  --learning-rate-scale 2 --gpu --irregular-density \
  --footprint-collision --collision-gradient-ratio 0.1 \
  --collision-margin-mm 0 --collision-tau-mm 0.025 \
  --exact-step-guard --exact-step-guard-backoff 0.5 \
  --exact-step-guard-max-retries 4 \
  --no-collision-pair-diagnostics --exact-contact-projection \
  --exact-contact-projection-max-iterations 8 \
  --exact-contact-projection-max-nodes 32 \
  --initialization-track checkpoint_warm_start \
  --output-dir \
    results/m336/native-cypress/m336-171-contact-projection-d2-warm-10-scale2
```

Source SHA is `f8370194b22149640cb6b55e3f814577df777f22`. Input,
assignment, implementation, and installed-file hashes match the D1 evidence.

## Results

Both runs prove the native chain with 13 backward calls, ten changing CUDA Adam
steps, native float64 HPWL/FLUTE scoring, and exact post-serialization replay.

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Accepted / rejected attempts | `10 / 3` | `10 / 3` |
| Final containment / keep-in / overlap | `100/100 / 0 / 0` | `100/100 / 0 / 0` |
| Raw proposal overlap range | `10-18` | `10-18` |
| Native HPWL | `15631.983134` | `15631.980929` |
| FLUTE RSMT | `17326.895` | `17327.198` |
| Normalized score | `0.9280885790` | `0.9280804625` |
| Anchor mean (`mm`) | `6.523922318` | `6.524060019` |
| Anchor p90 (`mm`) | `12.047258356` | `12.047783728` |
| Constrained path / net (`mm`) | `0.010654611 / 0.010124661` | `0.009045246 / 0.008559809` |
| Hard keep-in projected nodes | `2` | `2` |
| Contact-control time (`s`) | `0.712234` | `0.661502` |
| GPU optimization / end-to-end (`s`) | `2.08943 / 13.5108` | `2.10312 / 14.8057` |

Relative to the corresponding D1 scale-1 runs:

- E2 path/net displacement rises only `1.501%/0.190%`.
- E3 path/net displacement rises `4.524%/3.006%`.
- HPWL and RSMT improve by `0.00281%/0.00221%` in E2 and
  `0.00299%/0.00339%` in E3.
- Contact correction events change from `236` to `246` in E2 and `252` to
  `253` in E3, while hard keep-in projections change from zero to two.
- Maximum contact correction rises from `0.00171982 mm` to `0.00338435 mm`,
  a `1.968x` increase.

Scale `2` therefore preserves and slightly improves native quality, but its
extra motion is small after backoff and its projection pressure is higher.
Most importantly, E3 versus E2 makes anchor mean `0.00211%` worse and p90
`0.00436%` worse. E3 RSMT is also `0.303` worse and normalized score is
`0.00000812` lower than E2. The anchor objective has no positive causal signal
under this D2 contract.

Placement SHA-256 values are:

```text
E2 6239b1d75a0ae8263c025365d262eddeee8bb3e9defb5c8d844ad63136cdf887
E3 fd4533d95d5108d316c7dcf160e5f155d2ef4bb3e083b3366f5c657f0a3e0928
```

Evidence hashes are:

```text
summary
63fdcadde5839d013d95ca9df43d11159b17994c7274aa625ea68436a0d8b0a3
E2 exact guard
ff2d227451f9a184e2a384099dcd87240c063eefc66d3c87c05f78f587e3c10c
E3 exact guard
334b99760cb10bb7e0b99bd7c12c5ac05ec2a808f832628788ad3b01c38a7825
```

## Contact-Budget Evidence

The requested LR is `0.02`; learning-rate estimation produces
`0.0453815013`, versus `0.0230855606` in D1. Both runs accept the first larger
step, then reject iteration 1 with 18 raw crossing pairs. The protected closure
contains 33 total nodes, 32 active nodes, and 13 disconnected components, so it
exceeds the global 32-node safety budget. The largest individual component has
only four nodes at this point.

E2 then rejects iterations 8 and 9 with 34 total contact nodes. E3 rejects
iteration 6 twice with 33 total nodes. In every case, the largest individual
component is at most five total/four active nodes; the limit is reached by the
aggregate support of many independent contacts, not one large coupled contact
component.

The exact guard correctly applies global LR backoff:

```text
initial scale-2 LR  0.0453815013
after first reject  0.0226907507
after second reject 0.0113453753
final accepted LR   0.0056726877
D1 initial LR       0.0230855606
```

E2 reaches the final LR at iteration 9. E3 reaches it at iteration 6 after two
retries and uses it for the remaining steps. Thus the nominal scale-2 run ends
at roughly one quarter of its initial LR and one quarter of the D1 LR. The
trust region preserves legality but cannot provide sustained larger motion.

## Root Cause

`ExactContactProjector` is intended to bound the active coordinates corrected
in one proposal so projection cannot become a broad legalizer. The affected
implementation instead bounds the union of active and inactive endpoints.
Inactive/frozen endpoints provide authoritative motion to
`_component_displacement()`, but `_apply_consensus()` never writes them and
optimizer-state cleanup never treats them as corrected coordinates. Counting
them against the correction budget is inconsistent with the actual operation.

All six D2 rejections have exactly 32 active contact nodes, which is within the
declared limit, and one or two inactive reference endpoints, which produce the
reported total of 33/34. This off-by-reference error triggers global backoff
even though the active correction scope has not exceeded 32.

Blindly raising `exact_contact_projection_max_nodes` would hide this signal and
allow an increasingly broad exact correction. Treating each disconnected
component as an unlimited independent repair would have the same contract
risk. The upstream proposal must first reduce the number of crossing contacts
or enforce non-penetrating motion for near-contact components before positive
area appears.

The anchor failure is related but distinct. Scale-2 E2 improves anchor metrics
slightly more than E3 relative to D1, so the small absolute decrease cannot be
attributed to the anchor objective. Repeated global backoff also applies one LR
to all nodes, allowing unrelated contacts to suppress anchor-directed motion.

## Active-Budget Correction Candidate

The default-off projector now checks the 32-node limit against active contact
nodes only. The numerical limit, exact validator, global active scope, closure
iterations, contact consensus, hard keep-in projection, transactional guard,
and fail-closed reason remain unchanged. Total endpoints are still serialized
for audit, together with:

- `contact_node_limit_basis = active_nodes`;
- total and active contact-node counts per closure iteration;
- total and active contact-node counts for the complete attempt;
- component count;
- maximum total and active nodes in any contact component.

The parameter and runner help text now state that the limit bounds active nodes
corrected in one native proposal. No automatic cap growth or per-component
unbounded processing is introduced.

A new mixed active/frozen test creates two independent crossing pairs with four
total endpoints, two active endpoints, and a limit of two. Projection succeeds,
does not move either inactive reference, and reports the two scopes separately.
The existing three-active-node case still fails closed at a limit of two.

Validation after source installation:

```text
exact contact projection       8/8
exact accepted-step guard      6/6
anchor/keep-in/collision      51/51
M336 baseline/config         104/104
reproducibility               17/17
source/install projector      byte-identical
source/install params         byte-identical
```

An initial module-style unittest command did not execute because the repository
directory name `unittest` is shadowed by Python's standard-library module. The
same test file was then run directly and passed; this was a command-selection
error, not a test failure.

This candidate is not yet an effect claim. M336-172 remains open until one
post-fix D2 replay proves whether removing false inactive-node backoffs keeps
the active scope bounded and restores a positive E3-minus-E2 anchor signal.

## Impact

- D2 fails its projection-pressure and anchor-direction gates.
- D3 warm 50-step E2/E3/E4 is prohibited.
- LR scales `4/8/16/32`, seed sweeps, larger scalar collision ratios, and broad
  E4 repair remain prohibited.
- The exact guard remains valid and must not be weakened; no illegal placement
  or fallback output was promoted.

## Required Remediation

1. Add accepted-step summaries for total contact nodes, component count,
   maximum component size, corrected-node fraction, and the reason each scope
   limit is reached. Do not infer pressure from one maximum alone.
2. Reduce broad crossing support before exact validation. Candidate approaches
   include a bounded near-contact active set or component-local proposal
   constraints that use the actual Adam displacement and conservative contact
   cones, including tangent-entry cases.
3. Keep an explicit global work/scope budget even if independent components are
   processed separately. Any change from the current 32-node contract requires
   focused tests and an ablation proving it is not broad legalization.
4. Avoid global LR collapse from unrelated components where possible. A local
   trust-region mechanism may limit only affected coordinates, but it must
   restore Adam state exactly and remain deterministic.
5. Re-establish a positive E3-minus-E2 anchor effect under identical collision
   settings before extending the iteration budget.
6. Preserve feature-off parity, hard keep-in projection, exact validation,
   float64 replay, default-off behavior, and the prohibition on CP-SAT or
   checkpoint fallback.

## Acceptance Criteria

- Focused tests cover multiple disconnected contact components near the global
  budget and one genuinely large coupled component.
- Scope metrics distinguish global total nodes from maximum component nodes and
  are byte-reproducible on CPU/GPU where coordinates are expected to match.
- The next single D2 replay has zero overlap after every accepted step and no
  broad E4 repair.
- Contact pressure stays within the predeclared global budget without silently
  increasing the current limit.
- Scale-2 constrained net displacement increases materially rather than only
  through its first step; the threshold must be declared before rerunning.
- E3 improves both anchor mean and p90 versus same-run E2.
- Native HPWL/RSMT do not regress versus D1, and all source/input/placement
  hashes and stage timings remain complete.
