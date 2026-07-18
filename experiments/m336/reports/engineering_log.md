# M336 Engineering Log

## 2026-07-17: Baseline and Input Audit

- Branch: `experiment`
- Starting SHA: `0d5e3981f683bea7d7af9842a524ef9cb301ed16`
- Existing dirty worktree was recorded before M336 edits and is being preserved.
- Installed `.agents/skills/m336-anchor-keepin-experiment/` and
  `experiments/m336/` from the supplied package without modifying the existing
  root `AGENTS.md`.
- Explicitly invoked `$m336-anchor-keepin-experiment`.
- `python3.11 experiments/m336/scripts/validate_manifest.py`: PASS. The source
  declares 27 modules but enumerates 25; those rows still cover all 125 unique
  clustered members. No missing module or refdes will be invented.
- Skill validation passes with Python 3.12. Python 3.11 cannot run the validator
  because that interpreter does not provide PyYAML.

## Architecture Findings

- Cypress already separates TOP and BOTTOM density through `node_side_flag`,
  `top_nodes_idx`, and `btm_nodes_idx`; M336 assignments must use those existing
  side identities rather than infer side from region proximity.
- Existing fence regions are unions of axis-aligned boxes. They are unsuitable
  as the exact source of truth for the four irregular M336 line/arc polygons.
- `move_boundary` only clips nodes to the global placement rectangle. M336 needs
  an additional footprint-aware projection before objective evaluation and
  after every optimizer step.
- Existing legality checks consume rectangular fence data. Final M336 checks
  must use the source polygons and test full footprint containment plus same-side
  constrained/fixed and constrained/constrained overlap.
- Global placement initializes movable nodes near the board center and spreads
  fillers over the full floorplan. Constrained nodes need region-aware
  initialization; fillers must be excluded from narrow M336 regions.
- Anchor nodes are ordinary movable nodes today. The M336 path must restore
  their coordinates after each update and zero their gradients.
- No M336 benchmark files matching the 140 source refdes were found outside the
  supplied JSON assets. Full E0-E4 placement runs remain blocked until a matching
  Cypress input database or an approved deterministic importer is available.

## Implemented Integration

1. Added pure-Python geometry, alignment, assignment, projection, and exact
   validation modules under `dreamplace/constraints/`.
2. Added a PyTorch anchor-loss operator under
   `dreamplace/ops/anchor_keepin/`, default-off parameters, and feature-gated
   integration before objective evaluation and after optimizer updates.
3. Generated a 0.05 mm/site Bookshelf database, fitted geometry alignment with
   maximum residual `0.0332111 mm`, and resolved 31 side-specific subgroups.
4. Validated all 100 constrained non-anchor components in E4 with zero exact
   keep-in violations and zero overlaps after repair.

## 2026-07-17: Initial E0-E4 Matrix and Weight Sweep

The 5-iteration smoke matrix ran on GPU for seeds 1000, 1001, and 1002. E4
reached zero exact violations and overlaps, but E3 reduced mean anchor distance
by only 15.50% versus the required 25%, reduced p90 by 14.03% versus 15%, and
E4 runtime was 5.97x E0 versus the 2x limit. A 12-run anchor-weight sweep showed
that soft keep-in gradient norm was zero in every run and that scaling matched
anchor lambda by 8x barely changed physical anchor distance. See
`docs/issues/M336-002-soft-keepin-zero-gradient.md` and
`docs/issues/M336-003-acceptance-shortfalls.md`.

## 2026-07-17: Manual Baseline Discovery

The root `pcb_geometry.json` is a manual placement of the same 140 named
components and 76-net topology. Its direct absolute-pin HPWL is `751.8613 mm`,
while E4 is `1176.2090 mm` at the generated 0.05 mm/site scale. The previous
E4-versus-E0 comparison therefore used the wrong baseline and does not satisfy
the user quality gate. Exact baseline legality and same-operator HPWL/RSMT
evaluation are the next mandatory phase; see
`docs/issues/M336-001-manual-baseline-score-gate.md`.

## 2026-07-18: Repository Issue Fallback

Creating a GitHub issue through the API failed with HTTP 410 because Issues are
disabled for this fork. Detailed issues are maintained under `docs/issues/` and
pushed at every key milestone. Each subsequent milestone starts with a pull and
review of upstream edits or responses.
