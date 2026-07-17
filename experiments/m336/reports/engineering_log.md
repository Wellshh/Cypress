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

## Planned Integration

1. Add pure-Python geometry, alignment, assignment, projection, and validation
   modules under `dreamplace/constraints/`.
2. Add a PyTorch anchor-loss operator under
   `dreamplace/ops/anchor_keepin/` and focused CPU unit tests.
3. Add default-off parameters and thin integration hooks without changing the
   feature-off execution path.
4. Run the manifest, new unit tests, existing reproducibility tests, and the
   smallest available placement smoke test before attempting M336 ablations.
