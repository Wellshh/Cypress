# M336-049: Reduce Fixed Domains for Regional HPWL Descent

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `bfbf7ee`

## Problem

The exact-site probe fixed unlisted components with site equalities but still
retained every K512 candidate. Those unreachable sites inflated rectangle and
nonrectangle collision tables, preventing practical coordinate descent from a
legal full-board state. The global BOTTOM score solve therefore searched 70
components simultaneously and remained `UNKNOWN`.

## Correction

When `M336_FIX_GUIDE=1` and core-chain release is disabled, every unlisted
component now receives only its selected hint site. Core-chain mode retains
the full domains because it must be able to release assumptions later. Results
record both the fixed refdes list and single-site fixed-domain count.

The all-fixed BOTTOM K64 regression reduced the model from 4,480 candidates to
70.
It reproduced HPWL `18070.692761`, 100/100 containment, zero violations and
zero overlaps. The placement SHA-256 remained
`74749eced0bc87945837b93ce708bf52a0fed643f6f4f0bf72763f05abbb257f`;
CP-SAT solve time was `0.002907` seconds.

## First Regional Improvement

The legal placement was then optimized with only the 17 `bottom_1` components
movable. Each movable K512 domain alternated candidates around the legal state
and the collision-relaxed quality guide; the other 53 BOTTOM components had
one fixed site. The full-board exact HPWL objective produced:

| Metric | Before | After |
| --- | ---: | ---: |
| HPWL | 18,070.692761 | 17,656.428748 |
| Optimistic score upper bound | 0.844482 | 0.864295 |
| Containment | 100/100 | 100/100 |
| Violations / overlaps | 0 / 0 | 0 / 0 |

The `414.264013` improvement is monotonic and exact. The run ended `FEASIBLE`
at 100.153171 deterministic-time with objective `17656.428764` and bound
`17463.464409`; no optimality claim is made. Evidence hashes are:

- result: `b3edbaee3ea4533124b780fa74c4df760412ef27f09ff1ff0a36b649528734bb`;
- placement: `46fa27d5141fdd3c45b56fd4001c628cca62adbb5b03019bc749027137d3ecf6`;
- canonical selected sites:
  `e3198c8e19e162a4b47d684cc351d2a5d80c02f0be35bdec37f9c755cb996311`.

The next stage fixed that result and optimized the 14 `bottom_2` components.
It reached a proven `OPTIMAL` HPWL `17293.213586` after 23.475082
deterministic-time, improving the second stage by `363.215162` and the legal
starting point by `777.479175`. Exact containment remained 100/100 with zero
violations and zero overlaps; the optimistic score upper bound rose to
`0.882448`. Evidence hashes are:

- result: `5b48ef8bc08968de56d5830520414a672b829317c4f20b84c508d11d11943ca5`;
- placement: `b34c2eb8989d786c814347c5eda30b89ad8bbf6c5acec2b54566eec6efd0ebda`;
- canonical selected sites:
  `8b56268b4e2b007ac1dfcc773268f0841ad0b9fefc662d7559496e88216d43a8`.

The third stage jointly released the 18 page-7 components in `bottom_0` so
the two adjacent logical groups could repack together. It remained `FEASIBLE`
at 150.000156 deterministic-time and reduced exact HPWL to `16966.809973`.
This is a stage improvement of `326.403613` and a cumulative improvement of
`1103.882788`; the optimistic upper bound is `0.899425`. The objective bound
was `16178.841353`, so no optimality claim is made. Exact legality remained
100/100 with zero violations and overlaps. Evidence hashes are:

- result: `4a54c8cfe3fa24c2b093f21bd56eb22231af8ca9d4389e15fea04428ed13fd6b`;
- placement: `79d92b7e2e5fa72d2fed504be23a537e65e48dd37a524e0b6fc04d2dc9267d04`;
- canonical selected sites:
  `89e9edccb1ea9b0f1f5e6c2016923688b2f213e95f13f97e39c314da74d80b0b`.

The fourth stage jointly optimized 19 spatially coupled page-3/4/6 components
in `bottom_0`. It reached `OPTIMAL` after only 4.921191 deterministic-time and
reduced exact HPWL to `16374.593616`. The stage improvement is `592.216357`
and the cumulative improvement is `1696.099145`; the optimistic score upper
bound rose to `0.931954`. Exact legality again remained 100/100 with zero
violations and overlaps. Evidence hashes are:

- result: `2d2eb5d304e14b27d99a585939cbd06a8b9f87135f8ac4ec46c86bd558c5ee0b`;
- placement: `35b7633b4c01c0b154cfd7b0a6395930b834e907c4b48b4c704cc56ceff2b65e`;
- canonical selected sites:
  `b4a58d4379519b5a5479b75010ac4babaec4f544070a9874867dca2c3bbbcf2f`.

The final first-sweep stage optimized the remaining `MHC8601` and `RT601`
sites to `OPTIMAL` in 0.001148 deterministic-time. It reduced HPWL by another
`3.999570` to `16370.594045`, for a first-sweep cumulative improvement of
`1700.098715` and optimistic score upper bound `0.932182`. Exact legality was
unchanged. Evidence hashes are:

- result: `6f5d3e02a5486e80f0b59b3a2db2afee697a9f6ce7b720a182f68e48f1a8d064`;
- placement: `9d5b551670ca4c4e92282769bd64c34856866acbb32c4d6cfcf5678c5df2b6d6`;
- canonical selected sites:
  `0c6e9fbf4c679a9974b0921e15c45a7b6f5fe272573ebf594dc2532a743117a3`.

A second sweep reopened the non-optimal page-7 block with K1024 domains. At
300.001580 deterministic-time it found a better exact legal incumbent with
HPWL `16249.944730`, a stage improvement of `120.649316` and cumulative
improvement of `1820.748031`. The optimistic score upper bound is `0.939103`.
The run remained `FEASIBLE` with objective bound `15539.905363`; it does not
prove the target unreachable. Evidence hashes are:

- result: `b9bafbd1502d4259f6298425de860a8739c8e6916a86a87f7cdad9e65d21a296`;
- placement: `52f35791a8cd3638eb6cebdddbbba94b9a4e45f89d9960e61d36aac13be0827e`;
- canonical selected sites:
  `b3daad5d952f337c82af2ca698aa29e7fbf9981f69b45485c25d30b6606eee70`.

The second-sweep `bottom_1` K1024 solve reached `OPTIMAL` after 112.075929
deterministic-time. It reduced exact HPWL by another `55.419107` to
`16194.525623`, for cumulative improvement `1876.167138` and optimistic score
upper bound `0.942317`. Exact legality remained unchanged. Evidence hashes
are:

- result: `46b6979f342f4d3db8afb966acfc11051ce7c5414f665401c78017ddf367a4ad`;
- placement: `73bfda2b970503cddaa4260a768503499c064c08873d03dc50764e776e1d7fbc`;
- canonical selected sites:
  `b69a9025b5cf41345712cf5f71a493b1ab8275f9ae89574c5d7109d3fe2c5ec4`.

Expanding the page-3/4/6 block to K1024 reached `OPTIMAL` in 6.963012
deterministic-time and reduced HPWL by `68.272715` to `16126.252908`. The
cumulative improvement is `1944.439853`, the optimistic score upper bound is
`0.946306`, and exact legality remains unchanged. Evidence hashes are:

- result: `02a486fec5d0848d62b71e9888c4a69b2d2c0b4bd4eae4c6e4ab512f48d284ec`;
- placement: `da8f69d0f3bec490c24d76d5a49c35ce9af78784aaf8ff62f056690f51717260`;
- canonical selected sites:
  `a9a7f68916ba777ff474e5ac32edf4688654e5d355f4d453d68f4405a86e3cfa`.

A complete TOP K1024 sweep then held the latest BOTTOM state fixed. The
page-6 block improved by `7.432339`; page-2/5/7 was already optimal; and the
page-3/86 block improved by `1.501289`. Every TOP subproblem reached
`OPTIMAL`. The resulting full-board HPWL is `16117.319280`, cumulative
improvement is `1953.373481`, and optimistic score upper bound is `0.946831`.
Exact legality remains 100/100 with zero violations and overlaps. Evidence
hashes are:

- result: `80bc6ee1eb89aafcd53822f6422ee383072a0177f764118fc7c71d8bafe282f5`;
- placement: `f858c733d920398cf12e164bf3f1c6eac94af5f3e9ff78e50edf089f9325c453`;
- canonical selected sites:
  `004ea7004289ce4667f6f8c34c61b772614502d81c293ad5b8baa76f2dbf1ff1`.

Adding manual-baseline projections as a third guide for the BOTTOM page-7
block reduced HPWL by `38.554288` to `16078.764992`. The cumulative legal
improvement is `1991.927769`, with optimistic score upper bound `0.949101`.
The run remained `FEASIBLE` at 500.002032 deterministic-time and preserved
exact legality. Evidence hashes are:

- result: `9751d02bd6a550ec53a63a1ee164a38d44d9ac64a6186a1337182f10b62af42d`;
- placement: `252597015d2e45650195d0c35eaf5a8e9377b3c8d77e612f8e1c96a9a6ab01d4`;
- canonical selected sites:
  `595991aaf3b6311260dbecf0b7ccddbc01315aebc4d4af57d0b1e818de219479`.

An alternating three-guide K1536 sweep then proved the TOP page-2/5/7 and
BOTTOM `bottom_2` blocks `OPTIMAL` without changing HPWL. BOTTOM `bottom_1`
also reached `OPTIMAL` at the same HPWL but selected an equal-objective legal
state with lower mean anchor distance. Starting from that state, the
page-3/4/6 BOTTOM block reached `OPTIMAL` in 10.526191 deterministic-time and
reduced HPWL by `8.936205` to `16069.828787`. The cumulative improvement is
now `2000.863974`, the optimistic score upper bound is `0.949629`, and exact
legality remains 100/100 with zero violations and overlaps. Evidence hashes
are:

- result: `fd87672cee39efd78f4c640d1c012b6ba8e9390cbe764470cf615650aedc2712`;
- placement: `484d2aeef5da13f1ed29e0001f3d11c00918f08949ea59eaa1ee10b69ea520f0`;
- canonical selected sites:
  `aec99eb687c1f1165aff72de452c84eabc4975463675c92a182fb842bd95a8d4`.

## Acceptance Impact

The result remains `809.459215` above the necessary HPWL threshold
`15260.369572`, and `0.949629` is only an optimistic HPWL/RSMT upper bound,
not a native acceptance score. The page-7-only K1536 objective lower bound is
`15420.003200`, so continuing that block while every other site stays fixed
cannot close the gate. Continue with cross-block movement as tracked in
[M336-050](M336-050-page7-net-span-bottleneck.md), then invoke the native
scorer. Acceptance still requires native normalized score at least 1.0 and
promotion of the EMI601 endpoint policy from diagnostic mode.
