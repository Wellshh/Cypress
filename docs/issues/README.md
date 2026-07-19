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
| [M336-049](M336-049-fixed-domain-region-coordinate-descent.md) | Critical | Mitigated | Exact regional/global descent improves certified legal HPWL by 2,073.420 |
| [M336-050](M336-050-page7-net-span-bottleneck.md) | Critical | Open | Certified boundary-driven expansion improves HPWL; its search bound remains quarantined |
| [M336-051](M336-051-cpsat-objective-replay-mismatch.md) | Critical | Mitigated | Objective metadata can lag postsolved values; replay audit and fixed certification fail closed |
| [M336-052](M336-052-exact-one-opt-descent.md) | Critical | Open | Reproducible exact one- and two-component descent improves HPWL but leaves a higher-order gap |
| [M336-053](M336-053-threshold-feasibility-search-unknown.md) | Critical | Open | Global threshold searches exhaust deterministic budgets as UNKNOWN, not infeasible |
| [M336-054](M336-054-hotspot-regional-domain-bound.md) | Critical | Open | A hotspot K512 region improves HPWL but its valid bound proves the restricted domain cannot score 1.0 |
| [M336-055](M336-055-physical-group-closure.md) | Critical | Open | Physical collision closure improves HPWL and exposes fixed-budget candidate-width regression |
| [M336-056](M336-056-bottom0-score-bound.md) | Critical | Open | Full bottom-0 K256 closure restores a valid lower bound below the score-1 threshold |
| [M336-057](M336-057-refreshed-regional-search-stall.md) | Critical | Open | Refreshed regional and global searches remain budget-limited without another incumbent |
| [M336-058](M336-058-bounded-improvement-search.md) | Critical | Mitigated | Hard improvement bounds expose reproducible restricted searches without weakening legality |
| [M336-059](M336-059-hint-repair-conflict-budget.md) | High | Mitigated | Hint repair can consume deterministic time without reaching its conflict budget |
| [M336-060](M336-060-hpwl-feasibility-audit-gap.md) | Critical | Mitigated | Pure HPWL feasibility now fails closed through selected-site and per-net replay |
| [M336-061](M336-061-current-quality-domain-search-stall.md) | Critical | Open | Current-first quality candidates still stall and the quality guide itself contains 383 overlaps |
| [M336-062](M336-062-guided-threshold-escape.md) | Critical | Mitigated | Deterministic guided threshold escape crosses local barriers without weakening exact legality |
| [M336-063](M336-063-exact-escape-search-seed.md) | High | Mitigated | Worse exact escape states can seed global search without entering the scoring path |
| [M336-064](M336-064-legacy-endpoint-metadata-replay.md) | Critical | Resolved | Legacy endpoint overrides now replay from either metadata location and conflict fail-closed |
| [M336-065](M336-065-corrected-residual-boundary-expansion.md) | Critical | Open | Corrected 80-component residual boundary is score-permitting but stalls under one K128 budget |
| [M336-066](M336-066-staged-page86-bounded-search.md) | Critical | Open | Staged page-86 K256 search is budget-limited and its restricted bound remains below incumbent but above score 1.0 |
| [M336-067](M336-067-page86-physical-group-closure.md) | Critical | Open | Complete page-86 physical-group domains are exact local optima and require cross-group release |
| [M336-068](M336-068-page6-group-improvement.md) | Critical | Mitigated | K1024 page-6 group optimization produces a strict certified improvement and fresh two-optimum |
| [M336-069](M336-069-current-quality-domain-breadth.md) | Critical | Mitigated | Current/quality K512 candidate allocation improves the certified bottom-0/page-7 closure |
| [M336-070](M336-070-topology-refresh-page6.md) | Critical | Mitigated | Refreshing the changed topology unlocks a second certified page-6 group improvement |
| [M336-071](M336-071-model-shape-search-effect.md) | Critical | Mitigated | Wider movable support changes deterministic CP-SAT search even when added variables remain at source sites |
| [M336-072](M336-072-cross-group-plateau-diversity.md) | Critical | Mitigated | Cross-group K1024 closure yields a certified improvement and distinct equal-HPWL plateau states |
| [M336-073](M336-073-explicit-guide-candidate-weights.md) | High | Mitigated | Multi-guide candidate allocation is now explicit, weighted, validated, and recorded |
| [M336-074](M336-074-alternating-regional-refresh.md) | Critical | Mitigated | Alternating cross-group closure with 80-component refresh produces another certified improvement |
| [M336-075](M336-075-hierarchical-bottom0-lns-closure.md) | Critical | Open | Every K1024 three-group bottom-0 LNS domain has a valid bound above score 1.0 |
| [M336-076](M336-076-candidate-guide-hint-coupling.md) | High | Mitigated | Candidate generation and solver hints are now independently controlled and rank-audited |
| [M336-077](M336-077-two-blocker-ejection-triplets.md) | Critical | Open | Leading two-blocker ejection triplets are full-site exact optima at the current placement |
| [M336-078](M336-078-complete-bottom0-k1024-search.md) | Critical | Open | Complete bottom-0 K1024 models are score-permitting but fail to improve within deterministic budgets |
| [M336-079](M336-079-full-site-four-component-closure.md) | Critical | Open | Directed four-component ejection closures are full-site exact optima at the current placement |
| [M336-080](M336-080-full-site-physical-group-closure.md) | Critical | Open | Major bottom-0 physical groups are exact optima over every available site |
| [M336-081](M336-081-exact-site-result-region-contract.md) | High | Resolved | Exact-site results now retain fail-closed region identity for scoped continuation |
| [M336-082](M336-082-zero-score-gate-semantics.md) | High | Resolved | Zero score thresholds disable only the score gate, not requested HPWL optimization |
| [M336-083](M336-083-rectangle-collision-quantization.md) | Critical | Resolved | Direct edge quantization removes a known-legal rectangle collision false positive |
| [M336-084](M336-084-full-site-cross-group-closure.md) | Critical | Open | Five full-site group pairs are exact optima; the sixth has a valid non-scoring domain bound |
| [M336-085](M336-085-hinted-capacity-continuation.md) | Critical | Resolved | Exact-legal hints establish a no-regression capacity floor and refresh assignment diagnostics |
| [M336-086](M336-086-incumbent-hpwl-ceiling.md) | High | Resolved | Explicit integer HPWL ceilings make finite continuation searches monotonic |
| [M336-087](M336-087-single-subgroup-k128-assignment-screen.md) | Critical | Open | Every single-subgroup K128 assignment domain has a valid bound above score 1.0 |
| [M336-088](M336-088-coupled-k256-assignment-search.md) | Critical | Open | Coupled K256 assignment domains admit score-level bounds but do not improve within budget |
| [M336-089](M336-089-coupled-k256-score-threshold-proof.md) | Critical | Open | Direct score gating proves four coupled K256 assignment domains infeasible |
| [M336-090](M336-090-coupled-k512-threshold-boundary.md) | Critical | Open | Coupled K512 score searches exhaust budget as UNKNOWN without an incumbent |
| [M336-091](M336-091-coupled-k512-strict-improvement.md) | Critical | Open | Coupled K512 searches cannot find even the nearest strict improvement within budget |
| [M336-092](M336-092-current-topology-seed-portfolio.md) | Critical | Open | Eight current-topology seeds converge to one incumbent while residual HPWL concentrates on page 7 |
| [M336-093](M336-093-exact-site-context-isolation.md) | High | Resolved | Exact-site probes now isolate generated context files by result output |
| [M336-094](M336-094-multi-plateau-candidate-guides.md) | Critical | Open | Balanced and quality-biased multi-plateau guides retain the same K256 incumbent |
| [M336-095](M336-095-page7-directed-escape-boundary.md) | Critical | Open | Page-7 K1024 search and an exact legal escape retain the current incumbent |
| [M336-096](M336-096-seeded-exact-escape-order.md) | High | Mitigated | Exact guided escape can replay seeded component-order portfolios without changing default behavior |
| [M336-097](M336-097-cpsat-incumbent-escape-hint-conflict.md) | Critical | Open | A single CP-SAT hint cannot preserve the current incumbent while encoding an escape topology |
| [M336-098](M336-098-per-move-escape-rise.md) | High | Mitigated | Guided escape can bound one HPWL rise independently from its total path envelope |
| [M336-099](M336-099-alternate-basin-support-closure.md) | High | Mitigated | A restricted movable set fixes nine components needed to reproduce a certified alternate basin |
| [M336-100](M336-100-guide-support-closure-audit.md) | High | Resolved | Exact probes now audit and optionally require candidate-guide support closure |
| [CUDA-001](CUDA-001-net-crossing-input-contract.md) | Critical | Mitigated | Invalid node/pin shape reached native net-crossing code |
| [REPRO-001](REPRO-001-placer-import-log-side-effect.md) | High | Resolved | Importing Placer truncated a tracked log in the caller's CWD |

Status values are `Open`, `Mitigated`, `Resolved`, and `Accepted Risk`. A
finding is resolved only after its acceptance criteria have direct test or
experiment evidence. If Issues are enabled later, migrate each document to a
GitHub issue and retain the resulting URL in this index.
