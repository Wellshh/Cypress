# M336-077: Leading Two-Blocker Ejection Triplets Are Exact Optima

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `b64f073`

## Problem

The certified HPWL `15811.065574` placement is a full one/two-optimum, but a
component may still enter a beneficial site by moving two blocking components.
Group K1024 runs do not establish whether farther exact sites permit such a
three-component ejection.

## Diagnostic

All 133,174 fixed-obstacle-free sites were evaluated against the current legal
placement. The blocker-count distribution includes 47,363 sites blocked by
exactly two controlled components. Of those, 1,567 would reduce HPWL if blocker
relocation had zero cost. The best target-only estimate improves HPWL by
`84.715553` to `15726.350021`. The top 1,000 such candidates collapse to 109
distinct target/blocker triplets.

This is an optimistic ranking only: target-only HPWL is evaluated in an
illegal intermediate state and excludes both blocker relocation costs.

## Exact Full-Site Models

Twelve high-ranked or topologically distinct triplets were then solved with
every obstacle-free site (`candidate_limit=0`), current/quality guides, an
independent current hint, exact polygon collision constraints, one worker, and
seed 1000:

| Movable triplet | Candidates | DT | Result |
| --- | ---: | ---: | --- |
| `FV702,FV706,R706` | 5,142 | 1.1171 | `OPTIMAL` at source |
| `FV706,R705,R706` | 5,319 | 1.1594 | `OPTIMAL` at source |
| `FV706,R702,R705` | 5,319 | 1.6304 | `OPTIMAL` at source |
| `C8602,C8614,L8601` | 682 | 0.0568 | `OPTIMAL` at source |
| `FV702,FV705,R706` | 5,142 | 1.3746 | `OPTIMAL` at source |
| `C8602,C8614,L8608` | 614 | 0.0509 | `OPTIMAL` at source |
| `FV704,FV706,R702` | 5,142 | 1.3086 | `OPTIMAL` at source |
| `C8614,L8603,L8604` | 600 | 0.0220 | `OPTIMAL` at source |
| `FV703,FV704,FV706` | 4,965 | 1.0923 | `OPTIMAL` at source |
| `C8608,C8609,C8614` | 864 | 0.0702 | `OPTIMAL` at source |
| `C203,C701,R704` | 6,048 | 1.8714 | `OPTIMAL` at source |
| `B402,FV710,R708` | 5,143 | 1.5443 | `OPTIMAL` at source |

Every objective and bound equals integer HPWL `15811065584`. HPWL and rank
replay audits pass, and exact validation reports 100/100 containment with zero
violations and overlaps.

## Finding

The largest apparent target-site gains are fully offset by legal blocker
relocation in every tested full-site triplet. These are complete proofs for the
twelve listed fixed-surrounding domains, not for the other 97 ranked triplets,
four-component moves, alternate assignments, or a continuous placement.

## Next Action

Do not repeat these triplets at wider candidate limits because their domains
are already complete. Finish the same-domain rank-ceiling ablation, then target
four-component ejection closures or a changed topology only where a valid
lower bound remains score-permitting.
