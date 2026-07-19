# M336-063: Exact Escape State Needs A Safe Search-Seed Contract

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `9f6f7af`

## Problem

Non-regression restoration correctly prevents a worse guided escape state from
becoming the incumbent, but it also hid a materially different exact-legal
topology from subsequent global search. Reconstructing that state ad hoc would
weaken provenance and risk accidentally scoring a worse placement.

## Mitigation

`greedy_exact_site_descent.py` now accepts paired
`--escape-state-output` and `--escape-state-placement` paths. It writes the
state immediately after deterministic escape and before descent or restoration.
The JSON includes the full move path, source and escaped HPWL, exact legality,
all selected sites, and candidate-domain metadata. It is fail-closed with:

- `search_seed_only=true`;
- `certification_required=true`;
- `objective_mode=guided_escape_hpwl`.

The ordinary non-regressing output remains unchanged.

## Verification

The budget-100 seed contains 100 exact sites and HPWL `15905.302755`, a
69.958559 regression from the certified incumbent. Its normalized score upper
bound is `0.959451688`; it is not an acceptance candidate. Exact validation is
100/100 containment with zero keep-in violations and overlaps. Seed JSON and
placement SHA-256 values are:

- `b72342dd3792525316c043f75ab83d078a08a28d8e3c3e7c5f15c16531c1c5a4`;
- `0c08e8438fd4c4855d0b65c4e8d1b5032a24550451489e012562ef862ce7cd67`.

An all-fixed CP-SAT replay returned `OPTIMAL`; response, variable, and selected
site integer HPWL all equal `15905302765`. Per-net and coordinate mismatch
counts are zero, and floating delta is `0.000009850150`. Certification result
SHA-256 is `8efd78ac4d8d662e814e3926791feb2492034232b57e97f54b67715a87b00efd`.
The scorer independently rejects the seed with `exact-site result requires
fixed certification`. The M336 suite passes 47/47.

## Next Action

Use this seed once as the current guide and legal hint for an all-100 K64
CP-SAT optimization, while comparing every returned result against the
certified HPWL `15835.344196`. A result that merely improves the seed is still
rejected; only a strict incumbent improvement proceeds to all-fixed replay.

