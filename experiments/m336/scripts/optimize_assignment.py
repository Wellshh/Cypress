#!/usr/bin/env python3
"""Optimize M336 subgroup assignment using the native scored net topology."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from analyze_quality_bound import (
    _baseline_positions,
    _bound_for_ranges,
    _fixed_assignment_ranges,
    _load_context,
    _runtime_fixed_positions,
)
from dreamplace.constraints.region_projection import (
    FeasibleDomain,
    InfeasibleDomainError,
)
from run_matrix import REPO_ROOT, repo_path, sha256_file, write_json


def _validate_interval(interval):
    lower, upper = (float(value) for value in interval)
    if not math.isfinite(lower) or not math.isfinite(upper):
        raise ValueError("interval endpoints must be finite")
    if lower > upper:
        raise ValueError("interval lower endpoint exceeds upper endpoint")
    return lower, upper


def solve_interval_assignment(
    group_options,
    group_areas,
    region_capacities,
    net_axes,
    secondary_costs,
    primary_tolerance=1e-6,
):
    """Solve the exact relaxed-HPWL subgroup assignment MILP.

    Each controlled pin supplies one interval per candidate region. The minimum
    possible axis span is max(interval lower) - min(interval upper), clipped at
    zero. Continuous envelope variables model that expression without coupling
    individual pin positions.
    """
    groups = tuple(sorted(group_options))
    options = []
    option_index = {}
    for group_id in groups:
        regions = tuple(sorted(set(group_options[group_id])))
        if not regions:
            raise ValueError("group has no candidate region: %s" % group_id)
        for region_id in regions:
            key = (group_id, region_id)
            option_index[key] = len(options)
            options.append(key)

    normalized_axes = []
    endpoints = []
    for axis in net_axes:
        weight = float(axis["weight"])
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("net-axis weight must be finite and non-negative")
        pins = []
        for pin in axis["pins"]:
            if "fixed" in pin:
                interval = _validate_interval(pin["fixed"])
                pins.append({"fixed": interval})
                endpoints.extend(interval)
                continue
            group_id = pin["group_id"]
            if group_id not in group_options:
                raise ValueError("pin references unknown group: %s" % group_id)
            intervals = {
                region_id: _validate_interval(interval)
                for region_id, interval in pin["intervals"].items()
            }
            expected = set(group_options[group_id])
            if set(intervals) != expected:
                raise ValueError(
                    "pin options differ from group options: %s" % group_id
                )
            pins.append({"group_id": group_id, "intervals": intervals})
            for interval in intervals.values():
                endpoints.extend(interval)
        if pins:
            normalized_axes.append(
                {"name": axis["name"], "weight": weight, "pins": pins}
            )

    if not normalized_axes or not endpoints:
        raise ValueError("quality MILP requires at least one populated net axis")
    coordinate_min = min(endpoints)
    coordinate_max = max(endpoints)
    coordinate_span = max(coordinate_max - coordinate_min, 1.0)
    big_m = coordinate_span + 1.0

    option_count = len(options)
    axis_variables = []
    for axis_index in range(len(normalized_axes)):
        start = option_count + 3 * axis_index
        axis_variables.append((start, start + 1, start + 2))
    variable_count = option_count + 3 * len(normalized_axes)

    row_indices = []
    column_indices = []
    coefficients = []
    lower_bounds = []
    upper_bounds = []

    def add_constraint(values, lower=-np.inf, upper=np.inf):
        row = len(lower_bounds)
        for column, value in values.items():
            if value:
                row_indices.append(row)
                column_indices.append(column)
                coefficients.append(float(value))
        lower_bounds.append(float(lower))
        upper_bounds.append(float(upper))

    for group_id in groups:
        add_constraint(
            {
                option_index[(group_id, region_id)]: 1.0
                for region_id in group_options[group_id]
            },
            lower=1.0,
            upper=1.0,
        )

    for region_id, capacity in sorted(region_capacities.items()):
        if not math.isfinite(capacity) or capacity < 0:
            raise ValueError("invalid region capacity: %s" % region_id)
        add_constraint(
            {
                option_index[(group_id, candidate_region)]: group_areas[group_id]
                for group_id, candidate_region in options
                if candidate_region == region_id
            },
            upper=capacity,
        )

    primary_objective = np.zeros(variable_count, dtype=np.float64)
    for axis, (max_lower, min_upper, span) in zip(
        normalized_axes, axis_variables
    ):
        primary_objective[span] = axis["weight"]
        for pin in axis["pins"]:
            if "fixed" in pin:
                lower, upper = pin["fixed"]
                add_constraint({max_lower: 1.0}, lower=lower)
                add_constraint({min_upper: 1.0}, upper=upper)
                continue
            group_id = pin["group_id"]
            for region_id, (lower, upper) in pin["intervals"].items():
                option = option_index[(group_id, region_id)]
                add_constraint(
                    {max_lower: 1.0, option: -big_m},
                    lower=lower - big_m,
                )
                add_constraint(
                    {min_upper: 1.0, option: big_m},
                    upper=upper + big_m,
                )
        add_constraint({span: 1.0, max_lower: -1.0, min_upper: 1.0}, lower=0.0)

    matrix = coo_matrix(
        (coefficients, (row_indices, column_indices)),
        shape=(len(lower_bounds), variable_count),
    ).tocsr()
    variable_lower = np.zeros(variable_count, dtype=np.float64)
    variable_upper = np.ones(variable_count, dtype=np.float64)
    for max_lower, min_upper, span in axis_variables:
        variable_lower[max_lower] = coordinate_min
        variable_upper[max_lower] = coordinate_max
        variable_lower[min_upper] = coordinate_min
        variable_upper[min_upper] = coordinate_max
        variable_lower[span] = 0.0
        variable_upper[span] = coordinate_span
    integrality = np.zeros(variable_count, dtype=np.int32)
    integrality[:option_count] = 1
    bounds = Bounds(variable_lower, variable_upper)
    constraints = LinearConstraint(
        matrix,
        np.asarray(lower_bounds),
        np.asarray(upper_bounds),
    )
    solver_options = {"disp": False, "mip_rel_gap": 0.0, "presolve": True}
    primary = milp(
        c=primary_objective,
        integrality=integrality,
        bounds=bounds,
        constraints=constraints,
        options=solver_options,
    )
    if not primary.success:
        raise RuntimeError("quality assignment MILP failed: %s" % primary.message)
    primary_value = float(np.dot(primary_objective, primary.x))

    tolerance = max(float(primary_tolerance), abs(primary_value) * 1e-9)
    locked_matrix = coo_matrix(primary_objective.reshape(1, -1)).tocsr()
    secondary_constraints = LinearConstraint(
        scipy.sparse.vstack([matrix, locked_matrix], format="csr"),
        np.append(np.asarray(lower_bounds), -np.inf),
        np.append(np.asarray(upper_bounds), primary_value + tolerance),
    )
    secondary_objective = np.zeros(variable_count, dtype=np.float64)
    for option, index in option_index.items():
        cost = float(secondary_costs[option])
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("secondary costs must be finite and non-negative")
        secondary_objective[index] = cost
    secondary = milp(
        c=secondary_objective,
        integrality=integrality,
        bounds=bounds,
        constraints=secondary_constraints,
        options=solver_options,
    )
    if not secondary.success:
        raise RuntimeError(
            "quality assignment secondary MILP failed: %s" % secondary.message
        )

    selected = {}
    for (group_id, region_id), index in option_index.items():
        if secondary.x[index] > 0.5:
            if group_id in selected:
                raise RuntimeError("MILP selected multiple regions for %s" % group_id)
            selected[group_id] = region_id
    if set(selected) != set(groups):
        raise RuntimeError("MILP did not select one region for every subgroup")
    return selected, {
        "primary_relaxed_hpwl": primary_value,
        "primary_lock_tolerance": tolerance,
        "secondary_cost": float(np.dot(secondary_objective, secondary.x)),
        "primary_solver_message": primary.message,
        "secondary_solver_message": secondary.message,
        "mip_gap": float(getattr(secondary, "mip_gap", 0.0)),
        "option_count": option_count,
        "continuous_variable_count": variable_count - option_count,
        "constraint_count": int(secondary_constraints.A.shape[0]),
    }


def _decode(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _template_data(path):
    data = json.loads(Path(path).read_text())
    assignments = data.get("assignments", [])
    diagnostics = data.get("candidate_diagnostics", [])
    if not assignments or len(diagnostics) != len(assignments):
        raise ValueError("assignment template lacks complete candidate diagnostics")
    return data


def _candidate_domains(
    context,
    template,
    clearance_mm,
    ignore_candidate_exclusions=False,
):
    constraints = {item.refdes: item for item in context.constraints}
    group_options = {}
    group_nodes = {}
    group_areas = {}
    candidate_rows = {
        row["subgroup_id"]: row for row in template["candidate_diagnostics"]
    }
    domains = {}
    cache = {}
    clearance = float(clearance_mm) * abs(context.alignment.scale)
    for assignment in template["assignments"]:
        group_id = assignment["subgroup_id"]
        diagnostics = candidate_rows[group_id]
        group_areas[group_id] = float(diagnostics["member_area_mm2"])
        members = tuple(
            constraints[refdes]
            for refdes in assignment["member_refdes"]
            if refdes in constraints
        )
        group_nodes[group_id] = members
        if ignore_candidate_exclusions:
            candidate_regions = tuple(
                sorted(
                    region_id
                    for region_id, region in context.geometry.regions.items()
                    if region.side == assignment["placement_side"]
                )
            )
        else:
            candidate_regions = tuple(
                sorted(
                    row["region_id"]
                    for row in diagnostics["candidates"]
                    if row["feasible"]
                )
            )
        regions = []
        for region_id in candidate_regions:
            region_domains = {}
            try:
                for constraint in members:
                    key = (
                        region_id,
                        constraint.domain.width,
                        constraint.domain.height,
                        constraint.domain.footprint_local.wkb_hex,
                    )
                    if key not in cache:
                        cache[key] = FeasibleDomain.build(
                            region=context.regions[region_id],
                            width=constraint.domain.width,
                            height=constraint.domain.height,
                            grid=context.grid,
                            clearance=clearance,
                            footprint_local=constraint.domain.footprint_local,
                        )
                    region_domains[(constraint.node_id, region_id)] = cache[key]
            except InfeasibleDomainError:
                if not ignore_candidate_exclusions:
                    raise
                continue
            domains.update(region_domains)
            regions.append(region_id)
        if not regions:
            raise InfeasibleDomainError(
                "subgroup has no individually feasible region: %s" % group_id
            )
        group_options[group_id] = tuple(regions)
    mapped = {
        constraint.node_id
        for members in group_nodes.values()
        for constraint in members
    }
    expected = {constraint.node_id for constraint in context.constraints}
    if mapped != expected:
        raise ValueError(
            "subgroup mapping does not cover constraints; missing=%s extra=%s"
            % (sorted(expected - mapped), sorted(mapped - expected))
        )
    return group_options, group_nodes, group_areas, domains


def _center_ranges(domains):
    ranges = {}
    for key, domain in domains.items():
        centers = domain.valid_centers
        ranges[key] = (
            float(np.min(centers[:, 0])),
            float(np.max(centers[:, 0])),
            float(np.min(centers[:, 1])),
            float(np.max(centers[:, 1])),
        )
    return ranges


def _secondary_costs(
    context,
    template,
    group_options,
    group_nodes,
    domains,
    baseline_x,
    baseline_y,
):
    candidate_rows = {
        row["subgroup_id"]: {
            candidate["region_id"]: candidate
            for candidate in row["candidates"]
        }
        for row in template["candidate_diagnostics"]
    }
    costs = {}
    diagnostics = {}
    for group_rank, group_id in enumerate(sorted(group_options)):
        for region_rank, region_id in enumerate(group_options[group_id]):
            manual_displacement = 0.0
            for constraint in group_nodes[group_id]:
                target = np.asarray(
                    [
                        baseline_x[constraint.node_id] + constraint.node_width / 2,
                        baseline_y[constraint.node_id] + constraint.node_height / 2,
                    ]
                )
                offsets = domains[(constraint.node_id, region_id)].valid_centers - target
                manual_displacement += float(
                    np.sqrt(np.square(offsets).sum(axis=1)).min()
                )
            anchor_distance = float(
                candidate_rows[group_id][region_id]["anchor_distance_mm"]
            ) * abs(context.alignment.scale)
            stable_tie_break = (group_rank + 1) * (region_rank + 1) * 1e-9
            cost = manual_displacement + 0.1 * anchor_distance + stable_tie_break
            costs[(group_id, region_id)] = cost
            diagnostics[(group_id, region_id)] = {
                "manual_displacement_sites": manual_displacement,
                "anchor_distance_sites": anchor_distance,
                "secondary_cost": cost,
            }
    return costs, diagnostics


def _net_axes(
    placedb,
    constraints,
    node_groups,
    group_options,
    ranges,
    fixed_x,
    fixed_y,
):
    axes = []
    for net_id, pins in enumerate(placedb.net2pin_map):
        pin_axes = {"x": [], "y": []}
        for pin_id in pins:
            node_id = int(placedb.pin2node_map[pin_id])
            if node_id not in constraints:
                pin_axes["x"].append(
                    {
                        "fixed": (
                            float(
                                fixed_x[node_id]
                                + placedb.pin_offset_x[pin_id]
                            ),
                        )
                        * 2
                    }
                )
                pin_axes["y"].append(
                    {
                        "fixed": (
                            float(
                                fixed_y[node_id]
                                + placedb.pin_offset_y[pin_id]
                            ),
                        )
                        * 2
                    }
                )
                continue
            constraint = constraints[node_id]
            group_id = node_groups[node_id]
            x_intervals = {}
            y_intervals = {}
            for region_id in group_options[group_id]:
                min_x, max_x, min_y, max_y = ranges[(node_id, region_id)]
                x_offset = (
                    -constraint.node_width / 2
                    + float(placedb.pin_offset_x[pin_id])
                )
                y_offset = (
                    -constraint.node_height / 2
                    + float(placedb.pin_offset_y[pin_id])
                )
                x_intervals[region_id] = (min_x + x_offset, max_x + x_offset)
                y_intervals[region_id] = (min_y + y_offset, max_y + y_offset)
            pin_axes["x"].append(
                {"group_id": group_id, "intervals": x_intervals}
            )
            pin_axes["y"].append(
                {"group_id": group_id, "intervals": y_intervals}
            )
        weight = float(placedb.net_weights[net_id])
        net_name = _decode(placedb.net_names[net_id])
        for axis_name in ("x", "y"):
            axes.append(
                {
                    "name": "%s:%s" % (net_name, axis_name),
                    "weight": weight,
                    "pins": pin_axes[axis_name],
                }
            )
    return axes


def optimize(args):
    template = _template_data(args.assignment)
    baseline_result = json.loads(args.baseline_result.read_text())
    baseline_hpwl = float(baseline_result["metrics"]["hpwl"])
    baseline_rsmt = float(baseline_result["metrics"]["rsmt"])
    placedb, context = _load_context(args)
    baseline_x, baseline_y = _baseline_positions(
        placedb, args.bookshelf_dir / "m336.baseline.pl"
    )
    fixed_x, fixed_y = _runtime_fixed_positions(
        context, baseline_x, baseline_y
    )
    group_options, group_nodes, group_areas, domains = _candidate_domains(
        context,
        template,
        args.clearance_mm,
        ignore_candidate_exclusions=args.ignore_candidate_exclusions,
    )
    ranges = _center_ranges(domains)
    constraints = {item.node_id: item for item in context.constraints}
    node_groups = {
        constraint.node_id: group_id
        for group_id, members in group_nodes.items()
        for constraint in members
    }
    template_capacity_ratios = template["method"]["capacity_ratios"]
    if args.capacity_ratio_override is None:
        capacity_ratios = {
            region_id: float(ratio)
            for region_id, ratio in template_capacity_ratios.items()
        }
    else:
        if not 0 < args.capacity_ratio_override <= 1:
            raise ValueError("capacity ratio override must be in (0, 1]")
        capacity_ratios = {
            region_id: args.capacity_ratio_override
            for region_id in template_capacity_ratios
        }
    if args.ignore_area_capacity:
        unconstrained_capacity = sum(group_areas.values()) + 1.0
        region_capacities = {
            region_id: unconstrained_capacity
            for region_id in template["capacity_diagnostics"]
        }
    else:
        region_capacities = {
            region_id: float(row["free_area_after_anchors_mm2"])
            * capacity_ratios[region_id]
            for region_id, row in template["capacity_diagnostics"].items()
        }
    secondary_costs, candidate_costs = _secondary_costs(
        context,
        template,
        group_options,
        group_nodes,
        domains,
        baseline_x,
        baseline_y,
    )
    selected, solver = solve_interval_assignment(
        group_options,
        group_areas,
        region_capacities,
        _net_axes(
            placedb,
            constraints,
            node_groups,
            group_options,
            ranges,
            fixed_x,
            fixed_y,
        ),
        secondary_costs,
    )
    selected_ranges = {
        node_id: ranges[(node_id, selected[group_id])]
        for node_id, group_id in node_groups.items()
    }
    selected_bound, _ = _bound_for_ranges(
        placedb,
        constraints,
        selected_ranges,
        fixed_x,
        fixed_y,
    )
    current_ranges, _ = _fixed_assignment_ranges(context)
    current_bound, _ = _bound_for_ranges(
        placedb,
        constraints,
        current_ranges,
        fixed_x,
        fixed_y,
    )
    if not math.isclose(
        selected_bound,
        solver["primary_relaxed_hpwl"],
        abs_tol=max(1e-5, abs(selected_bound) * 1e-8),
    ):
        raise RuntimeError(
            "MILP objective %.9g != independent bound %.9g"
            % (solver["primary_relaxed_hpwl"], selected_bound)
        )
    hpwl_ratio = selected_bound / baseline_hpwl
    rsmt_ratio = selected_bound / baseline_rsmt
    score_upper_bound = 2.0 / (hpwl_ratio + rsmt_ratio)

    output = copy.deepcopy(template)
    output["schema"] = "m336_region_assignment_v3"
    diagnostic_relaxation = (
        args.ignore_candidate_exclusions or args.ignore_area_capacity
    )
    output["status"] = (
        "quality_bound_diagnostic_assignment"
        if diagnostic_relaxation
        else "quality_bound_screened_assignment"
    )
    output["method"] = {
        "name": "native_relaxed_hpwl_two_phase_milp",
        "grid_mm": args.grid_mm,
        "clearance_mm": args.clearance_mm,
        "capacity_ratios": capacity_ratios,
        "template_capacity_ratios": template_capacity_ratios,
        "capacity_ratio_override": args.capacity_ratio_override,
        "ignore_area_capacity": args.ignore_area_capacity,
        "ignore_candidate_exclusions": args.ignore_candidate_exclusions,
        "packing_exclusions": template["method"].get("packing_exclusions", {}),
        "runtime_reassignment": False,
        "primary_objective": "native relaxed HPWL lower bound",
        "secondary_objective": (
            "manual feasible-domain displacement + 0.1 * anchor distance"
        ),
        "solver": "scipy.optimize.milp %s" % scipy.__version__,
    }
    for row in output["assignments"]:
        row["proposed_region_id"] = selected[row["subgroup_id"]]
        row["proposal_method"] = output["method"]["name"]
        row["status"] = output["status"]
    for row in output["candidate_diagnostics"]:
        group_id = row["subgroup_id"]
        for candidate in row["candidates"]:
            key = (group_id, candidate["region_id"])
            candidate["selected"] = selected[group_id] == candidate["region_id"]
            candidate["eligible_for_milp"] = (
                candidate["region_id"] in group_options[group_id]
            )
            if key in candidate_costs:
                candidate.update(candidate_costs[key])

    region_area = {region_id: 0.0 for region_id in region_capacities}
    for group_id, region_id in selected.items():
        region_area[region_id] += group_areas[group_id]
    for region_id, row in output["capacity_diagnostics"].items():
        row["member_area_mm2"] = region_area[region_id]
        row["utilization"] = region_area[region_id] / float(row["region_area_mm2"])
        row["free_area_utilization"] = region_area[region_id] / float(
            row["free_area_after_anchors_mm2"]
        )
    output["quality_optimization"] = {
        "current_assignment_relaxed_hpwl": current_bound,
        "optimized_assignment_relaxed_hpwl": selected_bound,
        "relaxed_hpwl_reduction": 1.0 - selected_bound / current_bound,
        "baseline_hpwl": baseline_hpwl,
        "baseline_rsmt": baseline_rsmt,
        "hpwl_lower_bound_ratio": hpwl_ratio,
        "rsmt_lower_bound_ratio": rsmt_ratio,
        "normalized_quality_score_upper_bound": score_upper_bound,
        "solver": solver,
        "runtime_fixed_node_count": len(context.frozen_lower_left),
    }
    output["quality_input_sha256"] = {
        "assignment_template": sha256_file(args.assignment),
        "baseline_result": sha256_file(args.baseline_result),
        "baseline_placement": sha256_file(
            args.bookshelf_dir / "m336.baseline.pl"
        ),
        "bookshelf_nodes": sha256_file(args.bookshelf_dir / "m336.nodes"),
        "bookshelf_nets": sha256_file(args.bookshelf_dir / "m336.nets"),
        "bookshelf_scl": sha256_file(args.bookshelf_dir / "m336.scl"),
    }
    write_json(args.output, output)
    if score_upper_bound + 1e-12 < args.minimum_score_potential:
        raise RuntimeError(
            "optimized assignment score upper bound %.9g is below %.9g"
            % (score_upper_bound, args.minimum_score_potential)
        )
    return {
        "output": repo_path(args.output),
        "selected_regions": selected,
        "quality_optimization": output["quality_optimization"],
        "quality_input_sha256": output["quality_input_sha256"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bookshelf-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/bookshelf",
    )
    parser.add_argument(
        "--assignment",
        type=Path,
        default=REPO_ROOT
        / "experiments/m336/configs/m336_region_assignment.final.json",
    )
    parser.add_argument(
        "--baseline-result",
        type=Path,
        default=REPO_ROOT / "results/m336/baseline/baseline-result.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results/m336/quality_assignment",
        help="scratch directory used to build the native constraint context",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT
        / "results/m336/quality_assignment/m336_region_assignment.quality.json",
    )
    parser.add_argument("--grid-mm", type=float, default=0.1)
    parser.add_argument("--clearance-mm", type=float, default=0.0)
    parser.add_argument(
        "--capacity-ratio-override",
        type=float,
        help="explicit diagnostic override; 1.0 still enforces physical free area",
    )
    parser.add_argument(
        "--ignore-area-capacity",
        action="store_true",
        help="diagnostic relaxation; never use the result as a legal assignment",
    )
    parser.add_argument(
        "--ignore-candidate-exclusions",
        action="store_true",
        help="diagnostic relaxation retaining only per-component domain checks",
    )
    parser.add_argument("--minimum-score-potential", type=float, default=1.0)
    args = parser.parse_args()
    for name in (
        "bookshelf_dir",
        "assignment",
        "baseline_result",
        "output_dir",
        "output",
    ):
        setattr(args, name, getattr(args, name).resolve())
    for path in (
        args.bookshelf_dir / "m336.aux",
        args.bookshelf_dir / "m336.baseline.pl",
        args.assignment,
        args.baseline_result,
    ):
        if not path.exists():
            parser.error("required input does not exist: %s" % path)
    result = optimize(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
