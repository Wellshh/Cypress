# M336-135 Fourth d6 Rank-11 Topology

`d6-rank11-nogood3/certificate.json` is the portable all-fixed K1 certificate
for the fourth rank-11 d6 topology in the unchanged M336-122 K4096 domain. The
M336-131, M336-133, and M336-134 tuples were excluded exactly.

```text
guide-rank:          11 (OPTIMAL after three no-goods)
HPWL:                15651.948651614910
integer HPWL:        15651948656
changed from M336-118:
  C703,FV707,FV708,FV710,R707,R708
legality:            100/100 contained, zero keep-in, zero overlap
```

This topology has the same changed-refdes support as M336-134 but different
`FV710/R708` sites. A K1 replay from `/tmp` reproduced the placement bytes.
One-opt maps it to the same `47e65c62...` placement as the first three rank-11
topologies, whose certified pair closure reaches the M336-129 equal-HPWL swap
plateau. This artifact is an enumeration/no-good reference, not a scoring
incumbent.
