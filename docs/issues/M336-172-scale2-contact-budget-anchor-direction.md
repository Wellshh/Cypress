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

## Post-Fix D2 Replay

Commit `e99673f1cff56ce7cb3db71fe78a54b7082cb659` was pushed and
pulled before the one authorized replay. The run uses the same D2 contract and
writes to
`results/m336/native-cypress/m336-172-active-budget-d2-warm-10-scale2/`.
It executes `NonLinearPlace`, `PlaceObj`, 13 backward calls, and ten changing
CUDA Adam steps in each arm. E4, CP-SAT placement, repair, and fallback remain
disabled.

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Accepted / rejected attempts | `10 / 4` | `10 / 5` |
| Final containment / keep-in / overlap | `100/100 / 0 / 0` | `100/100 / 0 / 0` |
| Native HPWL | `15631.746997` | `15631.705249` |
| FLUTE RSMT | `17325.858` | `17326.810` |
| Normalized score | `0.9281235331` | `0.9280990557` |
| Anchor mean (`mm`) | `6.523258388` | `6.523921861` |
| Anchor p90 (`mm`) | `12.045451606` | `12.047263630` |
| Constrained path / net (`mm`) | `0.013341648 / 0.012577319` | `0.009582606 / 0.009123127` |
| Hard keep-in projected nodes | `4` | `2` |
| GPU optimization / end-to-end (`s`) | `2.02390 / 13.7367` | `2.29210 / 14.4123` |

The correction has the intended narrow effect: a closure with 33 total
endpoints but only 32 active endpoints now converges and is accepted. It does
not remove the safeguard. Later E2 proposals reach 33, 33, and 34 active nodes;
E3 reaches 33 active nodes in five proposals. Those eight proposals correctly
fail with `contact_node_limit`. One additional E2 retry stays at 28 active
nodes but fails `stalled`. Maximum component scope remains four active/five
total nodes, confirming that aggregate support across 14-16 disconnected
components, not one coupled component, causes the real limit failure.

Every accepted step has zero exact keep-in and overlap violations. The true
active pressure nevertheless forces E2's final accepted LR to `0.0028363438`
and E3's to `0.0014181719`, below both the original D2 and D1 endpoints.
Relative to D1, constrained net displacement rises `24.461%` in E2 and
`9.784%` in E3, while HPWL/RSMT improve by `0.675270/1.420` and
`0.742851/0.976`, respectively. Larger motion therefore exists, but it is not
anchor-directed: E3 makes anchor mean `0.010171%` worse and p90 `0.015043%`
worse than same-run E2. E3 also gives back `0.952` RSMT and
`0.0000244774` normalized score.

The active-budget implementation fix is retained, but D2 still fails both the
global active-scope and anchor-direction gates. D3 remains prohibited. Do not
raise the 32-active-node cap; the next material change must reduce simultaneous
crossing support in the native proposal or introduce a bounded, deterministic
local trust region before another D2 replay.

Evidence SHA-256 values are:

```text
summary
048e13819208f650b0965ee2b77d3765cda9af2a6620cc2606344f320c255fd7
E2 exact guard
901f1577eacbac4288ca9b57c01569ff9dfc18963dd6b60de6058210cf00c746
E3 exact guard
4c2cdfb0761ee2271f1f5a101c0739f685aee2f6ef35a254a2846d6f6c089d0b
E2 placement
41c66e690c9d1b2c7fe90711dc0170c60951d9091c2475edce328ade73270acd
E3 placement
1574669cd1bba21ccdba154ad4727f53a408cf8c409febefc22ffa0eb1cbd562
```

## Representative-Scope D2 Replay

M336-174 replaces all-active averaging with one deterministic native
representative per component and bounds the cumulative union of selected
correction IDs. After its D1 gate passed, the single authorized scale-2 replay
ran at `d4fddbbaddf828df4d0544e4d3f4abdf36694f73` with the unchanged
seed, iteration, LR, collision, guard, and cap contract.

The narrower intervention materially improves scale-2 motion and anchor
direction, but it does not eliminate the real global scope boundary:

| Metric | E2 | E3 |
| --- | ---: | ---: |
| Accepted / rejected attempts | `10 / 1` | `10 / 1` |
| Maximum active / total contact endpoints | `51 / 53` | `51 / 53` |
| Maximum applied / required correction scope | `32 / 33` | `32 / 33` |
| Initial / final LR | `0.0453815013 / 0.0226907507` | `0.0453815013 / 0.0226907507` |
| Maximum correction (`mm`) | `0.00642050` | `0.00642050` |
| Constrained path / net (`mm`) | `0.018706298 / 0.017160281` | `0.018773225 / 0.017195781` |
| Native HPWL / RSMT | `15633.196929 / 17326.600` | `15633.106040 / 17326.477` |
| Anchor mean / p90 (`mm`) | `6.522501064 / 12.043654952` | `6.522317506 / 12.043574216` |

At iteration 7 in each arm, retry zero requires 33 cumulative correction IDs
across components whose largest active scope is only four. The projector fails
closed with `contact_node_limit`; the exact guard restores position and
optimizer hashes exactly, halves the LR once, and accepts retry one. All ten
accepted steps and both serialized placements remain 100/100 contained with
zero keep-in violations and overlaps.

The following gates pass:

- final LR is exactly half the initial scale-2 LR;
- maximum correction is `1.96694x` D1, below the `2x` ceiling;
- net displacement is `69.81%/106.93%` above the original M336-171 D1 values;
- E3 anchor mean and p90 are strictly lower than E2;
- RSMT improves from current D1 by `1.700/1.730` for E2/E3.

Two mandatory gates fail:

- required cumulative scope reaches 33, above the unchanged cap of 32;
- HPWL regresses from current D1 by `0.087139/0.086948` for E2/E3.

M336-173's anchor-direction defect is resolved independently, but M336-172
remains open on genuine simultaneous crossing pressure and quality retention.
D3, cap growth, E4 repair, and parameter ladders remain prohibited.

Evidence SHA-256 values:

```text
summary
8126ab17063f3c183a85566cfe4fa07409ea541e6e9591d0c00653fe16eef8d7
E2 exact guard
92345bcefbe1ae608b0703570596e6c3db8b0a46c1b9abfb84733de3fd8de999
E3 exact guard
647ccc7efbd9c8ec0f36fa9bdd1525efb6f3a9b036e718e27813be72b473e67e
E2 placement
7b200b6b8fc786411960c3930fa33ba5353f036ddbb3ce484c647266b703ae7e
E3 placement
7267600f9200d668a31ae943d13205088867346af2c82813d6499d5e436f49b2
```
