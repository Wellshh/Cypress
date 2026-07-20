# TEST-001: Aggregate Operator Suite Hides Compatibility Errors

**Severity:** High
**Status:** Open
**Found:** 2026-07-21
**Observed base:** `519c766`

## Problem

The repository aggregate operator command reports ten test errors but exits
with status zero. `unittest/unittests.py` calls `runner.run(suite)` without
checking the returned result or propagating `wasSuccessful()` to the process.
Automation can therefore treat a visibly failed suite as passing.

The ten errors also expose three independent compatibility/API drifts in legacy
operator tests. None of the failing test files or operators is modified by the
M336-174 contact-control worktree, so these errors are not evidence against that
change. They do prevent the aggregate suite from serving as a reliable broad
regression gate.

## Reproduction

On physical GPU 2 with the installed Python/native tree:

```bash
env CUDA_VISIBLE_DEVICES=2 \
  PYTHONPATH="$PWD/install:$PWD:/tmp/m336-ortools-py311" \
  python3.11 unittest/unittests.py
```

Observed footer and shell result:

```text
Ran 232 tests in 4.991s
FAILED (errors=10)
process exit code: 0
```

| Category | Tests | Failure |
| --- | --- | --- |
| NumPy 2 ragged arrays | `adjust_node_area`, `hpwl`, `logsumexp_wirelength`, `pin_utilization`, `rmst_wl`, `rudy`, `weighted_average_wirelength` | `np.array()` rejects nested pin arrays with unequal lengths unless an intentional representation is supplied |
| Native dtype contract | `density_potential` | The test sends `Double` position data to a path whose companion tensors/native kernel expect `Float` |
| Draw API drift | `draw_place` | The test omits the required `num_filler_nodes` and `filename` arguments |
| Boundary API drift | `move_boundary` | The test passes removed keyword arguments such as `xl` to the current constructor |

The seven NumPy failures occur before their operators execute. The two API
failures likewise test obsolete call contracts. The density failure reaches the
native operator but violates its current scalar-type contract.

## Impact

- A zero shell status cannot be used as proof that the aggregate suite passed.
- Current contribution instructions recommend the command without warning that
  failures are not propagated.
- Unrelated compatibility noise can obscure genuine regressions in newly added
  operator tests.
- M336 milestones must continue to report focused suite counts and outputs
  explicitly until this issue is resolved; they must not describe the aggregate
  suite as green.

## Required Remediation

1. Capture the result returned by `TextTestRunner.run()` and exit nonzero when
   `result.wasSuccessful()` is false.
2. Add a focused test proving a synthetic failing test produces a nonzero
   aggregate process status.
3. Replace legacy ragged `np.array()` setup with the actual flat/start-map input
   representation expected by each operator, rather than masking the problem
   with an object array unless the operator explicitly consumes one.
4. Update draw-place and move-boundary tests to the current production
   signatures and assert all newly required semantics.
5. Make density-potential test tensors use one explicit supported dtype and add
   a negative test if mixed dtypes are intentionally rejected.
6. Run the complete CPU/GPU suite under the documented Python 3.11, NumPy 2.4,
   PyTorch 2.5, and CUDA 12.4 environment.

## Acceptance Criteria

- A deliberately failing discovered test makes `unittest/unittests.py` exit
  nonzero.
- All 232 currently discovered tests pass or an intentional skip documents an
  unavailable optional dependency.
- Operator tests exercise current APIs rather than failing during fixture
  construction.
- The aggregate command's shell status and printed unittest result agree.
- The repair is committed independently from M336 native placement behavior.

## M336-176 Recheck

The M336-176 installed-tree regression reran the same command on physical GPU
2 after adding 12 focused tests. The runner reports:

```text
Ran 244 tests in 4.657s
FAILED (errors=10)
process exit code: 0
```

The failure set is unchanged: seven NumPy ragged-array fixtures, one mixed
density-potential dtype, one obsolete draw-place call, and one obsolete
move-boundary call. All 25 exact-contact tests and the new composite-projector
Adam-state test execute in this aggregate run without adding an error. TEST-001
therefore remains open and independent of M336-176.
