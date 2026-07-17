# M336 experiment workspace

See:

- `SPEC.md`
- `CODEX_GOAL.md`
- `CODEX_PROMPT.md`

Inputs are immutable source material. Generated configs, plots, placements, and reports should go to a gitignored or selectively committed results directory. Do not modify the source geometry to make a run pass.

The seed assignment is a proposal based only on same-side distance from each physical anchor to the source keep-in polygon. It must be validated against per-component feasible domains and region capacity before use.
