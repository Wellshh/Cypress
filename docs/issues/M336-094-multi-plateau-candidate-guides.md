# M336-094: Multi-Plateau K256 Guides Do Not Change the Incumbent

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `5a64ee4`

## Problem

M336-092 showed that changing only the CP-SAT seed does not leave the current
K256 incumbent. Two exactly legal equal-HPWL placements remain available as
distinct candidate centers: one changes `B402,C402,C8602,R605`, and the other
changes `FV703,FV704`. Their topology could alter candidate ordering even
though their HPWL equals the certified source.

## Method

Eight 80-component K256 models used four candidate guides in fixed order:
current certified, collision-relaxed quality, four-site plateau, and two-site
page-7 plateau. The certified current result remained the independent solver
hint. Four seeds tested balanced weights `1:1:1:1`; four tested quality-biased
weights `1:3:1:1`. All runs used exact fixed assignment and collisions, one
worker, and 300 deterministic seconds.

The runs began before M336-093 isolated context directories, but every process
used the same assignment, grid, clearance, and generated context content. All
completed without a context parse failure. Different-config concurrent runs
remain prohibited before that fix.

## Evidence

| Weights | Seed | Status | HPWL | Valid bound | Result SHA-256 |
| --- | ---: | --- | ---: | ---: | --- |
| `1:1:1:1` | 1000 | `FEASIBLE` | 15811.065574 | 14733.521304 | `5f2795bd4e0ec36ce015a9c2cbb2c275027584d6635e3382e4746e138f61adab` |
| `1:1:1:1` | 1001 | `FEASIBLE` | 15811.065574 | 14754.606706 | `398f452a47158af0b9e1b07841dc9b98031e51b68dc6ccf0eaf821b940f11bc7` |
| `1:1:1:1` | 1002 | `FEASIBLE` | 15811.065574 | 14733.521304 | `a538552c21e900a1312f87197192efe7b818d87a76831cb7e832b2c299a5aa43` |
| `1:1:1:1` | 1003 | `FEASIBLE` | 15811.065574 | 14724.679537 | `c3ee681863046baae3a1666c4a5ca7f2882a629ee6df373949f2a509d0cbeb30` |
| `1:3:1:1` | 1000 | `FEASIBLE` | 15811.065574 | 14711.314959 | `581d64fd29ecda0617a021330638b1c44cf1e3aa83299fa94b2a6e8a2f5af421` |
| `1:3:1:1` | 1001 | `FEASIBLE` | 15811.065574 | 14713.314744 | `9bd2eb6bf5db628a6687354b3c52003c3f4ea0913323b9c47185feae4abf232d` |
| `1:3:1:1` | 1002 | `FEASIBLE` | 15811.065574 | 14728.951038 | `46a3085c0f3ec86f928420e8321a46a98edd405f44ce8a2f99de6cdfaa1caaca` |
| `1:3:1:1` | 1003 | `FEASIBLE` | 15811.065574 | 14712.286843 | `c4ab3bcfc6835da14eb6fe3579f489d602ef6d17d5d186cea598444dd8df32e6` |

Every result passes integer objective replay, 100/100 containment, zero
violations, and zero overlaps. All eight placement files are byte-identical to
the certified source with SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`.
The score-permitting lower bounds prevent an optimality claim.

## Directed Guide

The next guide replaces only the 18 BOTTOM page-7 refdes with quality-guide
sites and keeps the other 82 current sites. `FV702` is already at the quality
coordinate, so 17 centers actually differ. The guide is explicitly marked
`guide_only`, contains all 100 selected-site identities, and has SHA-256
`cd27a437fedc7190227957dd8f143ece147613868573cc28b5dbf23683222b47`.

This guide must affect candidate ordering only; it is neither a legal hint nor
an acceptance candidate. Use it to allocate quality-directed width to page 7
while retaining current-centered neighborhoods elsewhere.
