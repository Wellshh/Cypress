# M336-111: Fifth 0.05 mm Pair Scan Exchanges Coupled Sites

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `a45468e`

## Search And Improvement

The fifth exact single-pair checkpoint started from the M336-110 certificate,
confirmed no strict one-component move, and evaluated 2,891 relevant pairs and
91,668,792 site combinations in `105.201870` seconds.

`C501` and `C502`, which share nets 6 and 73, exchange their y neighborhoods
while both shift by approximately one model unit in x. This coordinated TOP
move decreases HPWL by `0.999892604828`, from `15663.624330946632` to
`15662.624438341803`. Exact legality remains 100/100 contained with zero
keep-in violations and overlaps. The run stopped at the one-pair checkpoint,
not at a two-optimum.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`; response, modeled, and
selected-site integer HPWL all equal `15662624446`. The pair result, pair
placement, certification result, and certified placement SHA-256 values are:

- `bb5fd3a1d7936c4ebab9c55a18dc3a4af03dca594851aabec901ffb4e913a35b`;
- `5e6ea303d804fec212b47888218664cf27ffec59c6e7d7662c346d27d78c90ff`;
- `01d29bd77c4edeff3fa75729b5dcb7f49658a641dd0920f15441fa0d02b215c5`;
- `5e6ea303d804fec212b47888218664cf27ffec59c6e7d7662c346d27d78c90ff`.

## Remaining Boundary

The normalized score upper bound is `0.9743175310026294`; the necessary score-1
HPWL gap is `402.254866555171`. Continue exact pair checkpoints until a full
scan reports `two_optimum`.
