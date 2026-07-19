# M336-100: Candidate-Guide Support Was Not Auditable

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-19
**Affected commit:** `0658613`

## Problem

Exact CP-SAT results recorded candidate guides, the complete hint, and the
movable set independently, but did not report whether a restricted model could
represent a candidate guide. With `M336_FIX_GUIDE=1`, components outside
`M336_MOVABLE_REFDES` are fixed to the complete hint. A candidate guide that
differs at those components can still change candidate ordering, but its full
topology is unreachable. This silently invalidated the first M336-099
80-component alternate-basin experiment design.

The comparison must use the actual fixed hint, not always the source. If the
candidate guide is also the hint, its omitted components are already fixed to
the intended coordinates. All-fixed certification results also have an empty
effective movable set, so historical support must come from the originating
search result or an explicit list.

## Resolution

`probe_exact_site_cpsat.py` now emits `candidate_guide_support_audit` in result
and progress JSON. For every guide it records:

- changed modeled components relative to the fixed hint;
- changed components outside the movable set;
- maximum center displacement and a `support_complete` decision;
- required guide indices and the exact fixed-reference JSON.

The default remains audit-only. Setting
`M336_REQUIRED_GUIDE_SUPPORT_INDICES=0` or a comma-separated index set rejects
an incomplete required guide before candidate-domain construction. This does
not expand domains, alter hints, weaken collisions, or change legality.

## Verification

`py_compile`, `git diff --check`, and all 60 M336 unit tests pass. A real-board
fail-fast smoke test rejects the historical 80-component support and names the
nine omitted components. The same audit reports 25 changed components, zero
outside a corrected 89-component union, and passes the required-guide gate.
The completed pre-change 80/89 portfolios remain valid because the new default
does not alter solver semantics.
