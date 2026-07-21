# M336-181: Authority Search Repeats Separable Exact Work

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `f56fb09`

## Problem

M336-179 attributes the failed E2 runtime gate to 2,051 protected-authority
states. The current implementation rebuilds and projects every component and
then recreates every exact footprint for every Cartesian assignment. Most of
that work is repeated: a node has only one projected coordinate per distinct
proposal authority, and each protected constraint is a two-node edge.

The optimization cannot change the authority set, hard projector, exact edge
semantics, lexicographic objective, stable tie order, selected coordinates, or
any existing bound. A heuristic prefilter is not acceptable.

## Exact Factorization

The production callbacks have two explicit properties:

1. `RegionProjector.project_lower_left_subset()` projects every active node
   independently into that node's footprint-aware feasible domain.
2. `exact_contact_component_report()` is the conjunction of per-node keep-in
   containment and exact intersections for the supplied protected edges. It
   contains no three-body or component-global geometric constraint.

Therefore an assignment is exact legal if and only if every selected
node/authority candidate is keep-in legal and every protected edge's selected
candidate pair is non-overlapping. The optimized path may:

1. materialize and hard-project each distinct `(node, authority)` candidate
   once with the original dtype conversion;
2. deduplicate byte-identical projected candidates while retaining the stable
   lowest authority ID that the exhaustive key would select;
3. exact-check each protected candidate pair once;
4. enumerate the remaining compatibility products and calculate the unchanged
   key `(new corrected IDs, correction energy, assignment order)`; and
5. run the existing full component validator on the selected winner before it
   can be written.

If the full winner check contradicts the factorized proof, fail closed as
`authority_factorization_mismatch`. Do not try another state or fall back to a
historical mode.

## Diagnostics

Report, separately and additively:

- logical Cartesian states;
- unique projected candidate combinations;
- duplicate-coordinate prunes;
- exact incompatible-pair prunes;
- objective-dominated prunes;
- full component state evaluations;
- candidate projection and pair/full validation times;
- exhaustive-reference parity status in tests and trace replay.

Historical exhaustive behavior remains available and is the default. The
factorized strategy is default-off and valid only when callbacks explicitly
declare node-separable projection and edge-decomposable exact validation.

## Required Tests

1. Random small AABB components select byte-identical coordinates and
   authority assignments under exhaustive and factorized searches.
2. Cycle, protected-edge merge, inactive-authority, hard-projection, and stable
   tie fixtures retain the M336-178 result for float32/float64 on CPU/GPU.
3. Duplicate projected coordinates retain the exhaustive authority tie order.
4. A deliberately non-decomposable validator is rejected before mutation.
5. A factorization/full-validator contradiction fails before real writes.
6. Logical, pruned, pair-tested, and full-tested counts reconcile exactly.
7. Feature-off and all historical contact modes retain their prior output.
8. A deterministic M336-178 trace replay has identical coordinates and all
   non-timing diagnostics after strategy-only fields are removed.

## Experiment Boundary

This issue is runtime-only. It cannot claim quality evidence and it must not
run an M336 effect experiment alone. Implement, install, test, commit, push,
and pull it together with the reviewed M336-182 candidate. Then run exactly one
combined checkpoint-warm E2/E3 seed-1000, ten-step, scale-1 D1.

The D1 runtime limits remain `2.161724 s` for E2 and `2.695705 s` for E3 GPU
optimization, with both end-to-end ratios also at most `2x`. No cap, seed, LR,
collision ratio, repair, fallback, CP-SAT, D2, D3, or E4 change is authorized.

## Acceptance Criteria

- Exhaustive and factorized winners are byte-identical before M336-182 is on.
- Every prune has an exact proof and complete count provenance.
- Exact legality, protected-edge monotonicity, and all M336-178 bounds remain.
- The combined D1 passes both independent runtime gates.

## Implementation Evidence (2026-07-21)

The default-off `pairwise_factorized` strategy is now implemented. Production
enables it only with an explicit node-separable projector and edge-decomposable
validator contract. It projects each `(node, authority)` once, caches exact
candidate-edge checks, retains the exhaustive lexicographic key, and runs the
full component validator on the winner before any real position write. A
contradiction fails closed as `authority_factorization_mismatch`.

Diagnostics separately reconcile duplicate projected states, node-infeasible
states, incompatible-edge states, objective-dominated states, and the one full
winner check. This separation was added after review found that an initial
implementation incorrectly grouped keep-in failures with pair incompatibility.

Focused tests cover random components, stable ties, cycles, protected-edge
merges, inactive endpoints, hard projection, float32/float64, and CPU/GPU.
Sixteen direct `HEAD`/current fixtures across all four historical modes produce
byte-identical coordinates and identical non-timing diagnostics. The combined
installed applicable suite is `247/247`; five unrelated CP-SAT tests remain
excluded because the production environment does not install optional
OR-Tools. This is implementation evidence only. M336-179 remains open until
the single combined D1 passes its runtime gates.

The first combined D1 attempt is quarantined by M336-183: E2 GPU time fell to
`2.346527902 s` but still missed the `2.161724 s` gate, and a scoring-config
dependency stopped the runner before E3. This does not satisfy acceptance.
