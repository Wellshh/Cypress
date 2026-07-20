# M336-138: Residual Portfolio Changes Domain But Retains DATA2 Gap

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `0e72cbd`

## Search Contract

M336-138 replaces the five M336-122 candidate guides with M336-118 plus the
six M336-130 residual coordinate targets. It keeps the M336-118 source,
assignment, and separate hint; 18-component page-7 support; K4096 allocation;
0.05 mm grid; manual EMI601/runtime Q601 endpoints; exact BOTH-side
collisions; seed 8408; and one worker.

Weights `2,1,1,1,1,1,1` preserve M336-118's 25% share of the eight-unit
budget and divide the remaining 75% equally across `VSIM2`, `SIM_DET1`,
`PSIM2_DATA2`, `NFC_SWP`, `PSIM2_SRST2`, and `PSIM2_SCLK2`. The run has no
quality objective and stops after the first exact feasible solution.

A preliminary invocation omitted the explicit grid, side, and manual-endpoint
variables. Defaults selected TOP/0.1 mm/manual Q601, and the movable-support
check rejected every BOTTOM page-7 refdes before candidate construction. This
is not experiment evidence. The final run explicitly fixes all three values.

## Candidate Comparison

The model contains 73,810 candidates; the 18 movable components contribute
73,728 audited sites. Relative to the portable M336-137 M336-122 reference:

```text
intersection: 71229
union:        76227
Jaccard:      0.9344326813333859
added sites:  2499
removed sites:2499
```

Seventeen component candidate sets change; only `FV702` remains identical.
The largest changes are `C703` (Jaccard `0.635456`) and `FV707` (`0.623142`).
Thus this portfolio materially changes candidate topology rather than merely
renaming guides.

| Guide | First-admitted sites | Exact targets |
| --- | ---: | ---: |
| M336-118 | 18,432 | 18/18 |
| VSIM2 target | 9,216 | 18/18 |
| SIM_DET1 target | 9,216 | 18/18 |
| PSIM2_DATA2 target | 9,216 | 16/18 |
| NFC_SWP target | 9,216 | 18/18 |
| PSIM2_SRST2 target | 9,216 | 18/18 |
| PSIM2_SCLK2 target | 9,216 | 18/18 |

## Persistent DATA2 Boundary

The dedicated `PSIM2_DATA2` guide still has zero exact coverage for its two
controlled endpoints. The nearest selected site remains:

- `FV710`: 58.687819 model units, or `2.934706 mm`;
- `R708`: 0.999893 model units, or one `0.05 mm` lattice step.

These values are byte-for-byte equal to the generic quality-hybrid distances
in M336-137. Giving DATA2 its own positive candidate budget therefore does not
make its collision-relaxed coordinates exact-site representable. This result
does not prove that the K4096 domain has no improving topology, and it does not
yet distinguish off-lattice, keep-in, and fixed-obstacle causes. It does prove
that further weight or seed ladders over the same coordinate target are not a
valid remedy.

## Feasibility And Portability

The no-objective solve returned `OPTIMAL` after 182.593 build seconds, 23.560
solve seconds, and 8.073 deterministic-time units. It retained HPWL
`15634.450477332834`, the M336-118 placement SHA-256 `32f814e4...968cbf7`,
100/100 containment, zero keep-in violations, and zero overlaps.

The portable reference is
`experiments/m336/coverage/M336-138/m130-residual-k4096.json` (SHA-256
`2d3b41aee03cad416de6d336ae53bcf39386ceb6c044255ef087377e2f3900d9`).
All 11 dependencies match, and strict self-comparison gives Jaccard `1.0` over
73,728 sites.

Stop reusing the M336-130 collision-relaxed DATA2 coordinates as the endpoint
objective. Generate an exact feasible `PSIM2_DATA2` net-span guide directly,
classify the full-domain target obstruction, and include measured physical
partners before another topology solve. M336-118 remains the scoring
incumbent.
