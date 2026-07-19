# M336-050: Page-7 Net Spans Require Cross-Block Movement

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `1dbddca`

## Problem

Exact regional coordinate descent reduced full-board HPWL from
`18070.692761` to `16117.319280`, but the necessary score-1 HPWL threshold is
`15260.369572`. Repeatedly enlarging every block would be expensive and would
not identify which fixed blocks prevent further progress.

## Per-Net Finding

The exact legal state was compared against the collision-relaxed quality guide
with identical assignment and EMI601 endpoint policy. Positive per-net HPWL
deltas total `1821.723553`, partly offset by `-405.305752` where the legal
state is already better. Seven of the eight largest positive deltas are in the
two BOTTOM page-7 groups:

| Net | Legal minus guide HPWL |
| --- | ---: |
| `SIM_DET1` | 139.984965 |
| `VSIM2` | 114.986683 |
| `PSIM2_SRST2` | 108.668935 |
| `PSIM2_DATA2` | 108.488401 |
| `PSIM2_SCLK2` | 107.988401 |
| `SIM1_DATA1` | 99.989260 |
| `SIM1_RST1` | 87.990549 |
| `NFC_SWP` | 82.715768 |

These eight nets account for `850.812962` HPWL, approximately the entire
remaining gap at the start of the diagnostic.

The compared inputs were
`/tmp/m336_cd_top_sweep1_page386_k1024.json` at HPWL `16117.319280` and
`/tmp/m336_emi_only_grid01_no_collision.json` at HPWL `14700.901479`.
The paths are transient experiment artifacts; the legal input result,
placement, and canonical-site SHA-256 values are respectively
`80bc6ee1eb89aafcd53822f6422ee383072a0177f764118fc7c71d8bafe282f5`,
`f858c733d920398cf12e164bf3f1c6eac94af5f3e9ff78e50edf089f9325c453`,
and `004ea7004289ce4667f6f8c34c61b772614502d81c293ad5b8baa76f2dbf1ff1`.

## Three-Guide Boundary

The 18 BOTTOM page-7 components were optimized in K1536 domains built evenly
around manual-baseline projections, the current legal state, and the quality
guide. All other BOTTOM sites were fixed. At 500.002032 deterministic-time it
found a legal incumbent at HPWL `16078.764992`, but its valid objective lower
bound was `15420.003200`.

The bound is `159.633628` above the necessary score threshold. Therefore this
page-7-only model cannot pass score 1.0 while every other block stays fixed;
the `FEASIBLE` status does not weaken that bound. Result SHA-256 is
`9751d02bd6a550ec53a63a1ee164a38d44d9ac64a6186a1337182f10b62af42d`.
The placement and canonical-site SHA-256 values are
`252597015d2e45650195d0c35eaf5a8e9377b3c8d77e612f8e1c96a9a6ab01d4`
and `595991aaf3b6311260dbecf0b7ccddbc01315aebc4d4af57d0b1e818de219479`.
The model used OR-Tools `9.15.6755`, one worker, seed `1000`, exact
non-rectangular conflicts, 27,700 candidates, and 52 single-site fixed
domains. It stopped `FEASIBLE` at 500.002032 deterministic-time; it was not
`UNKNOWN` and no global infeasibility conclusion is made.

## Reproduction

The repository's system Python has PyTorch and geometry dependencies but no
OR-Tools; the existing `pcb_pr` Conda environment has OR-Tools but no PyTorch.
Install the exact optional solver packages into a disposable target without
administrator access or production dependency changes:

```bash
python3.11 -m pip install \
  --target /tmp/m336-ortools-py311 \
  --no-deps \
  ortools==9.15.6755 \
  absl-py==2.4.0 \
  protobuf==6.33.6 \
  immutabledict==4.3.1
```

From the repository root, with the two transient guide results present:

```bash
PYTHONPATH="/tmp/m336-ortools-py311:$PWD/install:$PWD" \
M336_SOURCE_JSON=/tmp/m336_cd_top_sweep1_page386_k1024.json \
M336_ASSIGNMENT_JSON=/tmp/m336_emi_only_grid01_assignment.json \
M336_OUTPUT_JSON=/tmp/m336_cd_sweep3_bottom0_page7_three_guides_k1536.json \
M336_PACKING_SIDE=BOTTOM \
M336_USE_BASELINE_GUIDE=1 \
M336_ADDITIONAL_GUIDE_JSONS=/tmp/m336_cd_top_sweep1_page386_k1024.json,/tmp/m336_emi_only_grid01_no_collision.json \
M336_HINT_GUIDE_INDEX=1 \
M336_MANUAL_BASELINE_ENDPOINTS=EMI601 \
M336_CANDIDATE_LIMIT=1536 \
M336_FIX_GUIDE=1 \
M336_MOVABLE_REFDES=C703,FV702,FV703,FV704,FV705,FV706,FV707,FV708,FV709,FV710,R702,R703,R705,R706,R707,R708,R709,R710 \
M336_OPTIMIZE_HPWL=1 \
M336_TIME=900 \
M336_DETERMINISTIC_TIME=500 \
M336_SEED=1000 \
python3.11 experiments/m336/scripts/probe_exact_site_cpsat.py
```

Expected evidence is 100/100 containment, zero keep-in violations, zero
overlaps, HPWL `16078.764992`, objective `16078.765007`, and objective lower
bound `15420.003200`.

## Alternating Sweep

Starting from the page-7 result, four neighboring regional models were
reopened with the same baseline/current/quality guides and K1536 domains:

| Movable block | Status | Deterministic time | HPWL change |
| --- | --- | ---: | ---: |
| TOP page-2/5/7, 10 components | `OPTIMAL` | 7.043199 | 0.000000 |
| BOTTOM `bottom_2`, 14 components | `OPTIMAL` | 22.396480 | 0.000000 |
| BOTTOM `bottom_1`, 17 components | `OPTIMAL` | 99.492609 | 0.000000 |
| BOTTOM page-3/4/6, 19 components | `OPTIMAL` | 10.526191 | -8.936205 |

The `bottom_1` solve changed sites at equal HPWL and lowered mean anchor
distance; using that state enabled the page-3/4/6 improvement to HPWL
`16069.828787`. Exact legality remained 100/100 with zero violations and
overlaps. Result, placement, and canonical-site SHA-256 values are
`fd87672cee39efd78f4c640d1c012b6ba8e9390cbe764470cf615650aedc2712`,
`484d2aeef5da13f1ed29e0001f3d11c00918f08949ea59eaa1ee10b69ea520f0`,
and `aec99eb687c1f1165aff72de452c84eabc4975463675c92a182fb842bd95a8d4`.

## Next Action

Reopen BOTTOM page-7 once from the improved page-3/4/6 state, then jointly
release only blocks appearing in the remaining high-delta nets. Preserve the
current legal incumbent at every stage. If the repeated side-specific sweep
stalls, extend the exact model to separate TOP and BOTTOM collision sets so a
small mixed-side component set can move in one solve. A full global solve is
justified only after these cross-block candidates are assembled; acceptance
still requires native HPWL/RSMT score at least 1.0.

This issue is resolved only when either a legal cross-block model reaches the
native score gate or a valid lower bound for a model containing every relevant
cross-block degree of freedom proves the gate unreachable. A bound from one
fixed-neighbor regional subproblem is insufficient.
