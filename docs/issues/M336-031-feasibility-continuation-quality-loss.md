# M336-031: Feasibility Continuation Loses Placement Quality

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `e729300`

## Problem

Frozen-anchor continuation established replayable TOP packings through 93.75%,
but packing-only CP-SAT accepts the first legal state. HPWL increased from
`21359.767400` at 80% to `22287.766734` at 93.75%, moving farther from the
manual baseline score even as `Q601` approached its manual endpoint.

At 94.375%, both site encodings remained inconclusive after 300 seconds on the
same 29,720-site domain. Coordinate tables explored 2,020,056 branches with
981,036 KiB peak RSS; elements explored 447,432 branches with 1,546,988 KiB.
Neither produced a legal candidate.

## Mitigation

`--packing-objective hint-l1` explicitly minimizes total x/y displacement from
the structured site hint over the full CP-SAT search. It is available only in
packing-only mode with exactly one hint source. Reports distinguish its
objective and lower bound from HPWL, so displacement units cannot be mistaken
for wirelength.

This differs operationally from `repair_hint`: the latter runs a bounded local
repair phase controlled by `hint_conflict_limit`, while the explicit objective
remains active for the complete solve.

## Verification

A single-worker fixed replay of the 93.75% state was `OPTIMAL` with objective
and bound zero, zero branches, exact TOP legality, and unchanged placement
SHA-256
`9f5d982003f3849b92f89fc9c6ec3caa900ac68755256544a684e9331b024083`.

On the difficult 94.375% transition, the L1 run still remained `UNKNOWN` after
`300.125094 s`, 2,451,520 branches, and 1,586,727 conflicts. It established
only a displacement lower bound of `9.081992`; no feasible objective was found.
The option is therefore validated but not an acceptance improvement.

Opening 2,048 sites per component from the replayed 93.75% state and moving
`Q601` directly to its exact manual endpoint retained 49,682 TOP candidates
and 620 exact part constraints. Seed 1000 remained `UNKNOWN` after
`300.158448 s`, 4,357,459 branches, and 1,372,410 conflicts, with 1,126,016 KiB
peak RSS. This broad-domain result is also inconclusive and must not be cited
as endpoint infeasibility.

Changing only the portfolio seed to 1001 also remained `UNKNOWN` after
`300.132242 s`. It explored 1,725,608 branches and 29,778 conflicts versus
seed 1000's 4,357,459 and 1,372,410, respectively. This large trajectory
change without a candidate confirms seed sensitivity but does not justify
additional blind random restarts.

## Required Improvement

- Reach the exact manual endpoint with a replayable globally legal placement.
- Then optimize native HPWL/RSMT, not only displacement from a poor waypoint.
- Preserve exact legality and deterministic fixed replay after every quality
  improvement.
- Do not promote L1 minimization to the default without cross-case evidence.
