# M336-119: Exact-Site Checkpoints Were Not Durable Or Portable

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `480328c`

## Problem

Promoted exact-site results, placements, assignments, and quality guides were
stored under `/tmp` or ignored `results/` directories. The issue ledger kept
their SHA-256 values, but a fresh clone could neither retrieve those bytes nor
continue from the certified incumbent. Copying a certificate alone was also
insufficient because `assignment_json` and `placement` were interpreted
relative to the caller's working directory or remained absolute `/tmp` paths.

This made the documented optimization chain auditable only while one machine's
temporary files survived, contradicting the reproducibility objective.

## Remediation

`exact_site_checkpoint.py` now validates that an export source is feasible,
uses the exact collision model, needs no further certification, passes HPWL
objective replay, and has zero exact legality violations. It atomically exports
an immutable directory containing:

- the original certificate bytes;
- a portable certificate with relative dependency paths;
- the exact placement and assignment;
- an optional candidate quality guide;
- a manifest with SHA-256 for every file and canonical selected sites.

The exporter refuses to overwrite an existing checkpoint. Exact-site descent
and native scoring now resolve relative metadata against the declaring result
file, not the process working directory. Descent outputs persist the resolved
assignment path so subsequent results do not inherit a broken relative path.

## Verification

All 65 M336 unit tests pass, including source-relative path and self-contained
export coverage. The real M336-118 certificate was exported to
`experiments/m336/checkpoints/M336-118/` and replayed while the process working
directory was `/tmp`. The replay resolved the repository checkpoint assignment,
enumerated 532,193 sites, stopped at `one_optimum`, reproduced HPWL
`15634.450477332834`, and retained 100/100 containment with zero overlaps.

The bundled and replayed placement SHA-256 values both equal
`32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`.
The checkpoint manifest SHA-256 is
`485e86b0356db0614ce937040b2b7b71de4d5942d51ddb470218cd7249215c26`.

## Operating Rule

Every future promoted incumbent must receive a new issue-numbered checkpoint
directory. Do not cite a temporary result as recoverable evidence, and do not
overwrite a prior checkpoint when the incumbent changes.
