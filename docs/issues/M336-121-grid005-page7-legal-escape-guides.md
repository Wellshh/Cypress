# M336-121: Page-7 Escape Produces Three Certified Guide Topologies

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `e364b4d`

## Problem

M336-120 showed that page7ab seeds and current/quality candidate weights retain
the M336-118 incumbent. A different exact-legal topology was needed without
relaxing the scoring placement, collision checks, or keep-in containment.

## Escape Ablation

An initial eight-seed escape toward the full quality guide moved 78--90
components and raised HPWL by `63.757216` to `95.466066`. All states were exact
legal, but a one-sweep closure returned every run to the incumbent. Inspection
showed that only `R707/R708` changed on page 7; unrelated groups consumed most
of the 100-HPWL escape budget.

A page-7 quality hybrid therefore retained the incumbent coordinates for 82
components and used quality coordinates only for the 17 changed page-7
members. Eight PCG64 order seeds `3000..3007` used three escape sweeps, total
rise budget 100, and per-move rise limit 20. Every state remained 100/100
contained with zero keep-in violations and overlaps.

## Targeted Results

The eight runs converge to three distinct placement families. Every family
changes only `C703`, `FV707`, `R707`, and `R708`:

| Family | Seeds | Escape moves | State HPWL | Rise | Certificate objective |
| --- | --- | ---: | ---: | ---: | ---: |
| A | 3000,3005,3006 | 9 | 15652.448544219742 | 17.998067 | 15652448549 |
| B | 3001,3002,3007 | 9 | 15649.948866405257 | 15.498389 | 15649948871 |
| C | 3003,3004 | 7--9 | 15652.948544219742 | 18.498067 | 15652948549 |

One ordinary closure sweep could not improve any escape state, so all final
search results correctly restored the M336-118 incumbent. The escape states
are not scoring candidates.

Independent all-fixed K1 replays for representative seeds 3000, 3001, and
3003 all returned `OPTIMAL`, with zero hint distance, exact objective replay,
100/100 containment, and zero overlaps. Their certification result and
placement SHA-256 pairs are:

- seed 3000: `ed0f29dcb715e7a74a6807b00de7bccfbddb6e42224ebc1e1f0946981cd13035`, `9a3ea48d129e4ba8b4b57d1f19376028f8744fd97a3e40ee23691cdca9783c5f`;
- seed 3001: `a3a8a8ffbbd3070477e5dec13c82815b561dd5b153d0f2b2f0f4197c9c4b3f15`, `14b534af7e58bd277ff1fcfd4045636756bbb3a9de4386f3c307f021ddec2ed5`;
- seed 3003: `d868b2b3fc0ba0fd5ea675ebaf30495b59220885237d864561b45c798fec2a99`, `1d6830320d438463c3244232c4d68291be34d82bed0a02e9fb7da555cefc434b`.

## Durable Evidence And Next Action

The three certificates, placements, page-7 quality hybrid, and content
manifest are tracked under `experiments/m336/guides/M336-121/`. Use all three
certified states as additional candidate guides in a refreshed page7ab K4096
solve. Keep M336-118 as the independent hint and hard HPWL ceiling; promote
only a strict all-fixed certified improvement.
