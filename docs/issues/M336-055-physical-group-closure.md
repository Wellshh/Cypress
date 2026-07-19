# M336-055: Physical Group Closure Beats Net-Ranked Neighborhoods

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `0d666ee`

## Problem

Selecting movable components only from high-penalty nets omits components that
do not dominate HPWL but block the same physical keep-in space. The prior
top-15 solve was followed by new `FV702`/`R705` and `RT601` local moves,
demonstrating that the network-ranked boundary was not collision-closed.

## Physical Closure

The next model includes every controlled component in the page-4 bottom group
and all three controlled page-7 groups, plus `RT601`, which previously swapped
with page-4 `C404`. This produces 29 movable and 71 fixed components. Manual,
current, and quality guides use identical `EMI601` endpoint semantics. K256
and K512 runs use one worker, seed 1000, and 300 deterministic-time units.

| Domain | Candidates | Status | HPWL | Valid lower bound |
| --- | ---: | --- | ---: | ---: |
| K256 | 7,495 | `FEASIBLE` | 15860.403158 | 15285.096308 |
| K512 | 14,919 | `FEASIBLE` | 15888.961231 | 15285.096308 |

Both objective replay audits pass and both placements are exactly legal. K256
improves the certified source by `40.776552`; K512 improves by only
`12.218479` in the same budget. This is an incumbent-search effect, not proof
that the wider K512 domain is worse. Neither run is `OPTIMAL` or `UNKNOWN`.

The shared valid lower bound is `24.726736` above the score-1 HPWL threshold.
Therefore this 29-component physical closure cannot reach score 1.0 while the
other 71 sites remain fixed, even though its incumbent materially improves.
This restricted-domain proof is not a global infeasibility result.

## Certification

The promoted K256 result changes 24 components and reaches normalized score
upper bound `0.962167823`. Its all-fixed replay returns `OPTIMAL` at `1e-8`
deterministic-time with all integer objectives equal `15860403168`, floating
delta `0.000010154772`, 100/100 containment, and zero violations or overlaps.
The regional result, placement, certification result, and certified placement
SHA-256 values are:

- `bd009c54a6c3d56aba01d2d23c94e982a6d3747af056cf759725cf62616b04bb`;
- `2c2e5e83bdaaa658da367ab405fcbfdd5fa0f9b594df534c77811e4dbf73e40d`;
- `0af4453e9f4e8ac3dad893c5a6a9c374781348af65ffea1b826b8a701085b272`;
- `2c2e5e83bdaaa658da367ab405fcbfdd5fa0f9b594df534c77811e4dbf73e40d`.

## Next Action

The certified incumbent remains `600.033586` above the score-1 threshold.
Run exact local closure, then recompute residual network penalties. Expand by
whole same-side physical groups or explicit blocker closure, not isolated
network members. Use K256 as the first incumbent phase and separately budget a
wider-domain continuation; do not compare FEASIBLE incumbents as domain proofs.

## Exact Local Closure

Full-domain one/two-opt descent from the certified K256 result found one
`R702`/`R705` blocker-release swap. The components share no net and exchange
their occupied sites; HPWL decreases exactly `12.0` to `15848.403158`. A
second complete pair search found no improving move.

The all-fixed replay is `OPTIMAL` at `1e-8` deterministic-time with all integer
objectives equal `15848403168`, floating delta `0.000010154772`, 100/100
containment, and zero violations or overlaps. The local result, placement,
certification result, and certified placement SHA-256 values are:

- `7e554b0d1fea1f7a8f419d8eb7d2396578ec00e763f91789b66348cc5eb09bc8`;
- `83431dc5428672c89e72c5e8d98438544ab7958a1c5b6fafc6662f99f851556d`;
- `4ec40e582d2842519b634554a45f46c3b667bdc9c83fd61ceeb308bdf70878d7`;
- `83431dc5428672c89e72c5e8d98438544ab7958a1c5b6fafc6662f99f851556d`.

The remaining score-1 HPWL gap is `588.033586`. Recompute the physical and
network boundary from this new two-optimum before the next regional expansion.
