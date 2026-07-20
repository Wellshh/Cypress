# M336-138 Residual Portfolio Coverage

`m130-residual-k4096.json` compares M336-118 plus the six M336-130 residual
coordinate targets against the tracked M336-137 M336-122 reference.

```text
movable support:    18 page-7 components
candidate policy:   K4096, guide weights 2,1,1,1,1,1,1
model candidates:   73810
audited candidates: 73728
reference Jaccard:  0.9344326813333859
added/removed sites:2499 / 2499
```

Each residual guide first admits 9,216 sites while M336-118 admits 18,432.
Five dedicated targets have exact endpoint coverage. `PSIM2_DATA2` remains
uncovered at both endpoints: `FV710` is `2.934706 mm` from its nearest selected
site and `R708` is `0.05 mm` away. These distances are unchanged from M336-137,
despite a materially different candidate set.

The no-objective feasibility run retained the exact M336-118 placement with
100/100 containment and zero keep-in/overlap violations. The checkpoint
SHA-256 is
`2d3b41aee03cad416de6d336ae53bcf39386ceb6c044255ef087377e2f3900d9`;
all 11 dependencies match, and strict self-Jaccard is `1.0`. This artifact is
a coverage reference, not a scoring incumbent or an infeasibility proof.
