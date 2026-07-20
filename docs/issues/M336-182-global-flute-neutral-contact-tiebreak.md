# M336-182: Local Contact Choices Miss a Global FLUTE Boundary

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-21
**Affected commit:** `f56fb09`

## Problem

M336-180 attributes the M336-178 E2 RSMT regression to a `+1.127` change on
the 84-pin `GND` net while its HPWL is unchanged. The first visible authority
difference is `{C501,C502,R704}`: M336-174 applies `C501`'s proposal motion to
all three nodes, while M336-178 preserves `C501` and `C502` and applies
`C501`'s authority only to `R704`. This repeats on all ten accepted steps, and
`C502` has the largest final cross-run displacement at `0.245849609` Cypress
units (`0.012294 mm`).

That local difference is not itself the FLUTE transition. Read-only replay of
the committed float64 artifacts gives:

| Existing or hybrid coordinates | GND RSMT | Total RSMT | HPWL | Exact result |
| --- | ---: | ---: | ---: | --- |
| M336-178 E2 | `2846.914` | `17328.847` | `15632.829467` | legal |
| M336-178 with only M336-174 `C502` | `2846.914` | `17329.093` | `15632.829467` | legal |
| M336-178 with M336-174 `C501/C502/R704` | `2846.913` | `17329.091` | `15632.829467` | legal |
| M336-178 with all 33 changed GND nodes from M336-174 | `2845.787` | `17328.197` | `15633.074595` | 2 overlaps |

The first two hybrids prove that a component-local C502 rule does not control
the global topology. The last hybrid is attribution only and cannot be emitted
because mixing trajectories breaks legality.

Simple proxies are also insufficient. A median-star sum ranks the complete
M336-174 artifact ahead of M336-178 (`17404.761084` versus `17404.901629`),
but C502's own contribution moves in the opposite direction. Both dynamic and
fixed rectilinear-MST proxies rank M336-178 ahead despite its worse FLUTE
result. No such proxy is authorized for an effect run.

Artifact identities are:

```text
M336-174 E2 placement
dbaffb7e4c6bda1e70079ddb2d89d8c3a4f6fdda8214371932d5590a310e5914
M336-178 E2 placement
9dc7e3b551a646c974d43a0e3a659f63ce621d4f4b3b39f843d282a6a1b9e272
```

## Required Native Mechanism

Add a default-off, deterministic hard-projection tie-break for protected
proposal-authority mode. It is not a differentiable objective and must be
reported as projection-boundary control.

For each affected protected pass, form at most two global candidates from the
same immutable GPU optimizer proposal:

1. the exhaustive-equivalent proposal-authority winner; and
2. the existing proposal-medoid component-consensus candidate.

The second candidate is a planned alternative, not a fallback. It is eligible
only if normal footprint-aware hard projection succeeds and exact component
validation proves every historical protected edge remains closed. A failed
candidate is discarded with a reason; it cannot trigger checkpoint, origin,
repair, or exact-site substitution.

Evaluate both candidates on a fixed, generic topology-sensitive net set:

- net degree is at least an explicit configured threshold;
- net degree remains below the native scorer's ignore limit;
- TOP/BOTTOM coordinates and ordinary pin offsets are unchanged;
- the same native HPWL and FLUTE implementation is used.

Select by `(selected-net HPWL, selected-net FLUTE RSMT, authority preference)`.
FLUTE therefore decides only an HPWL-neutral high-degree topology tie; it
cannot buy RSMT by worsening that net set's HPWL. Exact authority wins complete
ties, preserving its smaller correction scope whenever topology is unchanged.

The evaluator is bounded to two score calls per protected pass and must report
call count, selected net IDs/degrees, candidate costs, selection reason, and
elapsed CPU/GPU synchronization time. It must never invoke FLUTE for every
authority assignment. A local benchmark on the recorded environment measured
`26.9 us` per repeated full-net FLUTE call after LUT initialization; this is a
design budget observation, not D1 runtime evidence.

## Required Tests

1. A synthetic multi-pin pair with equal HPWL and distinct FLUTE topology
   selects the lower-RSMT legal candidate.
2. Lower selected-net HPWL wins even when its RSMT is higher.
3. Exact ties select proposal authority and preserve byte identity.
4. A consensus candidate reopening any protected edge is ineligible.
5. No topology-sensitive net yields zero score calls and the authority result.
6. Score calls never exceed two per pass and never scale with authority states.
7. Feature-off, exhaustive authority, and topology-guard-off traces are
   byte-identical to M336-178 after new disabled diagnostics are removed.
8. Recorded M336-174/M336-178 E2 artifacts reproduce equal GND HPWL and select
   M336-174's lower GND FLUTE direction without writing a placement.

## Combined D1 Gate

No M336 effect run is authorized until M336-181 and this candidate are
implemented, installed, tested, signed, committed, pushed, and pulled. Then run
one checkpoint-warm E2/E3, seed `1000`, ten iterations, scale `1`, deterministic
CuBLAS, physical GPU 2, with explicit run-local output/summary/report paths.

Both arms must preserve the complete native CUDA chain, exact accepted-step
legality, protected-edge monotonicity, correction/component/state bounds,
zero-drift float64 serialization, HPWL no-regression, positive E3 anchor
direction, and M336-179 runtime gates. E2 must satisfy native
`RSMT <= 17328.300`. Stop at the first failed conjunct. D2, D3, E4, CP-SAT,
repair, fallback, and parameter ladders remain prohibited.

## Acceptance Criteria

- The topology decision is global, exact, bounded, and proposal-derived.
- It controls the recorded zero-HPWL-delta FLUTE direction without a local
  heuristic or post-failure output substitution.
- The one combined D1 passes M336-179 and M336-180 together.
