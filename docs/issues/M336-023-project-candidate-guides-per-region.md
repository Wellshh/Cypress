# M336-023: Candidate Guides Are Bound to One Region

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-18
**Affected commit:** `b874e61`

## Problem

`--candidate-guide-placement` stored a region-local site index and rejected
optimized assignment. A site index has no meaning outside the domain that
created it, so the guide could not safely seed alternate subgroup regions.
The restriction also prevented controlled A/B tests using the same site budget
around both the known legal skeleton and the manual baseline.

## Correction

The guide loader now stores each component's physical center. During model
construction, that center is projected independently to the nearest feasible
site in every eligible region. Candidate limiting then ranks sites by distance
to either the exact structured hint or the projected guide while preserving
the original total per-region limit. The guide does not fix sites, alter region
eligibility, or weaken capacity, keep-in, collision, or HPWL constraints.

## Contract Evidence

An optimized-scoped fixed replay with 128 candidates per component-region used
the manual baseline as the second guide:

- `OPTIMAL`, one worker, zero branches and conflicts, `0.010991 s` solver time;
- 18,048 retained sites;
- unchanged HPWL `17320.120203` and score upper bound `0.881078`;
- unchanged zero keep-in violations and seven exact overlaps; and
- mean/max baseline-guide projection distance `35.655609/437.028691`.

The replay proves the guide expands the modeled domain without changing the
hinted assignment or coordinates.

## Search Evidence

At a 1,024 limit, the five-subgroup scoped model retained the same 143,409
sites as the single-guide run. It remained `INFEASIBLE`, but reached 1,370
branches instead of failing in presolve at zero branches. Opening all 61
assignment options retained 227,377 sites and was also proven `INFEASIBLE`
after `178.427277 s` and 107,340 branches. Thus the manual baseline is a valid
second center, but these two neighborhoods still do not contain a legal repair.

## Residual Risk

Nearest projection can place a remote guide on a crowded boundary and does not
guarantee a useful packing neighborhood. Every exploratory multi-worker result
still requires fixed single-worker replay and exact validation. The restored-
anchor packing failure remains tracked by `M336-022`.

## Acceptance Criteria

- One physical guide maps independently into each eligible region.
- Candidate selection remains deterministic and preserves the exact hint.
- Optimized and scoped assignment accept candidate guides.
- Fixed replay leaves assignment, coordinates, metrics, and legality unchanged.
