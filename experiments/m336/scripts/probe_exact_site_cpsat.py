#!/usr/bin/env python3
"""Probe exact M336 TOP-site packing with a deterministic CP-SAT model."""

from __future__ import annotations

import json
import os
import time
from argparse import Namespace
from importlib import metadata
from pathlib import Path

PREPROCESS_THREADS = int(os.environ.get("M336_PREPROCESS_THREADS", "1"))
if PREPROCESS_THREADS <= 0:
    raise ValueError("preprocess thread count must be positive")
for thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[thread_variable] = str(PREPROCESS_THREADS)

import numpy as np
import torch
from shapely import affinity

from analyze_quality_bound import (
    _baseline_positions,
    _load_context,
    _override_manual_baseline_endpoints,
    _select_fixed_endpoints,
)
from dreamplace.constraints.anchor_keepin import (
    _is_axis_aligned_rectangle,
    _obstacle_free_candidate_indices,
)
from solve_discrete_placement import _convex_parts, _fixed_footprint_local


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(
    os.environ.get(
        "M336_SOURCE_JSON",
        ROOT / "results/m336/grid01_restored_bottom_1024_replay/result.json",
    )
)
GUIDE = Path(
    os.environ.get(
        "M336_GUIDE_JSON",
        ROOT / "results/m336/discrete_two_anchor/result-no-collision.json",
    )
)
ADDITIONAL_GUIDES = [
    Path(value)
    for value in os.environ.get("M336_ADDITIONAL_GUIDE_JSONS", "").split(",")
    if value
]
OUTPUT = Path(
    os.environ.get("M336_OUTPUT_JSON", "/tmp/m336_exact_site_cpsat.json")
)
PROGRESS = Path(
    os.environ.get("M336_PROGRESS_JSON", f"{OUTPUT}.progress")
)
GEOMETRY_EPSILON = 1e-10


def _load_cp_model():
    try:
        from ortools.sat.python import cp_model
    except ImportError as error:
        raise RuntimeError(
            "probe_exact_site_cpsat.py requires optional OR-Tools; "
            "install it outside the production environment"
        ) from error
    return cp_model


def load_guide(path: Path) -> dict[str, list[float]]:
    data = json.loads(path.read_text())
    if "top_0" in data:
        return data["top_0"]["placements"]
    return {
        refdes: row["center"] for refdes, row in data["selected_sites"].items()
    }


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def strict_convex_overlap_mask(first, second, displacement):
    first_vertices = np.asarray(first.exterior.coords[:-1], dtype=np.float64)
    second_vertices = np.asarray(second.exterior.coords[:-1], dtype=np.float64)
    edges = np.concatenate(
        (
            np.roll(first_vertices, -1, axis=0) - first_vertices,
            np.roll(second_vertices, -1, axis=0) - second_vertices,
        ),
        axis=0,
    )
    axes = np.column_stack((edges[:, 1], -edges[:, 0]))
    axes = axes[np.linalg.norm(axes, axis=1) > GEOMETRY_EPSILON]
    overlap = np.ones(len(displacement), dtype=bool)
    for axis in axes:
        first_projection = first_vertices @ axis
        second_projection = second_vertices @ axis
        translation = displacement @ axis
        overlap &= (
            translation + first_projection.max()
            > second_projection.min() + GEOMETRY_EPSILON
        ) & (
            second_projection.max()
            > translation + first_projection.min() + GEOMETRY_EPSILON
        )
        if not np.any(overlap):
            break
    return overlap


def acceptance_overlap_mask(first, second, dx_values, dy_values, area_epsilon):
    displacement = np.column_stack((dx_values, dy_values))
    positive = np.zeros(len(displacement), dtype=bool)
    for first_part in _convex_parts(first):
        for second_part in _convex_parts(second):
            positive |= strict_convex_overlap_mask(
                first_part, second_part, displacement
            )
    positive_indices = np.flatnonzero(positive)
    if not len(positive_indices):
        return positive
    displacements, inverse = np.unique(
        displacement[positive_indices], axis=0, return_inverse=True
    )
    accepted_conflicts = np.zeros(len(displacements), dtype=bool)
    for index, (displacement_x, displacement_y) in enumerate(displacements):
        moved = affinity.translate(
            first,
            xoff=float(displacement_x),
            yoff=float(displacement_y),
        )
        accepted_conflicts[index] = (
            float(moved.intersection(second).area) > area_epsilon
        )
    result = np.zeros(len(positive), dtype=bool)
    result[positive_indices] = accepted_conflicts[inverse]
    return result


def main() -> int:
    cp_model = _load_cp_model()
    args = Namespace(
        output_dir=Path("/tmp/m336_exact_site_cpsat_context"),
        assignment=ROOT
        / "results/m336/quality_assignment/"
        "m336_region_assignment.grid01.corrected.quality.json",
        grid_mm=float(os.environ.get("M336_GRID_MM", "0.1")),
        clearance_mm=0.0,
        bookshelf_dir=ROOT / "results/m336/bookshelf",
    )
    placedb, context = _load_context(args)
    area_epsilon = float(
        context.config.get("reporting", {}).get("area_epsilon_mm2", 1e-5)
    ) * abs(float(context.alignment.scale)) ** 2
    baseline_result = json.loads(
        (
            ROOT
            / "results/m336/baseline_warmstart_smoke/baseline/"
            "baseline-result.json"
        ).read_text()
    )
    baseline_hpwl = float(baseline_result["metrics"]["hpwl"])
    baseline_rsmt = float(baseline_result["metrics"]["rsmt"])
    baseline_x, baseline_y = _baseline_positions(
        placedb, args.bookshelf_dir / "m336.baseline.pl"
    )
    fixed_x, fixed_y = _select_fixed_endpoints(
        context, baseline_x, baseline_y, "runtime"
    )
    manual_baseline_endpoints = frozenset(
        value
        for value in os.environ.get(
            "M336_MANUAL_BASELINE_ENDPOINTS", "Q601"
        ).split(",")
        if value
    )
    fixed_x, fixed_y = _override_manual_baseline_endpoints(
        context,
        placedb,
        baseline_x,
        baseline_y,
        fixed_x,
        fixed_y,
        manual_baseline_endpoints,
    )

    controlled_ids = {constraint.node_id for constraint in context.constraints}
    obstacles = []
    for node_id in range(placedb.num_physical_nodes):
        if node_id in controlled_ids or not placedb.node_side_flag[node_id]:
            continue
        width = float(placedb.node_size_x[node_id])
        height = float(placedb.node_size_y[node_id])
        footprint = _fixed_footprint_local(
            context, placedb, node_id, "decomposed"
        )
        obstacles.append(
            affinity.translate(
                footprint,
                xoff=float(fixed_x[node_id]) + width / 2,
                yoff=float(fixed_y[node_id]) + height / 2,
            )
        )

    constraints = sorted(
        (row for row in context.constraints if row.side == "TOP"),
        key=lambda row: row.refdes,
    )
    use_baseline_guide = os.environ.get("M336_USE_BASELINE_GUIDE", "0") == "1"
    if use_baseline_guide:
        guide_paths = ["<manual-baseline>"]
        guides = [
            {
                constraint.refdes: [
                    float(baseline_x[constraint.node_id])
                    + constraint.node_width / 2,
                    float(baseline_y[constraint.node_id])
                    + constraint.node_height / 2,
                ]
                for constraint in constraints
            }
        ]
    else:
        guide_paths = [str(GUIDE)]
        guides = [load_guide(GUIDE)]
    guide_paths.extend(str(path) for path in ADDITIONAL_GUIDES)
    guides.extend(load_guide(path) for path in ADDITIONAL_GUIDES)

    candidate_limit = int(os.environ.get("M336_CANDIDATE_LIMIT", "512"))
    expanded_limit = int(os.environ.get("M336_EXPANDED_CANDIDATE_LIMIT", "0"))
    expanded_refdes = frozenset(
        value
        for value in os.environ.get("M336_EXPANDED_REFDES", "").split(",")
        if value
    )
    integer_scale = int(os.environ.get("M336_INTEGER_SCALE", "1000000"))
    interval_inset = int(os.environ.get("M336_INTERVAL_INSET", "1"))
    if interval_inset < 0:
        raise ValueError("interval inset must be non-negative")
    model = cp_model.CpModel()
    rows = []
    candidate_count = 0
    candidate_counts = {}
    conservative_bbox_refdes = []
    nonrect_mode = os.environ.get("M336_NONRECT_MODE", "exact")
    if nonrect_mode not in {"bbox", "exact"}:
        raise ValueError(f"unknown non-rectangle mode: {nonrect_mode}")
    nonrect_conflict_count = 0
    max_quantization_error = 0.0
    fix_guide = os.environ.get("M336_FIX_GUIDE", "0") == "1"
    movable_refdes = frozenset(
        value
        for value in os.environ.get("M336_MOVABLE_REFDES", "").split(",")
        if value
    )
    core_chain = os.environ.get("M336_CORE_CHAIN", "0") == "1"
    core_chain_max_steps = int(
        os.environ.get("M336_CORE_CHAIN_MAX_STEPS", "30")
    )
    if core_chain_max_steps <= 0:
        raise ValueError("core-chain max steps must be positive")
    known_refdes = {constraint.refdes for constraint in constraints}
    unknown_movable_refdes = movable_refdes - known_refdes
    if unknown_movable_refdes:
        raise ValueError(
            "unknown movable refdes: "
            + ", ".join(sorted(unknown_movable_refdes))
        )
    if movable_refdes and not fix_guide:
        raise ValueError("movable refdes require M336_FIX_GUIDE=1")
    if core_chain and not fix_guide:
        raise ValueError("core-chain mode requires M336_FIX_GUIDE=1")
    fixed_assumption_refdes = {}
    fixed_assumptions = {}
    guide_site_distances = {}
    build_started = time.perf_counter()

    for constraint in constraints:
        local = constraint.domain.footprint_local
        is_rectangle = _is_axis_aligned_rectangle(local)
        if not is_rectangle and nonrect_mode == "bbox":
            # A bounding box only removes solutions; it cannot admit a true
            # polygon overlap that NoOverlap2D would otherwise miss.
            conservative_bbox_refdes.append(constraint.refdes)
        eligible = _obstacle_free_candidate_indices(constraint, obstacles)
        centers = constraint.domain.valid_centers[eligible]
        orders = []
        for guide in guides:
            preferred = np.asarray(guide[constraint.refdes], dtype=np.float64)
            distances = np.square(centers - preferred).sum(axis=1)
            orders.append(np.lexsort((eligible, distances)))
        local_limit = (
            expanded_limit
            if expanded_limit and constraint.refdes in expanded_refdes
            else candidate_limit
        )
        if len(orders) == 1:
            order = orders[0]
            if local_limit:
                order = order[:local_limit]
        else:
            target_count = min(local_limit or len(eligible), len(eligible))
            selected = []
            seen = set()
            pointers = [0] * len(orders)
            while len(selected) < target_count:
                progressed = False
                for guide_index, current_order in enumerate(orders):
                    while pointers[guide_index] < len(current_order):
                        index = int(current_order[pointers[guide_index]])
                        pointers[guide_index] += 1
                        if index in seen:
                            continue
                        seen.add(index)
                        selected.append(index)
                        progressed = True
                        break
                    if len(selected) >= target_count:
                        break
                if not progressed:
                    break
            order = np.asarray(selected, dtype=np.int64)
        eligible = eligible[order]
        centers = centers[order]

        min_x, min_y, max_x, max_y = map(float, local.bounds)
        starts = np.column_stack((centers[:, 0] + min_x, centers[:, 1] + min_y))
        integer_starts = np.rint(starts * integer_scale).astype(np.int64)
        quantization_error = np.max(
            np.abs(integer_starts / integer_scale - starts), initial=0.0
        )
        max_quantization_error = max(max_quantization_error, quantization_error)
        integer_starts += interval_inset
        _, unique_indices = np.unique(integer_starts, axis=0, return_index=True)
        unique_indices.sort()
        integer_starts = integer_starts[unique_indices]
        centers = centers[unique_indices]
        eligible = eligible[unique_indices]
        guide_site_distances[constraint.refdes] = float(
            np.linalg.norm(
                centers[0]
                - np.asarray(guides[0][constraint.refdes], dtype=np.float64)
            )
        )

        width = int(round((max_x - min_x) * integer_scale)) - 2 * interval_inset
        height = int(round((max_y - min_y) * integer_scale)) - 2 * interval_inset
        if width <= 0 or height <= 0:
            raise ValueError(f"non-positive footprint size: {constraint.refdes}")
        x_var = model.new_int_var(
            int(integer_starts[:, 0].min()),
            int(integer_starts[:, 0].max()),
            f"{constraint.refdes}_x",
        )
        y_var = model.new_int_var(
            int(integer_starts[:, 1].min()),
            int(integer_starts[:, 1].max()),
            f"{constraint.refdes}_y",
        )
        site_var = model.new_int_var(
            0, len(integer_starts) - 1, f"{constraint.refdes}_site"
        )
        allowed = [
            (int(x), int(y), index)
            for index, (x, y) in enumerate(integer_starts)
        ]
        model.add_allowed_assignments([x_var, y_var, site_var], allowed)
        x_interval = model.new_fixed_size_interval_var(
            x_var, width, f"{constraint.refdes}_xi"
        )
        y_interval = model.new_fixed_size_interval_var(
            y_var, height, f"{constraint.refdes}_yi"
        )
        model.add_hint(x_var, int(integer_starts[0, 0]))
        model.add_hint(y_var, int(integer_starts[0, 1]))
        model.add_hint(site_var, 0)
        if fix_guide and constraint.refdes not in movable_refdes:
            assumption = model.new_bool_var(
                f"assume_fixed_{constraint.refdes}"
            )
            model.add_assumption(assumption)
            model.add(site_var == 0).only_enforce_if(assumption)
            fixed_assumption_refdes[assumption.index] = constraint.refdes
            fixed_assumptions[constraint.refdes] = assumption
        rows.append(
            {
                "constraint": constraint,
                "eligible": eligible,
                "centers": centers,
                "site_var": site_var,
                "footprint": local,
                "is_rectangle": is_rectangle,
                "integer_starts": integer_starts,
                "width": width,
                "height": height,
                "x_interval": x_interval,
                "y_interval": y_interval,
            }
        )
        candidate_count += len(centers)
        candidate_counts[constraint.refdes] = len(centers)

    no_overlap_rows = [
        row
        for row in rows
        if row["is_rectangle"] or nonrect_mode == "bbox"
    ]
    model.add_no_overlap_2d(
        [row["x_interval"] for row in no_overlap_rows],
        [row["y_interval"] for row in no_overlap_rows],
    )
    rectangle_audit = {
        "enabled": os.environ.get("M336_AUDIT_RECTANGLES", "1") == "1",
        "pair_count": 0,
        "candidate_pair_count": 0,
        "cp_false_positive_count": 0,
        "cp_false_negative_count": 0,
        "minimum_positive_overlap_area": None,
    }
    if rectangle_audit["enabled"]:
        rectangle_rows = [row for row in rows if row["is_rectangle"]]
        minimum_positive_area = None
        for first_index, first in enumerate(rectangle_rows):
            first_bounds = first["footprint"].bounds
            for second in rectangle_rows[first_index + 1 :]:
                second_bounds = second["footprint"].bounds
                first_centers = first["centers"]
                second_centers = second["centers"]
                overlap_x = np.maximum(
                    0.0,
                    np.minimum(
                        first_centers[:, None, 0] + first_bounds[2],
                        second_centers[None, :, 0] + second_bounds[2],
                    )
                    - np.maximum(
                        first_centers[:, None, 0] + first_bounds[0],
                        second_centers[None, :, 0] + second_bounds[0],
                    ),
                )
                overlap_y = np.maximum(
                    0.0,
                    np.minimum(
                        first_centers[:, None, 1] + first_bounds[3],
                        second_centers[None, :, 1] + second_bounds[3],
                    )
                    - np.maximum(
                        first_centers[:, None, 1] + first_bounds[1],
                        second_centers[None, :, 1] + second_bounds[1],
                    ),
                )
                overlap_area = overlap_x * overlap_y
                positive = overlap_area[overlap_area > 0.0]
                if len(positive):
                    current_minimum = float(positive.min())
                    minimum_positive_area = (
                        current_minimum
                        if minimum_positive_area is None
                        else min(minimum_positive_area, current_minimum)
                    )
                validator_conflicts = overlap_area > area_epsilon

                first_starts = first["integer_starts"]
                second_starts = second["integer_starts"]
                integer_overlap_x = (
                    np.minimum(
                        first_starts[:, None, 0] + first["width"],
                        second_starts[None, :, 0] + second["width"],
                    )
                    > np.maximum(
                        first_starts[:, None, 0],
                        second_starts[None, :, 0],
                    )
                )
                integer_overlap_y = (
                    np.minimum(
                        first_starts[:, None, 1] + first["height"],
                        second_starts[None, :, 1] + second["height"],
                    )
                    > np.maximum(
                        first_starts[:, None, 1],
                        second_starts[None, :, 1],
                    )
                )
                cp_conflicts = integer_overlap_x & integer_overlap_y
                rectangle_audit["pair_count"] += 1
                rectangle_audit["candidate_pair_count"] += overlap_area.size
                rectangle_audit["cp_false_positive_count"] += int(
                    np.count_nonzero(cp_conflicts & ~validator_conflicts)
                )
                rectangle_audit["cp_false_negative_count"] += int(
                    np.count_nonzero(~cp_conflicts & validator_conflicts)
                )
        rectangle_audit["minimum_positive_overlap_area"] = minimum_positive_area
    if nonrect_mode == "exact":
        for first_index, first in enumerate(rows):
            for second in rows[first_index + 1 :]:
                if first["is_rectangle"] and second["is_rectangle"]:
                    continue
                dx = (
                    first["centers"][:, None, 0]
                    - second["centers"][None, :, 0]
                )
                dy = (
                    first["centers"][:, None, 1]
                    - second["centers"][None, :, 1]
                )
                conflicts = acceptance_overlap_mask(
                    first["footprint"],
                    second["footprint"],
                    dx.ravel(),
                    dy.ravel(),
                    area_epsilon,
                ).reshape(dx.shape)
                first_sites, second_sites = np.nonzero(conflicts)
                if len(first_sites):
                    model.add_forbidden_assignments(
                        [first["site_var"], second["site_var"]],
                        [
                            (int(first_site), int(second_site))
                            for first_site, second_site in zip(
                                first_sites, second_sites
                            )
                        ],
                    )
                    nonrect_conflict_count += len(first_sites)
    candidate_domain_overlap_model_exact = (
        rectangle_audit["enabled"]
        and rectangle_audit["cp_false_positive_count"] == 0
        and rectangle_audit["cp_false_negative_count"] == 0
        and nonrect_mode == "exact"
    )
    minimize_guide_rank = os.environ.get("M336_MINIMIZE_GUIDE_RANK", "0") == "1"
    if minimize_guide_rank:
        model.minimize(sum(row["site_var"] for row in rows))
    build_seconds = time.perf_counter() - build_started

    max_time_in_seconds = float(os.environ.get("M336_TIME", "300"))
    max_deterministic_time = float(
        os.environ.get("M336_DETERMINISTIC_TIME", "0")
    )
    random_seed = int(os.environ.get("M336_SEED", "1000"))
    repair_hint = os.environ.get("M336_REPAIR_HINT", "0") == "1"
    hint_conflict_limit = int(
        os.environ.get("M336_HINT_CONFLICT_LIMIT", "10")
    )
    log_search_progress = os.environ.get("M336_LOG_SEARCH", "0") == "1"

    def new_solver():
        current_solver = cp_model.CpSolver()
        current_solver.parameters.max_time_in_seconds = max_time_in_seconds
        if max_deterministic_time > 0:
            current_solver.parameters.max_deterministic_time = (
                max_deterministic_time
            )
        current_solver.parameters.num_search_workers = 1
        current_solver.parameters.random_seed = random_seed
        current_solver.parameters.repair_hint = repair_hint
        current_solver.parameters.hint_conflict_limit = hint_conflict_limit
        current_solver.parameters.log_search_progress = log_search_progress
        return current_solver

    def extract_fixed_core(current_solver, current_status_code):
        current_core = []
        if (
            current_status_code == cp_model.INFEASIBLE
            and fixed_assumption_refdes
        ):
            for literal in (
                current_solver.sufficient_assumptions_for_infeasibility()
            ):
                literal = int(literal)
                index = literal if literal >= 0 else -literal - 1
                if index not in fixed_assumption_refdes:
                    raise ValueError(
                        "infeasibility core contains unknown assumption"
                    )
                current_core.append(fixed_assumption_refdes[index])
            current_core.sort()
        return current_core

    core_chain_steps = []
    released_refdes = set()
    total_solve_seconds = 0.0
    core_chain_stop_reason = None

    def write_progress(complete, stop_reason=None):
        progress = {
            "candidate_domain_overlap_model_exact": (
                candidate_domain_overlap_model_exact
            ),
            "complete": complete,
            "core_chain_steps": core_chain_steps,
            "guide_jsons": guide_paths,
            "initial_movable_refdes": sorted(movable_refdes),
            "output_json": str(OUTPUT),
            "released_refdes": sorted(released_refdes),
            "total_solve_seconds": total_solve_seconds,
        }
        if stop_reason is not None:
            progress["core_chain_stop_reason"] = stop_reason
        write_json_atomic(PROGRESS, progress)

    while True:
        active_fixed_refdes = sorted(
            set(fixed_assumptions) - released_refdes
        )
        solver = new_solver()
        solve_started = time.perf_counter()
        status_code = solver.solve(model)
        solve_seconds = time.perf_counter() - solve_started
        total_solve_seconds += solve_seconds
        status = solver.status_name(status_code)
        fixed_core = extract_fixed_core(solver, status_code)
        step_result = {
            "step": len(core_chain_steps),
            "status": status,
            "fixed_assumption_count": len(active_fixed_refdes),
            "fixed_refdes": active_fixed_refdes,
            "fixed_core": fixed_core,
            "solve_seconds": solve_seconds,
            "solver_wall_time": solver.wall_time,
            "solver_deterministic_time": (
                solver.response_proto.deterministic_time
            ),
            "solver_conflicts": solver.num_conflicts,
            "solver_branches": solver.num_branches,
        }
        core_chain_steps.append(step_result)
        write_progress(complete=False)
        print(
            "\nM336_CORE_CHAIN_STEP "
            + json.dumps({"core_chain_step": step_result}),
            flush=True,
        )
        if not core_chain:
            core_chain_stop_reason = "disabled"
            break
        if status_code != cp_model.INFEASIBLE:
            core_chain_stop_reason = status.lower()
            break
        if not fixed_core:
            core_chain_stop_reason = "empty_core"
            break
        if len(core_chain_steps) >= core_chain_max_steps:
            core_chain_stop_reason = "max_steps"
            break
        newly_released = set(fixed_core) - released_refdes
        if not newly_released:
            raise ValueError("core chain did not release a new assumption")
        model.clear_assumptions()
        for refdes in sorted(newly_released):
            model.add(fixed_assumptions[refdes] == 0)
        released_refdes.update(newly_released)
        model.add_assumptions(
            fixed_assumptions[refdes]
            for refdes in sorted(set(fixed_assumptions) - released_refdes)
        )
        write_progress(complete=False)

    selected_sites = None
    legality = None
    hpwl = None
    score = None
    if status_code in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        source = json.loads(SOURCE.read_text())
        node_x = np.asarray(placedb.node_x, dtype=np.float64).copy()
        node_y = np.asarray(placedb.node_y, dtype=np.float64).copy()
        node_x[: placedb.num_physical_nodes] = baseline_x
        node_y[: placedb.num_physical_nodes] = baseline_y
        for node_id in range(placedb.num_physical_nodes):
            if node_id not in controlled_ids:
                node_x[node_id] = fixed_x[node_id]
                node_y[node_id] = fixed_y[node_id]
        top_rows = {row["constraint"].refdes: row for row in rows}
        selected_sites = {}
        for constraint in context.constraints:
            center = np.asarray(
                source["selected_sites"][constraint.refdes]["center"],
                dtype=np.float64,
            )
            if constraint.side == "TOP":
                row = top_rows[constraint.refdes]
                selected = int(solver.value(row["site_var"]))
                center = row["centers"][selected]
                selected_sites[constraint.refdes] = {
                    "candidate_index": selected,
                    "region_candidate_index": int(row["eligible"][selected]),
                    "center": center.tolist(),
                }
            node_x[constraint.node_id] = center[0] - constraint.node_width / 2
            node_y[constraint.node_id] = center[1] - constraint.node_height / 2
        position = torch.from_numpy(np.concatenate((node_x, node_y)))
        legality = context.exact_report(position, placedb)
        hpwl = float(placedb.hpwl(node_x, node_y))
        score = 2.0 / (hpwl / baseline_hpwl + hpwl / baseline_rsmt)

    result = {
        "status": status,
        "source_json": str(SOURCE),
        "guide_json": guide_paths[0],
        "guide_jsons": guide_paths,
        "manual_baseline_endpoints": sorted(manual_baseline_endpoints),
        "guide_site_distances": guide_site_distances,
        "fix_guide": fix_guide,
        "movable_refdes": sorted(movable_refdes),
        "effective_movable_refdes": sorted(movable_refdes | released_refdes),
        "initial_fixed_assumption_count": len(fixed_assumption_refdes),
        "initial_fixed_refdes": sorted(fixed_assumptions),
        "fixed_assumption_count": len(active_fixed_refdes),
        "fixed_refdes": active_fixed_refdes,
        "fixed_core": fixed_core,
        "core_chain": core_chain,
        "core_chain_max_steps": core_chain_max_steps,
        "core_chain_released_refdes": sorted(released_refdes),
        "core_chain_steps": core_chain_steps,
        "core_chain_stop_reason": core_chain_stop_reason,
        "grid_mm": args.grid_mm,
        "candidate_limit": candidate_limit,
        "expanded_candidate_limit": expanded_limit,
        "expanded_refdes": sorted(expanded_refdes),
        "candidate_count": candidate_count,
        "candidate_counts": candidate_counts,
        "conservative_bbox_refdes": conservative_bbox_refdes,
        "nonrect_mode": nonrect_mode,
        "nonrect_refdes": sorted(
            row["constraint"].refdes
            for row in rows
            if not row["is_rectangle"]
        ),
        "nonrect_conflict_count": nonrect_conflict_count,
        "area_epsilon": area_epsilon,
        "rectangle_equivalence_audit": rectangle_audit,
        "candidate_domain_overlap_model_exact": (
            candidate_domain_overlap_model_exact
        ),
        "ortools_version": metadata.version("ortools"),
        "integer_scale": integer_scale,
        "interval_inset": interval_inset,
        "max_quantization_error": max_quantization_error,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "total_solve_seconds": total_solve_seconds,
        "solver_wall_time": solver.wall_time,
        "solver_deterministic_time": solver.response_proto.deterministic_time,
        "solver_conflicts": solver.num_conflicts,
        "solver_branches": solver.num_branches,
        "solver_parameters": {
            "hint_conflict_limit": hint_conflict_limit,
            "max_deterministic_time": max_deterministic_time,
            "max_time_in_seconds": max_time_in_seconds,
            "minimize_guide_rank": minimize_guide_rank,
            "num_search_workers": 1,
            "preprocess_threads": PREPROCESS_THREADS,
            "random_seed": random_seed,
            "repair_hint": repair_hint,
        },
        "solver_response_stats": solver.response_stats(),
        "legality": legality,
        "hpwl": hpwl,
        "normalized_score_upper_bound": score,
        "selected_sites": selected_sites,
    }
    write_json_atomic(OUTPUT, result)
    write_progress(complete=True, stop_reason=core_chain_stop_reason)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "candidate_count",
                    "build_seconds",
                    "solve_seconds",
                    "legality",
                    "hpwl",
                    "normalized_score_upper_bound",
                )
            },
            indent=2,
        )
    )
    return 0 if status_code in (cp_model.FEASIBLE, cp_model.OPTIMAL) else 2


if __name__ == "__main__":
    raise SystemExit(main())
