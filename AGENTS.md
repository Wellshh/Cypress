# AGENTS.md

## Repository guidance

Read `CLAUDE.md` before changing code. Cypress extends DREAMPlace; preserve the existing placement flow and keep all new behavior disabled by default.

### Build and test

- Preferred container root: `/Cypress`.
- Run placement with `python dreamplace/Placer.py <config.json>`.
- Run focused unit tests with `python unittest/ops/<op_name>_unittest.py`.
- New Python-only geometry or objective code must have CPU unit tests even when GPU execution is unavailable.
- Do not claim a GPU experiment passed unless the run log and output metrics are present.

### Change discipline

- Target the `experiment` branch. Do not modify `main`.
- Keep M336-specific data and orchestration under `docs/experiments/m336_anchor_keepin`, `scripts/m336`, `benchmark_configs`, and `artifacts/experiments/m336`.
- Core placement code must stay design-agnostic: no hard-coded M336 refdes, coordinates, region IDs, or paths.
- Gate every new algorithm path behind `anchor_keepin_flag`; when false, baseline behavior and numerical outputs must remain unchanged within test tolerance.
- Preserve anchors, fixed cells, layer assignments, and source orientations unless the experiment manifest explicitly says otherwise.
- Emit machine-readable metrics and fail loudly on invalid or missing geometry. Never silently fall back to a rectangular board or a different benchmark.

## M336 anchor/keep-in work

For tasks involving M336, irregular keep-in regions, anchor attraction, module clustering, or constrained PCB placement:

1. Explicitly invoke `$m336-anchor-keepin`.
2. Read `docs/experiments/m336_anchor_keepin/SPEC.md`.
3. Use the checked-in cluster and assignment manifests as the experiment contract.
4. Treat the supplied table as containing 25 modules and 125 clustered components; also report that the source prose says 27 modules.
5. Split mixed TOP/BOTTOM modules into side-specific subgroups while retaining the same anchor XY.
6. Keep the 25 anchors and 15 unclustered named components fixed for the first controlled experiment; the remaining 100 non-anchor members are movable.
7. Produce an ablation report, not just a placement image.
