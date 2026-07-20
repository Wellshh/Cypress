# M336-139 Full-Domain Target Audit

`m130-target-domain.json` replays the M336-138 residual portfolio and extends
its candidate audit from selected K4096 sites to the complete keep-in and
uncontrolled-obstacle-free domains.

```text
reference candidate Jaccard: 1.0 (73728 / 73728)
PSIM2_DATA2 FV710:
  exact keep-in lattice:      yes
  fixed blocker:              MIC401, 0.081943924 mm2
  nearest obstacle-free site: 2.934706 mm
PSIM2_DATA2 R708:
  exact keep-in lattice:      yes
  fixed blocker:              MIC401, 0.013330545 mm2
  nearest obstacle-free site: 0.050000 mm
```

The other five dedicated residual guides have exact obstacle-free endpoint
coverage. The no-objective solve retained byte-identical M336-118 placement,
100/100 containment, and zero keep-in/overlap violations.

Checkpoint SHA-256 is
`d21a6dc381038efc918e0e2384fae4b82e43a5857dc002ee09714c7d77df89c0`.
All 11 dependencies match and strict self-Jaccard is `1.0`. This artifact is a
domain-classification reference, not a scoring incumbent or infeasibility
proof for alternative exact DATA2 placements.
