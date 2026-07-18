# M336-029: Site Elements Throttle Coordinate Packing Search

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-18
**Affected commit:** `c9df8af`

## Problem

The discrete solver represented each component with a site-index variable and
three `Element` constraints mapping that index to x, y, and region. TOP domains
contain only 55–65 y rows and 74–110 x values per component, but the indirect
encoding retained 50,425 site rows. `NoOverlap2D` therefore propagated through
index mappings rather than a direct discrete coordinate relation.

## Correction

The optional `--site-model coordinate-table` encoding creates explicit x and y
integer domains and adds an allowed `(x, y, region_option)` tuple table. It uses
the same candidate sites, assignment variables, exact footprint constraints,
HPWL expressions, and final geometry validator. The original `element` model
remains the default pending broader evidence.

Solved coordinates are reverse-mapped to exactly one region-local site. A
missing or ambiguous mapping fails instead of silently choosing a candidate.

## Equivalence Evidence

A single-worker fixed replay of the known legal runtime-anchor grid01 placement
was `OPTIMAL` with zero branches, 100/100 containment, and zero overlaps. Both
encodings wrote placement SHA-256
`fbbbf6b3e3f81e84e578d16b3e01ba78f28ed67ae241065ac44146e20ba50cfe`.
Coordinate-table solver time was `0.132902 s`, versus `0.267033 s` for the
existing element replay.

## Search A/B

The restored-anchor TOP packing used the same 50,425 candidates, 656 exact part
constraints, seed 1000, eight workers, and 300-second limit.

| Encoding | Status | Branches | Conflicts | Peak RSS |
| --- | --- | ---: | ---: | ---: |
| `element` | `UNKNOWN` | 391,220 | 12,134 | about 2.01 GB |
| `coordinate-table` | `UNKNOWN` | 3,812,716 | 1,186,130 | 1,106,532 KiB |

The new encoding cuts measured peak memory by about 45% and explores more
search nodes, but it did not produce a candidate. This is a model-efficiency
improvement, not evidence of packing feasibility or score improvement.

## Verification

- M336 baseline tests pass 28/28, including unique coordinate-to-site lookup.
- Exact fixed replay preserves placement bytes and legality.
- Model reports identify the selected site encoding.

## Residual Risk

Allowed tuple tables may perform worse for other assignments or grid sizes.
Keep the option experimental until deterministic single-worker comparisons and
a restored-anchor feasible candidate are available.
