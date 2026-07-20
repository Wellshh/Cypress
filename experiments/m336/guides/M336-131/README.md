# M336-131 d6 Rank-11 Topology

`d6-rank11/certificate.json` is the portable all-fixed K1 certificate for the
first d6 optimum found in the unchanged M336-122 K4096 candidate domain. It is
a Solve-A topology seed, not a scoring incumbent.

```text
guide-rank:          11 (OPTIMAL)
HPWL:                15649.948866405257
integer HPWL:        15649948871
changed from M336-118:
  C703,FV705,FV707,FV708,FV710,R707
legality:            100/100 contained, zero keep-in, zero overlap
```

The topology was found only after replacing the infeasible d4 solver hint with
the certified M336-130 d6 hint. All hint-to-candidate distances were zero. Full
one-opt and exact pair closure return this topology to the already certified
M336-129 equal-HPWL swap plateau, so it must not replace M336-118.

The checkpoint manifest verifies all portable dependencies. The original rank
solve has SHA-256
`1abfd9e78f534686ec4920b9bc82a01481ecf1584d4d68b02a64773b05824ab1`;
its complete parameters and closure evidence are recorded in M336-131.
