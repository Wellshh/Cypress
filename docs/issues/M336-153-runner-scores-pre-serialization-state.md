# M336-153: Runner Scores Pre-Serialization State

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `d912f4c`

## Problem

`run_matrix.py` previously accepted the `Final PPA` emitted by the main placer
and, for E2-E4, reused `constraints/legality.json`. Both are produced before
`Placer.save_placement()` serializes the final `.pl`. The run ledger therefore
did not prove exact legality or native HPWL/FLUTE RSMT for the bytes it exposed
as the result artifact.

## Impact

- A serialization drift could invalidate legality after the reported check.
- Float32 in-memory HPWL/RSMT could be presented as a serialized replay score.
- The required chain stopped before independent post-serialization evidence.
- E4 acceptance and runtime ratios omitted replay validation/scoring cost.

## Remediation

After every E0-E4 placement, create an isolated validation context and parse the
serialized output in float64. Then run a separate evaluate-only native scorer
on an AUX that references those exact bytes, force float64, disable all
placement/repair features, and require zero coordinate replay drift. Treat the
replayed HPWL/RSMT and exact report as authoritative while retaining the
pre-serialization values only as diagnostics. Include both replay stages in
end-to-end runtime.

## Acceptance Criteria

- Every run has isolated post-serialization legality and native-score files.
- Native replay uses float64 and reports finite HPWL and FLUTE RSMT.
- Replayed coordinates differ from serialized input by at most `1e-9`.
- `run-result.json` uses replayed metrics and records pre-serialization metrics.
- E4 exact legality is decided from the post-serialization report.

## Resolution

Every E0-E4 result now runs one isolated float64 exact validator and one
evaluate-only native HPWL/FLUTE scorer against the serialized PL. Authoritative
metrics come from that replay; pre-serialization HPWL/RSMT remain explicit
diagnostics. Warm E4 replay reports zero coordinate error, native HPWL/RSMT
`15632.260310/17328.977`, 100/100 containment, and zero overlaps. The runner
fails closed if post-serialization E4 legality is not exact, and reevaluation
uses the same isolated path while checking input hashes.
