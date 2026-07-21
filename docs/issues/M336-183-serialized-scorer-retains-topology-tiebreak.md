# M336-183: Serialized Scorer Retains a Disabled Projection Dependency

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-21
**Affected commit:** `3af907a`

## Failure

The only authorized M336-181/M336-182 combined D1 was launched on physical
GPU 2 with checkpoint-warm E2/E3, seed `1000`, ten iterations, scale `1`, and
explicit run-local artifact paths. E2 completed its native optimization, but
the runner stopped before E3 when post-serialization float64 scoring exited
with status 1:

```text
ValueError: contact topology tie-break requires exact contact projection
```

The fail-closed exception occurred before aggregate serialization, so no
`summary.json` or `REPORT.md` was emitted for the aborted matrix.

The failed scoring config proves the contradictory state directly:

```text
exact_contact_projection_flag = false
exact_contact_projection_authority_search_strategy = pairwise_factorized
exact_contact_topology_tiebreak_flag = true
global_place_flag = 0
initial_placement_role = serialized_native_replay
```

`_serialized_native_score_config()` correctly disabled the pre-existing
constraint context but did not clear the new dependent topology flag. The
existing isolation test used only legacy fields, so it did not cover this
cross-feature dependency. This is a runner/scorer isolation defect, not an
optimizer or FLUTE failure.

## Reproduction Contract

The run used commit `3af907a5b733b2b296735ef15adcb9e103940584`, GPU
`GPU-ab571afa-cbb6-542c-f2d2-1ccf5045d040`, and
`CUBLAS_WORKSPACE_CONFIG=:4096:8`. Key SHA-256 inputs were:

```text
M336-118 float64 placement  3d3d3ef72bab1f279e9906ada249a724a451c8f415d777f98f84adfa1d93cdbc
M336-118 assignment         e6a08bf40a1f0ceeedda762ab48dcfcc404c9764b0f37a930184036fb2f72c87
pcb_geometry.json           af2f270e520104a0cafbddd7c36ef942a1086fe5e995fd60d7dae705336c6b98
```

The exact runner arguments were:

```text
--experiments E2 E3 --seeds 1000 --iterations 10
--learning-rate-scale 1 --gpu --irregular-density
--footprint-collision --collision-gradient-ratio 0.1
--collision-margin-mm 0 --collision-tau-mm 0.025
--exact-step-guard --exact-step-guard-backoff 0.5
--exact-step-guard-max-retries 4 --no-collision-pair-diagnostics
--exact-contact-projection --exact-contact-projection-max-iterations 8
--exact-contact-projection-mode protected_proposal_authority_search
--exact-contact-projection-max-nodes 32
--exact-contact-projection-max-cover-component-nodes 16
--exact-contact-projection-max-authority-states 4096
--exact-contact-projection-authority-search-strategy pairwise_factorized
--exact-contact-topology-tiebreak --exact-contact-topology-min-net-degree 32
--initialization-track checkpoint_warm_start
--checkpoint-placement experiments/m336/checkpoints/M336-118/placement.float64.pl
--feasible-domain-cache-dir results/m336/native-cypress/cache/feasible-domains
--grid-mm 0.05 --clearance-mm 0 --keepin-margin-mm 0.1
--keepin-margin-tau-mm 0.05 --site-mm 0.05
--assignment experiments/m336/checkpoints/M336-118/assignment.json
--baseline-geometry pcb_geometry.json --bookshelf-dir results/m336/bookshelf
--baseline-output-dir results/m336/baseline
--placer install/dreamplace/Placer.py --anchor-gradient-ratio 0.1
--output-dir results/m336/native-cypress/m336-183-factorized-topology-d1-warm-10-scale1
--summary-path results/m336/native-cypress/m336-183-factorized-topology-d1-warm-10-scale1/summary.json
--report-path results/m336/native-cypress/m336-183-factorized-topology-d1-warm-10-scale1/REPORT.md
```

## Preserved Partial Evidence

The aborted result is retained only as diagnostic evidence under
`results/m336/native-cypress/m336-183-factorized-topology-d1-warm-10-scale1/`.
It is not a complete D1 result and cannot be promoted.

- `NonLinearPlace`, `PlaceObj.obj_fn`, `backward()`, and ten Adam steps ran on
  CUDA; all ten steps changed the native proposal.
- Exact guard accepted `10/10` steps with zero retries. Final validation was
  `100/100` contained, zero keep-in violations, and zero overlaps.
- Factorization represented `2,158` logical authority states with `758` node
  tests, `1,116` pair tests, and only `141` full winner tests.
- The GND tie-break used runtime `net_id=6`, degree `84`, for 17 protected
  passes and 34 bounded score calls; authority won 10 and consensus won 7.
- The serialized placement SHA-256 is
  `44f62b5010c88550ef5927ba454ef9876f9143ef00da5b6f0af2d4ac75154dfd`.
- Primary float32 PPA was HPWL `15632.94921875`, RSMT `17327.96875`; it is not
  the required float-preserving score and therefore is not gate evidence.

E2 GPU optimization took `2.346527902 s`, down `10.08%` from M336-178
(`2.609474063 s`) but still `0.184803902 s` (`8.55%`) above the fixed
`2.161724 s` limit. Thus runtime remains independently open even after the
scorer defect is removed.

## Fix

Serialized scoring now explicitly resets authority search to `exhaustive`
and disables `exact_contact_topology_tiebreak_flag` together with contact
projection. The regression fixture starts from the exact contradictory D1
configuration and asserts that the scoring copy is isolated while the source
configuration remains unchanged.

A scoring-only native diagnostic then replayed the quarantined E2 placement
successfully:

```text
dtype                         float64
HPWL                          15632.948904752731
FLUTE RSMT                    17327.972
coordinate replay max error   0.0
input/replay SHA-256           44f62b5010c88550ef5927ba454ef9876f9143ef00da5b6f0af2d4ac75154dfd
```

The diagnostic HPWL and RSMT satisfy the M336-174 E2 sub-gates
(`15633.109790` and `17328.300`), but this replay is not an atomic combined D1
and cannot repair the missing E3 or failed E2 runtime gate. It validates only
the scorer isolation fix.

## Experiment Boundary

The failed D1 stopped at its first fatal conjunct and did not run E3. A
scoring-only replay may validate this infrastructure fix, but it is not
Cypress algorithm evidence. Do not resume this output or infer a combined D1
pass. Any later effect attempt requires a fresh output directory and explicit
authorization after this fix is committed, pushed, and pulled. D2, D3, E4,
repair, fallback, CP-SAT, and parameter ladders remain prohibited.

## Acceptance Criteria

- Scoring-only configs disable all contact-projection dependants.
- The contradictory source config is not modified in place.
- A native float64 diagnostic replay exits successfully.
- M336-181/M336-182 remain open until a fresh combined D1 passes quality,
  legality, anchor, determinism, and both runtime gates.
