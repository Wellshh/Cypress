# CUDA-001: Net-Crossing Accepted Node Coordinates as Pin Coordinates

**Severity:** Critical
**Status:** Mitigated, pending full placement validation
**Found:** 2026-07-17
**Fix commit:** `d9e7674`

## Problem

The Python wrapper could return the native net-crossing operator before
converting node coordinates to pin coordinates. M336 supplied 280 coordinate
values while native metadata referenced 307 pins. Native CPU/CUDA code trusted
the metadata and could read out of bounds, causing heap corruption rather than
a deterministic Python exception. Zero-weight configurations could still invoke
the operator, and one CSR side lookup used a position instead of the pin ID.

## Impact

- Process memory corruption and nonlocal crashes.
- Device-dependent scores and gradients from invalid reads.
- Apparent nondeterminism that cannot be fixed by RNG seeding.
- Disabled objectives still incurred unsafe native execution.

## Implemented Mitigation

- Convert node coordinates with PinPos before invoking native net crossing.
- Skip the operator when its effective weight is zero.
- Validate 1-D shapes, dtypes, devices, CSR monotonicity/span, pin coverage, pin
  IDs, and expected flattened coordinate count in Python and native code.
- Use pin IDs for side mapping and reject negative/out-of-range IDs in kernels.
- Remove a forced CUDA synchronization from the forward path.
- Add rejection tests for node-coordinate vectors and invalid pin IDs.

## Evidence

CUDA 12.4/GCC 12 compilation and installation succeeded on an NVIDIA H100. The
focused `net_crossing_unittest.py` suite passed 3/3, including the CPU golden
result and 20 exactly equal deterministic GPU forward/backward repetitions.

## Remaining Work

1. Run an end-to-end feature-off placement with nonzero net-crossing weight.
2. Run sanitizer or compute-sanitizer coverage over malformed native metadata.
3. Measure the deterministic CPU-reference fallback cost in a realistic tuning
   run and replace it with a fixed-order GPU reduction if prohibitive.

## Acceptance Criteria

- Every malformed shape/CSR/pin mapping fails before kernel launch.
- CPU and GPU scores agree on a representative multi-net fixture.
- At least 50 deterministic GPU repetitions are bitwise equal.
- End-to-end placement completes without allocator or sanitizer errors.
