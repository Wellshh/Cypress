# M336-076: Candidate Guides And Solver Hints Were Coupled

**Severity:** High
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `09fde92`

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

## Next Action

Repeat rank-seed HPWL recovery on the original quality/current K256 candidate
domain. Compare seed versus current hints with and without the seed rank
ceiling; promote only a strict HPWL improvement after all-fixed certification.
