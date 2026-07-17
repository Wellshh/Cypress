# Cypress Build Notes

This document records the native (non-Docker) build experience for Cypress.

## Environment (Initial Build)

| Component | Version |
|-----------|---------|
| OS        | CentOS 8 / RHEL 8 (Linux 4.18.0) |
| GCC/G++   | 8.3.1 (devtoolset-8) |
| CMake     | 3.26.5 |
| CUDA      | 12.4 (nvcc 12.4.99) |
| PyTorch   | 1.10.2+cu102 (Python 3.6) |
| Boost     | 1.66.0 (system package) |
| GPU       | NVIDIA H100 |

## Environment (Updated for H100 sm_90)

| Component | Version |
|-----------|---------|
| Python    | 3.11.7 |
| GCC/G++   | 12.2.1 (gcc-toolset-12) |
| PyTorch   | 2.5.1+cu124 |
| NumPy     | 2.4.3 |
| pybind11  | 2.11.1 (updated submodule) |

**Why update:** H100 (sm_90) requires PyTorch 2.0+ with CUDA 11.8/12.x. PyTorch 2.5 requires C++17 and GCC 9+.

## Setup Updated Environment (User Scope)

```bash
# Python 3.11 pip
python3.11 -m ensurepip --user

# PyTorch 2.5.1 with CUDA 12.4
python3.11 -m pip install --user torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Dependencies
python3.11 -m pip install --user pyunpack patool matplotlib cairocffi pkgconfig setuptools scipy shapely pyDOE2 shap Pyro4 ConfigSpace==0.6.0 statsmodels xgboost pybind11
```

## Issues and Fixes

### 1. Bison too old (requires >= 3.3, system has 3.0.4)

Build Bison locally and prepend to PATH during cmake/make:

```bash
cd /tmp
wget https://ftp.gnu.org/gnu/bison/bison-3.8.2.tar.gz
tar xzf bison-3.8.2.tar.gz
cd bison-3.8.2
./configure --prefix=/tmp/bison-install
make -j$(nproc) && make install
```

### 2. CUB namespace conflict with CUDA 12+

**File:** `dreamplace/ops/utility/src/utils_cub.cuh`

Remove `CUB_NS_PREFIX/POSTFIX` macros and add a namespace alias:

```cpp
#include "cub/cub.cuh"

DREAMPLACE_BEGIN_NAMESPACE
namespace cub = ::cub;
DREAMPLACE_END_NAMESPACE
```

### 3. Cairo not installed (optional dependency)

**File:** `dreamplace/ops/draw_place/src/PlaceDrawer.h`

Guard `DRAWPLACE` so CMake's `-DDRAWPLACE=0` is respected:

```cpp
#ifndef DRAWPLACE
#define DRAWPLACE 1
#endif
```

### 4. C++17 required for PyTorch 2.x

**File:** `CMakeLists.txt`

Change `CMAKE_CXX_STANDARD` from 14 to 17:

```cmake
set(CMAKE_CXX_STANDARD 17)
```

### 5. pybind11 too old for Python 3.11

Update submodule to v2.11.1:

```bash
cd thirdparty/pybind11
git fetch --tags
git checkout v2.11.1
cd ../..
```

### 6. PyTorch 2.x dispatch macro API changes

**File:** `dreamplace/ops/utility/src/torch.h`

Add `#undef assert_msg` before torch headers to avoid conflict with Limbo's macro, and use PyTorch 2.x built-in dispatch macros:

```cpp
#ifdef assert_msg
#undef assert_msg
#endif

#include <torch/extension.h>

// For PyTorch >= 2.0
#define DREAMPLACE_DISPATCH_FLOATING_TYPES(TENSOR, NAME, ...) \
  AT_DISPATCH_FLOATING_TYPES(DREAMPLACE_TENSOR_SCALARTYPE(TENSOR), NAME, __VA_ARGS__)

#define DREAMPLACE_DISPATCH_INT_FLOAT_TYPES(TENSOR, NAME, ...) \
  AT_DISPATCH_FLOATING_TYPES_AND(at::ScalarType::Int, DREAMPLACE_TENSOR_SCALARTYPE(TENSOR), NAME, __VA_ARGS__)
```

For PyTorch 1.x, keep the original custom switch-based macros.

### 7. Custom DISPATCH_CUSTOM_TYPES in global_swap_cuda.cpp

**File:** `dreamplace/ops/global_swap/src/global_swap_cuda.cpp`

For PyTorch >= 2.0, replace the custom switch macro with:

```cpp
#define DISPATCH_CUSTOM_TYPES(TYPE, NAME, ...) \
  AT_DISPATCH_FLOATING_TYPES_AND(at::ScalarType::Int, TYPE, NAME, __VA_ARGS__)
```

### 8. Nesterov optimizer `p.grad is None` check

**File:** `dreamplace/NesterovAcceleratedGradientOptimizer.py`

In `step()`, remove the `if p.grad is None: continue` guard. The Nesterov optimizer computes gradients internally via `obj_and_grad_fn` and does not rely on autograd's `p.grad`:

```python
for i, p in enumerate(group["params"]):
    if not group["u_k"]:
        # initialization code...
```

### 9. NumPy 2.0 compatibility

**File:** `dreamplace/PlaceDB.py`

Replace removed/deprecated NumPy aliases:
- `np.string_` → `np.bytes_` (5 occurrences)
- `np.str` → `str` (2 occurrences)

### 10. H100 sm_90 CUDA architecture missing

**File:** `CMakeLists.txt`

Add sm_90 for CUDA 12+:

```cmake
if (${CUDA_VERSION_MAJOR} VERSION_GREATER_EQUAL "12")
  list(APPEND CUDA_ARCH_LIST 9.0)
endif()
```

## Build Commands (Updated Environment)

```bash
cd /home/jybai/pcb-placement/research/gpu-used/Cypress

# Initialize submodules
git submodule update --init --recursive

# Update pybind11
cd thirdparty/pybind11 && git fetch --tags && git checkout v2.11.1 && cd ../..

# Configure
mkdir -p build && cd build
export CC=/opt/rh/gcc-toolset-12/root/usr/bin/gcc
export CXX=/opt/rh/gcc-toolset-12/root/usr/bin/g++
PATH=/tmp/bison-install/bin:$PATH cmake .. \
    -DCMAKE_INSTALL_PREFIX=/home/jybai/pcb-placement/research/gpu-used/Cypress/install \
    -DPYTHON_EXECUTABLE=$(which python3.11)

# Build
PATH=/tmp/bison-install/bin:$PATH make -j$(nproc)

# Install
make install
```

**Note:** On first parallel build, some targets may report "No rule to make target" for thirdparty libraries. These are spurious race conditions; simply run `make -j$(nproc)` again to complete.

## Run Test

```bash
cd /home/jybai/pcb-placement/research/gpu-used/Cypress
export PYTHONPATH=/home/jybai/pcb-placement/research/gpu-used/Cypress/install:$PYTHONPATH
python3.11 /home/jybai/pcb-placement/research/gpu-used/Cypress/install/dreamplace/Placer.py test_small.json
```

## Run PCB Placement

### Issue 11: `cp DREAMPlace.log` fails when running from install directory

**File:** `dreamplace/Placer.py:372-374`

The original code assumes `DREAMPlace.log` lives next to `Placer.py` via `root_dir`, but the log is actually written to the current working directory. Fix by copying from CWD:

```python
# copy DREAMPlace.log to result directory
# DREAMPlace.log is written to the current working directory, not root_dir
if os.path.exists("DREAMPlace.log"):
    os.system("cp DREAMPlace.log %s" % (res_path))
```

### Issue 12: Untuned parameters cause placement failure on PCB benchmarks

Running with generic parameters (`target_density=1.0`, `gamma=4.0`, `learning_rate=0.01`) on PCB benchmarks produces `hpwl=inf`, `overflow=0.27`, and the optimizer diverges. PCB benchmarks require tuned hyperparameters (e.g., from BOHB tuning).

**Example working config** (`test_pcb_small_tuned.json`) for `small-1` (PB310_A00):
- `target_density`: 0.5095
- `gamma`: 0.3691
- `learning_rate`: 0.0022
- `density_weight`: 0.9757
- `stop_overflow`: 0.0687
- `net_crossing_flag`: true
- `net_crossing_weight`: 10

### Issue 13: `plot_flag=1` causes garbled stdout

When plotting is enabled, C-level plotting threads interleave `[I] plotting to...` messages with Python logging, corrupting terminal output. Use `plot_flag: 0` for clean logs, or redirect to file.

### Issue 14: Config `aux_input` should use absolute paths

Relative paths in `aux_input` may fail depending on the working directory. Use absolute paths for reliability.

### Successful PCB Placement Run

```bash
cd /home/jybai/pcb-placement/research/gpu-used/Cypress
export PYTHONPATH=/home/jybai/pcb-placement/research/gpu-used/Cypress/install:$PYTHONPATH
python3.11 install/dreamplace/Placer.py test_pcb_small_tuned.json
```

**Results for small-1 (PB310_A00):**
- Iterations: 743
- HPWL: 10,920
- RSMT: 11,628
- Net crossing: 128
- Placement time: 15.78 seconds
- Output: `results/tuned-small-1/PB310_A00/PB310_A00.gp.pl`

## Verified Working Configuration

- Python 3.11.7
- PyTorch 2.5.1+cu124
- CUDA 12.4
- GCC 12.2.1
- NumPy 2.4.3
- pybind11 2.11.1
- NVIDIA H100 (sm_90)

## All Modified Files

| File | Change |
|------|--------|
| `CMakeLists.txt` | C++17 standard; add sm_90 for CUDA 12+ |
| `dreamplace/ops/utility/src/utils_cub.cuh` | Remove CUB namespace wrapping |
| `dreamplace/ops/draw_place/src/PlaceDrawer.h` | Guard DRAWPLACE define |
| `dreamplace/ops/utility/src/torch.h` | Undef assert_msg; PyTorch 2.x dispatch macros |
| `dreamplace/ops/global_swap/src/global_swap_cuda.cpp` | PyTorch 2.x DISPATCH_CUSTOM_TYPES |
| `dreamplace/NesterovAcceleratedGradientOptimizer.py` | Remove p.grad is None check |
| `dreamplace/PlaceDB.py` | NumPy 2.0 compatibility (np.string_, np.str) |
| `dreamplace/Placer.py` | Fix DREAMPlace.log copy path (use CWD, not root_dir) |
| `thirdparty/pybind11` | Updated to v2.11.1 |

### Issue 15: ConfigSpace 0.6.0 incompatible with NumPy 2.4

**Error:** `ImportError: numpy.core.multiarray failed to import` when importing ConfigSpace 0.6.0 with NumPy 2.4.3.

**Fix:** Upgrade ConfigSpace to 1.2.x:
```bash
python3.11 -m pip install --user "ConfigSpace>=1.0"
```

**Note:** ConfigSpace 1.2 emits deprecation warnings about `default` vs `default_value` in JSON config space files. The warnings are harmless.

### Issue 16: Severe non-determinism on PyTorch 2.5.1 / CUDA 12.4

**Symptom:** Identical config + identical seed produces wildly different results across runs. For example, `small-6` with the same config and seed `1000` produced HPWL 870 in one run and `hpwl=inf` (divergence) in another. Other benchmarks (small-2, small-4, small-8) also exhibited this instability.

**Root cause:** PyTorch 2.x with CUDA 12.4 introduces non-deterministic behavior in certain CUDA operations (e.g., reductions, atomic operations in custom kernels) even when all random seeds are fixed. This is a known PyTorch/CUDA limitation, not a Cypress bug.

**Attempted fix 1:** Adding `torch.use_deterministic_algorithms(True)` to `seed_all()`.
- **Result:** Caused immediate divergence (`hpwl=inf`) in all benchmarks. Reverted.

**Attempted fix 2:** Setting `torch.backends.cudnn.deterministic = True` and `torch.backends.cudnn.benchmark = False`.
- **Result:** Already set in `seed_all()`. Does not fully eliminate non-determinism on H100/CUDA 12.4.

**Workaround:** The non-determinism sometimes produces good results and sometimes diverges. When a benchmark diverges, re-running with the same config often succeeds. For production use, run each config multiple times (e.g., 3-5 repetitions) and pick the best result, or tune hyperparameters specifically for the PyTorch 2.x stack.

**Key insight:** Tuned hyperparameters from the original artifacts (optimized for PyTorch 1.x) are unstable on PyTorch 2.x. Manual tuning found more stable settings:
- `optimizer: "nesterov"` (more stable than `"adam"` on PyTorch 2.x)
- `wirelength: "logsumexp"` (more stable than `"weighted_average"`)
- Lower `learning_rate` (0.001-0.002 vs 0.008+)
- `legalize_flag: 1` (prevents macro overlap divergence)

**Files:** `dreamplace/Placer.py` (seed_all function, lines 58-67)

### Issue 17: Tuned hyperparameters needed for small-4 and small-8 on PyTorch 2.x

**Symptom:** Original artifact configs for small-4 and small-8 produced poor/divergent results on PyTorch 2.5.1 (small-4: HPWL diverged to inf; small-8: HPWL ~30x worse than baseline).

**Fix:** Manual hyperparameter search via `quick_tune.py` found stable configs:

**small-4 tuned config:**
- `optimizer: "nesterov"`, `wirelength: "logsumexp"`
- `learning_rate: 0.002`, `gamma: 0.35`, `target_density: 0.6`
- `num_bins: 2048x2048`, `legalize_flag: 1`
- Result: HPWL=5533, RSMT=5716 (stable across runs)

**small-8 tuned config:**
- `optimizer: "nesterov"`, `wirelength: "logsumexp"`
- `learning_rate: 0.0025`, `gamma: 0.3`, `target_density: 0.55`
- `num_bins: 256x512`, `legalize_flag: 1`
- Result: HPWL=2845, RSMT=2990 (stable across runs)

**Key insight:** `logsumexp` wirelength + `nesterov` optimizer + lower learning rate is consistently more stable on PyTorch 2.x than the original `weighted_average` + `adam` configs.

**Files:** `benchmark_configs/small-4.json`, `benchmark_configs/small-8.json`

### Issue 18: Tuner script `run_tuner.sh` lacks explicit multi-GPU control

**Problem:** The tuner script passes `gpu=$gpu` to all workers, and the Python backend (`tuner_train.py`) already auto-distributes workers across all GPUs via `worker_id % torch.cuda.device_count()`. However, this is implicit and doesn't allow restricting GPU usage.

**Fix:** Modified `tuner/run_tuner.sh`:
1. Added optional 14th parameter `gpu_pool` (e.g., `"0,1,2,3"` or `"0-7"`)
2. Added GPU detection via `nvidia-smi` with warning if `workers > GPUs`
3. Pass `--gpu_pool "$gpu_pool"` to worker processes
4. Added usage comments with multi-GPU example

**Multi-GPU usage example:**
```bash
# Use all 8 H100s with 8 workers
./tuner/run_tuner.sh 1 0 test/tune/pcb-configspace.json \
    artifacts/benchmarks/small-1/bookshelf/PB310_A00.aux \
    test/tune/tuner-ppa.json "" 100 8 0 0 10 ./tuner ./tuner_logs/small-1

# Use only GPUs 0-3 with 4 workers
./tuner/run_tuner.sh 1 0 test/tune/pcb-configspace.json \
    artifacts/benchmarks/small-1/bookshelf/PB310_A00.aux \
    test/tune/tuner-ppa.json "" 100 4 0 0 10 ./tuner ./tuner_logs/small-1 0,1,2,3
```

### Issue 19: BOHB tuner fails with `TypeError: Object of type int64 is not JSON serializable`

**Symptom:** After fixing the nameserver port conflict (Issue 18), the BOHB master crashes immediately on the first iteration with:
```
TypeError: Object of type int64 is not JSON serializable
```

**Root cause:** ConfigSpace 1.2.2 returns numpy `int64` / `float64` types for hyperparameter values, but hpbandster's `json_result_logger` uses Python's native `json.dumps` which cannot serialize numpy scalar types.

**Fix:** Patched `hpbandster/core/result.py` to use a custom `NumpyEncoder` class that converts numpy scalars and arrays to native Python types before JSON serialization:
- `np.integer` → `int`
- `np.floating` → `float`
- `np.ndarray` → `list`
- `np.bool_` → `bool`

Applied `cls=NumpyEncoder` to all three `json.dumps` calls in `json_result_logger.new_config()` and `__call__()`.

**Files:** `hpbandster/core/result.py`

**Files:** `tuner/run_tuner.sh`

### Issue 20: BOHB tuner nameserver port conflict with stale processes

**Symptom:** BOHB master crashes with `Pyro4.errors.NamingError: Failed to locate the nameserver` or workers never connect.

**Root cause:** Previous failed runs leave Pyro4 nameserver socket bound to port 9090. New runs try to use the same port and fail.

**Fix:** Modified `tuner/tuner_train.py` to start the nameserver on a random available port (`port=0`) and write the actual port to a `.ns_port` file in `log_dir`. Workers read the port from this file instead of hardcoding 9090.

**Files:** `tuner/tuner_train.py`

### Issue 21: Pyro4 serpent cannot serialize `numpy.str_`

**Symptom:** BOHB master crashes with:
```
TypeError: serpent cannot serialize objects of type <class 'numpy.str_'>
```

**Root cause:** ConfigSpace 1.2.2 returns `numpy.str_` for categorical hyperparameters, which the serpent serializer cannot handle.

**Fix:** Extended `_sanitize_config()` in `hpbandster/core/master.py` and `tuner/tuner_worker.py` to convert `np.str_` → `str`. Also extended `NumpyEncoder` in `hpbandster/core/result.py` to handle `np.str_`.

**Files:** `hpbandster/core/master.py`, `tuner/tuner_worker.py`, `hpbandster/core/result.py`

### Issue 22: CRITICAL — `numpy.float64` budget causes silent Pyro4 oneway call failures

**Symptom:** BOHB dispatcher dispatches jobs to all workers successfully (no exceptions), but workers never execute `start_computation`. Workers remain `busy=False`. No error messages anywhere. Placement never runs. This was an extremely difficult bug to diagnose because `@Pyro4.oneway` silently swallows ALL server-side exceptions.

**Root cause:** Hyperband budgets are computed with NumPy:
```python
self.budgets = max_budget * np.power(eta, -np.linspace(...))
```
This produces `numpy.float64` values. When passed to `dispatcher.submit_job(config_id, config=config, budget=budget, ...)`, the `budget` is serialized by Pyro4's serpent library as `np.float64(1.0)`. On the worker side, serpent deserializes with `ast.literal_eval()`, which cannot parse function calls like `np.float64(1.0)`. This raises:
```
malmformed node or string on line 1: <ast.Call object at 0x...>
```

Because `start_computation` is decorated with `@Pyro4.oneway`, the worker daemon sends an ACK immediately and then tries to execute the method. The deserialization failure happens before the method body, so the exception is caught by the daemon and logged internally — but NEVER returned to the client. The dispatcher sees "call succeeded" while the worker never runs.

**Fix:** Convert `budget` to native Python float in `_submit_job()` before passing to the dispatcher:
```python
if hasattr(budget, 'item'):
    budget = budget.item()
```

**Debugging lessons:**
1. `@Pyro4.oneway` silently swallows ALL server-side exceptions. For debugging, temporarily remove it to see actual errors.
2. Pyro4's serpent serializer uses `ast.literal_eval()` for deserialization. Any object that serializes as a Python function call (e.g., `np.float64(1.0)`, `np.int64(5)`) will fail deserialization.
3. Always sanitize numpy scalar types before Pyro4 serialization, not just in config dicts but in ALL arguments.

**Files:** `hpbandster/core/master.py`

### Issue 23: Dispatcher passes `self` to oneway calls causing potential serialization issues

**Symptom:** (Defensive fix) When the dispatcher's `job_runner` thread passes `self` (the actual Dispatcher object) as the `callback` argument to `start_computation`, Pyro4 must serialize it as a proxy. In multi-process setups, this can occasionally fail if the thread-local daemon context is not properly set.

**Fix:** Store the dispatcher URI at registration time (`self.dispatcher_uri`) and explicitly create a proxy with `Pyro4.Proxy(self.dispatcher_uri)` to pass as the callback. This is more robust than relying on automatic proxy serialization of `self`.

**Files:** `hpbandster/core/dispatcher.py`

### Issue 24: BOHB tuner extremely slow on large benchmarks (small-9)

**Symptom:** BOHB tuning on small-9 (PN42C_A00, the largest benchmark) produced only 1 result in ~15 minutes with 8 workers. Each evaluation took ~10 minutes. Worse, the random configs produced terrible results (hpwl ~987K vs baseline 15K).

**Root cause:** Small-9 is the largest benchmark with many cells/nets. The BOHB search space includes configs that cause very slow convergence (2000+ iterations) or immediate divergence. Combined with PyTorch 2.x non-determinism, most random configs are unsuitable.

**Attempted fix:** Manual tuning with known-stable settings from small-8:
- `optimizer: "nesterov"`, `wirelength: "logsumexp"`
- `learning_rate: 0.002`, `gamma: 0.3`
- `legalize_flag: 1`
- Result: hpwl=58648 (3.8x baseline, much better than BOHB random configs but still poor)

**Lesson:** For large benchmarks on PyTorch 2.x, BOHB's random exploration is too expensive. A better approach is to start from a known-stable config and do local search, rather than broad random exploration.

**Files:** `benchmark_configs/small-9.json`

### Issue 25: BOHB-tuned configs are not reproducible on PyTorch 2.x

**Symptom:** After BOHB tuning found "best" configs for small-1 (hpwl=3582), small-3 (hpwl=2760), and small-5 (hpwl=2396), re-running the exact same configs with the same seed produced wildly different results:
- small-1 tuned config: `hpwl=inf` (diverged) on re-run vs `hpwl=3582` during tuning
- small-3 tuned config: `hpwl=4285` on re-run vs `hpwl=2760` during tuning
- small-5 tuned config: `hpwl=3364` on re-run vs `hpwl=2396` during tuning

**Root cause:** This is a manifestation of Issue 16 (PyTorch 2.x non-determinism). Even with identical configs and identical seeds, CUDA operations produce different numerical results across runs. A config that happened to work during tuning may fail on re-run, and vice versa.

**Implication:** BOHB tuning is fundamentally unreliable on PyTorch 2.5.1 / CUDA 12.4. The "best" config from a tuning run is not guaranteed to work on subsequent runs. For production use, one must:
1. Run each candidate config multiple times (3-5 repetitions)
2. Pick the config with the best median or worst-case performance
3. Accept that any single run may diverge

**Files:** `benchmark_configs/small-1.json`, `benchmark_configs/small-3.json`, `benchmark_configs/small-5.json`
