# M336-042: Score-Feasible Guide Requires Near-Global Repacking

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `ec84609`

## Problem

The collision-relaxed exact-site result
`results/m336/discrete_two_anchor/result-no-collision.json` is the only known
restored-anchor guide above the manual score gate. Its HPWL is `14114.924192`
and its necessary normalized score upper bound is `1.081151`, but it disables
collision constraints and has 310 full-board overlaps. The validator-aligned
CNF model was used to determine whether its 30 controlled TOP positions admit
a local exact repair without abandoning that quality neighborhood.

## Guide-Centered Domains

The nearest fixed-obstacle-free K256 domain has 7,436 candidates and 2,873,465
pair-conflict clauses. It is `UNSAT` in 0.026 seconds. Building K512 while
assuming every component remains in K256 gives the following sufficient
domain-core chain:

| Released to K512 | Status | Time (s) | Next K256 core |
| ---: | --- | ---: | --- |
| 0 | `UNSAT` | 0.118 | `C601` |
| 1 | `UNSAT` | 88.001 | 14 components |
| 15 | `UNSAT` | 0.975 | 8 components |
| 23 | `UNKNOWN` | 300.050 | none |
| All 30 | `UNKNOWN` | 900.037 | none |

The 14-component core is `C201 C202 C301 C604 C611 C612 C8653 FV607
FV618 L8606 L8607 L8626 L8630 R602`. The next core is `C203 C701 FV301
FV601 FV602 FV617 R604 RT201`. `UNKNOWN` is only a timeout and does not prove
K512 feasible or infeasible.

## Fixed-Site Core Chain

Fixing each component at its nearest retained guide site exposes why local
repair is ineffective. Unfixed components retain all K512 candidates.

| Movable | Fixed | Status | Time (s) | Next sufficient fixed core |
| ---: | ---: | --- | ---: | --- |
| 0 | 30 | `UNSAT` | 0.114 | `C201 C202` |
| 2 | 28 | `UNSAT` | 0.119 | `C203 C204` |
| 4 | 26 | `UNSAT` | 0.120 | `C501 C502` |
| 6 | 24 | `UNSAT` | 0.113 | `C601` |
| 7 | 23 | `UNSAT` | 0.117 | `C301 C604` |
| 9 | 21 | `UNSAT` | 0.117 | `C611 C612` |
| 11 | 19 | `UNSAT` | 0.113 | `FV301` |
| 12 | 18 | `UNSAT` | 0.114 | `FV601 FV602` |
| 14 | 16 | `UNSAT` | 0.116 | `FV604 FV607` |
| 16 | 14 | `UNSAT` | 0.116 | `C701 FV617` |
| 18 | 12 | `UNSAT` | 0.115 | `C8653 FV618` |
| 20 | 10 | `UNSAT` | 0.140 | `L8607 L8626` |
| 22 | 8 | `UNSAT` | 0.117 | `FV701 R604` |
| 24 | 6 | `UNSAT` | 0.235 | `L8606 L8630 R602 R704` |
| 28 | 2 | `UNSAT` | 92.691 | `R605 RT201` |
| 29, `RT201` fixed | 1 | `UNSAT` | 84.625 | `RT201` |
| 29, `R605` fixed | 1 | `UNKNOWN` | 300.061 | none |

This is a sufficient release path, not a minimum-movement proof. It does prove
that the retained `RT201` guide site cannot participate in any K512 solution.

## Dual-Guide Control

A deterministic round-robin domain combined equal quotas around the score
guide and the one-overlap feasibility guide from M336-039. The mixed K256
domain (128 nearest unique sites per guide) was `UNSAT` in 11.372 seconds.
K512 constrained to that K256 subset was `UNSAT` in 56.817 seconds with a
22-component core. Releasing all 22 was `UNKNOWN` after 300.127 seconds, and
full mixed K512 was `UNKNOWN` after 901.142 seconds. Candidate diversity alone
did not produce a legal state.

As a non-proof control, two 100,000-step weighted-breakout restarts over full
domains reached two exact overlaps, HPWL `22990.549301`, and score upper bound
`0.663767`. Conflict repair again destroyed the guide's quality potential.

Key evidence SHA-256 values are:

```text
score K256:             9846de10b9ba5b42c3f1ce0451f21510091d4295de83890fed5a17d9c562f8df
score K512/K256:        ae92d3efe5b30bfabaa7898ec838ace5a3d410c927af67079f362fc013952274
score full K512:        e674beaa3b0f7c1ce7eef3f5dafeb7fa65a588d5a87f14ec5eeffa6312c6f20d
fixed 28/2:             f59c5c09494d57a71e4854e4c4dee188ff8414247eb380f9f7dc85956ca0273b
fixed RT201:            d6b6d9c73c1ea9b43a3242261380fd405fbb9e9dc959b795dda4ccd407113856
fixed R605:             ea14b152cb8bb942c3f7e319cf825c2bbbadeff8ee6d2e217508e0039d82e146
mixed K256:             0be0e33b991d85f79a18934dc765f927b654454a34044de79945d93fed130432
mixed K512/K256:        f4b543587dda1109c511b7076b1142db865d8e39f8c4157dd46b66dcd0a7fd9f
mixed full K512:        d9c7cea6387c8f781dde0c528ed5d63bd7fc99e8387883bf5d2614d784f6d39d
weighted-breakout:      baecab065315b6dabbe17f260849765546a70b5a3f4722b130046b395f272f95
```

## Acceptance Impact

No SAT placement was produced, so exact legality, native RSMT, and score remain
unmet. The next exact search should selectively widen `RT201` and subsequent
cores beyond K512 instead of globally multiplying every domain. A survivor
must then be merged with the known legal BOTTOM placement, pass full-board
Shapely validation and one-worker replay, and achieve native normalized
HPWL/RSMT score `>= 1.0`.
