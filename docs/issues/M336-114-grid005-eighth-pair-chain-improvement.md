# M336-114: Eighth 0.05 mm Pair Scan Unlocks A Follow-Up Move

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `105edfd`

## Search And Improvement

The eighth exact single-pair checkpoint started from the M336-113 certificate.
It evaluated 2,887 relevant pairs and 98,307,503 site combinations in
`106.560293` seconds after confirming the source one-optimum.

The accepted TOP pair `C8653/L8630` shares net 18 and improves HPWL by about
one unit. The changed collision topology then unlocks a strict one-component
`L8607` move in the next sweep for another one-unit reduction. Total HPWL
decreases by `1.999785209657`, from `15660.624653132147` to
`15658.624867922490`. Exact legality remains 100/100 contained with zero
keep-in violations and overlaps.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`; response, modeled, and
selected-site integer HPWL all equal `15658624877`. The checkpoint result,
placement, certification result, and certified placement SHA-256 values are:

- `b28008579cbb4888e20ea45b96afdd89fd65f80712b2ceb48a9eabf7aa2c6eb3`;
- `2e8e355ef094c00da6bb6fa4a5a7282c0ea830734d833446abe3c776836d70b0`;
- `01cc4beb27bcc9058bbad5e772b7a8a55ec5c5260370e6bd79529d7b44fc3954`;
- `2e8e355ef094c00da6bb6fa4a5a7282c0ea830734d833446abe3c776836d70b0`.

## Remaining Boundary

The normalized score upper bound is `0.9745663939525299`; the necessary score-1
HPWL gap is `398.255296135858`. The pair chain remains open, but recent gains
are too small relative to the remaining gap. Retain this certified state and
prioritize higher-order 0.05 mm physical-group searches; return to full pair
closure after each material group improvement.
