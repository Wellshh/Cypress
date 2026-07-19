# M336-110: Fourth 0.05 mm Pair Scan Releases A Blocked Site

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-20
**Affected commit:** `bf1d5d8`

## Search And Improvement

The fourth exact single-pair checkpoint started from the M336-109 certificate.
It evaluated 2,889 relevant pairs and 101,743,226 site combinations in
`107.282044` seconds after confirming no strict one-component move.

The accepted BOTTOM pair has no shared net: `C302` moves to a distant released
site while `MHC8601` shifts by approximately one model unit in y. This physical
coordination decreases HPWL by `0.999892604828`, from `15664.624223551460` to
`15663.624330946632`. Exact containment and overlap validation remain clean.
The stop reason is the intentional one-pair checkpoint, not `two_optimum`.

## Certification

An independent all-fixed K1 replay returned `OPTIMAL`; response, modeled, and
selected-site integer HPWL all equal `15663624338`. The pair result, pair
placement, certification result, and certified placement SHA-256 values are:

- `0fac0be7323673affb3403491afc919c941fdd3085a89ab689981a65ab70c4b4`;
- `7c5feca0f57cf1ccbb9391ff8eabc0da43ad1d81592aeca652700f632f823928`;
- `501086e0f2706d8fcdd4570c9c00b574e5e37dfd2999acf24bfad2f6357a5ca4`;
- `7c5feca0f57cf1ccbb9391ff8eabc0da43ad1d81592aeca652700f632f823928`.

## Remaining Boundary

The normalized score upper bound is `0.9742553351229645`; the necessary score-1
HPWL gap is `403.254759160000`. Continue exact pair checkpoints until a complete
scan returns `two_optimum`.
