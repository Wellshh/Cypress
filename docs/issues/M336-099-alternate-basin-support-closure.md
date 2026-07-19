# M336-099: Restricted Movable Support Masks an Alternate Basin

**Severity:** High
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `3a4e218`

## Problem

M336-098 limit 10, seed 1003 followed by exact pair closure produced a
certified legal placement at HPWL `15814.564714651957`. It differs from the
current incumbent at 25 component centers:

`B402,C201,C202,C301,C302,C402,C405,C501,C502,C601,C604,C606,C610,C611,C701,C703,C8602,C8603,C8606,C8612,C8613,FV302,FV617,FV707,R604`.

The first alternate-first CP-SAT portfolio reused the incumbent's historical
80-component movable set. Nine changed components were absent:

`C201,C202,C301,C501,C502,C601,C604,C611,FV617`.

`--movable-refdes` fixes every omitted component to its hinted site by model
equality. A candidate guide changes candidate ordering but cannot override
those equalities. Consequently, the 80-component portfolio cannot reproduce
the complete certified basin and cannot support a claim that the basin fails
to improve. `UNKNOWN` remains budget exhaustion, never infeasibility.

## Restricted A/B Result

All four 80-component K256 runs completed at deterministic time 300. They
retained the incumbent exactly and remained fully legal:

| Seed | Status | HPWL | Best HPWL bound |
| ---: | --- | ---: | ---: |
| 1000 | `FEASIBLE` | 15811.06557381333 | 14715.885225 |
| 1001 | `FEASIBLE` | 15811.06557381333 | 14745.783707 |
| 1002 | `FEASIBLE` | 15811.06557381333 | 14733.521304 |
| 1003 | `FEASIBLE` | 15811.06557381333 | 14733.521304 |

Every objective replay passed with 100/100 containment, zero violations, and
zero overlaps. All four placement files have the incumbent SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`.
The bounds remain below the score-1 HPWL threshold, so these finite searches
do not prove absence of a better solution even inside the restricted domain.

## Mitigation

Retain the 80-component runs only as an ordering A/B. The corrected support is
the sorted union of the historical 80 components and all 25 coordinate
differences, totaling 89 components. The corrected four-seed K256 portfolio:

- uses the alternate basin first with guide weights `4,1,2`;
- retains the certified incumbent as a separate complete hint;
- enforces the incumbent integer HPWL ceiling `15811065584`;
- uses exact BOTH-side collision and keep-in validation;
- writes isolated context, progress, result, and placement artifacts per seed.

## Acceptance Criteria

- Record all four statuses and bounds without relabeling `UNKNOWN`.
- Independently all-fixed certify any strict improvement.
- Before future restricted guided searches, compute the guide/source center
  difference and verify it is a subset of the movable support.
- Promote no result unless objective replay passes with 100/100 containment,
  zero keep-in violations, and zero overlaps.
