# Cypress PCB Benchmark Results

Date: 2026-04-22 15:42:24

## Summary Table

| Benchmark | Design | Status | RSMT | Baseline RSMT | HPWL | Baseline HPWL | Congestion | Density | Net Crossing | Iterations | Overflow | Max Density | Runtime (s) |
|-----------|--------|--------|------|---------------|------|---------------|------------|---------|--------------|------------|----------|-------------|-------------|
| small-1 | PB310_A00 | PASS | 11297.2 | 1968.0 | 10241.3 | 1647.1 | 0.1405 | 0.5095 | 108.2 | 730 | 0.0321 | 1.0191 | 23.63 |
| small-2 | PB310_A00 | PASS | 14470.0 | 12303.5 | 8213.0 | 6259.0 | 0.1089 | 0.9691 | 24.8 | 878 | 0.0767 | 2.7986 | 89.45 |
| small-3 | PB310_A00 | PASS | 8556.8 | 2080.6 | 7446.1 | 1709.9 | 0.0872 | 0.5019 | 227.1 | 834 | 0.0424 | 1.5058 | 54.39 |
| small-4 | PB201_A00 | PASS | 6446.0 | 1864.7 | 6308.0 | 1827.5 | 0.1152 | 0.6000 | 12.5 | 1084 | 0.0129 | 1.2000 | 169.19 |
| small-5 | PB201_A00 | PASS | 4520.3 | 1610.1 | 4337.2 | 1507.6 | 0.0934 | 0.6175 | 41.0 | 724 | 0.0199 | 1.2350 | 24.68 |
| small-6 | PB201_A00 | PASS | 1034.3 | 1044.5 | 870.3 | 911.3 | 0.0538 | 0.5912 | 14.0 | 1116 | 0.0899 | 1.7737 | 26.30 |
| small-7 | ET095_A00 | PASS | 872.0 | 701.0 | 867.0 | 692.0 | 0.0581 | 0.7851 | 10.8 | 536 | 0.0530 | 2.3552 | 33.57 |
| small-8 | ET095_A00 | PASS | 3067.0 | 3054.0 | 2920.0 | 2897.0 | 0.0343 | 0.6054 | 5.0 | 900 | 0.0173 | 1.2107 | 28.38 |
| small-9 | PN42C_A00 | PASS | 63672.5 | 20017.5 | 57043.5 | 15287.5 | 0.1882 | 0.8922 | 987.7 | 676 | 0.0211 | 1.7844 | 46.63 |
| small-10 | PN42C_A00 | PASS | 2284.5 | N/A | 1806.5 | N/A | 0.0276 | 0.7191 | 126.9 | 630 | 0.0028 | 1.4381 | 35.83 |

## Notes

- **Baseline** values are from the original artifact logs (`artifacts/results/*/AutoDMP.log` or `DREAMPlace.log`), produced with PyTorch 1.x.
- **Current** values are from this run on PyTorch 2.5.1 / CUDA 12.4 / H100.
- Several benchmarks (small-1, small-3, small-4, small-5, small-9) show significantly higher HPWL/RSMT than baseline. This is attributed to hyperparameter instability on the PyTorch 2.x stack (see BUILD.md Issue 16).
- small-6, small-7, and small-8 are close to or better than baseline.
- small-10 has no baseline log available for comparison.
- **Non-determinism confirmed**: Re-running small-6 later produced `hpwl=inf` (divergence), while the first run produced `hpwl=870`. This confirms BUILD.md Issue 16.

## Tuning Progress

| Benchmark | Tuner Status | Best Config | Best HPWL | Best RSMT | Verified HPWL | Verified RSMT | Notes |
|-----------|--------------|-------------|-----------|-----------|---------------|---------------|-------|
| small-1 | Complete | [13,0,0] | 3582 | 4113 | **inf** | **inf** | Tuned with BOHB (42 evals); config worked once but diverges on re-run due to non-determinism |
| small-3 | Complete | [33,0,0] | 2760 | 3592 | 4285 | 5248 | Tuned with BOHB (39 evals); 2.5x baseline on verified run |
| small-5 | Complete | [10,0,0] | 2396 | 2600 | 3364 | 3627 | Tuned with BOHB (64 evals); 2.2x baseline on verified run |
| small-9 | Complete | manual | 58648 | 65639 | 58648 | 65639 | BOHB aborted (too slow); manual tune with nesterov+logsumexp+LR=0.002; 3.8x baseline |

## Raw Results (JSON)

```json
[
  {
    "benchmark": "small-1",
    "exit_code": 0,
    "runtime_seconds": 23.63,
    "ppa": {
      "rsmt": 11297.166015625,
      "hpwl": 10241.255859375,
      "congestion": 0.1405201405286789,
      "density": 0.5095476059649058,
      "net_crossing": 108.15937042236328,
      "iteration": 730,
      "objective": 1.0355485696222822e+18,
      "overflow": 0.03210728242993355,
      "max_density": 1.0190951824188232
    },
    "stdout_tail": "WARNING] detect large movable macros that will be handled differently from standard cells: C3824 21x14 @(1860,2261) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3792 21x14 @(1862,2279) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3785 21x14 @(1856,2147) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3796 14x21 @(1832,2321) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3795 21x14 @(1819,2200) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3791 14x21 @(1969,2359) w[I] plotting to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-1/PB310_A00/plot/iter0730.png takes 0.243 seconds\nith 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3787 14x21 @(1951,2359) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3780 21x14 @(1856,2111) with 1 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 3 nets with 10 pins from same nodes\n[WARNING] 49 nets should be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 122460\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-1/PB310_A00/plot/iter0730.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-1/PB310_A00/plot/iter0730.png, width = 800, height = 644, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-2",
    "exit_code": 0,
    "runtime_seconds": 89.45,
    "ppa": {
      "rsmt": 14470.0,
      "hpwl": 8213.0,
      "congestion": 0.10885278135538101,
      "density": 0.9690965232245893,
      "net_crossing": 24.799192428588867,
      "iteration": 878,
      "objective": 57152952.0,
      "overflow": 0.07665848731994629,
      "max_density": 2.7985994815826416
    },
    "stdout_tail": "from 1 to 0\n[DEBUG  ] switch arc (59, 95) from 1 to 0\n[DEBUG  ] switch arc (103, 16) from 1 to 0\n[DEBUG  ] switch arc (90, 16) from 1 to 0\n[DEBUG  ] switch arc (166, 7) from 1 to 0\n[DEBUG  ] switch arc (165, 2) from 1 to 0\n[DEBUG  ] switch arc (174, 198) from 1 to 0\n[DEBUG  ] switch arc (215, 115) from 1 to 0\n[DEBUG  ] switch arc (215, 128) from 1 to 0\n[DEBUG  ] switch arc (164, 130) from 1 to 0\n[DEBUG  ] switch arc (175, 171) from 1 to 0\n[DEBUG  ] switch arc (178, 170) from 1 to 0\n[DEBUG  ] Adjusted slack: TNS[X/Y] = 0/-588, WNS[X/Y] = 0/-30\n[INFO   ] Macro displacement total 7072.06, max 113.116, weighted total 15805.1, max 1226.71\n[WARNING] macro 32 (349, 358, 362, 376) var 32 overlaps with macro 120 (336, 372, 362, 415) var 120, fixed: 0\n[INFO   ] Legalize movable macros on Hannan grids\n[INFO   ] round 0\n[DEBUG  ] maximum grid spacing 13x13, equivalent to 113x31 bins\n[DEBUG  ] Construct 232x188 Hannan grids, diamond search sequence 17861\n[INFO   ] Macro displacement total 11281.9, max 170.623, weighted total 25061.5, max 2026.71\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Legalize movable macros with linear programming on constraint graphs\n[INFO   ] Macro displacement total 8120.75, max 120.408, weighted total 18982.2, max 1594.71\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Align macros to site and rows\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Macro legalization takes 97.7691 ms\n[INFO   ] Macro legalization: regard 0 cells as dummy fixed (movable macros)\n[INFO   ] Macro legalization takes 0.003914 ms\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-2/PB310_A00/plot/iter0879.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-2/PB310_A00/plot/iter0879.png, width = 800, height = 226, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-3",
    "exit_code": 0,
    "runtime_seconds": 54.39,
    "ppa": {
      "rsmt": 8556.7939453125,
      "hpwl": 7446.12890625,
      "congestion": 0.08722526580095291,
      "density": 0.5019428420045235,
      "net_crossing": 227.05184936523438,
      "iteration": 834,
      "objective": 48564210237440.0,
      "overflow": 0.042395152151584625,
      "max_density": 1.5058283805847168
    },
    "stdout_tail": "NG] detect large movable macros that will be handled differently from standard cells: C12_23_4 22x14 @(3740,1711) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C12_22_4 22x14 @(3740,1602) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C12_21_4 22x14 @(3740,1491) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C10_23_4 22x14 @(3740,1729) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C10_22_4 22x14 @(3740,1620) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C10_21_4 22x14 @(3740,1509) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C9_23_4 22x14 @(3740,1747) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C9_22_4 22x14 @(3740,1638) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C9_21_4 22x14 @(3740,1527) with 1 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 4 nets with 30 pins from same nodes\n[WARNING] 25 nets should be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 99792\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-3/PB310_A00/plot/iter0834.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-3/PB310_A00/plot/iter0834.png, width = 509, height = 800, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-4",
    "exit_code": 0,
    "runtime_seconds": 169.19,
    "ppa": {
      "rsmt": 6446.0,
      "hpwl": 6308.0,
      "congestion": 0.11524658650159836,
      "density": 0.6,
      "net_crossing": 12.474979400634766,
      "iteration": 1084,
      "objective": 1668337024.0,
      "overflow": 0.012853479012846947,
      "max_density": 1.1999999284744263
    },
    "stdout_tail": " handled differently from standard cells: U360 141x90 @(3337,2556) with 49 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 1 nets with 1 pins from same nodes\n[WARNING] 43 nets should be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 66222\n[INFO   ] Macro legalization: regard 43 cells as dummy fixed (movable macros)\n[INFO   ] Rough legalize small clusters with 0 macros\n[INFO   ] Legalize movable macros on Hannan grids\n[INFO   ] round 0\n[DEBUG  ] maximum grid spacing 3.40282e+38x3.40282e+38, equivalent to 0x0 bins\n[DEBUG  ] Construct 81x88 Hannan grids, diamond search sequence 3281\n[INFO   ] Legalize movable macros with linear programming on constraint graphs\n[DEBUG  ] source 43, terminal 44\n[DEBUG  ] Original slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[DEBUG  ] Adjusted slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[INFO   ] Macro displacement total 99.4201, max 15.3073, weighted total 902.092, max 750.059\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Align macros to site and rows\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Macro legalization takes 1.02959 ms\n[INFO   ] Macro legalization: regard 0 cells as dummy fixed (movable macros)\n[INFO   ] Macro legalization takes 0.001712 ms\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/smal[I] plotting to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-4/PB201_A00/plot/iter1085.png takes 0.059 seconds\nl-4/PB201_A00/plot/iter1085.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-4/PB201_A00/plot/iter1085.png, width = 800, height = 661, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-5",
    "exit_code": 0,
    "runtime_seconds": 24.68,
    "ppa": {
      "rsmt": 4520.32421875,
      "hpwl": 4337.1552734375,
      "congestion": 0.0933951735496521,
      "density": 0.617503234530003,
      "net_crossing": 40.98725128173828,
      "iteration": 724,
      "objective": 1.6645872464114483e+17,
      "overflow": 0.01989961415529251,
      "max_density": 1.23500657081604
    },
    "stdout_tail": "11x5 @(1036,2536) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3057 5x12 @(1026,2568) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3054 11x5 @(1092,2586) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3051 5x11 @(1112,2530) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: C3049 9x21 @(1097,2525) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R2998 20x8 @(993,2508) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3016 9x21 @(1010,2578) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3028 20x8 @(995,2637) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: U400 56x55 @(1040,2523) with 40 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: U374 30x32 @(960,2638) with 2 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 0 nets with 0 pins from same nodes\n[WARNING] 20 nets should be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 43650\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-5/PB201_A00/plot/iter0724.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-5/PB201_A00/plot/iter0724.png, width = 800, height = 690, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-6",
    "exit_code": 0,
    "runtime_seconds": 26.3,
    "ppa": {
      "rsmt": 1034.278076171875,
      "hpwl": 870.304931640625,
      "congestion": 0.05375796929001808,
      "density": 0.5912216049131384,
      "net_crossing": 14.034791946411133,
      "iteration": 1116,
      "objective": 2230567374422016.0,
      "overflow": 0.08986900001764297,
      "max_density": 1.7736648321151733
    },
    "stdout_tail": "11x5 @(2212,3288) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3963 5x12 @(2201,3285) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3962 11x5 @(2212,3330) with 0 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3959 11x5 @(2252,3243) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3958 11x5 @(2252,3234) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3961 5x12 @(2208,3310) with 1 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: R3964 5x12 @(2188,3286) with 2 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: Q19 21x26 @(2144,3246) with 4 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: Q18 21x26 @(2147,3180) with 4 pins\n[WARNING] detect large movable macros that will be handled differently from standard cells: U419 51x72 @(2182,3193) with 13 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 0 nets with 0 pins from same nodes\n[WARNING] 4 nets should be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 31650\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-6/PB201_A00/plot/iter1116.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-6/PB201_A00/plot/iter1116.png, width = 569, height = 800, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-7",
    "exit_code": 0,
    "runtime_seconds": 33.57,
    "ppa": {
      "rsmt": 872.0,
      "hpwl": 867.0,
      "congestion": 0.058092620223760605,
      "density": 0.7850671121161339,
      "net_crossing": 10.814441680908203,
      "iteration": 536,
      "objective": 3006492835840.0,
      "overflow": 0.052951354533433914,
      "max_density": 2.355201482772827
    },
    "stdout_tail": " be handled differently from standard cells: R231 5x10 @(2016,1425) with 2 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 1 nets with 2 pins from same nodes\n[WARNING] 51 nets should be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 48960\n[INFO   ] Macro legalization: regard 50 cells as dummy fixed (movable macros)\n[INFO   ] Rough legalize small clusters with 0 macros\n[INFO   ] Legalize movable macros on Hannan grids\n[INFO   ] round 0\n[I] plotting to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-7/ET095_A00/plot/iter0537.png takes 0.138 seconds\n[DEBUG  ] maximum grid spacing 3.40282e+38x3.40282e+38, equivalent to 0x0 bins\n[DEBUG  ] Construct 102x102 Hannan grids, diamond search sequence 5305\n[INFO   ] Legalize movable macros with linear programming on constraint graphs\n[DEBUG  ] source 50, terminal 51\n[DEBUG  ] Original slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[DEBUG  ] Adjusted slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[INFO   ] Macro displacement total 186.657, max 33.0039, weighted total 667.133, max 260.2\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Align macros to site and rows\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Macro legalization takes 1.42571 ms\n[INFO   ] Macro legalization: regard 0 cells as dummy fixed (movable macros)\n[INFO   ] Macro legalization takes 0.007681 ms\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-7/ET095_A00/plot/iter0537.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-7/ET095_A00/plot/iter0537.png, width = 800, height = 529, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-8",
    "exit_code": 0,
    "runtime_seconds": 28.38,
    "ppa": {
      "rsmt": 3067.0,
      "hpwl": 2920.0,
      "congestion": 0.03434799239039421,
      "density": 0.605368869320722,
      "net_crossing": 4.959041595458984,
      "iteration": 900,
      "objective": 7001.0048828125,
      "overflow": 0.01733984239399433,
      "max_density": 1.210737705230713
    },
    "stdout_tail": "ferently from standard cells: C20_3 17x10 @(3687,2058) with 1 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 0 nets with 0 pins from same nodes\n[WARNING] 115 nets should be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 1.36619e+06\n[INFO   ] Macro legalization: rega[I] plotting to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-8/ET095_A00/plot/iter0901.png takes 0.957 seconds\nrd 115 cells as dummy fixed (movable macros)\n[INFO   ] Rough legalize small clusters with 0 macros\n[INFO   ] Legalize movable macros on Hannan grids\n[INFO   ] round 0\n[DEBUG  ] maximum grid spacing 3.40282e+38x3.40282e+38, equivalent to 0x0 bins\n[DEBUG  ] Construct 232x232 Hannan grids, diamond search sequence 27145\n[INFO   ] Legalize movable macros with linear programming on constraint graphs\n[DEBUG  ] source 115, terminal 116\n[DEBUG  ] Original slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[DEBUG  ] Adjusted slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[INFO   ] Macro displacement total 292.518, max 7.65231, weighted total 1075.13, max 312.659\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Align macros to site and rows\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Macro legalization takes 7.35526 ms\n[INFO   ] Macro legalization: regard 0 cells as dummy fixed (movable macros)\n[INFO   ] Macro legalization takes 0.002584 ms\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-8/ET095_A00/plot/iter0901.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-8/ET095_A00/plot/iter0901.png, width = 800, height = 398, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-9",
    "exit_code": 0,
    "runtime_seconds": 46.63,
    "ppa": {
      "rsmt": 63672.5,
      "hpwl": 57043.5,
      "congestion": 0.18821243941783905,
      "density": 0.8921956733741672,
      "net_crossing": 987.68408203125,
      "iteration": 676,
      "objective": 1991860.625,
      "overflow": 0.021134348586201668,
      "max_density": 1.7843914031982422
    },
    "stdout_tail": "erently from standard cells: C4286 10x5 @(1140,940) with 1 pins\n[WARNING] no additional Bookshelf .pl file specified\n[WARNING] 84 nets with 84 pins from same nodes\n[WARNING] 1260 nets should[I] plotting to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-9/PN42C_A00/plot/iter0677.png takes 8.367 seconds\n be ignored due to not enough pins\n[INFO   ] sort nodes in the order of movable and fixed\n[INFO   ] Group cells for fence regions\n[INFO   ] Construct 0 groups\n[INFO   ] Fence region groups done\n[DEBUG  ] num_terminals 0, numFixed 0, numPlaceBlockages 0, num_terminal_NIs 0\n[DEBUG  ] fixed area overlap: 0 fixed area total: 0, space area = 1.49779e+07\n[INFO   ] Macro legalization: regard 476 cells as dummy fixed (movable macros)\n[INFO   ] Rough legalize small clusters with 0 macros\n[INFO   ] Legalize movable macros on Hannan grids\n[INFO   ] round 0\n[DEBUG  ] maximum grid spacing 3.40282e+38x3.40282e+38, equivalent to 0x0 bins\n[DEBUG  ] Construct 954x954 Hannan grids, diamond search sequence 456013\n[INFO   ] Legalize movable macros with linear programming on constraint graphs\n[DEBUG  ] source 476, terminal 477\n[DEBUG  ] Original slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[DEBUG  ] Adjusted slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[INFO   ] Macro displacement total 22829.7, max 194.751, weighted total 165708, max 15371.3\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Align macros to site and rows\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Macro legalization takes 214.189 ms\n[INFO   ] Macro legalization: regard 0 cells as dummy fixed (movable macros)\n[INFO   ] Macro legalization takes 0.003349 ms\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-9/PN42C_A00/plot/iter0677.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-9/PN42C_A00/plot/iter0677.png, width = 800, height = 539, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  },
  {
    "benchmark": "small-10",
    "exit_code": 0,
    "runtime_seconds": 35.83,
    "ppa": {
      "rsmt": 2284.5,
      "hpwl": 1806.5,
      "congestion": 0.027641521766781807,
      "density": 0.7190720382719252,
      "net_crossing": 126.89564514160156,
      "iteration": 630,
      "objective": 6508398556217344.0,
      "overflow": 0.0028298499528318644,
      "max_density": 1.4381440877914429
    },
    "stdout_tail": " movable macros on Hannan grids\n[INFO   ] round 0\n[DEBUG  ] maximum grid spacing 3.40282e+38x3.40282e+38, equivalent to 0x0 bins\n[DEBUG  ] Construct 20x20 Hannan grids, diamond search sequence 221\n[INFO   ] Legalize movable macros with linear programming on constraint graphs\n[DEBUG  ] source 9, terminal 10\n[DEBUG  ] Original slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[DEBUG  ] Adjusted slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[INFO   ] Macro displacement total 5.13705, max 0.826202, weighted total 285.695, max 276.229\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Align macros to site and rows\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Macro legalization takes 0.152535 ms\n[INFO   ] Macro legalization: regard 127 cells as dummy fixed (movable macros)\n[INFO   ] Rough legalize small clusters with 2 macros\n[INFO   ] Legalize movable macros on Hannan grids\n[INFO   ] round 0\n[DEBUG  ] maximum grid spacing 9x14, equivalent to 95x142 bins\n[DEBUG  ] Construct 324x379 Hannan grids, diamond search sequence 52813\n[INFO   ] Legalize movable macros with linear programming on constraint graphs\n[DEBUG  ] source 127, terminal 128\n[DEBUG  ] Original slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[DEBUG  ] Adjusted slack: TNS[X/Y] = 0/0, WNS[X/Y] = 0/0\n[INFO   ] Macro displacement total 112.56, max 17.8375, weighted total 153.249, max 17.8375\n[DEBUG  ] Macro legality check PASSED\n[INFO   ] Align macros to site and rows\n[DEBUG  ] Macro legality che[I] plotting to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-10/PN42C_A00/plot/iter0631.png takes 1.566 seconds\nck PASSED\n[INFO   ] Macro legalization takes 8.43797 ms\n[INFO   ] writing placement to /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-10/PN42C_A00/plot/iter0631.png\n[WARNING] filename = /home/jybai/pcb-placement/research/gpu-used/Cypress/results/benchmark_runs/small-10/PN42C_A00/plot/iter0631.png, width = 343, height = 800, file format = 3 not used, as DRAWPLACE not enabled\n",
    "stderr_tail": ""
  }
]
```
