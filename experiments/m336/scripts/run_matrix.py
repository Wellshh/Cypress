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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from dreamplace.constraints.exact_contact_projection import (
    AUTHORITY_SEARCH_STRATEGIES,
    CONTACT_POLICIES,
    CONTACT_PROJECTION_MODES,
    CONSENSUS_PER_STEP_CONTACT_POLICY,
    CONSENSUS_PLUS_STAGE_MICRO_CONTACT_POLICY,
    EXHAUSTIVE_AUTHORITY_SEARCH,
    PAIRWISE_FACTORIZED_AUTHORITY_SEARCH,
    PROPOSAL_AUTHORITY_MODES,
    STRICT_REFERENCE_CONTACT_POLICY,
    contact_policy_settings,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_M336_ASSIGNMENT = (
    REPO_ROOT / "experiments/m336/checkpoints/M336-118/assignment.json"
)
DEFAULT_M336_CHECKPOINT_PL = (
    REPO_ROOT / "experiments/m336/checkpoints/M336-118/placement.float64.pl"
)
DEFAULT_M336_CONSTRAINT_GRID_MM = 0.05
DEFAULT_M336_TARGET_DENSITY = 0.85
DEFAULT_M336_LEARNING_RATE = 0.01
DEFAULT_M336_TOPOLOGY_MIN_NET_DEGREE = 32
M336_ANCHOR_WEIGHT_UPDATE_INTERVAL = 1
M336_ANCHOR_WEIGHT_EMA_DECAY = 0.8
M336_ANCHOR_WEIGHT_MIN = 0.0
M336_ANCHOR_WEIGHT_MAX = 5000.0
M336_ANCHOR_WEIGHT_WARMUP_ITERATIONS = 2
M336_ANCHOR_WEIGHT_RAMP_ITERATIONS = 10
MIN_M336_LEARNING_RATE_SCALE = 1.0
MAX_M336_LEARNING_RATE_SCALE = 32.0
DEFAULT_CUBLAS_WORKSPACE_CONFIG = ":4096:8"
DEFAULT_EXPERIMENTS = ("E0", "E1", "E2", "E3", "E4")
IMPLEMENTATION_FILES = (
    "dreamplace/BasicPlace.py",
    "dreamplace/NesterovAcceleratedGradientOptimizer.py",
    "dreamplace/NonLinearPlace.py",
    "dreamplace/PlaceObj.py",
    "dreamplace/Placer.py",
    "dreamplace/params.json",
    "dreamplace/constraints/anchor_keepin.py",
    "dreamplace/constraints/exact_contact_projection.py",
    "dreamplace/constraints/exact_step_guard.py",
    "dreamplace/constraints/irregular_density.py",
    "dreamplace/constraints/pcb_geometry.py",
    "dreamplace/constraints/region_assignment.py",
    "dreamplace/constraints/region_projection.py",
    "dreamplace/constraints/region_validation.py",
    "dreamplace/ops/anchor_keepin/anchor_keepin.py",
    "dreamplace/ops/electric_potential/electric_overflow.py",
    "dreamplace/ops/electric_potential/electric_potential.py",
    "experiments/m336/scripts/analyze_quality_bound.py",
    "experiments/m336/scripts/analyze_shared_box_bound.py",
    "experiments/m336/scripts/finalize_assignment.py",
    "experiments/m336/scripts/generate_bookshelf.py",
    "experiments/m336/scripts/optimize_assignment.py",
    "experiments/m336/scripts/prepare_baseline.py",
    "experiments/m336/scripts/probe_exact_site_cpsat.py",
    "experiments/m336/scripts/run_matrix.py",
    "experiments/m336/scripts/score_exact_site_result.py",
    "experiments/m336/scripts/solve_discrete_placement.py",
    "install/dreamplace/BasicPlace.py",
    "install/dreamplace/NesterovAcceleratedGradientOptimizer.py",
    "install/dreamplace/NonLinearPlace.py",
    "install/dreamplace/PlaceObj.py",
    "install/dreamplace/Placer.py",
    "install/dreamplace/params.json",
    "install/dreamplace/constraints/anchor_keepin.py",
    "install/dreamplace/constraints/exact_contact_projection.py",
    "install/dreamplace/constraints/exact_step_guard.py",
    "install/dreamplace/constraints/irregular_density.py",
    "install/dreamplace/constraints/pcb_geometry.py",
    "install/dreamplace/constraints/region_assignment.py",
    "install/dreamplace/constraints/region_projection.py",
    "install/dreamplace/constraints/region_validation.py",
    "install/dreamplace/ops/anchor_keepin/anchor_keepin.py",
    "install/dreamplace/ops/electric_potential/electric_overflow.py",
    "install/dreamplace/ops/electric_potential/electric_potential.py",
)
EXPERIMENTS = {
    "E0": {
        "name": "cypress_baseline",
        "anchor_loss": False,
        "projection": False,
        "soft_loss": False,
        "irregular_density": False,
        "repair": False,
        "freeze_anchors": False,
        "integrated_context": False,
    },
    "E1": {
        "name": "anchor_only",
        "anchor_loss": True,
        "projection": False,
        "soft_loss": False,
        "irregular_density": False,
        "repair": False,
        "freeze_anchors": True,
        "integrated_context": True,
    },
    "E2": {
        "name": "keepin_only",
        "anchor_loss": False,
        "projection": True,
        "soft_loss": True,
        "irregular_density": True,
        "repair": False,
        "freeze_anchors": True,
        "integrated_context": True,
    },
    "E3": {
        "name": "anchor_plus_keepin",
        "anchor_loss": True,
        "projection": True,
        "soft_loss": True,
        "irregular_density": True,
        "repair": False,
        "freeze_anchors": True,
        "integrated_context": True,
    },
    "E4": {
        "name": "anchor_keepin_plus_repair",
        "anchor_loss": True,
        "projection": True,
        "soft_loss": True,
        "irregular_density": True,
        "repair": True,
        "freeze_anchors": True,
        "integrated_context": True,
    },
}

N7_SCHEMA = "m336_n7_paired_timing_v1"
N7_CONTRACT_SCHEMA = "m336_n7_paired_timing_contract_v1"
N7_FEATURE_OFF_ARM = "feature_off"
N7_CONSENSUS_ARM = CONSENSUS_PER_STEP_CONTACT_POLICY
N7_ARMS = (N7_FEATURE_OFF_ARM, N7_CONSENSUS_ARM)
N7_EXPERIMENTS = ("E2", "E3")
N7_SEED = 1000
N7_ITERATIONS = 50
N7_PAIR_COUNT = 5
N7_PHYSICAL_GPU_INDEX = 2
N7_SAMPLE_INTERVAL_SECONDS = 1.0
N7_REPLACEMENT_DELAY_SECONDS = 5.0
N7_RUN_LOCAL_CONFIG_FIELDS = {
    "anchor_keepin_config",
    "aux_input",
    "result_dir",
}
N7_CONTACT_CONFIG_FIELDS = {
    "collision_gradient_ratio",
    "collision_margin_mm",
    "collision_pair_diagnostics_flag",
    "collision_tau_mm",
    "exact_contact_policy",
    "exact_contact_projection_authority_search_strategy",
    "exact_contact_projection_flag",
    "exact_contact_projection_max_authority_states",
    "exact_contact_projection_max_cover_component_nodes",
    "exact_contact_projection_max_iterations",
    "exact_contact_projection_max_nodes",
    "exact_contact_projection_mode",
    "exact_contact_topology_min_net_degree",
    "exact_contact_topology_tiebreak_flag",
    "exact_step_guard_backoff",
    "exact_step_guard_flag",
    "exact_step_guard_max_retries",
    "footprint_collision_loss_flag",
}
N7_TIMING_FIELDS = (
    "gpu_optimization_seconds",
    "end_to_end_seconds",
)
N7_REPORTED_TIMING_FIELDS = (
    "optimization_wall_seconds",
    "exact_step_guard_seconds",
    "exact_overlap_diagnostic_seconds",
    "gpu_optimization_seconds",
    "preprocessing_seconds",
    "cache_load_seconds",
    "cache_write_seconds",
    "domain_build_seconds",
    "initialization_seconds",
    "exact_validation_seconds",
    "serialization_seconds",
    "native_scoring_seconds",
    "post_serialization_validation_seconds",
    "post_serialization_scoring_seconds",
    "bounded_repair_seconds",
    "end_to_end_seconds",
)
N7_PRESERVED_PATHS = (
    REPO_ROOT / "DREAMPlace.log",
    REPO_ROOT / "experiments/m336/guides/M336-141",
    REPO_ROOT / "m336_native_cypress_codex",
)
N7_RUN_LOCAL_INPUT_METADATA = {
    "manifest.json",
    "baseline_manifest.json",
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
    implementation_sha256 = hash_paths(IMPLEMENTATION_FILES)
    source_install_mismatches = []
    for source_path, source_digest in implementation_sha256.items():
        if not source_path.startswith("dreamplace/"):
            continue
        install_path = "install/" + source_path
        install_digest = implementation_sha256.get(install_path)
        if install_digest is not None and install_digest != source_digest:
            source_install_mismatches.append(
                {
                    "source": source_path,
                    "source_sha256": source_digest,
                    "install": install_path,
                    "install_sha256": install_digest,
                }
            )
    return {
        "branch": git_branch(),
        "git_sha": git_sha(),
        "dirty": bool(status),
        "dirty_paths": status,
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "implementation_sha256": implementation_sha256,
        "source_install_mismatches": source_install_mismatches,
    }


def _native_subprocess_environment(base_environment=None, overrides=None):
    environment = dict(
        os.environ if base_environment is None else base_environment
    )
    if overrides:
        environment.update(overrides)
    configured = environment.get("CUBLAS_WORKSPACE_CONFIG")
    if configured not in (None, DEFAULT_CUBLAS_WORKSPACE_CONFIG):
        raise ValueError(
            "deterministic M336 runs require CUBLAS_WORKSPACE_CONFIG=%s; "
            "found %s"
            % (DEFAULT_CUBLAS_WORKSPACE_CONFIG, configured)
        )
    environment["CUBLAS_WORKSPACE_CONFIG"] = (
        DEFAULT_CUBLAS_WORKSPACE_CONFIG
    )
    return environment


def runtime_environment():
    native_environment = _native_subprocess_environment()
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "cublas_workspace_config": native_environment[
            "CUBLAS_WORKSPACE_CONFIG"
        ],
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
            args.checkpoint_placement,
            REPO_ROOT / "experiments/m336/input/pcb_geometry_keepin.json",
            REPO_ROOT / "experiments/m336/input/m336_clusters.json",
            args.assignment,
            *bookshelf_files,
        )
    )


def constraint_config(
    run_dir,
    spec,
    assignment,
    grid_mm,
    clearance_mm,
    margin_mm,
    margin_tau_mm,
    manual_endpoint_placement,
    runtime_endpoint_placement,
):
    cluster_path = REPO_ROOT / "experiments/m336/input/m336_clusters.json"
    cluster_manifest = json.loads(cluster_path.read_text())
    return {
        "schema": "m336_anchor_keepin_config_v2",
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
        "endpoint_policy": {
            "default": "runtime",
            "manual_endpoints": ["EMI601"],
            "runtime_endpoints": ["Q601"],
            "manual_placement_file": str(
                Path(manual_endpoint_placement).resolve()
            ),
            "runtime_placement_file": str(
                Path(runtime_endpoint_placement).resolve()
            ),
        },
        "feature_flags": {
            "enable_anchor_loss": spec["anchor_loss"],
            "enable_hard_keepin_projection": spec["projection"],
            "enable_exact_repair": spec["repair"],
            "enable_rotation": False,
        },
        "repair": {
            "max_restore_components": 64,
            "max_restore_rounds": 4,
        },
        "geometry": {
            "placement_region_field": "component_placeable_regions",
            "constraint_grid_mm": grid_mm,
            "clearance_mm": clearance_mm,
            "keepin_margin_mm": margin_mm,
            "keepin_margin_tau_mm": margin_tau_mm,
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


def _resolve_contact_policy_contract(
    policy,
    mode=None,
    authority_search_strategy=None,
    topology_tiebreak=None,
    topology_min_net_degree=DEFAULT_M336_TOPOLOGY_MIN_NET_DEGREE,
):
    policy = str(policy or "").strip()
    if not policy:
        return {
            "policy": "",
            "mode": str(mode or "component_consensus"),
            "authority_search_strategy": str(
                authority_search_strategy or EXHAUSTIVE_AUTHORITY_SEARCH
            ),
            "topology_tiebreak": bool(topology_tiebreak or False),
            "topology_min_net_degree": int(topology_min_net_degree),
        }

    settings = contact_policy_settings(policy)
    if settings["stage_micro_enabled"]:
        raise ValueError(
            "%s is reserved until D3 authorizes stage micro"
            % CONSENSUS_PLUS_STAGE_MICRO_CONTACT_POLICY
        )
    conflicts = []
    if mode is not None and str(mode) != settings["mode"]:
        conflicts.append("mode")
    if (
        authority_search_strategy is not None
        and str(authority_search_strategy)
        != settings["authority_search_strategy"]
    ):
        conflicts.append("authority search")
    if (
        topology_tiebreak is not None
        and bool(topology_tiebreak) != settings["topology_tiebreak"]
    ):
        conflicts.append("topology tie-break")
    if (
        settings["topology_tiebreak"]
        and int(topology_min_net_degree)
        != settings["topology_min_net_degree"]
    ):
        conflicts.append("topology minimum net degree")
    if conflicts:
        raise ValueError(
            "exact contact policy %s conflicts with %s"
            % (policy, ", ".join(conflicts))
        )
    return {
        "policy": policy,
        "mode": settings["mode"],
        "authority_search_strategy": settings[
            "authority_search_strategy"
        ],
        "topology_tiebreak": settings["topology_tiebreak"],
        "topology_min_net_degree": settings[
            "topology_min_net_degree"
        ],
    }


def placement_config(
    run_dir,
    constraint_path,
    spec,
    seed,
    iterations,
    gpu,
    anchor_gradient_ratio,
    grid_mm,
    clearance_mm,
    margin_mm,
    margin_tau_mm,
    aux_input,
    source_placement=None,
    initial_placement=None,
    irregular_density=True,
    initialization_track="cold_source",
    feasible_domain_cache_dir=None,
    learning_rate_scale=1.0,
    footprint_collision=False,
    collision_gradient_ratio=0.1,
    collision_margin_mm=0.0,
    collision_tau_mm=0.025,
    exact_step_guard=False,
    exact_step_guard_backoff=0.5,
    exact_step_guard_max_retries=4,
    collision_pair_diagnostics=False,
    exact_contact_projection=False,
    exact_contact_policy="",
    exact_contact_projection_mode=None,
    exact_contact_projection_max_iterations=8,
    exact_contact_projection_max_nodes=32,
    exact_contact_projection_max_cover_component_nodes=16,
    exact_contact_projection_max_authority_states=4096,
    exact_contact_projection_authority_search_strategy=None,
    exact_contact_topology_tiebreak=None,
    exact_contact_topology_min_net_degree=(
        DEFAULT_M336_TOPOLOGY_MIN_NET_DEGREE
    ),
):
    learning_rate_scale = float(learning_rate_scale)
    if (
        not math.isfinite(learning_rate_scale)
        or learning_rate_scale < MIN_M336_LEARNING_RATE_SCALE
        or learning_rate_scale > MAX_M336_LEARNING_RATE_SCALE
    ):
        raise ValueError(
            "learning-rate scale must be finite and within [%g, %g]"
            % (MIN_M336_LEARNING_RATE_SCALE, MAX_M336_LEARNING_RATE_SCALE)
        )
    (
        collision_gradient_ratio,
        collision_margin_mm,
        collision_tau_mm,
    ) = (
        float(collision_gradient_ratio),
        float(collision_margin_mm),
        float(collision_tau_mm),
    )
    if (
        not all(
            math.isfinite(value)
            for value in (
                collision_gradient_ratio,
                collision_margin_mm,
                collision_tau_mm,
            )
        )
        or collision_gradient_ratio <= 0
        or collision_margin_mm < 0
        or collision_tau_mm <= 0
    ):
        raise ValueError(
            "collision ratio and tau must be positive and finite; "
            "collision margin must be finite and non-negative"
        )
    exact_step_guard_backoff = float(exact_step_guard_backoff)
    exact_step_guard_max_retries = int(exact_step_guard_max_retries)
    exact_contact_projection_max_iterations = int(
        exact_contact_projection_max_iterations
    )
    exact_contact_projection_max_nodes = int(
        exact_contact_projection_max_nodes
    )
    exact_contact_projection_max_cover_component_nodes = int(
        exact_contact_projection_max_cover_component_nodes
    )
    exact_contact_projection_max_authority_states = int(
        exact_contact_projection_max_authority_states
    )
    contact_policy = _resolve_contact_policy_contract(
        exact_contact_policy,
        mode=exact_contact_projection_mode,
        authority_search_strategy=(
            exact_contact_projection_authority_search_strategy
        ),
        topology_tiebreak=exact_contact_topology_tiebreak,
        topology_min_net_degree=exact_contact_topology_min_net_degree,
    )
    exact_contact_policy = contact_policy["policy"]
    exact_contact_projection_mode = contact_policy["mode"]
    exact_contact_projection_authority_search_strategy = contact_policy[
        "authority_search_strategy"
    ]
    exact_contact_topology_tiebreak = contact_policy[
        "topology_tiebreak"
    ]
    exact_contact_topology_min_net_degree = contact_policy[
        "topology_min_net_degree"
    ]
    if (
        not math.isfinite(exact_step_guard_backoff)
        or not 0 < exact_step_guard_backoff < 1
    ):
        raise ValueError("exact-step guard backoff must be in (0, 1)")
    if exact_step_guard_max_retries < 0:
        raise ValueError("exact-step guard retries must be non-negative")
    if exact_step_guard and not footprint_collision:
        raise ValueError("exact-step guard requires footprint collision")
    if collision_pair_diagnostics and not exact_step_guard:
        raise ValueError("collision pair diagnostics require exact-step guard")
    if exact_contact_projection and not exact_step_guard:
        raise ValueError("exact contact projection requires exact-step guard")
    if exact_contact_projection_max_iterations <= 0:
        raise ValueError("exact contact projection iterations must be positive")
    if exact_contact_projection_max_nodes < 2:
        raise ValueError(
            "exact contact projection node limit must be at least two"
        )
    if exact_contact_projection_mode not in CONTACT_PROJECTION_MODES:
        raise ValueError(
            "unknown exact contact projection mode: %s"
            % exact_contact_projection_mode
        )
    if exact_contact_projection_max_cover_component_nodes < 2:
        raise ValueError(
            "exact contact projection cover component limit must be at least "
            "two"
        )
    if (
        exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES
        and exact_contact_projection_max_authority_states <= 0
    ):
        raise ValueError(
            "exact contact projection authority state limit must be positive"
        )
    if (
        exact_contact_projection_authority_search_strategy
        not in AUTHORITY_SEARCH_STRATEGIES
    ):
        raise ValueError(
            "unknown exact contact projection authority search strategy: %s"
            % exact_contact_projection_authority_search_strategy
        )
    if (
        exact_contact_projection_authority_search_strategy
        != EXHAUSTIVE_AUTHORITY_SEARCH
        and exact_contact_projection_mode not in PROPOSAL_AUTHORITY_MODES
    ):
        raise ValueError(
            "factorized authority search requires proposal authority mode"
        )
    if exact_contact_topology_min_net_degree < 2:
        raise ValueError(
            "exact contact topology minimum net degree must be at least two"
        )
    if exact_contact_topology_tiebreak:
        if not exact_contact_projection:
            raise ValueError(
                "contact topology tie-break requires exact contact projection"
            )
        if (
            exact_contact_projection_mode
            != "protected_proposal_authority_search"
        ):
            raise ValueError(
                "contact topology tie-break requires protected proposal "
                "authority mode"
            )
    initialization_modes = {
        "cold_source": "preserve_legal",
        "checkpoint_warm_start": "checkpoint_warm_start",
    }
    if initialization_track not in initialization_modes:
        raise ValueError(
            "unknown initialization track: %s" % initialization_track
        )
    if initialization_track == "checkpoint_warm_start" and not initial_placement:
        raise ValueError("checkpoint track requires an initial placement")
    if initialization_track == "cold_source" and initial_placement:
        raise ValueError("cold/source track cannot load a checkpoint placement")
    if initialization_track == "cold_source" and not source_placement:
        raise ValueError("cold/source track requires a float source placement")
    selected_initial_placement = (
        initial_placement
        if initialization_track == "checkpoint_warm_start"
        else source_placement
    )
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
                "learning_rate": (
                    DEFAULT_M336_LEARNING_RATE * learning_rate_scale
                ),
                "wirelength": "weighted_average",
                "optimizer": "adam",
                "Llambda_density_weight_iteration": 1,
                "Lsub_iteration": 1,
            }
        ],
        "target_density": DEFAULT_M336_TARGET_DENSITY,
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
        "random_center_init_flag": 0,
        "sort_nets_by_degree": 0,
        "num_threads": 8,
        "deterministic_flag": 1,
        "enable_rotation": 0,
        "initial_placement_file": (
            str(Path(selected_initial_placement).resolve())
            if selected_initial_placement
            else ""
        ),
        "initial_placement_role": (
            "m336_118_checkpoint"
            if initialization_track == "checkpoint_warm_start"
            else "runtime_float_source"
        ),
        "initial_placement_strict": True,
        "initialization_track": initialization_track,
        "feasible_domain_cache_dir": (
            str(Path(feasible_domain_cache_dir).resolve())
            if feasible_domain_cache_dir
            else ""
        ),
    }
    if spec["integrated_context"]:
        config.update(
            {
                "anchor_keepin_config": str(constraint_path.resolve()),
                "anchor_keepin_flag": True,
                "anchor_loss_flag": spec["anchor_loss"],
                "anchor_gradient_ratio": anchor_gradient_ratio,
                "anchor_weight_update_interval": (
                    M336_ANCHOR_WEIGHT_UPDATE_INTERVAL
                ),
                "anchor_weight_ema_decay": M336_ANCHOR_WEIGHT_EMA_DECAY,
                "anchor_weight_min": M336_ANCHOR_WEIGHT_MIN,
                "anchor_weight_max": M336_ANCHOR_WEIGHT_MAX,
                "anchor_weight_warmup_iterations": (
                    M336_ANCHOR_WEIGHT_WARMUP_ITERATIONS
                ),
                "anchor_weight_ramp_iterations": (
                    M336_ANCHOR_WEIGHT_RAMP_ITERATIONS
                ),
                "keepin_soft_loss_flag": spec["soft_loss"],
                "irregular_density_flag": bool(
                    spec["irregular_density"] and irregular_density
                ),
                "irregular_density_require_feasible_target": bool(
                    spec["irregular_density"] and irregular_density
                ),
                "diagnostic_validation_on_high_overflow_flag": True,
                "exact_overlap_diagnostic_interval": 1,
                "footprint_collision_loss_flag": bool(
                    footprint_collision and spec["projection"]
                ),
                "collision_gradient_ratio": float(collision_gradient_ratio),
                "collision_margin_mm": float(collision_margin_mm),
                "collision_tau_mm": float(collision_tau_mm),
                "exact_step_guard_flag": bool(
                    exact_step_guard
                    and footprint_collision
                    and spec["projection"]
                ),
                "exact_step_guard_backoff": exact_step_guard_backoff,
                "exact_step_guard_max_retries": exact_step_guard_max_retries,
                "collision_pair_diagnostics_flag": bool(
                    collision_pair_diagnostics
                    and exact_step_guard
                    and footprint_collision
                    and spec["projection"]
                ),
                "exact_contact_projection_flag": bool(
                    exact_contact_projection
                    and exact_step_guard
                    and footprint_collision
                    and spec["projection"]
                ),
                "exact_contact_projection_mode": (
                    exact_contact_projection_mode
                ),
                "exact_contact_projection_max_iterations": (
                    exact_contact_projection_max_iterations
                ),
                "exact_contact_projection_max_nodes": (
                    exact_contact_projection_max_nodes
                ),
                "exact_contact_projection_max_cover_component_nodes": (
                    exact_contact_projection_max_cover_component_nodes
                ),
                "keepin_soft_loss_weight_scale": 1.0,
                "keepin_projection_flag": spec["projection"],
                "constraint_grid_mm": grid_mm,
                "keepin_clearance_mm": clearance_mm,
                "keepin_margin_mm": margin_mm,
                "keepin_margin_tau_mm": margin_tau_mm,
                "freeze_anchor_nodes": spec["freeze_anchors"],
                "allow_region_reassignment": False,
                "exact_repair_flag": spec["repair"],
                "anchor_keepin_initialization": initialization_modes[
                    initialization_track
                ],
            }
        )
        if (
            config["exact_contact_projection_flag"]
            and exact_contact_policy
        ):
            config["exact_contact_policy"] = exact_contact_policy
        if exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES:
            config["exact_contact_projection_max_authority_states"] = (
                exact_contact_projection_max_authority_states
            )
            if (
                exact_contact_projection_authority_search_strategy
                != EXHAUSTIVE_AUTHORITY_SEARCH
            ):
                config[
                    "exact_contact_projection_authority_search_strategy"
                ] = exact_contact_projection_authority_search_strategy
            if (
                exact_contact_topology_tiebreak
                and config["exact_contact_projection_flag"]
            ):
                config["exact_contact_topology_tiebreak_flag"] = True
                config["exact_contact_topology_min_net_degree"] = (
                    exact_contact_topology_min_net_degree
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


def _contact_projection_run_tags(config, args):
    contact_projection_enabled = bool(
        config.get("exact_contact_projection_flag", False)
    )
    contact_policy = str(config.get("exact_contact_policy", ""))
    policy_tag = (
        "-policy-%s" % contact_policy
        if contact_projection_enabled and contact_policy
        else ""
    )
    contact_tag = (
        "-contact-%s" % args.exact_contact_projection_mode
        if contact_projection_enabled
        else ""
    )
    authority_search_strategy = str(
        config.get(
            "exact_contact_projection_authority_search_strategy",
            EXHAUSTIVE_AUTHORITY_SEARCH,
        )
    )
    authority_search_tag = (
        "-authority-%s" % authority_search_strategy
        if authority_search_strategy != EXHAUSTIVE_AUTHORITY_SEARCH
        else ""
    )
    topology_tiebreak_enabled = bool(
        config.get("exact_contact_topology_tiebreak_flag", False)
    )
    topology_tag = (
        "-topology-degree-%d" % args.exact_contact_topology_min_net_degree
        if topology_tiebreak_enabled
        else ""
    )
    return {
        "policy": policy_tag,
        "contact": contact_tag,
        "authority_search": authority_search_tag,
        "topology": topology_tag,
    }


def evaluate_feature_off(
    config, constraint_path, placement_path, output_path, database_aux=None
):
    install_path = str(REPO_ROOT / "install")
    if install_path not in sys.path:
        sys.path.insert(0, install_path)
    from dreamplace import Params, PlaceDB
    from dreamplace.constraints.anchor_keepin import AnchorKeepInContext

    replay_config = dict(config)
    replay_config["dtype"] = "float64"
    params = Params.Params()
    params.update(replay_config)
    if database_aux is not None:
        params.aux_input = str(Path(database_aux).resolve())
    params.anchor_keepin_config = str(Path(constraint_path).resolve())
    params.anchor_keepin_flag = True
    params.anchor_loss_flag = False
    params.keepin_soft_loss_flag = False
    params.footprint_collision_loss_flag = False
    params.exact_step_guard_flag = False
    params.collision_pair_diagnostics_flag = False
    params.exact_contact_projection_flag = False
    params.keepin_projection_flag = False
    params.exact_repair_flag = False
    params.freeze_anchor_nodes = False
    placedb = PlaceDB.PlaceDB()
    placedb.read(params)
    placedb.initialize_from_rawdb(params)
    placedb.initialize(params)
    runtime_position = np.concatenate(
        (placedb.node_x.copy(), placedb.node_y.copy())
    )
    context = AnchorKeepInContext.from_params(
        params, placedb, runtime_position=runtime_position
    )
    pos = torch.from_numpy(runtime_position.copy())
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


def require_finite_native_scores(ppa):
    nonfinite = [
        name
        for name in ("hpwl", "rsmt")
        if not math.isfinite(float(ppa[name]))
    ]
    if nonfinite:
        raise ValueError(
            "native scoring returned non-finite metrics: %s" % nonfinite
        )


def _serialized_native_score_config(config, replay_aux, native_dir):
    score_config = dict(config)
    score_config.update(
        {
            "anchor_keepin_config": "",
            "anchor_keepin_flag": False,
            "anchor_loss_flag": False,
            "keepin_soft_loss_flag": False,
            "footprint_collision_loss_flag": False,
            "exact_step_guard_flag": False,
            "collision_pair_diagnostics_flag": False,
            "exact_contact_projection_flag": False,
            "exact_contact_policy": "",
            "exact_contact_projection_authority_search_strategy": (
                EXHAUSTIVE_AUTHORITY_SEARCH
            ),
            "exact_contact_topology_tiebreak_flag": False,
            "irregular_density_flag": False,
            "keepin_projection_flag": False,
            "exact_repair_flag": False,
            "exact_overlap_diagnostic_interval": 0,
            "aux_input": str(replay_aux.resolve()),
            "dtype": "float64",
            "evaluate_pl": 0,
            "global_place_flag": 0,
            "legalize_flag": 0,
            "detailed_place_flag": 0,
            "initial_placement_file": "",
            "initial_placement_role": "serialized_native_replay",
            "plot_flag": 0,
            "random_center_init_flag": 0,
            "result_dir": str(native_dir.resolve()),
        }
    )
    return score_config


def score_serialized_placement(
    config,
    placement_path,
    output_dir,
    bookshelf_dir,
    python,
    placer,
):
    """Replay serialized coordinates through native float64 HPWL/FLUTE."""
    input_dir = output_dir / "input"
    native_dir = output_dir / "native"
    input_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("m336.nodes", "m336.nets", "m336.scl"):
        shutil.copyfile(bookshelf_dir / filename, input_dir / filename)
    replay_placement = input_dir / "m336.serialized.pl"
    shutil.copyfile(placement_path, replay_placement)
    replay_aux = input_dir / "m336.serialized.aux"
    replay_aux.write_text(
        "RowBasedPlacement : m336.nodes m336.nets "
        "m336.serialized.pl m336.scl\n"
    )

    score_config = _serialized_native_score_config(
        config, replay_aux, native_dir
    )
    config_path = output_dir / "placement.json"
    write_json(config_path, score_config)
    command = [str(python), str(placer), str(config_path)]
    environment = _native_subprocess_environment(
        overrides={
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "PYTHONFAULTHANDLER": "1",
            "PYTHONPATH": str(REPO_ROOT / "install"),
        },
    )
    completed = subprocess.run(
        command,
        cwd=output_dir,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    process_log = output_dir / "process.log"
    process_log.write_text(completed.stdout)
    if completed.returncode:
        raise RuntimeError(
            "post-serialization native scoring failed with exit code %d; see %s"
            % (completed.returncode, process_log)
        )

    logs = sorted(native_dir.rglob("DREAMPlace.log"))
    placements = sorted(native_dir.rglob("*.gp.pl"))
    if len(logs) != 1 or len(placements) != 1:
        raise RuntimeError(
            "post-serialization scorer emitted unexpected artifacts: "
            "logs=%s placements=%s" % (logs, placements)
        )
    ppa = parse_final_ppa(logs[0].read_text())
    require_finite_native_scores(ppa)

    expected = parse_placement(replay_placement)
    actual = parse_placement(placements[0])
    if set(expected) != set(actual):
        raise ValueError("native scorer changed serialized placement identity")
    max_coordinate_error = max(
        abs(expected[name][axis] - actual[name][axis])
        for name in expected
        for axis in (0, 1)
    )
    if max_coordinate_error > 1e-9:
        raise ValueError(
            "native scorer moved serialized coordinates: max error=%g"
            % max_coordinate_error
        )
    result = {
        "schema": "m336_serialized_native_score_v1",
        "command": command,
        "input_placement": str(Path(placement_path).resolve()),
        "input_placement_sha256": sha256_file(placement_path),
        "replayed_placement": str(placements[0].resolve()),
        "replayed_placement_sha256": sha256_file(placements[0]),
        "coordinate_replay_max_error": max_coordinate_error,
        "dtype": "float64",
        "hpwl": float(ppa["hpwl"]),
        "rsmt": float(ppa["rsmt"]),
        "log": str(logs[0].resolve()),
        "process_log": str(process_log.resolve()),
    }
    write_json(output_dir / "native-score.json", result)
    return result


def validate_and_score_serialized_placement(
    config,
    constraint_path,
    placement_path,
    serialized_dir,
    bookshelf_dir,
    python,
    placer,
):
    """Validate and natively score the exact serialized placement bytes."""
    serialized_constraint_path = serialized_dir / "anchor_keepin.json"
    serialized_constraint = json.loads(Path(constraint_path).read_text())
    serialized_constraint.setdefault("reporting", {})["output_dir"] = str(
        (serialized_dir / "constraints").resolve()
    )
    write_json(serialized_constraint_path, serialized_constraint)

    legality_path = serialized_dir / "constraints" / "legality.json"
    validation_started = time.perf_counter()
    legality = evaluate_feature_off(
        config,
        serialized_constraint_path,
        placement_path,
        legality_path,
        database_aux=bookshelf_dir / "m336.aux",
    )
    validation_seconds = time.perf_counter() - validation_started

    scoring_started = time.perf_counter()
    score = score_serialized_placement(
        config,
        placement_path,
        serialized_dir / "native-score",
        bookshelf_dir,
        python,
        placer,
    )
    scoring_seconds = time.perf_counter() - scoring_started
    return {
        "constraint_path": serialized_constraint_path,
        "legality_path": legality_path,
        "legality": legality,
        "score": score,
        "validation_seconds": validation_seconds,
        "scoring_seconds": scoring_seconds,
    }


def parse_native_execution(log_text):
    matches = re.findall(r"native execution summary: (\{.*\})", log_text)
    if not matches:
        return None
    evidence = json.loads(matches[-1])
    required = {
        "backward_call_count",
        "nonlinear_place_executed",
        "optimizer_step_count",
        "place_obj_executed",
    }
    missing = sorted(required - evidence.keys())
    if missing:
        raise ValueError("native execution summary is missing: %s" % missing)
    return evidence


def parse_weight(log_text, label):
    matches = re.findall(
        r"%s weight = ([0-9.Ee+-]+)" % re.escape(label), log_text
    )
    return float(matches[-1]) if matches else None


def parse_anchor_weight_updates(log_text):
    return [
        json.loads(match)
        for match in re.findall(r"anchor weight update: (\{.*\})", log_text)
    ]


def parse_collision_weight_updates(log_text):
    return [
        json.loads(match)
        for match in re.findall(r"collision weight update: (\{.*\})", log_text)
    ]


def _configured_anchor_control(config, default_ratio):
    if "anchor_gradient_ratio" in config:
        return "anchor_gradient_ratio", float(config["anchor_gradient_ratio"])
    if "anchor_loss_weight_scale" in config:
        return "anchor_weight_scale", float(config["anchor_loss_weight_scale"])
    return "anchor_gradient_ratio", float(default_ratio)


def parse_weight_diagnostics(log_text, label, configured_scale):
    if label == "anchor loss":
        updates = parse_anchor_weight_updates(log_text)
        if updates:
            latest = updates[-1]
            return {
                "configured_target_ratio": float(configured_scale),
                "matched_weight": latest["effective_weight"],
                "wirelength_gradient_l1": latest[
                    "wirelength_gradient_l1"
                ],
                "constraint_gradient_l1": latest["anchor_gradient_l1"],
                "initial_loss": updates[0]["anchor_loss"],
                "effective_ratio": latest["effective_ratio"],
                "raw_weight": latest["raw_weight"],
                "bounded_weight": latest["bounded_weight"],
                "ema_weight": latest["ema_weight"],
                "ramp": latest["ramp"],
                "gradient_refresh_iteration": latest.get(
                    "gradient_refresh_iteration"
                ),
                "gradient_age": latest.get("gradient_age"),
                "effective_ratio_basis": latest.get(
                    "effective_ratio_basis"
                ),
                "effective_ratio_is_current": latest.get(
                    "effective_ratio_is_current"
                ),
                "update_count": len(updates),
            }
    if label == "footprint collision loss":
        updates = parse_collision_weight_updates(log_text)
        if updates:
            latest = updates[-1]
            return {
                "configured_target_ratio": float(configured_scale),
                "matched_weight": latest["effective_weight"],
                "wirelength_gradient_l1": latest[
                    "wirelength_gradient_l1"
                ],
                "constraint_gradient_l1": latest[
                    "collision_gradient_l1"
                ],
                "initial_loss": updates[0]["collision_loss"],
                "effective_ratio": latest["effective_ratio"],
                "raw_weight": latest["raw_weight"],
                "bounded_weight": latest["bounded_weight"],
                "ema_weight": latest["ema_weight"],
                "ramp": latest["ramp"],
                "update_count": len(updates),
            }
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
        "timing": run_dir / "constraints" / "timing.json",
        "collision_barrier": run_dir / "constraints" / "collision_barrier.json",
        "exact_step_guard": run_dir / "constraints" / "exact_step_guard.json",
        "exact_step_guard_failure": (
            run_dir / "constraints" / "exact_step_guard_failure.json"
        ),
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


def anchor_feasible_lower_bound_summary(report):
    lower_bound = report.get("anchor_feasible_lower_bound")
    if lower_bound is None:
        return None
    return {
        key: value
        for key, value in lower_bound.items()
        if key != "per_component"
    }


def preflight_summary(preflight):
    return {
        "resolved_member_count": preflight["resolved_member_count"],
        "movable_non_anchor_constraint_count": preflight[
            "movable_non_anchor_constraint_count"
        ],
        "frozen_anchor_count": preflight["frozen_anchor_count"],
        "frozen_fixed_obstacle_count": preflight.get(
            "frozen_fixed_obstacle_count", 0
        ),
        "infeasible_domain_count": len(preflight["infeasible_domains"]),
        "input_paths": preflight.get("input_paths", {}),
        "input_sha256": preflight.get("input_sha256", {}),
        "alignment": preflight["alignment"],
        "keepin_margin_mm": preflight.get("keepin_margin_mm"),
        "keepin_margin_tau_mm": preflight.get("keepin_margin_tau_mm"),
        "endpoint_policy": preflight.get("endpoint_policy"),
        "resolved_endpoints": preflight.get("resolved_endpoints", []),
        "domain_cache": preflight.get("domain_cache", {}),
        "anchor_feasible_lower_bound": (
            anchor_feasible_lower_bound_summary(preflight)
        ),
        "timing": preflight.get("timing", {}),
    }


def require_exact_e4_legality(experiment_id, legality):
    """Reject an E4 result unless serialized M336 output is exactly legal."""
    if experiment_id != "E4":
        return
    summary = legality_summary(legality)
    legal = (
        summary["constrained_components"] == 100
        and summary["fully_contained_components"] == 100
        and summary["keepin_violation_count"] == 0
        and summary["overlap_pair_count"] == 0
    )
    if not legal:
        raise RuntimeError(
            "E4 post-serialization exact legality failed: %s" % summary
        )


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
            args.keepin_margin_mm,
            args.keepin_margin_tau_mm,
            args.baseline_pl,
            args.bookshelf_dir / "m336.pl",
        ),
    )
    config = placement_config(
        run_dir,
        constraint_path,
        EXPERIMENTS["E0"],
        args.seeds[0],
        0,
        args.gpu,
        args.anchor_gradient_ratio,
        args.grid_mm,
        args.clearance_mm,
        args.keepin_margin_mm,
        args.keepin_margin_tau_mm,
        args.bookshelf_dir / "m336.aux",
        source_placement=args.baseline_pl,
        feasible_domain_cache_dir=args.feasible_domain_cache_dir,
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
    environment = _native_subprocess_environment(
        overrides={
            "PYTHONPATH": str(REPO_ROOT / "install"),
            "PYTHONFAULTHANDLER": "1",
        }
    )
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
    require_finite_native_scores(ppa)
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
        "environment": args.environment_identity,
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


def _require_collision_contract(config, args, spec, result_path, action):
    expected_enabled = bool(
        args.footprint_collision and spec["integrated_context"] and spec["projection"]
    )
    actual_enabled = bool(config.get("footprint_collision_loss_flag", False))
    expected_guard = bool(
        getattr(args, "exact_step_guard", False) and expected_enabled
    )
    actual_guard = bool(config.get("exact_step_guard_flag", False))
    expected_pair_diagnostics = bool(
        getattr(args, "collision_pair_diagnostics", False) and expected_guard
    )
    actual_pair_diagnostics = bool(
        config.get("collision_pair_diagnostics_flag", False)
    )
    expected_contact_projection = bool(
        getattr(args, "exact_contact_projection", False) and expected_guard
    )
    actual_contact_projection = bool(
        config.get("exact_contact_projection_flag", False)
    )
    actual_contact_policy = str(config.get("exact_contact_policy", ""))
    expected_contact_policy = str(
        getattr(args, "exact_contact_policy", "")
    )
    actual_contact_projection_mode = str(
        config.get(
            "exact_contact_projection_mode",
            "component_consensus",
        )
    )
    expected_contact_projection_mode = str(
        getattr(
            args,
            "exact_contact_projection_mode",
            "component_consensus",
        )
    )
    actual_authority_search_strategy = str(
        config.get(
            "exact_contact_projection_authority_search_strategy",
            EXHAUSTIVE_AUTHORITY_SEARCH,
        )
    )
    expected_authority_search_strategy = str(
        getattr(
            args,
            "exact_contact_projection_authority_search_strategy",
            EXHAUSTIVE_AUTHORITY_SEARCH,
        )
    )
    actual_topology_tiebreak = bool(
        config.get("exact_contact_topology_tiebreak_flag", False)
    )
    expected_topology_tiebreak = bool(
        getattr(args, "exact_contact_topology_tiebreak", False)
        and expected_contact_projection
    )
    checks = (
        ("enabled", float(actual_enabled), float(expected_enabled)),
        (
            "gradient ratio",
            float(config.get("collision_gradient_ratio", 0.1)),
            float(args.collision_gradient_ratio),
        ),
        (
            "margin",
            float(config.get("collision_margin_mm", 0.0)),
            float(args.collision_margin_mm),
        ),
        (
            "tau",
            float(config.get("collision_tau_mm", 0.025)),
            float(args.collision_tau_mm),
        ),
        ("guard enabled", float(actual_guard), float(expected_guard)),
        (
            "pair diagnostics enabled",
            float(actual_pair_diagnostics),
            float(expected_pair_diagnostics),
        ),
        (
            "contact projection enabled",
            float(actual_contact_projection),
            float(expected_contact_projection),
        ),
        (
            "guard backoff",
            float(config.get("exact_step_guard_backoff", 0.5)),
            float(getattr(args, "exact_step_guard_backoff", 0.5)),
        ),
        (
            "guard retries",
            float(config.get("exact_step_guard_max_retries", 4)),
            float(getattr(args, "exact_step_guard_max_retries", 4)),
        ),
    )
    if actual_contact_projection or expected_contact_projection:
        checks += (
            (
                "contact projection iterations",
                float(
                    config.get("exact_contact_projection_max_iterations", 8)
                ),
                float(
                    getattr(
                        args,
                        "exact_contact_projection_max_iterations",
                        8,
                    )
                ),
            ),
            (
                "contact projection nodes",
                float(config.get("exact_contact_projection_max_nodes", 32)),
                float(
                    getattr(args, "exact_contact_projection_max_nodes", 32)
                ),
            ),
            (
                "contact projection cover component nodes",
                float(
                    config.get(
                        "exact_contact_projection_max_cover_component_nodes",
                        16,
                    )
                ),
                float(
                    getattr(
                        args,
                        "exact_contact_projection_max_cover_component_nodes",
                        16,
                    )
                ),
            ),
        )
        if (
            actual_contact_projection_mode in PROPOSAL_AUTHORITY_MODES
            or expected_contact_projection_mode in PROPOSAL_AUTHORITY_MODES
        ):
            checks += (
                (
                    "contact projection authority states",
                    float(
                        config.get(
                            "exact_contact_projection_max_authority_states",
                            4096,
                        )
                    ),
                    float(
                        getattr(
                            args,
                            "exact_contact_projection_max_authority_states",
                            4096,
                        )
                    ),
                ),
            )
        if actual_topology_tiebreak or expected_topology_tiebreak:
            checks += (
                (
                    "contact topology minimum net degree",
                    float(
                        config.get(
                            "exact_contact_topology_min_net_degree",
                            DEFAULT_M336_TOPOLOGY_MIN_NET_DEGREE,
                        )
                    ),
                    float(
                        getattr(
                            args,
                            "exact_contact_topology_min_net_degree",
                            DEFAULT_M336_TOPOLOGY_MIN_NET_DEGREE,
                        )
                    ),
                ),
            )
    mismatches = [
        label
        for label, actual, expected in checks
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
    ]
    if (
        actual_contact_projection or expected_contact_projection
    ) and actual_contact_projection_mode != expected_contact_projection_mode:
        mismatches.append("contact projection mode")
    if (
        actual_contact_projection or expected_contact_projection
    ) and actual_contact_policy != expected_contact_policy:
        mismatches.append("contact policy")
    if (
        (actual_contact_projection or expected_contact_projection)
        and (
            actual_contact_projection_mode in PROPOSAL_AUTHORITY_MODES
            or expected_contact_projection_mode in PROPOSAL_AUTHORITY_MODES
        )
        and actual_authority_search_strategy
        != expected_authority_search_strategy
    ):
        mismatches.append("contact projection authority search strategy")
    if actual_topology_tiebreak != expected_topology_tiebreak:
        mismatches.append("contact topology tie-break")
    if mismatches:
        raise RuntimeError(
            "cannot %s with changed collision contract (%s): %s"
            % (action, ", ".join(mismatches), result_path)
        )


def run_one(
    args,
    experiment_id,
    seed,
    output_dir=None,
    anchor_gradient_ratio=None,
    initialization_track="cold_source",
):
    spec = EXPERIMENTS[experiment_id]
    output_dir = output_dir or args.output_dir
    anchor_gradient_ratio = (
        args.anchor_gradient_ratio
        if anchor_gradient_ratio is None
        else anchor_gradient_ratio
    )
    run_dir = (
        output_dir
        / initialization_track
        / experiment_id
        / ("seed_%d" % seed)
    )
    result_path = run_dir / "run-result.json"
    if args.reevaluate:
        if not result_path.exists():
            raise FileNotFoundError("cannot reevaluate missing run: %s" % result_path)
        result = json.loads(result_path.read_text())
        previous_input_identity = result.get("input_sha256")
        if (
            previous_input_identity is not None
            and previous_input_identity != args.input_identity
        ):
            raise RuntimeError(
                "cannot reevaluate with changed input hashes: %s" % result_path
            )
        config = result["config"]
        _require_collision_contract(
            config, args, spec, result_path, "reevaluate"
        )
        configured_learning_rate_scale = (
            float(config["global_place_stages"][0]["learning_rate"])
            / DEFAULT_M336_LEARNING_RATE
        )
        if not math.isclose(
            configured_learning_rate_scale,
            args.learning_rate_scale,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError(
                "cannot reevaluate with changed learning-rate scale: %s"
                % result_path
            )
        constraint_path = run_dir / "anchor_keepin.json"
        placement_dir = run_dir / "m336"
        placement_path = placement_dir / "m336.gp.pl"
        serialized_dir = run_dir / "post-serialization"
        replay = validate_and_score_serialized_placement(
            config,
            constraint_path,
            placement_path,
            serialized_dir,
            args.bookshelf_dir,
            args.python,
            args.placer,
        )
        legality = replay["legality"]
        serialized_score = replay["score"]
        require_exact_e4_legality(experiment_id, legality)
        result["metrics"]["anchor_distance_mm"] = legality["anchor_distance_mm"]
        result["metrics"]["projected_anchor_distance_mm"] = legality[
            "projected_anchor_distance_mm"
        ]
        result["metrics"]["anchor_feasible_lower_bound"] = (
            anchor_feasible_lower_bound_summary(legality)
        )
        result["metrics"]["per_group"] = legality["per_group"]
        result["metrics"]["hpwl"] = serialized_score["hpwl"]
        result["metrics"]["rsmt"] = serialized_score["rsmt"]
        log_text = (placement_dir / "DREAMPlace.log").read_text()
        in_memory_ppa = parse_final_ppa(log_text)
        require_finite_native_scores(in_memory_ppa)
        result["metrics"]["pre_serialization_hpwl"] = float(
            in_memory_ppa["hpwl"]
        )
        result["metrics"]["pre_serialization_rsmt"] = float(
            in_memory_ppa["rsmt"]
        )
        anchor_control_key, configured_anchor_control = (
            _configured_anchor_control(config, anchor_gradient_ratio)
        )
        result["metrics"]["matched_anchor_weight"] = parse_weight(
            log_text, "anchor loss"
        )
        result["metrics"]["anchor_loss_diagnostics"] = parse_weight_diagnostics(
            log_text, "anchor loss", configured_anchor_control
        )
        result["metrics"]["soft_keepin_loss_diagnostics"] = (
            parse_weight_diagnostics(log_text, "soft keep-in loss", 1.0)
        )
        result["metrics"]["matched_collision_weight"] = parse_weight(
            log_text, "footprint collision loss"
        )
        result["metrics"]["collision_loss_diagnostics"] = (
            parse_weight_diagnostics(
                log_text,
                "footprint collision loss",
                args.collision_gradient_ratio,
            )
        )
        result["metrics"]["native_execution"] = parse_native_execution(log_text)
        result["metrics"]["anchor_weight_updates"] = (
            parse_anchor_weight_updates(log_text)
        )
        result["metrics"]["collision_weight_updates"] = (
            parse_collision_weight_updates(log_text)
        )
        result["legality"] = legality_summary(legality)
        if anchor_control_key == "anchor_gradient_ratio":
            result[anchor_control_key] = configured_anchor_control
            result.pop("anchor_weight_scale", None)
        else:
            result[anchor_control_key] = configured_anchor_control
            result.pop("anchor_gradient_ratio", None)
        result["constraint_grid_mm"] = float(args.grid_mm)
        result["keepin_clearance_mm"] = float(args.clearance_mm)
        result["keepin_margin_mm"] = float(
            config.get("keepin_margin_mm", args.keepin_margin_mm)
        )
        result["keepin_margin_tau_mm"] = float(
            config.get("keepin_margin_tau_mm", args.keepin_margin_tau_mm)
        )
        result["footprint_collision_enabled"] = bool(
            config.get("footprint_collision_loss_flag", False)
        )
        result["collision_gradient_ratio"] = float(
            config.get("collision_gradient_ratio", args.collision_gradient_ratio)
        )
        result["collision_margin_mm"] = float(
            config.get("collision_margin_mm", args.collision_margin_mm)
        )
        result["collision_tau_mm"] = float(
            config.get("collision_tau_mm", args.collision_tau_mm)
        )
        result["exact_step_guard_enabled"] = bool(
            config.get("exact_step_guard_flag", False)
        )
        result["exact_step_guard_backoff"] = float(
            config.get(
                "exact_step_guard_backoff", args.exact_step_guard_backoff
            )
        )
        result["exact_step_guard_max_retries"] = int(
            config.get(
                "exact_step_guard_max_retries",
                args.exact_step_guard_max_retries,
            )
        )
        result["collision_pair_diagnostics_enabled"] = bool(
            config.get("collision_pair_diagnostics_flag", False)
        )
        result["exact_contact_projection_enabled"] = bool(
            config.get("exact_contact_projection_flag", False)
        )
        result["exact_contact_policy"] = str(
            config.get("exact_contact_policy", "")
        )
        result["exact_contact_projection_mode"] = str(
            config.get(
                "exact_contact_projection_mode",
                "component_consensus",
            )
        )
        result["exact_contact_projection_max_iterations"] = int(
            config.get("exact_contact_projection_max_iterations", 8)
        )
        result["exact_contact_projection_max_nodes"] = int(
            config.get("exact_contact_projection_max_nodes", 32)
        )
        result[
            "exact_contact_projection_max_cover_component_nodes"
        ] = int(
            config.get(
                "exact_contact_projection_max_cover_component_nodes",
                16,
            )
        )
        if (
            result["exact_contact_projection_mode"]
            in PROPOSAL_AUTHORITY_MODES
        ):
            result[
                "exact_contact_projection_max_authority_states"
            ] = int(
                config.get(
                    "exact_contact_projection_max_authority_states",
                    4096,
                )
            )
            authority_search_strategy = str(
                config.get(
                    "exact_contact_projection_authority_search_strategy",
                    EXHAUSTIVE_AUTHORITY_SEARCH,
                )
            )
            if authority_search_strategy != EXHAUSTIVE_AUTHORITY_SEARCH:
                result[
                    "exact_contact_projection_authority_search_strategy"
                ] = authority_search_strategy
            else:
                result.pop(
                    "exact_contact_projection_authority_search_strategy",
                    None,
                )
            topology_tiebreak_enabled = bool(
                config.get("exact_contact_topology_tiebreak_flag", False)
            )
            if topology_tiebreak_enabled:
                result["exact_contact_topology_tiebreak_enabled"] = True
                result["exact_contact_topology_min_net_degree"] = int(
                    config.get(
                        "exact_contact_topology_min_net_degree",
                        DEFAULT_M336_TOPOLOGY_MIN_NET_DEGREE,
                    )
                )
            else:
                result.pop(
                    "exact_contact_topology_tiebreak_enabled", None
                )
                result.pop(
                    "exact_contact_topology_min_net_degree", None
                )
        result["irregular_density_enabled"] = bool(
            config.get("irregular_density_flag", False)
        )
        result["learning_rate_scale"] = configured_learning_rate_scale
        result["input_sha256"] = args.input_identity
        result.setdefault("source_state", args.source_identity)
        result["environment"] = args.environment_identity
        result["reevaluation"] = {
            "git_sha": git_sha(),
            "source_state": args.source_identity,
            "input_sha256": args.input_identity,
            "post_serialization_validation_seconds": replay[
                "validation_seconds"
            ],
            "post_serialization_scoring_seconds": replay["scoring_seconds"],
        }
        preflight_path = run_dir / "constraints" / "preflight.json"
        if not preflight_path.exists():
            preflight_path = serialized_dir / "constraints" / "preflight.json"
        if preflight_path.exists():
            preflight = json.loads(preflight_path.read_text())
            result["preflight"] = preflight_summary(preflight)
        initialization_path = run_dir / "constraints" / "initialization.json"
        if initialization_path.exists():
            result["initialization"] = json.loads(
                initialization_path.read_text()
            )
        timing_path = run_dir / "constraints" / "timing.json"
        if timing_path.exists():
            result["timing"] = json.loads(timing_path.read_text())
        else:
            result.setdefault("timing", {})
        native_runtime = float(
            result.get(
                "native_placement_runtime_seconds",
                result.get("runtime_seconds", 0.0),
            )
        )
        result["native_placement_runtime_seconds"] = native_runtime
        result["post_serialization_validation_seconds"] = replay[
            "validation_seconds"
        ]
        result["post_serialization_scoring_seconds"] = replay[
            "scoring_seconds"
        ]
        result["runtime_seconds"] = (
            native_runtime
            + replay["validation_seconds"]
            + replay["scoring_seconds"]
        )
        result["timing"].update(
            {
                "post_serialization_validation_seconds": replay[
                    "validation_seconds"
                ],
                "post_serialization_scoring_seconds": replay[
                    "scoring_seconds"
                ],
                "end_to_end_seconds": result["runtime_seconds"],
            }
        )
        aggregate_timing_path = run_dir / "timing.json"
        write_json(aggregate_timing_path, result["timing"])
        write_per_group_csv(run_dir / "per_group.csv", legality["per_group"])
        result["artifacts"] = stable_artifacts(
            run_dir, placement_dir, replay["legality_path"]
        )
        result["artifacts"].update(
            {
                "aggregate_timing": repo_path(aggregate_timing_path),
                "post_serialization_constraint": repo_path(
                    replay["constraint_path"]
                ),
                "post_serialization_legality": repo_path(
                    replay["legality_path"]
                ),
                "post_serialization_native_score": repo_path(
                    serialized_dir / "native-score" / "native-score.json"
                ),
                "post_serialization_preflight": repo_path(
                    serialized_dir / "constraints" / "preflight.json"
                ),
                "post_serialization_input_alignment": repo_path(
                    serialized_dir / "constraints" / "input_alignment.json"
                ),
            }
        )
        repair_path = run_dir / "constraints" / "repair.json"
        if repair_path.exists():
            result["artifacts"]["repair"] = repo_path(repair_path)
            result["repair"] = json.loads(repair_path.read_text())
        result["serialized_native_score"] = serialized_score
        result["manual_baseline_comparison"] = compare_with_manual_baseline(
            result["metrics"], args.manual_baseline
        )
        write_json(result_path, result)
        return result
    if args.resume and result_path.exists():
        result = json.loads(result_path.read_text())
        _require_collision_contract(
            result.get("config", {}), args, spec, result_path, "resume"
        )
        if not math.isclose(
            float(result.get("learning_rate_scale", 1.0)),
            args.learning_rate_scale,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError(
                "cannot resume with changed learning-rate scale: %s"
                % result_path
            )
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
            run_dir,
            spec,
            args.assignment,
            args.grid_mm,
            args.clearance_mm,
            args.keepin_margin_mm,
            args.keepin_margin_tau_mm,
            args.baseline_pl,
            args.bookshelf_dir / "m336.pl",
        ),
    )
    initial_placement = (
        args.checkpoint_placement
        if initialization_track == "checkpoint_warm_start"
        else None
    )
    config = placement_config(
        run_dir,
        constraint_path,
        spec,
        seed,
        args.iterations,
        args.gpu,
        anchor_gradient_ratio,
        args.grid_mm,
        args.clearance_mm,
        args.keepin_margin_mm,
        args.keepin_margin_tau_mm,
        args.bookshelf_dir / "m336.aux",
        source_placement=args.bookshelf_dir / "m336.pl",
        initial_placement=initial_placement,
        irregular_density=args.irregular_density,
        initialization_track=initialization_track,
        feasible_domain_cache_dir=args.feasible_domain_cache_dir,
        learning_rate_scale=args.learning_rate_scale,
        footprint_collision=args.footprint_collision,
        collision_gradient_ratio=args.collision_gradient_ratio,
        collision_margin_mm=args.collision_margin_mm,
        collision_tau_mm=args.collision_tau_mm,
        exact_step_guard=args.exact_step_guard,
        exact_step_guard_backoff=args.exact_step_guard_backoff,
        exact_step_guard_max_retries=args.exact_step_guard_max_retries,
        collision_pair_diagnostics=args.collision_pair_diagnostics,
        exact_contact_projection=args.exact_contact_projection,
        exact_contact_policy=args.exact_contact_policy,
        exact_contact_projection_mode=args.exact_contact_projection_mode,
        exact_contact_projection_max_iterations=(
            args.exact_contact_projection_max_iterations
        ),
        exact_contact_projection_max_nodes=(
            args.exact_contact_projection_max_nodes
        ),
        exact_contact_projection_max_cover_component_nodes=(
            args.exact_contact_projection_max_cover_component_nodes
        ),
        exact_contact_projection_max_authority_states=(
            args.exact_contact_projection_max_authority_states
        ),
        exact_contact_projection_authority_search_strategy=(
            args.exact_contact_projection_authority_search_strategy
        ),
        exact_contact_topology_tiebreak=(
            args.exact_contact_topology_tiebreak
        ),
        exact_contact_topology_min_net_degree=(
            args.exact_contact_topology_min_net_degree
        ),
    )
    write_json(config_path, config)
    command = [args.python, str(args.placer), str(config_path)]
    environment = _native_subprocess_environment(
        overrides={
            "PYTHONPATH": str(REPO_ROOT / "install"),
            "PYTHONFAULTHANDLER": "1",
        }
    )
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
    in_memory_ppa = parse_final_ppa(log_text)
    require_finite_native_scores(in_memory_ppa)
    in_memory_legality_path = run_dir / "constraints" / "legality.json"
    in_memory_legality = (
        json.loads(in_memory_legality_path.read_text())
        if in_memory_legality_path.exists()
        else None
    )

    serialized_dir = run_dir / "post-serialization"
    replay = validate_and_score_serialized_placement(
        config,
        constraint_path,
        placement_dir / "m336.gp.pl",
        serialized_dir,
        args.bookshelf_dir,
        args.python,
        args.placer,
    )
    legality = replay["legality"]
    serialized_score = replay["score"]
    post_serialization_validation_seconds = replay["validation_seconds"]
    post_serialization_scoring_seconds = replay["scoring_seconds"]
    require_exact_e4_legality(experiment_id, legality)

    preflight_path = run_dir / "constraints" / "preflight.json"
    if not preflight_path.exists():
        preflight_path = serialized_dir / "constraints" / "preflight.json"
    preflight = json.loads(preflight_path.read_text())
    write_per_group_csv(run_dir / "per_group.csv", legality["per_group"])
    learning_rate_tag = (
        ""
        if math.isclose(
            args.learning_rate_scale, 1.0, rel_tol=0.0, abs_tol=1e-12
        )
        else "-lr-%s" % format(args.learning_rate_scale, "g")
    )
    collision_enabled = bool(config.get("footprint_collision_loss_flag", False))
    collision_tag = (
        "-collision-%s" % format(args.collision_gradient_ratio, "g")
        if collision_enabled
        else ""
    )
    exact_step_guard_enabled = bool(config.get("exact_step_guard_flag", False))
    guard_tag = "-guard" if exact_step_guard_enabled else ""
    contact_projection_enabled = bool(
        config.get("exact_contact_projection_flag", False)
    )
    contact_tags = _contact_projection_run_tags(config, args)
    authority_search_strategy = str(
        config.get(
            "exact_contact_projection_authority_search_strategy",
            EXHAUSTIVE_AUTHORITY_SEARCH,
        )
    )
    topology_tiebreak_enabled = bool(
        config.get("exact_contact_topology_tiebreak_flag", False)
    )

    result = {
        "run_id": "%s-%s-ar-%s%s%s%s%s%s%s%s-margin-%s-seed-%d"
        % (
            initialization_track,
            experiment_id.lower(),
            format(anchor_gradient_ratio, "g"),
            learning_rate_tag,
            collision_tag,
            guard_tag,
            contact_tags["policy"],
            contact_tags["contact"],
            contact_tags["authority_search"],
            contact_tags["topology"],
            format(args.keepin_margin_mm, "g"),
            seed,
        ),
        "git_sha": git_sha(),
        "experiment_id": experiment_id,
        "experiment_name": spec["name"],
        "initialization_track": initialization_track,
        "seed": seed,
        "anchor_gradient_ratio": float(anchor_gradient_ratio),
        "learning_rate_scale": float(args.learning_rate_scale),
        "constraint_grid_mm": float(args.grid_mm),
        "keepin_clearance_mm": float(args.clearance_mm),
        "keepin_margin_mm": float(args.keepin_margin_mm),
        "keepin_margin_tau_mm": float(args.keepin_margin_tau_mm),
        "footprint_collision_enabled": collision_enabled,
        "collision_gradient_ratio": float(args.collision_gradient_ratio),
        "collision_margin_mm": float(args.collision_margin_mm),
        "collision_tau_mm": float(args.collision_tau_mm),
        "exact_step_guard_enabled": exact_step_guard_enabled,
        "exact_step_guard_backoff": float(args.exact_step_guard_backoff),
        "exact_step_guard_max_retries": int(
            args.exact_step_guard_max_retries
        ),
        "collision_pair_diagnostics_enabled": bool(
            config.get("collision_pair_diagnostics_flag", False)
        ),
        "exact_contact_projection_enabled": bool(
            config.get("exact_contact_projection_flag", False)
        ),
        "exact_contact_policy": str(
            config.get("exact_contact_policy", "")
        ),
        "exact_contact_projection_mode": str(
            config.get(
                "exact_contact_projection_mode",
                "component_consensus",
            )
        ),
        "exact_contact_projection_max_iterations": int(
            config.get("exact_contact_projection_max_iterations", 8)
        ),
        "exact_contact_projection_max_nodes": int(
            config.get("exact_contact_projection_max_nodes", 32)
        ),
        "exact_contact_projection_max_cover_component_nodes": int(
            config.get(
                "exact_contact_projection_max_cover_component_nodes",
                16,
            )
        ),
        "irregular_density_enabled": bool(
            config.get("irregular_density_flag", False)
        ),
        "command": command,
        "config": config,
        "environment": args.environment_identity,
        "input_sha256": args.input_identity,
        "source_state": args.source_identity,
        "preflight": preflight_summary(preflight),
        "runtime_seconds": (
            runtime
            + post_serialization_validation_seconds
            + post_serialization_scoring_seconds
        ),
        "native_placement_runtime_seconds": runtime,
        "post_serialization_validation_seconds": (
            post_serialization_validation_seconds
        ),
        "post_serialization_scoring_seconds": (
            post_serialization_scoring_seconds
        ),
        "device": (
            "NVIDIA H100"
            if "Using Torch GPU device" in log_text
            else "CPU"
        ),
        "metrics": {
            "hpwl": serialized_score["hpwl"],
            "rsmt": serialized_score["rsmt"],
            "pre_serialization_hpwl": float(in_memory_ppa["hpwl"]),
            "pre_serialization_rsmt": float(in_memory_ppa["rsmt"]),
            "objective": float(in_memory_ppa["objective"]),
            "overflow": float(in_memory_ppa["overflow"]),
            "iterations": int(in_memory_ppa["iteration"]),
            "anchor_distance_mm": legality["anchor_distance_mm"],
            "projected_anchor_distance_mm": legality[
                "projected_anchor_distance_mm"
            ],
            "anchor_feasible_lower_bound": (
                anchor_feasible_lower_bound_summary(legality)
            ),
            "per_group": legality["per_group"],
            "total_projected_nodes": (
                in_memory_legality.get("total_projected_nodes", 0)
                if in_memory_legality is not None
                else 0
            ),
            "matched_anchor_weight": parse_weight(log_text, "anchor loss"),
            "anchor_loss_diagnostics": parse_weight_diagnostics(
                log_text, "anchor loss", anchor_gradient_ratio
            ),
            "soft_keepin_loss_diagnostics": parse_weight_diagnostics(
                log_text, "soft keep-in loss", 1.0
            ),
            "matched_collision_weight": parse_weight(
                log_text, "footprint collision loss"
            ),
            "collision_loss_diagnostics": parse_weight_diagnostics(
                log_text,
                "footprint collision loss",
                args.collision_gradient_ratio,
            ),
            "native_execution": parse_native_execution(log_text),
            "anchor_weight_updates": parse_anchor_weight_updates(log_text),
            "collision_weight_updates": parse_collision_weight_updates(log_text),
        },
        "legality": legality_summary(legality),
        "artifacts": stable_artifacts(
            run_dir, placement_dir, replay["legality_path"]
        ),
        "serialized_native_score": serialized_score,
        "warnings": [
            "Source declares 27 clusters but enumerates 25 rows/125 unique members."
        ],
        "manual_baseline_comparison": compare_with_manual_baseline(
            {"hpwl": serialized_score["hpwl"], "rsmt": serialized_score["rsmt"]},
            args.manual_baseline,
        ),
    }
    if result["exact_contact_projection_mode"] in PROPOSAL_AUTHORITY_MODES:
        result["exact_contact_projection_max_authority_states"] = int(
            config.get(
                "exact_contact_projection_max_authority_states",
                4096,
            )
        )
        if authority_search_strategy != EXHAUSTIVE_AUTHORITY_SEARCH:
            result[
                "exact_contact_projection_authority_search_strategy"
            ] = authority_search_strategy
        if topology_tiebreak_enabled:
            result["exact_contact_topology_tiebreak_enabled"] = True
            result["exact_contact_topology_min_net_degree"] = int(
                args.exact_contact_topology_min_net_degree
            )
    initialization_path = run_dir / "constraints" / "initialization.json"
    if initialization_path.exists():
        result["initialization"] = json.loads(initialization_path.read_text())
    timing_path = run_dir / "constraints" / "timing.json"
    if timing_path.exists():
        result["timing"] = json.loads(timing_path.read_text())
    else:
        result["timing"] = {}
    result["timing"].update(
        {
            "post_serialization_validation_seconds": (
                post_serialization_validation_seconds
            ),
            "post_serialization_scoring_seconds": (
                post_serialization_scoring_seconds
            ),
            "end_to_end_seconds": result["runtime_seconds"],
        }
    )
    aggregate_timing_path = run_dir / "timing.json"
    write_json(aggregate_timing_path, result["timing"])
    result["artifacts"].update(
        {
            "aggregate_timing": repo_path(aggregate_timing_path),
            "post_serialization_constraint": repo_path(
                replay["constraint_path"]
            ),
            "post_serialization_legality": repo_path(
                replay["legality_path"]
            ),
            "post_serialization_native_score": repo_path(
                serialized_dir / "native-score" / "native-score.json"
            ),
            "post_serialization_preflight": repo_path(
                serialized_dir / "constraints" / "preflight.json"
            ),
            "post_serialization_input_alignment": repo_path(
                serialized_dir / "constraints" / "input_alignment.json"
            ),
        }
    )
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


def _result_anchor_gradient_ratio(result):
    if "anchor_gradient_ratio" in result:
        return float(result["anchor_gradient_ratio"])
    return float(result["anchor_weight_scale"])


def aggregate_weight_sweep(results):
    rows = {}
    ratios = sorted({_result_anchor_gradient_ratio(row) for row in results})
    experiments = sorted({row["experiment_id"] for row in results})
    for ratio in ratios:
        ratio_key = format(ratio, "g")
        rows[ratio_key] = {}
        for experiment_id in experiments:
            selected = [
                row
                for row in results
                if row["experiment_id"] == experiment_id
                and _result_anchor_gradient_ratio(row) == ratio
            ]
            if not selected:
                continue
            matched_weights = [
                row["metrics"]["anchor_loss_diagnostics"]["matched_weight"]
                for row in selected
                if row["metrics"].get("anchor_loss_diagnostics")
            ]
            rows[ratio_key][experiment_id] = {
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


def _warm_runtime_gate(results, runtime_ratio):
    tracks = {row.get("initialization_track") for row in results}
    if tracks != {"checkpoint_warm_start"}:
        return None
    return runtime_ratio <= 2.0


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
                "runtime_at_most_2x": _warm_runtime_gate(
                    results,
                    comparisons["e4_vs_e0"]["runtime_ratio"],
                ),
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
        "- CuBLAS workspace: `%s`."
        % environment["cublas_workspace_config"],
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
        runtime_gate = summary["acceptance"]["goals"]["runtime_at_most_2x"]
        if runtime_gate is None:
            lines.append(
                "- `NOT APPLICABLE` E4/E0 end-to-end runtime ratio: "
                "`%.2fx`; the <=2x gate applies only to checkpoint warm runs."
                % comparison["runtime_ratio"]
            )
        else:
            lines.append(
                "- `%s` E4/E0 end-to-end runtime ratio: `%.2fx` "
                "(warm target <=2x)."
                % (
                    _status(runtime_gate),
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
                "## Anchor Gradient-Ratio Sweep",
                "",
                "Artifact: `%s`" % sweep["artifact"],
                "Seeds: `%s`; iterations: `%d`."
                % (", ".join(map(str, sweep["seeds"])), sweep["iterations"]),
                "",
                "| Target ratio | Run | Runs | Effective lambda | HPWL | Mean mm | P90 mm | Violations |",
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
    soft_diagnostics = [
        row["metrics"].get("soft_keepin_loss_diagnostics")
        for row in summary["runs"]
    ]
    soft_diagnostics = [row for row in soft_diagnostics if row is not None]
    if any(row["constraint_gradient_l1"] > 0 for row in soft_diagnostics):
        lines.append(
            "- The interior keep-in margin produced a nonzero GPU gradient; "
            "projection pressure and quality still require a controlled ablation."
        )
    elif soft_diagnostics:
        lines.append(
            "- The configured soft keep-in term produced zero gradient and is "
            "not evidence of stabilization."
        )
    lines.extend(
        [
            "- End-to-end runtime misses the target because each subprocess rebuilds 100 Shapely feasible domains and E4 performs exact packing repair.",
            "- Full configs, hashes, logs, placements, per-group CSV files, legality reports, and E4 repair reports are indexed by `summary.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_weight_sweep_report(summary):
    lines = [
        "# M336 Anchor Gradient-Ratio Sweep",
        "",
        "- Git SHA: `%s`" % summary["git_sha"],
        "- Seeds: `%s`" % ", ".join(map(str, summary["seeds"])),
        "- Iterations: `%d`" % summary["iterations"],
        "- Grid/clearance: `%.3f mm` / `%.3f mm`."
        % (summary["constraint_grid_mm"], summary["keepin_clearance_mm"]),
        "",
        "## Results",
        "",
        "| Target ratio | Run | Runs | Effective lambda | HPWL | Mean mm | P90 mm | Keep-in | Overlaps | Runtime s |",
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
        "--learning-rate-scale",
        format(args.learning_rate_scale, "g"),
        "--gpu" if args.gpu else "--no-gpu",
        (
            "--irregular-density"
            if args.irregular_density
            else "--no-irregular-density"
        ),
        (
            "--footprint-collision"
            if args.footprint_collision
            else "--no-footprint-collision"
        ),
        "--collision-gradient-ratio",
        format(args.collision_gradient_ratio, "g"),
        "--collision-margin-mm",
        format(args.collision_margin_mm, "g"),
        "--collision-tau-mm",
        format(args.collision_tau_mm, "g"),
        (
            "--exact-step-guard"
            if args.exact_step_guard
            else "--no-exact-step-guard"
        ),
        "--exact-step-guard-backoff",
        format(args.exact_step_guard_backoff, "g"),
        "--exact-step-guard-max-retries",
        str(args.exact_step_guard_max_retries),
        (
            "--collision-pair-diagnostics"
            if args.collision_pair_diagnostics
            else "--no-collision-pair-diagnostics"
        ),
        (
            "--exact-contact-projection"
            if args.exact_contact_projection
            else "--no-exact-contact-projection"
        ),
        "--exact-contact-projection-max-iterations",
        str(args.exact_contact_projection_max_iterations),
        "--exact-contact-projection-mode",
        args.exact_contact_projection_mode,
        "--exact-contact-projection-max-nodes",
        str(args.exact_contact_projection_max_nodes),
        "--exact-contact-projection-max-cover-component-nodes",
        str(args.exact_contact_projection_max_cover_component_nodes),
        "--initialization-track",
        args.initialization_track,
        "--checkpoint-placement",
        repo_path(args.checkpoint_placement),
        "--feasible-domain-cache-dir",
        repo_path(args.feasible_domain_cache_dir),
        "--grid-mm",
        format(args.grid_mm, "g"),
        "--clearance-mm",
        format(args.clearance_mm, "g"),
        "--keepin-margin-mm",
        format(args.keepin_margin_mm, "g"),
        "--keepin-margin-tau-mm",
        format(args.keepin_margin_tau_mm, "g"),
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
    if args.exact_contact_policy:
        command.extend(
            ["--exact-contact-policy", args.exact_contact_policy]
        )
    if getattr(args, "n7_arm", None):
        command.extend(["--n7-arm", args.n7_arm])
    if args.exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES:
        command.extend(
            [
                "--exact-contact-projection-max-authority-states",
                str(args.exact_contact_projection_max_authority_states),
            ]
        )
        if (
            args.exact_contact_projection_authority_search_strategy
            != EXHAUSTIVE_AUTHORITY_SEARCH
        ):
            command.extend(
                [
                    "--exact-contact-projection-authority-search-strategy",
                    args.exact_contact_projection_authority_search_strategy,
                ]
            )
        if args.exact_contact_topology_tiebreak:
            command.extend(
                [
                    "--exact-contact-topology-tiebreak",
                    "--exact-contact-topology-min-net-degree",
                    str(args.exact_contact_topology_min_net_degree),
                ]
            )
    if weights:
        command.extend(
            [
                "--anchor-gradient-ratio-sweep",
                *(format(weight, "g") for weight in weights),
            ]
        )
        command.extend(["--sweep-output-dir", repo_path(args.sweep_output_dir)])
    else:
        command.extend(
            [
                "--anchor-gradient-ratio",
                format(args.anchor_gradient_ratio, "g"),
            ]
        )
        command.extend(["--output-dir", repo_path(args.output_dir)])
    visible_devices = shlex.quote(
        os.environ.get("CUDA_VISIBLE_DEVICES") or "<physical-gpu>"
    )
    return (
        "CUBLAS_WORKSPACE_CONFIG=%s CUDA_VISIBLE_DEVICES=%s "
        "PYTHONPATH=\"$PWD/install\" %s"
        % (
            shlex.quote(DEFAULT_CUBLAS_WORKSPACE_CONFIG),
            visible_devices,
            shlex.join(command),
        )
    )


def n7_pair_order(pair_index):
    pair_index = int(pair_index)
    if pair_index < 1 or pair_index > N7_PAIR_COUNT:
        raise ValueError("N7 pair index must be within [1, %d]" % N7_PAIR_COUNT)
    if pair_index % 2:
        return [N7_FEATURE_OFF_ARM, N7_CONSENSUS_ARM]
    return [N7_CONSENSUS_ARM, N7_FEATURE_OFF_ARM]


def _n7_canonical_json(payload):
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _n7_payload_sha256(payload):
    return hashlib.sha256(_n7_canonical_json(payload).encode("utf-8")).hexdigest()


def n7_metric_statistics(control_values, candidate_values):
    controls = [float(value) for value in control_values]
    candidates = [float(value) for value in candidate_values]
    if len(controls) != N7_PAIR_COUNT or len(candidates) != N7_PAIR_COUNT:
        raise ValueError("N7 statistics require exactly five paired values")
    if any(
        not math.isfinite(value) or value <= 0
        for value in (*controls, *candidates)
    ):
        raise ValueError("N7 timing values must be positive and finite")
    ratios = [candidate / control for control, candidate in zip(controls, candidates)]
    deltas = [candidate - control for control, candidate in zip(controls, candidates)]
    median = statistics.median(ratios)
    return {
        "control_seconds": controls,
        "candidate_seconds": candidates,
        "candidate_minus_control_seconds": deltas,
        "ratios": ratios,
        "median": median,
        "minimum": min(ratios),
        "maximum": max(ratios),
        "arithmetic_mean": statistics.mean(ratios),
        "geometric_mean": statistics.geometric_mean(ratios),
        "median_absolute_deviation": statistics.median(
            abs(value - median) for value in ratios
        ),
        "passes_2x": median <= 2.0,
    }


def _n7_normalized_placement_config(config):
    normalized = json.loads(json.dumps(config))
    for field in N7_RUN_LOCAL_CONFIG_FIELDS | N7_CONTACT_CONFIG_FIELDS:
        normalized.pop(field, None)
    return normalized


def _n7_normalized_constraint_config(config):
    normalized = json.loads(json.dumps(config))
    normalized.get("reporting", {}).pop("output_dir", None)
    endpoint_policy = normalized.get("endpoint_policy", {})
    endpoint_policy.pop("manual_placement_file", None)
    endpoint_policy.pop("runtime_placement_file", None)
    return normalized


def _n7_first_difference(left, right, path="config"):
    if type(left) is not type(right):
        return "%s type %s != %s" % (
            path,
            type(left).__name__,
            type(right).__name__,
        )
    if isinstance(left, dict):
        if set(left) != set(right):
            return "%s keys %s != %s" % (
                path,
                sorted(left),
                sorted(right),
            )
        for key in sorted(left):
            difference = _n7_first_difference(
                left[key], right[key], "%s.%s" % (path, key)
            )
            if difference:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return "%s length %d != %d" % (path, len(left), len(right))
        for index, (left_value, right_value) in enumerate(zip(left, right)):
            difference = _n7_first_difference(
                left_value,
                right_value,
                "%s[%d]" % (path, index),
            )
            if difference:
                return difference
        return None
    if left != right:
        return "%s %r != %r" % (path, left, right)
    return None


def validate_n7_config_equivalence(
    control_config,
    candidate_config,
    control_constraint=None,
    candidate_constraint=None,
):
    normalized_control = _n7_normalized_placement_config(control_config)
    normalized_candidate = _n7_normalized_placement_config(candidate_config)
    difference = _n7_first_difference(
        normalized_control, normalized_candidate
    )
    if difference:
        raise RuntimeError(
            "N7 control/candidate config drift outside contact fields: %s"
            % difference
        )
    result = {
        "placement_config_sha256": _n7_payload_sha256(normalized_control),
        "removed_run_local_fields": sorted(N7_RUN_LOCAL_CONFIG_FIELDS),
        "removed_contact_fields": sorted(N7_CONTACT_CONFIG_FIELDS),
    }
    if control_constraint is not None or candidate_constraint is not None:
        if control_constraint is None or candidate_constraint is None:
            raise RuntimeError("N7 constraint config pair is incomplete")
        normalized_control_constraint = _n7_normalized_constraint_config(
            control_constraint
        )
        normalized_candidate_constraint = _n7_normalized_constraint_config(
            candidate_constraint
        )
        difference = _n7_first_difference(
            normalized_control_constraint,
            normalized_candidate_constraint,
            path="constraint",
        )
        if difference:
            raise RuntimeError("N7 constraint config drift: %s" % difference)
        result["constraint_config_sha256"] = _n7_payload_sha256(
            normalized_control_constraint
        )
    return result


def n7_arm_directory(
    root,
    experiment_id,
    arm,
    pair_index=None,
    attempt_index=1,
    warmup=False,
):
    root = Path(root)
    if experiment_id not in N7_EXPERIMENTS:
        raise ValueError("N7 supports only E2 and E3")
    if arm not in N7_ARMS:
        raise ValueError("unknown N7 arm: %s" % arm)
    if warmup:
        if pair_index is not None:
            raise ValueError("N7 warm-up paths do not have a pair index")
        attempt_index = int(attempt_index)
        if attempt_index not in (1, 2):
            raise ValueError("N7 permits at most one replacement attempt")
        return (
            root
            / "warmup"
            / experiment_id
            / ("attempt_%02d" % attempt_index)
            / arm
        )
    pair_index = int(pair_index)
    attempt_index = int(attempt_index)
    if pair_index < 1 or pair_index > N7_PAIR_COUNT:
        raise ValueError("invalid N7 pair index")
    if attempt_index not in (1, 2):
        raise ValueError("N7 permits at most one replacement attempt")
    return (
        root
        / experiment_id
        / ("pair_%02d" % pair_index)
        / ("attempt_%02d" % attempt_index)
        / arm
    )


def _n7_utc_now():
    return datetime.now(timezone.utc).isoformat()


def _n7_pid_is_descendant(pid, ancestor_pid):
    try:
        pid = int(pid)
        ancestor_pid = int(ancestor_pid)
    except (TypeError, ValueError):
        return False
    visited = set()
    while pid > 1 and pid not in visited:
        if pid == ancestor_pid:
            return True
        visited.add(pid)
        status_path = Path("/proc") / str(pid) / "status"
        try:
            status = status_path.read_text()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            return False
        match = re.search(r"^PPid:\s+(\d+)$", status, flags=re.MULTILINE)
        if not match:
            return False
        pid = int(match.group(1))
    return pid == ancestor_pid


def _n7_nvidia_cuda_version():
    output = subprocess.check_output(
        ["nvidia-smi", "--query"], text=True, timeout=10
    )
    match = re.search(r"^CUDA Version\s*:\s*(.+)$", output, re.MULTILINE)
    return match.group(1).strip() if match else None


def n7_gpu_snapshot(physical_index, owner_pid=None):
    physical_index = int(physical_index)
    owner_pid = os.getpid() if owner_pid is None else int(owner_pid)
    query_fields = (
        "index",
        "uuid",
        "name",
        "driver_version",
        "temperature.gpu",
        "pstate",
        "clocks.current.sm",
        "clocks.current.memory",
        "power.draw",
        "memory.used",
        "memory.total",
        "utilization.gpu",
        "utilization.memory",
    )
    output = subprocess.check_output(
        [
            "nvidia-smi",
            "--id=%d" % physical_index,
            "--query-gpu=%s" % ",".join(query_fields),
            "--format=csv,noheader,nounits",
        ],
        text=True,
        timeout=10,
    ).strip()
    rows = list(csv.reader([output], skipinitialspace=True))
    if len(rows) != 1 or len(rows[0]) != len(query_fields):
        raise RuntimeError("unexpected nvidia-smi GPU query output: %r" % output)
    values = dict(zip(query_fields, rows[0]))
    process_output = subprocess.check_output(
        [
            "nvidia-smi",
            "--id=%d" % physical_index,
            "--query-compute-apps=pid,process_name,used_gpu_memory,gpu_uuid",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        timeout=10,
    ).strip()
    processes = []
    if process_output:
        for row in csv.reader(process_output.splitlines(), skipinitialspace=True):
            if len(row) != 4:
                raise RuntimeError(
                    "unexpected nvidia-smi process query output: %r" % row
                )
            pid = int(row[0])
            processes.append(
                {
                    "pid": pid,
                    "process_name": row[1],
                    "used_gpu_memory_mib": float(row[2]),
                    "gpu_uuid": row[3],
                    "owned_by_campaign": _n7_pid_is_descendant(
                        pid, owner_pid
                    ),
                }
            )
    return {
        "timestamp_utc": _n7_utc_now(),
        "physical_index": int(values["index"]),
        "uuid": values["uuid"],
        "name": values["name"],
        "driver_version": values["driver_version"],
        "temperature_c": float(values["temperature.gpu"]),
        "pstate": values["pstate"],
        "sm_clock_mhz": float(values["clocks.current.sm"]),
        "memory_clock_mhz": float(values["clocks.current.memory"]),
        "power_draw_w": float(values["power.draw"]),
        "memory_used_mib": float(values["memory.used"]),
        "memory_total_mib": float(values["memory.total"]),
        "gpu_utilization_percent": float(values["utilization.gpu"]),
        "memory_utilization_percent": float(values["utilization.memory"]),
        "active_compute_processes": processes,
        "foreign_compute_processes": [
            process for process in processes if not process["owned_by_campaign"]
        ],
    }


def n7_environment_invalid_reasons(
    snapshots,
    expected_physical_index,
    expected_uuid,
    expected_driver_version=None,
):
    reasons = []
    foreign = {}
    for snapshot in snapshots:
        if snapshot["physical_index"] != int(expected_physical_index):
            reasons.append(
                "physical_gpu_index_changed:%s"
                % snapshot["physical_index"]
            )
        if snapshot["uuid"] != expected_uuid:
            reasons.append("gpu_uuid_changed:%s" % snapshot["uuid"])
        if (
            expected_driver_version is not None
            and snapshot["driver_version"] != expected_driver_version
        ):
            reasons.append(
                "driver_version_changed:%s" % snapshot["driver_version"]
            )
        for process in snapshot.get("foreign_compute_processes", []):
            foreign[(process["pid"], process["process_name"])] = process
    for pid, process_name in sorted(foreign):
        reasons.append("foreign_compute_process:%d:%s" % (pid, process_name))
    return sorted(set(reasons))


def _n7_require_close(label, actual, expected, tolerance=1e-12):
    if not math.isclose(
        float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance
    ):
        raise ValueError(
            "N7 frozen %s drifted: %r != %r" % (label, actual, expected)
        )


def validate_n7_frozen_arguments(args, child_arm=None):
    expected_experiments = (
        list(N7_EXPERIMENTS) if child_arm is None else [args.experiments[0]]
    )
    if list(args.experiments) != expected_experiments:
        raise ValueError(
            "N7 experiments must be %s" % " ".join(expected_experiments)
        )
    if child_arm is not None and args.experiments[0] not in N7_EXPERIMENTS:
        raise ValueError("N7 child supports only E2 or E3")
    if list(args.seeds) != [N7_SEED]:
        raise ValueError("N7 seed must remain 1000")
    if int(args.n7_physical_gpu_index) != N7_PHYSICAL_GPU_INDEX:
        raise ValueError("N7 must remain on physical GPU 2")
    if int(args.iterations) != N7_ITERATIONS:
        raise ValueError("N7 iteration count must remain 50")
    _n7_require_close("learning-rate scale", args.learning_rate_scale, 1.0)
    _n7_require_close("anchor gradient ratio", args.anchor_gradient_ratio, 0.1)
    _n7_require_close(
        "collision gradient ratio", args.collision_gradient_ratio, 0.1
    )
    _n7_require_close("collision margin", args.collision_margin_mm, 0.0)
    _n7_require_close("collision tau", args.collision_tau_mm, 0.025)
    _n7_require_close("guard backoff", args.exact_step_guard_backoff, 0.5)
    if int(args.exact_step_guard_max_retries) != 4:
        raise ValueError("N7 guard retries must remain four")
    if int(args.exact_contact_projection_max_iterations) != 8:
        raise ValueError("N7 contact iterations must remain eight")
    if int(args.exact_contact_projection_max_nodes) != 32:
        raise ValueError("N7 corrected-node limit must remain 32")
    if int(args.exact_contact_projection_max_cover_component_nodes) != 16:
        raise ValueError("N7 component-node limit must remain 16")
    _n7_require_close("constraint grid", args.grid_mm, 0.05)
    _n7_require_close("clearance", args.clearance_mm, 0.0)
    _n7_require_close("Keep-in margin", args.keepin_margin_mm, 0.1)
    _n7_require_close("Keep-in margin tau", args.keepin_margin_tau_mm, 0.05)
    _n7_require_close("site size", args.site_mm, 0.05)
    if not args.gpu or not args.irregular_density:
        raise ValueError("N7 requires GPU and irregular density")
    if args.initialization_track != "checkpoint_warm_start":
        raise ValueError("N7 requires checkpoint_warm_start")
    if Path(args.checkpoint_placement).resolve() != DEFAULT_M336_CHECKPOINT_PL.resolve():
        raise ValueError("N7 checkpoint placement drifted")
    if Path(args.assignment).resolve() != DEFAULT_M336_ASSIGNMENT.resolve():
        raise ValueError("N7 assignment drifted")
    if not Path(args.python).resolve().is_file():
        raise ValueError("N7 requires an explicit existing Python executable")
    if args.anchor_gradient_ratio_sweep:
        raise ValueError("N7 prohibits anchor-ratio sweeps")
    if args.resume or args.reevaluate:
        raise ValueError("N7 prohibits resume and reevaluation")
    if args.collision_pair_diagnostics:
        raise ValueError("N7 pair diagnostics must remain disabled")
    if child_arm is None or child_arm == N7_CONSENSUS_ARM:
        if not (
            args.footprint_collision
            and args.exact_step_guard
            and args.exact_contact_projection
        ):
            raise ValueError("N7 consensus contact stack is incomplete")
        if args.exact_contact_policy != N7_CONSENSUS_ARM:
            raise ValueError("N7 candidate policy must be consensus_per_step")
        if args.exact_contact_projection_mode != "component_consensus":
            raise ValueError("N7 candidate contact mode drifted")
        if args.exact_contact_topology_tiebreak:
            raise ValueError("N7 topology tie-break must remain disabled")
    elif child_arm == N7_FEATURE_OFF_ARM:
        if (
            args.footprint_collision
            or args.exact_step_guard
            or args.exact_contact_projection
        ):
            raise ValueError("N7 feature-off contact stack must be disabled")
        if args.exact_contact_policy:
            raise ValueError("N7 feature-off control cannot name a policy")
    else:
        raise ValueError("unknown N7 child arm: %s" % child_arm)


def validate_n7_arm_config(config, experiment_id, arm):
    if experiment_id not in N7_EXPERIMENTS or arm not in N7_ARMS:
        raise RuntimeError("invalid N7 experiment or arm")
    stage = config["global_place_stages"]
    if len(stage) != 1:
        raise RuntimeError("N7 requires exactly one native GP stage")
    stage = stage[0]
    expected_common = {
        "iteration": N7_ITERATIONS,
        "learning_rate": DEFAULT_M336_LEARNING_RATE,
        "optimizer": "adam",
        "wirelength": "weighted_average",
    }
    for field, expected in expected_common.items():
        actual = stage.get(field)
        if actual != expected:
            raise RuntimeError(
                "N7 stage field %s drifted: %r != %r"
                % (field, actual, expected)
            )
    common = {
        "gpu": 1,
        "gpu_id": 0,
        "target_density": DEFAULT_M336_TARGET_DENSITY,
        "random_seed": N7_SEED,
        "dtype": "float32",
        "deterministic_flag": 1,
        "irregular_density_flag": True,
        "keepin_projection_flag": True,
        "constraint_grid_mm": 0.05,
        "keepin_clearance_mm": 0.0,
        "keepin_margin_mm": 0.1,
        "keepin_margin_tau_mm": 0.05,
        "initialization_track": "checkpoint_warm_start",
        "initial_placement_role": "m336_118_checkpoint",
        "exact_repair_flag": False,
        "legalize_flag": 0,
        "detailed_place_flag": 0,
        "collision_pair_diagnostics_flag": False,
    }
    for field, expected in common.items():
        if config.get(field) != expected:
            raise RuntimeError(
                "N7 config field %s drifted: %r != %r"
                % (field, config.get(field), expected)
            )
    if Path(config["initial_placement_file"]).resolve() != DEFAULT_M336_CHECKPOINT_PL.resolve():
        raise RuntimeError("N7 config checkpoint path drifted")
    if bool(config.get("anchor_loss_flag")) != (experiment_id == "E3"):
        raise RuntimeError("N7 E2/E3 anchor contract drifted")
    if arm == N7_FEATURE_OFF_ARM:
        for field in (
            "footprint_collision_loss_flag",
            "exact_step_guard_flag",
            "exact_contact_projection_flag",
        ):
            if config.get(field):
                raise RuntimeError("N7 feature-off field enabled: %s" % field)
        if config.get("exact_contact_policy"):
            raise RuntimeError("N7 feature-off config names a contact policy")
    else:
        candidate = {
            "footprint_collision_loss_flag": True,
            "collision_gradient_ratio": 0.1,
            "collision_margin_mm": 0.0,
            "collision_tau_mm": 0.025,
            "exact_step_guard_flag": True,
            "exact_step_guard_backoff": 0.5,
            "exact_step_guard_max_retries": 4,
            "exact_contact_projection_flag": True,
            "exact_contact_policy": N7_CONSENSUS_ARM,
            "exact_contact_projection_mode": "component_consensus",
            "exact_contact_projection_max_iterations": 8,
            "exact_contact_projection_max_nodes": 32,
            "exact_contact_projection_max_cover_component_nodes": 16,
        }
        for field, expected in candidate.items():
            if config.get(field) != expected:
                raise RuntimeError(
                    "N7 candidate field %s drifted: %r != %r"
                    % (field, config.get(field), expected)
                )
        forbidden = (
            "exact_contact_projection_authority_search_strategy",
            "exact_contact_topology_tiebreak_flag",
        )
        if any(config.get(field) for field in forbidden):
            raise RuntimeError("N7 candidate enabled authority/topology work")


def validate_n7_constraint_config(config):
    if Path(config["region_assignment_file"]).resolve() != (
        DEFAULT_M336_ASSIGNMENT.resolve()
    ):
        raise RuntimeError("N7 constraint assignment drifted")
    if Path(config["geometry_file"]).resolve() != (
        REPO_ROOT / "experiments/m336/input/pcb_geometry_keepin.json"
    ).resolve():
        raise RuntimeError("N7 constraint geometry drifted")
    endpoint = config["endpoint_policy"]
    if (
        endpoint.get("default") != "runtime"
        or endpoint.get("manual_endpoints") != ["EMI601"]
        or endpoint.get("runtime_endpoints") != ["Q601"]
    ):
        raise RuntimeError("N7 constraint endpoint policy drifted")
    geometry = config["geometry"]
    expected_geometry = {
        "constraint_grid_mm": 0.05,
        "clearance_mm": 0.0,
        "keepin_margin_mm": 0.1,
        "keepin_margin_tau_mm": 0.05,
        "no_board_bbox_fallback": True,
    }
    for field, expected in expected_geometry.items():
        if geometry.get(field) != expected:
            raise RuntimeError("N7 constraint geometry field drifted: %s" % field)
    if config["feature_flags"].get("enable_exact_repair"):
        raise RuntimeError("N7 constraint enabled repair")
    if config["reporting"].get("area_epsilon_mm2") != 1e-5:
        raise RuntimeError("N7 exact legality epsilon drifted")


def n7_canonical_input_identity(input_sha256):
    bookshelf_names = {
        "m336.aux",
        "m336.nodes",
        "m336.nets",
        "m336.pl",
        "m336.baseline.aux",
        "m336.baseline.pl",
        "m336.scl",
    }
    canonical = {}
    for path, digest in sorted(input_sha256.items()):
        name = Path(path).name
        if name in N7_RUN_LOCAL_INPUT_METADATA:
            continue
        key = "bookshelf/%s" % name if name in bookshelf_names else path
        if key in canonical and canonical[key] != digest:
            raise RuntimeError("N7 canonical input key collision: %s" % key)
        canonical[key] = digest
    return canonical


def validate_n7_provenance(reference, result):
    source = result["source_state"]
    expected_source = reference["source_state"]
    for field in (
        "branch",
        "git_sha",
        "tracked_diff_sha256",
        "dirty_paths",
        "implementation_sha256",
        "source_install_mismatches",
    ):
        if source.get(field) != expected_source.get(field):
            raise RuntimeError("N7 source/install drift: %s" % field)
    actual_raw_input = result["input_sha256"]
    for path, digest in reference.get("static_input_sha256", {}).items():
        if actual_raw_input.get(path) != digest:
            raise RuntimeError("N7 static input hash drift: %s" % path)
    actual_input = n7_canonical_input_identity(actual_raw_input)
    expected_input = reference.get("input_sha256")
    if expected_input is None:
        reference["input_sha256"] = actual_input
    elif actual_input != expected_input:
        difference = _n7_first_difference(
            expected_input, actual_input, path="input_sha256"
        )
        raise RuntimeError("N7 input hash drift: %s" % difference)


def _n7_effective_step_size(attempt):
    step_size = attempt.get("step_size")
    if isinstance(step_size, dict):
        step_size = step_size.get("effective_step_size")
    return None if step_size is None else float(step_size)


def n7_attempt_sequence(native_execution):
    sequence = []
    for attempt in native_execution.get("exact_step_guard_attempts", []):
        contact = attempt.get("contact_projection") or {}
        rollback = attempt.get("rollback") or {}
        sequence.append(
            {
                "iteration": int(attempt["iteration"]),
                "retry_index": int(attempt["retry_index"]),
                "accepted": bool(attempt["accepted"]),
                "reason": str(attempt.get("reason", "")),
                "contact_reason": str(contact.get("reason", "")),
                "effective_step_size": _n7_effective_step_size(attempt),
                "position_restored": rollback.get("position_restored"),
                "optimizer_restored": rollback.get("optimizer_restored"),
            }
        )
    return sequence


def _n7_final_learning_rate(result):
    native = result["metrics"]["native_execution"]
    accepted = [
        attempt
        for attempt in native.get("exact_step_guard_attempts", [])
        if attempt.get("accepted")
    ]
    if accepted:
        return _n7_effective_step_size(accepted[-1])
    steps = native.get("optimizer_steps", [])
    return float(steps[-1]["learning_rate"]) if steps else None


def n7_result_identity(result, include_guard):
    score = result["serialized_native_score"]
    native = result["metrics"]["native_execution"]
    identity = {
        "input_placement_sha256": score["input_placement_sha256"],
        "replayed_placement_sha256": score["replayed_placement_sha256"],
        "hpwl": float(score["hpwl"]),
        "rsmt": float(score["rsmt"]),
        "normalized_quality_score": float(
            result["manual_baseline_comparison"]["normalized_quality_score"]
        ),
        "anchor_distance_mm": result["metrics"]["anchor_distance_mm"],
        "projected_anchor_distance_mm": result["metrics"][
            "projected_anchor_distance_mm"
        ],
        "legality": result["legality"],
        "optimizer_step_count": int(native["optimizer_step_count"]),
        "optimizer_changed_step_count": int(
            native["optimizer_changed_step_count"]
        ),
        "final_effective_learning_rate": _n7_final_learning_rate(result),
    }
    if include_guard:
        sequence = n7_attempt_sequence(native)
        identity.update(
            {
                "attempt_sequence": sequence,
                "attempt_sequence_sha256": _n7_payload_sha256(sequence),
            }
        )
    return identity


def _n7_require_zero_checkpoint_legality(native):
    checkpoints = native.get("exact_overlap_checkpoints", [])
    if len(checkpoints) != N7_ITERATIONS + 1:
        raise RuntimeError(
            "N7 candidate requires 51 exact accepted checkpoints; found %d"
            % len(checkpoints)
        )
    for checkpoint in checkpoints:
        if (
            int(checkpoint["overlap_pair_count"]) != 0
            or float(checkpoint["overlap_area_mm2"]) != 0.0
            or int(checkpoint["keepin_violation_count"]) != 0
        ):
            raise RuntimeError(
                "N7 candidate accepted an illegal checkpoint: %s"
                % checkpoint
            )


def validate_n7_result(result, experiment_id, arm):
    if result.get("experiment_id") != experiment_id:
        raise RuntimeError("N7 child experiment identity drifted")
    if result.get("seed") != N7_SEED:
        raise RuntimeError("N7 child seed drifted")
    if result.get("initialization_track") != "checkpoint_warm_start":
        raise RuntimeError("N7 child initialization track drifted")
    validate_n7_arm_config(result["config"], experiment_id, arm)
    native = result["metrics"].get("native_execution")
    if native is None:
        raise RuntimeError("N7 child lacks native execution evidence")
    required_native = {
        "nonlinear_place_executed": True,
        "place_obj_executed": True,
        "backward_call_count": 53,
        "optimizer_step_count": N7_ITERATIONS,
        "optimizer_changed_step_count": N7_ITERATIONS,
        "optimizer_names": ["adam"],
    }
    for field, expected in required_native.items():
        if native.get(field) != expected:
            raise RuntimeError(
                "N7 native evidence %s drifted: %r != %r"
                % (field, native.get(field), expected)
            )
    score = result["serialized_native_score"]
    if (
        not math.isfinite(float(score["hpwl"]))
        or not math.isfinite(float(score["rsmt"]))
        or float(score["coordinate_replay_max_error"]) != 0.0
        or score["input_placement_sha256"]
        != score["replayed_placement_sha256"]
    ):
        raise RuntimeError("N7 native score or float64 replay is invalid")
    legality = result["legality"]
    if (
        float(legality["area_epsilon_mm2"]) != 1e-5
        or
        int(legality["constrained_components"]) != 100
        or int(legality["fully_contained_components"]) != 100
        or int(legality["keepin_violation_count"]) != 0
    ):
        raise RuntimeError("N7 final containment/Keep-in contract failed")
    if (
        result.get("repair") is not None
        or "repair" in result.get("artifacts", {})
        or float(result.get("timing", {}).get("bounded_repair_seconds", 0.0))
        != 0.0
    ):
        raise RuntimeError("N7 run used prohibited repair")
    endpoint = result.get("preflight", {}).get("endpoint_policy", {})
    if (
        endpoint.get("default") != "runtime"
        or endpoint.get("manual_endpoints") != ["EMI601"]
        or endpoint.get("runtime_endpoints") != ["Q601"]
    ):
        raise RuntimeError("N7 endpoint policy drifted")
    if arm == N7_FEATURE_OFF_ARM:
        if (
            result.get("footprint_collision_enabled")
            or result.get("exact_step_guard_enabled")
            or result.get("exact_contact_projection_enabled")
            or result.get("exact_contact_policy")
        ):
            raise RuntimeError("N7 feature-off result enabled contact work")
    else:
        if (
            not result.get("footprint_collision_enabled")
            or not result.get("exact_step_guard_enabled")
            or not result.get("exact_contact_projection_enabled")
            or result.get("exact_contact_policy") != N7_CONSENSUS_ARM
        ):
            raise RuntimeError("N7 candidate result lacks production policy")
        if (
            int(native.get("exact_step_guard_accepted_step_count", -1))
            != N7_ITERATIONS
        ):
            raise RuntimeError("N7 candidate did not accept 50 legal steps")
        _n7_require_zero_checkpoint_legality(native)
        if (
            int(legality["overlap_pair_count"]) != 0
            or float(legality["overlap_area_mm2"]) != 0.0
        ):
            raise RuntimeError("N7 candidate final overlap is nonzero")
        for attempt in native.get("exact_step_guard_attempts", []):
            contact = attempt.get("contact_projection") or {}
            if int(contact.get("cover_search_state_count", 0)) != 0:
                raise RuntimeError("N7 candidate enumerated authority states")
            if not attempt.get("accepted"):
                rollback = attempt.get("rollback") or {}
                if not (
                    rollback.get("position_restored")
                    and rollback.get("optimizer_restored")
                ):
                    raise RuntimeError("N7 candidate rollback was incomplete")
    identity = n7_result_identity(
        result, include_guard=(arm == N7_CONSENSUS_ARM)
    )
    return {
        "identity": identity,
        "identity_sha256": _n7_payload_sha256(identity),
        "timing": n7_timing_record(result["timing"]),
        "correctness": {
            "backward_call_count": int(native["backward_call_count"]),
            "optimizer_step_count": int(native["optimizer_step_count"]),
            "optimizer_changed_step_count": int(
                native["optimizer_changed_step_count"]
            ),
            "guard_accepted_step_count": int(
                native.get("exact_step_guard_accepted_step_count", 0)
            ),
            "guard_rejected_attempt_count": int(
                native.get("exact_step_guard_rejected_attempt_count", 0)
            ),
            "rollback_count": sum(
                1
                for attempt in native.get("exact_step_guard_attempts", [])
                if not attempt.get("accepted")
                and (attempt.get("rollback") or {}).get("position_restored")
                and (attempt.get("rollback") or {}).get("optimizer_restored")
            ),
            "accepted_checkpoint_count": len(
                native.get("exact_overlap_checkpoints", [])
            ),
        },
        "gpu_optimization_seconds": float(
            result["timing"]["gpu_optimization_seconds"]
        ),
        "end_to_end_seconds": float(result["timing"]["end_to_end_seconds"]),
    }


def n7_timing_record(timing):
    missing = [field for field in N7_REPORTED_TIMING_FIELDS if field not in timing]
    if missing:
        raise RuntimeError("N7 timing fields are missing: %s" % missing)
    record = {
        field: float(timing[field]) for field in N7_REPORTED_TIMING_FIELDS
    }
    if any(not math.isfinite(value) or value < 0 for value in record.values()):
        raise RuntimeError("N7 timing buckets must be finite and non-negative")
    expected_gpu = max(
        record["optimization_wall_seconds"]
        - record["exact_step_guard_seconds"]
        - record["exact_overlap_diagnostic_seconds"],
        0.0,
    )
    if not math.isclose(
        record["gpu_optimization_seconds"],
        expected_gpu,
        rel_tol=0.0,
        abs_tol=max(1e-9, record["optimization_wall_seconds"] * 1e-9),
    ):
        raise RuntimeError("N7 GPU timing-boundary identity changed")
    return record


def validate_n7_determinism(reference_identity, candidate_identity, label):
    if reference_identity is None:
        return json.loads(json.dumps(candidate_identity))
    difference = _n7_first_difference(
        reference_identity, candidate_identity, path=label
    )
    if difference:
        raise RuntimeError("N7 deterministic output divergence: %s" % difference)
    return reference_identity


def n7_directory_manifest(path):
    path = Path(path)
    rows = []
    if path.exists():
        for file_path in sorted(
            (candidate for candidate in path.rglob("*") if candidate.is_file()),
            key=lambda candidate: str(candidate.relative_to(path)),
        ):
            rows.append(
                {
                    "path": str(file_path.relative_to(path)),
                    "sha256": sha256_file(file_path),
                    "size": file_path.stat().st_size,
                }
            )
    return {
        "path": repo_path(path),
        "file_count": len(rows),
        "files": rows,
        "manifest_sha256": _n7_payload_sha256(rows),
    }


def n7_arm_command(args, experiment_id, arm, arm_dir):
    arm_dir = Path(arm_dir).resolve()
    command = [
        str(Path(args.python).resolve()),
        str(Path(__file__).resolve()),
        "--experiments",
        experiment_id,
        "--seeds",
        str(N7_SEED),
        "--iterations",
        str(N7_ITERATIONS),
        "--learning-rate-scale",
        "1",
        "--gpu",
        "--irregular-density",
        "--collision-gradient-ratio",
        "0.1",
        "--collision-margin-mm",
        "0",
        "--collision-tau-mm",
        "0.025",
        "--exact-step-guard-backoff",
        "0.5",
        "--exact-step-guard-max-retries",
        "4",
        "--no-collision-pair-diagnostics",
        "--exact-contact-projection-max-iterations",
        "8",
        "--exact-contact-projection-max-nodes",
        "32",
        "--exact-contact-projection-max-cover-component-nodes",
        "16",
        "--initialization-track",
        "checkpoint_warm_start",
        "--checkpoint-placement",
        str(Path(args.checkpoint_placement).resolve()),
        "--feasible-domain-cache-dir",
        str(Path(args.feasible_domain_cache_dir).resolve()),
        "--python",
        str(Path(args.python).resolve()),
        "--placer",
        str(Path(args.placer).resolve()),
        "--assignment",
        str(Path(args.assignment).resolve()),
        "--baseline-geometry",
        str(Path(args.baseline_geometry).resolve()),
        "--bookshelf-dir",
        str((arm_dir / "input" / "bookshelf").resolve()),
        "--baseline-output-dir",
        str((arm_dir / "manual-baseline").resolve()),
        "--anchor-gradient-ratio",
        "0.1",
        "--grid-mm",
        "0.05",
        "--clearance-mm",
        "0",
        "--keepin-margin-mm",
        "0.1",
        "--keepin-margin-tau-mm",
        "0.05",
        "--site-mm",
        "0.05",
        "--validation-path",
        str((arm_dir / "validation.json").resolve()),
        "--output-dir",
        str(arm_dir),
        "--summary-path",
        str((arm_dir / "summary.json").resolve()),
        "--report-path",
        str((arm_dir / "REPORT.md").resolve()),
        "--n7-arm",
        arm,
        "--n7-physical-gpu-index",
        str(args.n7_physical_gpu_index),
    ]
    if arm == N7_FEATURE_OFF_ARM:
        command.extend(
            [
                "--no-footprint-collision",
                "--no-exact-step-guard",
                "--no-exact-contact-projection",
            ]
        )
    elif arm == N7_CONSENSUS_ARM:
        command.extend(
            [
                "--footprint-collision",
                "--exact-step-guard",
                "--exact-contact-projection",
                "--exact-contact-policy",
                N7_CONSENSUS_ARM,
            ]
        )
    else:
        raise ValueError("unknown N7 arm: %s" % arm)
    return command


def _n7_monitored_subprocess(command, output_path, physical_gpu_index):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    environment = _native_subprocess_environment(
        overrides={
            "CUDA_VISIBLE_DEVICES": str(physical_gpu_index),
            "PYTHONPATH": "%s:%s"
            % (REPO_ROOT / "install", REPO_ROOT),
            "PYTHONFAULTHANDLER": "1",
        }
    )
    started_utc = _n7_utc_now()
    started = time.perf_counter()
    samples = []
    sampling_errors = []
    with output_path.open("w") as output:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=environment,
            text=True,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        while process.poll() is None:
            try:
                samples.append(
                    n7_gpu_snapshot(
                        physical_gpu_index, owner_pid=os.getpid()
                    )
                )
            except Exception as error:
                sampling_errors.append(
                    "%s:%s" % (type(error).__name__, error)
                )
            time.sleep(N7_SAMPLE_INTERVAL_SECONDS)
        returncode = process.wait()
    elapsed = time.perf_counter() - started
    try:
        samples.append(
            n7_gpu_snapshot(physical_gpu_index, owner_pid=os.getpid())
        )
    except Exception as error:
        sampling_errors.append("%s:%s" % (type(error).__name__, error))
    return {
        "command": command,
        "command_shell": shlex.join(command),
        "started_utc": started_utc,
        "finished_utc": _n7_utc_now(),
        "elapsed_seconds": elapsed,
        "returncode": returncode,
        "gpu_samples": samples,
        "gpu_sampling_errors": sampling_errors,
        "process_log": repo_path(output_path),
    }


class N7EnvironmentalError(RuntimeError):
    """An objective environment failure that may use one replacement."""


class N7CorrectnessError(RuntimeError):
    """A frozen-contract, legality, or determinism failure."""


def n7_invalid_attempt_action(attempt_index):
    attempt_index = int(attempt_index)
    if attempt_index == 1:
        return "replace"
    if attempt_index == 2:
        return "stop_incomplete"
    raise ValueError("N7 permits exactly one replacement attempt")


def n7_preserved_paths_state():
    state = {}
    for path in N7_PRESERVED_PATHS:
        if path.is_file():
            state[repo_path(path)] = {
                "kind": "file",
                "exists": True,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        elif path.is_dir():
            state[repo_path(path)] = {
                "kind": "directory",
                "exists": True,
                **n7_directory_manifest(path),
            }
        else:
            state[repo_path(path)] = {
                "kind": "missing",
                "exists": False,
            }
    return state


def n7_repository_snapshot():
    return {
        "timestamp_utc": _n7_utc_now(),
        "status_short": subprocess.check_output(
            ["git", "status", "--short"], cwd=REPO_ROOT, text=True
        ).splitlines(),
        "branch": git_branch(),
        "head": git_sha(),
        "log_10": subprocess.check_output(
            ["git", "log", "-10", "--oneline"],
            cwd=REPO_ROOT,
            text=True,
        ).splitlines(),
        "diff_check": subprocess.run(
            ["git", "diff", "--check"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).stdout.splitlines(),
    }


def n7_static_input_hashes(args):
    return hash_paths(
        (
            REPO_ROOT / "experiments/m336/input/pcb_geometry_keepin.json",
            REPO_ROOT / "experiments/m336/input/m336_clusters.json",
            args.baseline_geometry,
            args.checkpoint_placement,
            args.assignment,
        )
    )


def _n7_attempt_directory(
    root, experiment_id, attempt_index, pair_index=None, warmup=False
):
    return n7_arm_directory(
        root,
        experiment_id,
        N7_FEATURE_OFF_ARM,
        pair_index=pair_index,
        attempt_index=attempt_index,
        warmup=warmup,
    ).parent


def _n7_require_fresh_path(path, label):
    path = Path(path)
    if path.exists():
        raise N7CorrectnessError(
            "N7 %s path is not fresh: %s" % (label, path)
        )


def _n7_load_child_result(arm_dir):
    summary_path = Path(arm_dir) / "summary.json"
    report_path = Path(arm_dir) / "REPORT.md"
    if not summary_path.is_file() or not report_path.is_file():
        raise N7EnvironmentalError(
            "required child summary/report artifacts are absent: %s"
            % arm_dir
        )
    try:
        summary = json.loads(summary_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise N7EnvironmentalError(
            "cannot read child summary %s: %s" % (summary_path, error)
        ) from error
    if len(summary.get("runs", [])) != 1:
        raise N7EnvironmentalError(
            "child summary must contain exactly one run: %s" % summary_path
        )
    return summary, summary["runs"][0], summary_path, report_path


def _n7_require_arm_artifact_isolation(
    arm_dir, summary_path, report_path, result
):
    arm_dir = Path(arm_dir).resolve()
    expected_paths = {
        "summary": arm_dir / "summary.json",
        "report": arm_dir / "REPORT.md",
    }
    actual_paths = {
        "summary": Path(summary_path).resolve(),
        "report": Path(report_path).resolve(),
    }
    if actual_paths != expected_paths:
        raise N7CorrectnessError("N7 summary/report path isolation failed")
    config = result["config"]
    for field in N7_RUN_LOCAL_CONFIG_FIELDS:
        value = config.get(field)
        if value is None:
            continue
        try:
            Path(value).resolve().relative_to(arm_dir)
        except ValueError as error:
            raise N7CorrectnessError(
                "N7 run-local config path escaped its arm: %s=%s"
                % (field, value)
            ) from error


def _n7_execute_arm(
    args,
    reference,
    experiment_id,
    arm,
    attempt_dir,
    pair_index=None,
    attempt_index=1,
    warmup=False,
):
    arm_dir = n7_arm_directory(
        args.output_dir,
        experiment_id,
        arm,
        pair_index=pair_index,
        attempt_index=attempt_index,
        warmup=warmup,
    )
    _n7_require_fresh_path(arm_dir, "arm output")
    command = n7_arm_command(args, experiment_id, arm, arm_dir)
    if "--resume" in command or "--reevaluate" in command:
        raise N7CorrectnessError("N7 child command enabled result reuse")
    execution = _n7_monitored_subprocess(
        command,
        Path(attempt_dir) / ("%s-runner.log" % arm),
        args.n7_physical_gpu_index,
    )
    write_json(Path(attempt_dir) / ("%s-execution.json" % arm), execution)
    if execution["gpu_sampling_errors"]:
        raise N7EnvironmentalError(
            "N7 GPU monitoring failed: %s"
            % execution["gpu_sampling_errors"]
        )
    if execution["returncode"] != 0:
        raise N7EnvironmentalError(
            "N7 child exited with code %d: %s"
            % (execution["returncode"], execution["process_log"])
        )
    summary, result, summary_path, report_path = _n7_load_child_result(
        arm_dir
    )
    if summary.get("n7_arm") != arm:
        raise N7CorrectnessError("N7 child arm identity is absent or wrong")
    try:
        validate_n7_provenance(reference, result)
    except RuntimeError as error:
        raise N7EnvironmentalError(str(error)) from error
    try:
        validation = validate_n7_result(result, experiment_id, arm)
        _n7_require_arm_artifact_isolation(
            arm_dir, summary_path, report_path, result
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        if isinstance(error, N7CorrectnessError):
            raise
        raise N7CorrectnessError(str(error)) from error
    constraint_path = Path(result["config"]["anchor_keepin_config"])
    if not constraint_path.is_file():
        raise N7EnvironmentalError(
            "N7 child constraint artifact is absent: %s" % constraint_path
        )
    constraint = json.loads(constraint_path.read_text())
    try:
        validate_n7_constraint_config(constraint)
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        raise N7CorrectnessError(str(error)) from error
    record = {
        "arm": arm,
        "output_dir": repo_path(arm_dir),
        "summary_path": repo_path(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "report_path": repo_path(report_path),
        "report_sha256": sha256_file(report_path),
        "run_result_path": repo_path(
            Path(result["config"]["result_dir"]) / "run-result.json"
        ),
        "command": execution["command"],
        "command_shell": execution["command_shell"],
        "started_utc": execution["started_utc"],
        "finished_utc": execution["finished_utc"],
        "runner_elapsed_seconds": execution["elapsed_seconds"],
        "runner_returncode": execution["returncode"],
        "gpu_samples": execution["gpu_samples"],
        "process_log": execution["process_log"],
        "input_sha256": result["input_sha256"],
        "canonical_input_sha256": n7_canonical_input_identity(
            result["input_sha256"]
        ),
        **validation,
    }
    return {
        "record": record,
        "config": result["config"],
        "constraint": constraint,
        "result": result,
    }


def _n7_source_drift_reason(reference_source):
    current = source_state()
    difference = _n7_first_difference(
        reference_source, current, path="source_state"
    )
    return None if difference is None else "source_or_install_drift:%s" % difference


def _n7_cache_drift_reason(reference_cache):
    current = n7_directory_manifest(reference_cache["path"])
    if current["manifest_sha256"] == reference_cache["manifest_sha256"]:
        return None
    return "feasible_domain_cache_drift:%s!=%s" % (
        current["manifest_sha256"],
        reference_cache["manifest_sha256"],
    )


def _n7_run_pair_attempt(
    args,
    reference,
    expected_gpu,
    cache_manifest,
    experiment_id,
    order,
    attempt_index,
    pair_index=None,
    warmup=False,
):
    attempt_dir = _n7_attempt_directory(
        args.output_dir,
        experiment_id,
        attempt_index,
        pair_index=pair_index,
        warmup=warmup,
    )
    _n7_require_fresh_path(attempt_dir, "pair attempt")
    attempt_dir.mkdir(parents=True)
    record = {
        "experiment_id": experiment_id,
        "warmup": bool(warmup),
        "pair_index": pair_index,
        "attempt_index": int(attempt_index),
        "order": list(order),
        "started_utc": _n7_utc_now(),
        "status": "running",
        "arms": {},
        "environmental_invalid_reasons": [],
    }
    pre_snapshot = n7_gpu_snapshot(
        args.n7_physical_gpu_index, owner_pid=os.getpid()
    )
    record["pre_pair_gpu"] = pre_snapshot
    environmental_reasons = n7_environment_invalid_reasons(
        [pre_snapshot],
        expected_gpu["physical_index"],
        expected_gpu["uuid"],
        expected_gpu["driver_version"],
    )
    arm_payloads = {}
    correctness_error = None
    if not environmental_reasons:
        for arm in order:
            try:
                payload = _n7_execute_arm(
                    args,
                    reference,
                    experiment_id,
                    arm,
                    attempt_dir,
                    pair_index=pair_index,
                    attempt_index=attempt_index,
                    warmup=warmup,
                )
                arm_payloads[arm] = payload
                record["arms"][arm] = payload["record"]
            except N7EnvironmentalError as error:
                environmental_reasons.append(str(error))
                break
            except N7CorrectnessError as error:
                correctness_error = str(error)
                break
            except Exception as error:
                correctness_error = (
                    "unexpected N7 arm orchestration failure: %s" % error
                )
                break
    post_snapshot = n7_gpu_snapshot(
        args.n7_physical_gpu_index, owner_pid=os.getpid()
    )
    record["post_pair_gpu"] = post_snapshot
    all_samples = [pre_snapshot, post_snapshot]
    for payload in arm_payloads.values():
        all_samples.extend(payload["record"]["gpu_samples"])
    environmental_reasons.extend(
        n7_environment_invalid_reasons(
            all_samples,
            expected_gpu["physical_index"],
            expected_gpu["uuid"],
            expected_gpu["driver_version"],
        )
    )
    source_reason = _n7_source_drift_reason(reference["source_state"])
    if source_reason:
        environmental_reasons.append(source_reason)
    cache_reason = _n7_cache_drift_reason(cache_manifest)
    if cache_reason:
        environmental_reasons.append(cache_reason)
    if correctness_error is None and not environmental_reasons:
        if set(arm_payloads) != set(N7_ARMS):
            environmental_reasons.append("required_pair_arm_artifacts_absent")
        else:
            try:
                record["config_equivalence"] = validate_n7_config_equivalence(
                    arm_payloads[N7_FEATURE_OFF_ARM]["config"],
                    arm_payloads[N7_CONSENSUS_ARM]["config"],
                    arm_payloads[N7_FEATURE_OFF_ARM]["constraint"],
                    arm_payloads[N7_CONSENSUS_ARM]["constraint"],
                )
            except RuntimeError as error:
                correctness_error = str(error)
    record["finished_utc"] = _n7_utc_now()
    if correctness_error is not None:
        record["status"] = "correctness_failure"
        record["correctness_failure"] = correctness_error
    elif environmental_reasons:
        record["status"] = "environmentally_invalid"
        record["environmental_invalid_reasons"] = sorted(
            set(environmental_reasons)
        )
    else:
        record["status"] = "valid"
    write_json(attempt_dir / "pair-attempt.json", record)
    return record


def _n7_run_pair_with_replacement(
    args,
    reference,
    expected_gpu,
    cache_manifest,
    experiment_id,
    order,
    pair_index=None,
    warmup=False,
):
    attempts = []
    for attempt_index in (1, 2):
        attempt = _n7_run_pair_attempt(
            args,
            reference,
            expected_gpu,
            cache_manifest,
            experiment_id,
            order,
            attempt_index,
            pair_index=pair_index,
            warmup=warmup,
        )
        attempts.append(attempt)
        if attempt["status"] == "valid":
            return {"status": "valid", "attempts": attempts, "valid": attempt}
        if attempt["status"] == "correctness_failure":
            return {
                "status": "correctness_failure",
                "attempts": attempts,
                "valid": None,
            }
        action = n7_invalid_attempt_action(attempt_index)
        attempt["replacement_action"] = action
        write_json(
            _n7_attempt_directory(
                args.output_dir,
                experiment_id,
                attempt_index,
                pair_index=pair_index,
                warmup=warmup,
            )
            / "pair-attempt.json",
            attempt,
        )
        if action == "stop_incomplete":
            return {
                "status": "environment_incomplete",
                "attempts": attempts,
                "valid": None,
            }
        time.sleep(N7_REPLACEMENT_DELAY_SECONDS)
    raise AssertionError("unreachable N7 replacement state")


def n7_update_determinism(references, experiment_id, arm_record):
    arm = arm_record["arm"]
    key = "%s:%s" % (experiment_id, arm)
    try:
        references[key] = validate_n7_determinism(
            references.get(key), arm_record["identity"], key
        )
    except RuntimeError as error:
        raise N7CorrectnessError(str(error)) from error


def _n7_experiment_statistics(pair_records):
    statistics_by_metric = {}
    for field in N7_TIMING_FIELDS:
        controls = [
            pair["arms"][N7_FEATURE_OFF_ARM][field]
            for pair in pair_records
        ]
        candidates = [
            pair["arms"][N7_CONSENSUS_ARM][field]
            for pair in pair_records
        ]
        statistics_by_metric[field] = n7_metric_statistics(
            controls, candidates
        )
    return statistics_by_metric


def _n7_contract_payload(args, source, repository, preserved, cache, gpu):
    return {
        "schema": N7_CONTRACT_SCHEMA,
        "created_utc": _n7_utc_now(),
        "repository": repository,
        "source_state": source,
        "static_input_sha256": n7_static_input_hashes(args),
        "preserved_paths_before": preserved,
        "physical_gpu": gpu,
        "cuda_version": _n7_nvidia_cuda_version(),
        "python": subprocess.check_output(
            [str(Path(args.python).resolve()), "--version"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip(),
        "cublas_workspace_config": DEFAULT_CUBLAS_WORKSPACE_CONFIG,
        "feasible_domain_cache": cache,
        "protocol": {
            "experiments": list(N7_EXPERIMENTS),
            "seed": N7_SEED,
            "iterations": N7_ITERATIONS,
            "learning_rate_scale": 1.0,
            "warmup_pairs_per_experiment": 1,
            "measured_pairs_per_experiment": N7_PAIR_COUNT,
            "alternating_order": [
                n7_pair_order(index)
                for index in range(1, N7_PAIR_COUNT + 1)
            ],
            "control": N7_FEATURE_OFF_ARM,
            "candidate": N7_CONSENSUS_ARM,
            "resume": False,
            "cache_read_only": True,
            "run_local_input_metadata_excluded_from_pair_hash": sorted(
                N7_RUN_LOCAL_INPUT_METADATA
            ),
        },
        "frozen_algorithm": {
            "initialization_track": "checkpoint_warm_start",
            "checkpoint_placement": repo_path(args.checkpoint_placement),
            "assignment": repo_path(args.assignment),
            "grid_mm": 0.05,
            "keepin_margin_mm": 0.1,
            "keepin_margin_tau_mm": 0.05,
            "collision_gradient_ratio": 0.1,
            "collision_margin_mm": 0.0,
            "collision_tau_mm": 0.025,
            "guard_backoff": 0.5,
            "guard_retries": 4,
            "contact_iterations": 8,
            "contact_max_nodes": 32,
            "contact_max_component_nodes": 16,
            "strict_reference_default_off": True,
            "stage_micro_enabled": False,
        },
        "timing": {
            "primary_fields": list(N7_TIMING_FIELDS),
            "reported_fields": list(N7_REPORTED_TIMING_FIELDS),
            "median_ratio_limit": 2.0,
        },
        "prohibited": [
            "D2",
            "D3 rerun",
            "E4",
            "stage micro",
            "repair",
            "fallback",
            "CP-SAT",
            "one-opt",
            "pair scan",
            "parameter tuning",
            "cold/source",
        ],
    }


def render_n7_report(summary):
    lines = [
        "# M336 N7 Paired Production Runtime Evidence",
        "",
        "- Status: `%s`" % summary["status"],
        "- Decision: `%s`" % summary["decision"],
        "- Source: `%s`" % summary["source_state"]["git_sha"],
        "- GPU: physical `%s`, `%s`"
        % (
            summary["environment"]["initial_gpu"]["physical_index"],
            summary["environment"]["initial_gpu"]["uuid"],
        ),
        "- Candidate: `consensus_per_step`; control: M336-171 feature-off",
        "",
    ]
    for experiment_id in N7_EXPERIMENTS:
        experiment = summary.get("experiments", {}).get(experiment_id)
        if not experiment or not experiment.get("pairs"):
            continue
        lines.extend(
            [
                "## %s" % experiment_id,
                "",
                "| Pair | Order | Control GPU | Candidate GPU | GPU delta | "
                "GPU ratio | Control E2E | Candidate E2E | E2E delta | E2E ratio |",
                "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for pair in experiment["pairs"]:
            control = pair["arms"][N7_FEATURE_OFF_ARM]
            candidate = pair["arms"][N7_CONSENSUS_ARM]
            lines.append(
                "| %d | `%s` | %.6f | %.6f | %.6f | %.6f | %.6f | %.6f | %.6f | %.6f |"
                % (
                    pair["pair_index"],
                    " -> ".join(pair["order"]),
                    control["gpu_optimization_seconds"],
                    candidate["gpu_optimization_seconds"],
                    candidate["gpu_optimization_seconds"]
                    - control["gpu_optimization_seconds"],
                    candidate["gpu_optimization_seconds"]
                    / control["gpu_optimization_seconds"],
                    control["end_to_end_seconds"],
                    candidate["end_to_end_seconds"],
                    candidate["end_to_end_seconds"]
                    - control["end_to_end_seconds"],
                    candidate["end_to_end_seconds"]
                    / control["end_to_end_seconds"],
                )
            )
        statistics_payload = experiment.get("statistics")
        if statistics_payload is None:
            lines.extend(["", "Distribution statistics pending five valid pairs.", ""])
        else:
            lines.extend(
                [
                    "",
                    "| Metric | GPU ratio | E2E ratio |",
                    "| --- | ---: | ---: |",
                ]
            )
            for label, key in (
                ("Median", "median"),
                ("Minimum", "minimum"),
                ("Maximum", "maximum"),
                ("Arithmetic mean", "arithmetic_mean"),
                ("Geometric mean", "geometric_mean"),
                ("MAD", "median_absolute_deviation"),
            ):
                lines.append(
                    "| %s | %.6f | %.6f |"
                    % (
                        label,
                        statistics_payload["gpu_optimization_seconds"][key],
                        statistics_payload["end_to_end_seconds"][key],
                    )
                )
            lines.extend(
                [
                    "",
                    "GPU gate: `%s`; end-to-end gate: `%s`."
                    % (
                        "PASS"
                        if statistics_payload["gpu_optimization_seconds"][
                            "passes_2x"
                        ]
                        else "FAIL",
                        "PASS"
                        if statistics_payload["end_to_end_seconds"][
                            "passes_2x"
                        ]
                        else "FAIL",
                    ),
                    "",
                ]
            )
        candidate = experiment["pairs"][0]["arms"][N7_CONSENSUS_ARM]
        identity = candidate["identity"]
        correctness = candidate["correctness"]
        legality = identity["legality"]
        lines.extend(
            [
                "Candidate placement `%s`; replay `%s`."
                % (
                    identity["input_placement_sha256"],
                    identity["replayed_placement_sha256"],
                ),
                "",
                "- Native HPWL / FLUTE RSMT / score: `%.12f / %.6f / %.12f`"
                % (
                    identity["hpwl"],
                    identity["rsmt"],
                    identity["normalized_quality_score"],
                ),
                "- Exact legality: `%d/100` contained, `%d` Keep-in violations, "
                "`%d` overlaps, `%.12g mm2` overlap area"
                % (
                    legality["fully_contained_components"],
                    legality["keepin_violation_count"],
                    legality["overlap_pair_count"],
                    legality["overlap_area_mm2"],
                ),
                "- Guard accepted/rejected/rollback: `%d / %d / %d`; final LR: `%.12g`"
                % (
                    correctness["guard_accepted_step_count"],
                    correctness["guard_rejected_attempt_count"],
                    correctness["rollback_count"],
                    identity["final_effective_learning_rate"],
                ),
                "- Anchor mean / p90: `%.12f / %.12f mm`"
                % (
                    identity["anchor_distance_mm"]["mean"],
                    identity["anchor_distance_mm"]["p90"],
                ),
                "",
            ]
        )
    invalid = summary.get("invalid_attempts", [])
    lines.extend(
        [
            "## Validity",
            "",
            "- Invalid attempts: `%d`" % len(invalid),
            "- Candidate determinism: `%s`"
            % summary.get("candidate_determinism", "not-complete"),
            "- Prohibited work executed: `none`",
            "",
        ]
    )
    if summary.get("failure"):
        lines.extend(
            ["## Failure", "", "```text", summary["failure"], "```", ""]
        )
    if invalid:
        lines.extend(["## Invalid Attempts", ""])
        for attempt in invalid:
            lines.append(
                "- `%s` pair `%s` attempt `%s`: %s"
                % (
                    attempt["experiment_id"],
                    attempt["pair_index"] or "warmup",
                    attempt["attempt_index"],
                    "; ".join(attempt["environmental_invalid_reasons"]),
                )
            )
        lines.append("")
    return "\n".join(lines)


def run_n7_paired_timing(args):
    _n7_require_fresh_path(args.output_dir, "campaign output")
    if args.summary_path is None or args.report_path is None:
        raise ValueError("N7 requires explicit summary and report paths")
    expected_summary = args.output_dir / "paired-summary.json"
    expected_report = args.output_dir / "REPORT.md"
    if args.summary_path.resolve() != expected_summary.resolve():
        raise ValueError("N7 summary path must be run-local paired-summary.json")
    if args.report_path.resolve() != expected_report.resolve():
        raise ValueError("N7 report path must be run-local REPORT.md")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != str(
        args.n7_physical_gpu_index
    ):
        raise ValueError("N7 parent must be pinned to physical GPU 2")
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != (
        DEFAULT_CUBLAS_WORKSPACE_CONFIG
    ):
        raise ValueError("N7 parent CUBLAS workspace contract is missing")
    source = source_state()
    if source["branch"] != "experiment":
        raise ValueError("N7 must remain on branch experiment")
    if source["source_install_mismatches"]:
        raise ValueError("N7 source/install parity failed")
    cache_manifest = n7_directory_manifest(args.feasible_domain_cache_dir)
    if cache_manifest["file_count"] == 0:
        raise ValueError("N7 requires an existing read-only feasible cache")
    repository = n7_repository_snapshot()
    if repository["diff_check"]:
        raise ValueError("N7 repository has git diff --check failures")
    preserved_before = n7_preserved_paths_state()
    initial_gpu = n7_gpu_snapshot(
        args.n7_physical_gpu_index, owner_pid=os.getpid()
    )
    contract = _n7_contract_payload(
        args,
        source,
        repository,
        preserved_before,
        cache_manifest,
        initial_gpu,
    )
    args.output_dir.mkdir(parents=True)
    write_json(args.output_dir / "contract.json", contract)
    environment = {
        "created_utc": _n7_utc_now(),
        "initial_gpu": initial_gpu,
        "cuda_version": contract["cuda_version"],
        "python": contract["python"],
        "cublas_workspace_config": DEFAULT_CUBLAS_WORKSPACE_CONFIG,
    }
    write_json(args.output_dir / "environment.json", environment)
    expected_gpu = {
        key: initial_gpu[key]
        for key in ("physical_index", "uuid", "driver_version")
    }
    provenance_reference = {
        "source_state": source,
        "static_input_sha256": contract["static_input_sha256"],
        "input_sha256": None,
    }
    summary = {
        "schema": N7_SCHEMA,
        "status": "running",
        "decision": "pending",
        "started_utc": _n7_utc_now(),
        "source_state": source,
        "static_input_sha256": contract["static_input_sha256"],
        "canonical_input_sha256": None,
        "contract_path": repo_path(args.output_dir / "contract.json"),
        "environment_path": repo_path(args.output_dir / "environment.json"),
        "environment": environment,
        "cache_manifest": cache_manifest,
        "preserved_paths_before": preserved_before,
        "warmups": {},
        "experiments": {},
        "invalid_attempts": [],
        "candidate_determinism": "not-complete",
        "prohibited_work_executed": [],
    }
    deterministic_references = {}

    def persist():
        summary["canonical_input_sha256"] = provenance_reference.get(
            "input_sha256"
        )
        write_json(args.summary_path, summary)
        args.report_path.write_text(render_n7_report(summary))

    try:
        for experiment_id in N7_EXPERIMENTS:
            warmup = _n7_run_pair_with_replacement(
                args,
                provenance_reference,
                expected_gpu,
                cache_manifest,
                experiment_id,
                [N7_FEATURE_OFF_ARM, N7_CONSENSUS_ARM],
                warmup=True,
            )
            summary["warmups"][experiment_id] = warmup
            summary["invalid_attempts"].extend(
                attempt
                for attempt in warmup["attempts"]
                if attempt["status"] == "environmentally_invalid"
            )
            if warmup["status"] != "valid":
                if warmup["status"] == "correctness_failure":
                    raise N7CorrectnessError(
                        warmup["attempts"][-1]["correctness_failure"]
                    )
                raise N7EnvironmentalError(
                    "N7 warm-up evidence is environmentally incomplete"
                )

        for experiment_id in N7_EXPERIMENTS:
            measured_pairs = []
            summary["experiments"][experiment_id] = {
                "pairs": measured_pairs,
                "statistics": None,
            }
            for pair_index in range(1, N7_PAIR_COUNT + 1):
                pair = _n7_run_pair_with_replacement(
                    args,
                    provenance_reference,
                    expected_gpu,
                    cache_manifest,
                    experiment_id,
                    n7_pair_order(pair_index),
                    pair_index=pair_index,
                )
                summary["invalid_attempts"].extend(
                    attempt
                    for attempt in pair["attempts"]
                    if attempt["status"] == "environmentally_invalid"
                )
                if pair["status"] != "valid":
                    if pair["status"] == "correctness_failure":
                        raise N7CorrectnessError(
                            pair["attempts"][-1]["correctness_failure"]
                        )
                    raise N7EnvironmentalError(
                        "N7 measured pair %s/%d is environmentally incomplete"
                        % (experiment_id, pair_index)
                    )
                valid = pair["valid"]
                measured_pairs.append(valid)
                for arm in N7_ARMS:
                    n7_update_determinism(
                        deterministic_references,
                        experiment_id,
                        valid["arms"][arm],
                    )
                persist()
            summary["experiments"][experiment_id]["statistics"] = (
                _n7_experiment_statistics(measured_pairs)
            )

        gates = {}
        for experiment_id in N7_EXPERIMENTS:
            experiment_stats = summary["experiments"][experiment_id][
                "statistics"
            ]
            for field in N7_TIMING_FIELDS:
                gates["%s_%s" % (experiment_id, field)] = experiment_stats[
                    field
                ]["passes_2x"]
        summary["gates"] = gates
        summary["candidate_determinism"] = "pass"
        summary["status"] = "complete"
        if all(gates.values()):
            summary["decision"] = "pass_promote_consensus_per_step"
        else:
            summary["decision"] = "timing_gate_failed_human_decision_required"
    except N7CorrectnessError as error:
        summary["status"] = "correctness_failure"
        summary["decision"] = "fail_stop_immediately"
        summary["failure"] = str(error)
    except N7EnvironmentalError as error:
        summary["status"] = "environment_incomplete"
        summary["decision"] = "incomplete_human_decision_required"
        summary["failure"] = str(error)
    except Exception as error:
        summary["status"] = "measurement_runner_failure"
        summary["decision"] = "fail_stop_immediately"
        summary["failure"] = "unexpected N7 runner failure: %s" % error
    finally:
        summary["finished_utc"] = _n7_utc_now()
        final_gpu = n7_gpu_snapshot(
            args.n7_physical_gpu_index, owner_pid=os.getpid()
        )
        summary["environment"]["final_gpu"] = final_gpu
        summary["repository_after"] = n7_repository_snapshot()
        summary["preserved_paths_after"] = n7_preserved_paths_state()
        summary["preserved_paths_unchanged"] = (
            summary["preserved_paths_after"]
            == summary["preserved_paths_before"]
        )
        if (
            summary["status"] == "complete"
            and not summary["preserved_paths_unchanged"]
        ):
            summary["status"] = "environment_incomplete"
            summary["decision"] = "incomplete_human_decision_required"
            summary["failure"] = "preserved user-owned artifact hashes drifted"
        summary["cache_manifest_after"] = n7_directory_manifest(
            args.feasible_domain_cache_dir
        )
        persist()
        write_json(args.output_dir / "environment.json", summary["environment"])
    print("wrote %s and %s" % (args.summary_path, args.report_path))
    if summary["status"] != "complete":
        raise RuntimeError(summary["failure"])
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", nargs="+", default=list(DEFAULT_EXPERIMENTS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[1000, 1001, 1002])
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument(
        "--learning-rate-scale",
        type=float,
        default=1.0,
        help="bounded multiplier for the native stage learning rate",
    )
    parser.add_argument("--gpu", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--irregular-density",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable side-specific irregular capacity for E2-E4",
    )
    parser.add_argument(
        "--footprint-collision",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="enable the preventive footprint collision barrier for E2-E4",
    )
    parser.add_argument("--collision-gradient-ratio", type=float, default=0.1)
    parser.add_argument("--collision-margin-mm", type=float, default=0.0)
    parser.add_argument("--collision-tau-mm", type=float, default=0.025)
    parser.add_argument(
        "--exact-step-guard",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="reject exact-illegal native steps and retry with bounded backoff",
    )
    parser.add_argument("--exact-step-guard-backoff", type=float, default=0.5)
    parser.add_argument(
        "--exact-step-guard-max-retries", type=int, default=4
    )
    parser.add_argument(
        "--collision-pair-diagnostics",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="record pair-local gradients and actual guarded proposal motion",
    )
    parser.add_argument(
        "--exact-contact-projection",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="project exact-crossing contact components before guard acceptance",
    )
    parser.add_argument(
        "--exact-contact-projection-max-iterations", type=int, default=8
    )
    parser.add_argument(
        "--exact-contact-policy",
        choices=CONTACT_POLICIES,
        default=CONSENSUS_PER_STEP_CONTACT_POLICY,
        help=(
            "named per-step contact architecture; stage micro remains "
            "reserved until D3 evidence"
        ),
    )
    parser.add_argument(
        "--exact-contact-projection-mode",
        choices=CONTACT_PROJECTION_MODES,
        default=None,
        help="legacy low-level override; must agree with contact policy",
    )
    parser.add_argument(
        "--exact-contact-projection-max-nodes",
        type=int,
        default=32,
        help=(
            "maximum cumulative active nodes selected for contact "
            "correction per native proposal"
        ),
    )
    parser.add_argument(
        "--exact-contact-projection-max-cover-component-nodes",
        type=int,
        default=16,
        help="maximum component size for bounded exact contact enumeration",
    )
    parser.add_argument(
        "--exact-contact-projection-max-authority-states",
        type=int,
        default=4096,
        help="maximum proposal-authority assignments per contact component",
    )
    parser.add_argument(
        "--exact-contact-projection-authority-search-strategy",
        choices=AUTHORITY_SEARCH_STRATEGIES,
        default=None,
        help="legacy low-level override; must agree with contact policy",
    )
    parser.add_argument(
        "--exact-contact-topology-tiebreak",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="legacy low-level override; must agree with contact policy",
    )
    parser.add_argument(
        "--exact-contact-topology-min-net-degree",
        type=int,
        default=DEFAULT_M336_TOPOLOGY_MIN_NET_DEGREE,
    )
    parser.add_argument(
        "--initialization-track",
        choices=("cold_source", "checkpoint_warm_start"),
        default="cold_source",
    )
    parser.add_argument(
        "--checkpoint-placement",
        type=Path,
        default=DEFAULT_M336_CHECKPOINT_PL,
    )
    parser.add_argument(
        "--feasible-domain-cache-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/native-cypress/cache/feasible-domains",
    )
    parser.add_argument("--python", default="python3.11")
    parser.add_argument(
        "--placer", type=Path, default=REPO_ROOT / "install/dreamplace/Placer.py"
    )
    parser.add_argument(
        "--assignment",
        type=Path,
        default=DEFAULT_M336_ASSIGNMENT,
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
    parser.add_argument(
        "--anchor-gradient-ratio",
        "--anchor-weight",
        dest="anchor_gradient_ratio",
        type=float,
        default=0.1,
    )
    parser.add_argument(
        "--anchor-gradient-ratio-sweep",
        "--anchor-weight-sweep",
        dest="anchor_gradient_ratio_sweep",
        nargs="+",
        type=float,
    )
    parser.add_argument(
        "--sweep-output-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/weight_sweep/runs",
    )
    parser.add_argument(
        "--grid-mm", type=float, default=DEFAULT_M336_CONSTRAINT_GRID_MM
    )
    parser.add_argument("--clearance-mm", type=float, default=0.0)
    parser.add_argument("--keepin-margin-mm", type=float, default=0.1)
    parser.add_argument("--keepin-margin-tau-mm", type=float, default=0.05)
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
    parser.add_argument(
        "--n7-paired-timing",
        action="store_true",
        help="run the frozen M336 N7 paired timing campaign",
    )
    parser.add_argument(
        "--n7-arm",
        choices=N7_ARMS,
        help="internal isolated arm identity for an N7 child process",
    )
    parser.add_argument(
        "--n7-physical-gpu-index",
        type=int,
        default=N7_PHYSICAL_GPU_INDEX,
        help="physical GPU used by the N7 parent and every child",
    )
    args = parser.parse_args()
    if args.n7_arm == N7_FEATURE_OFF_ARM:
        args.exact_contact_policy = ""
    try:
        contact_policy = _resolve_contact_policy_contract(
            args.exact_contact_policy,
            mode=args.exact_contact_projection_mode,
            authority_search_strategy=(
                args.exact_contact_projection_authority_search_strategy
            ),
            topology_tiebreak=args.exact_contact_topology_tiebreak,
            topology_min_net_degree=(
                args.exact_contact_topology_min_net_degree
            ),
        )
    except ValueError as error:
        parser.error(str(error))
    args.exact_contact_policy = contact_policy["policy"]
    args.exact_contact_projection_mode = contact_policy["mode"]
    args.exact_contact_projection_authority_search_strategy = contact_policy[
        "authority_search_strategy"
    ]
    args.exact_contact_topology_tiebreak = contact_policy[
        "topology_tiebreak"
    ]
    args.exact_contact_topology_min_net_degree = contact_policy[
        "topology_min_net_degree"
    ]
    args.output_dir = args.output_dir.resolve()
    args.sweep_output_dir = args.sweep_output_dir.resolve()
    args.baseline_geometry = args.baseline_geometry.resolve()
    args.bookshelf_dir = args.bookshelf_dir.resolve()
    args.baseline_output_dir = args.baseline_output_dir.resolve()
    args.checkpoint_placement = args.checkpoint_placement.resolve()
    args.feasible_domain_cache_dir = args.feasible_domain_cache_dir.resolve()
    args.assignment = args.assignment.resolve()
    args.placer = args.placer.resolve()
    if args.summary_path is not None:
        args.summary_path = args.summary_path.resolve()
    if args.report_path is not None:
        args.report_path = args.report_path.resolve()
    invalid = sorted(set(args.experiments) - set(EXPERIMENTS))
    if invalid:
        parser.error("unknown experiments: %s" % invalid)
    if (
        not args.assignment.exists()
        or not args.placer.exists()
        or not args.baseline_geometry.exists()
        or not args.checkpoint_placement.exists()
    ):
        parser.error(
            "assignment, installed placer, baseline geometry, and checkpoint "
            "placement must exist"
        )
    if (
        args.anchor_gradient_ratio <= 0
        or args.collision_gradient_ratio <= 0
        or not math.isfinite(args.collision_gradient_ratio)
        or args.collision_margin_mm < 0
        or not math.isfinite(args.collision_margin_mm)
        or args.collision_tau_mm <= 0
        or not math.isfinite(args.collision_tau_mm)
        or not math.isfinite(args.exact_step_guard_backoff)
        or not 0 < args.exact_step_guard_backoff < 1
        or args.exact_step_guard_max_retries < 0
        or args.exact_contact_projection_max_iterations <= 0
        or args.exact_contact_projection_max_nodes < 2
        or args.exact_contact_projection_max_cover_component_nodes < 2
        or args.exact_contact_topology_min_net_degree < 2
        or (
            args.exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES
            and args.exact_contact_projection_max_authority_states <= 0
        )
        or not math.isfinite(args.learning_rate_scale)
        or args.learning_rate_scale < MIN_M336_LEARNING_RATE_SCALE
        or args.learning_rate_scale > MAX_M336_LEARNING_RATE_SCALE
        or args.grid_mm <= 0
        or args.clearance_mm < 0
        or args.keepin_margin_mm < 0
        or args.keepin_margin_tau_mm <= 0
        or args.site_mm <= 0
    ):
        parser.error(
            "anchor/collision ratios, grid, margin taus, and site size must be positive; "
            "guard backoff must be in (0, 1) and retries non-negative; "
            "contact projection iterations must be positive and its node "
            "and cover-component limits at least two, and authority state "
            "limit positive; "
            "learning-rate scale must be within [%g, %g]; clearance and "
            "margin must be non-negative"
            % (MIN_M336_LEARNING_RATE_SCALE, MAX_M336_LEARNING_RATE_SCALE)
        )
    if args.exact_step_guard and not args.footprint_collision:
        parser.error("exact-step guard requires --footprint-collision")
    if args.collision_pair_diagnostics and not args.exact_step_guard:
        parser.error(
            "--collision-pair-diagnostics requires --exact-step-guard"
        )
    if args.exact_contact_projection and not args.exact_step_guard:
        parser.error("--exact-contact-projection requires --exact-step-guard")
    if (
        args.exact_contact_projection_authority_search_strategy
        != EXHAUSTIVE_AUTHORITY_SEARCH
        and args.exact_contact_projection_mode not in PROPOSAL_AUTHORITY_MODES
    ):
        parser.error(
            "factorized authority search requires a proposal-authority mode"
        )
    if args.exact_contact_topology_tiebreak:
        if not args.exact_contact_projection:
            parser.error(
                "--exact-contact-topology-tiebreak requires "
                "--exact-contact-projection"
            )
        if (
            args.exact_contact_projection_mode
            != "protected_proposal_authority_search"
        ):
            parser.error(
                "--exact-contact-topology-tiebreak requires protected "
                "proposal-authority mode"
            )
    if args.anchor_gradient_ratio_sweep and any(
        ratio <= 0 for ratio in args.anchor_gradient_ratio_sweep
    ):
        parser.error("all anchor gradient-ratio sweep values must be positive")
    if args.n7_paired_timing and args.n7_arm is not None:
        parser.error("N7 parent and child modes are mutually exclusive")
    if args.n7_paired_timing or args.n7_arm is not None:
        try:
            validate_n7_frozen_arguments(args, child_arm=args.n7_arm)
        except ValueError as error:
            parser.error(str(error))
    if args.n7_paired_timing:
        run_n7_paired_timing(args)
        return

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
    if args.anchor_gradient_ratio_sweep:
        ratios = sorted(set(args.anchor_gradient_ratio_sweep))
        for ratio in ratios:
            ratio_dir = args.sweep_output_dir / ("ratio_%s" % format(ratio, "g"))
            for experiment_id in args.experiments:
                for seed in args.seeds:
                    print(
                        "running %s anchor gradient ratio %g seed %d"
                        % (experiment_id, ratio, seed),
                        flush=True,
                    )
                    results.append(
                        run_one(
                            args,
                            experiment_id,
                            seed,
                            output_dir=ratio_dir,
                            anchor_gradient_ratio=ratio,
                            initialization_track=args.initialization_track,
                        )
                    )
        summary = {
            "schema": "m336_anchor_gradient_ratio_sweep_v2",
            "git_sha": git_sha(),
            "source_state": args.source_identity,
            "environment": args.environment_identity,
            "input_sha256": args.input_identity,
            "experiments": args.experiments,
            "seeds": args.seeds,
            "iterations": args.iterations,
            "learning_rate_scale": args.learning_rate_scale,
            "footprint_collision": args.footprint_collision,
            "collision_gradient_ratio": args.collision_gradient_ratio,
            "collision_margin_mm": args.collision_margin_mm,
            "collision_tau_mm": args.collision_tau_mm,
            "exact_step_guard": args.exact_step_guard,
            "exact_step_guard_backoff": args.exact_step_guard_backoff,
            "exact_step_guard_max_retries": (
                args.exact_step_guard_max_retries
            ),
            "collision_pair_diagnostics": args.collision_pair_diagnostics,
            "exact_contact_projection": args.exact_contact_projection,
            "exact_contact_policy": args.exact_contact_policy,
            "exact_contact_projection_mode": (
                args.exact_contact_projection_mode
            ),
            "exact_contact_projection_max_iterations": (
                args.exact_contact_projection_max_iterations
            ),
            "exact_contact_projection_max_nodes": (
                args.exact_contact_projection_max_nodes
            ),
            "exact_contact_projection_max_cover_component_nodes": (
                args.exact_contact_projection_max_cover_component_nodes
            ),
            "anchor_gradient_ratios": ratios,
            "constraint_grid_mm": args.grid_mm,
            "keepin_clearance_mm": args.clearance_mm,
            "keepin_margin_mm": args.keepin_margin_mm,
            "keepin_margin_tau_mm": args.keepin_margin_tau_mm,
            "irregular_density": args.irregular_density,
            "initialization_track": args.initialization_track,
            "invocation": invocation,
            "reproduction_command": reproduction_command(args, ratios),
            "manual_baseline": args.manual_baseline,
            "runs": results,
            "aggregate": aggregate_weight_sweep(results),
        }
        if args.exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES:
            summary["exact_contact_projection_max_authority_states"] = (
                args.exact_contact_projection_max_authority_states
            )
            if (
                args.exact_contact_projection_authority_search_strategy
                != EXHAUSTIVE_AUTHORITY_SEARCH
            ):
                summary[
                    "exact_contact_projection_authority_search_strategy"
                ] = args.exact_contact_projection_authority_search_strategy
            if args.exact_contact_topology_tiebreak:
                summary["exact_contact_topology_tiebreak"] = True
                summary["exact_contact_topology_min_net_degree"] = (
                    args.exact_contact_topology_min_net_degree
                )
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
                results.append(
                    run_one(
                        args,
                        experiment_id,
                        seed,
                        initialization_track=args.initialization_track,
                    )
                )

        aggregate_rows, comparisons = aggregate(results, args.manual_baseline)
        sweep_path = REPO_ROOT / "results/m336/weight_sweep/summary.json"
        sweep_summary = optional_json(sweep_path)
        summary = {
            "schema": "m336_experiment_summary_v2",
            "n7_arm": args.n7_arm,
            "git_sha": git_sha(),
            "source_state": args.source_identity,
            "environment": args.environment_identity,
            "input_sha256": args.input_identity,
            "experiments": args.experiments,
            "seeds": args.seeds,
            "iterations": args.iterations,
            "learning_rate_scale": args.learning_rate_scale,
            "footprint_collision": args.footprint_collision,
            "collision_gradient_ratio": args.collision_gradient_ratio,
            "collision_margin_mm": args.collision_margin_mm,
            "collision_tau_mm": args.collision_tau_mm,
            "exact_step_guard": args.exact_step_guard,
            "exact_step_guard_backoff": args.exact_step_guard_backoff,
            "exact_step_guard_max_retries": (
                args.exact_step_guard_max_retries
            ),
            "collision_pair_diagnostics": args.collision_pair_diagnostics,
            "exact_contact_projection": args.exact_contact_projection,
            "exact_contact_policy": args.exact_contact_policy,
            "exact_contact_projection_mode": (
                args.exact_contact_projection_mode
            ),
            "exact_contact_projection_max_iterations": (
                args.exact_contact_projection_max_iterations
            ),
            "exact_contact_projection_max_nodes": (
                args.exact_contact_projection_max_nodes
            ),
            "exact_contact_projection_max_cover_component_nodes": (
                args.exact_contact_projection_max_cover_component_nodes
            ),
            "constraint_grid_mm": args.grid_mm,
            "keepin_clearance_mm": args.clearance_mm,
            "keepin_margin_mm": args.keepin_margin_mm,
            "keepin_margin_tau_mm": args.keepin_margin_tau_mm,
            "irregular_density": args.irregular_density,
            "initialization_track": args.initialization_track,
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
        if args.exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES:
            summary["exact_contact_projection_max_authority_states"] = (
                args.exact_contact_projection_max_authority_states
            )
            if (
                args.exact_contact_projection_authority_search_strategy
                != EXHAUSTIVE_AUTHORITY_SEARCH
            ):
                summary[
                    "exact_contact_projection_authority_search_strategy"
                ] = args.exact_contact_projection_authority_search_strategy
            if args.exact_contact_topology_tiebreak:
                summary["exact_contact_topology_tiebreak"] = True
                summary["exact_contact_topology_min_net_degree"] = (
                    args.exact_contact_topology_min_net_degree
                )
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
