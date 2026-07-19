# M336-097: One CP-SAT Hint Cannot Express Incumbent And Escape Topology

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `d24c33e`

## Problem

Monotonic continuation needs the certified current placement available as an
incumbent while search branches toward a different exact-legal topology.
`probe_exact_site_cpsat.py` can provide one complete CP-SAT hint, but that hint
cannot simultaneously encode both states. Candidate guides alter domain
selection only; they do not install another incumbent or force the solver to
visit the guided topology.

The current integer HPWL is `15811065584`. The page-7 escape hint is
independently fixed-site certified and legal, but has worse integer HPWL
`15821064510`. Under the current hard ceiling it is therefore an infeasible
hint even though the model itself has a known feasible current solution.

## Controlled Hint Ablation

Eight otherwise identical 80-component K256 models used exact BOTH-side
collisions, fixed assignment, current/page-7-hybrid/escape candidate guides
weighted `1:3:4`, one worker, 300 deterministic seconds, and hard ceiling
`15811065584`.

| Hint | Seed | Status | HPWL | Valid bound | Result SHA-256 |
| --- | ---: | --- | ---: | ---: | --- |
| current | 1000 | `FEASIBLE` | 15811.065574 | 14854.437478 | `f9dec3e52d683f07257d32bcc7e26e49681f78cd04ac74ea4363309acdeef0c9` |
| current | 1001 | `FEASIBLE` | 15811.065574 | 14858.437048 | `ec41a8e45db326fa4eb256880586337491f762605c5268303fcdcc65681dcf7d` |
| current | 1002 | `FEASIBLE` | 15811.065574 | 14854.437478 | `46e81248efa1cba86f075099e9e054f032c8d63913be6377e5b05d5ad9ff46c5` |
| current | 1003 | `FEASIBLE` | 15811.065574 | 14854.437478 | `b0c7e1007802dafb072fdd78f77407bb977084e13d18cb3a298b2db162bf8b8a` |
| escape | 1000 | `UNKNOWN` | none | 14854.437478 | `46083afaad31d88d560561e38ed03c437c6260a138431dddb02ec76bcf9ea1d0` |
| escape | 1001 | `UNKNOWN` | none | 14871.116754 | `8a674ca5d79a05d6c302f968725f5db13e38bdd0d8aef0d72e5bada6471e842e` |
| escape | 1002 | `UNKNOWN` | none | 14863.755410 | `15e7024aa5bfd79b10fa8bcd89e5bc03e4b98988b547fc23a1b3e912f4d65fe0` |
| escape | 1003 | `UNKNOWN` | none | 14880.113962 | `671b6e4171eeccabe5d10f4092558a3ee810038b8c8498129350db0a577a9db6` |

All current-hint placements are byte-identical to the certified source and
pass objective replay plus exact legality. Every escape-hint run exhausted its
budget with no incumbent; script exit code 2 correctly represents `UNKNOWN`,
not an execution failure. The score-permitting bounds prohibit any
infeasibility claim.

## Deeper Candidate Guides

Two sorted full-quality escape states were separately fixed-site certified:

- 44 moves, HPWL `15896.962164053146`, placement SHA-256
  `f6274c2b38f96a357f660d29a414091fd2fd9cc5dab704d0b66e06055e56deb9`;
- 50 moves, HPWL `16082.446269567727`, placement SHA-256
  `3a7cc069ec160d486da9ea2e2fb0182210c28bf51052e9f5ec394785674074ac`.

Four current-hint K256 runs then used current, collision-relaxed quality, and
both certified deep states as candidate guides weighted `1:2:3:3`. Seeds
1000-1003 all retained current HPWL and exact legality. Their valid bounds
range from `14729.564502` to `14755.057107`; result SHA-256 values are:

- `62e59a31adb4318196c392d55067ff4c57f29c5b49550daede5691b0f0529040`;
- `fb57be384ef906f08f7a62f0f0c8f4fb767e7a85967ed1c4e9cc758533999c09`;
- `8e85a0a88a8088a497bbe328cf749e21bdeb6e720b9c428e0cf1762e4e89ff8e`;
- `a389914602283cfb60a42c99d47097d198d30f2875d8733acd7802c0483a339f`.

Thus materially different legal centers in the candidate domain do not solve
the one-hint limitation.

## Required Action

Do not call escape-hint `UNKNOWN` runs infeasible and do not remove the hard
ceiling from production continuation. Test a deterministic search policy that
keeps the current complete hint for incumbent construction but orders site
branching from a declared escape guide. Any policy must record its branching
mode and retain one-worker replay. A no-ceiling escape-hint run may be used
only as quarantined exploration; it cannot replace the monotonic acceptance
path, and only a strict independently certified improvement may be promoted.
