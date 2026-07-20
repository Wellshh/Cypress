# M336-130: Residual-Guided Pair Escapes Expose Missing Blocker Support

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `cfed746`

## Problem

The M336-122 18-component K4096 model had never produced a `d=6` incumbent.
Its only hint changed four sites, so a hard minimum of six changed sites made
the hint infeasible. Repeating seeds or guide weights could therefore spend the
entire budget without establishing whether a legal d6 topology was reachable.
The existing M336-121 escape families also covered only four components and did
not exercise most high-residual page-7 endpoints.

## Inconclusive CP-SAT Searches

Two one-worker, `Delta=20`, 300 deterministic-time rank runs returned no
incumbent:

| Domain | Candidates | Build | Solve / DT | Bound | Result SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| Exact M336-122 guides | 73,810 | 121.751 s | 289.085 s / 307.706 | 6 | `8efa014ea6c89bebad3e3b46e2ddc9632d62ded337aabe2cc00a39c25953b8f8` |
| Residual-focused guides | 73,810 | 112.211 s | 298.192 s / 300.003 | 2 | `0f9669a0440cc826f7cdd7fedccce289b6c4a7e1c10d677d0de2ef4cac1eb6fb` |

Both statuses are `UNKNOWN`. The bounds are guide-rank bounds, not HPWL lower
bounds, and neither run is an infeasibility proof. The focused run required and
passed support audits for all five input guides, so missing guide coordinates
do not explain that result.

## Implementation

`build_hybrid_guide.py` now creates deterministic, fail-closed coordinate
guides. It requires identical source/target component identities, finite 2-D
centers, unique requested refdes, and nonzero target displacement. It records
both input hashes and changes only requested components.

`greedy_exact_site_descent.py` now has a default-off guided pair escape through
`--max-escape-pair-moves`. Each candidate pair:

- includes a guide target and either shares a net or releases one exact current
  blocker;
- uses exact keep-in sites and exact BOTH-side collision acceptance;
- requires both components to change site and aggregate squared guide distance
  to decrease strictly;
- obeys both the global escape envelope and per-move HPWL rise cap;
- is selected deterministically by HPWL, guide distance, refdes, and canonical
  region-site index.

Candidate enumeration is bounded to the nearest 512 guide sites per component
plus its exact current site. Search behavior remains feature-off by default;
the result schema only adds explicit zero-valued pair limits and counters.

## Certified Residual Families

Six residual targets produced the following exact results from M336-118 under
the `Delta=20` envelope:

| Target | Actual changed refdes | HPWL | Integer HPWL | Certificate SHA-256 |
| --- | --- | ---: | ---: | --- |
| `VSIM2` | `C703,FV707,R707` | 15647.449081 | 15647449086 | `6243d6d4efd58c2260e4b2f20b518cc2ef99b7633cd77df2d77c73f9f455e3d4` |
| `SIM_DET1` | `FV705,FV708` | 15637.950585 | 15637950590 | `fc5765c1cb17b2ce048f0c377360528e4c099b0ecd63c6c4c5896cf76602f28d` |
| `PSIM2_DATA2` | `R708` | 15636.950263 | 15636950268 | `40d3cd6f31d89cce01ee80bb415f7f8794bc17f30512ffa08bf4778373546ed6` |
| `NFC_SWP` | `FV705,FV706` | 15652.448544 | 15652448550 | `08457061d571710a7f31c21f5c9469ec0e1de41233ed1ecab7a671af749cf3fe` |
| `PSIM2_SRST2` | `C404,FV708` | 15635.450370 | 15635450377 | `07d23079da198800a490c7c68a1ea63bc5569cc96c3eee525d32974d90189291` |
| `PSIM2_SCLK2` | `FV704,FV709` | 15645.449296 | 15645449301 | `cd97eab25e11eb2e4313008d0533c5d7963b4dd89d11d021b0f8d562d8638cc1` |

Every family passed an independent one-worker all-fixed K1 replay: `OPTIMAL`,
100 candidates, zero hint-site distance, 100/100 containment, zero keep-in
violations, zero overlaps, and exact objective/per-net replay. Their manifests
and portable dependencies are under `experiments/m336/guides/M336-130/` and all
declared file hashes pass `sha256sum -c`.

The portable d6 entry point was also loaded from working directory `/tmp`; its
relative assignment and placement dependencies resolved and exact one-opt
replay started from HPWL `15653.448973800429`.

The actual partner moves are important. `SIM_DET1` needs `FV708`, `NFC_SWP`
needs `FV705`, and `PSIM2_SCLK2` needs `FV704`. More significantly,
`PSIM2_SRST2` needs `C404`, which is outside the page-7 18-component support.
This is direct evidence that endpoint-only support is incomplete.

## First Certified d6 Topology

Sequential exact escapes built a legal six-site topology:

```text
VSIM2 triple
  -> add FV705/FV708 guided pair
  -> add R708 DATA2 move
```

It changes `C703,FV705,FV707,FV708,R707,R708`, has HPWL
`15653.448973800429` (rise `18.998496467595`), and stays inside the `Delta=20`
envelope. Its all-fixed K1 objective is `15653448978`; certificate SHA-256 is
`6a8c9a32033c7ee8f8cbdd0e28b9057c216846e801958e9c05b439593961e7a6`
and placement SHA-256 is
`b78b9829b72d89af2fef0db42a5a883c879eb8915e33b711c04011e6d439d758`.
This is the first certified feasible hint satisfying the requested d6 distance.

## Independent Closure

Full-site one-opt reduced the d6 state to `15649.949295985944` and four changed
sites. Three successive exhaustive exact pair scans then followed this strict
chain:

```text
15649.949295985944
  -> 15637.450584728005  (C703/FV707)
  -> 15635.950262542490  (FV705/FV708)
  -> 15634.450477332834  (FV705/FV707)
```

The final placement SHA-256 is
`c69e3d9186ab6d3da64e8696e4e398a782293509bda93bf6bf6c59c6d2359628`,
identical to the already certified M336-129 equal-HPWL swap plateau. The chain
therefore discovers no strict scoring improvement and does not replace
M336-118. A fourth scan from that plateau evaluated 2,890 component pairs and
105,394,431 site combinations in 107.550 seconds, accepted no move, and ended
at `two_optimum` with unchanged HPWL and exact legality.

## Remaining Boundary

M336-130 proves that d6 is geometrically reachable and that explicit pair
ejection is necessary for several residual targets. It does not complete the
residual-guide objective: `R703`, `FV710`, `R709`, and `R710` still have no
certified target-directed displacement, and the coordinate targets originate
from a collision-relaxed quality guide rather than independent per-net span
optimization.

Next, rerun d6 exact rank generation with the portable d6 certificate as the
feasible independent hint, enumerate additional no-goods, and add measured
candidate-set contribution/Jaccard/endpoint coverage. Expand support to `C404`
and the other measured pair partners before d8. Promotion remains forbidden
until floating and integer HPWL are strictly below M336-118 and fresh K1
certification passes.
