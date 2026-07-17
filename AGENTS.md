# Repository Guidelines

## Project Structure & Module Organization

Core placement logic lives in `dreamplace/`; Python orchestration sits beside C++/CUDA operators in `dreamplace/ops/<operator>/`. Hyperparameter search code is under `tuner/` and `hpbandster/`, and top-level `run_*.py` scripts launch jobs. Configurations and regression inputs are in `test/`, operator tests in `unittest/ops/`, PCB data in `benchmarks/`, and M336 assets in `experiments/m336/`. Treat `thirdparty/` as vendored code. Do not edit generated `build/`, `install/`, `results/`, `tuner_logs/`, or `artifacts/` outputs as source.

## Build, Test, and Development Commands

- `git submodule update --init --recursive` fetches native dependencies.
- `python -m pip install -r requirements.txt` installs Python requirements.
- `cmake -S . -B build -DCMAKE_INSTALL_PREFIX="$PWD/install" -DPYTHON_EXECUTABLE="$(which python)"` configures the native build; CUDA is enabled when detected.
- `cmake --build build -j && cmake --install build` compiles and stages extensions.
- `PYTHONPATH="$PWD/install" python unittest/unittests.py` runs all `*_unittest.py` tests.
- `PYTHONPATH="$PWD/install" python install/dreamplace/Placer.py test_small.json` runs the small placement smoke test.

## Coding Style & Naming Conventions

Use four-space indentation, PEP 8-style `snake_case` for Python functions and variables, and established `CamelCase` class names. Match neighboring C++/CUDA style and keep operator code inside its operator directory. Format changed native files with `clang-format -style=file -i <files>`. Avoid broad formatting, dead commented code, and unrelated vendored changes.

## Testing Guidelines

Use Python `unittest`; name files `*_unittest.py`. Add focused operator tests under `unittest/ops/` and benchmark regressions under `unittest/regression/`. Run the focused test, aggregate suite, and one representative placement before submitting. Report the GPU model, CUDA version, exact commands, and generated metrics for GPU-dependent changes.

## M336 Experiment Discipline

Read `CLAUDE.md`, invoke `$m336-anchor-keepin-experiment`, and treat `experiments/m336/SPEC.md` as the acceptance contract. Work only on `experiment`. Keep core code design-agnostic and all new behavior disabled by default. Preserve side, anchors, fixed cells, and orientation; never substitute the board bounding box for missing geometry. Use the 25 enumerated modules and 125 members while documenting the source's 27-module mismatch. Emit machine-readable results and exact legality evidence; do not claim unrun experiments.

## Commit & Pull Request Guidelines

Follow `CONTRIBUTING.md`: use imperative subjects such as `#123 - Fix deterministic projection` and sign with `git commit -s`. Keep commits and PRs focused, link relevant issues, list validation commands, and attach placement metrics or screenshots when outputs change. Mark unfinished PRs `[WIP]` and include explicit manual test results.
