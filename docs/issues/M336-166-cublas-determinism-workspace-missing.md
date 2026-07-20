# M336-166: CUDA Determinism Lacks a CuBLAS Workspace Contract

**Severity:** High
**Status:** Resolved
**Found:** 2026-07-20
**Affected commit:** `cc05a44`

## Problem

M336 native configs set `deterministic_flag=1`, but the runner does not set
`CUBLAS_WORKSPACE_CONFIG`. PyTorch therefore warns that the group-balanced anchor
matrix multiplication and its backward pass are not deterministic on CUDA 12.4.

## Evidence

The 50-step cold E3/E4 process logs emit PyTorch determinism warnings from
`anchor_keepin.py:105` and `torch.autograd` and explicitly require either
`CUBLAS_WORKSPACE_CONFIG=:4096:8` or `:16:8`. The run metadata records the GPU,
driver, PyTorch, and CUDA versions but not this environment variable.

## Impact

- A deterministic seed does not prove reproducible GPU coordinates.
- Placement hashes and native scores may drift between repeated runs.
- The final three-seed matrix would have an incomplete execution contract.

## Remediation

Set one explicit CuBLAS workspace value in every native runner subprocess before
CUDA context creation, record it in run provenance, and reject conflicting
values unless the run is explicitly marked nondeterministic. Add a runner test
and repeat one E3/E4 seed twice on the same GPU.

## Acceptance Criteria

- Deterministic native runs record `CUBLAS_WORKSPACE_CONFIG`.
- CuBLAS determinism warnings disappear.
- Two same-seed runs have identical input hashes, placement hash, legality,
  HPWL, and RSMT.
- Feature-off invocations retain their existing environment unless the
  deterministic native contract requests this setting.

## Resolution

The native runner now freezes `CUBLAS_WORKSPACE_CONFIG=:4096:8` before every
placement and scoring subprocess, rejects conflicting values, and records the
contract in result provenance, reports, and reproduction commands. A focused
runner test covers the default, passthrough, override, and conflict behavior.

Two independent checkpoint-warm E3 seed-1000 runs on GPU 2, each with 10 native
Adam iterations, produced identical placement and replay SHA-256
`a6445d6a98180ff4449afdffe37ad313f5215cd336153030c5637aaa10b94c5c`,
HPWL `15632.686697721481`, FLUTE RSMT `17325.676`, legality metrics, and
normalized score `0.9281007794550066`. Both logs record 13 `backward()` calls,
10 changing optimizer steps, and no CuBLAS determinism warning. The repeated
placement still has 28 exact overlap pairs; this resolves execution
determinism only and does not promote the result as legal Cypress evidence.
