# M336-134 Third d6 Rank-11 Topology

`d6-rank11-nogood2/certificate.json` is the portable all-fixed K1 certificate
for the third rank-11 d6 topology in the unchanged M336-122 K4096 domain. The
M336-131 and M336-133 rank-11 tuples were excluded exactly.

```text
guide-rank:          11 (OPTIMAL after two no-goods)
HPWL:                15650.448759010082
integer HPWL:        15650448765
changed from M336-118:
  C703,FV707,FV708,FV710,R707,R708
legality:            100/100 contained, zero keep-in, zero overlap
```

A K1 replay launched from `/tmp` using only this portable certificate and its
tracked assignment returned the same objective and placement bytes.

This topology combines the `FV710` and `R708` choices that appeared separately
in M336-131 and M336-133. One-opt maps all three topologies to placement SHA
`47e65c62fe82959c717235152fb5244355a530c805a1847ad17cd976c32cc97c`;
the already certified pair closure maps those exact bytes to the M336-129
equal-HPWL swap plateau. This artifact is an enumeration/no-good reference,
not a scoring incumbent.
