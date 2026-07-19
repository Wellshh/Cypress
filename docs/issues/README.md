# Engineering Issue Ledger

This directory is the durable issue tracker for the `experiment` branch. The
GitHub Issues API returned `410 Issues has been disabled in this repository` on
2026-07-18, so findings are recorded here and pushed as ordinary reviewed
commits. Each milestone must pull first, inspect updates to these files, then
append evidence rather than replacing prior observations.

| ID | Severity | Status | Summary |
| --- | --- | --- | --- |
| [M336-001](M336-001-manual-baseline-score-gate.md) | Critical | Mitigated | Manual baseline is scored, but E4 remains below its quality gate |
| [M336-002](M336-002-soft-keepin-zero-gradient.md) | High | Open | Soft keep-in contributes zero gradient after hard projection |
| [M336-003](M336-003-acceptance-shortfalls.md) | High | Open | Initial matrix misses anchor-distance and runtime targets |
| [M336-004](M336-004-bookshelf-coordinate-fidelity.md) | Critical | Mitigated | BOTTOM pins were mirrored twice and placement evaluation rounded coordinates |
| [M336-005](M336-005-initialization-runtime-quality.md) | High | Open | Warm-start initialization dominates runtime and destroys baseline quality |
| [M336-006](M336-006-partial-matrix-reporting.md) | Medium | Resolved | E4-only report crashed before writing the summary |
| [M336-007](M336-007-fixed-assignment-quality-bound.md) | Critical | Open | Current fixed assignment cannot reach the manual quality baseline |
| [M336-008](M336-008-grid-resolution-packing-feasibility.md) | Critical | Mitigated | A packing exclusion was incorrectly reused across grid resolutions |
| [M336-009](M336-009-runtime-fixed-endpoint-bound.md) | Critical | Resolved | Quality bounds used implicit placement coordinates for runtime-fixed endpoints |
| [M336-010](M336-010-shared-coordinate-quality-bound.md) | Critical | Open | The interval MILP admits a candidate that shared component coordinates prove impossible |
| [M336-011](M336-011-integer-quality-proof-margin.md) | Critical | Resolved | Integer scaling lacked a conservative HPWL threshold allowance |
| [M336-012](M336-012-global-discrete-quality-infeasibility.md) | Critical | Open | No same-side assignment can pass score 1.0 on the 0.05 mm lattice |
| [M336-013](M336-013-clearance-double-application.md) | High | Resolved | Alternate-region search applied nonzero clearance twice |
| [M336-014](M336-014-continuous-quality-infeasibility.md) | Critical | Open | The score target is impossible even in a continuous no-collision relaxation |
| [M336-015](M336-015-warmstart-anchor-coordinate-contract.md) | Critical | Open | Runtime freezing overwrites two materially moved manual-baseline anchors |
| [M336-016](M336-016-two-anchor-discrete-quality-candidate.md) | Critical | Open | Two baseline anchor endpoints restore an exact-site score candidate, but collision search is unresolved |
| [M336-017](M336-017-convex-collision-false-infeasibility.md) | Critical | Resolved | Convex hull collision constraints rejected a known legal concave-footprint placement |
| [M336-018](M336-018-anchor-relocation-requires-global-repacking.md) | Critical | Open | Restored baseline anchors require movement beyond their first physical-neighbor ring |
| [M336-019](M336-019-prune-impossible-collision-pairs.md) | High | Resolved | Swept-domain bounds remove 94.55% of impossible convex-part collision constraints |
| [M336-020](M336-020-structured-assignment-site-hints.md) | High | Resolved | Region-local result hints now seed optimized assignment without disabling alternate regions |
| [M336-021](M336-021-scope-hinted-assignment-search.md) | High | Resolved | Structured hints can limit alternate-region choices without freezing component coordinates |
| [M336-022](M336-022-local-restored-anchor-domain-infeasible.md) | Critical | Open | Hint-centered restored-anchor domains remain infeasible through 4,096 sites per component-region |
| [M336-023](M336-023-project-candidate-guides-per-region.md) | High | Resolved | Physical candidate guides now project independently into every eligible region |
| [M336-024](M336-024-isolate-packing-from-hpwl.md) | High | Resolved | Diagnostic packing can omit HPWL, confirming collision search is the remaining bottleneck |
| [M336-025](M336-025-decompose-packing-by-side.md) | High | Resolved | Side decomposition produces a deterministic zero-overlap BOTTOM packing |
| [M336-026](M336-026-packing-hint-fixed-footprint-mismatch.md) | Critical | Resolved | Packing hints now use exact fixed footprints and the shared deterministic strategy chain |
| [M336-027](M336-027-partial-fix-domain-inflation.md) | High | Resolved | Partially fixed components now retain one hinted site instead of broad candidate domains |
| [M336-028](M336-028-coarse-top-lattice-infeasible.md) | High | Open | Restored-anchor TOP packing is infeasible on the tested 0.2 mm lattice |
| [M336-029](M336-029-indirect-site-coordinate-encoding.md) | High | Mitigated | Direct coordinate tables reduce packing memory but have not solved restored TOP packing |
| [M336-030](M336-030-frozen-anchor-continuation.md) | Critical | Mitigated | Bounded frozen-anchor continuation finds replayable TOP states hidden by the direct jump |
| [M336-031](M336-031-feasibility-continuation-quality-loss.md) | Critical | Open | Feasibility continuation is replayable but loses HPWL and stalls before the final endpoint |
| [M336-032](M336-032-fixed-obstacle-site-pruning.md) | High | Mitigated | Exact preprocessing removes candidate sites that necessarily overlap fixed obstacles |
| [M336-033](M336-033-staged-controlled-collision-relaxation.md) | Critical | Mitigated | Staged shape-class packing yields small conflict sets but not an exact endpoint placement |
| [M336-034](M336-034-incremental-controlled-collision-cuts.md) | Critical | Open | Incremental exact collision cuts converge to 100 pairs, then stall before zero-overlap closure |
| [M336-035](M336-035-rotated-footprint-inner-propagation.md) | High | Mitigated | Exact-safe inner rectangles strengthen rotated-footprint propagation but do not close packing |
| [M336-036](M336-036-nonrectangle-first-search-regression.md) | High | Resolved | Explicit nonrectangle-first branching regresses CP-SAT conflict learning and is not retained |
| [M336-037](M336-037-side-scoped-fixed-site-cores.md) | High | Mitigated | Assumption cores identify 12 stale fixed TOP sites, but the remaining seven-site boundary is unresolved |
| [M336-038](M336-038-fixed-obstacles-in-min-conflicts.md) | High | Mitigated | Min-conflicts now hard-prunes fixed-obstacle sites, but exact TOP closure remains unresolved |
| [M336-039](M336-039-discrete-packing-stalls-at-one-overlap.md) | Critical | Open | Exact heuristic packing reaches one overlap; CP encodings remain unresolved and require quantization audit |
| [M336-040](M336-040-exact-site-cnf-core-boundary.md) | Critical | Open | Validator-aligned CNF closes K256 and exposes a global K512 repacking boundary |
| [M336-041](M336-041-quality-guide-k512-infeasible.md) | Critical | Open | Exact CNF proves the quality-guide K512 domain has no legal TOP packing |
| [M336-042](M336-042-score-guide-global-repacking.md) | Critical | Open | Score-feasible collision-relaxed sites require near-global TOP repacking |
| [M336-043](M336-043-exact-cpsat-local-domain-proof.md) | Critical | Open | Exact CP-SAT proves score-guide and manual-baseline K512 domains infeasible |
| [M336-044](M336-044-cpsat-search-budget-reproducibility.md) | High | Mitigated | CP-SAT now records deterministic budgets, preprocessing threads, and hint repair controls |
| [M336-045](M336-045-known-legal-fixed-site-core-chain.md) | Critical | Open | Restored obstacles turn known-legal TOP repair into a near-global K1024 repacking problem |
| [M336-046](M336-046-no-overlap-2d-propagation-regression.md) | High | Resolved | Optional NoOverlap2D propagators regress K512 and do not find a K1024 placement |
| [M336-047](M336-047-emi-only-legal-skeleton.md) | Critical | Mitigated | EMI-only restores exact K512 TOP packing, but BOTTOM quality remains below the score gate |
| [M336-048](M336-048-side-specific-hpwl-native-replay.md) | Critical | Mitigated | Exact side packing now couples HPWL and native replay, but final BOTTOM closure remains unresolved |
| [CUDA-001](CUDA-001-net-crossing-input-contract.md) | Critical | Mitigated | Invalid node/pin shape reached native net-crossing code |
| [REPRO-001](REPRO-001-placer-import-log-side-effect.md) | High | Resolved | Importing Placer truncated a tracked log in the caller's CWD |

Status values are `Open`, `Mitigated`, `Resolved`, and `Accepted Risk`. A
finding is resolved only after its acceptance criteria have direct test or
experiment evidence. If Issues are enabled later, migrate each document to a
GitHub issue and retain the resulting URL in this index.
