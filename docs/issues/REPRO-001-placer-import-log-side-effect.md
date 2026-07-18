# REPRO-001: Importing Placer Truncated Caller Files

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `b1f98f5`

## Problem

`dreamplace.Placer` configured a `FileHandler("DREAMPlace.log", mode="w")` at
module import. Unit tests and tuning workers therefore created or truncated a
file in whichever directory happened to be current, before any placement ran.
In this repository, the side effect repeatedly replaced the tracked root log
while otherwise successful tests were running.

## Impact

- A pure import mutated repository state and changed provenance hashes.
- Concurrent workers could target the same relative log path before installing
  their per-replicate handlers.
- Failed setup or help invocations could destroy the prior run's evidence.

## Remediation

Logging setup now lives in `configure_cli_logging()` and is called only by the
CLI entrypoint after argument/help handling. Programmatic users inherit or
install their own handler; `AutoDMPWorker` already creates one per replicate.
The CLI retains the historical current-directory `DREAMPlace.log` behavior.

## Acceptance Criteria

- An isolated `import dreamplace.Placer` creates no files.
- CLI placement still writes and copies `DREAMPlace.log` to its result folder.
- Tuning replicates continue to use distinct `AutoDMP-*.log` files.
- Running focused reproducibility tests leaves the git worktree unchanged.
