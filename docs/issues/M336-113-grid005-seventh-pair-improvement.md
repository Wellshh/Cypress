# M336-113: Seventh 0.05 mm Pair Scan Improves Page-86 Net 29

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `1f170a3`

## Search And Improvement

The seventh exact single-pair checkpoint started from the M336-112 certificate,
confirmed no strict single-component move, and evaluated 2,887 relevant pairs
plus 98,240,365 site combinations in `107.384983` seconds.

`C8622` and `L8602`, which share net 29, each move by one 0.05 mm lattice step
in y. The coordinated BOTTOM page-86 move decreases HPWL by
`0.999892604828`, from `15661.624545736975` to `15660.624653132147`.
Exact legality remains 100/100 contained with zero keep-in violations and
overlaps. The run stopped at the intentional one-pair checkpoint.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`; response, modeled, and
selected-site integer HPWL all equal `15660624662`. The pair result, pair
placement, certification result, and certified placement SHA-256 values are:

- `28102bedc826c3735ed6f8d2e800e112831ce9eaa7c20f52cb2a44a598a20236`;
- `e30c62f0ef17bf38185b9c8235ed7cbdb452a8903358bb228a790fa93e46fe51`;
- `ff4ca2f51f46cb7e9c47a1d03125edd3fcfd756dcc6432233ed9a56a71c9db73`;
- `e30c62f0ef17bf38185b9c8235ed7cbdb452a8903358bb228a790fa93e46fe51`.

## Remaining Boundary

The normalized score upper bound is `0.9744419465882888`; the necessary score-1
HPWL gap is `400.255081345515`. Continue exact pair checkpoints until a full
scan reports `two_optimum`.
