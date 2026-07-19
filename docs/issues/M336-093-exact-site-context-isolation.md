# M336-093: Exact-Site Probes Shared a Writable Context Directory

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `5a64ee4`

## Problem

`probe_exact_site_cpsat.py` hard-coded every invocation's context output to
`/tmp/m336_exact_site_cpsat_context`. Context loading writes
`anchor_keepin.json`, `input_alignment.json`, and `preflight.json` before the
model is built. Parallel probes with different assignments, grids, or
clearances could therefore overwrite one another's configuration or expose a
partially written JSON file. This invalidates isolation required for parallel
seed and tuning experiments.

Identical concurrent configurations usually write identical content, so this
does not by itself invalidate the M336-092 seed portfolio. It is nevertheless
unsafe as a general experiment contract.

## Resolution

The default context directory is now derived from the complete output path:
`<M336_OUTPUT_JSON>.context`. Distinct outputs therefore receive distinct
writable context trees. `M336_CONTEXT_DIR` remains available as an explicit
override for controlled workflows, and every result records
`context_output_dir`.

The helper is deterministic and preserves relative override paths without
silently resolving them against a different directory.

## Verification

The M336 unit suite passes 57/57, including separate default paths for two
outputs and explicit override behavior. Python syntax compilation and
`git diff --check` pass.

Two probes were then launched concurrently without `M336_CONTEXT_DIR`:

| Output | Context directory | Status | Integer objective |
| --- | --- | --- | ---: |
| `m336_context_iso_a.json` | `m336_context_iso_a.json.context` | `OPTIMAL` | 15811065584 |
| `m336_context_iso_b.json` | `m336_context_iso_b.json.context` | `OPTIMAL` | 15811065584 |

Both context trees contain independent constraint reports. Both exact reports
pass objective replay, 100/100 containment, zero violations, and zero overlaps.
Their placement SHA-256 is
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`,
identical to the certified source. Result SHA-256 values are
`fc9f3ad0562de1005409af433a20ab7021f19c3074b64cacb331e65c73001525`
and `6d27c9010e0e2658df3522517ebeb0d94fbbf6ac1775b75d5854696903f6f483`.
