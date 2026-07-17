#!/usr/bin/env python3
"""Quick manual hyperparameter search for failing PCB benchmarks."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/home/jybai/pcb-placement/research/gpu-used/Cypress")

def load_base_config(bench_name):
    """Load the current (bad) config as base."""
    config_path = REPO_ROOT / "benchmark_configs" / f"{bench_name}.json"
    with open(config_path) as f:
        return json.load(f)

def run_placement(config, label):
    """Run placement with given config and return result."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "install") + ":" + env.get("PYTHONPATH", "")

    # Write temp config
    tmp_path = REPO_ROOT / f"tmp_{label}.json"
    with open(tmp_path, "w") as f:
        json.dump(config, f, indent=2)

    cmd = [
        sys.executable,
        str(REPO_ROOT / "install" / "dreamplace" / "Placer.py"),
        str(tmp_path),
    ]

    start = time.time()
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    elapsed = time.time() - start

    # Parse DREAMPlace.log
    ppa = None
    log_path = REPO_ROOT / "DREAMPlace.log"
    if log_path.exists():
        with open(log_path) as f:
            for line in f:
                if "Final PPA:" in line:
                    import re
                    match = re.search(r"Final PPA:\s*(\{.*\})", line)
                    if match:
                        try:
                            ppa = eval(match.group(1))
                        except Exception:
                            pass
                    break

    if ppa:
        hpwl = ppa.get("hpwl", float("inf"))
        rsmt = ppa.get("rsmt", float("inf"))
        overflow = ppa.get("overflow", 1.0)
        net_x = ppa.get("net_crossing", float("inf"))
        print(f"  [{label}] HPWL={hpwl:.1f} RSMT={rsmt:.1f} Overflow={overflow:.4f} NetX={net_x:.1f} Time={elapsed:.1f}s")
        return {"hpwl": hpwl, "rsmt": rsmt, "overflow": overflow, "net_crossing": net_x, "time": elapsed}
    else:
        print(f"  [{label}] FAILED (exit={proc.returncode})")
        return {"hpwl": float("inf"), "rsmt": float("inf"), "overflow": 1.0, "net_crossing": float("inf"), "time": elapsed}

def search_small_4():
    print("\n=== Searching small-4 (PB201_A00) ===")
    base = load_base_config("small-4")
    results = []

    # Variants to try
    variants = [
        # Variant 0: current config but with legalize enabled and lower learning rate
        {"legalize_flag": 1, "global_place_stages": [{"num_bins_x": 2048, "num_bins_y": 2048, "iteration": 3000, "learning_rate": 0.002, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.6, "gamma": 0.35, "density_weight": 0.01, "stop_overflow": 0.07},
        # Variant 1: closer to small-6 which works well
        {"legalize_flag": 1, "global_place_stages": [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000, "learning_rate": 0.0025, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.6, "gamma": 0.32, "density_weight": 0.005, "stop_overflow": 0.04},
        # Variant 2: adam with logsumexp, lower lr
        {"legalize_flag": 1, "global_place_stages": [{"num_bins_x": 2048, "num_bins_y": 2048, "iteration": 3000, "learning_rate": 0.002, "wirelength": "logsumexp", "optimizer": "adam", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.65, "gamma": 0.35, "density_weight": 0.02, "stop_overflow": 0.05},
        # Variant 3: small bins, nesterov, low gamma
        {"legalize_flag": 1, "global_place_stages": [{"num_bins_x": 256, "num_bins_y": 256, "iteration": 3000, "learning_rate": 0.003, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.55, "gamma": 0.25, "density_weight": 0.05, "stop_overflow": 0.08},
        # Variant 4: very conservative
        {"legalize_flag": 1, "global_place_stages": [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000, "learning_rate": 0.001, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.5, "gamma": 0.3, "density_weight": 0.1, "stop_overflow": 0.08},
    ]

    for i, variant in enumerate(variants):
        cfg = {**base, **variant}
        # Merge global_place_stages properly
        if "global_place_stages" in variant:
            cfg["global_place_stages"] = variant["global_place_stages"]
        result = run_placement(cfg, f"small-4-v{i}")
        results.append((i, result, cfg))

    best = min(results, key=lambda x: x[1]["hpwl"] if x[1]["hpwl"] != float("inf") else 1e18)
    print(f"\nBest variant for small-4: v{best[0]} with HPWL={best[1]['hpwl']:.1f}")
    return best

def search_small_8():
    print("\n=== Searching small-8 (ET095_A00) ===")
    base = load_base_config("small-8")
    results = []

    variants = [
        # Variant 0: switch to logsumexp, increase gamma
        {"global_place_stages": [{"num_bins_x": 512, "num_bins_y": 1024, "iteration": 3000, "learning_rate": 0.002, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.6, "gamma": 0.35, "density_weight": 0.02, "stop_overflow": 0.08},
        # Variant 1: switch to adam
        {"global_place_stages": [{"num_bins_x": 512, "num_bins_y": 1024, "iteration": 3000, "learning_rate": 0.002, "wirelength": "logsumexp", "optimizer": "adam", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.6, "gamma": 0.35, "density_weight": 0.02, "stop_overflow": 0.08},
        # Variant 2: lower bins, nesterov, logsumexp
        {"global_place_stages": [{"num_bins_x": 256, "num_bins_y": 512, "iteration": 3000, "learning_rate": 0.0025, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.55, "gamma": 0.3, "density_weight": 0.05, "stop_overflow": 0.07},
        # Variant 3: closer to small-7 params (small-7 works well)
        {"global_place_stages": [{"num_bins_x": 256, "num_bins_y": 256, "iteration": 3000, "learning_rate": 0.002, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.5, "gamma": 0.3, "density_weight": 0.1, "stop_overflow": 0.07},
        # Variant 4: conservative
        {"global_place_stages": [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000, "learning_rate": 0.001, "wirelength": "logsumexp", "optimizer": "nesterov", "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}], "target_density": 0.5, "gamma": 0.25, "density_weight": 0.1, "stop_overflow": 0.08},
    ]

    for i, variant in enumerate(variants):
        cfg = {**base, **variant}
        if "global_place_stages" in variant:
            cfg["global_place_stages"] = variant["global_place_stages"]
        result = run_placement(cfg, f"small-8-v{i}")
        results.append((i, result, cfg))

    best = min(results, key=lambda x: x[1]["hpwl"] if x[1]["hpwl"] != float("inf") else 1e18)
    print(f"\nBest variant for small-8: v{best[0]} with HPWL={best[1]['hpwl']:.1f}")
    return best

if __name__ == "__main__":
    best_4 = search_small_4()
    best_8 = search_small_8()

    print("\n=== Summary ===")
    print(f"small-4 best: v{best_4[0]} HPWL={best_4[1]['hpwl']:.1f} RSMT={best_4[1]['rsmt']:.1f}")
    print(f"small-8 best: v{best_8[0]} HPWL={best_8[1]['hpwl']:.1f} RSMT={best_8[1]['rsmt']:.1f}")

    # Save best configs
    with open(REPO_ROOT / "benchmark_configs" / "small-4.json", "w") as f:
        json.dump(best_4[2], f, indent=2)
    with open(REPO_ROOT / "benchmark_configs" / "small-8.json", "w") as f:
        json.dump(best_8[2], f, indent=2)
    print("\nUpdated benchmark_configs/small-4.json and small-8.json with best found configs.")
