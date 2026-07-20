# M336-179: Protected Authority Enumeration Exceeds E2 Runtime

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `f56fb09`

## Problem

M336-178 removes the protected-edge cycle and accepts all ten scale-1 E2/E3
steps without retry. E2 GPU optimization still takes `2.609474 s`, however,
or `2.414253x` the matching M336-171 feature-off time of `1.080862 s`. The
predeclared limit is `2x`, or `2.161724 s`; E2 exceeds it by `0.447750 s`.

E3 takes `2.612749 s`, or `1.938453x` its `1.347852 s` feature-off control.
Both end-to-end ratios pass (`1.197140x/1.167840x`), but end-to-end time cannot
replace the independently required GPU-stage gate.

## Evidence

The only authorized replay is:

```text
results/m336/native-cypress/
  m336-178-protected-authority-d1-warm-10-scale1/
summary SHA-256
ce275a8b3a315e04cfb90936c2a373be35dd505ea1252eabd8931cbb6ca933c2
E2/E3 exact-guard SHA-256
7e79d4073aace712865d716d93b724c62bdccfdb4e33c0c5ca5a814f58fd0569
e7d8a2f61e4e2cb3b87268f9dd6dc764b06164dc549abb7dc84d0f308ba7e97f
```

The inputs are byte-identical to M336-171 feature-off and M336-174 D1. Both
arms execute `NonLinearPlace`, `PlaceObj`, 13 backward calls, and ten changing
CUDA Adam steps. All attempts finish on retry zero and are exact legal.

| Measure | E2 | E3 |
| --- | ---: | ---: |
| Accepted / rejected attempts | `10 / 0` | `10 / 0` |
| Logical authority states/tests | `2051` | `1935` |
| Maximum states in one component | `256 / 4096` | `256 / 4096` |
| Authority scratch projection | `0.230774 s` | `0.210523 s` |
| Authority exact validation | `0.413813 s` | `0.373116 s` |
| Complete contact projection | `1.257221 s` | `1.197908 s` |
| GPU optimization | `2.609474 s` | `2.612749 s` |
| Ratio to feature-off | **`2.414253x`** | `1.938453x` |

For comparison, M336-174 rigid contact projection takes `0.529680/0.529209 s`.
The protected search adds `0.727541/0.668699 s` even though it avoids every
guard retry. The E2 excess is therefore an exact-enumeration cost, not the old
closure-liveness failure.

## Root Cause

Each affected protected component exhaustively evaluates every assignment of
its immutable native proposal authorities. Every state runs the footprint-aware
component projector and exact component validator before the lexicographic
minimum can be selected. Real components reach five nodes and 256 states; the
complete E2 trajectory evaluates 2,051 states. The implementation is bounded
and correct, but the Python/geometry loop is too expensive for the E2 control's
smaller feature-off denominator.

## Required Correction Contract

1. Preserve M336-178 authority sets, hard projection, exact edge constraints,
   lexicographic objective, stable tie order, and selected coordinates exactly.
2. Add separate logical, exactly evaluated, and admissibly pruned state counts.
   Never relabel a heuristic rejection as an exact prune.
3. Reduce exact work only with proven lower bounds, duplicate-state elimination,
   or batched conservative prefilters. Every surviving winner still requires
   the existing exact component validator and full post-write validator.
4. Compare an optimized search against the exhaustive reference over random
   small components, cycle/merge fixtures, inactive authorities, hard-projector
   cases, float32/float64, and CPU/GPU stable ties.
5. Preserve all historical mode schemas and default-off behavior. No state,
   component, correction, iteration, LR, seed, or collision-ratio change is
   part of this issue.
6. Keep the M336-178 placement and all non-timing diagnostics identical in a
   deterministic trace replay. Runtime-only work cannot claim quality evidence.
7. Do not run another M336 effect experiment until M336-180 also has a reviewed
   candidate; one combined scale-1 D1 must retest both blockers.

The next D1 must keep E2 GPU optimization at or below `2.161724 s` and E3 at
or below `2.695705 s` on the same physical GPU and inputs. End-to-end time must
also remain within `2x`.

## Rejected Alternatives

- Raising caps increases work and does not address the measured limit.
- Reducing iterations, LR, or collision pressure changes the qualified native
  trajectory and becomes an unauthorized parameter ladder.
- Skipping exact component or full validation weakens the safety contract.
- Comparing only with M336-174 or reporting end-to-end time hides the explicit
  feature-off GPU-stage failure.
- Reusing a state result across different proposals without a complete cache
  key is unsound because coordinates and projected geometry change each step.

## Acceptance Criteria

- Exhaustive and optimized searches select byte-identical coordinates.
- Exact legality, protected-edge monotonicity, and all existing bounds remain.
- Both scale-1 arms pass their independent `2x` GPU and end-to-end gates.
- M336-180's RSMT gate passes in the same replay before N6 can advance.
