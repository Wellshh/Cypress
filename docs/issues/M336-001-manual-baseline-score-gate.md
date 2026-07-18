# M336-001: Manual Baseline Quality Gate Is Not Met

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-17
**Affected commit:** `d9e7674`

## Problem

The initial M336 report compared E4 with a generated/random E0 placement, not
the manually placed root `pcb_geometry.json`. The runner now imports and scores
the manual board, but the first legal warm-start E4 remains substantially worse
than that reference.

## Evidence

- Manual input SHA-256:
  `af2f270e520104a0cafbddd7c36ef942a1086fe5e995fd60d7dae705336c6b98`.
- Keep-in input SHA-256:
  `a7c2c788a7df386db9f94df76bfe64a21d49f21beacb0e233ebedac75cc4ad8d`.
- Both inputs contain the same 140 named components, 76 nets, and 378 pins.
  Side, rotation, and local pin offsets match for all named components; 73
  component positions differ.
- Direct absolute-pin HPWL is `751.8613 mm` for the manual input and
  `1367.7118 mm` for the keep-in source placement.
- Fail-closed compatibility proves identical refdes, side, orientation,
  footprint, pin, and net topology. It rejects any non-placement mismatch.
- Same-operator manual scores at `0.05 mm/site` are HPWL `14627.84765625`
  (`731.3924 mm`) and RSMT `15950.0654296875` (`797.5033 mm`).
- Exact validation finds only `25/100` constrained components contained, `75`
  keep-in violations (`28.2565 mm2`), and `5` overlaps (`0.6160 mm2`). The
  manual board is therefore a quality reference, not a legal fallback.
- A one-iteration E4 warm-start is exact legal but scores HPWL `24823.8262` and
  RSMT `26321.7852`. Its normalized score is `0.5975` versus baseline `1.0`,
  with HPWL/RSMT regressions of `69.70%/65.03%`.
- Earlier matrix values used incorrect BOTTOM pin offsets and are not valid
  final evidence; see M336-004.

## Impact

An acceptance check can pass against an inferior placement. Tuning also starts
from an avoidably poor state, and mixed unit paths can hide regressions.

## Remediation

1. Generate a compatible `m336.baseline.pl` after fail-closed identity checks
   for refdes, side, orientation, footprint, pins, and nets.
2. Evaluate baseline and candidates through the same PlaceDB, PinPos, HPWL,
   RSMT, exact source-polygon containment, and exact overlap paths.
3. Warm-start ablations from the manual baseline while restoring source anchors
   and the 15 explicitly fixed unclustered obstacles.
4. Add a design-agnostic, feature-gated reference-quality guard. If an
   exact-legal candidate regresses a required metric, retain the reference.
5. Record hashes, units, raw metrics, normalized comparisons, and fallback
   decisions in `summary.json` and `REPORT.md`.

Items 1-3 and machine-readable scoring are implemented. Candidate quality and
the final three-seed gate remain open.

## Acceptance Criteria

- Import is deterministic and rejects every identity mismatch.
- Baseline legality and all metric units are explicit.
- Final E4 has zero keep-in violations and zero constrained overlaps.
- Final E4 HPWL and RSMT are each no worse than the accepted manual reference.
- Three seeds have identical input hashes and machine-readable comparisons.
- Feature-off placement is unchanged.
