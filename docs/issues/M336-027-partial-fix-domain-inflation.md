# M336-027: Partial Fixing Retained Full Candidate Domains

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `604057f`

## Problem

Local CP-SAT repair accepted a list of movable refdes and fixed every other
controlled component to its structured site hint. However, `_build_model`
first enumerated the fixed component's entire limited domain, built broad
coordinate ranges and swept collision boxes, and only then added `site ==
hint`. This preserved unnecessary element-table rows and collision constraints
for components that had no remaining decision.

## Correction

Each partially fixed component now retains exactly one candidate: its hinted
`{region_id, site_index}`. Other assignment-option arrays are empty. The
resulting coordinate and swept domains therefore describe the actual fixed
footprint before collision-pair pruning.

## Evidence

A `0.1 mm` repair with 12 TOP components movable and 88 controlled components
fixed retained 21,409 sites, 125 possible component collision pairs, and 693
convex-part constraints. It used 627,736 KiB peak RSS and completed in 14.92 s.
For context, the unscoped model at the same grid retained 215,749 sites and
3,500 part constraints, then remained `UNKNOWN` after 300.71 solver seconds.

The repaired local model returned `INFEASIBLE` after 3.93 solver seconds with
zero branches. That is a useful domain result, not a placement candidate: the
two 4,096-site guide neighborhoods are insufficient when all other sites stay
fixed.

## Verification

- A unit test checks singleton retention, empty non-hinted regions, and unknown
  region rejection.
- The M336 baseline suite passes 27/27 tests.
- Model reports preserve the movable-refdes and fixed-site counts.

## Residual Risk

CP-SAT still models every fixed controlled shape. A future component-only LNS
model could replace them with constant obstacles, but the remaining size is no
longer the immediate bottleneck for this local repair.
