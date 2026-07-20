# M336-128: Unbounded Rank Exposes The Missing Incumbent Exclusion

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `1a4f3a6`

## Problem

M336-127 proved that the 20-component expanded page-7 domain has the same
minimum guide-rank topology through a `+200` HPWL envelope. It remained
possible that the HPWL model itself prevented a more guide-aligned legal
topology. The envelope was therefore removed entirely.

The exact probe currently has independent source, candidate guides and solver
hint, but it has no constraint requiring a minimum site distance from the
incumbent and no exact tuple no-good for previously found placements. A rank
objective can consequently optimize successfully while returning an existing
topology; seed changes cannot answer whether a distinct legal topology exists.

## Unbounded Rank Evidence

Four one-worker K4096 solves reused the M336-125 20-component, 82,000-candidate
domain, exact BOTH-side collisions, expanded quality primary guide, guide
weights `4,2,1,1,2`, and certified seed 3001 as an independent hint. There was
no HPWL objective, threshold, or ceiling.

| Branching | Seed | Status | Rank | Result SHA-256 |
| --- | ---: | --- | ---: | --- |
| automatic | 8200 | OPTIMAL | 72 | `21d77b5b2fb0386709bf9b60b4d5fcaa8555c9773c6075dcccad7b0a1c4effd8` |
| automatic | 8201 | OPTIMAL | 72 | `d68ffd5ad63cff570b4d097e6a7cf99dcc6d324d6ed2947cb17a9c78b3e5ab7f` |
| partial-fixed | 8200 | OPTIMAL | 72 | `dd14e494ae0d5473b05b2857fea62255cbcb060f9373203ba218a10c4b361222` |
| partial-fixed | 8201 | OPTIMAL | 72 | `7e01f4dfc7628677fe70002c1f8197b6100d8d1df169818f8f6956d4a34dc6fa` |

All four returned HPWL `15649.948866405257` and placement SHA-256
`14b534af7e58bd277ff1fcfd4045636756bbb3a9de4386f3c307f021ddec2ed5`,
byte-identical to the tracked M336-121 seed 3001. Model build took
145.93--152.93 seconds; solve time was 17.12--17.31 seconds and only
8.077 deterministic units. Guide-rank replay passed, and every placement has
100/100 containment, zero keep-in violations, and zero overlaps.

This closes the global minimum-rank question only inside this finite candidate
domain. It does not prove that the domain lacks a better HPWL placement.

## Required Remediation

Add independent inputs for a diversity reference, minimum changed-site count,
and one or more exact site-tuple no-goods. For every movable multi-site
component, create a reified Boolean equivalent to `site != reference_site` and
enforce the requested Hamming lower bound. Resolve each reference coordinate
to exactly one candidate site and fail closed instead of nearest-site
projection. Fixed domains must not contribute to the count.

Serialize and replay the reference path/hash, canonical site tuple, requested
and actual changed refdes, and excluded tuple hashes. Candidate guide, source,
solver hint, and diversity reference must remain four separate concepts.

## Acceptance Criteria

- A minimum changed-site count cannot emit the reference placement.
- The reported changed count and refdes exactly replay from selected sites.
- An impossible requested distance returns solver `INFEASIBLE`, not a relaxed
  result; `UNKNOWN` remains explicitly inconclusive.
- A reference coordinate absent from the candidate domain fails before solve.
- Each exact no-good rejects only its mapped complete tuple.
- Existing behavior and result schema remain compatible when exclusion inputs
  are omitted.
- CPU unit tests cover exact mapping, Hamming enforcement, no-good enumeration,
  fixed-domain handling, and fail-closed metadata.

## Next Experiment

Start with the M336-122 18-component candidate domain and M336-118 as the
diversity reference. Cross `d=2,4,6,8` with HPWL rise envelopes
`0,1,2,5,10,20`; minimize stable guide rank, add a full no-good after each
topology, then run an independent HPWL closure with M336-118 as hard ceiling.
Repeat on the 20-component B402/L401 domain only after the exclusion mechanism
passes replay tests.

## Remediation

`probe_exact_site_cpsat.py` now accepts the three specified inputs. It maps the
reference and every no-good onto the final post-truncation candidate domains
with a unique `1e-8` site tolerance. Missing, ambiguous, non-candidate, duplicate,
and outside-movable tuples fail before solve. Reified equality/disequality
literals enforce the Hamming lower bound, while complete forbidden assignments
exclude prior tuples independently of source, candidate guides, and solver hint.

Results and progress metadata record input paths and SHA-256 values, canonical
site tuples, scope and fixed-domain exclusions, requested distance, actual
changed refdes, no-good matches, and replay status. Omitting all diversity
inputs adds no model variables or constraints.

## Verification

The M336 CPU suite now passes `71/71` tests. New tests cover strict path parsing,
feature-off model identity, exact mapping, fixed-domain exclusion, Hamming
enforcement, solver-proved impossible distance, tuple enumeration, replay, and
outside-support rejection.

Two real K16 probes released only `C703,FV707` from M336-118. The first required
one changed site and returned `OPTIMAL` at rank 2 by moving `FV707`; the second
used that complete tuple as a no-good and returned a different `OPTIMAL` rank-2
state by moving `C703`. Their HPWL values were `15635.450369937662` and
`15634.950369937662`. Both retained 100/100 containment, zero keep-in
violations, zero overlaps, and passed diversity replay.

Result SHA-256 values are
`f13c7885e5ef3ea9700f6744d1c46010ab8c637d6db4dfa34d6825a51280d06f`
and `2a62d896246ab2d93dd9501d52bcabd34af5e7e3b09bf3964c63159f5fad36bb`;
placement SHA-256 values are
`1bfb6c81e2a1f5b4c19e675790a96b3d2e2673b4354c149f14b08a6ecf4dfe53`
and `4d426c3c0b31e07235b7acd478b7205526c37289cfbfc69a6592ce1f016f2974`.
These are non-scoring integration states, not promoted incumbents.

A real feature-off all-fixed K1 replay omitted all diversity variables. It
returned `OPTIMAL`, HPWL `15634.450477332834`, integer objective
`15634450483`, complete per-net/objective replay, and zero legality failures.
Its placement SHA-256 is the exact M336-118 value
`32f814e4b4f49a1450f4d02cc4d197f668ca0ddadc45b6cf523f049ae968cbf7`.
The result SHA-256 is
`dbbc0bc08a3b0cb98d1f7aeb6d5b8f05c3cf5904a786a340cbb0f35a97986589`.
