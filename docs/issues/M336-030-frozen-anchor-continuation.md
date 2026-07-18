# M336-030: Direct Frozen-Anchor Relocation Hides a Feasible Path

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `45423c5`

## Problem

`Q601` moves from runtime lower-left `(669.335, 540.624)` to the manual
baseline `(526.06, 247.47)`. Applying that full displacement before repacking
creates 12 TOP overlaps. Full grid01 TOP searches remained `UNKNOWN` after 300
seconds, while fixing the 12 direct neighbors or a 20-component spatial ring
was strictly infeasible. The relocation requires an all-TOP displacement chain,
but the direct jump provides no feasible intermediate state.

Enabling CP-SAT `repair_hint` with a 100,000-conflict budget did not repair the
12-overlap hint. It remained `UNKNOWN` after `300.166597 s`, with only 21,716
branches and two reported conflicts, and used 1,465,440 KiB peak RSS. The hint
repair phase stalled rather than improving the normal portfolio search.

## Correction

The solver now supports repeatable `--fixed-endpoint-override REFDES X Y`
arguments. Overrides are limited to known frozen components and reject
non-finite coordinates, conflicting duplicates, and simultaneous manual and
explicit overrides. Structured coordinates are persisted in the model report.

`--repair-hint` and `--hint-conflict-limit` are also explicit and reported;
their defaults preserve OR-Tools behavior. They are diagnostic controls, not a
default workaround.

## Continuation Evidence

Moving `Q601` 75% toward the manual endpoint, to `(561.87875, 320.7585)`, kept
the known runtime TOP sites legal. A fixed replay was `OPTIMAL` with zero
branches and reduced HPWL from `23336.872601` to `21410.904250`.

At 80%, `(554.715, 306.1008)`, the prior sites had two TOP overlaps. A
single-center 1,024-site coordinate-table model repaired all 30 TOP components
in `7.094571 s`, using 76 branches and no reported conflicts. Exact TOP
validation found zero keep-in violations and zero overlaps. A single-worker
fixed replay was `OPTIMAL` in `0.027493 s`, zero branches, and reproduced
placement SHA-256
`892f8eafd94a951b71327ed664e5066c343f043b111b78b3f057456e14ab7051`.

The next 5% step moved `Q601` to `(547.55125, 291.4431)`. Its input had four
TOP overlaps; CP-SAT found a zero-overlap TOP packing in `8.325890 s` after
178,042 branches and 2,526 conflicts. Fixed replay reproduced placement
SHA-256
`b03effceab7962cef80988887d687c9076e1b3c640daa62cb9830e42c3e96713`
with zero branches. Feasibility-only search increased HPWL to `21748.257336`,
so continuation preserves packing feasibility but does not preserve quality.

At 90%, `(540.3875, 276.7854)`, the prior state had five TOP overlaps. The
same 1,024-site model found a legal TOP packing in `7.427512 s` after 230,949
branches and 13,047 conflicts. Fixed replay reproduced placement SHA-256
`c91aeba7794cb0dad4fbc5b237a0a78fdd752a41dbf7df31525212e36889ca30`.
HPWL was `21828.103303`, confirming that the feasibility path remains stable
while its unconstrained quality does not improve monotonically.

## Remaining Work

The 80% endpoint is not the acceptance target. Its HPWL is `21359.767400` and
necessary normalized score upper bound is only `0.714445`. Continue bounded
steps to the exact manual endpoint, merge with the zero-overlap BOTTOM result,
then run global fixed replay and native HPWL/RSMT scoring. No intermediate
side-only result may be reported as accepted.
