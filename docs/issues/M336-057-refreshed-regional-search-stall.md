# M336-057: Refreshed Regional Search Stalls At Certified Incumbent

**Severity:** Critical
**Status:** Open
**Found:** 2026-07-19
**Affected commit:** `7ca16cb`

## Problem

The 42-component bottom-0 plus page-7-TOP K256 model has a valid lower bound
below the score-1 HPWL threshold, but its first incumbent remained 577.282211
above that threshold. Rebuilding candidate domains around the locally closed
certified placement tests whether a shifted current-guide neighborhood alone
can expose the missing coupled move.

## Deterministic Continuation

The continuation retained the same manual/current/quality guides, `EMI601`
endpoint override, movable set, K256 limit, seed 1000, one worker, and 300
deterministic-time budget. It built 10,810 candidates and returned `FEASIBLE`
after 411.085276 solver wall seconds, 639,522 conflicts, and 2,692,498
branches.

No site changed. Response, solved-variable, and selected-site objectives all
equal `15836404459`; floating HPWL is `15836.404447`, with delta
`0.000012412711` inside the rounding allowance. Exact legality remains 100/100
containment with zero violations and overlaps. The valid lower bound is again
`15156.895723`, below the necessary threshold `15260.369572`. This is search
stall evidence, not restricted-domain or global infeasibility.

The result and byte-identical placement SHA-256 values are:

- `e33f2b72e88af94dfab8e01bf56b30c45576db420730e2d5a0f5cd301c8073b2`;
- `e22d5f697dd4779af0c41a6acf63988055cdb99a326e08d02d05aac6e5ed8849`.

## Residual Boundary

With identical fixed-endpoint semantics, the quality guide replays at
`14700.901479`. Positive current-minus-guide per-net deltas total
`1640.100680`, offset by `-504.597713`. The largest page-7 residuals remain
inside the movable set: `VSIM2` (116.986468), `PSIM2_DATA2` (115.987542),
`PSIM2_SCLK2` (97.989475), and `SIM_DET1` (95.989690). Important fixed
boundary residuals include page-86 `N31800043` (69.992482), TOP
`USB_MOS_CTL` through `R604/R605` (56.954318), and page-86 `N31800175`
(46.646434).

## Next Action

Refresh an all-100 K64 model from the certified incumbent. This releases the
fixed physical boundary while keeping only about 6,400 candidates, materially
smaller than an immediate all-region K256 expansion. Audit every returned
objective and certify any strict improvement before local closure. Preserve
`FEASIBLE` and `UNKNOWN` status distinctions; the lower bound does not prove a
threshold-passing placement exists.
