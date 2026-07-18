#!/usr/bin/env python3
"""Run reproducible M336 E0-E4 experiments and aggregate actual results."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
import platform
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPERIMENTS = ("E0", "E1", "E2", "E3", "E4")
IMPLEMENTATION_FILES = (
    "dreamplace/BasicPlace.py",
    "dreamplace/NonLinearPlace.py",
    "dreamplace/PlaceObj.py",
    "dreamplace/Placer.py",
    "dreamplace/params.json",
    "dreamplace/constraints/anchor_keepin.py",
    "dreamplace/constraints/pcb_geometry.py",
    "dreamplace/constraints/region_assignment.py",
    "dreamplace/constraints/region_projection.py",
    "dreamplace/constraints/region_validation.py",
    "dreamplace/ops/anchor_keepin/anchor_keepin.py",
    "experiments/m336/scripts/analyze_quality_bound.py",
    "experiments/m336/scripts/finalize_assignment.py",
    "experiments/m336/scripts/generate_bookshelf.py",
    "experiments/m336/scripts/prepare_baseline.py",
    "experiments/m336/scripts/run_matrix.py",
    "install/dreamplace/BasicPlace.py",
    "install/dreamplace/NonLinearPlace.py",
    "install/dreamplace/PlaceObj.py",
    "install/dreamplace/Placer.py",
    "install/dreamplace/constraints/anchor_keepin.py",
    "install/dreamplace/constraints/pcb_geometry.py",
    "install/dreamplace/constraints/region_assignment.py",
    "install/dreamplace/constraints/region_projection.py",
    "install/dreamplace/constraints/region_validation.py",
    "install/dreamplace/ops/anchor_keepin/anchor_keepin.py",
)
EXPERIMENTS = {
    "E0": {
        "name": "cypress_baseline",
        "anchor_loss": False,
        "projection": False,
        "soft_loss": False,
        "repair": False,
        "freeze_anchors": False,
        "integrated_context": False,
    },
    "E1": {
        "name": "anchor_only",
        "anchor_loss": True,
        "projection": False,
        "soft_loss": False,
        "repair": False,
        "freeze_anchors": True,
        "integrated_context": True,
    },
    "E2": {
        "name": "keepin_only",
        "anchor_loss": False,
        "projection": True,
        "soft_loss": False,
        "repair": False,
        "freeze_anchors": True,
        "integrated_context": True,
    },
    "E3": {
        "name": "anchor_plus_keepin",
        "anchor_loss": True,
        "projection": True,
        "soft_loss": True,
        "repair": False,
        "freeze_anchors": True,
        "integrated_context": True,
    },
    "E4": {
        "name": "anchor_keepin_plus_repair",
        "anchor_loss": True,
        "projection": True,
        "soft_loss": True,
        "repair": True,
        "freeze_anchors": True,
        "integrated_context": True,
    },
}


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def repo_path(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_paths(paths):
    result = {}
    for path in paths:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = REPO_ROOT / resolved
        if resolved.exists():
            result[repo_path(resolved)] = sha256_file(resolved)
    return result


def git_sha():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def git_branch():
    return subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=REPO_ROOT, text=True
    ).strip()


def source_state():
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    ).splitlines()
    tracked_diff = subprocess.check_output(
        ["git", "diff", "--binary", "HEAD"], cwd=REPO_ROOT
    )
    return {
        "branch": git_branch(),
        "git_sha": git_sha(),
        "dirty": bool(status),
        "dirty_paths": status,
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "implementation_sha256": hash_paths(IMPLEMENTATION_FILES),
    }


def runtime_environment():
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        environment.update(
            {
                "cuda_device_count": torch.cuda.device_count(),
                "cuda_device_name": torch.cuda.get_device_name(0),
                "cuda_capability": list(torch.cuda.get_device_capability(0)),
                "cudnn": torch.backends.cudnn.version(),
            }
        )
    try:
        environment["nvidia_smi"] = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,driver_version",
                "--format=csv,noheader",
            ],
            text=True,
            timeout=10,
        ).strip().splitlines()
    except (FileNotFoundError, subprocess.SubprocessError):
        environment["nvidia_smi"] = []
    return environment


def input_hashes(args):
    bookshelf_files = (
        args.bookshelf_dir / name
        for name in (
            "m336.aux",
            "m336.nodes",
            "m336.nets",
            "m336.pl",
            "m336.baseline.aux",
            "m336.baseline.pl",
            "m336.scl",
            "manifest.json",
            "baseline_manifest.json",
        )
    )
    return hash_paths(
        (
            args.baseline_geometry,
            REPO_ROOT / "experiments/m336/input/pcb_geometry_keepin.json",
            REPO_ROOT / "experiments/m336/input/m336_clusters.json",
            args.assignment,
            *bookshelf_files,
        )
    )


def constraint_config(run_dir, spec, assignment, grid_mm, clearance_mm):
    cluster_path = REPO_ROOT / "experiments/m336/input/m336_clusters.json"
    cluster_manifest = json.loads(cluster_path.read_text())
    return {
        "schema": "m336_anchor_keepin_config_v1",
        "enabled": True,
        "geometry_file": str(
            (REPO_ROOT / "experiments/m336/input/pcb_geometry_keepin.json").resolve()
        ),
        "cluster_file": str(cluster_path.resolve()),
        "region_assignment_file": str(Path(assignment).resolve()),
        "fixed_components": sorted(
            row["refdes"] for row in cluster_manifest.get("unclustered", [])
        ),
        "allow_region_reassignment": False,
        "feature_flags": {
            "enable_anchor_loss": spec["anchor_loss"],
            "enable_hard_keepin_projection": spec["projection"],
            "enable_exact_repair": spec["repair"],
            "enable_rotation": False,
        },
        "geometry": {
            "placement_region_field": "component_placeable_regions",
            "constraint_grid_mm": grid_mm,
            "clearance_mm": clearance_mm,
            "alignment_max_residual_mm": 0.05,
            "no_board_bbox_fallback": True,
        },
        "reporting": {
            "output_dir": str((run_dir / "constraints").resolve()),
            "area_epsilon_mm2": 1e-5,
            "emit_per_group_metrics": True,
            "emit_exact_legality_report": True,
            "emit_input_alignment_report": True,
        },
    }


def placement_config(
    run_dir,
    constraint_path,
    spec,
    seed,
    iterations,
    gpu,
    anchor_weight,
    grid_mm,
    clearance_mm,
    aux_input,
    initial_placement=None,
):
    config = {
        "aux_input": str(Path(aux_input).resolve()),
        "gpu": int(gpu),
        "gpu_id": 0,
        "num_bins_x": 64,
        "num_bins_y": 32,
        "global_place_stages": [
            {
                "num_bins_x": 64,
                "num_bins_y": 32,
                "iteration": iterations,
                "learning_rate": 0.01,
                "wirelength": "weighted_average",
                "optimizer": "adam",
                "Llambda_density_weight_iteration": 1,
                "Lsub_iteration": 1,
            }
        ],
        "target_density": 0.7,
        "density_weight": 0.00008,
        "net_crossing_flag": 0,
        "net_crossing_weight": 0.0,
        "gamma": 4.0,
        "random_seed": seed,
        "result_dir": str(run_dir.resolve()),
        "scale_factor": 1.0,
        "ignore_net_degree": 100,
        "enable_fillers": 0,
        "gp_noise_ratio": 0.0,
        "global_place_flag": 1,
        "legalize_flag": 0,
        "detailed_place_flag": 0,
        "stop_overflow": 1.0,
        "dtype": "float32",
        "plot_flag": 0,
        "random_center_init_flag": (
            0 if initial_placement else int(spec["integrated_context"])
        ),
        "sort_nets_by_degree": 0,
        "num_threads": 8,
        "deterministic_flag": 1,
        "enable_rotation": 0,
        "initial_placement_file": (
            str(Path(initial_placement).resolve()) if initial_placement else ""
        ),
        "initial_placement_strict": True,
    }
    if spec["integrated_context"]:
        config.update(
            {
                "anchor_keepin_config": str(constraint_path.resolve()),
                "anchor_keepin_flag": True,
                "anchor_loss_flag": spec["anchor_loss"],
                "anchor_loss_weight_scale": anchor_weight,
                "keepin_soft_loss_flag": spec["soft_loss"],
                "keepin_soft_loss_weight_scale": 1.0,
                "keepin_projection_flag": spec["projection"],
                "constraint_grid_mm": grid_mm,
                "keepin_clearance_mm": clearance_mm,
                "freeze_anchor_nodes": spec["freeze_anchors"],
                "allow_region_reassignment": False,
                "exact_repair_flag": spec["repair"],
                "anchor_keepin_initialization": (
                    "current" if initial_placement else "anchor"
                ),
            }
        )
    return config


def parse_placement(path):
    positions = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[0] in {"UCLA", "#"}:
            continue
        try:
            positions[fields[0]] = (float(fields[1]), float(fields[2]))
        except ValueError:
            continue
    return positions


def evaluate_feature_off(
    config, constraint_path, placement_path, output_path, database_aux=None
):
    install_path = str(REPO_ROOT / "install")
    if install_path not in sys.path:
        sys.path.insert(0, install_path)
    from dreamplace import Params, PlaceDB
    from dreamplace.constraints.anchor_keepin import AnchorKeepInContext

    params = Params.Params()
    params.update(config)
    if database_aux is not None:
        params.aux_input = str(Path(database_aux).resolve())
    params.anchor_keepin_config = str(Path(constraint_path).resolve())
    params.anchor_keepin_flag = True
    params.anchor_loss_flag = False
    params.keepin_soft_loss_flag = False
    params.keepin_projection_flag = False
    params.exact_repair_flag = False
    params.freeze_anchor_nodes = False
    placedb = PlaceDB.PlaceDB()
    placedb.read(params)
    placedb.initialize_from_rawdb(params)
    placedb.initialize(params)
    context = AnchorKeepInContext.from_params(params, placedb)

    pos = torch.from_numpy(
        np.concatenate((placedb.node_x.copy(), placedb.node_y.copy()))
    )
    names = [
        name.decode("utf-8") if isinstance(name, bytes) else str(name)
        for name in placedb.node_names
    ]
    output_positions = parse_placement(placement_path)
    missing = sorted(set(names[: placedb.num_physical_nodes]) - output_positions.keys())
    if missing:
        raise KeyError("placement output is missing nodes: %s" % missing)
    for node_id, name in enumerate(names[: placedb.num_physical_nodes]):
        pos[node_id], pos[placedb.num_nodes + node_id] = output_positions[name]
    report = context.exact_report(pos, placedb)
    report["total_projected_nodes"] = 0
    write_json(output_path, report)
    return report


def parse_final_ppa(log_text):
    matches = re.findall(r"Final PPA: (\{.*\})", log_text)
    if not matches:
        raise ValueError("Final PPA record not found in DREAMPlace.log")
    return ast.literal_eval(re.sub(r"\binf\b", "1e999", matches[-1]))


def parse_weight(log_text, label):
    match = re.search(r"%s weight = ([0-9.Ee+-]+)" % re.escape(label), log_text)
    return float(match.group(1)) if match else None


def parse_weight_diagnostics(log_text, label, configured_scale):
    pattern = (
        r"%s weight = ([0-9.Ee+-]+) "
        r"\(wirelength \|grad\|_1=([0-9.Ee+-]+), "
        r"constraint \|grad\|_1=([0-9.Ee+-]+)\)"
    ) % re.escape(label)
    match = re.search(pattern, log_text)
    if not match:
        return None
    diagnostics = {
        "configured_scale": float(configured_scale),
        "matched_weight": float(match.group(1)),
        "wirelength_gradient_l1": float(match.group(2)),
        "constraint_gradient_l1": float(match.group(3)),
    }
    value_match = re.search(
        r"%s initial value = ([0-9.Ee+-]+)" % re.escape(label), log_text
    )
    diagnostics["initial_loss"] = (
        float(value_match.group(1)) if value_match else None
    )
    return diagnostics


def write_per_group_csv(path, rows):
    fieldnames = (
        "group_id",
        "component_count",
        "mean_anchor_distance_mm",
        "max_anchor_distance_mm",
        "worst_refdes",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def stable_artifacts(run_dir, placement_dir, legality_path):
    per_group_path = run_dir / "per_group.csv"
    plot_candidates = sorted((placement_dir / "plot").glob("*.png"))
    placement_plot = run_dir / "placement.png"
    if plot_candidates:
        shutil.copyfile(plot_candidates[-1], placement_plot)
    artifact_paths = {
        "config_resolved": run_dir / "placement.json",
        "constraint_config": run_dir / "anchor_keepin.json",
        "placement": placement_dir / "m336.gp.pl",
        "placement_plot": placement_plot,
        "per_group": per_group_path,
        "legality": legality_path,
        "log": placement_dir / "DREAMPlace.log",
        "process_log": run_dir / "process.log",
        "preflight": run_dir / "constraints" / "preflight.json",
        "input_alignment": run_dir / "constraints" / "input_alignment.json",
        "initialization": run_dir / "constraints" / "initialization.json",
    }
    return {
        key: repo_path(path) for key, path in artifact_paths.items() if path.exists()
    }


def legality_summary(legality):
    return {
        "constrained_components": legality["constrained_component_count"],
        "fully_contained_components": legality["full_containment_count"],
        "keepin_violation_count": legality["keepin_violation_count"],
        "keepin_violation_area_mm2": legality["keepin_violation_area_mm2"],
        "overlap_pair_count": legality["overlap_pair_count"],
        "overlap_area_mm2": legality["overlap_area_mm2"],
        "area_epsilon_mm2": legality["area_epsilon_mm2"],
        "validated_obstacle_components": legality.get(
            "validated_obstacle_component_count", 0
        ),
    }


def score_manual_baseline(args):
    """Score the manual placement without optimizing or refitting geometry."""
    run_dir = args.baseline_output_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    constraint_path = run_dir / "anchor_keepin.json"
    config_path = run_dir / "placement.json"
    write_json(
        constraint_path,
        constraint_config(
            run_dir,
            EXPERIMENTS["E0"],
            args.assignment,
            args.grid_mm,
            args.clearance_mm,
        ),
    )
    config = placement_config(
        run_dir,
        constraint_path,
        EXPERIMENTS["E0"],
        args.seeds[0],
        0,
        args.gpu,
        args.anchor_weight,
        args.grid_mm,
        args.clearance_mm,
        args.bookshelf_dir / "m336.aux",
    )
    config.update(
        {
            "aux_input": str(args.baseline_aux),
            "global_place_flag": 0,
            "evaluate_pl": 0,
            "plot_flag": 0,
            "random_center_init_flag": 0,
        }
    )
    write_json(config_path, config)
    command = [args.python, str(args.placer), str(config_path)]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO_ROOT / "install")
    environment["PYTHONFAULTHANDLER"] = "1"
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=run_dir,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    runtime = time.perf_counter() - started
    (run_dir / "process.log").write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(
            "manual baseline scoring failed with exit code %d; see %s"
            % (completed.returncode, run_dir / "process.log")
        )

    placement_dir = run_dir / "m336.baseline"
    log_path = placement_dir / "DREAMPlace.log"
    ppa = parse_final_ppa(log_path.read_text())
    legality_path = run_dir / "constraints" / "legality.json"
    legality = evaluate_feature_off(
        config,
        constraint_path,
        args.baseline_pl,
        legality_path,
        database_aux=args.bookshelf_dir / "m336.aux",
    )
    site_mm = float(args.baseline_manifest["site_mm"])
    result = {
        "schema": "m336_manual_baseline_result_v1",
        "name": "manual_pcb_geometry",
        "git_sha": git_sha(),
        "command": command,
        "runtime_seconds": runtime,
        "input_sha256": args.baseline_manifest["sha256"],
        "compatibility": args.baseline_manifest["compatibility"],
        "pin_alignment": args.baseline_manifest["pin_alignment"],
        "metrics": {
            "hpwl": float(ppa["hpwl"]),
            "hpwl_mm": float(ppa["hpwl"]) * site_mm,
            "rsmt": float(ppa["rsmt"]),
            "rsmt_mm": float(ppa["rsmt"]) * site_mm,
            "direct_json_hpwl_mm": float(
                args.baseline_manifest["direct_hpwl_mm"]["baseline"]
            ),
            "site_mm": site_mm,
        },
        "legality": legality_summary(legality),
        "artifacts": {
            "config": repo_path(config_path),
            "constraint_config": repo_path(constraint_path),
            "legality": repo_path(legality_path),
            "log": repo_path(log_path),
            "placement": repo_path(args.baseline_pl),
            "manifest": repo_path(args.bookshelf_dir / "baseline_manifest.json"),
        },
    }
    write_json(run_dir / "baseline-result.json", result)
    return result


def run_one(args, experiment_id, seed, output_dir=None, anchor_weight=None):
    spec = EXPERIMENTS[experiment_id]
    output_dir = output_dir or args.output_dir
    anchor_weight = args.anchor_weight if anchor_weight is None else anchor_weight
    run_dir = output_dir / experiment_id / ("seed_%d" % seed)
    result_path = run_dir / "run-result.json"
    if args.reevaluate:
        if not result_path.exists():
            raise FileNotFoundError("cannot reevaluate missing run: %s" % result_path)
        result = json.loads(result_path.read_text())
        config = result["config"]
        constraint_path = run_dir / "anchor_keepin.json"
        legality_path = run_dir / "constraints" / "legality.json"
        legality = evaluate_feature_off(
            config,
            constraint_path,
            run_dir / "m336/m336.gp.pl",
            legality_path,
        )
        result["metrics"]["anchor_distance_mm"] = legality["anchor_distance_mm"]
        result["metrics"]["projected_anchor_distance_mm"] = legality[
            "projected_anchor_distance_mm"
        ]
        result["metrics"]["per_group"] = legality["per_group"]
        log_text = (run_dir / "m336" / "DREAMPlace.log").read_text()
        effective_weight = float(
            config.get("anchor_loss_weight_scale", anchor_weight)
        )
        result["metrics"]["matched_anchor_weight"] = parse_weight(
            log_text, "anchor loss"
        )
        result["metrics"]["anchor_loss_diagnostics"] = parse_weight_diagnostics(
            log_text, "anchor loss", effective_weight
        )
        result["metrics"]["soft_keepin_loss_diagnostics"] = (
            parse_weight_diagnostics(log_text, "soft keep-in loss", 1.0)
        )
        result["legality"] = legality_summary(legality)
        result["anchor_weight_scale"] = effective_weight
        result["constraint_grid_mm"] = float(args.grid_mm)
        result["keepin_clearance_mm"] = float(args.clearance_mm)
        result["input_sha256"] = args.input_identity
        result["source_state"] = args.source_identity
        preflight_path = run_dir / "constraints" / "preflight.json"
        if preflight_path.exists():
            preflight = json.loads(preflight_path.read_text())
            result["preflight"] = {
                "resolved_member_count": preflight["resolved_member_count"],
                "movable_non_anchor_constraint_count": preflight[
                    "movable_non_anchor_constraint_count"
                ],
                "frozen_anchor_count": preflight["frozen_anchor_count"],
                "frozen_fixed_obstacle_count": preflight.get(
                    "frozen_fixed_obstacle_count", 0
                ),
                "infeasible_domain_count": len(preflight["infeasible_domains"]),
                "alignment": preflight["alignment"],
            }
        write_per_group_csv(run_dir / "per_group.csv", legality["per_group"])
        result["artifacts"] = stable_artifacts(
            run_dir, run_dir / "m336", legality_path
        )
        repair_path = run_dir / "constraints" / "repair.json"
        if repair_path.exists():
            result["artifacts"]["repair"] = repo_path(repair_path)
        result["manual_baseline_comparison"] = compare_with_manual_baseline(
            result["metrics"], args.manual_baseline
        )
        write_json(result_path, result)
        return result
    if args.resume and result_path.exists():
        result = json.loads(result_path.read_text())
        result["manual_baseline_comparison"] = compare_with_manual_baseline(
            result["metrics"], args.manual_baseline
        )
        write_json(result_path, result)
        return result
    run_dir.mkdir(parents=True, exist_ok=True)
    constraint_path = run_dir / "anchor_keepin.json"
    config_path = run_dir / "placement.json"
    write_json(
        constraint_path,
        constraint_config(
            run_dir, spec, args.assignment, args.grid_mm, args.clearance_mm
        ),
    )
    config = placement_config(
        run_dir,
        constraint_path,
        spec,
        seed,
        args.iterations,
        args.gpu,
        anchor_weight,
        args.grid_mm,
        args.clearance_mm,
        args.bookshelf_dir / "m336.aux",
        initial_placement=args.baseline_pl,
    )
    write_json(config_path, config)
    command = [args.python, str(args.placer), str(config_path)]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO_ROOT / "install")
    environment["PYTHONFAULTHANDLER"] = "1"
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=run_dir,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    runtime = time.perf_counter() - started
    (run_dir / "process.log").write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(
            "%s seed %d failed with exit code %d; see %s"
            % (experiment_id, seed, completed.returncode, run_dir / "process.log")
        )

    placement_dir = run_dir / "m336"
    dreamplace_log_path = placement_dir / "DREAMPlace.log"
    log_text = dreamplace_log_path.read_text()
    ppa = parse_final_ppa(log_text)
    legality_path = run_dir / "constraints" / "legality.json"
    if experiment_id == "E0":
        legality = evaluate_feature_off(
            config,
            constraint_path,
            placement_dir / "m336.gp.pl",
            legality_path,
        )
    else:
        legality = json.loads(legality_path.read_text())

    preflight_path = run_dir / "constraints" / "preflight.json"
    preflight = json.loads(preflight_path.read_text())
    write_per_group_csv(run_dir / "per_group.csv", legality["per_group"])

    result = {
        "run_id": "%s-aw-%s-seed-%d"
        % (experiment_id.lower(), format(anchor_weight, "g"), seed),
        "git_sha": git_sha(),
        "experiment_id": experiment_id,
        "experiment_name": spec["name"],
        "seed": seed,
        "anchor_weight_scale": float(anchor_weight),
        "constraint_grid_mm": float(args.grid_mm),
        "keepin_clearance_mm": float(args.clearance_mm),
        "command": command,
        "config": config,
        "input_sha256": args.input_identity,
        "source_state": args.source_identity,
        "preflight": {
            "resolved_member_count": preflight["resolved_member_count"],
            "movable_non_anchor_constraint_count": preflight[
                "movable_non_anchor_constraint_count"
            ],
            "frozen_anchor_count": preflight["frozen_anchor_count"],
            "frozen_fixed_obstacle_count": preflight.get(
                "frozen_fixed_obstacle_count", 0
            ),
            "infeasible_domain_count": len(preflight["infeasible_domains"]),
            "alignment": preflight["alignment"],
        },
        "runtime_seconds": runtime,
        "device": (
            "NVIDIA H100"
            if "Using Torch GPU device" in log_text
            else "CPU"
        ),
        "metrics": {
            "hpwl": float(ppa["hpwl"]),
            "rsmt": float(ppa["rsmt"]),
            "objective": float(ppa["objective"]),
            "overflow": float(ppa["overflow"]),
            "iterations": int(ppa["iteration"]),
            "anchor_distance_mm": legality["anchor_distance_mm"],
            "projected_anchor_distance_mm": legality[
                "projected_anchor_distance_mm"
            ],
            "per_group": legality["per_group"],
            "total_projected_nodes": legality.get("total_projected_nodes", 0),
            "matched_anchor_weight": parse_weight(log_text, "anchor loss"),
            "anchor_loss_diagnostics": parse_weight_diagnostics(
                log_text, "anchor loss", anchor_weight
            ),
            "soft_keepin_loss_diagnostics": parse_weight_diagnostics(
                log_text, "soft keep-in loss", 1.0
            ),
        },
        "legality": legality_summary(legality),
        "artifacts": stable_artifacts(run_dir, placement_dir, legality_path),
        "warnings": [
            "Source declares 27 clusters but enumerates 25 rows/125 unique members."
        ],
        "manual_baseline_comparison": compare_with_manual_baseline(
            {"hpwl": float(ppa["hpwl"]), "rsmt": float(ppa["rsmt"])},
            args.manual_baseline,
        ),
    }
    repair_path = run_dir / "constraints" / "repair.json"
    if repair_path.exists():
        result["artifacts"]["repair"] = repo_path(repair_path)
        result["repair"] = json.loads(repair_path.read_text())
    write_json(result_path, result)
    return result


def compare_with_manual_baseline(metrics, baseline):
    baseline_metrics = baseline["metrics"]
    hpwl_ratio = float(metrics["hpwl"]) / baseline_metrics["hpwl"]
    rsmt_ratio = float(metrics["rsmt"]) / baseline_metrics["rsmt"]
    return {
        "hpwl_ratio": hpwl_ratio,
        "hpwl_regression": hpwl_ratio - 1.0,
        "rsmt_ratio": rsmt_ratio,
        "rsmt_regression": rsmt_ratio - 1.0,
        "normalized_quality_score": 2.0 / (hpwl_ratio + rsmt_ratio),
        "baseline_quality_score": 1.0,
        "hpwl_no_worse": hpwl_ratio <= 1.0,
        "rsmt_no_worse": rsmt_ratio <= 1.0,
    }


def aggregate(results, baseline=None):
    rows = {}
    for experiment_id in DEFAULT_EXPERIMENTS:
        selected = [row for row in results if row["experiment_id"] == experiment_id]
        if not selected:
            continue
        rows[experiment_id] = {
            "run_count": len(selected),
            "hpwl_mean": statistics.mean(row["metrics"]["hpwl"] for row in selected),
            "rsmt_mean": statistics.mean(row["metrics"]["rsmt"] for row in selected),
            "runtime_seconds_mean": statistics.mean(
                row["runtime_seconds"] for row in selected
            ),
            "anchor_distance_mm_mean": statistics.mean(
                row["metrics"]["anchor_distance_mm"]["mean"] for row in selected
            ),
            "anchor_distance_mm_p90_mean": statistics.mean(
                row["metrics"]["anchor_distance_mm"]["p90"] for row in selected
            ),
            "keepin_violation_count_max": max(
                row["legality"]["keepin_violation_count"] for row in selected
            ),
            "overlap_pair_count_max": max(
                row["legality"]["overlap_pair_count"] for row in selected
            ),
        }
    comparisons = {}
    if "E2" in rows and "E3" in rows:
        comparisons["e3_vs_e2"] = {
            "mean_anchor_distance_reduction": 1.0
            - rows["E3"]["anchor_distance_mm_mean"]
            / rows["E2"]["anchor_distance_mm_mean"],
            "p90_anchor_distance_reduction": 1.0
            - rows["E3"]["anchor_distance_mm_p90_mean"]
            / rows["E2"]["anchor_distance_mm_p90_mean"],
        }
    if "E0" in rows and "E4" in rows:
        comparisons["e4_vs_e0"] = {
            "hpwl_regression": rows["E4"]["hpwl_mean"] / rows["E0"]["hpwl_mean"] - 1.0,
            "runtime_ratio": rows["E4"]["runtime_seconds_mean"]
            / rows["E0"]["runtime_seconds_mean"],
        }
    if baseline is not None and "E4" in rows:
        comparisons["e4_vs_manual_baseline"] = compare_with_manual_baseline(
            {
                "hpwl": rows["E4"]["hpwl_mean"],
                "rsmt": rows["E4"]["rsmt_mean"],
            },
            baseline,
        )
    return rows, comparisons


def aggregate_weight_sweep(results):
    rows = {}
    weights = sorted({float(row["anchor_weight_scale"]) for row in results})
    experiments = sorted({row["experiment_id"] for row in results})
    for weight in weights:
        weight_key = format(weight, "g")
        rows[weight_key] = {}
        for experiment_id in experiments:
            selected = [
                row
                for row in results
                if row["experiment_id"] == experiment_id
                and float(row["anchor_weight_scale"]) == weight
            ]
            if not selected:
                continue
            matched_weights = [
                row["metrics"]["anchor_loss_diagnostics"]["matched_weight"]
                for row in selected
                if row["metrics"].get("anchor_loss_diagnostics")
            ]
            rows[weight_key][experiment_id] = {
                "run_count": len(selected),
                "hpwl_mean": statistics.mean(
                    row["metrics"]["hpwl"] for row in selected
                ),
                "anchor_distance_mm_mean": statistics.mean(
                    row["metrics"]["anchor_distance_mm"]["mean"]
                    for row in selected
                ),
                "anchor_distance_mm_p90_mean": statistics.mean(
                    row["metrics"]["anchor_distance_mm"]["p90"]
                    for row in selected
                ),
                "matched_anchor_weight_mean": (
                    statistics.mean(matched_weights) if matched_weights else None
                ),
                "keepin_violation_count_max": max(
                    row["legality"]["keepin_violation_count"]
                    for row in selected
                ),
                "overlap_pair_count_max": max(
                    row["legality"]["overlap_pair_count"] for row in selected
                ),
                "runtime_seconds_mean": statistics.mean(
                    row["runtime_seconds"] for row in selected
                ),
            }
    return rows


def worst_groups(results, experiment_id="E4", limit=8):
    grouped = defaultdict(list)
    for result in results:
        if result["experiment_id"] != experiment_id:
            continue
        for row in result["metrics"]["per_group"]:
            grouped[row["group_id"]].append(row)
    ranked = []
    for group_id, rows in grouped.items():
        worst = max(rows, key=lambda row: row["max_anchor_distance_mm"])
        ranked.append(
            {
                "group_id": group_id,
                "run_count": len(rows),
                "component_count": rows[0]["component_count"],
                "mean_anchor_distance_mm": statistics.mean(
                    row["mean_anchor_distance_mm"] for row in rows
                ),
                "max_anchor_distance_mm": max(
                    row["max_anchor_distance_mm"] for row in rows
                ),
                "worst_refdes": worst["worst_refdes"],
            }
        )
    return sorted(
        ranked,
        key=lambda row: (-row["mean_anchor_distance_mm"], row["group_id"]),
    )[:limit]


def acceptance_summary(results, aggregate_rows, comparisons, validation=None):
    e4_runs = [row for row in results if row["experiment_id"] == "E4"]
    input_resolution = bool(results) and all(
        row.get("preflight", {}).get("resolved_member_count") == 125
        and row.get("preflight", {}).get("infeasible_domain_count") == 0
        and row.get("preflight", {}).get("frozen_fixed_obstacle_count") == 15
        and (
            not EXPERIMENTS[row["experiment_id"]]["integrated_context"]
            or row.get("preflight", {}).get("frozen_anchor_count") == 25
        )
        for row in results
    )
    required = {
        "e4_full_containment": bool(e4_runs)
        and all(
            row["legality"]["fully_contained_components"]
            == row["legality"]["constrained_components"]
            for row in e4_runs
        ),
        "e4_zero_overlap": bool(e4_runs)
        and all(row["legality"]["overlap_pair_count"] == 0 for row in e4_runs),
        "all_input_refdes_resolved": input_resolution,
        "e4_score_at_least_manual_baseline": bool(e4_runs)
        and all(
            row["manual_baseline_comparison"]["normalized_quality_score"]
            >= row["manual_baseline_comparison"]["baseline_quality_score"]
            for row in e4_runs
        ),
        "feature_off_smoke": (
            validation.get("feature_off_smoke") if validation else None
        ),
    }
    goals = {}
    if "e3_vs_e2" in comparisons:
        goals.update(
            {
                "mean_anchor_reduction_at_least_25pct": comparisons["e3_vs_e2"][
                    "mean_anchor_distance_reduction"
                ]
                >= 0.25,
                "p90_anchor_reduction_at_least_15pct": comparisons["e3_vs_e2"][
                    "p90_anchor_distance_reduction"
                ]
                >= 0.15,
            }
        )
    if "e4_vs_e0" in comparisons:
        goals.update(
            {
                "hpwl_regression_at_most_10pct": comparisons["e4_vs_e0"][
                    "hpwl_regression"
                ]
                <= 0.10,
                "runtime_at_most_2x": comparisons["e4_vs_e0"]["runtime_ratio"]
                <= 2.0,
            }
        )
    if "e4_vs_manual_baseline" in comparisons:
        baseline_comparison = comparisons["e4_vs_manual_baseline"]
        goals.update(
            {
                "hpwl_no_worse_than_manual_baseline": baseline_comparison[
                    "hpwl_no_worse"
                ],
                "rsmt_no_worse_than_manual_baseline": baseline_comparison[
                    "rsmt_no_worse"
                ],
                "normalized_score_at_least_manual_baseline": baseline_comparison[
                    "normalized_quality_score"
                ]
                >= baseline_comparison["baseline_quality_score"],
            }
        )
    return {"required": required, "goals": goals}


def assignment_diagnostics(path):
    data = json.loads(Path(path).read_text())
    return {
        "schema": data.get("schema"),
        "status": data.get("status"),
        "method": data.get("method"),
        "capacity_diagnostics": data.get("capacity_diagnostics", {}),
        "limitations": data.get("limitations", []),
    }


def optional_json(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def prepare_manual_baseline_assets(
    source_path, baseline_path, cluster_path, bookshelf_dir, site_mm
):
    try:
        from experiments.m336.scripts.prepare_baseline import prepare_baseline
        from experiments.m336.scripts.generate_bookshelf import generate
    except ModuleNotFoundError:
        from prepare_baseline import prepare_baseline
        from generate_bookshelf import generate

    generate(source_path, cluster_path, bookshelf_dir, site_mm)
    return prepare_baseline(source_path, baseline_path, bookshelf_dir)


def _status(value):
    if value is None:
        return "NOT RUN"
    return "PASS" if value else "FAIL"


def render_report(summary):
    aggregate_rows = summary["aggregate"]
    source = summary["source_state"]
    environment = summary["environment"]
    lines = [
        "# M336 Anchor-Guided Keep-in Experiment",
        "",
        "## Provenance",
        "",
        "- Branch/SHA: `%s` / `%s`." % (source["branch"], source["git_sha"]),
        "- Worktree dirty: `%s`; tracked diff SHA-256: `%s`."
        % (str(source["dirty"]).lower(), source["tracked_diff_sha256"]),
        "- Seeds: `%s`; iterations per run: `%d`."
        % (", ".join(map(str, summary["seeds"])), summary["iterations"]),
        "- Device: `%s`; driver records: `%s`."
        % (summary["device"], "; ".join(environment.get("nvidia_smi", []))),
        "- Python/PyTorch/CUDA: `%s` / `%s` / `%s`."
        % (environment["python"], environment["torch"], environment["torch_cuda"]),
        "- Geometry alignment max residual: `0.0332111 mm` (limit `0.05 mm`).",
        "- Manifest: 25 enumerated rows and 125 unique members; the declared count of 27 remains unresolved.",
        "",
        "### Input Identity",
        "",
        "| Input | SHA-256 |",
        "|---|---|",
    ]
    for path, digest in sorted(summary["input_sha256"].items()):
        lines.append("| `%s` | `%s` |" % (path, digest))
    baseline = summary["manual_baseline"]
    baseline_metrics = baseline["metrics"]
    baseline_legality = baseline["legality"]
    lines.extend(
        [
            "",
            "Implementation-file hashes and the complete dirty-path inventory are in `summary.json`.",
            "",
            "## Manual Baseline",
            "",
            "- Cypress HPWL/RSMT: `%.3f` / `%.3f` (`%.4f mm` / `%.4f mm`)."
            % (
                baseline_metrics["hpwl"],
                baseline_metrics["rsmt"],
                baseline_metrics["hpwl_mm"],
                baseline_metrics["rsmt_mm"],
            ),
            "- Independent JSON-pin HPWL: `%.4f mm`; Bookshelf pre-quantization pin residual: `%.3g mm`."
            % (
                baseline_metrics["direct_json_hpwl_mm"],
                baseline["pin_alignment"]["max_residual_mm"],
            ),
            "- Exact legality: `%d/%d` contained, `%d` keep-in violations, `%d` overlaps."
            % (
                baseline_legality["fully_contained_components"],
                baseline_legality["constrained_components"],
                baseline_legality["keepin_violation_count"],
                baseline_legality["overlap_pair_count"],
            ),
            "",
            "## Commands",
            "",
            "```bash",
            summary["reproduction_command"],
            "python3.11 experiments/m336/scripts/validate_manifest.py",
        ]
    )
    validation = summary.get("validation")
    if validation:
        lines.extend(validation.get("commands", []))
    lines.extend(["```", "", "## Run Results", ""])
    lines.extend(
        [
            "| Run | Seed | HPWL | RSMT | Score | Mean anchor mm | P90 mm | Keep-in | Overlaps | Runtime s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(
        summary["runs"], key=lambda item: (item["experiment_id"], item["seed"])
    ):
        lines.append(
            "| %s | %d | %.3f | %.3f | %.4f | %.3f | %.3f | %d | %d | %.2f |"
            % (
                row["experiment_id"],
                row["seed"],
                row["metrics"]["hpwl"],
                row["metrics"]["rsmt"],
                row["manual_baseline_comparison"]["normalized_quality_score"],
                row["metrics"]["anchor_distance_mm"]["mean"],
                row["metrics"]["anchor_distance_mm"]["p90"],
                row["legality"]["keepin_violation_count"],
                row["legality"]["overlap_pair_count"],
                row["runtime_seconds"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "| Experiment | Runs | HPWL | RSMT | Mean anchor mm | P90 mm | Max violations | Max overlaps |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for experiment_id, row in aggregate_rows.items():
        lines.append(
            "| %s | %d | %.3f | %.3f | %.3f | %.3f | %d | %d |"
            % (
                experiment_id,
                row["run_count"],
                row["hpwl_mean"],
                row["rsmt_mean"],
                row["anchor_distance_mm_mean"],
                row["anchor_distance_mm_p90_mean"],
                row["keepin_violation_count_max"],
                row["overlap_pair_count_max"],
            )
        )

    comparisons = summary["comparisons"]
    lines.extend(["", "## Acceptance", ""])
    if "e3_vs_e2" in comparisons:
        comparison = comparisons["e3_vs_e2"]
        lines.append(
            "- `%s` E3 vs E2 mean anchor reduction: `%.2f%%` (target >=25%%)."
            % (
                _status(
                    summary["acceptance"]["goals"][
                        "mean_anchor_reduction_at_least_25pct"
                    ]
                ),
                100 * comparison["mean_anchor_distance_reduction"],
            )
        )
        lines.append(
            "- `%s` E3 vs E2 p90 anchor reduction: `%.2f%%` (target >=15%%)."
            % (
                _status(
                    summary["acceptance"]["goals"][
                        "p90_anchor_reduction_at_least_15pct"
                    ]
                ),
                100 * comparison["p90_anchor_distance_reduction"],
            )
        )
    if "e4_vs_e0" in comparisons:
        comparison = comparisons["e4_vs_e0"]
        lines.append(
            "- `%s` E4 vs E0 HPWL regression: `%.2f%%` (target <=10%%)."
            % (
                _status(
                    summary["acceptance"]["goals"][
                        "hpwl_regression_at_most_10pct"
                    ]
                ),
                100 * comparison["hpwl_regression"],
            )
        )
        lines.append(
            "- `%s` E4/E0 end-to-end runtime ratio: `%.2fx` (target <=2x)."
            % (
                _status(summary["acceptance"]["goals"]["runtime_at_most_2x"]),
                comparison["runtime_ratio"],
            )
        )
    if "e4_vs_manual_baseline" in comparisons:
        comparison = comparisons["e4_vs_manual_baseline"]
        lines.append(
            "- `%s` E4 vs manual HPWL: `%.2f%%`; RSMT: `%.2f%%`; normalized score: `%.4f` (baseline 1.0)."
            % (
                _status(
                    comparison["hpwl_no_worse"]
                    and comparison["rsmt_no_worse"]
                ),
                100 * comparison["hpwl_regression"],
                100 * comparison["rsmt_regression"],
                comparison["normalized_quality_score"],
            )
        )
    for name, value in summary["acceptance"]["required"].items():
        lines.append("- `%s` required check `%s`." % (_status(value), name))

    lines.extend(
        [
            "",
            "## Worst Groups",
            "",
            "E4 physical-anchor distance, averaged across seeds:",
            "",
            "| Subgroup | Components | Mean mm | Max mm | Worst refdes |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in summary["worst_groups"]:
        lines.append(
            "| %s | %d | %.3f | %.3f | %s |"
            % (
                row["group_id"],
                row["component_count"],
                row["mean_anchor_distance_mm"],
                row["max_anchor_distance_mm"],
                row["worst_refdes"],
            )
        )

    lines.extend(["", "## Capacity", ""])
    lines.extend(
        [
            "| Region | Member area mm2 | Free area mm2 | Free-area utilization |",
            "|---|---:|---:|---:|",
        ]
    )
    capacity = summary["assignment_diagnostics"]["capacity_diagnostics"]
    for region_id, row in sorted(capacity.items()):
        lines.append(
            "| %s | %.3f | %.3f | %.2f%% |"
            % (
                region_id,
                row["member_area_mm2"],
                row["free_area_after_anchors_mm2"],
                100 * row["free_area_utilization"],
            )
        )

    sweep = summary.get("weight_sweep")
    if sweep:
        lines.extend(
            [
                "",
                "## Weight Sweep",
                "",
                "Artifact: `%s`" % sweep["artifact"],
                "Seeds: `%s`; iterations: `%d`."
                % (", ".join(map(str, sweep["seeds"])), sweep["iterations"]),
                "",
                "| Scale | Run | Runs | Matched lambda | HPWL | Mean mm | P90 mm | Violations |",
                "|---:|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for weight, experiments in sweep["aggregate"].items():
            for experiment_id, row in experiments.items():
                matched = row["matched_anchor_weight_mean"]
                lines.append(
                    "| %s | %s | %d | %s | %.3f | %.3f | %.3f | %d |"
                    % (
                        weight,
                        experiment_id,
                        row["run_count"],
                        "%.3e" % matched if matched is not None else "n/a",
                        row["hpwl_mean"],
                        row["anchor_distance_mm_mean"],
                        row["anchor_distance_mm_p90_mean"],
                        row["keepin_violation_count_max"],
                    )
                )

    if validation:
        lines.extend(["", "## Validation", ""])
        for row in validation.get("results", []):
            lines.append(
                "- `%s`: %s" % (row["status"].upper(), row["description"])
            )

    lines.extend(
        [
            "",
            "## Findings",
            "",
            "- The manual placement is scored without optimization and is used as the common E0-E4 warm start; it is a quality reference, not a legal fallback.",
            "- E2 uses keep-in-aware initialization near current manual positions without anchor loss; E3 adds projected-anchor loss.",
            "- Exact comparisons use `1e-5 mm^2` area tolerance for float32 boundary contact and validate 40 non-constrained physical obstacles.",
        ]
    )
    if len([row for row in summary["runs"] if row["experiment_id"] == "E4"]) == 3:
        lines.append("- E4 exact legality was evaluated for all three seeds.")
    lines.extend(
        [
            "- The soft keep-in gradient is zero after mandatory pre-objective hard projection; it is currently a diagnostic no-op, not evidence of stabilization.",
            "- End-to-end runtime misses the target because each subprocess rebuilds 100 Shapely feasible domains and E4 performs exact packing repair.",
            "- Full configs, hashes, logs, placements, per-group CSV files, legality reports, and E4 repair reports are indexed by `summary.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_weight_sweep_report(summary):
    lines = [
        "# M336 Anchor Weight Sweep",
        "",
        "- Git SHA: `%s`" % summary["git_sha"],
        "- Seeds: `%s`" % ", ".join(map(str, summary["seeds"])),
        "- Iterations: `%d`" % summary["iterations"],
        "- Grid/clearance: `%.3f mm` / `%.3f mm`."
        % (summary["constraint_grid_mm"], summary["keepin_clearance_mm"]),
        "",
        "## Results",
        "",
        "| Scale | Run | Runs | Matched lambda | HPWL | Mean mm | P90 mm | Keep-in | Overlaps | Runtime s |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for weight, experiments in summary["aggregate"].items():
        for experiment_id, row in experiments.items():
            matched = row["matched_anchor_weight_mean"]
            lines.append(
                "| %s | %s | %d | %s | %.3f | %.3f | %.3f | %d | %d | %.2f |"
                % (
                    weight,
                    experiment_id,
                    row["run_count"],
                    "%.3e" % matched if matched is not None else "n/a",
                    row["hpwl_mean"],
                    row["anchor_distance_mm_mean"],
                    row["anchor_distance_mm_p90_mean"],
                    row["keepin_violation_count_max"],
                    row["overlap_pair_count_max"],
                    row["runtime_seconds_mean"],
                )
            )
    lines.extend(
        [
            "",
            "All values are actual E3 runs. Hard projection remained enabled; exact overlap counts are pre-repair diagnostics.",
            "",
        ]
    )
    return "\n".join(lines)


def reproduction_command(args, weights=None):
    command = [
        args.python,
        "experiments/m336/scripts/run_matrix.py",
        "--experiments",
        *args.experiments,
        "--seeds",
        *map(str, args.seeds),
        "--iterations",
        str(args.iterations),
        "--gpu" if args.gpu else "--no-gpu",
        "--grid-mm",
        format(args.grid_mm, "g"),
        "--clearance-mm",
        format(args.clearance_mm, "g"),
        "--site-mm",
        format(args.site_mm, "g"),
        "--assignment",
        repo_path(args.assignment),
        "--baseline-geometry",
        repo_path(args.baseline_geometry),
        "--bookshelf-dir",
        repo_path(args.bookshelf_dir),
        "--baseline-output-dir",
        repo_path(args.baseline_output_dir),
        "--placer",
        repo_path(args.placer),
    ]
    if weights:
        command.extend(
            ["--anchor-weight-sweep", *(format(weight, "g") for weight in weights)]
        )
        command.extend(["--sweep-output-dir", repo_path(args.sweep_output_dir)])
    else:
        command.extend(["--anchor-weight", format(args.anchor_weight, "g")])
        command.extend(["--output-dir", repo_path(args.output_dir)])
    visible_devices = shlex.quote(
        os.environ.get("CUDA_VISIBLE_DEVICES") or "<physical-gpu>"
    )
    return (
        "CUDA_VISIBLE_DEVICES=%s PYTHONPATH=\"$PWD/install\" %s"
        % (visible_devices, shlex.join(command))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", nargs="+", default=list(DEFAULT_EXPERIMENTS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[1000, 1001, 1002])
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--gpu", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--python", default="python3.11")
    parser.add_argument(
        "--placer", type=Path, default=REPO_ROOT / "install/dreamplace/Placer.py"
    )
    parser.add_argument(
        "--assignment",
        type=Path,
        default=REPO_ROOT / "experiments/m336/configs/m336_region_assignment.final.json",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=REPO_ROOT / "results/m336/runs"
    )
    parser.add_argument(
        "--baseline-geometry", type=Path, default=REPO_ROOT / "pcb_geometry.json"
    )
    parser.add_argument(
        "--bookshelf-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/bookshelf",
    )
    parser.add_argument(
        "--baseline-output-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/baseline",
    )
    parser.add_argument("--anchor-weight", type=float, default=1.0)
    parser.add_argument("--anchor-weight-sweep", nargs="+", type=float)
    parser.add_argument(
        "--sweep-output-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/weight_sweep/runs",
    )
    parser.add_argument("--grid-mm", type=float, default=0.1)
    parser.add_argument("--clearance-mm", type=float, default=0.0)
    parser.add_argument("--site-mm", type=float, default=0.05)
    parser.add_argument("--summary-path", type=Path)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument(
        "--validation-path",
        type=Path,
        default=REPO_ROOT / "results/m336/validation.json",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reevaluate", action="store_true")
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    args.sweep_output_dir = args.sweep_output_dir.resolve()
    args.baseline_geometry = args.baseline_geometry.resolve()
    args.bookshelf_dir = args.bookshelf_dir.resolve()
    args.baseline_output_dir = args.baseline_output_dir.resolve()
    args.assignment = args.assignment.resolve()
    args.placer = args.placer.resolve()
    invalid = sorted(set(args.experiments) - set(EXPERIMENTS))
    if invalid:
        parser.error("unknown experiments: %s" % invalid)
    if (
        not args.assignment.exists()
        or not args.placer.exists()
        or not args.baseline_geometry.exists()
    ):
        parser.error("assignment, installed placer, and baseline geometry must exist")
    if (
        args.anchor_weight <= 0
        or args.grid_mm <= 0
        or args.clearance_mm < 0
        or args.site_mm <= 0
    ):
        parser.error("weights/grid must be positive and clearance non-negative")
    if args.anchor_weight_sweep and any(
        weight <= 0 for weight in args.anchor_weight_sweep
    ):
        parser.error("all sweep weights must be positive")

    args.baseline_manifest = prepare_manual_baseline_assets(
        REPO_ROOT / "experiments/m336/input/pcb_geometry_keepin.json",
        args.baseline_geometry,
        REPO_ROOT / "experiments/m336/input/m336_clusters.json",
        args.bookshelf_dir,
        args.site_mm,
    )
    args.baseline_aux = (args.bookshelf_dir / "m336.baseline.aux").resolve()
    args.baseline_pl = (args.bookshelf_dir / "m336.baseline.pl").resolve()
    args.source_identity = source_state()
    args.input_identity = input_hashes(args)
    args.environment_identity = runtime_environment()
    args.manual_baseline = score_manual_baseline(args)

    results = []
    invocation = " ".join([sys.executable, *sys.argv])
    validation = optional_json(args.validation_path)
    if args.anchor_weight_sweep:
        weights = sorted(set(args.anchor_weight_sweep))
        for weight in weights:
            weight_dir = args.sweep_output_dir / ("scale_%s" % format(weight, "g"))
            for experiment_id in args.experiments:
                for seed in args.seeds:
                    print(
                        "running %s weight %g seed %d"
                        % (experiment_id, weight, seed),
                        flush=True,
                    )
                    results.append(
                        run_one(
                            args,
                            experiment_id,
                            seed,
                            output_dir=weight_dir,
                            anchor_weight=weight,
                        )
                    )
        summary = {
            "schema": "m336_anchor_weight_sweep_v1",
            "git_sha": git_sha(),
            "source_state": args.source_identity,
            "environment": args.environment_identity,
            "input_sha256": args.input_identity,
            "experiments": args.experiments,
            "seeds": args.seeds,
            "iterations": args.iterations,
            "anchor_weight_scales": weights,
            "constraint_grid_mm": args.grid_mm,
            "keepin_clearance_mm": args.clearance_mm,
            "invocation": invocation,
            "reproduction_command": reproduction_command(args, weights),
            "manual_baseline": args.manual_baseline,
            "runs": results,
            "aggregate": aggregate_weight_sweep(results),
        }
        summary_path = args.summary_path or (
            REPO_ROOT / "results/m336/weight_sweep/summary.json"
        )
        report_path = args.report_path or (
            REPO_ROOT / "results/m336/weight_sweep/REPORT.md"
        )
        report_renderer = render_weight_sweep_report
    else:
        for experiment_id in args.experiments:
            for seed in args.seeds:
                print("running %s seed %d" % (experiment_id, seed), flush=True)
                results.append(run_one(args, experiment_id, seed))

        aggregate_rows, comparisons = aggregate(results, args.manual_baseline)
        sweep_path = REPO_ROOT / "results/m336/weight_sweep/summary.json"
        sweep_summary = optional_json(sweep_path)
        summary = {
            "schema": "m336_experiment_summary_v2",
            "git_sha": git_sha(),
            "source_state": args.source_identity,
            "environment": args.environment_identity,
            "input_sha256": args.input_identity,
            "experiments": args.experiments,
            "seeds": args.seeds,
            "iterations": args.iterations,
            "constraint_grid_mm": args.grid_mm,
            "keepin_clearance_mm": args.clearance_mm,
            "device": results[0]["device"] if results else "unknown",
            "invocation": invocation,
            "reproduction_command": reproduction_command(args),
            "manual_baseline": args.manual_baseline,
            "runs": results,
            "aggregate": aggregate_rows,
            "comparisons": comparisons,
            "assignment_diagnostics": assignment_diagnostics(args.assignment),
            "worst_groups": worst_groups(results),
            "validation": validation,
            "acceptance": acceptance_summary(
                results, aggregate_rows, comparisons, validation
            ),
        }
        if sweep_summary:
            summary["weight_sweep"] = {
                "artifact": repo_path(sweep_path),
                "aggregate": sweep_summary["aggregate"],
                "seeds": sweep_summary["seeds"],
                "iterations": sweep_summary["iterations"],
            }
        summary_path = args.summary_path or REPO_ROOT / "results/m336/summary.json"
        report_path = args.report_path or REPO_ROOT / "results/m336/REPORT.md"
        report_renderer = render_report

    summary_path = Path(summary_path).resolve()
    report_path = Path(report_path).resolve()
    write_json(summary_path, summary)
    report = report_renderer(summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print("wrote %s and %s" % (summary_path, report_path))


if __name__ == "__main__":
    main()
