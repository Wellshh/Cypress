# M336-103: Monotonic Guide Rank Reaches An Alternate Plateau

**Severity:** Critical
**Status:** Mitigated
**Found:** 2026-07-19
**Affected commit:** `bc34cc4`

## Problem

The M336-076 guide-rank seed improved candidate rank only by allowing HPWL to
regress to `16314.696146`. It did not establish whether rank could cross toward
the certified alternate basin while preserving the current exact HPWL. That
monotonic experiment was blocked by the objective loss fixed in M336-102.

## Method

Eight exact CP-SAT runs used the same support-closed 89-component K256 model:
the alternate basin, current placement, and collision-relaxed quality guide
were weighted `4:1:2`; the certified current placement was a separate complete
hint; and integer HPWL was constrained to at most `15811065584`. One worker,
seeds 1000--1003, and both `automatic` and
`partial_fixed_guide_delta` branching were compared. The only objective was
minimum candidate guide rank.

## Evidence

All eight runs returned `OPTIMAL` at rank and bound `12`, passed the required
guide-support gate and both replay audits, and emitted one byte-identical
placement. Automatic search used 10.93--11.53 deterministic seconds; partial
fixed search used 10.81--10.91. Every result has HPWL
`15811.06557381333`, normalized score upper bound `0.9651702157924906`,
100/100 exact containment, zero keep-in violations, and zero overlaps.

The prior current solution has rank `81` in this domain. The rank-0 alternate
guide has HPWL `15814.564714651957` and is excluded by the hard current ceiling.
The optimum rank-12 state restores `C8603,C8606,C8612` to candidate index 4 and
retains the other 22 alternate-basin changes:

`B402,C201,C202,C301,C302,C402,C405,C501,C502,C601,C604,C606,C610,C611,C701,C703,C8602,C8613,FV302,FV617,FV707,R604`.

Its placement SHA-256 is
`9956865cba18a73080729695d5b412172be8d93b1cb477c002ae8e793dba6ed6`.
An independent all-fixed K1 replay certifies it `OPTIMAL` with 100 single-site
domains, HPWL objective and bound `15811.065584`, passing exact replay and
legality. Certification result SHA-256 is
`e60b87503cf35083f3c3324b710ddf0ac07eab5a93084052e928c033249d669c`.

## Conclusion

The monotonic objective now produces a certified topology near the alternate
basin without sacrificing HPWL, so the diversity limitation is mitigated. It
does not improve the scoring incumbent.

## Rank-12 HPWL Closure

Eight follow-up runs kept the identical model and plateau hint, changed the
objective back to HPWL, and imposed guide rank at most 12. Both branching modes
and seeds 1000--1003 returned `OPTIMAL` at HPWL objective and bound
`15811.065584`. All emitted the certified plateau and passed both replay audits
and exact legality. Automatic runs used 0.307--0.308 deterministic seconds;
partial-fixed runs used 0.304--0.316.

Therefore, within this fixed 89-component K256 candidate domain, no strict
HPWL improvement exists at rank 12 or below; an improving candidate must have
rank at least 13. This is a restricted-domain proof, not a whole-board bound.
The next recovery removes the rank cap while retaining the current HPWL ceiling
and plateau hint. Promote only a strict independently certified improvement.

## Unrestricted HPWL Recovery

The final eight-run recovery removed the rank cap and retained every other
model input, with automatic and partial-fixed branching over seeds 1000--1003
for 300 deterministic seconds each. All runs were `FEASIBLE`, retained rank 12
and HPWL `15811.06557381333`, reproduced placement SHA-256
`9956865cba18a73080729695d5b412172be8d93b1cb477c002ae8e793dba6ed6`,
and passed both replay audits and exact legality.

Automatic best bounds ranged from `14675.326677` to `14697.608727`; all four
partial-fixed bounds were `14667.827965`. These bounds are below the incumbent,
so finite-budget completion does not prove the unrestricted domain optimal or
infeasible. It does show that replacing the current hint with the certified
rank-12 topology changes the retained incumbent but does not improve HPWL.
Stop this same-domain seed ladder and test a materially different candidate
domain or lattice resolution.
