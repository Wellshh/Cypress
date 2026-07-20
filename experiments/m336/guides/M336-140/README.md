# M336-140 Direct DATA2 Topology

`data2-direct-d20/certificate.json` is the portable all-fixed K1 certificate
for the first legal topology produced by directly minimizing the
`PSIM2_DATA2` span under an M336-118 plus 20 global HPWL envelope.

The topology changes `C703,FV707,FV708,FV710,R708`, reduces the DATA2 integer
span from `272367284` to `260868573`, and has HPWL `15654.448329429399`. It is
100/100 contained with zero keep-in violations and zero exact overlaps. A K1
replay launched from `/tmp` produced byte-identical placement SHA-256
`884c0d2973454418e60cb8a36176697cd112a1fd7548ea1d809e577c7c261c96`.

This is a legal search guide, not a scoring incumbent. Full one-opt followed by
one complete pair scan returns the certified M336-129 equal-HPWL swap plateau.
M336-118 remains the only scoring checkpoint.

`data2-cpsat-plateau/certificate.json` records the independent hard-ceiling
Solve B result. CP-SAT proved the 21,072-candidate finite domain optimal at the
M336-118 integer HPWL, while returning a distinct double-swap plateau over
`C703/FV707` and `FV703/FV704`. Its K1 and `/tmp` portable replays have
placement SHA-256
`279005fe88212da93942307d6733b24d5b3a2c7b0969fe4948b96287beae09b6`.
This is also a non-scoring guide, not a replacement incumbent.
