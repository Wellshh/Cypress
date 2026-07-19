# M336-090: Coupled K512 Score Searches Exhaust Their Budget

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `3a7e37b`

## Problem

M336-089 proves that four coupled K256 assignment domains contain no score-1
placement. Widening the current/quality site neighborhoods is necessary, but a
wider model must not inherit the K256 infeasibility conclusion without a new
completed proof.

## Method

The four score-gated first-feasible searches from M336-089 were repeated with
`--candidate-limit-per-region 512`. All other model and solver settings were
held fixed: exact decomposed collision geometry, 0.1 mm lattice, score-derived
integer HPWL limit `15260369875`, structured exact-legal hint, capacity floor,
manual `EMI601` endpoint, one worker, seed 1000, and OR-Tools `9.15.6755`.
The deterministic budget increased from 120 to 300 seconds.

## Evidence

| Released subgroups | Candidates | Collision constraints | Status | Branches | Conflicts | Wall seconds | Result SHA-256 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `ANT8604 + U8601` | 64,434 | 4,581 | `UNKNOWN` | 1,964,937 | 635,771 | 497.975126 | `a6e66bf6802e93783ad849578e0cf3d4744ac87b7a6d17b913f629ec670025a9` |
| `MIC401 + J601` | 65,128 | 4,237 | `UNKNOWN` | 3,502,562 | 963,180 | 498.923003 | `a70486b9639f8057d199e5f96d8a046b951b022c37b24f8e42b8ee767a12b07b` |
| `J701 + J702` | 67,133 | 4,470 | `UNKNOWN` | 3,184,441 | 929,448 | 462.546190 | `27773b99ad856c345b4a04dacdddac4d4a8bd3c46f81e820873391c6d7d40215` |
| all five page-86 groups | 73,811 | 10,934 | `UNKNOWN` | 3,438,303 | 815,894 | 563.261906 | `01b5670ffc1b2973425ba535a2f8101ccda08ae365eb3b64237a5af9ab4fa49a` |

All reports use `objective_mode: first_feasible`, record the active score
limit, and contain no placement because no incumbent was found. Every run
consumed its deterministic search budget. The exact status is `UNKNOWN`; none
of these results proves feasibility or infeasibility.

K512 roughly doubles the candidate count relative to K256 and changes all four
completed `INFEASIBLE` proofs into unresolved searches. This is the current
candidate-width boundary.

## Next Step

Use the same K512 domains with a hard integer ceiling one unit below the
certified incumbent (`15811065583`) and no score gate. This asks for any strict
improvement while preserving exact legality and monotonic continuation. If it
produces an incumbent, certify all selected sites before promotion and tighten
from the new value. If it returns `UNKNOWN`, preserve that status and change
search structure rather than claiming the K512 domain is closed.
