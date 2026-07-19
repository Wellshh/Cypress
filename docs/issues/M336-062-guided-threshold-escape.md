# M336-062: Exact Descent Needs A Bounded Escape Phase

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `26dad72`

## Problem

The certified incumbent at HPWL `15835.344196` is an exact one- and
two-component local optimum. A quality-guided plateau run accepted 18 legal
moves but retained the same HPWL and again stopped at a two-optimum. Strict or
equal-only descent therefore cannot cross the remaining 574.974624 gap.

## Mitigation

`greedy_exact_site_descent.py` now has an optional deterministic guided
threshold phase. `--max-escape-sweeps` enables it and
`--escape-hpwl-budget` sets a hard floating HPWL envelope relative to the
source. Every accepted move must:

- use an obstacle-free feasible-domain site;
- pass exact same-side footprint overlap checks;
- move strictly closer to the declared plateau guide;
- remain below the source HPWL plus the explicit budget;
- match an independent PlaceDB HPWL replay within `1e-8`.

The phase stops immediately if its combined path improves the source, then
runs ordinary strict one/two-opt closure. If closure does not improve the
source, emitted coordinates and selected sites are restored to the source.
Attempted moves, peak rise, stop reasons, and restoration remain in the JSON.

## Verification

The M336 suite passes 45/45. The real-board `+1.0` HPWL, one-sweep integration
accepted 18 guided moves: 16 plateau and two uphill. Peak rise was `0.885394`
and the perturbed state reached `15836.229590`. Subsequent one-opt did not find
a better basin, so the result restored HPWL `15835.344196`. Final exact
legality is 100/100 containment with zero keep-in violations and overlaps.

An independent rerun produced identical normalized JSON SHA-256
`f51d72605cbc485a0c6a28297df67f57b62f0c7811192597bd9b5195fb079dba`.
Both emitted placements and the source placement are byte-identical with
SHA-256 `a44942bee4ba8c1bf275ef08177ed359de588b8045907e2b3853d3f5a0a179c6`.

## Next Action

Run a small deterministic budget ladder with multiple escape sweeps. Add pair
closure only after a threshold path changes the post-descent topology; avoid
repeating the already closed one-sweep basin. Any strict improvement still
requires all-fixed CP-SAT replay certification before promotion.
