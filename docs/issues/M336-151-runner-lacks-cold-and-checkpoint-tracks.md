# M336-151: Runner Lacks Cold and Checkpoint Tracks

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

`run_matrix.py` passes `args.baseline_pl` as `initial_placement_file` for every
E0-E4 run. That file is generated from the artificial `pcb_geometry.json`
baseline. It is neither the source/runtime placement nor the M336-118 portable
checkpoint. Its presence also disables random cold initialization and selects
the old `current` packing preference.

The existing matrix therefore has one implicit artificial-baseline track, even
though reports require separate cold/source and M336-118 checkpoint-warm runs.

## Impact

- Cold preprocessing and initialization are not measured.
- M336-118 preservation and warm-cache runtime are untested.
- E4/E0 runtime ratios can mix different initialization semantics.
- Reproduction commands do not identify an initialization track or warm source.

## Remediation

Add explicit `cold_source` and `checkpoint_warm_start` tracks. Cold runs begin
from the source PlaceDB contract; warm runs require and hash
`experiments/m336/checkpoints/M336-118/placement.pl`. Keep the manual baseline
only as an endpoint/scoring reference. Encode track and initialization mode in
run IDs, configs, summaries, and reproduction commands.

## Acceptance Criteria

- Every run declares exactly one initialization track.
- Warm mode fails if the checkpoint is absent or identity-invalid.
- Cold mode does not load the manual baseline as an initial placement.
- Runtime reports separate preprocessing, cache, initialization, optimization,
  validation, repair, serialization, and scoring.
- Final E0-E4 comparisons use equal track, device, seed, and iteration budget.

## Resolution

The runner now requires an explicit `cold_source` or
`checkpoint_warm_start` track and rejects inconsistent placement arguments.
Track identity is included in configs, run IDs, summaries, and reproduction
commands. Seed-1000 10-step E0-E4 matrices completed on both tracks with the
same GPU, assignment, endpoint policy, grid, target density, and iteration
budget. Every result separates preprocessing, cache load/build, initialization,
GPU optimization, exact validation, bounded repair, serialization, and native
scoring time.
