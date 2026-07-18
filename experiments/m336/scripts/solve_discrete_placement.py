#!/usr/bin/env python3
"""Solve a fixed M336 assignment on exact keep-in grid sites with CP-SAT."""

from __future__ import annotations

import argparse
import copy
from dataclasses import replace
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
from optimize_assignment import _candidate_domains, _template_data
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


def _fixed_assignment_space(context, assignment_path):
    template = json.loads(assignment_path.read_text())
    preferred_regions = {
        row["subgroup_id"]: row["proposed_region_id"]
        for row in template["assignments"]
    }
    group_options = {
        group_id: (region_id,)
        for group_id, region_id in preferred_regions.items()
    }
    group_nodes = {group_id: [] for group_id in group_options}
    node_groups = {}
    domains = {}
    for constraint in context.constraints:
        group_id = constraint.subgroup_id
        if preferred_regions.get(group_id) != constraint.region_id:
            raise ValueError(
                "context assignment differs from input row: %s" % group_id
            )
        group_nodes[group_id].append(constraint)
        node_groups[constraint.node_id] = group_id
        domains[(constraint.node_id, constraint.region_id)] = constraint.domain
    return {
        "mode": "fixed",
        "template": template,
        "group_options": group_options,
        "group_nodes": {
            group_id: tuple(nodes) for group_id, nodes in group_nodes.items()
        },
        "group_areas": {group_id: 0.0 for group_id in group_options},
        "region_capacities": {},
        "node_groups": node_groups,
        "domains": domains,
        "preferred_regions": preferred_regions,
    }


def _optimized_assignment_space(args, context):
    template = _template_data(args.assignment)
    group_options, group_nodes, group_areas, domains = _candidate_domains(
        context,
        template,
        args.clearance_mm,
        ignore_candidate_exclusions=False,
    )
    preferred_regions = {
        row["subgroup_id"]: row["proposed_region_id"]
        for row in template["assignments"]
    }
    capacity_ratios = {
        region_id: float(value)
        for region_id, value in template["method"]["capacity_ratios"].items()
    }
    region_capacities = (
        {}
        if args.ignore_area_capacity
        else {
            region_id: float(row["free_area_after_anchors_mm2"])
            * capacity_ratios[region_id]
            for region_id, row in template["capacity_diagnostics"].items()
        }
    )
    node_groups = {
        constraint.node_id: group_id
        for group_id, constraints in group_nodes.items()
        for constraint in constraints
    }
    expected = {constraint.node_id for constraint in context.constraints}
    if set(node_groups) != expected:
        raise ValueError("assignment search does not cover every controlled node")
    return {
        "mode": "optimized",
        "template": template,
        "group_options": group_options,
        "group_nodes": group_nodes,
        "group_areas": group_areas,
        "region_capacities": region_capacities,
        "capacity_ratios": capacity_ratios,
        "ignore_area_capacity": args.ignore_area_capacity,
        "node_groups": node_groups,
        "domains": domains,
        "preferred_regions": preferred_regions,
    }


def _capacity_integer_bounds(group_areas, region_capacities, scale):
    if scale <= 0:
        raise ValueError("capacity scale must be positive")
    area_units = {
        group_id: int(math.ceil(float(area) * scale - 1e-12))
        for group_id, area in group_areas.items()
    }
    capacity_units = {
        region_id: int(math.floor(float(capacity) * scale + 1e-12))
        for region_id, capacity in region_capacities.items()
    }
    if any(value < 0 for value in area_units.values()) or any(
        value < 0 for value in capacity_units.values()
    ):
        raise ValueError("assignment areas and capacities must be non-negative")
    return area_units, capacity_units


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


def _add_assignment_variables(model, assignment_space, capacity_scale):
    group_vars = {}
    option_literals = {}
    for group_id in sorted(assignment_space["group_options"]):
        options = assignment_space["group_options"][group_id]
        if not options:
            raise ValueError("subgroup has no assignment option: %s" % group_id)
        group_var = model.new_int_var(
            0, len(options) - 1, "region_%s" % group_id
        )
        literals = []
        for option_index, region_id in enumerate(options):
            literal = model.new_bool_var(
                "assign_%s_%s" % (group_id, region_id)
            )
            literals.append(literal)
            option_literals[(group_id, region_id)] = literal
        model.add_exactly_one(literals)
        model.add(
            group_var
            == sum(index * literal for index, literal in enumerate(literals))
        )
        preferred_region = assignment_space["preferred_regions"][group_id]
        if preferred_region not in options:
            raise ValueError(
                "preferred region is not eligible for subgroup: %s" % group_id
            )
        preferred_index = options.index(preferred_region)
        model.add_hint(group_var, preferred_index)
        if not assignment_space["group_nodes"][group_id]:
            model.add(group_var == preferred_index)
        group_vars[group_id] = group_var

    area_units, capacity_units = _capacity_integer_bounds(
        assignment_space["group_areas"],
        assignment_space["region_capacities"],
        capacity_scale,
    )
    for region_id, capacity in sorted(capacity_units.items()):
        terms = [
            area_units[group_id] * option_literals[(group_id, region_id)]
            for group_id, options in assignment_space["group_options"].items()
            if region_id in options and area_units[group_id]
        ]
        model.add(sum(terms) <= capacity)
    return {
        "group_vars": group_vars,
        "option_literals": option_literals,
        "option_count": len(option_literals),
        "capacity_scale": capacity_scale,
        "area_units": area_units,
        "capacity_units": capacity_units,
    }


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
    assignment_space,
    capacity_scale,
):
    model = cp_model.CpModel()
    assignment_state = _add_assignment_variables(
        model, assignment_space, capacity_scale
    )
    fixed_x, fixed_y = _runtime_fixed_positions(
        context, baseline_x, baseline_y
    )
    constraint_by_node = {
        constraint.node_id: constraint for constraint in context.constraints
    }
    site_vars = {}
    site_choices = {}
    x_vars = {}
    y_vars = {}
    candidate_count = 0
    x_intervals = {"TOP": [], "BOTTOM": []}
    y_intervals = {"TOP": [], "BOTTOM": []}
    controlled_shapes = {"TOP": [], "BOTTOM": []}

    for constraint in sorted(context.constraints, key=lambda item: item.refdes):
        node_id = constraint.node_id
        group_id = assignment_space["node_groups"][node_id]
        options = assignment_space["group_options"][group_id]
        domain_options = [
            assignment_space["domains"][(node_id, region_id)]
            for region_id in options
        ]
        footprint_shapes = {
            domain.footprint_local.wkb_hex for domain in domain_options
        }
        if len(footprint_shapes) != 1:
            raise ValueError(
                "candidate regions changed the effective footprint: %s"
                % constraint.refdes
            )
        centers = np.concatenate(
            [domain.valid_centers for domain in domain_options], axis=0
        )
        region_indices = np.concatenate(
            [
                np.full(len(domain.valid_centers), index, dtype=np.int64)
                for index, domain in enumerate(domain_options)
            ]
        )
        local_indices = np.concatenate(
            [
                np.arange(len(domain.valid_centers), dtype=np.int64)
                for domain in domain_options
            ]
        )
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
        model.add_element(
            site,
            region_indices.tolist(),
            assignment_state["group_vars"][group_id],
        )
        site_vars[node_id] = site
        site_choices[node_id] = {
            "centers": centers,
            "region_indices": region_indices,
            "local_indices": local_indices,
            "regions": options,
        }
        x_vars[node_id] = x_var
        y_vars[node_id] = y_var
        candidate_count += len(centers)

        footprint_local = domain_options[0].footprint_local
        local_min_x, local_min_y, local_max_x, local_max_y = (
            footprint_local.bounds
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
        is_rectangle = _is_rectangle(footprint_local)
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
                    footprint_local,
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
        preferred_region_index = options.index(
            assignment_space["preferred_regions"][group_id]
        )
        preferred_candidates = np.flatnonzero(
            region_indices == preferred_region_index
        )
        nearest = int(
            preferred_candidates[
                np.argmin(
                    np.square(centers[preferred_candidates] - target).sum(axis=1)
                )
            ]
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
        "site_choices": site_choices,
        "assignment": assignment_state,
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


def _model_report(args, state, assignment_space):
    assignment_state = state["assignment"]
    return {
        "integer_scale": args.integer_scale,
        "constraint_grid_mm": args.grid_mm,
        "minimum_score": args.minimum_score,
        "necessary_hpwl_limit": state["hpwl_limit"],
        "integer_hpwl_limit": state["hpwl_limit_integer"],
        "hpwl_rounding_allowance": state["hpwl_rounding_allowance"],
        "candidate_count": state["candidate_count"],
        "controlled_node_count": state["controlled_node_count"],
        "fixed_node_count": state["fixed_node_count"],
        "assignment_mode": assignment_space["mode"],
        "assignment_group_count": len(assignment_state["group_vars"]),
        "assignment_option_count": assignment_state["option_count"],
        "assignment_options": {
            group_id: list(options)
            for group_id, options in sorted(
                assignment_space["group_options"].items()
            )
        },
        "ignore_area_capacity": assignment_space.get(
            "ignore_area_capacity", False
        ),
        "capacity_scale": assignment_state["capacity_scale"],
        "capacity_units": assignment_state["capacity_units"],
        "region_capacities": assignment_space["region_capacities"],
        "collision_mode": args.collision_mode,
        "geometry_model": (
            "rectangles plus convex hull separating axes"
            if args.collision_mode == "convex"
            else "collision constraints disabled for lower bound"
        ),
    }


def _selected_assignment_data(template, selected_regions, search_report):
    output = copy.deepcopy(template)
    output["schema"] = "m336_region_assignment_v4"
    output["status"] = "shared_coordinate_quality_candidate"
    output["shared_coordinate_search"] = copy.deepcopy(search_report)
    for row in output["assignments"]:
        group_id = row["subgroup_id"]
        row["proposed_region_id"] = selected_regions[group_id]
        row["proposal_method"] = "shared_coordinate_cp_sat"
        row["status"] = output["status"]
    for row in output.get("candidate_diagnostics", []):
        selected_region = selected_regions[row["subgroup_id"]]
        for candidate in row["candidates"]:
            candidate["selected"] = candidate["region_id"] == selected_region
    return output


def solve(args):
    cp_model = _load_cp_model()
    ortools_version = metadata.version("ortools")
    baseline_result = json.loads(args.baseline_result.read_text())
    baseline_hpwl = float(baseline_result["metrics"]["hpwl"])
    baseline_rsmt = float(baseline_result["metrics"]["rsmt"])
    placedb, context = _load_context(args)
    assignment_space = (
        _optimized_assignment_space(args, context)
        if args.optimize_assignment
        else _fixed_assignment_space(context, args.assignment)
    )
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
        assignment_space,
        args.capacity_scale,
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
                "model": _model_report(args, state, assignment_space),
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

    selected_regions = dict(assignment_space["preferred_regions"])
    for group_id, group_var in state["assignment"]["group_vars"].items():
        option_index = int(solver.value(group_var))
        selected_regions[group_id] = assignment_space["group_options"][
            group_id
        ][option_index]

    selected_sites = {}
    selected_constraints = []
    constraints = {item.node_id: item for item in context.constraints}
    for node_id, site_var in state["site_vars"].items():
        site_index = int(solver.value(site_var))
        constraint = constraints[node_id]
        choices = state["site_choices"][node_id]
        region_index = int(choices["region_indices"][site_index])
        region_id = choices["regions"][region_index]
        local_index = int(choices["local_indices"][site_index])
        if region_id != selected_regions[constraint.subgroup_id]:
            raise RuntimeError(
                "site and subgroup region disagree for %s" % constraint.refdes
            )
        domain = assignment_space["domains"][(node_id, region_id)]
        center = domain.valid_centers[local_index]
        node_x[node_id] = center[0] - constraint.node_width / 2
        node_y[node_id] = center[1] - constraint.node_height / 2
        target, _ = domain.project(
            context.anchor_centers[constraint.anchor_refdes]
        )
        selected_constraints.append(
            replace(
                constraint,
                region_id=region_id,
                domain=domain,
                target_center=target,
            )
        )
        selected_sites[constraint.refdes] = {
            "candidate_index": site_index,
            "region_candidate_index": local_index,
            "center": [float(center[0]), float(center[1])],
            "lower_left": [float(node_x[node_id]), float(node_y[node_id])],
            "region_id": region_id,
            "side": constraint.side,
        }

    position = torch.from_numpy(np.concatenate((node_x, node_y)))
    legality = context.exact_report(
        position, placedb, constraints=selected_constraints
    )
    hpwl = float(placedb.hpwl(node_x, node_y))
    score_upper_bound = 2.0 / (
        hpwl / baseline_hpwl + hpwl / baseline_rsmt
    )
    result = {
        "schema": "m336_discrete_placement_v1",
        "assignment": repo_path(args.assignment),
        "input_sha256": input_sha256,
        "model": _model_report(args, state, assignment_space),
        "solver": solver_report,
        "metrics": {
            "hpwl": hpwl,
            "baseline_hpwl": baseline_hpwl,
            "baseline_rsmt": baseline_rsmt,
            "normalized_score_upper_bound": score_upper_bound,
        },
        "legality": legality,
        "selected_regions": selected_regions,
        "selected_sites": selected_sites,
    }
    if args.assignment_output is not None:
        assignment_output = _selected_assignment_data(
            assignment_space["template"],
            selected_regions,
            {
                "input_assignment": repo_path(args.assignment),
                "input_assignment_sha256": input_sha256["assignment"],
                "model": result["model"],
                "solver": solver_report,
                "metrics": result["metrics"],
            },
        )
        write_json(args.assignment_output, assignment_output)
        result["selected_assignment"] = repo_path(args.assignment_output)
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
        "--optimize-assignment",
        action="store_true",
        help="couple subgroup region selection to shared component sites",
    )
    parser.add_argument(
        "--assignment-output",
        type=Path,
        help="write a diagnostic assignment when CP-SAT finds a candidate",
    )
    parser.add_argument(
        "--ignore-area-capacity",
        action="store_true",
        help="diagnostic only: omit subgroup-area capacity constraints",
    )
    parser.add_argument(
        "--collision-mode",
        choices=("convex", "none"),
        default="convex",
        help="'none' omits collisions and is only a lower-bound diagnostic",
    )
    parser.add_argument("--integer-scale", type=int, default=1000000)
    parser.add_argument("--capacity-scale", type=int, default=1000000)
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
    if args.assignment_output is not None:
        args.assignment_output = args.assignment_output.resolve()
    if (
        args.integer_scale <= 0
        or args.capacity_scale <= 0
        or args.time_limit <= 0
        or args.workers <= 0
    ):
        parser.error("scales, time limit, and workers must be positive")
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
                "selected_assignment": result.get("selected_assignment"),
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
