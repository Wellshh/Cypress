# Cypress experiment-branch instructions

## Scope

This repository task targets `Wellshh/Cypress` on the `experiment` branch and the M336 anchor-guided irregular keep-in placement experiment under `experiments/m336/`.

Read these before editing:

1. `CLAUDE.md`
2. `BUILD.md`
3. `experiments/m336/SPEC.md`
4. `.agents/skills/m336-anchor-keepin-experiment/SKILL.md`

## Git safety

- Confirm the current branch is `experiment`.
- Preserve all existing experiment-branch build and benchmark changes.
- Inspect before editing; do not overwrite unrelated work.
- Do not create or switch branches unless the user explicitly asks.
- Do not push to remotes unless the user explicitly asks.
- Do not commit generated logs, large result images, caches, build trees, or binary artifacts.
- Report the starting and ending commit SHA.

## Engineering rules

- New M336 behavior must be feature-gated and default off.
- Do not hardcode absolute paths or M336 refdes in Cypress core modules.
- Keep board-specific inputs and scripts under `experiments/m336/`.
- Never substitute the board bounding rectangle for an unavailable keep-in polygon.
- Never invent missing cluster modules or refdes.
- Keep TOP and BOTTOM constraints separate. Split mixed-side clusters into side-specific subgroups.
- Phase 1 keeps rotation disabled and freezes anchor nodes.
- Use exact source polygons for final legality; rectangle/raster approximations are optimization aids only.
- Preserve existing behavior when anchor/keepin flags are disabled.
- Prefer a clear Python/PyTorch reference implementation before adding CUDA.
- Avoid new production dependencies unless they are necessary and documented.

## Required validation

Run the lightest applicable checks after each phase:

```bash
python experiments/m336/scripts/validate_manifest.py
```

Then run new unit tests directly, following the repository’s existing unittest style. Run an existing small-board smoke test when the build/environment allows it.

If GPU/native builds are unavailable, still run pure-Python geometry, manifest, loss, projection, and validation tests. Clearly report blocked commands; never fabricate results.

## Output expectations

- Emit resolved configs and machine-readable metrics.
- Include git SHA, seed, input hashes, actual commands, and runtime in reports.
- Keep a concise engineering log in `experiments/m336/reports/`.
- Finish with changed files, tests, actual M336 results, known limitations, and review hotspots.
