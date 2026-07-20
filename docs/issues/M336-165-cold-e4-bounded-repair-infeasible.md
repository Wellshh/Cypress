# M336-165: Cold E4 Bounded Repair Is Infeasible

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `cc05a44`

## Problem

The seed-1000, 50-step cold/source E4 run completes native GPU optimization but
cannot legalize its bounded conflict subset. The Placer exits nonzero before
serialization and native scoring, so the cold matrix correctly stops without a
promoted result.

## Evidence

Cold initialization repairs the measured 96-component source closure in
`53.7927 s` and starts optimization exact legal. The optimizer executes 53
backward calls and 50 changing Adam steps, then reports BOTTOM normalized
overflow `1.558634`. During E4 repair, every deterministic packing order fails
immediately at `MHC8602` with `placed_count=0`, raising
`InfeasibleDomainError`. No `run-result.json`, final legality report, serialized
placement, HPWL, or RSMT is produced for E4.

The completed cold diagnostics are also far from the quality gate: E2/E3 scores
are `0.745054/0.745068`, while anchor mean/p90 remain approximately
`7.54/15.75 mm`.

## Impact

- The required cold E4 track is incomplete.
- A raw exception is the only repair failure artifact.
- The same native overlap problem affects both initialization tracks.

## Remediation

Preserve the fail-closed behavior. Emit a machine-readable repair failure report
before raising, including the exact closure, fixed occupancy, candidate counts,
failed component, attempted strategies, and elapsed time. Audit whether the
subset is physically closed around `MHC8602`; expand only by measured collision
closure within the E4 bound. The primary fix remains reducing native overlap
growth, not returning the initial exact placement.

## Acceptance Criteria

- Cold E4 either produces an independently validated exact-legal result or a
  complete structured failure artifact.
- Bounded repair candidate occupancy excludes self-conflicts and records all
  frozen blockers.
- No initial/checkpoint placement is silently emitted after repair failure.
- A successful cold result receives serialized float64 legality and native
  HPWL/RSMT replay.
