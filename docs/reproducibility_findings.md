# Reproducibility Remediation Findings

This document tracks findings discovered while making CUDA placement and tuning
results reproducible. Status reflects source-level remediation and validation on
the current `experiment` branch. Open follow-up work is tracked in
[`docs/issues/`](issues/README.md).

## F-01: Trial RNG State Leaked Across Jobs

**Severity:** Critical
**Status:** Remediated; focused CPU/GPU tests pass

`PlacementEngine` was seeded only when a worker was created. Subsequent jobs
therefore inherited NumPy and PyTorch RNG state from earlier jobs. Placement now
reseeds at the start of every `run()`. Tuning workers evaluate candidates with a
fixed seed panel derived from `study_seed` and the replicate index. Each
replicate uses a fresh engine and a budget/seed-specific result directory.
Rotation logits no longer consume random values when rotation is disabled.

## F-02: Single Noisy Evaluation Selected Lucky Configurations

**Severity:** Critical
**Status:** Remediated in BOHB worker and launchers

BOHB budget now represents the number of repeated evaluations. Scalar results
use `median + 0.25 * IQR`; failed runs receive the configured bad-run metrics.
All replicate results, seeds, dispersion, and failure rate are returned as run
metadata. Standalone quick/parallel tuners now evaluate the same three-seed
panel and rank median HPWL with an IQR and failure-rate penalty.

The search space, NumPy, Python, PyTorch, BOHB/MOBOHB and placement replicates
now share an explicit `study_seed`. BOHB budgets range from one to three fixed
replicates by default.

ConfigSpace hyperparameters are deduplicated without an unordered `set`, so a
fixed seed produces the same declaration and sampling order. Each replicate
writes commit, Python/NumPy/PyTorch/CUDA versions, GPU identity, budget, and seed
to `run_metadata.json` beside its full `parameters.json`.

ConfigSpace 1.2 treats the first positional `ConfigurationSpace` argument as its
name, not its seed. Construction now uses the explicit `seed=` keyword; a
same-seed sampling regression test guards this API detail.

Candidate analysis now flattens aggregate metrics instead of treating replicate
metadata as scalar columns. KMeans and train/test splitting use fixed random
states, and single-objective candidates are ranked by the recorded robust cost.

## F-03: Net-Crossing CUDA Races

**Severity:** Critical
**Status:** Remediated; focused GPU tests pass

Multiple pair threads updated the same forward accumulator, while gradients used
floating-point atomics. The fast CUDA path now assigns one thread to each net's
forward accumulator. Deterministic mode uses the serial CPU reference path to
avoid unordered gradient atomics, then returns the score and gradient to the
original device. This is intentionally slower. The test now uses four nets and
checks 20 repeated GPU forward/backward evaluations for exact equality.

CPU and CUDA implementations now share side filtering and skip near-parallel
segments instead of perturbing only selected denominators with epsilon.

## F-04: Nesterov Step Can Commit Non-Finite State

**Severity:** High
**Status:** Remediated, pending placement validation

Barzilai-Borwein norm ratios had no denominator floor or finite-value checks.
Step estimates now use float64 norms, fall back on tiny/invalid denominators,
and are bounded to a 10x relative change. Non-finite candidates are backtracked;
if no finite candidate is found, the trial raises before optimizer state is
committed. Initial learning-rate Armijo search now has a finite retry bound.

## F-05: Result Delivery and Launcher Failures Are Hidden

**Severity:** High
**Status:** Remediated, pending distributed integration test

Pyro result registration was one-way, so workers could not confirm acceptance.
Registration now returns an acknowledgement, tolerates duplicate completed job
IDs, and retries three times. Jobs are entered into `running_jobs` before remote
dispatch to close a fast-completion race. The shell launcher now checks the
saved child exit code and terminates remaining jobs when one fails.

## F-06: Optimizer-State Reset Mutated the Placement Tensor

**Severity:** Critical
**Status:** Remediated; regression test passes

The recursive optimizer-state reset traversed each parameter group's `params`
entry and zeroed the actual placement parameter, not only momentum/history
buffers. This silently destroyed the projected initialization and made outcomes
depend on when a reset occurred. The reset now skips `params` and tensor objects
identical to optimizer parameters. A focused test asserts that state buffers are
cleared while node coordinates remain unchanged.

## F-07: Native Net-Crossing Trusted Inconsistent Pin Metadata

**Severity:** Critical
**Status:** Mitigated; full sanitizer coverage remains open

The wrapper could pass a node-coordinate vector to native code that indexed it
as a pin-coordinate vector. Python and C++/CUDA now validate shapes, dtypes,
devices, CSR structure, pin coverage, and pin IDs before execution; the wrapper
always applies PinPos first. Detailed evidence and remaining criteria are in
[`CUDA-001`](issues/CUDA-001-net-crossing-input-contract.md).

## F-08: M336 Baseline Used Inconsistent Coordinate Paths

**Severity:** Critical
**Status:** Mitigated; baseline round-trip tests pass

BOTTOM pin offsets were written in board orientation and then mirrored again by
PlaceIO for `FN` nodes. The old M336 matrix therefore used incorrect pin
coordinates. The generator now pre-flips BOTTOM x offsets, and baseline import
validates all 378 connected source pins before native site quantization.
Baseline scoring uses the float placement path because `evaluate_pl=1` silently
rounds node positions through C++ integer storage. Details are in
[`M336-004`](issues/M336-004-bookshelf-coordinate-fidelity.md).

## F-09: Reported Fixed Obstacles Were Still Optimizer-Movable

**Severity:** High
**Status:** Remediated; integrated preflight evidence passes

Exact validation classified all 40 non-constrained components as fixed, while
only 25 anchors were actually frozen. The 15 unclustered components could move
during optimization, making initialization, optimization, and validation use
different obstacle semantics. Runtime config now explicitly lists those 15
refdes; the core validates they are physical, unclustered, and present before
restoring source coordinates and zeroing their gradients. Preflight reports the
two frozen sets separately as `25` anchors and `15` fixed obstacles.

## F-10: Report Rendering Could Erase Completed Experiment Evidence

**Severity:** Medium
**Status:** Remediated; E4-only resume path passes

The E4-only report indexed an E0/E4 runtime comparison that did not exist and
raised `KeyError`. Since Markdown was rendered before `summary.json` was
written, the completed run lacked an aggregate artifact. Runtime output is now
conditional, and JSON is persisted before report rendering. See
[`M336-006`](issues/M336-006-partial-matrix-reporting.md).

## F-11: Importing Placer Truncated a Relative Log File

**Severity:** High
**Status:** Remediated; isolated import test passes

`dreamplace.Placer` opened `DREAMPlace.log` in write mode at import time. Tests
and programmatic tuning could therefore mutate the caller's working directory
before a run started. CLI logging is now configured only in the CLI entrypoint;
tuning retains its existing per-replicate handlers. Detailed evidence is in
[`REPRO-001`](issues/REPRO-001-placer-import-log-side-effect.md).

## F-12: Region Assignment Made the Quality Gate Impossible

**Severity:** Critical
**Status:** Open; deterministic lower-bound diagnostic added

The final M336 subgroup assignment minimized anchor distance and seed changes,
but did not model connectivity. Under the corrected 40-node runtime freeze
state, its `0.1 mm` relaxed HPWL is `17996.2459` versus the manual baseline's
`14627.8477`, and its normalized score cannot exceed `0.847975`. A quality-aware
MILP improves the upper bound to `0.964781`, which is still impossible. At
`0.05 mm`, an interval relaxation reaches `1.039878`, but a shared-component
site model proves the selected assignment cannot meet score `1.0` even with
collisions disabled. A coupled search then rejects all 61 same-side assignment
options on the `0.05 mm` lattice, even after removing collision and capacity
constraints. See [`M336-007`](issues/M336-007-fixed-assignment-quality-bound.md),
[`M336-009`](issues/M336-009-runtime-fixed-endpoint-bound.md), and
[`M336-012`](issues/M336-012-global-discrete-quality-infeasibility.md).

## Validation Plan

1. Run CPU operator and optimizer unit tests.
2. Repeat net-crossing CUDA forward/backward at least 50 times and require exact
   equality in deterministic mode.
3. Compare one-worker and multi-worker tuning with identical `study_seed`.
4. Record commit, CUDA/PyTorch versions, GPU model, seeds, and full parameters
   with every promoted configuration.

## Validation Evidence

As of 2026-07-18, the environment can access an NVIDIA H100 with driver
550.54.14, CUDA 12.4, and PyTorch 2.5.1+cu124. Native build and installation
pass. The focused net-crossing suite passes 3/3 on GPU, including the CPU golden
result and 20 bitwise-equal deterministic GPU forward/backward repetitions.
Eight reproducibility tests pass for RNG reset, schedule-independent seed
panels, same-seed ConfigSpace sampling, bounded BB steps, finite Nesterov
progress, non-finite rollback, strict float initial-placement loading, and
side-effect-free Placer import. Ten manual-baseline tests and fifteen
anchor/keep-in tests also pass. The feature-off small placement smoke completes.

Multi-worker Pyro integration, a 50-repeat net-crossing run, sanitizer coverage,
and end-to-end repeated tuning remain pending. Deterministic net crossing still
transfers work to a serial CPU reference; measure this cost before large searches
and replace it with a fixed-order GPU reduction if it is prohibitive.
