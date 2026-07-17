#!/usr/bin/env python3
"""
Fixed BOHB/MOBOHB tuner launcher that handles nameserver port conflicts.
Replaces run_tuner.sh with proper explicit port allocation.
"""
import argparse
import os
import subprocess
import sys
import time
import signal
import atexit
from pathlib import Path

# Find repo root
REPO_ROOT = Path(__file__).parent.parent.resolve()
os.chdir(REPO_ROOT)

# Set PYTHONPATH
sys.path.insert(0, str(REPO_ROOT / "install"))
os.environ["PYTHONPATH"] = str(REPO_ROOT / "install") + ":" + os.environ.get("PYTHONPATH", "")


def find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def kill_all(procs):
    for p in procs:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def run_tuner(bench_name, aux_path, cfg_path, base_ppa, iterations, workers,
              d_ratio, c_ratio, m_points, log_dir, gpu_pool, multiobj=False,
              study_seed=0):
    """Run BOHB/MOBOHB tuner for a single benchmark."""
    print(f"\n{'='*60}")
    print(f"Tuning {bench_name}")
    print(f"  aux: {aux_path}")
    print(f"  workers: {workers}, iterations: {iterations}")
    print(f"  GPU pool: {gpu_pool}")
    print(f"{'='*60}\n")

    script_dir = REPO_ROOT / "tuner"
    bench_log_dir = Path(log_dir) / bench_name
    bench_log_dir.mkdir(parents=True, exist_ok=True)

    # Pick a free port for the nameserver
    ns_port = find_free_port()
    print(f"Using nameserver port: {ns_port}")

    # We need to launch nameserver separately with explicit port
    # Then launch master and workers

    procs = []

    def cleanup():
        print("\nCleaning up processes...")
        kill_all(procs)

    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())

    # 1. Start Pyro4 nameserver on explicit port
    ns_env = os.environ.copy()
    ns_env["PYRO_SERIALIZERS_ACCEPTED"] = "pickle"
    ns_proc = subprocess.Popen(
        [sys.executable, "-m", "Pyro4.naming", "-n", "127.0.0.1", "-p", str(ns_port)],
        env=ns_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    procs.append(ns_proc)
    time.sleep(3)  # Give nameserver time to start
    print(f"Nameserver started on port {ns_port}")

    # 2. Start master process
    master_cmd = [
        sys.executable,
        str(script_dir / "tuner_train.py"),
        "--multiobj", str(int(multiobj)),
        "--cfgSearchFile", str(cfg_path),
        "--n_workers", str(workers),
        "--n_iterations", str(iterations),
        "--min_points_in_model", str(m_points),
        "--study_seed", str(study_seed),
        "--log_dir", str(bench_log_dir),
        "--run_args", f"aux_input={aux_path}",
    ]
    master_env = os.environ.copy()
    master_env["PYRO_NS_PORT"] = str(ns_port)
    master_env["PYTHONHASHSEED"] = str(study_seed)
    master_proc = subprocess.Popen(
        master_cmd,
        env=master_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    procs.append(master_proc)
    print(f"Master started (PID {master_proc.pid})")
    time.sleep(5)  # Give master time to register with nameserver

    # 3. Start worker processes
    for i in range(1, workers + 1):
        worker_cmd = [
            sys.executable,
            str(script_dir / "tuner_train.py"),
            "--multiobj", str(int(multiobj)),
            "--log_dir", str(bench_log_dir),
            "--worker",
            "--worker_id", str(i),
            "--study_seed", str(study_seed),
            "--run_args", f"aux_input={aux_path}", "gpu=1",
            f"base_ppa={base_ppa}", "reuse_params=",
            "--density_ratio", str(d_ratio),
            "--congestion_ratio", str(c_ratio),
            "--gpu_pool", gpu_pool,
        ]
        worker_env = os.environ.copy()
        worker_env["PYRO_NS_PORT"] = str(ns_port)
        worker_env["PYTHONHASHSEED"] = str(study_seed)
        worker_proc = subprocess.Popen(
            worker_cmd,
            env=worker_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        procs.append(worker_proc)
        time.sleep(0.5)

    print(f"Started {workers} workers")

    # 4. Stream output and wait
    try:
        stdout, _ = master_proc.communicate(timeout=1800)  # 30 min timeout
        print(stdout)
    except subprocess.TimeoutExpired:
        print("Tuner timed out after 30 minutes")
        cleanup()
        return False

    # Workers should finish shortly after master
    time.sleep(5)
    for p in procs[2:]:  # workers
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()

    # Check master exit code
    if master_proc.returncode != 0:
        print(f"Master failed with exit code {master_proc.returncode}")
        return False
    failed_workers = [p.returncode for p in procs[2:] if p.returncode not in (0, None)]
    if failed_workers:
        print(f"Workers failed with exit codes {failed_workers}")
        return False

    print(f"\nTuning for {bench_name} completed successfully")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run BOHB tuner with explicit port allocation")
    parser.add_argument("--bench", required=True, help="Benchmark name (e.g. small-1)")
    parser.add_argument("--aux", required=True, help="Path to .aux file")
    parser.add_argument("--cfg", default="test/tune/pcb-configspace.json", help="ConfigSpace search config")
    parser.add_argument("--base-ppa", default="test/tune/tuner-ppa.json", help="Base PPA reference")
    parser.add_argument("--iterations", type=int, default=100, help="BOHB iterations")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--d-ratio", type=float, default=0, help="Density cost ratio")
    parser.add_argument("--c-ratio", type=float, default=0, help="Congestion cost ratio")
    parser.add_argument("--m-points", type=int, default=10, help="Min points in model")
    parser.add_argument("--log-dir", default="tuner_logs", help="Log directory")
    parser.add_argument("--gpu-pool", default="0,1,2,3,4,5,6,7", help="GPU IDs to use")
    parser.add_argument("--multiobj", action="store_true", help="Use MOBOHB")
    parser.add_argument("--study-seed", type=int, default=0)
    args = parser.parse_args()

    success = run_tuner(
        bench_name=args.bench,
        aux_path=args.aux,
        cfg_path=args.cfg,
        base_ppa=args.base_ppa,
        iterations=args.iterations,
        workers=args.workers,
        d_ratio=args.d_ratio,
        c_ratio=args.c_ratio,
        m_points=args.m_points,
        log_dir=args.log_dir,
        gpu_pool=args.gpu_pool,
        multiobj=args.multiobj,
        study_seed=args.study_seed,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
