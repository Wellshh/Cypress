# M336-092: Current-Topology Seed Portfolio Converges to One Incumbent

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `168cf1e`

## Problem

Earlier seed-1001 through seed-1008 refresh runs used the pre-M336-074 source
at HPWL `15812.627220927616`. They did not test whether random-seed search
trajectories from the current certified topology could cross its local barrier.

## Method

Eight 80-component K256 models used the certified HPWL
`15811.06557381333` source as an independent hint and first candidate guide,
the collision-relaxed quality placement as the second guide, explicit `1:1`
guide weights, exact fixed assignment and collision geometry, one worker, and
300 deterministic seconds. Only the recorded CP-SAT seed changed from 1001
through 1008.

## Evidence

| Seed | Status | HPWL | Valid bound | Conflicts | Result SHA-256 |
| ---: | --- | ---: | ---: | ---: | --- |
| 1001 | `FEASIBLE` | 15811.065574 | 14729.600909 | 617,888 | `2a8c4ddb5a4ed41f9d2a2c6991fc385e08c5f1b8f70b540e532413f4ab51366e` |
| 1002 | `FEASIBLE` | 15811.065574 | 14758.865157 | 586,867 | `b735d3c01b127184c25f188c2c7462cb54f2d4ba462a0b449a55d0ff1a3e548a` |
| 1003 | `FEASIBLE` | 15811.065574 | 14733.721126 | 567,034 | `d46291a7d1452adc4631233fd66b1423ebc08a595e2f564e5cc36c5189c082ae` |
| 1004 | `FEASIBLE` | 15811.065574 | 14728.951038 | 617,980 | `4812c2a18a05e67e8a967cebadf9f7db62cb55a18c7f0627b27b99a04dfd15d1` |
| 1005 | `FEASIBLE` | 15811.065574 | 14720.335757 | 586,316 | `4c41b686f02dc3ceb13ebb8c0d3bba75318efcb36945675fa43baf800efcd551` |
| 1006 | `FEASIBLE` | 15811.065574 | 14711.964830 | 626,444 | `ea898221e5fe582579e9ab5362ba02bac9cf16d0b6ae29ac30f3db0c1087a57f` |
| 1007 | `FEASIBLE` | 15811.065574 | 14730.530428 | 606,478 | `be58ba17c81045f37b3cc4655e425a7e79c22a2530177cd1b0020cb254ccb15a` |
| 1008 | `FEASIBLE` | 15811.065574 | 14711.964830 | 570,681 | `288014f147f492b0b90f5337253a0c3c61edfc7a843615c51f87db4f47e0c8fa` |

Every objective replay passes, and every result has 100/100 containment, zero
keep-in violations, and zero overlaps. All eight emitted placements are
byte-identical with SHA-256
`e3fa2a59b85653751ef6c67ba63157c85082996ed142aef828626fbf572119bf`.
The differing bounds confirm that seeds change search trajectories, but none
changes the incumbent. All bounds remain score-permitting, so no optimality or
infeasibility conclusion follows.

## Residual Diagnosis

An independent PlaceDB replay compared the certified placement with the
HPWL `14700.901479300053` collision-relaxed quality guide. The six largest
current-minus-guide net residuals are all dominated by page-7 components:

| Net | Residual HPWL | Controlled refdes |
| --- | ---: | --- |
| `VSIM2` | 107.487542 | `C703,FV707,R707` |
| `SIM_DET1` | 93.989905 | `FV705,R703` |
| `PSIM2_DATA2` | 89.990334 | `FV710,R708` |
| `NFC_SWP` | 84.715553 | `FV706` |
| `PSIM2_SRST2` | 80.671942 | `FV708,R709` |
| `PSIM2_SCLK2` | 79.991408 | `FV709,R710` |

Their gross residual is `536.846685`, close to the remaining score-1 HPWL gap
`550.696002`. This is an optimistic localization signal, not an additive
achievable gain: the quality guide has 383 overlaps, and moving a shared
component can improve one listed net while degrading another.

## Next Step

Stop the current/quality K256 seed ladder. Use the two retained equal-HPWL
plateau placements as additional candidate centers and refresh the page-7 plus
bottom-0 collision boundary. Keep the certified placement as the independent
hint and promote only a strict all-fixed replay improvement.
