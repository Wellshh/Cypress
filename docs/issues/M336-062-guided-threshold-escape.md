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

## Budget Ladder

Three wider deterministic runs retained the same source, quality guide, sorted
component order, and exact checks. None produced a strict improvement, so all
restored the source placement:

| Budget | Sweeps | Guided moves | Uphill moves | Peak rise | Stop reason |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 1 | 18 | 2 | 0.885394 | sweep limit |
| 5 | 3 | 24 | 5 | 4.286124 | no guided candidate |
| 20 | 3 | 24 | 5 | 19.443496 | no guided candidate |
| 100 | 3 | 33 | 15 | 69.958559 | no guided candidate |

All final reports remain 100/100 contained with zero violations and overlaps.
Raw result SHA-256 values in ascending budget order are:

- `9dc1f248c2b06dbaa2c9e10c978e8c46a227b6743c9f65d5c675739d8c615379`;
- `e672eccd5a9f8cb5b4af9034a7acb96aa6b2d225199881859570332d178d61e6`;
- `147159c8e2818686a32bd3c5879685dae0ef17ab738bd7178bb4567ddb0f058b`;
- `88b46cc299821192007ee02e35bbfe6e3aab63957a8fb278c18f10867f7df56d`.

The budget-100 closure immediately reversed 10 perturbations before other
components could adapt. Its largest exact reversals were `C8606` (-23.349699),
`C8611` (-7.999141), and `C8603` (-7.928230). Increasing the envelope further
therefore does not address the observed mechanism.

## Next Action

Hold only the uphill-moved components for one deterministic adaptation sweep,
allowing all other components to descend while the changed blocker topology is
present. Then release the hold and run normal closure. Do not enlarge the HPWL
budget unless this controlled hold exposes a new reason. Any strict improvement
still requires all-fixed CP-SAT replay certification before promotion.
