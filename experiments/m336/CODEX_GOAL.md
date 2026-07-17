# Codex durable objective: M336 anchor-guided irregular keep-in placement

Modify `Wellshh/Cypress` on the existing `experiment` branch to add a feature-gated M336 experiment in which clustered, non-anchor PCB components are placed as close as practical to their physical anchor while their complete footprints remain inside an assigned TOP/BOTTOM irregular `component_placeable_region`.

Deliver a reproducible implementation and E0–E4 ablation report that:

1. preserves existing behavior when disabled;
2. validates the supplied 25-row/125-member cluster manifest without inventing the two modules missing from the declared count of 27;
3. aligns source geometry coordinates to Cypress coordinates with measured residuals;
4. splits mixed-side clusters into TOP/BOTTOM subgroups;
5. constructs per-component feasible domains rather than testing only component centers;
6. adds anchor attraction, soft keep-in stabilization, and hard feasible-domain projection;
7. removes the narrow-region-breaking `virtual_macro.clamp(min=30)` behavior for this path;
8. uses exact polygon containment and overlap checks as final truth;
9. runs E0 baseline, E1 anchor-only, E2 keepin-only, E3 anchor+keepin, and E4 with exact repair where the environment permits;
10. reports actual commands, git SHA, seeds, hard legality, anchor-distance statistics, HPWL, runtime, regressions, and unresolved issues.

Primary success criterion: E4 has zero keep-in violations and zero constrained-component overlaps. Primary quality comparison: E3/E4 reduce mean and p90 anchor distance versus E2 without more than 10% HPWL regression.
