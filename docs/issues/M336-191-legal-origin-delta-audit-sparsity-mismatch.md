# M336-191: Legal-Origin Delta Audit Is Not Sparse

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-21
**Affected commit:** `7526d27`

## Finding

The saved M336-189 E2 trace disproves the sparsity assumption behind the
original exact-delta contract. Every Adam proposal changes all `100/100`
constrained nodes relative to the exact-legal accepted origin. The accepted
states still differ from that origin at `97-100` nodes. Therefore this contract
cannot take a useful delta path:

```text
if origin_report.is_exact_legal and provenance_matches(origin):
    audit_delta(changed_node_ids)
else:
    audit_full()
```

It would either audit nearly the whole board or correctly fall back to the
existing full audit. Implementing it as written cannot close M336-190.

## Measured Contact Trace

The ten accepted E2 steps make `27` global validator calls: `2` calls in the
first three steps and `3` calls in the remaining seven. Each first call audits
the 100-node optimizer proposal. Contact authority then changes only `1-21`
nodes per correction, with a mean of `10.41` over `17` corrections. Hard
projection changes zero nodes in every correction.

This sparse set is relative to the immediately preceding, fully audited
proposal/candidate. That state is Keep-in legal but can contain `10-21` exact
overlap pairs; it is not an exact-legal accepted origin. The distinction is
material because unchanged overlap rows must be retained rather than assumed
absent.

## Strictly Equivalent Incremental Contract

An offline-only implementation may use the preceding exact report if all of
the following hold:

```text
provenance binds exact position bytes and the active geometry context
previous report has zero Keep-in violations and complete overlap-pair rows
changed IDs are recomputed from the two tensors, not trusted from metadata
all report rows incident to changed IDs are discarded
changed Keep-in, fixed, and same-side interactions are recomputed exactly
unchanged rows are retained and the complete report is deterministically rebuilt
otherwise: audit_full()
```

The geometry context must bind PlaceDB identity, constrained templates,
fixed-geometry cache key, epsilon, scale, side assignment, and region mapping.
The fast path must reject stale tensors, incomplete rows, non-constrained
changes, Keep-in-illegal origins, and mismatched contexts. Mixed changed/changed
pairs must be emitted once. Full and delta paths must match overlap floats,
pair ordering, conflict closure, JSON serialization, authority winner, and
placement bytes.

## Runtime Bound

Only the `17` post-correction calls are sparse; the ten initial proposal calls
remain full. More importantly, M336-189 spends only `0.038758447 s` in all 31
E2 position audits while the fixed runtime gap is `0.058410705 s`. Deleting the
entire audit would still leave the measured GPU metric `0.019652258 s` above
the limit. Delta auditing therefore cannot independently provide a stable D1
margin.

## Required Next Evidence

Implement and test the generalized incremental contract only as an offline
measurement. Reuse the synthetic oracle corpus and saved M336 positions, add
stale-provenance and illegal-origin fallbacks, and report full counted-path
timing. Do not run another D1 unless repeated offline evidence demonstrates a
stable end-to-end margin beyond the fixed gate. If it does not, stop D1
micro-optimization and request the already identified human architecture
decision about authority/FLUTE selection frequency. Collision behavior,
anchor control, learning rate, and Legalization remain frozen.

## Resolution Evidence

M336-192 implements the only useful strict-equivalent variant: reuse is bound
to the immediately preceding exact, Keep-in-legal candidate while complete
overlap rows are merged rather than assumed absent. It passes `204/204` real
M336 CPU/H100 float32/float64 report comparisons. The measured saving is only
`0.009932717 s` across the 17 sparse correction calls, so the implementation
mitigates validator cost but cannot authorize another D1.
