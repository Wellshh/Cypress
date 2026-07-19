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

## Global K64 Follow-up

The all-100 model built 6,380 candidates and returned `FEASIBLE` after
248.446742 wall seconds and 300.000792 deterministic-time. It explored
330,493 conflicts and 3,191,366 branches. Its integer objective improved by
two units to `15836404457`, but floating HPWL remained `15836.404447`; this is
not a strict reported improvement. The valid lower bound is `15113.310818`.
All objective replays agree, and exact legality remains unchanged.

The solve moved six components on the zero-HPWL plateau: `C607`, `C610`,
`FV603`, `MHC8601`, `R601`, and `R606`. Full-domain local closure from that
alternate blocker topology found no strict move. It scanned 2,896 relevant
pairs and 2,129,407 site combinations before stopping at a two-optimum. The
global result, global placement, local result, and local placement SHA-256
values are:

- `7edef65bc75570843b2e11d1c1474e7781c9d481b6616c9db3b787cb752709bd`;
- `2e7d5be0b9817b864e1e92e98cd2d2a5b1274937a991baf853bd601a5ee1aa4b`;
- `09a72af41c6c24e988776608eb6e94a2c3a0cb4584daf48c51497967f0a806bc`;
- `2e7d5be0b9817b864e1e92e98cd2d2a5b1274937a991baf853bd601a5ee1aa4b`.

Refreshing all components at K64 therefore changes plateau topology but does
not close the score gap. Test all-100 K128 next; do not spend more budget on
the proven repeatable K64 neighborhood unless the guides change.
