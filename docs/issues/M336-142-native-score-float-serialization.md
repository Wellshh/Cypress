# M336-142: Native Scorer Loses Exact Legality During PL Serialization

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `f0e4cb9`

## Problem

The first required M336-118 native HPWL/FLUTE RSMT replay fails before native
scoring. The reconstructed in-memory placement is exact legal, but
`PlaceDB.write_pl()` serializes coordinates with `%g`, which retains only about
six significant digits. Re-reading that file changes the geometry enough to
create an overlap.

## Evidence

The pre-serialization validator reports 100/100 contained, zero keep-in
violations, and zero overlaps. The serialized placement still has 100/100
containment but creates one BOTTOM overlap between `FV705` and `R709`:

```text
overlap area: 0.000014647367121980288 mm2
maximum coordinate drift: 0.003736545894525989 Cypress units
coordinates changed: 139/139 physical components
```

The generated file is byte-identical to the committed M336-118 `placement.pl`,
so the checkpoint's selected-site certificate is legal while its rounded PL
artifact is not sufficient evidence for the new post-serialization gate.

After changing PL output to binary64 round-trip precision, the scorer reached
native evaluation but exposed a second loss: it inherited the old baseline's
`dtype=float32`. The native output then drifted by
`5.490526950779895e-05` Cypress units. The evaluate-only scorer must use
`float64`; otherwise a high-precision input file is silently quantized in
memory before HPWL/RSMT evaluation.

## Impact

- M336-118 has no valid repeated native score under the new phase contract.
- Native scoring can reject a legal in-memory solution or score coordinates
  different from those independently validated.
- Placement hashes based on the rounded file do not identify the actual
  floating-point placement passed to the scorer.

## Remediation

1. Serialize Bookshelf coordinates with enough precision to round-trip a
   binary64 value.
2. Force the native evaluate-only path to use `float64` without mutating the
   baseline configuration.
3. Add regression tests for exact coordinate round-trip and scorer precision.
4. Require post-serialization exact legality and zero coordinate drift before
   native HPWL/RSMT scoring.
5. Re-run M336-118 twice and compare input hashes, placement hashes, HPWL, and
   RSMT.

## Acceptance Criteria

- The precision regression test passes in source and installed trees.
- M336-118 remains 100/100 contained with zero violations and overlaps after
  serialization.
- Two independent scorer runs produce identical placement bytes and native
  HPWL/RSMT metrics.

## Resolution Evidence

`PlaceDB.write_pl()` now emits coordinates with binary64 round-trip precision,
and the evaluate-only scorer copies its input configuration before forcing
`dtype=float64`. The focused source-tree precision tests pass. The aggregate
M336 baseline suite passes 78/83 tests; the remaining five require the optional
OR-Tools package and do not exercise this native scorer path.

Two independent replays under
`results/m336/native-cypress/baseline/m336-118-score-{1,2}-float64/`
produce the same placement SHA-256
`ce1835c9b2b58a15ef5f27f143bc61b3446ddb06abd280b7e7f9ffcba90b47ab`,
zero coordinate drift, 100/100 containment, zero keep-in violations, and zero
overlaps. Both native evaluations report:

```text
HPWL:             15634.45047733283
FLUTE RSMT:       17333.037
normalized score: 0.9278501538723687
```

This resolves the reproducibility and post-serialization legality blocker. It
also replaces the historical `0.9760733` HPWL-only upper bound with the first
actual native HPWL/FLUTE RSMT score for M336-118 under the new phase contract.
