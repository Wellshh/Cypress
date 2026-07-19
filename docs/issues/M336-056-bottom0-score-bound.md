# M336-056: Full Bottom-0 Closure Restores a Score-Feasible Bound

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `48b40e7`

## Problem

The 29-component page-based closure in M336-055 has a valid HPWL lower bound
above the score-1 threshold. Assignment inspection shows that it omits 13
controlled components sharing physical region `bottom_0`. A page boundary is
therefore still not a complete collision boundary.

## Expanded Domain

The model releases all 39 controlled `bottom_0` components plus the three TOP
members coupled to page-7 nets. The remaining 58 controlled sites stay fixed.
Both runs use manual/current/quality guides, the `EMI601` endpoint override,
one worker, seed 1000, and 300 deterministic-time units.

| Domain | Candidates | Status | HPWL | Valid lower bound |
| --- | ---: | --- | ---: | ---: |
| K128 | 5,434 | `FEASIBLE` | 15840.404661 | 15292.889572 |
| K256 | 10,810 | `FEASIBLE` | 15837.651783 | 15156.895723 |

Both objective replay audits pass and both outputs are exactly legal. K256
improves the certified source by `10.751375` and changes 41 components. K128's
bound remains above the score-1 threshold, but K256's bound is `103.473849`
below it. The expanded K256 restricted domain therefore cannot be ruled out as
score-feasible. This is not proof that a score-feasible placement exists; both
runs stopped `FEASIBLE`, not `OPTIMAL`.

## Certification

The K256 incumbent has normalized score upper bound `0.963550012` and remains
`577.282211` HPWL above the required threshold. Its all-fixed replay returns
`OPTIMAL` at `1e-8` deterministic-time with all integer objectives equal
`15837651795`, floating delta `0.000012136010`, 100/100 containment, and zero
violations or overlaps. The search result, placement, certification result,
and certified placement SHA-256 values are:

- `a0f61130d441481ef091179520601191582da3d7c335640ad5af6032e31383f6`;
- `5ba78b809e6badcae2cf928f4be6cafc74205a2bea8489812a327cde05d1b8b5`;
- `6b1d164afaca42fff2d997c38e78c458bf82143969b6ae7118edb134aa139276`;
- `5ba78b809e6badcae2cf928f4be6cafc74205a2bea8489812a327cde05d1b8b5`.

## Next Action

Run exact local closure, then continue K256 optimization from the certified
incumbent with the same physical boundary. A continuation changes the
current-guide candidate neighborhood while retaining the quality and manual
sites. If progress stalls, expand TOP collision closure or add bottom-1/2
network endpoints; do not revert to direct global threshold feasibility while
M336-053 remains unresolved.

## Exact Local Closure

Full-domain one/two-opt descent accepted one strict `FV302` move of
`-1.247336`; the following complete pair scan evaluated 2,896 relevant pairs
and 2,363,505 site combinations without another improvement. HPWL is
`15836.404447`, normalized score upper bound is `0.963625905`, and the remaining
score-1 gap is `576.034875`.

The all-fixed replay is `OPTIMAL` at `1e-8` deterministic-time. All integer
objectives equal `15836404459`, floating delta is `0.000012412711`, and exact
legality remains 100/100 with zero violations and overlaps. The local result,
placement, certification result, and certified placement SHA-256 values are:

- `d22ed304f3f777679f062b81678000d8a87cd4d27d0c949151ece66995a37cc7`;
- `e22d5f697dd4779af0c41a6acf63988055cdb99a326e08d02d05aac6e5ed8849`;
- `6d435c4f3c2dc920e1c9034b91a94297efa3d063b0ff0d5363633e4589d997df`;
- `e22d5f697dd4779af0c41a6acf63988055cdb99a326e08d02d05aac6e5ed8849`.
