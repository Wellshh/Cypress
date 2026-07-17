#!/usr/bin/env python3
"""
Run all Cypress PCB benchmarks with tuned parameters and collect results.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/home/jybai/pcb-placement/research/gpu-used/Cypress")
BENCHMARK_CONFIGS_DIR = REPO_ROOT / "benchmark_configs"
RESULTS_DIR = REPO_ROOT / "results" / "benchmark_runs"

BENCHMARKS = [
    {"name": "small-1", "design": "PB310_A00", "source": "artifacts/results/small-1/parameters.json"},
    {"name": "small-2", "design": "PB310_A00", "source": "artifacts/results/small-2/parameters.json"},
    {"name": "small-3", "design": "PB310_A00", "source": "artifacts/results/small-3/parameters.json"},
    {"name": "small-4", "design": "PB201_A00", "source": "artifacts/results/small-4/parameters.json"},
    {"name": "small-5", "design": "PB201_A00", "source": "artifacts/results/small-5/parameters.json"},
    {"name": "small-6", "design": "PB201_A00", "source": "artifacts/results/small-6/small-6.json"},
    {"name": "small-7", "design": "ET095_A00", "source": "artifacts/results/small-7/ET095_A00/small-7.json"},
    {"name": "small-8", "design": "ET095_A00", "source": "artifacts/results/small-8/parameters.json"},
    {"name": "small-9", "design": "PN42C_A00", "source": "artifacts/results/small-9/parameters.json"},
    {"name": "small-10", "design": "PN42C_A00", "source": "artifacts/results/small-10/parameters.json"},
]


def prepare_configs(force=False):
    """Create runnable configs from tuned parameters with fixed paths.
    Skips existing configs unless force=True, to preserve manually tuned configs."""
    BENCHMARK_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    for bench in BENCHMARKS:
        out_path = BENCHMARK_CONFIGS_DIR / f"{bench['name']}.json"
        if out_path.exists() and not force:
            print(f"Skipping existing config: {out_path}")
            continue

        src_path = REPO_ROOT / bench["source"]
        with open(src_path) as f:
            config = json.load(f)

        # Fix aux_input to local path (use absolute for reliability)
        bench_dir = REPO_ROOT / "artifacts" / "benchmarks" / bench["name"] / "bookshelf"
        aux_name = bench["design"]
        config["aux_input"] = str(bench_dir / f"{aux_name}.aux")

        # Set local result dir
        config["result_dir"] = str(RESULTS_DIR / bench["name"])

        # Disable plotting for clean logs
        config["plot_flag"] = 0

        # Ensure gpu is set
        config["gpu"] = 1

        with open(out_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Prepared config: {out_path}")


def run_benchmark(config_path: Path):
    """Run a single benchmark and return parsed results."""
    bench_name = config_path.stem
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "install") + ":" + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable,
        str(REPO_ROOT / "install" / "dreamplace" / "Placer.py"),
        str(config_path),
    ]

    print(f"\n{'='*60}")
    print(f"Running {bench_name}...")
    print(f"{'='*60}")

    start = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start

    # Parse DREAMPlace.log for Final PPA
    # Prefer the copy in result_dir/design_name/ since it's isolated per run
    ppa = None
    with open(config_path) as f:
        cfg = json.load(f)
    result_dir = cfg.get("result_dir", "")
    design = cfg.get("design_name", bench_name)
    # Try to infer design_name from aux_input if not in config
    if not design and cfg.get("aux_input"):
        design = Path(cfg["aux_input"]).stem
    log_paths = []
    if result_dir and design:
        log_paths.append(Path(result_dir) / design / "DREAMPlace.log")
    log_paths.append(REPO_ROOT / "DREAMPlace.log")

    for log_path in log_paths:
        if log_path.exists():
            with open(log_path) as f:
                for line in f:
                    if "Final PPA:" in line:
                        match = re.search(r"Final PPA:\s*(\{.*\})", line)
                        if match:
                            try:
                                ppa = eval(match.group(1))
                            except Exception:
                                pass
                        break
            if ppa:
                break

    result = {
        "benchmark": bench_name,
        "exit_code": proc.returncode,
        "runtime_seconds": round(elapsed, 2),
        "ppa": ppa,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
    }

    if ppa:
        print(f"  RSMT: {ppa.get('rsmt', 'N/A')}")
        print(f"  HPWL: {ppa.get('hpwl', 'N/A')}")
        print(f"  Net Crossing: {ppa.get('net_crossing', 'N/A')}")
        print(f"  Iterations: {ppa.get('iteration', 'N/A')}")
        print(f"  Overflow: {ppa.get('overflow', 'N/A')}")
        print(f"  Time: {elapsed:.2f}s")
    else:
        print(f"  WARNING: No Final PPA found (exit code {proc.returncode})")
        if proc.returncode != 0:
            print(f"  STDERR: {proc.stderr[:500]}")

    return result


def build_comparison_table(all_results):
    """Generate markdown comparison table."""
    lines = [
        "# Cypress PCB Benchmark Results",
        "",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary Table",
        "",
        "| Benchmark | Design | Status | RSMT | HPWL | Congestion | Density | Net Crossing | Iterations | Overflow | Max Density | Runtime (s) |",
        "|-----------|--------|--------|------|------|------------|---------|--------------|------------|----------|-------------|-------------|",
    ]

    for r in all_results:
        bench = r["benchmark"]
        design = next(b["design"] for b in BENCHMARKS if b["name"] == bench)
        if r["ppa"]:
            p = r["ppa"]
            status = "PASS" if r["exit_code"] == 0 and p.get("hpwl") != float("inf") else "FAIL"
            rsmt = f"{p.get('rsmt', 'N/A'):.1f}" if isinstance(p.get('rsmt'), (int, float)) and p.get('rsmt') != float('inf') else "N/A"
            hpwl = f"{p.get('hpwl', 'N/A'):.1f}" if isinstance(p.get('hpwl'), (int, float)) and p.get('hpwl') != float('inf') else "N/A"
            congestion = f"{p.get('congestion', 'N/A'):.4f}" if isinstance(p.get('congestion'), (int, float)) and p.get('congestion') != float('inf') else "N/A"
            density = f"{p.get('density', 'N/A'):.4f}" if isinstance(p.get('density'), (int, float)) else "N/A"
            net_crossing = f"{p.get('net_crossing', 'N/A'):.1f}" if isinstance(p.get('net_crossing'), (int, float)) and p.get('net_crossing') != float('inf') else "N/A"
            iterations = p.get('iteration', 'N/A')
            overflow = f"{p.get('overflow', 'N/A'):.4f}" if isinstance(p.get('overflow'), (int, float)) else "N/A"
            max_density = f"{p.get('max_density', 'N/A'):.4f}" if isinstance(p.get('max_density'), (int, float)) else "N/A"
            runtime = r["runtime_seconds"]
        else:
            status = "FAIL"
            rsmt = hpwl = congestion = density = net_crossing = iterations = overflow = max_density = "N/A"
            runtime = r["runtime_seconds"]

        lines.append(
            f"| {bench} | {design} | {status} | {rsmt} | {hpwl} | {congestion} | {density} | {net_crossing} | {iterations} | {overflow} | {max_density} | {runtime} |"
        )

    lines.extend(["", "## Raw Results (JSON)", "", "```json", json.dumps(all_results, indent=2, default=str), "```", ""])
    return "\n".join(lines)


def main():
    prepare_configs()

    all_results = []
    for bench in BENCHMARKS:
        config_path = BENCHMARK_CONFIGS_DIR / f"{bench['name']}.json"
        result = run_benchmark(config_path)
        all_results.append(result)

    # Write comparison table
    md = build_comparison_table(all_results)
    md_path = REPO_ROOT / "BENCHMARK_RESULTS.md"
    with open(md_path, "w") as f:
        f.write(md)
    print(f"\nComparison table written to: {md_path}")

    # Write raw JSON
    json_path = REPO_ROOT / "benchmark_results.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"Raw results written to: {json_path}")

    # Summary
    passed = sum(1 for r in all_results if r["ppa"] and r["ppa"].get("hpwl") != float("inf") and r["exit_code"] == 0)
    failed = len(all_results) - passed
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY: {passed} passed, {failed} failed out of {len(all_results)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
