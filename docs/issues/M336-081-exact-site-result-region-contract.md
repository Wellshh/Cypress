# M336-081: Exact-Site Results Omitted Region Identity

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `404ff71`

## Problem

`probe_exact_site_cpsat.py` wrote candidate indices and centers but omitted
`region_id` from `selected_sites`. Those indices are local to one feasible
region, so `solve_discrete_placement.py --site-hint-result` could not safely
reuse the result in assignment optimization or `--movable-subgroup` searches.
Inferring a region from the index would be ambiguous and could silently remap a
legal incumbent.

## Resolution

Every selected site now carries the region from its fixed constraint. Reused
source rows are copied through `_selected_site_in_region`, which rejects a
pre-existing conflicting region instead of overwriting it. Newly optimized
rows write the region directly.

A fixed current-placement certification wrote 100/100 explicit regions to
`/tmp/m336_current_region_metadata_certified.json` (SHA-256
`79a6d47798863cf90fabe34607a3b71ccf657755f4fe9aaa43e44f80fe089734`).
The structured consumer accepted all sites with zero remaps. Its output
placement retained SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`.

## Acceptance Impact

Scoped assignment continuation is no longer blocked by missing provenance.
This change does not improve placement quality: exact HPWL remains
`15811.06557381333`, with normalized score upper bound
`0.9651702157924906`. Any future result whose stored region contradicts its
assignment now fails closed.
