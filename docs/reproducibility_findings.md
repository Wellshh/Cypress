# Reproducibility Remediation Findings

This document tracks findings discovered while making CUDA placement and tuning
results reproducible. Status reflects source-level remediation in this branch;
GPU validation remains required on a CUDA-capable host.

## F-01: Trial RNG State Leaked Across Jobs

**Severity:** Critical  
**Status:** Remediated, pending GPU validation

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
**Status:** Remediated, pending GPU validation

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

## Validation Plan

1. Run CPU operator and optimizer unit tests.
2. Repeat net-crossing CUDA forward/backward at least 50 times and require exact
   equality in deterministic mode.
3. Compare one-worker and multi-worker tuning with identical `study_seed`.
4. Record commit, CUDA/PyTorch versions, GPU model, seeds, and full parameters
   with every promoted configuration.

## Validation Evidence

As of 2026-07-17, both `net_crossing_cpp` and `net_crossing_cuda` compile with
CUDA 12.4 and GCC 12. The CPU net-crossing golden-value/gradient test passes.
Six CPU reproducibility tests cover RNG reset, schedule-independent seed panels,
same-seed ConfigSpace sampling, bounded BB steps, finite Nesterov progress, and
non-finite rollback. Python compilation and shell syntax checks pass.

GPU execution, multi-worker Pyro integration, and end-to-end repeated placement
remain unverified because this environment cannot initialize the NVIDIA driver.
Deterministic net crossing currently transfers work to a serial CPU reference;
measure this cost before large searches and replace it with a fixed-order GPU
reduction if it is prohibitive.
