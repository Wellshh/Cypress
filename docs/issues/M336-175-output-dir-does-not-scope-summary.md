# M336-175: Output Directory Does Not Scope Matrix Summary

**Severity:** High
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `0d2cae5`

## Problem

`run_matrix.py --output-dir <run-root>` writes every per-arm placement and
constraint artifact below `<run-root>`, but it does not place `summary.json` or
`REPORT.md` there. Unless the caller separately supplies both
`--summary-path` and `--report-path`, the non-sweep path always writes to:

```text
results/m336/summary.json
results/m336/REPORT.md
```

Those mutable global files are silently overwritten by the next matrix run.
An output root can therefore look complete while lacking its evidence index,
and a summary found at the global path may describe a different run.

## Evidence

The post-M336-174 D1 command supplied:

```text
--output-dir results/m336/native-cypress/
  m336-174-representative-d1-warm-10-scale1
```

It did not supply the two summary flags. The process completed both E2 and E3
arms, then printed that it wrote the global paths. The requested output root
contained all per-arm artifacts but neither top-level file. Source lines
`3004-3005` select fixed repository defaults independently of `args.output_dir`.

The generated global summary was positively tied to this run before archival:

- git SHA: `0d2cae5d2994e3a982214deed0a84e4f1aec317c`;
- experiments/seeds/iterations: `E2 E3`, `1000`, `10`;
- both run commands point into the requested M336-174 output root;
- source/install mismatches: none;
- summary SHA-256:
  `2d61a48d8284f126e43832dd09ed58dceaf2c55726255203ff74ef8bcac646e4`;
- report SHA-256:
  `88110aded627482cd02677ae4e771b4f5754989833a9a60465a19a3a41ee20f6`.

Both files were copied byte-for-byte into the requested output root. Source and
destination hashes match. No placement arm was rerun and no metric was edited.

## Impact

- A later run can destroy the only top-level index for earlier ignored results.
- A copied or archived output directory is not self-describing by default.
- Reviewers can accidentally pair one run's arm artifacts with another run's
  global summary.
- Reproduction commands emitted by the summary repeat `--output-dir` but do not
  add the missing summary/report paths, so the unsafe behavior reproduces.

This does not invalidate the M336-174 D1 metrics because their identity was
checked before another matrix run and the files were archived byte-identically.
It is nevertheless a durable evidence-chain defect.

## Required Remediation

1. When neither explicit path is supplied, derive both files from
   `args.output_dir`.
2. Keep explicit `--summary-path` and `--report-path` overrides authoritative.
3. Fail closed if either resolved output escapes the intended run root unless
   the caller explicitly requested that external path.
4. Include both resolved paths in the summary and reproduction command.
5. Refuse to overwrite an existing summary/report unless an explicit overwrite
   option is provided and recorded.
6. Add tests for normal runs, weight sweeps, explicit overrides, existing-file
   rejection, and reproduction-command identity.

## Interim Contract

Until remediation is implemented and tested, every promoted M336 matrix command
must include:

```text
--summary-path <output-dir>/summary.json
--report-path <output-dir>/REPORT.md
```

The single authorized M336-174 D2 replay must use new paths, check that neither
exists before launch, and hash both files before any later experiment.

## Acceptance Criteria

- A run given only `--output-dir X` atomically creates `X/summary.json` and
  `X/REPORT.md` without modifying the global defaults.
- Re-running against existing evidence fails closed by default.
- The emitted reproduction command regenerates the same path contract.
- Unit tests cover default, explicit, sweep, and collision cases.
- One bounded smoke demonstrates a self-contained run root with matching run
  IDs, git SHA, input hashes, and source/install hashes.
