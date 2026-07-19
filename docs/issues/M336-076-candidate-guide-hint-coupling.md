# M336-076: Candidate Guides And Solver Hints Were Coupled

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `09fde92`
**Mitigated by:** `b64f073`

## Problem

`probe_exact_site_cpsat.py` required the solver hint to be selected from the
candidate guides. A two-phase search therefore could not use a legal
guide-rank result as its HPWL hint without also adding that result to candidate
generation. This changed candidate membership, site indices, and the meaning
of the guide-rank objective between phases.

The earlier recovery used rank-seed/current/quality guides with weights
`1:1:6`, whereas the rank phase used quality/current guides with weights
`255:1`. Its result is useful search evidence, but it is not a strict same-domain
comparison.

## Fix

`M336_HINT_JSON` now supplies a complete hint independently of candidate
guides. When omitted, `M336_HINT_GUIDE_INDEX` preserves the previous behavior.
Results record `hint_json`, `hint_source`, and a null candidate-guide index for
separate hints.

`M336_GUIDE_RANK_CEILING` adds an optional non-negative bound over the stable
candidate site indices. Every incumbent now records a guide-rank replay audit.
The audit checks the selected rank, the ceiling, and the response objective
when guide rank is optimized; the process exits nonzero if this audit fails.

## Verification

Python compilation, `git diff --check`, and all 52 M336 unit tests pass. Tests
cover strict ceiling parsing plus objective and ceiling replay failures.

An all-fixed quality/current `255:1` smoke used the certified incumbent as a
separate hint and rank ceiling zero. It returned `OPTIMAL`; HPWL objective and
bound both equal `15811065584`, selected rank is zero, both replay audits pass,
and exact validation reports 100/100 containment with no violation or overlap.
Its placement SHA-256 is
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`,
identical to the source. Result SHA-256 is
`f4a2cddb982d7975c44ba729e367c70e185648d2f1403e9fb7d7b82cb9311bcd`.

## Same-Domain Ablation

The original 80-component K256 rank phase has 19,486 candidates, quality/current
weights `255:1`, selected rank `7925`, valid rank bound `754`, and legal HPWL
`16314.696146`. The certified incumbent has rank `10011` in that exact domain.

HPWL recovery retained the same source, movable set, guide order, weights,
candidate width, one worker, seed 1000, and 300 deterministic-time units. Only
the independent hint and rank ceiling changed:

| Hint | Rank ceiling | Selected rank | HPWL | Valid HPWL bound |
| --- | ---: | ---: | ---: | ---: |
| rank seed | 7,925 | 7,925 | 16265.201516 | 14714.752238 |
| rank seed | 9,000 | 9,000 | 16106.212680 | 14714.815173 |
| rank seed | 10,010 | 9,149 | 16092.597859 | 14710.815603 |
| rank seed | none | 9,133 | 16077.911805 | 14713.930854 |
| incumbent | none | 10,011 | 15811.065574 | 14720.994664 |

All runs are `FEASIBLE`; HPWL replay, guide-rank replay, 100/100 containment,
and zero-overlap validation pass. Their result SHA-256 values in table order
are:

- `dcf2af18da7ca37c907d2c598e753fbc37a9c7e824dfa188b0f449fd423136af`;
- `a3a36301ffbcb9543c89c4019438b4f013d131e3d411b034711b2bb3fed0e4d7`;
- `6ae7d03bbd96527fe4aab127c44048c8a81e1f588c42c730b096f25a28e04540`;
- `f61915e57231d549fdc6818e0540f6215807f3fb849149f774dda5c21558fd1b`;
- `8bdb101599a2d7744e091e9e24c35378d3c16eb51628e37b52ad5614d58bf5ca`.

Relaxing rank recovers HPWL from the quality-ranked basin but is not monotonic:
the ceiling-10010 result selects rank 9149, while the unbounded result selects
the lower rank 9133 and better HPWL. The incumbent hint remains materially
better than every rank-seed trajectory. Thus guide rank is useful for creating
legal diversity, not as a quality proxy or continuation coordinate. Every
HPWL bound remains below the score-1 threshold, so these budget-limited runs do
not prove the candidate domain score-infeasible.

## Next Action

Stop the tested rank-ceiling ladder. Retain separate hints and replay audits as
the corrected experiment contract. Use rank-generated states only as diverse
search seeds, and promote only a strict HPWL improvement after all-fixed
certification.
