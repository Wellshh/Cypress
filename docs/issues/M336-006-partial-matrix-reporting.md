# M336-006: Partial Matrix Report Lost the Summary

**Severity:** Medium
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `b1f98f5` plus uncommitted baseline integration

## Problem

An E4-only smoke had a manual-baseline comparison but no E0 runtime comparison.
`render_report()` unconditionally read `runtime_at_most_2x` from the acceptance
map and raised `KeyError` after the 178-second placement completed. The runner
also rendered Markdown before writing `summary.json`, so structured aggregate
evidence was lost even though `run-result.json` existed.

## Remediation and Evidence

Runtime output is now conditional on an actual `e4_vs_e0` comparison. The main
path writes `summary.json` before rendering the report. Re-running the same E4
command with `--resume` completed and wrote both requested artifacts.

## Acceptance Criteria

- Any non-empty subset of E0-E4 can produce a report.
- Missing comparisons render as absent/not-run rather than raising.
- A Markdown failure cannot prevent the JSON summary from being persisted.
