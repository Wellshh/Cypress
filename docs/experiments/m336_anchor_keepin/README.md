# M336 Cypress Codex experiment package

This directory contains the implementation specification, Codex skill, prompt, and structured M336 experiment inputs for anchor-guided placement inside irregular keep-in regions.

## Files

```text
AGENTS.md
.agents/skills/m336-anchor-keepin/SKILL.md
.agents/skills/m336-anchor-keepin/agents/openai.yaml
docs/experiments/m336_anchor_keepin/
  SPEC.md
  CODEX_PROMPT.md
  README.md
  data/
    m336_clusters.json
    m336_assignment_seed.json
    m336_geometry_manifest.json
  config/
    m336_anchor_keepin.example.json
```

## Before launching Codex

Place the supplied large geometry file at:

```text
artifacts/experiments/m336/pcb_geometry_keepin.json
```

Verify:

```text
sha256 a7c2c788a7df386db9f94df76bfe64a21d49f21beacb0e233ebedac75cc4ad8d
```

Do not rename or substitute another benchmark.

## Launch

1. Select repository `Wellshh/Cypress`.
2. Select branch `experiment`.
3. Select `5.6 Sol` and `Extra High` reasoning.
4. Paste the prompt in `CODEX_PROMPT.md`.
5. The prompt explicitly invokes `$m336-anchor-keepin`; the skill is located in the repository-standard `.agents/skills` directory.

## Important input warning

The supplied clustering prose says there are 27 modules, while the supplied table contains 25 modules. The 25 parsed rows contain exactly 125 clustered components. The experiment intentionally preserves this warning and uses the parsed table as the source of truth.

## Scope of the first experiment

- 25 anchors fixed;
- 15 unclustered components fixed;
- 100 non-anchor members movable;
- six mixed-side modules split by side;
- TOP has one keep-in region;
- BOTTOM has three keep-in regions;
- rotation and fillers disabled;
- E0–E4 ablation matrix.

The provisional assignment is a seed, not a proof of feasibility. Codex must validate exact per-component feasible domains and repair or reject invalid assignments before running placement.
