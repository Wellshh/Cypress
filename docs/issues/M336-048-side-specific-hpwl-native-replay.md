# M336-048: Couple Side Packing to HPWL and Native Replay

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `5d4a28e`

## Problem

The EMI-only path could pack TOP exactly, but the probe only optimized guide
rank and emitted partial site maps. It could neither constrain full-board HPWL
while packing BOTTOM nor produce a placement suitable for native FLUTE RSMT
scoring. Consequently, an optimistic HPWL bound could be mistaken for an
accepted score and transient JSON could not be replayed independently.

## Findings

The probe now packs either side, retains all 100 selected sites, and models
the exact weighted pin HPWL against fixed opposite-side coordinates. A
fixed-site equivalence check produced CP HPWL `21493.113779` versus float
HPWL `21493.113773`, an error of `0.000006` below the conservative `0.000304`
rounding allowance.

Using the collision-relaxed EMI-only guide, exact BOTTOM domains K64, K128,
and K256 are infeasible; K512 remained `UNKNOWN` at 500 deterministic-time.
Mixing the score guide with a known-legal guide found exact legal K256
placements at HPWL `18725.306432`, improved to `18523.289517` by guide-rank
minimization, but both miss the necessary HPWL threshold `15260.369572`.

Optimizing TOP K512 with exact collisions and the score gate produced a
`FEASIBLE` TOP state at HPWL `14819.892320`. It has zero TOP overlaps and
leaves 440.477252 HPWL for BOTTOM legalization. Result SHA-256 is
`b1b9dcbf20cb8c28de8b8830f04312fb708a1e8cc430f083de59154dbee539c1`.
With that TOP fixed, the final BOTTOM K256 domain is exactly infeasible. K512
remained `UNKNOWN` after 500.000006 deterministic-time, 4,371,530 branches,
and 1,155,391 conflicts; its HPWL lower bound was `14797.604030`, so the
score domain is not ruled out. Result SHA-256 is
`54fe5f1744edc0a62edd553c6ab5b04835b1ea63259a93aa0b6207210b7635f5`.

A selectable legal hint was also tested. The merged legal skeleton has
100/100 containment, zero violations/overlaps, and HPWL `18070.692761`.
Repairing its mixed K256 score domain returned `UNKNOWN`, not infeasible, at
200.002068 deterministic-time with 34,496 branches and zero conflicts. This
indicates `repair_hint` stalled near a legal but low-quality state and must not
be promoted as the default strategy.

## Native Acceptance Audit

`score_exact_site_result.py` independently reconstructs all sites, repeats
exact validation before and after `.pl` serialization, and runs the baseline
native HPWL/FLUTE RSMT path without placement iterations. It then compares all
140 input and replayed coordinates. A legal negative-control placement had
zero coordinate drift and native HPWL/RSMT `21228.726562/22973.886719`, giving
score `0.691654`; the scorer correctly wrote evidence and exited `2`.
Serialization changed HPWL by `0.014741` but preserved exact legality. Native
replay was repeated with identical placement SHA-256
`99c73dc8b789dfb099f969fe352aef45482b2185e274243ba182d30590680ba9`,
native metrics, and zero coordinate drift. The result containing full input
hashes has SHA-256
`0b8f739ec326fa2ef2c499488f4e8322577a9cc5c8fbbf130db6a41351d73199`.

## Resolution Criteria

Do not infer infeasibility from either `UNKNOWN` run. Continue deterministic
K512 search from score-directed domains without `repair_hint`, then require:

- full containment with zero exact overlaps after `.pl` serialization;
- native replay coordinate error exactly zero;
- native normalized HPWL/RSMT score at least `1.0`;
- a second replay with matching placement hash and native metrics;
- promotion of the EMI601 endpoint policy out of diagnostic-only flags before
  claiming an E1-E4 production result.
