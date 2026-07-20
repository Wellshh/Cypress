# M336-132: Exact-Site Results Misresolve Relative Dependency Paths

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `4a58b3c`

## Symptom

The M336-131 all-fixed K1 run was launched from the repository root with a
repository-relative `M336_ASSIGNMENT_JSON` and an output under `/tmp`. The solve
succeeded, but `exact_site_checkpoint.py` later failed before export:

```text
FileNotFoundError: checkpoint dependencies are missing:
  /data/root/tmp/experiments/m336/checkpoints/M336-118/assignment.json
```

Passing `--assignment` explicitly allowed a safe export, but silently requiring
that override would make formal results non-portable and easy to mis-replay.

## Root Cause

`probe_exact_site_cpsat.py` opened environment paths relative to its current
working directory and serialized the same relative text into the result. The
checkpoint contract correctly interprets relative metadata from the directory
of the declaring result. A repository-relative path that worked during a run
therefore changed meaning after the result was written to `/tmp`.

The same defect affected source, primary/additional guides, assignment, solver
hint, diversity reference, excluded-site inputs, output placement, and progress
paths. Textually different no-good paths could also resolve to the same file
without triggering duplicate validation.

## Fix

All external exact-site paths now pass through `_resolved_path`, which expands
the user path and resolves it against the launch working directory before any
I/O or metadata serialization. Comma-separated excluded-site paths are
canonicalized before uniqueness checks. Actual file locations are unchanged;
only ambiguous metadata is removed. The solver model, candidate ordering,
objective, and default feature gates are unaffected.

## Validation

- Python compilation succeeds for the probe and tests.
- The focused M336 suite passes 75/75 tests, including canonical metadata and
  declaration-relative replay assertions.
- A real all-fixed K1 run used only repository-relative source, guide, hint,
  and assignment environment values while writing its result to `/tmp`.
- The run returned `OPTIMAL`, HPWL `15649.948866405257`, 100/100 containment,
  zero keep-in violations, zero overlaps, and complete objective replay.
- Every serialized source/guide/hint/assignment/placement path is absolute.
- `exact_site_checkpoint.py` exported that result without any path override.

The K1 result, exported certificate, and export manifest SHA-256 values are:

- `a9222bd8e9810a3d09a0eac5fd221968f2cf7acc465b93f661e545c08173b948`;
- `c179765fdf36eab0162e82694a3529fb4595f3d8b7fc47755b1054820740a854`;
- `79f54684426b12c6b296658d3f01fafaa5bc1ac63b8400342e60053b84ce85a5`.

Future exact-site results may still be exported with explicit dependency
overrides, but correctness no longer depends on them when relative environment
paths were used at launch.
