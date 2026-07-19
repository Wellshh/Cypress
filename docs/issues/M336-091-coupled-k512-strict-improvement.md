# M336-091: Coupled K512 Strict-Improvement Searches Remain Unknown

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `0b8bfdd`

## Problem

The direct score-1 K512 searches in M336-090 may be too restrictive to expose
an intermediate legal state. A smaller certified improvement could refresh net
topology and candidate centers before the score gate is attempted again.

## Method

The same four K512 domains were searched in first-feasible mode with score
gating disabled and hard integer HPWL ceiling `15811065583`, one unit below the
certified objective `15811065584`. Exact decomposed collisions, the 0.1 mm
lattice, structured hint, capacity floor, current/quality candidate centers,
manual `EMI601` endpoint, one worker, seed 1000, and 300 deterministic seconds
were unchanged.

The source hint violates the new ceiling, so any emitted placement would be a
strict model-level improvement. It would still require fixed-site objective
replay before promotion.

## Evidence

| Released subgroups | Candidates | Collision constraints | Status | Branches | Conflicts | Wall seconds | Result SHA-256 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `ANT8604 + U8601` | 64,434 | 4,581 | `UNKNOWN` | 2,766,112 | 808,318 | 693.343639 | `c7531e604d246c642273a21c38cd4bfa18f6d766df284d33af07c039d33757c5` |
| `MIC401 + J601` | 65,128 | 4,237 | `UNKNOWN` | 3,406,303 | 1,039,865 | 603.627480 | `f6bfebf53aacc001e86f297917ae0bfedb8896dc217146655a4d44cc929d4df0` |
| `J701 + J702` | 67,133 | 4,470 | `UNKNOWN` | 3,810,385 | 998,801 | 662.113294 | `fdc05eb9e95f88bb1f8cc827624bb61d0d5d5641805c0f838f9f9843f35108bc` |
| all five page-86 groups | 73,811 | 10,934 | `UNKNOWN` | 2,688,479 | 1,098,296 | 856.689623 | `26590a2fa53d197d6b1bb7c18b71d375bcdd4f6759cadf8fd66f1a3b7d82fa12` |

No run emitted a placement or assignment. Each exhausted its deterministic
budget. These are `UNKNOWN` outcomes: they neither prove that the certified
placement is optimal in a K512 domain nor prove that a strict improvement
exists.

## Impact and Next Step

Relaxing the score threshold to the nearest strict-improvement boundary did
not remove the search stall. Repeating the same model with more wall time is
not yet justified. The next search should change structure by reusing the
previously effective regional refresh and physical-group closure pipeline,
adding assignment alternatives only after a new fixed-region guide is
available. Candidate-guide rank and hint coupling must remain independently
audited so a guide change cannot silently alter the certified incumbent.
