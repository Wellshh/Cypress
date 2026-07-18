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
| [CUDA-001](CUDA-001-net-crossing-input-contract.md) | Critical | Mitigated | Invalid node/pin shape reached native net-crossing code |
| [REPRO-001](REPRO-001-placer-import-log-side-effect.md) | High | Resolved | Importing Placer truncated a tracked log in the caller's CWD |

Status values are `Open`, `Mitigated`, `Resolved`, and `Accepted Risk`. A
finding is resolved only after its acceptance criteria have direct test or
experiment evidence. If Issues are enabled later, migrate each document to a
GitHub issue and retain the resulting URL in this index.
