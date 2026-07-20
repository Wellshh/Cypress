# M336-180: HPWL Improvement Masks E2 FLUTE Regression

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `f56fb09`

## Problem

The M336-178 scale-1 D1 produces a lower E2 HPWL than the qualifying M336-174
trajectory, but a higher native FLUTE RSMT. The D1 contract requires neither
metric to regress, so the conjunction fails even though protected closure is
legal, monotonic, and retry-free.

| E2 metric | M336-174 | M336-178 | Delta | Result |
| --- | ---: | ---: | ---: | :---: |
| HPWL | `15633.109790` | `15632.829467` | `-0.280323` | pass |
| FLUTE RSMT | `17328.300` | `17328.847` | `+0.547` | **fail** |
| Normalized score | `0.9280174763` | `0.9280109609` | `-0.0000065154` | **fail** |

E3 does not share the failure: HPWL improves by `0.106598`, RSMT improves by
`0.439`, and normalized score rises to `0.9280376473`. Both arms remain far
below the manual normalized score of `1.0`.

The source artifact and immutable evidence hashes are:

```text
results/m336/native-cypress/
  m336-178-protected-authority-d1-warm-10-scale1/
summary SHA-256
ce275a8b3a315e04cfb90936c2a373be35dd505ea1252eabd8931cbb6ca933c2
report SHA-256
4c2797a81724660c5343f31409531db21f8dc9ea8184730f33db42fcc10df53c
E2 serialized placement SHA-256
9dc7e3b551a646c974d43a0e3a659f63ce621d4f4b3b39f843d282a6a1b9e272
```

## Native Per-Net Attribution

An offline diagnostic loaded the two exact serialized float64 placements
through the installed `PlaceDB` and CPU `RmstWL` operator with the same FLUTE
LUT and ignore-degree contract. Per-net sums reproduce both committed aggregate
HPWL and RSMT exactly. This is attribution of existing artifacts, not a new
Cypress effect run.

E2 changes 17 per-net RSMT values. The main deltas are:

| Net | Degree | HPWL delta | RSMT delta |
| --- | ---: | ---: | ---: |
| `GND` | 84 | `0.000000` | **`+1.127`** |
| `N31799919` | 2 | `+0.081940` | `+0.082` |
| `N31801164` | 4 | `+0.000008` | `+0.039` |
| `VDD_VIBR` | 4 | `0.000000` | `-0.245` |
| `SIM1_DATA1` | 3 | `-0.088898` | `-0.089` |
| `USB_CON_THERM` | 3 | `-0.088867` | `-0.089` |
| `SIM1_RST1` | 3 | `-0.088821` | `-0.088` |

`GND` alone regresses by more than the total after improvements on other nets.
Its bounding-box HPWL is unchanged while its 84-pin Steiner result changes,
which isolates a discrete multi-pin FLUTE topology change. Thirty-three GND
components differ between the two placements; the largest displacement is
`0.245850` Cypress units (`0.012294 mm`), at `C502`.

## Root Cause

Cypress optimizes a differentiable wirelength surrogate plus density and
constraint losses. The protected authority selector minimizes new corrected
IDs and correction energy. Neither objective observes native FLUTE topology.
M336-178 preserves more full-LR native motion than M336-177 and lowers final
HPWL, but internal motion on a high-degree net can cross a discrete FLUTE
topology boundary without changing that net's bounding box.

This is not evidence of nondeterminism, a scorer mismatch, or coordinate drift:
the two comparisons use identical inputs and scoring code; each serialized
input/replay hash matches with zero coordinate error; and the per-net RSMT sum
equals the recorded native score.

## Required Design Before Code

1. Trace the E2 authority choices and accepted node motions that alter `GND`,
   beginning with `C502`, without rerunning optimization.
2. Define a bounded, default-off Cypress-native mechanism that preserves the
   optimizer proposal and exact legality while preventing known multi-pin RSMT
   topology regressions. A final score check alone is not a mechanism and may
   only fail closed; it cannot return M336-174 or M336-118 as fallback output.
3. State explicitly whether the mechanism is a differentiable objective signal
   or a deterministic hard-projection tie-break. It must not be CP-SAT, one-opt,
   pair scan, checkpoint substitution, or post-failure exact repair.
4. If a proxy is proposed, validate its direction on the recorded E2 `GND`
   transition and on synthetic multi-pin topology changes before any effect run.
5. Account for its complete GPU/CPU cost under M336-179's runtime gate. Native
   FLUTE calls inside every authority state are not acceptable without a proven
   bound and runtime budget.
6. Preserve HPWL no-regression, E3 anchor direction, exact legality, protected
   closure, and deterministic serialization. Do not trade one conjunct for
   another.

## Rejected Alternatives

- Relaxing the RSMT gate would hide a real normalized-score regression.
- Optimizing HPWL harder does not control the demonstrated zero-HPWL-delta GND
  topology change.
- Seed, LR, anchor, collision, or cap ladders are not causal experiments for a
  deterministic final-net topology difference.
- Scoring M336-118 or M336-174 after failure and returning it would be the
  prohibited checkpoint fallback path.
- CP-SAT or local exact-site cleanup is not Cypress algorithm evidence.

## Acceptance Criteria

- The selected mechanism has a reviewed native-Cypress contract and focused
  topology-direction tests before implementation.
- A single combined D1 passes E2 and E3 HPWL/RSMT no-regression gates against
  M336-174, including E2 `RSMT <= 17328.300`.
- Both serialized placements remain 100/100 contained with zero overlap and
  coordinate drift, and M336-179 runtime gates pass.
- No D2, D3, E4, fallback, exact-site optimization, or parameter ladder runs
  before that D1 is committed, pushed, and pulled.
