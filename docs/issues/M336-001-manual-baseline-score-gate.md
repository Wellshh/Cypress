# M336-001: Manual Baseline Is Not the Score Reference

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-17
**Affected commit:** `d9e7674`

## Problem

The initial M336 report compares E4 with a generated/random E0 placement, not
the manually placed root `pcb_geometry.json`. It can therefore report an HPWL
improvement while remaining substantially worse than the required baseline.

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
- The 5-iteration E4 mean is `23524.1796875` Cypress units, or `1176.2090 mm`
  at `0.05 mm/site`: approximately 56.44% worse than the manual HPWL.
- The reported E4-versus-E0 HPWL change of `-16.38%` therefore uses the wrong
  reference. RSMT and exact baseline legality have not yet been measured.

## Impact

An acceptance check can pass against an inferior placement. Tuning also starts
from an avoidably poor state, and mixed unit paths can hide regressions.

## Remediation

1. Generate a compatible `m336.baseline.pl` after fail-closed identity checks
   for refdes, side, orientation, footprint, pins, and nets.
2. Evaluate baseline and candidates through the same PlaceDB, PinPos, HPWL,
   RSMT, exact source-polygon containment, and exact overlap paths.
3. Warm-start ablations from the manual baseline where the matrix permits.
4. Add a design-agnostic, feature-gated reference-quality guard. If an
   exact-legal candidate regresses a required metric, retain the reference.
5. Record hashes, units, raw metrics, normalized comparisons, and fallback
   decisions in `summary.json` and `REPORT.md`.

## Acceptance Criteria

- Import is deterministic and rejects every identity mismatch.
- Baseline legality and all metric units are explicit.
- Final E4 has zero keep-in violations and zero constrained overlaps.
- Final E4 HPWL and RSMT are each no worse than the accepted manual reference.
- Three seeds have identical input hashes and machine-readable comparisons.
- Feature-off placement is unchanged.
