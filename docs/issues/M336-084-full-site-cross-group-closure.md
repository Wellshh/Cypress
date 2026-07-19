# M336-084: Full-Site Cross-Group Closure

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `404ff71`

## Problem

M336-080 proved each major bottom-0 physical group locally optimal when every
other component stayed fixed. A strict improvement could still require two
groups to exchange space or move cooperatively, so all six pairwise unions
needed full-site closure before changing the search topology.

## Results

Each released component could use every fixed-obstacle-free exact site. Models
used current and quality candidate guides, a separate current solver hint, one
worker, seed 1000, exact nonrectangle conflict tables, and acceptance-audited
rectangle intervals.

| Groups | Movable | Candidates | Deterministic time | Result |
| --- | ---: | ---: | ---: | --- |
| page 4 + page 6 | 17 | 30,993 | 11.6281 | `OPTIMAL` at source |
| page 4 + page 7/J701 | 16 | 28,595 | 49.9617 | `OPTIMAL` at source |
| page 4 + page 7/J702 | 16 | 29,054 | 17.4774 | `OPTIMAL` at source |
| page 6 + page 7/J701 | 19 | 33,016 | 73.8639 | `OPTIMAL` at source |
| page 6 + page 7/J702 | 19 | 33,475 | 54.2505 | `OPTIMAL` at source |
| page 7/J701 + page 7/J702 | 18 | 31,077 | 300.0018 | `FEASIBLE` at source |

The first five objective values and bounds are integer HPWL `15811065584`.
The final model retained the same incumbent but has valid integer lower bound
`15374001721` (`15374.001721`). Its rectangle audit covered 455,098,186
candidate pairs with zero false positives and zero false negatives; exact
nonrectangle tables add 9,739 conflicts. After subtracting the `0.000304`
HPWL rounding allowance, the bound is still above the score-1 necessary HPWL
threshold `15260.369571786632`. Thus this fixed-surrounding pair domain cannot
meet score 1.0, although its `FEASIBLE` status is not an optimality claim.

Result SHA-256 values in table order are:

- `d7097219fc132fcbf25dbe30f32de437e3837bb2542ce326684db26c7af7318a`;
- `91dbd684038a9d535a37b0e396e99e12d7d1b00470cafde54f59a34abe7b4a2f`;
- `0c50969ae3ad4be1c375ca81d6dc50fa411810a93a3f0935cbf8aff0b9e70103`;
- `bfbdb186bb6466e91b11bd80a4904ee6ecc0c4f26a0e9036da4a0b63645d7e37`;
- `fd8aad2b7e47a9f89c8095d8586677af9e34c86fc7256d21b4655bdadf8cf745`;
- `9de8f73ea7b7427c968a5f19b912ec0c975df24e1cc3236baaea10b903429f77`.

All incumbents pass objective and guide-rank replay plus exact 100/100
containment with zero violations and overlaps.

## Next Action

Stop spending deterministic budget on these pair domains. Use the now-repaired
structured result contract to test one side-specific subgroup assignment at a
time while retaining the certified legal incumbent. Any improvement must be
recertified and compared against the manual baseline.
