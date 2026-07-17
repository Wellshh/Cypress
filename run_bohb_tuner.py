#!/usr/bin/env python3
"""
Self-contained BOHB tuner that avoids Pyro4 nameserver port conflicts.
Runs master + workers in-process using Python multiprocessing.
"""
import os
import sys
import json
import time
import argparse
import signal
import random
import multiprocessing as mp
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).parent.resolve()
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT / "install"))
os.environ["PYTHONPATH"] = str(REPO_ROOT / "install") + ":" + os.environ.get("PYTHONPATH", "")

import torch
import hpbandster.core.nameserver as hpns
import hpbandster.core.result as hpres
from hpbandster.optimizers import BOHB, MOBOHB

# Import after setting paths
from tuner.tuner_worker import AutoDMPWorker
from tuner.tuner_utils import str2bool
from tuner.tuner_analyze import get_candidates, plot_pareto


def worker_process(worker_id, gpu_pool, ns_host, ns_port, log_dir, multiobj,
                   d_ratio, c_ratio, default_config, study_seed):
    """Run a single worker process."""
    import time as ttime
    ttime.sleep(5 + worker_id * 2)  # Stagger startup

    if default_config.get("gpu") == "1":
        if gpu_pool == [-1]:
            available_gpus = list(range(torch.cuda.device_count()))
        else:
            available_gpus = gpu_pool
        gpu_id = available_gpus[worker_id % len(available_gpus)]
        default_config["gpu_id"] = gpu_id
        print(f"Worker {worker_id}: using GPU {gpu_id}")

    w = AutoDMPWorker(
        nameserver=ns_host,
        nameserver_port=ns_port,
        run_id=str(study_seed),
        log_dir=log_dir,
        congestion_ratio=c_ratio,
        density_ratio=d_ratio,
        default_config=default_config,
        multiobj=multiobj,
        study_seed=study_seed,
    )
    try:
        w.run(background=False)
    except Exception as e:
        print(f"Worker {worker_id} error: {e}")
        raise


def parse_gpu_pool(s):
    if s == "-1":
        return [-1]
    parts = []
    for p in s.split(","):
        if "-" in p:
            a, b = p.split("-")
            parts.extend(range(int(a), int(b) + 1))
        else:
            parts.append(int(p))
    return parts


def run_tuning(bench_name, aux_path, cfg_path, base_ppa_path, iterations,
               workers, d_ratio, c_ratio, m_points, log_dir, gpu_pool_str,
               multiobj=False, study_seed=0):

    random.seed(study_seed)
    np.random.seed(study_seed)
    torch.manual_seed(study_seed)

    print(f"\n{'='*60}")
    print(f"BOHB Tuning: {bench_name}")
    print(f"  aux: {aux_path}")
    print(f"  workers: {workers}, iterations: {iterations}")
    print(f"  GPU pool: {gpu_pool_str}")
    print(f"{'='*60}\n")

    bench_log_dir = Path(log_dir) / bench_name
    bench_log_dir.mkdir(parents=True, exist_ok=True)
    result_logger = hpres.json_result_logger(directory=str(bench_log_dir), overwrite=True)

    # Load base PPA
    base_ppa = {}
    if base_ppa_path and Path(base_ppa_path).exists():
        with open(base_ppa_path) as f:
            base_ppa = json.load(f)

    default_config = {"aux_input": str(aux_path), "gpu": "1", "base_ppa": base_ppa, "reuse_params": ""}

    # Start nameserver on a random port
    run_id = str(study_seed)
    ns = hpns.NameServer(run_id=run_id, host="127.0.0.1", port=0)
    ns.start()
    ns_host, ns_port = ns.host, ns.port
    print(f"Nameserver started on {ns_host}:{ns_port}")

    # Build configspace
    cs = AutoDMPWorker.get_configspace(cfg_path, study_seed)

    # Start optimizer
    if multiobj:
        motpe_params = {
            "init_method": "random",
            "num_initial_samples": 10,
            "num_candidates": 24,
            "gamma": 0.10,
        }
        bohb = MOBOHB(
            configspace=cs,
            parameters=motpe_params,
            run_id=run_id,
            min_points_in_model=m_points,
            min_budget=1,
            max_budget=3,
            num_samples=64,
            result_logger=result_logger,
        )
    else:
        bohb = BOHB(
            configspace=cs,
            run_id=run_id,
            min_points_in_model=m_points,
            min_budget=1,
            max_budget=3,
            num_samples=64,
            result_logger=result_logger,
        )

    # Launch worker processes
    gpu_pool = parse_gpu_pool(gpu_pool_str)
    worker_procs = []

    def cleanup_workers():
        for p in worker_procs:
            if p.is_alive():
                p.terminate()
                p.join(timeout=2)
                if p.is_alive():
                    p.kill()
                    p.join(timeout=2)

    signal.signal(signal.SIGTERM, lambda s, f: cleanup_workers())

    for i in range(workers):
        p = mp.Process(
            target=worker_process,
            args=(i, gpu_pool, ns_host, ns_port, str(bench_log_dir), multiobj,
                  d_ratio, c_ratio, default_config.copy(), study_seed),
        )
        p.start()
        worker_procs.append(p)
        time.sleep(0.5)

    print(f"Started {workers} workers")

    # Run optimization
    try:
        res = bohb.run(n_iterations=iterations, min_n_workers=workers)
    except KeyboardInterrupt:
        print("Interrupted, shutting down...")
        cleanup_workers()
        bohb.shutdown(shutdown_workers=True)
        ns.shutdown()
        return None

    # Shutdown
    bohb.shutdown(shutdown_workers=True)
    ns.shutdown()
    cleanup_workers()

    # Analysis
    id2config = res.get_id2config_mapping()
    incumbent = res.get_incumbent_id()
    all_runs = res.get_all_runs()

    print(f"\nTotal unique configs: {len(id2config)}")
    print(f"Total runs: {len(all_runs)}")
    if all_runs:
        elapsed = all_runs[-1].time_stamps["finished"] - all_runs[0].time_stamps["started"]
        print(f"Total time: {elapsed:.1f}s")

    # Get Pareto candidates
    try:
        result = hpres.logged_results_to_HBS_result(str(bench_log_dir))
        candidates, paretos, df = get_candidates(result, num=5)
        print("\nPareto candidates:")
        print(candidates.to_markdown())

        # Save best configs
        dest = bench_log_dir / "best_cfgs"
        dest.mkdir(exist_ok=True)
        df.to_pickle(dest / f"{bench_name}.dataframe.pkl")

        for _, row in candidates.iterrows():
            cfg_id = "run-" + "_".join([s for s in str(row['ID']).split() if s.isdigit()])
            print(f"Candidate {cfg_id}: {dict(row)}")

        # Save top config as JSON
        if not candidates.empty:
            best_cfg = candidates.iloc[0].to_dict()
            # Remove internal columns
            for col in ["rsmt", "congestion", "density", "target_density", "convergent",
                        "iteration", "objective", "overflow", "max_density", "cost", "hpwl", "ID"]:
                best_cfg.pop(col, None)
            with open(dest / f"{bench_name}_best_config.json", "w") as f:
                json.dump(best_cfg, f, indent=2)
            print(f"\nBest config saved to {dest / f'{bench_name}_best_config.json'}")
            return best_cfg
    except Exception as e:
        print(f"Analysis error: {e}")

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True)
    parser.add_argument("--aux", required=True)
    parser.add_argument("--cfg", default="test/tune/pcb-configspace.json")
    parser.add_argument("--base-ppa", default="test/tune/tuner-ppa.json")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--d-ratio", type=float, default=0)
    parser.add_argument("--c-ratio", type=float, default=0)
    parser.add_argument("--m-points", type=int, default=10)
    parser.add_argument("--log-dir", default="tuner_logs")
    parser.add_argument("--gpu-pool", default="0,1,2,3,4,5,6,7")
    parser.add_argument("--multiobj", action="store_true")
    parser.add_argument("--study-seed", type=int, default=0)
    args = parser.parse_args()

    # Use spawn for multiprocessing (required with CUDA)
    mp.set_start_method("spawn", force=True)

    best = run_tuning(
        bench_name=args.bench,
        aux_path=args.aux,
        cfg_path=args.cfg,
        base_ppa_path=args.base_ppa,
        iterations=args.iterations,
        workers=args.workers,
        d_ratio=args.d_ratio,
        c_ratio=args.c_ratio,
        m_points=args.m_points,
        log_dir=args.log_dir,
        gpu_pool_str=args.gpu_pool,
        multiobj=args.multiobj,
        study_seed=args.study_seed,
    )

    if best:
        print(f"\nBest config for {args.bench}:")
        for k, v in best.items():
            print(f"  {k}: {v}")
    else:
        print("Tuning failed or no valid configs found")
        sys.exit(1)


if __name__ == "__main__":
    main()
