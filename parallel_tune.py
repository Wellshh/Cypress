#!/usr/bin/env python3
"""Parallel hyperparameter search using multiple GPUs."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO_ROOT = Path("/home/jybai/pcb-placement/research/gpu-used/Cypress")

def load_base_config(bench_name):
    config_path = REPO_ROOT / "benchmark_configs" / f"{bench_name}.json"
    with open(config_path) as f:
        return json.load(f)

def run_variant(args):
    """Run a single variant on a specific GPU. Returns (variant_id, result dict)."""
    bench_name, variant_id, config, gpu_id = args
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "install") + ":" + env.get("PYTHONPATH", "")
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    tmp_path = REPO_ROOT / f"tmp_{bench_name}_v{variant_id}_gpu{gpu_id}.json"
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

    # Parse DREAMPlace.log from result directory for reliability
    ppa = None
    result_dir = config.get("result_dir", "")
    design = Path(config.get("aux_input", "")).stem
    if result_dir and design:
        log_path = Path(result_dir) / design / "DREAMPlace.log"
    else:
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
    else:
        hpwl = rsmt = float("inf")
        overflow = 1.0
        net_x = float("inf")

    return (variant_id, {
        "hpwl": hpwl, "rsmt": rsmt, "overflow": overflow,
        "net_crossing": net_x, "time": elapsed, "ppa": ppa,
        "exit_code": proc.returncode,
    }, config)

def make_variants(base_config, bench_name):
    """Generate parameter variants to try."""
    variants = []
    # Variant 0: lower gamma, nesterov, logsumexp
    v0 = json.loads(json.dumps(base_config))
    v0["global_place_stages"] = [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000,
        "learning_rate": 0.002, "wirelength": "logsumexp", "optimizer": "nesterov",
        "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}]
    v0["gamma"] = 0.3
    v0["target_density"] = 0.55
    v0["density_weight"] = 0.05
    v0["stop_overflow"] = 0.07
    variants.append(v0)

    # Variant 1: higher lr, adam
    v1 = json.loads(json.dumps(base_config))
    v1["global_place_stages"] = [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000,
        "learning_rate": 0.004, "wirelength": "logsumexp", "optimizer": "adam",
        "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}]
    v1["gamma"] = 0.35
    v1["target_density"] = 0.6
    v1["density_weight"] = 0.02
    v1["stop_overflow"] = 0.06
    variants.append(v1)

    # Variant 2: smaller bins
    v2 = json.loads(json.dumps(base_config))
    v2["global_place_stages"] = [{"num_bins_x": 256, "num_bins_y": 256, "iteration": 3000,
        "learning_rate": 0.0025, "wirelength": "logsumexp", "optimizer": "nesterov",
        "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}]
    v2["gamma"] = 0.25
    v2["target_density"] = 0.5
    v2["density_weight"] = 0.1
    v2["stop_overflow"] = 0.08
    variants.append(v2)

    # Variant 3: very conservative
    v3 = json.loads(json.dumps(base_config))
    v3["global_place_stages"] = [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000,
        "learning_rate": 0.001, "wirelength": "logsumexp", "optimizer": "nesterov",
        "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}]
    v3["gamma"] = 0.2
    v3["target_density"] = 0.5
    v3["density_weight"] = 0.1
    v3["stop_overflow"] = 0.08
    variants.append(v3)

    # Variant 4: weighted_average wirelength (baseline style)
    v4 = json.loads(json.dumps(base_config))
    v4["global_place_stages"] = [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000,
        "learning_rate": 0.002, "wirelength": "weighted_average", "optimizer": "nesterov",
        "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}]
    v4["gamma"] = 0.3
    v4["target_density"] = 0.55
    v4["density_weight"] = 0.05
    v4["stop_overflow"] = 0.07
    variants.append(v4)

    # Variant 5: large bins
    v5 = json.loads(json.dumps(base_config))
    v5["global_place_stages"] = [{"num_bins_x": 1024, "num_bins_y": 1024, "iteration": 3000,
        "learning_rate": 0.0015, "wirelength": "logsumexp", "optimizer": "nesterov",
        "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}]
    v5["gamma"] = 0.35
    v5["target_density"] = 0.6
    v5["density_weight"] = 0.03
    v5["stop_overflow"] = 0.06
    variants.append(v5)

    # Variant 6: higher target density
    v6 = json.loads(json.dumps(base_config))
    v6["global_place_stages"] = [{"num_bins_x": 512, "num_bins_y": 512, "iteration": 3000,
        "learning_rate": 0.002, "wirelength": "logsumexp", "optimizer": "nesterov",
        "Llambda_density_weight_iteration": 10, "Lsub_iteration": 2, "learning_rate_decay": 0.999}]
    v6["gamma"] = 0.3
    v6["target_density"] = 0.65
    v6["density_weight"] = 0.01
    v6["stop_overflow"] = 0.05
    variants.append(v6)

    # Variant 7: original config but with legalize enabled and logsumexp
    v7 = json.loads(json.dumps(base_config))
    gp = v7.get("global_place_stages", [{}])[0]
    gp["wirelength"] = "logsumexp"
    gp["optimizer"] = "nesterov"
    v7["legalize_flag"] = 1
    variants.append(v7)

    # Give each variant a unique result_dir to avoid conflicts
    for i, v in enumerate(variants):
        v["result_dir"] = str(REPO_ROOT / "results" / "tune" / bench_name / f"v{i}")

    return variants

def tune_benchmark(bench_name):
    print(f"\n=== Tuning {bench_name} ===")
    base = load_base_config(bench_name)
    variants = make_variants(base, bench_name)

    # Build args list with GPU assignment
    args_list = []
    for i, v in enumerate(variants):
        gpu_id = i % 8
        args_list.append((bench_name, i, v, gpu_id))

    results = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(run_variant, args): args for args in args_list}
        for future in as_completed(futures):
            variant_id, result, cfg = future.result()
            hpwl = result["hpwl"]
            if hpwl != float("inf"):
                print(f"  [v{variant_id}] HPWL={hpwl:.1f} RSMT={result['rsmt']:.1f} Overflow={result['overflow']:.4f} Time={result['time']:.1f}s")
            else:
                print(f"  [v{variant_id}] FAILED")
            results.append((variant_id, result, cfg))

    # Find best
    best = min(results, key=lambda x: x[1]["hpwl"] if x[1]["hpwl"] != float("inf") else 1e18)
    print(f"Best variant for {bench_name}: v{best[0]} with HPWL={best[1]['hpwl']:.1f}")
    return best

if __name__ == "__main__":
    benchmarks_to_tune = ["small-1", "small-3", "small-6", "small-9"]
    best_configs = {}
    for bench in benchmarks_to_tune:
        best = tune_benchmark(bench)
        best_configs[bench] = best[2]

    # Save best configs
    for bench, cfg in best_configs.items():
        cfg["result_dir"] = str(REPO_ROOT / "results" / "benchmark_runs" / bench)
        out_path = REPO_ROOT / "benchmark_configs" / f"{bench}.json"
        with open(out_path, "w") as f:
            json.dump(cfg, f, indent=2)
        print(f"Saved tuned config: {out_path}")

    print("\n=== Done ===")
