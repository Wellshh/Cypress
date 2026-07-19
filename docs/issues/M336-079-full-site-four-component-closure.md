# M336-079: Directed Four-Component Full-Site Closures Do Not Improve

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `008b163`

## Problem

M336-077 closes twelve high-ranked two-blocker triplets, but either blocker may
need a fourth component to vacate its replacement site. Repeating a broad
K1024 solve does not isolate whether this next ejection layer is sufficient.

## Directed Quadruplets

Overlapping high-ranked triplets were unioned into page-7 and page-86
quadruplets. One cross-boundary page-4/page-7 set was retained. Each model used
every fixed-obstacle-free site (`candidate_limit=0`), exact polygon collisions,
current/quality candidate guides, an independent current hint, one worker, and
seed 1000.

| Movable quadruplet | Candidates | DT | Result |
| --- | ---: | ---: | --- |
| `FV702,FV706,R705,R706` | 6,882 | 2.0808 | `OPTIMAL` at source |
| `FV706,R702,R705,R706` | 7,059 | 2.0949 | `OPTIMAL` at source |
| `FV702,FV705,FV706,R706` | 6,881 | 2.0693 | `OPTIMAL` at source |
| `FV704,FV706,R702,R705` | 6,882 | 2.0830 | `OPTIMAL` at source |
| `FV703,FV704,FV706,R702` | 6,705 | 2.1130 | `OPTIMAL` at source |
| `FV703,FV704,FV705,FV706` | 6,704 | 1.8992 | `OPTIMAL` at source |
| `FV702,FV703,FV706,R706` | 6,705 | 2.0499 | `OPTIMAL` at source |
| `FV702,FV706,R706,RT601` | 7,014 | 2.1075 | `OPTIMAL` at source |
| `C8602,C8614,L8601,L8608` | 844 | 0.0919 | `OPTIMAL` at source |
| `C8614,L8603,L8604,L8608` | 762 | 0.0516 | `OPTIMAL` at source |
| `C8608,C8609,C8614,C8620` | 1,094 | 0.1068 | `OPTIMAL` at source |
| `C8609,C8614,C8622,L8602` | 908 | 0.0672 | `OPTIMAL` at source |
| `C8614,C8619,L8601,L8605` | 898 | 0.0527 | `OPTIMAL` at source |
| `B402,FV710,R708,R709` | 6,883 | 2.1925 | `OPTIMAL` at source |

Every response objective and bound equals integer HPWL `15811065584`. HPWL
and guide-rank replay audits pass, and exact validation reports 100/100
containment with no violation or overlap.

Result SHA-256 values in table order are:

- `887a0c92cb6666e84bf8d7dcb214ae73641373485eafb259ce9e2b8c094068fe`;
- `e583f3f122975efff184a2a0230e1a5684acf0b9937a33764ac39d46a7bee0c1`;
- `6f40925e4b3dc61b704b43cc9c59c199337cfd51f2a33c99b238be30f5ec930c`;
- `6ee79a320d6f463d9980f4e8dd3d34c353f21ae1aa0558b194c288b0e9f85504`;
- `e23b4363e71312b34f531ef9950d0543919f2c4399fa7ba6c640854a28935f0b`;
- `2a2e8e483dd81610ee7c083884dacfabb33969ec32a500591fd1f37ff0d9f5f1`;
- `b68c65e713ec09223b670cb2402b8503d7a2e97c03ddc00d254ba5486e4cbacd`;
- `06cf3a430f7fb93eefc10451db3f7cc490b239aae9914e9ac91901e33eda7f5a`;
- `c5dc7c7ed9648a52bf4c1a19b3b18d6921a944ef717aac20ab4968fc827404ba`;
- `bbf4e384dd160e0239fc0ce11308bd448834f7840deaa17f9f4cc6fa94245d5f`;
- `84a0458e2935ee4d418e103f9965df7dc0127c20d574c6bc4886546dd53268f1`;
- `6de34de940fc63b9055e8367bf2b0e121604aa12a33426dc44e8a6c4207c6a36`;
- `bbc812bdc1fd03017272b7ba0bca835feed1e081cbdcf7eaaa2579c7c022200c`;
- `4909dd6b7a4545274769ef1919304e100fd57777ef6372919a3074b499a5c8b5`.

## Finding

Adding one directed ejection layer does not unlock an improving legal move in
any tested full-site domain. This proves complete local optimality only for the
fourteen listed fixed-surrounding quadruplets. It does not enumerate every
four-component subset and does not establish that five moves are globally
necessary.

## Next Action

Stop these exact quadruplets. Optimize each complete page-4/page-6/page-7
physical group over all sites to test whether the prior K1024 truncation hides
a farther cooperative move. Escalate to higher-order ejection only from a
group whose full-site result remains unresolved.
