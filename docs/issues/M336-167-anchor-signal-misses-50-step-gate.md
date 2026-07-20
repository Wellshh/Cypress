# M336-167: Anchor Signal Misses the 50-Step Quality Gate

**Severity:** High
**Status:** Open
**Found:** 2026-07-20
**Affected commit:** `cc05a44`

## Problem

The bounded adaptive anchor controller now reaches its requested gradient ratio,
but the physical-anchor metric barely changes relative to the otherwise
identical E2 run. Controller correctness has not translated into the required
placement effect.

## Evidence

For seed 1000 on the checkpoint-warm 50-step contract:

| Metric | E2 | E3 | Reduction |
| --- | ---: | ---: | ---: |
| Mean anchor distance | `6.515852 mm` | `6.512543 mm` | `0.0508%` |
| P90 anchor distance | `12.032805 mm` | `12.030223 mm` | `0.0215%` |

The acceptance targets are 25% and 15%. E3 performs 53 backward calls and 50
changing Adam steps. After warm-up, the controller holds effective ratio `0.1`;
its effective lambda converges near `1.0`. E3 improves HPWL/RSMT slightly over
E2 (`15632.496/17356.650` versus `15634.590/17374.695`), so the loss is active,
but its anchor displacement signal is far too weak.

## Remediation

Run the specified controlled ratios `0.05, 0.10, 0.25, 0.50` at the same
50-step budget and compare physical and projected-anchor metrics, overlap growth,
HPWL/RSMT, and effective lambda. Do not resume unbounded legacy scales. If no
ratio approaches the gate, compute per-component feasible-domain lower bounds
and identify whether physical-anchor distance is dominated by unreachable
targets or objective/optimizer scaling.

## Acceptance Criteria

- E3/E4 improves mean anchor distance by at least 25% and p90 by at least 15%
  versus E2, or a geometric lower-bound report supports an explicit decision.
- The selected ratio is bounded, dynamically refreshed, and serialized.
- Anchor gains do not rely on broad E4 packing or exact checkpoint fallback.
- HPWL/RSMT, overlaps, and runtime are reported for every tested ratio.
