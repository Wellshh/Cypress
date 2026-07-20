# M336-133 Second d6 Rank-11 Topology

`d6-rank11-nogood1/certificate.json` is the portable all-fixed K1 certificate
for the second rank-11 d6 topology in the unchanged M336-122 K4096 domain. The
M336-131 rank-11 tuple was excluded exactly.

```text
guide-rank:          11 (OPTIMAL after one no-good)
HPWL:                15651.948651614910
integer HPWL:        15651948656
changed from M336-118:
  C703,FV705,FV707,FV708,R707,R708
legality:            100/100 contained, zero keep-in, zero overlap
```

Compared with M336-131, this topology changes `R708` instead of `FV710`.
Independent one-opt closure maps both topologies to the same placement bytes;
exact pair closure then maps that state to the M336-129 equal-HPWL swap
plateau. This artifact is an enumeration seed/no-good reference, not a scoring
incumbent.
