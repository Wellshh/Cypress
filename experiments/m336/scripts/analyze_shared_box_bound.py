#!/usr/bin/env python3
"""Compute a continuous shared-coordinate M336 HPWL lower bound."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from analyze_quality_bound import (
    _baseline_positions,
    _load_context,
    _override_manual_baseline_endpoints,
    _runtime_fixed_positions,
    _select_fixed_endpoints,
)
from optimize_assignment import _template_data
from run_matrix import REPO_ROOT, repo_path, sha256_file, write_json


def _decode(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _frozen_endpoint_displacements(context, placedb, baseline_x, baseline_y):
    runtime_x, runtime_y = _runtime_fixed_positions(
        context, baseline_x, baseline_y
    )
    scale = abs(float(context.alignment.scale))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("geometry alignment scale must be positive")
    rows = []
    anchor_ids = set(context.frozen_anchor_ids)
    fixed_ids = set(context.frozen_fixed_ids)
    for node_id in sorted(context.frozen_lower_left):
        dx = float(runtime_x[node_id] - baseline_x[node_id])
        dy = float(runtime_y[node_id] - baseline_y[node_id])
        distance = math.hypot(dx, dy)
        rows.append(
            {
                "refdes": _decode(placedb.node_names[node_id]),
                "kind": "anchor" if node_id in anchor_ids else "fixed",
                "dx_sites": dx,
                "dy_sites": dy,
                "distance_sites": distance,
                "distance_mm": distance / scale,
            }
        )
    if {row["kind"] for row in rows} - {"anchor", "fixed"}:
        raise RuntimeError("unclassified runtime-frozen endpoint")
    if {int(node_id) for node_id in context.frozen_lower_left} != (
        anchor_ids | fixed_ids
    ):
        raise RuntimeError("runtime-frozen endpoint sets are inconsistent")

    def summarize(selected_rows):
        distances = [row["distance_mm"] for row in selected_rows]
        return {
            "count": len(selected_rows),
            "moved_count": sum(value > 1e-12 for value in distances),
            "maximum_mm": max(distances, default=0.0),
            "mean_mm": (
                sum(distances) / len(distances) if distances else 0.0
            ),
            "rms_mm": (
                math.sqrt(sum(value * value for value in distances) / len(distances))
                if distances
                else 0.0
            ),
        }

    return {
        "summary": {
            "all": summarize(rows),
            "anchors": summarize(
                [row for row in rows if row["kind"] == "anchor"]
            ),
            "fixed_components": summarize(
                [row for row in rows if row["kind"] == "fixed"]
            ),
        },
        "components": rows,
    }


def _continuous_box_space(context, template):
    constraints = {item.refdes: item for item in context.constraints}
    group_options = {}
    group_nodes = {}
    node_ranges = {}
    group_areas = {}
    candidate_rows = {
        row["subgroup_id"]: row for row in template["candidate_diagnostics"]
    }
    for assignment in template["assignments"]:
        group_id = assignment["subgroup_id"]
        members = tuple(
            constraints[refdes]
            for refdes in assignment["member_refdes"]
            if refdes in constraints
        )
        group_nodes[group_id] = members
        group_areas[group_id] = float(
            candidate_rows[group_id]["member_area_mm2"]
        )
        options = []
        for region_id, region_data in sorted(context.geometry.regions.items()):
            if region_data.side != assignment["placement_side"]:
                continue
            region_min_x, region_min_y, region_max_x, region_max_y = (
                context.regions[region_id].bounds
            )
            ranges = {}
            feasible = True
            for constraint in members:
                local_min_x, local_min_y, local_max_x, local_max_y = (
                    constraint.domain.footprint_local.bounds
                )
                center_range = (
                    region_min_x - local_min_x,
                    region_max_x - local_max_x,
                    region_min_y - local_min_y,
                    region_max_y - local_max_y,
                )
                if (
                    center_range[0] > center_range[1]
                    or center_range[2] > center_range[3]
                ):
                    feasible = False
                    break
                ranges[(constraint.node_id, region_id)] = center_range
            if feasible:
                options.append(region_id)
                node_ranges.update(ranges)
        if not options:
            raise ValueError(
                "subgroup has no bounding-box-feasible region: %s" % group_id
            )
        group_options[group_id] = tuple(options)

    node_groups = {
        constraint.node_id: group_id
        for group_id, members in group_nodes.items()
        for constraint in members
    }
    expected = {constraint.node_id for constraint in context.constraints}
    if set(node_groups) != expected:
        raise ValueError("continuous box space does not cover controlled nodes")
    return group_options, group_nodes, group_areas, node_groups, node_ranges


def _native_net_axes(placedb, constraints, fixed_x, fixed_y):
    axes = []
    for net_id, pins in enumerate(placedb.net2pin_map):
        net_name = _decode(placedb.net_names[net_id])
        axis_pins = {"x": [], "y": []}
        for pin_id in pins:
            node_id = int(placedb.pin2node_map[pin_id])
            if node_id in constraints:
                constraint = constraints[node_id]
                axis_pins["x"].append(
                    {
                        "node_id": node_id,
                        "offset": (
                            -constraint.node_width / 2
                            + float(placedb.pin_offset_x[pin_id])
                        ),
                    }
                )
                axis_pins["y"].append(
                    {
                        "node_id": node_id,
                        "offset": (
                            -constraint.node_height / 2
                            + float(placedb.pin_offset_y[pin_id])
                        ),
                    }
                )
            else:
                axis_pins["x"].append(
                    {
                        "fixed": float(
                            fixed_x[node_id] + placedb.pin_offset_x[pin_id]
                        )
                    }
                )
                axis_pins["y"].append(
                    {
                        "fixed": float(
                            fixed_y[node_id] + placedb.pin_offset_y[pin_id]
                        )
                    }
                )
        weight = float(placedb.net_weights[net_id])
        for axis_name in ("x", "y"):
            axes.append(
                {
                    "name": "%s:%s" % (net_name, axis_name),
                    "axis": axis_name,
                    "weight": weight,
                    "pins": axis_pins[axis_name],
                }
            )
    return axes


def solve_shared_box_assignment(
    group_options,
    group_areas,
    region_capacities,
    node_groups,
    node_ranges,
    net_axes,
):
    groups = tuple(sorted(group_options))
    options = [
        (group_id, region_id)
        for group_id in groups
        for region_id in sorted(set(group_options[group_id]))
    ]
    option_index = {option: index for index, option in enumerate(options)}
    nodes = tuple(sorted(node_groups))
    node_index = {node_id: index for index, node_id in enumerate(nodes)}
    option_count = len(options)
    node_start = option_count
    axis_start = node_start + 2 * len(nodes)
    axis_variables = [
        (axis_start + 3 * index, axis_start + 3 * index + 1, axis_start + 3 * index + 2)
        for index in range(len(net_axes))
    ]
    variable_count = axis_start + 3 * len(net_axes)

    rows = []
    columns = []
    values = []
    lower_bounds = []
    upper_bounds = []

    def add_constraint(coefficients, lower=-np.inf, upper=np.inf):
        row = len(lower_bounds)
        for column, value in coefficients.items():
            if value:
                rows.append(row)
                columns.append(column)
                values.append(float(value))
        lower_bounds.append(float(lower))
        upper_bounds.append(float(upper))

    def coordinate_index(node_id, axis_name):
        return node_start + 2 * node_index[node_id] + (axis_name == "y")

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
        add_constraint(
            {
                option_index[(group_id, candidate_region)]: group_areas[group_id]
                for group_id, candidate_region in options
                if candidate_region == region_id
            },
            upper=capacity,
        )

    variable_lower = np.zeros(variable_count, dtype=np.float64)
    variable_upper = np.ones(variable_count, dtype=np.float64)
    for node_id in nodes:
        group_id = node_groups[node_id]
        ranges = {
            region_id: node_ranges[(node_id, region_id)]
            for region_id in group_options[group_id]
        }
        for axis_offset, axis_name in enumerate(("x", "y")):
            lower_offset = 0 if axis_name == "x" else 2
            all_lower = [row[lower_offset] for row in ranges.values()]
            all_upper = [row[lower_offset + 1] for row in ranges.values()]
            global_lower = min(all_lower)
            global_upper = max(all_upper)
            coordinate = coordinate_index(node_id, axis_name)
            variable_lower[coordinate] = global_lower
            variable_upper[coordinate] = global_upper
            big_m = max(global_upper - global_lower, 1.0) + 1.0
            for region_id, row in ranges.items():
                selected = option_index[(group_id, region_id)]
                lower = row[lower_offset]
                upper = row[lower_offset + 1]
                add_constraint(
                    {coordinate: 1.0, selected: -big_m},
                    lower=lower - big_m,
                )
                add_constraint(
                    {coordinate: 1.0, selected: big_m},
                    upper=upper + big_m,
                )

    objective = np.zeros(variable_count, dtype=np.float64)
    for axis, (maximum, minimum, span) in zip(net_axes, axis_variables):
        pin_lower = []
        pin_upper = []
        for pin in axis["pins"]:
            if "fixed" in pin:
                value = float(pin["fixed"])
                pin_lower.append(value)
                pin_upper.append(value)
                add_constraint({maximum: 1.0}, lower=value)
                add_constraint({minimum: 1.0}, upper=value)
                continue
            node_id = int(pin["node_id"])
            coordinate = coordinate_index(node_id, axis["axis"])
            offset = float(pin["offset"])
            pin_lower.append(variable_lower[coordinate] + offset)
            pin_upper.append(variable_upper[coordinate] + offset)
            add_constraint(
                {maximum: 1.0, coordinate: -1.0}, lower=offset
            )
            add_constraint(
                {minimum: 1.0, coordinate: -1.0}, upper=offset
            )
        lower = min(pin_lower)
        upper = max(pin_upper)
        variable_lower[maximum] = lower
        variable_upper[maximum] = upper
        variable_lower[minimum] = lower
        variable_upper[minimum] = upper
        variable_lower[span] = 0.0
        variable_upper[span] = max(upper - lower, 0.0)
        add_constraint(
            {span: 1.0, maximum: -1.0, minimum: 1.0}, lower=0.0
        )
        weight = float(axis["weight"])
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("net weights must be finite and non-negative")
        objective[span] = weight

    matrix = coo_matrix(
        (values, (rows, columns)),
        shape=(len(lower_bounds), variable_count),
    ).tocsr()
    integrality = np.zeros(variable_count, dtype=np.int32)
    integrality[:option_count] = 1
    result = milp(
        c=objective,
        integrality=integrality,
        bounds=Bounds(variable_lower, variable_upper),
        constraints=LinearConstraint(
            matrix,
            np.asarray(lower_bounds),
            np.asarray(upper_bounds),
        ),
        options={"disp": False, "mip_rel_gap": 0.0, "presolve": True},
    )
    if not result.success:
        raise RuntimeError("shared-coordinate box MILP failed: %s" % result.message)

    selected = {
        group_id: region_id
        for (group_id, region_id), index in option_index.items()
        if result.x[index] > 0.5
    }
    if set(selected) != set(groups):
        raise RuntimeError("shared-coordinate MILP assignment is incomplete")
    coordinates = {
        node_id: {
            "x": float(result.x[coordinate_index(node_id, "x")]),
            "y": float(result.x[coordinate_index(node_id, "y")]),
        }
        for node_id in nodes
    }
    independent_objective = 0.0
    for axis in net_axes:
        pin_values = [
            float(pin["fixed"])
            if "fixed" in pin
            else coordinates[int(pin["node_id"])][axis["axis"]]
            + float(pin["offset"])
            for pin in axis["pins"]
        ]
        independent_objective += float(axis["weight"]) * (
            max(pin_values) - min(pin_values)
        )
    objective_value = float(np.dot(objective, result.x))
    if not math.isclose(
        objective_value,
        independent_objective,
        abs_tol=max(1e-5, abs(objective_value) * 1e-9),
    ):
        raise RuntimeError("shared-coordinate objective verification failed")
    return selected, coordinates, {
        "relaxed_hpwl": objective_value,
        "independent_relaxed_hpwl": independent_objective,
        "solver_message": result.message,
        "mip_gap": float(getattr(result, "mip_gap", 0.0)),
        "option_count": option_count,
        "coordinate_variable_count": 2 * len(nodes),
        "constraint_count": int(matrix.shape[0]),
        "solver": "scipy.optimize.milp %s" % scipy.__version__,
    }


def analyze(args):
    template = _template_data(args.assignment)
    baseline_result = json.loads(args.baseline_result.read_text())
    baseline_hpwl = float(baseline_result["metrics"]["hpwl"])
    baseline_rsmt = float(baseline_result["metrics"]["rsmt"])
    placedb, context = _load_context(args)
    baseline_x, baseline_y = _baseline_positions(
        placedb, args.bookshelf_dir / "m336.baseline.pl"
    )
    fixed_x, fixed_y = _select_fixed_endpoints(
        context,
        baseline_x,
        baseline_y,
        args.fixed_endpoint_mode,
    )
    fixed_x, fixed_y = _override_manual_baseline_endpoints(
        context,
        placedb,
        baseline_x,
        baseline_y,
        fixed_x,
        fixed_y,
        args.manual_baseline_endpoint,
    )
    frozen_displacements = _frozen_endpoint_displacements(
        context, placedb, baseline_x, baseline_y
    )
    (
        group_options,
        group_nodes,
        group_areas,
        node_groups,
        node_ranges,
    ) = _continuous_box_space(context, template)
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
    constraints = {item.node_id: item for item in context.constraints}
    selected, coordinates, solver = solve_shared_box_assignment(
        group_options,
        group_areas,
        region_capacities,
        node_groups,
        node_ranges,
        _native_net_axes(placedb, constraints, fixed_x, fixed_y),
    )
    hpwl = solver["relaxed_hpwl"]
    hpwl_ratio = hpwl / baseline_hpwl
    rsmt_ratio = hpwl / baseline_rsmt
    score_upper_bound = 2.0 / (hpwl_ratio + rsmt_ratio)
    score_one_hpwl_limit = 2.0 / (
        1.0 / baseline_hpwl + 1.0 / baseline_rsmt
    )
    output = {
        "schema": "m336_shared_coordinate_box_bound_v1",
        "status": "diagnostic_continuous_box_relaxation",
        "assignment": repo_path(args.assignment),
        "input_sha256": {
            "assignment": sha256_file(args.assignment),
            "baseline_result": sha256_file(args.baseline_result),
            "baseline_placement": sha256_file(
                args.bookshelf_dir / "m336.baseline.pl"
            ),
        },
        "model": {
            "assignment_group_count": len(group_options),
            "assignment_option_count": sum(
                len(options) for options in group_options.values()
            ),
            "assignment_options": {
                group_id: list(options)
                for group_id, options in sorted(group_options.items())
            },
            "controlled_node_count": len(node_groups),
            "runtime_fixed_node_count": len(context.frozen_lower_left),
            "fixed_endpoint_mode": args.fixed_endpoint_mode,
            "manual_baseline_endpoint_overrides": sorted(
                set(args.manual_baseline_endpoint)
            ),
            "runtime_frozen_displacement_from_manual_baseline": (
                frozen_displacements
            ),
            "ignore_area_capacity": args.ignore_area_capacity,
            "region_capacities": region_capacities,
            "relaxations": [
                "replace each exact keep-in domain by its region/footprint bounding interval",
                "allow continuous x/y combinations outside the physical polygon",
                "ignore all component overlap constraints",
                "ignore RSMT beyond the necessary RSMT >= HPWL inequality",
            ],
        },
        "solver": solver,
        "metrics": {
            "relaxed_hpwl": hpwl,
            "baseline_hpwl": baseline_hpwl,
            "baseline_rsmt": baseline_rsmt,
            "hpwl_lower_bound_ratio": hpwl_ratio,
            "rsmt_lower_bound_ratio": rsmt_ratio,
            "normalized_score_upper_bound": score_upper_bound,
            "score_one_hpwl_limit": score_one_hpwl_limit,
            "hpwl_excess_over_score_one_limit": hpwl
            - score_one_hpwl_limit,
        },
        "selected_regions": selected,
        "relaxed_component_centers": {
            _decode(placedb.node_names[node_id]): center
            for node_id, center in coordinates.items()
        },
    }
    write_json(args.output, output)
    if score_upper_bound + 1e-12 < args.minimum_score_potential:
        raise RuntimeError(
            "shared-coordinate box score upper bound %.9g is below %.9g"
            % (score_upper_bound, args.minimum_score_potential)
        )
    return output


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
        default=REPO_ROOT / "results/m336/shared_box/context",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "results/m336/shared_box/result.json",
    )
    parser.add_argument("--grid-mm", type=float, default=0.05)
    parser.add_argument("--clearance-mm", type=float, default=0.0)
    parser.add_argument("--minimum-score-potential", type=float, default=1.0)
    parser.add_argument("--ignore-area-capacity", action="store_true")
    parser.add_argument(
        "--fixed-endpoint-mode",
        choices=("runtime", "manual-baseline"),
        default="runtime",
    )
    parser.add_argument(
        "--manual-baseline-endpoint",
        action="append",
        default=[],
        metavar="REFDES",
        help="override one runtime-frozen endpoint with its manual position",
    )
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
    result = analyze(args)
    print(
        json.dumps(
            {
                "output": repo_path(args.output),
                "solver": result["solver"],
                "metrics": result["metrics"],
                "selected_regions": result["selected_regions"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
