# M336-152: Native Bookshelf Source Quantization

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

With `global_place_flag=1`, the native Bookshelf reader exposes integer-rounded
coordinates through `PlaceDB`, even though `results/m336/bookshelf/m336.pl`
contains the authoritative sub-millimeter source coordinates. The first N4
`cold_source` smoke did not load that float PL explicitly and compared all
runtime rows with a `0.001 mm` tolerance. It therefore failed before
`NonLinearPlace` with every physical component reported as a mismatch.

## Evidence

An independent source audit measured a maximum raw-PlaceDB versus float-PL
delta of exactly `0.5 mm`; examples include `J831` and `J822`. The failed smoke
used seed 1000, one E2 iteration, and stopped in
`AnchorKeepInContext.from_params()` before any optimizer evidence was emitted.

## Impact

- The attempted cold track was not float-preserving.
- Runtime `Q601` could silently inherit a rounded coordinate.
- Preserve-legal byte stability could not be evaluated against the source PL.
- Treating all sub-millimeter deltas as identity failures blocked valid inputs.

## Remediation

Load `m336.pl` explicitly for every `cold_source` run, including E0. Use it as
the float initial-position source, never as authority to refit the certified
geometry or runtime endpoints. Audit the native PlaceDB against the source with a
fixed `0.500001 mm` maximum tolerance, reflecting only the native parser's
nearest-integer quantization; reject any larger disagreement. Serialize the
maximum delta, tolerance, and affected component count in preflight evidence.

M336-154 supersedes the initial proposal to derive alignment from the float PL:
that changes the certified feasible domains and invalidates M336-118.

## Acceptance Criteria

- Cold runs identify `m336.pl` as `runtime_float_source`.
- `Q601` resolves from native-aligned geometry and `EMI601` from manual.
- M336 native parser deltas up to `0.5 mm` are measured, not used as endpoints.
- A source differing by more than `0.500001 mm` fails closed.
- Cold E2 reaches GPU optimization and post-serialization validation.

## Resolution

All cold runs explicitly load the hashed float `m336.pl` as
`runtime_float_source`. Preflight records 140 quantized physical components,
maximum native-parser delta `0.5 mm`, and tolerance `0.500001 mm`, while runtime
endpoints remain native-geometry aligned. The source-audit test rejects larger
deltas. The cold E2 10-step run completed 13 backward calls, 10 changing GPU
optimizer steps, exact post-serialization validation, and native scoring.
