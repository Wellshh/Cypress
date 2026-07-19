# M336-112: Sixth 0.05 mm Pair Scan Reorders A Page-7 Pair

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `66e559a`

## Search And Improvement

The sixth exact single-pair checkpoint started from the M336-111 certificate,
confirmed no strict single-component move, and evaluated 2,889 relevant pairs
plus 91,835,719 site combinations in `103.764823` seconds.

`C703` and `FV707`, which share nets 6 and 75, reorder their y neighborhoods.
This BOTTOM page-7 move decreases HPWL by `0.999892604828`, from
`15662.624438341803` to `15661.624545736975`. Exact legality remains 100/100
contained with zero keep-in violations and overlaps. The one-pair checkpoint
was reached before a two-optimality conclusion.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`; response, modeled, and
selected-site integer HPWL all equal `15661624554`. The pair result, pair
placement, certification result, and certified placement SHA-256 values are:

- `1897a4925227b8a710f7f080332f04bd0da5deb314eab81099df698fea49ad8e`;
- `7f7f262268d6f35f8f2c7283d375c13bee1c6e1df3615ab4e86087849c0bf2cf`;
- `921e61f4d0361a740e02abed8b6b39024779c07b056ac87d5fdc2238f46a57a2`;
- `7f7f262268d6f35f8f2c7283d375c13bee1c6e1df3615ab4e86087849c0bf2cf`.

## Remaining Boundary

The normalized score upper bound is `0.9743797348238972`; the necessary score-1
HPWL gap is `401.254973950343`. Continue exact pair checkpoints until a full
scan reports `two_optimum`.
