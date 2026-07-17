# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cypress is a scalable, GPU-accelerated PCB placement method inspired by VLSI. It extends DREAMPlace (a VLSI placement toolkit) with tailored cost functions, constraint handling, and optimized techniques for PCB layouts.

## Build and Run

### Build with Docker (Recommended)
```sh
# Build image (requires SSH keys for private repo access)
docker build --build-arg ssh_prv_key="$(cat ~/.ssh/id_ed25519)" --build-arg ssh_pub_key="$(cat ~/.ssh/id_ed25519.pub)" --squash -t cypress .

# Run container
docker run --gpus 1 -it -v $(pwd):/Cypress cypress bash
cd /Cypress
```

### Build without Docker
```sh
# Install Python dependencies
pip install -r requirements.txt

# Build C++/CUDA components
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/Cypress -DPYTHON_EXECUTABLE=$(which python)
make -j$(nproc)
make install
```

### Run PCB Placement
```sh
cd /Cypress
python dreamplace/Placer.py path/to/config.json
```

### Run Hyperparameter Tuning
```sh
./tuner/run_tuner.sh <gpu_id> <multiobj> <config.json> <input.aux> <base_ppa> <reuse_params> <iterations> <workers> <density_ratio> <congestion_ratio> <min_points> <script_dir> <log_dir>
```

### Run Unit Tests
```sh
python unittest/ops/<op_name>_unittest.py
```

## Architecture

```
Cypress/
├── dreamplace/              # Core placement engine (extended from DREAMPlace)
│   ├── Placer.py           # Main entry point, orchestrates full placement flow
│   ├── NonLinearPlace.py   # Nonlinear optimization core
│   ├── BasicPlace.py       # Base placement utilities
│   ├── Params.py           # Configuration parameter handling
│   ├── PlaceDB.py          # Placement database (cells, nets, pins)
│   ├── PlaceObj.py         # Placement object definitions
│   └── ops/                # PyTorch CUDA/CPU operators
│       ├── density_map/    # Density computation
│       ├── hpwl/           # Half-perimeter wirelength
│       ├── electric_potential/  # Electrostatic modeling
│       ├── rudy/           # Routing density estimation
│       ├── global_swap/    # Global swap optimization
│       └── ...             # Other placement operators
├── tuner/                  # Hyperparameter optimization
│   ├── tuner_train.py      # BOHB-based hyperparameter search
│   └── run_tuner.sh        # Launch script (master + workers)
├── test/                   # Test configurations (JSON)
│   ├── ispd2005/           # ISPD 2005 benchmarks
│   ├── ispd2015/           # ISPD 2015 benchmarks
│   └── tune/               # Tuner configurations
└── artifacts/              # Benchmark data (Bookshelf, KiCad)
```

## Key Components

**Placement Flow** (`dreamplace/Placer.py`): Global placement → Legalization → Detailed placement

**Configuration** (`*.json`): All placement parameters controlled via JSON configs (see `test/simple.json` for minimal example, `test/tune/pcb-configspace.json` for hyperparameter search space)

**Operators** (`dreamplace/ops/`): Individual PyTorch modules implementing placement cost functions and optimizations as CUDA kernels

**Tuner** (`tuner/tuner_train.py`): BOHB (Bayesian Optimization + Hyperband) for PPA (Power-Performance-Area) optimization

## Input Formats

- **Bookshelf**: `.aux` (main), `.nodes`, `.nets`, `.pl`, `.scl` files
- **LEF/DEF**: Standard VLSI library and design exchange formats
- **KiCad**: PCB design files (`.kicad_pcb`)

## Dependencies

- PyTorch 1.6+ (GPU required for acceleration)
- CUDA 9.1+ (compute capability 6.0+)
- GCC 5.1+, CMake 3.14+
- Boost 1.55+, Bison 3.3+
- Cairo (optional, for faster plotting)
