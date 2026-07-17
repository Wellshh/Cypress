#!/usr/bin/env python3
import json
import os
import subprocess

os.chdir('/home/jybai/pcb-placement/research/gpu-used/Cypress')
os.environ['PYTHONPATH'] = '/home/jybai/pcb-placement/research/gpu-used/Cypress/install'

benchmarks = ['small-6', 'small-7', 'small-8', 'small-10']
results = {}

for bm in benchmarks:
    cfg_file = f'benchmark_configs/{bm}.json'
    if not os.path.exists(cfg_file):
        print(f"Skipping {bm}: config not found")
        continue

    print(f"\n{'='*60}")
    print(f"Running {bm}...")
    print(f"{'='*60}")

    proc = subprocess.run(
        ['python3.11', 'install/dreamplace/Placer.py', cfg_file],
        capture_output=True,
        text=True,
        env={**os.environ, 'PYTHONPATH': '/home/jybai/pcb-placement/research/gpu-used/Cypress/install'}
    )

    ppa = None
    if os.path.exists('DREAMPlace.log'):
        with open('DREAMPlace.log') as f:
            for line in f:
                if 'Final PPA:' in line:
                    ppa = line.strip()

    results[bm] = {
        'exit_code': proc.returncode,
        'ppa_line': ppa,
    }

    print(f"Exit code: {proc.returncode}")
    if ppa:
        print(f"Result: {ppa}")
    else:
        print("No Final PPA found")

with open('/tmp/batch_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n\n=== SUMMARY ===")
for bm, r in results.items():
    print(f"{bm}: exit={r['exit_code']}, ppa={'YES' if r['ppa_line'] else 'NO'}")
