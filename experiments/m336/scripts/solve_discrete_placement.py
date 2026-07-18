#!/usr/bin/env python3
"""Solve a fixed M336 assignment on exact keep-in grid sites with CP-SAT."""

from __future__ import annotations

import argparse
from importlib import metadata
import json
import math
from pathlib import Path

import numpy as np
import torch
from shapely.geometry import box

from analyze_quality_bound import (
    _baseline_positions,
    _load_context,
    _runtime_fixed_positions,
)
from run_matrix import REPO_ROOT, repo_path, sha256_file, write_json


def _load_cp_model():
    try:
        from ortools.sat.python import cp_model
    except ImportError as error:
        raise RuntimeError(
            "solve_discrete_placement.py requires optional OR-Tools; "
            "install it outside the production environment"
        ) from error
    return cp_model


def _decode(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _scaled(value, scale):
    result = int(round(float(value) * scale))
    if abs(result) >= 2**62:
        raise OverflowError("scaled coordinate exceeds CP-SAT integer range")
    return result


def _score_hpwl_limit(baseline_hpwl, baseline_rsmt, minimum_score):
    return 2.0 * baseline_hpwl * baseline_rsmt / (
        minimum_score * (baseline_hpwl + baseline_rsmt)
    )


def _hpwl_rounding_allowance_units(net_weights):
    """Bound HPWL inflation from separately rounded positions and offsets."""
    total_weight = 0
    for weight in net_weights:
        weight = float(weight)
        if (
            not math.isfinite(weight)
            or weight < 0
            or not math.isclose(weight, round(weight), abs_tol=1e-12)
        ):
            raise ValueError("CP-SAT requires non-negative integral net weights")
        total_weight += int(round(weight))
    # Each pin coordinate has at most one scaled unit of error. Max-minus-min
    # can grow by two units per axis, hence four units per weighted net.
    return 4 * total_weight


def _is_rectangle(shape, epsilon=1e-9):
    return box(*shape.bounds).difference(shape).area <= epsilon


def _convex_vertices(shape, node_width, node_height, integer_scale):
    hull = shape.convex_hull
    return tuple(
        (
            _scaled(x + node_width / 2, integer_scale),
            _scaled(y + node_height / 2, integer_scale),
        )
        for x, y in list(hull.exterior.coords)[:-1]
    )


def _separating_axes(*vertex_sets):
    axes = set()
    for vertices in vertex_sets:
        for first, second in zip(vertices, vertices[1:] + vertices[:1]):
            edge_x = second[0] - first[0]
            edge_y = second[1] - first[1]
            normal_x, normal_y = edge_y, -edge_x
            divisor = math.gcd(abs(normal_x), abs(normal_y))
            if divisor:
                normal_x //= divisor
                normal_y //= divisor
            if normal_x < 0 or (normal_x == 0 and normal_y < 0):
                normal_x = -normal_x
                normal_y = -normal_y
            if normal_x or normal_y:
                axes.add((normal_x, normal_y))
    return tuple(sorted(axes))


def _add_convex_nonoverlap(model, first, second):
    literals = []
    for axis_index, (normal_x, normal_y) in enumerate(
        _separating_axes(first["vertices"], second["vertices"])
    ):
        first_projection = [
            normal_x * x + normal_y * y for x, y in first["vertices"]
        ]
        second_projection = [
            normal_x * x + normal_y * y for x, y in second["vertices"]
        ]
        first_before = model.new_bool_var(
            "%s_before_%s_axis_%d"
            % (first["name"], second["name"], axis_index)
        )
        second_before = model.new_bool_var(
            "%s_before_%s_axis_%d"
            % (second["name"], first["name"], axis_index)
        )
        first_translation = (
            normal_x * first["x"] + normal_y * first["y"]
        )
        second_translation = (
            normal_x * second["x"] + normal_y * second["y"]
        )
        model.add(
            first_translation + max(first_projection)
            <= second_translation + min(second_projection)
        ).only_enforce_if(first_before)
        model.add(
            second_translation + max(second_projection)
            <= first_translation + min(first_projection)
        ).only_enforce_if(second_before)
        literals.extend((first_before, second_before))
    model.add_bool_or(literals)


def _build_model(
    cp_model,
    placedb,
    context,
    baseline_x,
    baseline_y,
    minimum_score,
    baseline_hpwl,
    baseline_rsmt,
    integer_scale,
    collision_mode,
):
    model = cp_model.CpModel()
    fixed_x, fixed_y = _runtime_fixed_positions(
        context, baseline_x, baseline_y
    )
    constraint_by_node = {
        constraint.node_id: constraint for constraint in context.constraints
    }
    site_vars = {}
    x_vars = {}
    y_vars = {}
    candidate_count = 0
    x_intervals = {"TOP": [], "BOTTOM": []}
    y_intervals = {"TOP": [], "BOTTOM": []}
    controlled_shapes = {"TOP": [], "BOTTOM": []}

    for constraint in sorted(context.constraints, key=lambda item: item.refdes):
        node_id = constraint.node_id
        centers = constraint.domain.valid_centers
        x_values = np.rint(
            (centers[:, 0] - constraint.node_width / 2) * integer_scale
        ).astype(np.int64)
        y_values = np.rint(
            (centers[:, 1] - constraint.node_height / 2) * integer_scale
        ).astype(np.int64)
        site = model.new_int_var(0, len(centers) - 1, "site_%s" % constraint.refdes)
        x_var = model.new_int_var(
            int(x_values.min()), int(x_values.max()), "x_%s" % constraint.refdes
        )
        y_var = model.new_int_var(
            int(y_values.min()), int(y_values.max()), "y_%s" % constraint.refdes
        )
        model.add_element(site, x_values.tolist(), x_var)
        model.add_element(site, y_values.tolist(), y_var)
        site_vars[node_id] = site
        x_vars[node_id] = x_var
        y_vars[node_id] = y_var
        candidate_count += len(centers)

        local_min_x, local_min_y, local_max_x, local_max_y = (
            constraint.domain.footprint_local.bounds
        )
        x_offset = _scaled(
            constraint.node_width / 2 + local_min_x, integer_scale
        )
        y_offset = _scaled(
            constraint.node_height / 2 + local_min_y, integer_scale
        )
        width = max(1, _scaled(local_max_x - local_min_x, integer_scale))
        height = max(1, _scaled(local_max_y - local_min_y, integer_scale))
        x_start = x_var + x_offset
        y_start = y_var + y_offset
        is_rectangle = _is_rectangle(constraint.domain.footprint_local)
        if is_rectangle:
            x_intervals[constraint.side].append(
                model.new_fixed_size_interval_var(
                    x_start, width, "ix_%s" % constraint.refdes
                )
            )
            y_intervals[constraint.side].append(
                model.new_fixed_size_interval_var(
                    y_start, height, "iy_%s" % constraint.refdes
                )
            )
        controlled_shapes[constraint.side].append(
            {
                "name": constraint.refdes,
                "x": x_var,
                "y": y_var,
                "bbox_x": x_start,
                "bbox_y": y_start,
                "width": width,
                "height": height,
                "is_rectangle": is_rectangle,
                "vertices": _convex_vertices(
                    constraint.domain.footprint_local,
                    constraint.node_width,
                    constraint.node_height,
                    integer_scale,
                ),
            }
        )

        target = np.asarray(
            [
                baseline_x[node_id] + constraint.node_width / 2,
                baseline_y[node_id] + constraint.node_height / 2,
            ]
        )
        nearest = int(
            np.argmin(np.square(centers - target).sum(axis=1))
        )
        model.add_hint(site, nearest)

    constrained_ids = set(constraint_by_node)
    if collision_mode == "convex":
        for node_id in range(placedb.num_physical_nodes):
            if node_id in constrained_ids:
                continue
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            name = _decode(placedb.node_names[node_id])
            fixed_start_x = _scaled(fixed_x[node_id], integer_scale)
            fixed_start_y = _scaled(fixed_y[node_id], integer_scale)
            fixed_width = max(
                1, _scaled(placedb.node_size_x[node_id], integer_scale)
            )
            fixed_height = max(
                1, _scaled(placedb.node_size_y[node_id], integer_scale)
            )
            fixed_shape = {
                "name": name,
                "x": fixed_start_x,
                "y": fixed_start_y,
                "width": fixed_width,
                "height": fixed_height,
                "is_rectangle": True,
                "vertices": (
                    (0, 0),
                    (fixed_width, 0),
                    (fixed_width, fixed_height),
                    (0, fixed_height),
                ),
            }
            for controlled in controlled_shapes[side]:
                if not controlled["is_rectangle"]:
                    _add_convex_nonoverlap(model, controlled, fixed_shape)
                    continue
                refdes = controlled["name"]
                x_start = controlled["bbox_x"]
                y_start = controlled["bbox_y"]
                width = controlled["width"]
                height = controlled["height"]
                left = model.new_bool_var("%s_left_of_%s" % (refdes, name))
                right = model.new_bool_var("%s_right_of_%s" % (refdes, name))
                below = model.new_bool_var("%s_below_%s" % (refdes, name))
                above = model.new_bool_var("%s_above_%s" % (refdes, name))
                model.add(x_start + width <= fixed_start_x).only_enforce_if(left)
                model.add(
                    fixed_start_x + fixed_width <= x_start
                ).only_enforce_if(right)
                model.add(y_start + height <= fixed_start_y).only_enforce_if(below)
                model.add(
                    fixed_start_y + fixed_height <= y_start
                ).only_enforce_if(above)
                model.add_bool_or((left, right, below, above))

        for side in ("TOP", "BOTTOM"):
            model.add_no_overlap_2d(x_intervals[side], y_intervals[side])
            shapes = controlled_shapes[side]
            for first_index, first in enumerate(shapes):
                for second in shapes[first_index + 1 :]:
                    if first["is_rectangle"] and second["is_rectangle"]:
                        continue
                    _add_convex_nonoverlap(model, first, second)

    net_spans = []
    populated_net_weights = []
    coordinate_limit = 2**50
    for net_id, pins in enumerate(placedb.net2pin_map):
        pin_x = []
        pin_y = []
        for pin_id in pins:
            node_id = int(placedb.pin2node_map[pin_id])
            x_offset = _scaled(placedb.pin_offset_x[pin_id], integer_scale)
            y_offset = _scaled(placedb.pin_offset_y[pin_id], integer_scale)
            if node_id in constraint_by_node:
                pin_x.append(x_vars[node_id] + x_offset)
                pin_y.append(y_vars[node_id] + y_offset)
            else:
                pin_x.append(_scaled(fixed_x[node_id], integer_scale) + x_offset)
                pin_y.append(_scaled(fixed_y[node_id], integer_scale) + y_offset)
        if not pin_x:
            continue
        net_name = _decode(placedb.net_names[net_id])
        max_x = model.new_int_var(-coordinate_limit, coordinate_limit, "max_x_%s" % net_id)
        min_x = model.new_int_var(-coordinate_limit, coordinate_limit, "min_x_%s" % net_id)
        max_y = model.new_int_var(-coordinate_limit, coordinate_limit, "max_y_%s" % net_id)
        min_y = model.new_int_var(-coordinate_limit, coordinate_limit, "min_y_%s" % net_id)
        model.add_max_equality(max_x, pin_x)
        model.add_min_equality(min_x, pin_x)
        model.add_max_equality(max_y, pin_y)
        model.add_min_equality(min_y, pin_y)
        weight = float(placedb.net_weights[net_id])
        if (
            weight < 0
            or not math.isclose(weight, round(weight), abs_tol=1e-12)
        ):
            raise ValueError("CP-SAT requires integral net weights: %s" % net_name)
        integral_weight = int(round(weight))
        populated_net_weights.append(integral_weight)
        net_spans.append(integral_weight * (max_x - min_x + max_y - min_y))

    hpwl_objective = sum(net_spans)
    hpwl_limit = _score_hpwl_limit(
        baseline_hpwl, baseline_rsmt, minimum_score
    )
    rounding_allowance = _hpwl_rounding_allowance_units(
        populated_net_weights
    )
    hpwl_limit_integer = (
        math.floor(hpwl_limit * integer_scale) + rounding_allowance
    )
    model.add(hpwl_objective <= hpwl_limit_integer)
    model.minimize(hpwl_objective)
    return model, {
        "site_vars": site_vars,
        "fixed_x": fixed_x,
        "fixed_y": fixed_y,
        "hpwl_limit": hpwl_limit,
        "hpwl_limit_integer": hpwl_limit_integer,
        "hpwl_rounding_allowance_integer": rounding_allowance,
        "hpwl_rounding_allowance": rounding_allowance / integer_scale,
        "candidate_count": candidate_count,
        "controlled_node_count": len(constraint_by_node),
        "fixed_node_count": placedb.num_physical_nodes - len(constraint_by_node),
    }


def solve(args):
    cp_model = _load_cp_model()
    ortools_version = metadata.version("ortools")
    baseline_result = json.loads(args.baseline_result.read_text())
    baseline_hpwl = float(baseline_result["metrics"]["hpwl"])
    baseline_rsmt = float(baseline_result["metrics"]["rsmt"])
    placedb, context = _load_context(args)
    baseline_x, baseline_y = _baseline_positions(
        placedb, args.bookshelf_dir / "m336.baseline.pl"
    )
    model, state = _build_model(
        cp_model,
        placedb,
        context,
        baseline_x,
        baseline_y,
        args.minimum_score,
        baseline_hpwl,
        baseline_rsmt,
        args.integer_scale,
        args.collision_mode,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.time_limit
    solver.parameters.num_search_workers = args.workers
    solver.parameters.random_seed = args.seed
    solver.parameters.log_search_progress = args.log_search_progress
    if args.workers == 1:
        solver.parameters.max_deterministic_time = args.deterministic_time
    status = solver.solve(model)
    status_name = solver.status_name(status)
    input_sha256 = {
        "assignment": sha256_file(args.assignment),
        "baseline_result": sha256_file(args.baseline_result),
        "baseline_placement": sha256_file(
            args.bookshelf_dir / "m336.baseline.pl"
        ),
    }
    solver_report = {
        "status": status_name,
        "objective_hpwl": (
            solver.objective_value / args.integer_scale
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None
        ),
        "best_objective_bound_hpwl": solver.best_objective_bound
        / args.integer_scale,
        "wall_time_seconds": solver.wall_time,
        "branches": solver.num_branches,
        "conflicts": solver.num_conflicts,
        "workers": args.workers,
        "random_seed": args.seed,
        "max_time_seconds": args.time_limit,
        "max_deterministic_time": (
            args.deterministic_time if args.workers == 1 else None
        ),
        "ortools_version": ortools_version,
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        write_json(
            args.output,
            {
                "schema": "m336_discrete_placement_v1",
                "assignment": repo_path(args.assignment),
                "input_sha256": input_sha256,
                "solver": solver_report,
                "model": {
                    "integer_scale": args.integer_scale,
                    "constraint_grid_mm": args.grid_mm,
                    "minimum_score": args.minimum_score,
                    "necessary_hpwl_limit": state["hpwl_limit"],
                    "integer_hpwl_limit": state["hpwl_limit_integer"],
                    "hpwl_rounding_allowance": state[
                        "hpwl_rounding_allowance"
                    ],
                    "candidate_count": state["candidate_count"],
                    "controlled_node_count": state["controlled_node_count"],
                    "fixed_node_count": state["fixed_node_count"],
                    "collision_mode": args.collision_mode,
                    "geometry_model": (
                        "rectangles plus convex hull separating axes"
                        if args.collision_mode == "convex"
                        else "collision constraints disabled for lower bound"
                    ),
                },
            },
        )
        raise RuntimeError("CP-SAT placement failed: %s" % status_name)

    node_x = np.asarray(placedb.node_x, dtype=np.float64).copy()
    node_y = np.asarray(placedb.node_y, dtype=np.float64).copy()
    node_x[: placedb.num_physical_nodes] = baseline_x
    node_y[: placedb.num_physical_nodes] = baseline_y
    for node_id in range(placedb.num_physical_nodes):
        if node_id not in state["site_vars"]:
            node_x[node_id] = state["fixed_x"][node_id]
            node_y[node_id] = state["fixed_y"][node_id]

    selected_sites = {}
    constraints = {item.node_id: item for item in context.constraints}
    for node_id, site_var in state["site_vars"].items():
        site_index = int(solver.value(site_var))
        constraint = constraints[node_id]
        center = constraint.domain.valid_centers[site_index]
        node_x[node_id] = center[0] - constraint.node_width / 2
        node_y[node_id] = center[1] - constraint.node_height / 2
        selected_sites[constraint.refdes] = {
            "candidate_index": site_index,
            "center": [float(center[0]), float(center[1])],
            "lower_left": [float(node_x[node_id]), float(node_y[node_id])],
            "region_id": constraint.region_id,
            "side": constraint.side,
        }

    position = torch.from_numpy(np.concatenate((node_x, node_y)))
    legality = context.exact_report(position, placedb)
    hpwl = float(placedb.hpwl(node_x, node_y))
    score_upper_bound = 2.0 / (
        hpwl / baseline_hpwl + hpwl / baseline_rsmt
    )
    result = {
        "schema": "m336_discrete_placement_v1",
        "assignment": repo_path(args.assignment),
        "input_sha256": input_sha256,
        "model": {
            "integer_scale": args.integer_scale,
            "constraint_grid_mm": args.grid_mm,
            "minimum_score": args.minimum_score,
            "necessary_hpwl_limit": state["hpwl_limit"],
            "integer_hpwl_limit": state["hpwl_limit_integer"],
            "hpwl_rounding_allowance": state["hpwl_rounding_allowance"],
            "candidate_count": state["candidate_count"],
            "controlled_node_count": state["controlled_node_count"],
            "fixed_node_count": state["fixed_node_count"],
            "geometry_model": (
                "rectangles plus convex hull separating axes"
                if args.collision_mode == "convex"
                else "collision constraints disabled for lower bound"
            ),
            "collision_mode": args.collision_mode,
        },
        "solver": solver_report,
        "metrics": {
            "hpwl": hpwl,
            "baseline_hpwl": baseline_hpwl,
            "baseline_rsmt": baseline_rsmt,
            "normalized_score_upper_bound": score_upper_bound,
        },
        "legality": legality,
        "selected_sites": selected_sites,
    }
    write_json(args.output, result)
    if legality["keepin_violation_count"] or legality["overlap_pair_count"]:
        raise RuntimeError("CP-SAT placement failed exact geometry validation")
    if score_upper_bound + 1e-12 < args.minimum_score:
        raise RuntimeError("CP-SAT placement failed the necessary HPWL score gate")
    args.placement.parent.mkdir(parents=True, exist_ok=True)
    placedb.write_pl(None, str(args.placement), node_x, node_y)
    result["placement"] = repo_path(args.placement)
    write_json(args.output, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bookshelf-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/bookshelf",
    )
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument(
        "--baseline-result",
        type=Path,
        default=REPO_ROOT
        / "results/m336/baseline_warmstart_smoke/baseline/baseline-result.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/discrete_placement/context",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "results/m336/discrete_placement/result.json",
    )
    parser.add_argument(
        "--placement",
        type=Path,
        default=REPO_ROOT / "results/m336/discrete_placement/m336.cp.pl",
    )
    parser.add_argument("--grid-mm", type=float, default=0.05)
    parser.add_argument("--clearance-mm", type=float, default=0.0)
    parser.add_argument("--minimum-score", type=float, default=1.0)
    parser.add_argument(
        "--collision-mode",
        choices=("convex", "none"),
        default="convex",
        help="'none' omits collisions and is only a lower-bound diagnostic",
    )
    parser.add_argument("--integer-scale", type=int, default=1000000)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--deterministic-time", type=float, default=300.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--log-search-progress", action="store_true")
    args = parser.parse_args()
    for name in (
        "bookshelf_dir",
        "assignment",
        "baseline_result",
        "output_dir",
        "output",
        "placement",
    ):
        setattr(args, name, getattr(args, name).resolve())
    if args.integer_scale <= 0 or args.time_limit <= 0 or args.workers <= 0:
        parser.error("integer scale, time limit, and workers must be positive")
    for path in (
        args.bookshelf_dir / "m336.aux",
        args.bookshelf_dir / "m336.baseline.pl",
        args.assignment,
        args.baseline_result,
    ):
        if not path.exists():
            parser.error("required input does not exist: %s" % path)
    result = solve(args)
    print(
        json.dumps(
            {
                "placement": result["placement"],
                "solver": result["solver"],
                "metrics": result["metrics"],
                "legality": {
                    "keepin_violation_count": result["legality"][
                        "keepin_violation_count"
                    ],
                    "overlap_pair_count": result["legality"][
                        "overlap_pair_count"
                    ],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
