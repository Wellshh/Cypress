# M336-126: Expanded Guide Cannot Move Its External Blockers Sequentially

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `a77d058`

## Problem

M336-125 showed that jointly releasing `B402,L401` changes the finite domain
but direct CP-SAT search retains M336-118. A deterministic exact guided escape
was used to test whether sequential legal moves toward their quality
coordinates could seed a different topology.

## Experiment

Eight PCG64 order seeds 8000--8007 started from the portable M336-118
checkpoint. Each used the 20-component expanded quality hybrid, three escape
sweeps, total HPWL rise budget 100, per-move rise limit 20, and one ordinary
closure sweep. Candidate sites came from every valid `0.05 mm` domain site;
exact footprint collisions and keep-in containment remained mandatory after
every accepted move.

All runs took 193--200 seconds, accepted nine escape moves, and then restored
M336-118 during closure. Every escape state was 100/100 contained with zero
keep-in violations and zero overlaps.

## Result

The portfolio reproduced only the three M336-121 families:

| Seeds | Escape HPWL | Peak rise | Placement SHA-256 |
| --- | ---: | ---: | --- |
| 8000,8001,8003,8007 | 15649.948866405257 | 18.498067 | `14b534af7e58bd277ff1fcfd4045636756bbb3a9de4386f3c307f021ddec2ed5` |
| 8002,8004 | 15652.948544219742 | 26.497208 | `1d6830320d438463c3244232c4d68291be34d82bed0a02e9fb7da555cefc434b` |
| 8005,8006 | 15652.448544219742 | 17.998067 | `9a3ea48d129e4ba8b4b57d1f19376028f8744fd97a3e40ee23691cdca9783c5f` |

Those hashes are byte-identical to the three already tracked and all-fixed
certified guide placements. In every run, the held set was exactly
`C703,FV707,R707,R708`; neither `B402` nor `L401` moved. Increasing guide
support therefore did not affect this single-component transition mechanism.

Final-result SHA-256 values for seeds 8000--8007 are
`4031e20ac94da3a1d93b61d11f39824cf568d35a8f84470d4ada3c7fb9bb931c`,
`1dab7716041aa26b8ef47bc6200eb854f9164103a9662ea362e4a8668f7e9de4`,
`22700201cc59373ed62a210cde998a7456b852bc687eecbc4b27d617eb8d3504`,
`c5e349e5d041d4b2585f67daab08887a28a7b019eefdb900bfa05ba07410900b`,
`f32febdc75668b7c2da39a6be7fee011b0fe7e91ed4389a174dda5cd5df97381`,
`47810ae0b8c603fa90fd89986212355f16427f7c53fe81b2fa65c6cabbab68fe`,
`ced000b8073dcd93b22c17b33ea527e09059f19f70c88f78d2816e3ac71b1f6b`,
and `c3340e7bd9e4de3d5402f1810565e6f78d552ff4597f9ae63c0d8efc90c3cb35`.

## Conclusion And Next Action

The expanded transition requires simultaneous moves; more sequential-order
seeds cannot expose it. Do not duplicate the three certified guides. Use
CP-SAT minimum-rank solves with controlled relaxed HPWL envelopes so
`B402/L401` and page-7 components can move jointly while `MIC401` remains
fixed. Any distinct exact-legal topology remains a non-scoring guide until a
separate hard-incumbent HPWL closure and all-fixed certification succeed.
