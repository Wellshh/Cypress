# M336-087: Single-Subgroup K128 Assignment Domains Cannot Reach Score 1

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `db60091`

## Problem

The certified legal placement has HPWL `15811.06557381333` and normalized
score upper bound `0.9651702157924906`. A score of 1 requires HPWL no greater
than `15260.369571786632`, before native RSMT scoring. It was unclear whether
moving one BOTTOM subgroup to an alternate keep-in region, while globally
repairing component coordinates, could close this `550.6960020266979` gap.

## Method

Each nonempty BOTTOM subgroup with an alternate region was searched
independently. The selected subgroup retained all eligible regions; every
other subgroup retained the certified hint region, but no component coordinate
was fixed. Each component-region domain retained up to 128 sites around both
the certified placement and collision-relaxed quality guide.

All runs used OR-Tools `9.15.6755`, the 0.1 mm lattice, exact decomposed
footprints, one worker, seed 1000, 30 deterministic seconds, a 180-second wall
limit, manual endpoint override `EMI601`, and integer HPWL ceiling
`15811065584`. The exact-legal hint enabled the no-regression capacity floor;
in particular, `bottom_2` used effective capacity `4317002` instead of the
configured heuristic `3548999` units.

Hint result SHA-256 is
`79a6d47798863cf90fabe34607a3b71ccf657755f4fe9aaa43e44f80fe089734`;
quality-guide SHA-256 is
`e8b947cea9c595f887bd6e747c352dd24becfbbdf7f622a2f30833e0a647a52d`.

## Evidence

Every run returned `FEASIBLE` at the source HPWL, with 100/100 exact
containment, zero keep-in violations, and zero overlaps. None is optimal, so
the status is not reported as an exact local optimum.

| Movable subgroup | Selected region | Candidates | Valid HPWL bound | Result SHA-256 |
| --- | --- | ---: | ---: | --- |
| `page_2_J201__bottom` | `bottom_0` | 12,997 | 15474.166979 | `33007b018048b9eae8d1fa4db16801ec5c10e2e200dc7524459f0fab9c5c3c17` |
| `page_3_J302__bottom` | `bottom_0` | 13,253 | 15476.166764 | `fc0f04aa9e7a67f8339c5613b546e99bb45cb1e4049428598a224b200ff32808` |
| `page_4_MIC401__bottom` | `bottom_0` | 14,533 | 15404.163863 | `9d77b8c79906058af8e18972af272242298536963e9bb430d74e1d6eecfc6d4d` |
| `page_6_EMI601__bottom` | `bottom_0` | 13,253 | 15476.166764 | `4a2f7020e1b5e62f092eea25e050f5e51d32015ab08bce929f2bc8661c988411` |
| `page_6_J601__bottom` | `bottom_0` | 14,789 | 15474.166979 | `85e4981eed78be86d8fbbbe89db64fc61c99e576e6cea87ddeeed061a05fffec` |
| `page_7_J701__bottom` | `bottom_0` | 15,045 | 15473.051513 | `c826a4538c6311d4e98f1f51a89e8fc7cb40afc7b2178025a4e5acea7a9d49a6` |
| `page_7_J702__bottom` | `bottom_0` | 15,045 | 15472.309933 | `29efd0b9cd96538ef578567a95297a4942ee28a11e143e39e17cf01af535d29f` |
| `page_86_ANT8604__bottom` | `bottom_2` | 13,509 | 15408.516085 | `04c14259f3f464cbfc909b92e745c509319a34c7c9bbe2b824abf343a144ce47` |
| `page_86_ANT8605__bottom` | `bottom_1` | 12,997 | 15473.609246 | `2cc40331f7248dd478186321db2b303dfdd983b75dd8e44e8477be33c115b337` |
| `page_86_J8601__bottom` | `bottom_0` | 12,869 | 15471.681587 | `90d0bbdad8d55883d98b077e461110ddca6e4875b8c48982361d9a9853e0ab38` |
| `page_86_U8601__bottom` | `bottom_2` | 15,557 | 15388.875602 | `9514aab73612c4295adf49f9bebceea37146352aee7c4841d020b497bf9add83` |
| `page_86_U8602__bottom` | `bottom_1` | 14,789 | 15474.565222 | `831ef97b40e0a64d01e5a4b5d5fc7f3fb24bc67fc24ba69a195dd1d246cb8f7c` |

The lowest valid bound is `15388.875602`. After subtracting the model's
`0.000304` HPWL rounding allowance, it remains `128.505726213368` above the
score-1 threshold. Therefore none of these twelve restricted K128 models can
contain a score-1 placement.

`page_3_J301__bottom`, `page_5_J503__bottom`, `page_8_J821__bottom`, and
`page_8_J822__bottom` were excluded because they contain no controlled-area
components; changing their anchor-only assignment adds no component site to
this optimization model.

## Scope and Next Step

This is not a global infeasibility result. Candidate limiting excludes most
exact sites, and fixing every other subgroup's region prevents coordinated
assignment changes. The `FEASIBLE` statuses also do not prove optimality at the
current placement. Wider K256/K512 candidate domains and coupled subgroup
release are required, prioritizing the interacting page-86 groups and the
page-4/page-6/page-7 BOTTOM groups.

The accepted placement remains unchanged, and native scoring remains blocked
by the necessary HPWL gate rather than by driver access or exact legality.
