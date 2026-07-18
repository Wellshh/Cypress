# M336-012: No Same-Side Assignment Passes The Discrete Quality Gate

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-18
**Affected commit:** `c76f9ee`

## Problem

`M336-010` rejected one quality-optimized assignment, but another assignment
might have satisfied shared component coordinates. A coupled CP-SAT model now
searches subgroup region selection and component sites together.

## Deterministic Evidence

The model includes all 61 individually feasible side-preserving options for 31
subgroups and 1,410,293 exact `0.05 mm` feasible-domain sites. One site variable
defines each component's shared x/y across every pin and net. Runtime freezes
the declared 25 anchors and 15 fixed components.

The strongest diagnostic removes all overlap and area-capacity constraints,
making it more permissive than any accepted placement. It retains only
same-side keep-in sites, shared subgroup assignment, native HPWL, and the
necessary score-1 HPWL limit `15260.369571786632`. A conservative `0.000304`
integer-rounding allowance is included.

| Quantity | Value |
| --- | ---: |
| Status | `INFEASIBLE` |
| Workers / seed | `1 / 1000` |
| Branches / conflicts | `226 / 0` |
| Solver wall time | `65.510 s` |
| Candidate sites | `1,410,293` |
| Assignment options | `61` |

An eight-worker run independently returned the same status and branch count in
`70.392 s`. With normal capacity ratios enabled, the result was also
`INFEASIBLE` (`206` branches, `67.108 s`). Input hashes are assignment
`bb69ec27cfe48a428428eaecda0dd33f4e29192594bee04dae743cc95798365c`,
manual placement `65ea89cfae831871fd115f61b50e528bcc77a0285d85ecbf4c4a97ba898ad595`,
and baseline result `df8096d78fd3bff60bc2ad179fb83eda276da4566aeda1feafae7ffa9418ae2f`.

## Scope

This proves the score target impossible for the current `0.05 mm` lattice,
regions, sides, and runtime freeze policy. It does not yet prove impossibility
for continuous coordinates, a finer grid, reassigned sides, or movable anchors.

## Remediation

1. Compute a shared-coordinate continuous box relaxation.
2. If that survives, test `0.025 mm` before changing the production grid.
3. If the continuous relaxation fails, request a contract decision on anchors,
   keep-in regions, side assignment, or the score requirement.

## Acceptance Criteria

- A candidate survives the shared-coordinate score gate on the selected grid.
- Exact collision validation reports `100/100` and zero overlaps.
- Native HPWL/RSMT normalized score is at least `1.0`.
