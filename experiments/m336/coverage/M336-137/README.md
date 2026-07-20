# M336-137 Candidate Coverage Baseline

`m122-page7-k4096.json` is the portable candidate-coverage reference for the
unchanged M336-122 page-7 domain:

```text
source:            M336-118 checkpoint
movable support:   18 page-7 components
candidate policy:  K4096, guide weights 2,2,1,1,2
model candidates:  73810
audited candidates:73728
grid:              0.05 mm
collisions:        exact BOTH sides
```

The five guides first admit `18432,18432,9216,9216,18432` selected sites. The
page-7 quality-hybrid target is exactly present for 16/18 components, but not
for either `PSIM2_DATA2` endpoint: `FV710` is `2.934706 mm` from its nearest
candidate and `R708` is `0.05 mm` away.

The checkpoint stores exact selected region indices, full-domain fingerprints,
dependency hashes, endpoint coverage, and target distances. Its SHA-256 is
`de03e8caaa401f7d79c29b35d92eb94428fe96392677b89ba1177215c1a2470e`.
A strict self-comparison covers all 73,728 audited sites with Jaccard `1.0`.
Use it as the reference input for later portfolio comparisons; it is not a
scoring incumbent or an infeasibility certificate.
