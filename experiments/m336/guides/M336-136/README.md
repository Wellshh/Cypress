# M336-136 Fifth d6 Rank-11 Topology

`d6-rank11-nogood4/certificate.json` is the portable all-fixed K1 certificate
for the fifth rank-11 d6 topology in the unchanged M336-122 K4096 domain. The
first four certified rank-11 tuples were excluded exactly.

```text
guide-rank:          11 (OPTIMAL after four no-goods)
HPWL:                15650.448759010085
integer HPWL:        15650448764
changed from M336-118:
  C703,FV705,FV707,FV710,R707,R708
legality:            100/100 contained, zero keep-in, zero overlap
```

A K1 replay from `/tmp` reproduced the placement bytes. One-opt maps this new
changed-support pattern to the same `47e65c62...` state as the first four
rank-11 topologies, whose certified pair closure reaches the M336-129
equal-HPWL swap plateau. This artifact is a future enumeration/no-good
reference, not a scoring incumbent.
