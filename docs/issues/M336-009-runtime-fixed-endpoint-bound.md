# M336-009: Quality Bounds Used the Wrong Fixed Endpoints

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `cfbd7aa`

## Problem

The first quality-bound implementation read every uncontrolled net endpoint
from `placedb.node_x/node_y`. Those coordinates depend on which Bookshelf
placement happened to be loaded and do not represent the actual experiment.
An intermediate correction then used the manual baseline for every endpoint,
which was also wrong: the M336 contract freezes anchors and 15 unclustered
components at source-aligned runtime positions.

## Impact

The bound and assignment objective were not describing the placement that E4
executes. Reported upper bounds could change with input loading and the MILP
could select a different assignment for the wrong fixed geometry.

## Resolution

`_runtime_fixed_positions` now constructs one explicit endpoint state:

- ordinary uncontrolled nodes retain manual-baseline lower-left coordinates;
- the 25 anchors and 15 configured fixed components use
  `context.frozen_lower_left` source-aligned coordinates;
- interval analysis, assignment MILP, and discrete CP-SAT share that state.

The corrected runtime-fixed count is `40`. At `0.1 mm`, optimized relaxed HPWL
is `15817.4414` with score upper bound `0.964781`; at `0.05 mm`, it is
`14675.1473` with upper bound `1.039878`.

## Verification

Unit tests independently verify that supplied uncontrolled coordinates are
used and that runtime freeze coordinates override the manual placement only
for declared frozen nodes. Generated assignment reports also record baseline,
Bookshelf, and assignment SHA-256 hashes.

## Acceptance Criteria

- No quality path reads implicit `placedb.node_x/node_y` for fixed endpoints.
- All quality models share the same documented runtime-fixed state.
- Endpoint semantics and frozen overrides have focused regression tests.
