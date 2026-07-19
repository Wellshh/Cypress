# M336-064: Legacy Endpoint Metadata Is Ignored During Replay

**Severity:** Critical
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `0cb6807`

## Problem

Legacy exact-site quality results record the `EMI601` fixed-endpoint override
under `model.manual_baseline_endpoint_overrides`. The shared
`_result_positions` replay path read only the newer top-level
`manual_baseline_endpoints` field. It therefore silently used the runtime-fixed
coordinate when replaying the legacy result.

The affected quality JSON records HPWL `14700.901479`, but the incorrect replay
produced `16037.660192`, a material error of `1336.758713`. Per-net residuals
computed from that replay were invalid and were discarded before selecting a
new movable domain.

## Scope

Generic consumers of legacy selected-site results were affected. The prior
CP-SAT experiments explicitly set `M336_MANUAL_BASELINE_ENDPOINTS=EMI601`, so
their objective and legality evidence did not depend on this missing fallback.

## Fix

Replay now accepts either metadata location. If both are present, their sets
must agree or replay fails with `manual baseline endpoint metadata is
inconsistent`. New outputs continue to use the top-level field.

## Verification

The M336 suite passes 48/48, including legacy fallback, matching dual fields,
and conflicting dual fields. Replaying the legacy quality JSON now exactly
matches its recorded HPWL, with zero floating delta.

The corrected incumbent-minus-quality HPWL is `1134.442717`. Positive per-net
residuals total `1626.449893`, offset by `-492.007176`. The leading fixed
physical boundaries remain page-86 `N31800043` (69.992482), `R604/R605` on
`USB_MOS_CTL` (56.954318), and page-86 `N31800175` (46.646434). Corrected
residual JSON SHA-256 is
`0e89422fd7c01d8cfafbde30adffd737cb8f73798946228cafe4ee393e677f2e`.

## Next Action

Expand the existing 42-component bottom-0/page-7 closure by complete physical
groups covering the corrected page-86 and `R604/R605` boundary endpoints.
Keep the candidate width fixed so movable breadth is the controlled variable.

