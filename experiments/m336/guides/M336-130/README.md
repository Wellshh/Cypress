# M336-130 Residual Topology Portfolio

This directory records the first deterministic residual-net-specific topology
portfolio derived from M336-118. None of these states is a scoring incumbent.
The incumbent remains `experiments/m336/checkpoints/M336-118/`.

## Coordinate Targets

`targets/*.json` are hybrid coordinate guides, not legal placements. They take
only the named residual endpoints from the M336-121 page-7 quality target and
keep every other component at M336-118. Each file records the source and target
SHA-256, selected refdes, and displacement. The common source and target hashes
are respectively:

```text
d09c60f111d3987ea7bb2c60e6a05edf23dc699213a4717bf4d4dba339de99bb
0c3f83fd4d7510d316c3b08332124a5689f4b3340522fd8d41e10ccb907c2f46
```

## Certified Families

Each named subdirectory contains an all-fixed K1-certified, exact-legal,
portable topology and a SHA-256 manifest.

| Family | Actual changes from M336-118 | HPWL | Rise |
| --- | --- | ---: | ---: |
| `vsim2` | `C703,FV707,R707` | 15647.449081 | 12.998604 |
| `sim-det1` | `FV705,FV708` | 15637.950585 | 3.500107 |
| `psim2-data2` | `R708` | 15636.950263 | 2.499785 |
| `nfc-swp` | `FV705,FV706` | 15652.448544 | 17.998067 |
| `psim2-srst2` | `C404,FV708` | 15635.450370 | 0.999893 |
| `psim2-sclk2` | `FV704,FV709` | 15645.449296 | 10.998819 |
| `d6-chain` | `C703,FV705,FV707,FV708,R707,R708` | 15653.448974 | 18.998496 |

All families have 100/100 containment, zero keep-in violations, zero exact
overlaps, and complete objective/per-net replay. The unexpected partners
`FV704`, `FV705`, `FV708`, and especially cross-page `C404` are measured
physical/network closure evidence; they are not inferred residual endpoints.

Use `certificate.json` as the portable entry point. Treat `targets/` only as
guide inputs and never promote a family unless an independent HPWL closure is
strictly below M336-118 and passes a fresh all-fixed certification.
