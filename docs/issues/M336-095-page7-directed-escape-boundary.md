# M336-095: Page-7-Directed Search Retains the Current Incumbent

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `12de67b`

## Problem

M336-092 localized `536.846685` of optimistic current-to-quality HPWL
residual in six page-7 nets. M336-094 therefore built a directed guide that
replaces only the 18 BOTTOM page-7 refdes with quality-guide sites. A wider
page-7 domain and an exact legal escape were tested to determine whether the
current certified placement can leave its incumbent basin without weakening
containment or collision constraints.

The certified source has HPWL `15811.06557381333`, normalized score upper
bound `0.9651702157924906`, and placement SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`.
Passing score 1.0 still requires HPWL at most `15260.369571786632` before the
native RSMT scorer can accept a result.

## Exact Escape Probe

The deterministic exact-site descent used the directed guide with three
escape HPWL budgets. Each run allowed three escape sweeps, 20 closure sweeps,
10 pair moves, and 10 hold sweeps.

| Budget | Escape path | Peak rise | Final HPWL | Result SHA-256 |
| ---: | --- | ---: | ---: | --- |
| 5 | no guided candidate | 0.000000 | 15811.065574 | `f392f699f045fc74a9fc3746ff91bb3280515e7f388a4ac77070fe65a1d55d6c` |
| 20 | `C703` uphill, `FV707` plateau | 9.998926 | 15811.065574 | `cc9ebf91702432d8cdb6d8b77c86c2c03eab536f03a2ead208e3b97a83e95962` |
| 100 | same two moves | 9.998926 | 15811.065574 | `0a55ee74ad7d4ce7f9627db7b379327bae4340609654e4294760cec22740122f` |

The 20- and 100-budget escape seeds are byte-identical placements with HPWL
`15821.064499861614` and SHA-256
`2e771922e58a280671b848814d5cc25419d5d50c1c7734f733151396c62cfd74`.
An independent all-fixed K1 CP-SAT replay proves this intermediate state
`OPTIMAL`: 100/100 components fixed and contained, zero keep-in violations,
zero overlaps, and integer objective replay passed. The certification result
SHA-256 is
`f6a6e7d07a66922d01a822fb5502e3aed7e1cb1504dc62204e3cea2e69687fbc`.
This worse state is a legal search guide only; it is not an accepted result.

## Directed CP-SAT Portfolio

Both model families used the fixed assignment, exact BOTH-side collisions,
the 80-component M336-092 support, the certified source as a separate hint,
current plus page-7 hybrid candidate guides weighted `1:3`, one worker, seeds
1000-1003, and 300 deterministic seconds per run. The hybrid guide SHA-256 is
`cd27a437fedc7190227957dd8f143ece147613868573cc28b5dbf23683222b47`.

- Global K256: 19,486 candidates and 743,444 exact non-rectangle conflicts.
- Directed expansion: base K128 with the 18 page-7 refdes expanded to K1024,
  totaling 26,304 candidates and 386,044 exact non-rectangle conflicts.
- Every run used an isolated `<output>.context` directory from M336-093.

| Domain | Seed | Status | Valid bound | Branches | Conflicts | Result SHA-256 |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| K256 | 1000 | `FEASIBLE` | 14854.437478 | 2,357,697 | 480,759 | `5967ab72319f6ed58c1468ab516a0ac108feb3147b9c6600ee8fc7888e2066ce` |
| K256 | 1001 | `FEASIBLE` | 14854.437478 | 2,456,088 | 459,763 | `61e92641797dbcee488794af93b2f2d5262898dbceb757b3e72a56199aa75891` |
| K256 | 1002 | `FEASIBLE` | 14854.437478 | 2,237,861 | 471,874 | `13129bf88d39190ecedf473a3e37b6d5ddfd0e39ca67f9a675e5440e9b9fdad7` |
| K256 | 1003 | `FEASIBLE` | 14858.437048 | 2,515,150 | 447,745 | `ab70b9d49f11b5b021392e81e66814c633938c84ae534b052471d551c069a365` |
| page-7 K1024 | 1000 | `FEASIBLE` | 14923.788493 | 1,032,026 | 215,195 | `bf380ec1ac1301cb67ea6b2109c1a87b3be52f7eb6696f6fdc292ee8629eb53d` |
| page-7 K1024 | 1001 | `FEASIBLE` | 14923.788493 | 1,284,493 | 217,052 | `fcc816b0b09d6a4df3295d330b6026ceb84d2a6479236e671fd1a146093586a0` |
| page-7 K1024 | 1002 | `FEASIBLE` | 14923.788493 | 1,352,999 | 210,675 | `36076d4da1fa1737459629fefa05c5f4fdf8e4c1f2c928642d06fece1399f746` |
| page-7 K1024 | 1003 | `FEASIBLE` | 14923.788493 | 1,139,650 | 218,699 | `3be102ed081c66ebceae3425e9a0656442046530aedb98624bb5483190824dea` |

All eight incumbents have HPWL `15811.06557381333`, pass integer objective
replay and exact legality, and reproduce the certified placement byte for
byte. Their lower bounds are below the incumbent, so these finite searches do
not prove local optimality or infeasibility.

## Conclusion And Next Boundary

Allocating K1024 specifically to the page-7 residual and varying four seeds is
not sufficient to leave the current incumbent. The exact greedy path also
shows that the first guide-directed legal topology change costs approximately
`9.999` HPWL and needs at least two coordinated moves; increasing its budget
beyond 20 exposes no further guide-monotone move.

The certified escape state may next be added as a third candidate guide while
retaining the current independent hint and hard incumbent ceiling. Promotion
still requires a strict replayed HPWL improvement followed by independent
fixed-site certification. `FEASIBLE` budget exhaustion must not be reported as
an optimality or infeasibility result.
