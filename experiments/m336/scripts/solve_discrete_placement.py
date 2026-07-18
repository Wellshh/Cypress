#!/usr/bin/env python3
"""Solve a fixed M336 assignment on exact keep-in grid sites with CP-SAT."""

from __future__ import annotations

import argparse
import copy
from collections import defaultdict
from dataclasses import replace
from importlib import metadata
import json
import math
from pathlib import Path

import numpy as np
import torch
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from analyze_quality_bound import (
    _baseline_positions,
    _load_context,
    _override_manual_baseline_endpoints,
    _select_fixed_endpoints,
)
from dreamplace.constraints.anchor_keepin import (
    _pack_region,
)
from dreamplace.constraints.region_projection import InfeasibleDomainError
from optimize_assignment import _candidate_domains, _template_data
from run_matrix import (
    REPO_ROOT,
    parse_placement,
    repo_path,
    sha256_file,
    write_json,
)


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


def _exact_site_index(centers, center, tolerance=1e-8):
    centers = np.asarray(centers, dtype=np.float64)
    center = np.asarray(center, dtype=np.float64)
    if centers.ndim != 2 or centers.shape[1] != 2 or center.shape != (2,):
        raise ValueError("site centers and hint center must be two-dimensional")
    index, distance = _nearest_site_index(centers, center)
    if distance > tolerance:
        raise ValueError("packing hint is not an exact feasible-domain site")
    return index


def _nearest_site_index(centers, center):
    centers = np.asarray(centers, dtype=np.float64)
    center = np.asarray(center, dtype=np.float64)
    if centers.ndim != 2 or centers.shape[1] != 2 or center.shape != (2,):
        raise ValueError("site centers and hint center must be two-dimensional")
    if not len(centers):
        raise ValueError("site centers must not be empty")
    distances = np.square(centers - center).sum(axis=1)
    index = int(np.argmin(distances))
    return index, math.sqrt(float(distances[index]))


def _guide_site_indices(domains, guide_center):
    return tuple(
        _nearest_site_index(domain.valid_centers, guide_center)[0]
        for domain in domains
    )


def _limited_candidate_indices(
    centers,
    limit,
    preferred_index=None,
    guide_indices=(),
    eligible_indices=None,
):
    centers = np.asarray(centers, dtype=np.float64)
    if eligible_indices is None:
        eligible_indices = np.arange(len(centers), dtype=np.int64)
    else:
        eligible_indices = np.asarray(eligible_indices, dtype=np.int64)
        if len(np.unique(eligible_indices)) != len(eligible_indices):
            raise ValueError("eligible site indices must be unique")
        if np.any(eligible_indices < 0) or np.any(
            eligible_indices >= len(centers)
        ):
            raise ValueError("eligible site index is out of range")
        eligible_indices = np.sort(eligible_indices)
    if limit <= 0 or len(eligible_indices) <= limit:
        return eligible_indices
    preferred_indices = []
    if preferred_index is not None:
        preferred_indices.append(int(preferred_index))
    preferred_indices.extend(int(index) for index in guide_indices)
    preferred_indices = sorted(set(preferred_indices))
    if not preferred_indices:
        raise ValueError("candidate limiting requires a preferred site")
    if any(index < 0 or index >= len(centers) for index in preferred_indices):
        raise ValueError("preferred site index is out of range")
    distances = np.min(
        [
            np.square(
                centers[eligible_indices] - centers[index]
            ).sum(axis=1)
            for index in preferred_indices
        ],
        axis=0,
    )
    order = np.lexsort((eligible_indices, distances))[:limit]
    return np.sort(eligible_indices[order])


def _candidate_indices_without_obstacle_overlap(
    footprint_local, centers, obstacles, epsilon=1e-12
):
    """Return original site indices whose exact footprint clears obstacles."""
    centers = np.asarray(centers, dtype=np.float64)
    if centers.ndim != 2 or centers.shape[1] != 2:
        raise ValueError("candidate centers must be two-dimensional")
    if not obstacles or not len(centers):
        return np.arange(len(centers), dtype=np.int64)

    local_min_x, local_min_y, local_max_x, local_max_y = (
        footprint_local.bounds
    )
    candidate_bounds = np.column_stack(
        (
            centers[:, 0] + local_min_x,
            centers[:, 1] + local_min_y,
            centers[:, 0] + local_max_x,
            centers[:, 1] + local_max_y,
        )
    )
    obstacle_bounds = np.asarray(
        [obstacle.bounds for obstacle in obstacles], dtype=np.float64
    )
    keep = np.ones(len(centers), dtype=bool)
    chunk_size = 4096
    for start in range(0, len(centers), chunk_size):
        stop = min(start + chunk_size, len(centers))
        bounds = candidate_bounds[start:stop]
        overlap_x = (
            np.minimum(bounds[:, None, 2], obstacle_bounds[None, :, 2])
            - np.maximum(bounds[:, None, 0], obstacle_bounds[None, :, 0])
        )
        overlap_y = (
            np.minimum(bounds[:, None, 3], obstacle_bounds[None, :, 3])
            - np.maximum(bounds[:, None, 1], obstacle_bounds[None, :, 1])
        )
        possible = (overlap_x > epsilon) & (overlap_y > epsilon)
        for local_index in np.flatnonzero(np.any(possible, axis=1)):
            candidate_index = start + int(local_index)
            footprint = affinity.translate(
                footprint_local,
                xoff=float(centers[candidate_index, 0]),
                yoff=float(centers[candidate_index, 1]),
            )
            for obstacle_index in np.flatnonzero(possible[local_index]):
                if (
                    footprint.intersection(obstacles[int(obstacle_index)]).area
                    > epsilon
                ):
                    keep[candidate_index] = False
                    break
    return np.flatnonzero(keep).astype(np.int64)


def _fixed_hint_candidate_indices(
    region_ids, hint_region_id, hint_local_index
):
    if hint_region_id not in region_ids:
        raise ValueError("fixed hint region is absent from assignment options")
    return tuple(
        np.asarray([hint_local_index], dtype=np.int64)
        if region_id == hint_region_id
        else np.empty(0, dtype=np.int64)
        for region_id in region_ids
    )


def _coordinate_choice_index(choices, region_id, x_value, y_value):
    if region_id not in choices["regions"]:
        raise ValueError("solved region is absent from site choices")
    region_index = choices["regions"].index(region_id)
    matches = np.flatnonzero(
        (choices["region_indices"] == region_index)
        & (choices["x_values"] == x_value)
        & (choices["y_values"] == y_value)
    )
    if len(matches) != 1:
        raise ValueError(
            "solved coordinates must identify exactly one candidate site"
        )
    return int(matches[0])


def _override_fixed_endpoint_coordinates(
    context, placedb, fixed_x, fixed_y, override_rows
):
    output_x = np.asarray(fixed_x, dtype=np.float64).copy()
    output_y = np.asarray(fixed_y, dtype=np.float64).copy()
    frozen_by_refdes = {
        _decode(placedb.node_names[node_id]): node_id
        for node_id in context.frozen_lower_left
    }
    overrides = {}
    for row in override_rows or ():
        if len(row) != 3:
            raise ValueError(
                "fixed endpoint override requires REFDES X Y"
            )
        refdes = str(row[0])
        try:
            lower_left = (float(row[1]), float(row[2]))
        except (TypeError, ValueError) as error:
            raise ValueError(
                "fixed endpoint override coordinates must be numeric"
            ) from error
        if not all(math.isfinite(value) for value in lower_left):
            raise ValueError(
                "fixed endpoint override coordinates must be finite"
            )
        if refdes not in frozen_by_refdes:
            raise ValueError(
                "fixed endpoint override is not a frozen component: %s"
                % refdes
            )
        if refdes in overrides and overrides[refdes] != lower_left:
            raise ValueError(
                "conflicting fixed endpoint overrides for %s" % refdes
            )
        overrides[refdes] = lower_left

    report = []
    for refdes, lower_left in sorted(overrides.items()):
        node_id = frozen_by_refdes[refdes]
        output_x[node_id], output_y[node_id] = lower_left
        report.append(
            {"refdes": refdes, "lower_left": list(lower_left)}
        )
    return output_x, output_y, report


def _partial_fix_refdes(constraints, movable_refdes):
    movable_refdes = set(movable_refdes or ())
    if not movable_refdes:
        return frozenset()
    available = {constraint.refdes for constraint in constraints}
    unknown = sorted(movable_refdes - available)
    if unknown:
        raise ValueError(
            "movable refdes are not controlled components: %s"
            % ", ".join(unknown)
        )
    return frozenset(available - movable_refdes)


def _normalize_controlled_collision_pairs(pair_rows):
    pairs = set()
    for row in pair_rows or ():
        if len(row) != 2:
            raise ValueError(
                "controlled collision pairs require exactly two refdes"
            )
        first, second = str(row[0]), str(row[1])
        if first == second:
            raise ValueError(
                "controlled collision pair must contain two refdes"
            )
        pairs.add(tuple(sorted((first, second))))
    return frozenset(pairs)


def _inactive_controlled_collision_pairs(requested_pairs, available_pairs):
    return frozenset(requested_pairs) - frozenset(available_pairs)


def _side_legality_report(legality, side):
    violations = [
        row for row in legality["violations"] if row["side"] == side
    ]
    overlap_pairs = [
        row for row in legality["overlap_pairs"] if row["side"] == side
    ]
    return {
        "side": side,
        "keepin_violation_count": len(violations),
        "keepin_violation_area": sum(
            row["violation_area"] for row in violations
        ),
        "overlap_pair_count": len(overlap_pairs),
        "overlap_area": sum(row["overlap_area"] for row in overlap_pairs),
        "violations": violations,
        "overlap_pairs": overlap_pairs,
    }


def _site_hint_parts(site_hint):
    if not isinstance(site_hint, dict):
        raise ValueError("site hints must include region_id and site_index")
    if "region_id" not in site_hint or "site_index" not in site_hint:
        raise ValueError("site hints must include region_id and site_index")
    return str(site_hint["region_id"]), int(site_hint["site_index"])


def _hinted_group_regions(site_hints, assignment_space):
    hinted_regions = {}
    for node_id, site_hint in site_hints.items():
        region_id, _ = _site_hint_parts(site_hint)
        group_id = assignment_space["node_groups"][node_id]
        if region_id not in assignment_space["group_options"][group_id]:
            raise ValueError("site hint region is ineligible for %s" % group_id)
        if group_id in hinted_regions and hinted_regions[group_id] != region_id:
            raise ValueError("site hints split subgroup %s across regions" % group_id)
        hinted_regions[group_id] = region_id
    return hinted_regions


def _build_packing_hint(
    args,
    placedb,
    context,
    baseline_x,
    baseline_y,
    fixed_x,
    fixed_y,
    baseline_hpwl,
    baseline_rsmt,
):
    packing_context = copy.copy(context)
    packing_context.frozen_lower_left = {
        node_id: (float(fixed_x[node_id]), float(fixed_y[node_id]))
        for node_id in context.frozen_lower_left
    }
    packing_context.projection_enabled = True
    packing_context.initialization_mode = "current"
    packing_context.output_dir = args.output_dir / "packing_hint"

    position = np.zeros(2 * placedb.num_nodes, dtype=np.float64)
    position[: placedb.num_physical_nodes] = baseline_x
    position[
        placedb.num_nodes : placedb.num_nodes + placedb.num_physical_nodes
    ] = baseline_y
    for node_id in packing_context.frozen_lower_left:
        position[node_id] = fixed_x[node_id]
        position[placedb.num_nodes + node_id] = fixed_y[node_id]

    occupied = {"TOP": [], "BOTTOM": []}
    constrained_ids = {constraint.node_id for constraint in context.constraints}
    for node_id in range(placedb.num_physical_nodes):
        if node_id in constrained_ids:
            continue
        side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
        node_width = float(placedb.node_size_x[node_id])
        node_height = float(placedb.node_size_y[node_id])
        footprint_local = _fixed_footprint_local(
            context, placedb, node_id, "decomposed"
        )
        occupied[side].append(
            affinity.translate(
                footprint_local,
                xoff=float(position[node_id]) + node_width / 2,
                yoff=float(position[placedb.num_nodes + node_id])
                + node_height / 2,
            )
        )

    constraints_by_region = defaultdict(list)
    for constraint in context.constraints:
        constraints_by_region[(constraint.side, constraint.region_id)].append(
            constraint
        )
    packing_stats = []
    placements = {}
    for (side, region_id), region_constraints in sorted(
        constraints_by_region.items()
    ):
        preferred_centers = {}
        for constraint in region_constraints:
            current_center = (
                float(position[constraint.node_id])
                + constraint.node_width / 2,
                float(position[placedb.num_nodes + constraint.node_id])
                + constraint.node_height / 2,
            )
            preferred_centers[constraint.node_id], _ = (
                constraint.domain.project(current_center)
            )
        try:
            region_placements, region_stats = _pack_region(
                region_constraints,
                occupied[side],
                preferred_centers=preferred_centers,
            )
        except InfeasibleDomainError as error:
            raise RuntimeError(
                "packing hint exhausted for %s/%s: %s"
                % (side, region_id, error)
            ) from error
        placements.update(region_placements)
        for constraint in region_constraints:
            occupied[side].append(
                constraint.domain.footprint(
                    region_placements[constraint.node_id]
                )
            )
        packing_stats.append(
            dict(
                region_stats,
                side=side,
                region_id=region_id,
                component_count=len(region_constraints),
            )
        )

    for constraint in context.constraints:
        center = placements[constraint.node_id]
        position[constraint.node_id] = center[0] - constraint.node_width / 2
        position[placedb.num_nodes + constraint.node_id] = (
            center[1] - constraint.node_height / 2
        )
    node_x = position[: placedb.num_physical_nodes]
    node_y = position[
        placedb.num_nodes : placedb.num_nodes + placedb.num_physical_nodes
    ]
    legality = packing_context.exact_report(
        torch.from_numpy(position), placedb
    )
    if legality["keepin_violation_count"] or legality["overlap_pair_count"]:
        raise RuntimeError("packing hint failed exact legality validation")

    site_indices = {}
    selected_sites = {}
    for constraint in context.constraints:
        center = (
            float(node_x[constraint.node_id] + constraint.node_width / 2),
            float(node_y[constraint.node_id] + constraint.node_height / 2),
        )
        site_index = _exact_site_index(
            constraint.domain.valid_centers, center
        )
        site_indices[constraint.node_id] = {
            "region_id": constraint.region_id,
            "site_index": site_index,
        }
        selected_sites[constraint.refdes] = {
            "site_index": site_index,
            "center": list(center),
            "region_id": constraint.region_id,
        }

    hpwl = float(placedb.hpwl(node_x, node_y))
    score_upper_bound = 2.0 / (
        hpwl / baseline_hpwl + hpwl / baseline_rsmt
    )
    placement_path = args.output_dir / "packing_hint" / "m336.packing-hint.pl"
    result_path = args.output_dir / "packing_hint" / "result.json"
    placement_path.parent.mkdir(parents=True, exist_ok=True)
    placedb.write_pl(None, str(placement_path), node_x, node_y)
    write_json(
        result_path,
        {
            "schema": "m336_discrete_packing_hint_v1",
            "assignment": repo_path(args.assignment),
            "fixed_endpoint_mode": args.fixed_endpoint_mode,
            "manual_baseline_endpoint_overrides": sorted(
                set(args.manual_baseline_endpoint)
            ),
            "metrics": {
                "hpwl": hpwl,
                "baseline_hpwl": baseline_hpwl,
                "baseline_rsmt": baseline_rsmt,
                "normalized_score_upper_bound": score_upper_bound,
            },
            "legality": legality,
            "packing_stats": packing_stats,
            "selected_sites": selected_sites,
            "placement": repo_path(placement_path),
        },
    )
    return site_indices, {
        "result": repo_path(result_path),
        "result_sha256": sha256_file(result_path),
        "placement": repo_path(placement_path),
        "hpwl": hpwl,
        "normalized_score_upper_bound": score_upper_bound,
        "keepin_violation_count": legality["keepin_violation_count"],
        "overlap_pair_count": legality["overlap_pair_count"],
    }


def _load_site_hint(
    args,
    placedb,
    context,
    baseline_x,
    baseline_y,
    fixed_x,
    fixed_y,
    baseline_hpwl,
    baseline_rsmt,
):
    placement = parse_placement(args.site_hint_placement)
    position = np.zeros(2 * placedb.num_nodes, dtype=np.float64)
    position[: placedb.num_physical_nodes] = baseline_x
    position[
        placedb.num_nodes : placedb.num_nodes + placedb.num_physical_nodes
    ] = baseline_y
    constrained_ids = {constraint.node_id for constraint in context.constraints}
    for node_id in range(placedb.num_physical_nodes):
        if node_id in constrained_ids:
            continue
        position[node_id] = fixed_x[node_id]
        position[placedb.num_nodes + node_id] = fixed_y[node_id]

    site_indices = {}
    snap_distances = []
    for constraint in context.constraints:
        if constraint.refdes not in placement:
            raise ValueError(
                "site hint placement is missing %s" % constraint.refdes
            )
        lower_left_x, lower_left_y = placement[constraint.refdes]
        center = (
            lower_left_x + constraint.node_width / 2,
            lower_left_y + constraint.node_height / 2,
        )
        site_index, snap_distance = _nearest_site_index(
            constraint.domain.valid_centers, center
        )
        if snap_distance > 1e-5 and not args.snap_site_hint:
            raise ValueError(
                "site hint for %s is %.9g from the nearest exact site"
                % (constraint.refdes, snap_distance)
            )
        snapped_center = constraint.domain.valid_centers[site_index]
        site_indices[constraint.node_id] = {
            "region_id": constraint.region_id,
            "site_index": site_index,
        }
        snap_distances.append(snap_distance)
        position[constraint.node_id] = (
            snapped_center[0] - constraint.node_width / 2
        )
        position[placedb.num_nodes + constraint.node_id] = (
            snapped_center[1] - constraint.node_height / 2
        )

    node_x = position[: placedb.num_physical_nodes]
    node_y = position[
        placedb.num_nodes : placedb.num_nodes + placedb.num_physical_nodes
    ]
    legality = context.exact_report(torch.from_numpy(position), placedb)
    hpwl = float(placedb.hpwl(node_x, node_y))
    score_upper_bound = 2.0 / (
        hpwl / baseline_hpwl + hpwl / baseline_rsmt
    )
    return site_indices, {
        "kind": "placement",
        "placement": repo_path(args.site_hint_placement),
        "placement_sha256": sha256_file(args.site_hint_placement),
        "hpwl": hpwl,
        "normalized_score_upper_bound": score_upper_bound,
        "keepin_violation_count": legality["keepin_violation_count"],
        "overlap_pair_count": legality["overlap_pair_count"],
        "snap_to_exact_site": args.snap_site_hint,
        "snapped_component_count": sum(
            distance > 1e-5 for distance in snap_distances
        ),
        "maximum_snap_distance": max(snap_distances, default=0.0),
        "mean_snap_distance": (
            sum(snap_distances) / len(snap_distances)
            if snap_distances
            else 0.0
        ),
    }


def _load_result_site_hint(
    args,
    placedb,
    context,
    assignment_space,
    baseline_x,
    baseline_y,
    fixed_x,
    fixed_y,
    baseline_hpwl,
    baseline_rsmt,
):
    data = json.loads(args.site_hint_result.read_text())
    selected_sites = data.get("selected_sites", {})
    position = np.zeros(2 * placedb.num_nodes, dtype=np.float64)
    position[: placedb.num_physical_nodes] = baseline_x
    position[
        placedb.num_nodes : placedb.num_nodes + placedb.num_physical_nodes
    ] = baseline_y
    constrained_ids = {constraint.node_id for constraint in context.constraints}
    for node_id in range(placedb.num_physical_nodes):
        if node_id in constrained_ids:
            continue
        position[node_id] = fixed_x[node_id]
        position[placedb.num_nodes + node_id] = fixed_y[node_id]

    site_indices = {}
    hinted_regions = {}
    selected_constraints = []
    for constraint in context.constraints:
        if constraint.refdes not in selected_sites:
            raise ValueError(
                "site hint result is missing %s" % constraint.refdes
            )
        row = selected_sites[constraint.refdes]
        group_id = assignment_space["node_groups"][constraint.node_id]
        region_id = row.get("region_id")
        if region_id not in assignment_space["group_options"][group_id]:
            raise ValueError(
                "site hint result region is ineligible for %s"
                % constraint.refdes
            )
        if group_id in hinted_regions and hinted_regions[group_id] != region_id:
            raise ValueError(
                "site hint result splits subgroup %s across regions" % group_id
            )
        hinted_regions[group_id] = region_id
        domain = assignment_space["domains"][(constraint.node_id, region_id)]
        center = np.asarray(row["center"], dtype=np.float64)
        site_index = _exact_site_index(
            domain.valid_centers, center, tolerance=1e-5
        )
        exact_center = domain.valid_centers[site_index]
        site_indices[constraint.node_id] = {
            "region_id": region_id,
            "site_index": site_index,
        }
        position[constraint.node_id] = (
            exact_center[0] - constraint.node_width / 2
        )
        position[placedb.num_nodes + constraint.node_id] = (
            exact_center[1] - constraint.node_height / 2
        )
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

    node_x = position[: placedb.num_physical_nodes]
    node_y = position[
        placedb.num_nodes : placedb.num_nodes + placedb.num_physical_nodes
    ]
    legality = context.exact_report(
        torch.from_numpy(position), placedb, constraints=selected_constraints
    )
    hpwl = float(placedb.hpwl(node_x, node_y))
    score_upper_bound = 2.0 / (
        hpwl / baseline_hpwl + hpwl / baseline_rsmt
    )
    return site_indices, {
        "kind": "result",
        "result": repo_path(args.site_hint_result),
        "result_sha256": sha256_file(args.site_hint_result),
        "hpwl": hpwl,
        "normalized_score_upper_bound": score_upper_bound,
        "keepin_violation_count": legality["keepin_violation_count"],
        "overlap_pair_count": legality["overlap_pair_count"],
    }


def _load_candidate_guide(args, context):
    placement = parse_placement(args.candidate_guide_placement)
    guide_centers = {}
    distances = []
    for constraint in context.constraints:
        if constraint.refdes not in placement:
            raise ValueError(
                "candidate guide is missing %s" % constraint.refdes
            )
        lower_left_x, lower_left_y = placement[constraint.refdes]
        center = (
            lower_left_x + constraint.node_width / 2,
            lower_left_y + constraint.node_height / 2,
        )
        _, distance = _nearest_site_index(
            constraint.domain.valid_centers, center
        )
        guide_centers[constraint.node_id] = center
        distances.append(distance)
    return guide_centers, {
        "placement": repo_path(args.candidate_guide_placement),
        "placement_sha256": sha256_file(args.candidate_guide_placement),
        "maximum_projection_distance": max(distances, default=0.0),
        "mean_projection_distance": (
            sum(distances) / len(distances) if distances else 0.0
        ),
    }


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


def _scoped_assignment_space(assignment_space, site_hints, movable_subgroups):
    movable_subgroups = set(movable_subgroups or ())
    if not movable_subgroups:
        return assignment_space
    if assignment_space["mode"] != "optimized":
        raise ValueError("scoped assignment requires optimized assignment")
    unknown = sorted(
        movable_subgroups - set(assignment_space["group_options"])
    )
    if unknown:
        raise ValueError(
            "unknown movable subgroups: %s" % ", ".join(unknown)
        )
    hinted_regions = _hinted_group_regions(site_hints, assignment_space)
    missing = sorted(
        group_id
        for group_id, nodes in assignment_space["group_nodes"].items()
        if nodes and group_id not in hinted_regions
    )
    if missing:
        raise ValueError(
            "scoped assignment requires complete subgroup hints: %s"
            % ", ".join(missing)
        )
    output = dict(assignment_space)
    output["mode"] = "optimized_scoped"
    output["group_options"] = {
        group_id: (
            options
            if group_id in movable_subgroups
            else (
                hinted_regions.get(
                    group_id,
                    assignment_space["preferred_regions"][group_id],
                ),
            )
        )
        for group_id, options in assignment_space["group_options"].items()
    }
    output["movable_subgroups"] = tuple(sorted(movable_subgroups))
    return output


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


def _ring_without_collinear_vertices(coordinates, epsilon=1e-12):
    vertices = []
    for coordinate in coordinates:
        point = (float(coordinate[0]), float(coordinate[1]))
        if not vertices or point != vertices[-1]:
            vertices.append(point)
    if len(vertices) > 1 and vertices[0] == vertices[-1]:
        vertices.pop()

    changed = True
    while changed and len(vertices) > 3:
        changed = False
        retained = []
        for index, current in enumerate(vertices):
            previous = vertices[index - 1]
            following = vertices[(index + 1) % len(vertices)]
            cross = (
                (current[0] - previous[0])
                * (following[1] - current[1])
                - (current[1] - previous[1])
                * (following[0] - current[0])
            )
            if abs(cross) <= epsilon:
                changed = True
                continue
            retained.append(current)
        if retained:
            vertices = retained
    return vertices


def _signed_ring_area(vertices):
    return 0.5 * sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(vertices, vertices[1:] + vertices[:1])
    )


def _triangle_cross(first, second, third):
    return (
        (second[0] - first[0]) * (third[1] - first[1])
        - (second[1] - first[1]) * (third[0] - first[0])
    )


def _ear_clip_polygon(shape, epsilon=1e-9):
    if shape.interiors:
        raise ValueError("footprints with holes require explicit decomposition")
    vertices = _ring_without_collinear_vertices(shape.exterior.coords)
    if len(vertices) < 3:
        raise ValueError("footprint polygon has fewer than three vertices")
    if _signed_ring_area(vertices) < 0:
        vertices.reverse()

    source = shape.buffer(epsilon)
    triangles = []
    while len(vertices) > 3:
        ear_index = None
        for index, current in enumerate(vertices):
            previous = vertices[index - 1]
            following = vertices[(index + 1) % len(vertices)]
            if _triangle_cross(previous, current, following) <= epsilon:
                continue
            triangle = Polygon((previous, current, following))
            if not source.covers(triangle):
                continue
            if any(
                triangle.contains(Point(candidate))
                for candidate_index, candidate in enumerate(vertices)
                if candidate_index
                not in (index - 1, index, (index + 1) % len(vertices))
            ):
                continue
            ear_index = index
            triangles.append(triangle)
            break
        if ear_index is None:
            if abs(_signed_ring_area(vertices)) <= epsilon:
                vertices = []
                break
            raise ValueError("deterministic footprint triangulation failed")
        vertices.pop(ear_index)
    if len(vertices) == 3 and abs(_signed_ring_area(vertices)) > epsilon:
        triangles.append(Polygon(vertices))
    return tuple(triangles)


def _convex_parts(shape, epsilon=1e-8):
    if shape.is_empty or not shape.is_valid:
        raise ValueError("footprint must be non-empty and valid")
    if shape.geom_type == "MultiPolygon":
        parts = tuple(
            part
            for polygon in shape.geoms
            for part in _convex_parts(polygon, epsilon)
        )
    elif shape.geom_type != "Polygon":
        raise ValueError("unsupported footprint geometry: %s" % shape.geom_type)
    elif shape.convex_hull.area - shape.area <= epsilon:
        parts = (shape,)
    else:
        parts = _ear_clip_polygon(shape, epsilon=epsilon)

    merged = unary_union(parts)
    if shape.symmetric_difference(merged).area > epsilon:
        raise ValueError("footprint convex decomposition changed its area")
    if sum(part.area for part in parts) - shape.area > epsilon:
        raise ValueError("footprint convex decomposition contains overlaps")
    return parts


def _horizontal_inner_rectangles(shape, slice_count, epsilon=1e-10):
    if slice_count <= 0:
        return ()
    if shape.is_empty or not shape.is_valid:
        raise ValueError("inner rectangles require a non-empty valid polygon")
    if shape.convex_hull.symmetric_difference(shape).area > epsilon:
        raise ValueError("inner rectangles require a convex polygon")

    min_x, min_y, max_x, max_y = shape.bounds
    y_edges = np.linspace(min_y, max_y, slice_count + 1)
    vertex_y = sorted({float(y) for _, y in shape.exterior.coords[:-1]})
    inset = max(epsilon, (max_y - min_y) * 1e-9)
    rectangles = []
    for low_y, high_y in zip(y_edges[:-1], y_edges[1:]):
        sample_y = [low_y + inset, high_y - inset]
        sample_y.extend(y for y in vertex_y if low_y < y < high_y)
        intervals = []
        for y in sample_y:
            cross_section = shape.intersection(
                LineString(((min_x - 1.0, y), (max_x + 1.0, y)))
            )
            if not cross_section.is_empty:
                bounds = cross_section.bounds
                intervals.append((bounds[0], bounds[2]))
        if not intervals:
            continue
        low_x = max(interval[0] for interval in intervals) + inset
        high_x = min(interval[1] for interval in intervals) - inset
        if high_x <= low_x or high_y - low_y <= 2 * inset:
            continue
        rectangle = box(
            low_x,
            low_y + inset,
            high_x,
            high_y - inset,
        )
        if not shape.covers(rectangle):
            raise ValueError("generated inner rectangle escaped its polygon")
        rectangles.append(rectangle)
    return tuple(rectangles)


def _scaled_inner_rectangles(
    shape,
    node_width,
    node_height,
    integer_scale,
    slice_count,
):
    rectangles = []
    for rectangle in _horizontal_inner_rectangles(shape, slice_count):
        min_x, min_y, max_x, max_y = rectangle.bounds
        low_x = int(
            math.ceil(
                (node_width / 2 + min_x) * integer_scale - 1e-12
            )
        )
        low_y = int(
            math.ceil(
                (node_height / 2 + min_y) * integer_scale - 1e-12
            )
        )
        high_x = int(
            math.floor(
                (node_width / 2 + max_x) * integer_scale + 1e-12
            )
        )
        high_y = int(
            math.floor(
                (node_height / 2 + max_y) * integer_scale + 1e-12
            )
        )
        if high_x <= low_x or high_y <= low_y:
            continue
        scaled_rectangle = box(
            low_x / integer_scale - node_width / 2,
            low_y / integer_scale - node_height / 2,
            high_x / integer_scale - node_width / 2,
            high_y / integer_scale - node_height / 2,
        )
        if not shape.covers(scaled_rectangle):
            raise ValueError(
                "scaled inner rectangle escaped its footprint"
            )
        rectangles.append(
            (low_x, low_y, high_x - low_x, high_y - low_y)
        )
    return tuple(rectangles)


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


def _model_convex_parts(
    name,
    shape,
    node_width,
    node_height,
    x_translation,
    y_translation,
    integer_scale,
    collision_mode,
):
    try:
        source_parts = (
            _convex_parts(shape)
            if collision_mode == "decomposed"
            else (shape.convex_hull,)
        )
    except ValueError as error:
        raise ValueError("%s: %s" % (name, error)) from error
    return tuple(
        {
            "name": "%s_part_%d" % (name, index),
            "x": x_translation,
            "y": y_translation,
            "vertices": _convex_vertices(
                part, node_width, node_height, integer_scale
            ),
        }
        for index, part in enumerate(source_parts)
    )


def _fixed_footprint_local(context, placedb, node_id, collision_mode):
    node_width = float(placedb.node_size_x[node_id])
    node_height = float(placedb.node_size_y[node_id])
    name = _decode(placedb.node_names[node_id])
    if collision_mode == "decomposed" and name in context.geometry.symbols:
        symbol = context.geometry.symbols[name]
        source_center = context.alignment.transform_point(symbol.center_mm)
        return affinity.translate(
            context.alignment.transform_geometry(symbol.footprint_mm),
            xoff=-source_center[0],
            yoff=-source_center[1],
        )
    return box(
        -node_width / 2,
        -node_height / 2,
        node_width / 2,
        node_height / 2,
    )


def _add_rectangle_nonoverlap(model, first, second):
    left = model.new_bool_var(
        "%s_left_of_%s" % (first["name"], second["name"])
    )
    right = model.new_bool_var(
        "%s_right_of_%s" % (first["name"], second["name"])
    )
    below = model.new_bool_var(
        "%s_below_%s" % (first["name"], second["name"])
    )
    above = model.new_bool_var(
        "%s_above_%s" % (first["name"], second["name"])
    )
    model.add(
        first["bbox_x"] + first["width"] <= second["bbox_x"]
    ).only_enforce_if(left)
    model.add(
        second["bbox_x"] + second["width"] <= first["bbox_x"]
    ).only_enforce_if(right)
    model.add(
        first["bbox_y"] + first["height"] <= second["bbox_y"]
    ).only_enforce_if(below)
    model.add(
        second["bbox_y"] + second["height"] <= first["bbox_y"]
    ).only_enforce_if(above)
    model.add_bool_or((left, right, below, above))


def _add_part_nonoverlap(model, first, second):
    count = 0
    for first_part in first["parts"]:
        for second_part in second["parts"]:
            _add_convex_nonoverlap(model, first_part, second_part)
            count += 1
    return count


def _swept_bboxes_may_overlap(first, second):
    first_min_x, first_min_y, first_max_x, first_max_y = first[
        "swept_bbox"
    ]
    second_min_x, second_min_y, second_max_x, second_max_y = second[
        "swept_bbox"
    ]
    return not (
        first_max_x <= second_min_x
        or second_max_x <= first_min_x
        or first_max_y <= second_min_y
        or second_max_y <= first_min_y
    )


def _add_assignment_variables(
    model, assignment_space, capacity_scale, hinted_regions=None
):
    hinted_regions = dict(hinted_regions or {})
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
        preferred_region = hinted_regions.get(
            group_id, assignment_space["preferred_regions"][group_id]
        )
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
    fixed_x,
    fixed_y,
    minimum_score,
    baseline_hpwl,
    baseline_rsmt,
    integer_scale,
    collision_mode,
    assignment_space,
    capacity_scale,
    candidate_limit_per_region,
    site_hints=None,
    site_hint_report=None,
    candidate_guides=None,
    candidate_guide_report=None,
    optimize_hpwl=True,
    movable_refdes=(),
    enforce_hpwl=True,
    packing_side=None,
    site_model="element",
    packing_objective="none",
    prune_fixed_obstacle_sites=False,
    fix_site_hint=False,
    controlled_collision_relaxation="none",
    controlled_collision_pairs=(),
    nonrectangle_inner_slices=0,
):
    if site_model not in ("element", "coordinate-table"):
        raise ValueError("unknown site model: %s" % site_model)
    if packing_objective not in ("none", "hint-l1"):
        raise ValueError("unknown packing objective: %s" % packing_objective)
    if packing_objective != "none" and enforce_hpwl:
        raise ValueError("packing objectives require HPWL to be disabled")
    if prune_fixed_obstacle_sites and collision_mode != "decomposed":
        raise ValueError(
            "fixed-obstacle site pruning requires decomposed collision mode"
        )
    if controlled_collision_relaxation not in (
        "none",
        "mixed-nonrectangle",
        "all-nonrectangle",
    ):
        raise ValueError(
            "unknown controlled collision relaxation: %s"
            % controlled_collision_relaxation
        )
    if controlled_collision_relaxation != "none" and (
        collision_mode != "decomposed" or enforce_hpwl
    ):
        raise ValueError(
            "controlled nonrectangle relaxation requires decomposed "
            "packing-only mode"
        )
    controlled_collision_pairs = _normalize_controlled_collision_pairs(
        controlled_collision_pairs
    )
    if nonrectangle_inner_slices < 0:
        raise ValueError("nonrectangle inner slice count must be non-negative")
    if controlled_collision_pairs:
        if controlled_collision_relaxation != "none":
            raise ValueError(
                "collision pair allowlists and category relaxations are "
                "mutually exclusive"
            )
        if collision_mode != "decomposed" or enforce_hpwl:
            raise ValueError(
                "collision pair allowlists require decomposed packing-only "
                "mode"
            )
    site_hints = dict(site_hints or {})
    candidate_guides = dict(candidate_guides or {})
    model = cp_model.CpModel()
    hinted_regions = _hinted_group_regions(site_hints, assignment_space)
    assignment_state = _add_assignment_variables(
        model, assignment_space, capacity_scale, hinted_regions
    )
    modeled_constraints = tuple(
        constraint
        for constraint in context.constraints
        if packing_side is None or constraint.side == packing_side
    )
    constraint_by_node = {
        constraint.node_id: constraint for constraint in modeled_constraints
    }
    all_controlled_ids = {
        constraint.node_id for constraint in context.constraints
    }
    fixed_hint_refdes = _partial_fix_refdes(
        modeled_constraints, movable_refdes
    )
    if fixed_hint_refdes and not site_hints:
        raise ValueError("partial site fixing requires a complete site hint")
    fixed_obstacles = {"TOP": [], "BOTTOM": []}
    if prune_fixed_obstacle_sites:
        for node_id in range(placedb.num_physical_nodes):
            if node_id in all_controlled_ids:
                continue
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            if packing_side is not None and side != packing_side:
                continue
            node_width = float(placedb.node_size_x[node_id])
            node_height = float(placedb.node_size_y[node_id])
            footprint_local = _fixed_footprint_local(
                context, placedb, node_id, collision_mode
            )
            fixed_obstacles[side].append(
                affinity.translate(
                    footprint_local,
                    xoff=float(fixed_x[node_id]) + node_width / 2,
                    yoff=float(fixed_y[node_id]) + node_height / 2,
                )
            )
    site_vars = {}
    site_choices = {}
    x_vars = {}
    y_vars = {}
    candidate_count = 0
    x_intervals = {"TOP": [], "BOTTOM": []}
    y_intervals = {"TOP": [], "BOTTOM": []}
    controlled_shapes = {"TOP": [], "BOTTOM": []}
    controlled_inner_rectangle_reports = []
    packing_distance_terms = []
    fixed_obstacle_candidate_count = 0
    fixed_obstacle_pruned_site_count = 0
    site_hint_remapped_count = 0
    site_hint_maximum_remap_distance = 0.0
    site_hint_remaps = []

    for constraint in sorted(modeled_constraints, key=lambda item: item.refdes):
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
        hint_region_id = None
        hint_local_index = None
        hint_center = None
        if node_id in site_hints:
            hint_region_id, hint_local_index = _site_hint_parts(
                site_hints[node_id]
            )
            if hint_region_id not in options:
                raise ValueError(
                    "site hint region is ineligible for %s"
                    % constraint.refdes
                )
            hint_domain = assignment_space["domains"][
                (node_id, hint_region_id)
            ]
            if not 0 <= hint_local_index < len(hint_domain.valid_centers):
                raise ValueError(
                    "site hint index is out of range for %s"
                    % constraint.refdes
                )
            hint_center = hint_domain.valid_centers[hint_local_index]
        eligible_indices = []
        for domain in domain_options:
            fixed_obstacle_candidate_count += len(domain.valid_centers)
            if prune_fixed_obstacle_sites:
                eligible = _candidate_indices_without_obstacle_overlap(
                    domain.footprint_local,
                    domain.valid_centers,
                    fixed_obstacles[constraint.side],
                )
            else:
                eligible = np.arange(
                    len(domain.valid_centers), dtype=np.int64
                )
            fixed_obstacle_pruned_site_count += (
                len(domain.valid_centers) - len(eligible)
            )
            eligible_indices.append(eligible)
        if constraint.refdes in fixed_hint_refdes:
            selected_indices = _fixed_hint_candidate_indices(
                options, hint_region_id, hint_local_index
            )
            selected_hint = selected_indices[options.index(hint_region_id)]
            eligible_hint = eligible_indices[options.index(hint_region_id)]
            if not np.isin(selected_hint, eligible_hint).all():
                raise ValueError(
                    "fixed site hint overlaps a fixed obstacle: %s"
                    % constraint.refdes
                )
        else:
            selected_indices = []
            guide_indices = (
                _guide_site_indices(
                    domain_options, candidate_guides[node_id]
                )
                if node_id in candidate_guides
                else (None,) * len(domain_options)
            )
            for region_id, domain, guide_index, eligible in zip(
                options, domain_options, guide_indices, eligible_indices
            ):
                preferred_index = None
                if hint_center is not None:
                    preferred_index = (
                        hint_local_index
                        if region_id == hint_region_id
                        else _nearest_site_index(
                            domain.valid_centers, hint_center
                        )[0]
                    )
                selected_indices.append(
                    _limited_candidate_indices(
                        domain.valid_centers,
                        candidate_limit_per_region,
                        preferred_index,
                        (() if guide_index is None else (guide_index,)),
                        eligible,
                    )
                )
        centers = np.concatenate(
            [
                domain.valid_centers[indices]
                for domain, indices in zip(domain_options, selected_indices)
            ],
            axis=0,
        )
        region_indices = np.concatenate(
            [
                np.full(len(indices), index, dtype=np.int64)
                for index, indices in enumerate(selected_indices)
            ]
        )
        local_indices = np.concatenate(
            selected_indices
        )
        if not len(centers):
            raise ValueError(
                "component has no fixed-obstacle-free candidate: %s"
                % constraint.refdes
            )
        x_values = np.rint(
            (centers[:, 0] - constraint.node_width / 2) * integer_scale
        ).astype(np.int64)
        y_values = np.rint(
            (centers[:, 1] - constraint.node_height / 2) * integer_scale
        ).astype(np.int64)
        if site_model == "element":
            site = model.new_int_var(
                0, len(centers) - 1, "site_%s" % constraint.refdes
            )
            x_var = model.new_int_var(
                int(x_values.min()),
                int(x_values.max()),
                "x_%s" % constraint.refdes,
            )
            y_var = model.new_int_var(
                int(y_values.min()),
                int(y_values.max()),
                "y_%s" % constraint.refdes,
            )
            model.add_element(site, x_values.tolist(), x_var)
            model.add_element(site, y_values.tolist(), y_var)
            model.add_element(
                site,
                region_indices.tolist(),
                assignment_state["group_vars"][group_id],
            )
            site_vars[node_id] = site
        else:
            site = None
            x_var = model.new_int_var_from_domain(
                cp_model.Domain.from_values(
                    np.unique(x_values).astype(np.int64).tolist()
                ),
                "x_%s" % constraint.refdes,
            )
            y_var = model.new_int_var_from_domain(
                cp_model.Domain.from_values(
                    np.unique(y_values).astype(np.int64).tolist()
                ),
                "y_%s" % constraint.refdes,
            )
            model.add_allowed_assignments(
                (
                    x_var,
                    y_var,
                    assignment_state["group_vars"][group_id],
                ),
                [
                    [int(x_value), int(y_value), int(region_index)]
                    for x_value, y_value, region_index in zip(
                        x_values, y_values, region_indices
                    )
                ],
            )
        site_choices[node_id] = {
            "centers": centers,
            "x_values": x_values,
            "y_values": y_values,
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
        elif nonrectangle_inner_slices:
            is_convex = (
                footprint_local.convex_hull.symmetric_difference(
                    footprint_local
                ).area
                <= 1e-8
            )
            inner_rectangles = (
                _scaled_inner_rectangles(
                    footprint_local,
                    constraint.node_width,
                    constraint.node_height,
                    integer_scale,
                    nonrectangle_inner_slices,
                )
                if is_convex
                else ()
            )
            for inner_index, (
                inner_x_offset,
                inner_y_offset,
                inner_width,
                inner_height,
            ) in enumerate(inner_rectangles):
                x_intervals[constraint.side].append(
                    model.new_fixed_size_interval_var(
                        x_var + inner_x_offset,
                        inner_width,
                        "ix_inner_%s_%d"
                        % (constraint.refdes, inner_index),
                    )
                )
                y_intervals[constraint.side].append(
                    model.new_fixed_size_interval_var(
                        y_var + inner_y_offset,
                        inner_height,
                        "iy_inner_%s_%d"
                        % (constraint.refdes, inner_index),
                    )
                )
            inner_area = sum(
                width_units * height_units
                for _, _, width_units, height_units in inner_rectangles
            ) / float(integer_scale**2)
            controlled_inner_rectangle_reports.append(
                {
                    "refdes": constraint.refdes,
                    "rectangle_count": len(inner_rectangles),
                    "footprint_area": float(footprint_local.area),
                    "inner_area": inner_area,
                    "coverage": inner_area / float(footprint_local.area),
                    "skip_reason": None if is_convex else "nonconvex",
                }
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
                "swept_bbox": (
                    int(x_values.min()) + x_offset,
                    int(y_values.min()) + y_offset,
                    int(x_values.max()) + x_offset + width,
                    int(y_values.max()) + y_offset + height,
                ),
                "parts": _model_convex_parts(
                    constraint.refdes,
                    footprint_local,
                    constraint.node_width,
                    constraint.node_height,
                    x_var,
                    y_var,
                    integer_scale,
                    collision_mode,
                ),
            }
        )

        if node_id in site_hints:
            hint_region_index = options.index(hint_region_id)
            matches = np.flatnonzero(
                (region_indices == hint_region_index)
                & (local_indices == hint_local_index)
            )
            if len(matches) > 1:
                raise ValueError("site hint maps to multiple candidates")
            if not len(matches):
                if fix_site_hint or constraint.refdes in fixed_hint_refdes:
                    raise ValueError(
                        "fixed site hint is absent after obstacle pruning"
                    )
                same_region = np.flatnonzero(
                    region_indices == hint_region_index
                )
                match_index = None
                if len(same_region):
                    distances = np.square(
                        centers[same_region] - hint_center
                    ).sum(axis=1)
                    match_index = int(
                        same_region[int(np.argmin(distances))]
                    )
                    remap_distance = math.sqrt(
                        float(distances[np.argmin(distances)])
                    )
                    site_hint_remapped_count += 1
                    site_hint_maximum_remap_distance = max(
                        site_hint_maximum_remap_distance, remap_distance
                    )
                    site_hint_remaps.append(
                        {
                            "refdes": constraint.refdes,
                            "from_center": [
                                float(hint_center[0]),
                                float(hint_center[1]),
                            ],
                            "to_center": [
                                float(centers[match_index, 0]),
                                float(centers[match_index, 1]),
                            ],
                            "distance": remap_distance,
                        }
                    )
            else:
                match_index = int(matches[0])
            if match_index is not None:
                if site_model == "element":
                    model.add_hint(site, match_index)
                else:
                    model.add_hint(x_var, int(x_values[match_index]))
                    model.add_hint(y_var, int(y_values[match_index]))
            if constraint.refdes in fixed_hint_refdes:
                if site_model == "element":
                    model.add(site == match_index)
                else:
                    model.add(x_var == int(x_values[match_index]))
                    model.add(y_var == int(y_values[match_index]))
            if packing_objective == "hint-l1":
                hinted_x = _scaled(
                    hint_center[0] - constraint.node_width / 2,
                    integer_scale,
                )
                hinted_y = _scaled(
                    hint_center[1] - constraint.node_height / 2,
                    integer_scale,
                )
                maximum_dx = max(
                    abs(int(x_values.min()) - hinted_x),
                    abs(int(x_values.max()) - hinted_x),
                )
                maximum_dy = max(
                    abs(int(y_values.min()) - hinted_y),
                    abs(int(y_values.max()) - hinted_y),
                )
                dx = model.new_int_var(
                    0, maximum_dx, "hint_dx_%s" % constraint.refdes
                )
                dy = model.new_int_var(
                    0, maximum_dy, "hint_dy_%s" % constraint.refdes
                )
                model.add_abs_equality(dx, x_var - hinted_x)
                model.add_abs_equality(dy, y_var - hinted_y)
                packing_distance_terms.extend((dx, dy))
        else:
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
                        np.square(
                            centers[preferred_candidates] - target
                        ).sum(axis=1)
                    )
                ]
            )
            if site_model == "element":
                model.add_hint(site, nearest)
            else:
                model.add_hint(x_var, int(x_values[nearest]))
                model.add_hint(y_var, int(y_values[nearest]))

    controlled_shape_index = {
        shape["name"]: (side, shape)
        for side, shapes in controlled_shapes.items()
        for shape in shapes
    }
    requested_refdes = {
        refdes
        for pair in controlled_collision_pairs
        for refdes in pair
    }
    unknown_refdes = sorted(requested_refdes - set(controlled_shape_index))
    if unknown_refdes:
        raise ValueError(
            "collision pair refdes are not modeled controlled components: %s"
            % ", ".join(unknown_refdes)
        )
    for first_name, second_name in controlled_collision_pairs:
        first_side, first_shape = controlled_shape_index[first_name]
        second_side, second_shape = controlled_shape_index[second_name]
        if first_side != second_side:
            raise ValueError(
                "controlled collision pair crosses board sides: %s/%s"
                % (first_name, second_name)
            )
        if first_shape["is_rectangle"] and second_shape["is_rectangle"]:
            raise ValueError(
                "rectangle collision pair is already in NoOverlap2D: %s/%s"
                % (first_name, second_name)
            )

    collision_pair_constraint_count = 0
    collision_component_pair_count = 0
    collision_skipped_component_pair_count = 0
    fixed_obstacle_pair_eliminated_count = 0
    relaxed_controlled_component_pair_count = 0
    exact_controlled_component_pair_count = 0
    available_controlled_collision_pairs = set()
    fixed_shapes = {"TOP": [], "BOTTOM": []}
    if collision_mode in ("convex", "decomposed"):
        for node_id in range(placedb.num_physical_nodes):
            if node_id in all_controlled_ids:
                continue
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            if packing_side is not None and side != packing_side:
                continue
            name = _decode(placedb.node_names[node_id])
            fixed_start_x = _scaled(fixed_x[node_id], integer_scale)
            fixed_start_y = _scaled(fixed_y[node_id], integer_scale)
            node_width = float(placedb.node_size_x[node_id])
            node_height = float(placedb.node_size_y[node_id])
            footprint_local = _fixed_footprint_local(
                context, placedb, node_id, collision_mode
            )
            local_min_x, local_min_y, local_max_x, local_max_y = (
                footprint_local.bounds
            )
            fixed_bbox_x = fixed_start_x + _scaled(
                node_width / 2 + local_min_x, integer_scale
            )
            fixed_bbox_y = fixed_start_y + _scaled(
                node_height / 2 + local_min_y, integer_scale
            )
            fixed_width = max(
                1, _scaled(local_max_x - local_min_x, integer_scale)
            )
            fixed_height = max(
                1, _scaled(local_max_y - local_min_y, integer_scale)
            )
            fixed_shape = {
                "name": name,
                "x": fixed_start_x,
                "y": fixed_start_y,
                "bbox_x": fixed_bbox_x,
                "bbox_y": fixed_bbox_y,
                "width": fixed_width,
                "height": fixed_height,
                "is_rectangle": _is_rectangle(footprint_local),
                "swept_bbox": (
                    fixed_bbox_x,
                    fixed_bbox_y,
                    fixed_bbox_x + fixed_width,
                    fixed_bbox_y + fixed_height,
                ),
                "parts": _model_convex_parts(
                    name,
                    footprint_local,
                    node_width,
                    node_height,
                    fixed_start_x,
                    fixed_start_y,
                    integer_scale,
                    collision_mode,
                ),
            }
            fixed_shapes[side].append(fixed_shape)
            for controlled in controlled_shapes[side]:
                if not _swept_bboxes_may_overlap(controlled, fixed_shape):
                    collision_skipped_component_pair_count += 1
                    continue
                collision_component_pair_count += 1
                if prune_fixed_obstacle_sites:
                    fixed_obstacle_pair_eliminated_count += 1
                    continue
                if (
                    controlled["is_rectangle"]
                    and fixed_shape["is_rectangle"]
                ):
                    _add_rectangle_nonoverlap(model, controlled, fixed_shape)
                    collision_pair_constraint_count += 1
                else:
                    collision_pair_constraint_count += _add_part_nonoverlap(
                        model, controlled, fixed_shape
                    )

        collision_sides = (
            (packing_side,) if packing_side is not None else ("TOP", "BOTTOM")
        )
        for side in collision_sides:
            model.add_no_overlap_2d(x_intervals[side], y_intervals[side])
            shapes = controlled_shapes[side]
            for first_index, first in enumerate(shapes):
                for second in shapes[first_index + 1 :]:
                    if first["is_rectangle"] and second["is_rectangle"]:
                        continue
                    if not _swept_bboxes_may_overlap(first, second):
                        collision_skipped_component_pair_count += 1
                        continue
                    collision_component_pair_count += 1
                    pair = tuple(sorted((first["name"], second["name"])))
                    available_controlled_collision_pairs.add(pair)
                    if controlled_collision_pairs:
                        relax_pair = pair not in controlled_collision_pairs
                    else:
                        relax_pair = (
                            controlled_collision_relaxation
                            == "all-nonrectangle"
                            or (
                                controlled_collision_relaxation
                                == "mixed-nonrectangle"
                                and first["is_rectangle"]
                                != second["is_rectangle"]
                            )
                        )
                    if relax_pair:
                        relaxed_controlled_component_pair_count += 1
                        continue
                    exact_controlled_component_pair_count += 1
                    collision_pair_constraint_count += _add_part_nonoverlap(
                        model, first, second
                    )

    inactive_controlled_collision_pairs = sorted(
        _inactive_controlled_collision_pairs(
            controlled_collision_pairs,
            available_controlled_collision_pairs,
        )
    )

    hpwl_limit = None
    hpwl_limit_integer = None
    rounding_allowance = 0
    if enforce_hpwl:
        net_spans = []
        populated_net_weights = []
        coordinate_limit = 2**50
        for net_id, pins in enumerate(placedb.net2pin_map):
            pin_x = []
            pin_y = []
            for pin_id in pins:
                node_id = int(placedb.pin2node_map[pin_id])
                x_offset = _scaled(
                    placedb.pin_offset_x[pin_id], integer_scale
                )
                y_offset = _scaled(
                    placedb.pin_offset_y[pin_id], integer_scale
                )
                if node_id in constraint_by_node:
                    pin_x.append(x_vars[node_id] + x_offset)
                    pin_y.append(y_vars[node_id] + y_offset)
                else:
                    pin_x.append(
                        _scaled(fixed_x[node_id], integer_scale) + x_offset
                    )
                    pin_y.append(
                        _scaled(fixed_y[node_id], integer_scale) + y_offset
                    )
            if not pin_x:
                continue
            net_name = _decode(placedb.net_names[net_id])
            max_x = model.new_int_var(
                -coordinate_limit, coordinate_limit, "max_x_%s" % net_id
            )
            min_x = model.new_int_var(
                -coordinate_limit, coordinate_limit, "min_x_%s" % net_id
            )
            max_y = model.new_int_var(
                -coordinate_limit, coordinate_limit, "max_y_%s" % net_id
            )
            min_y = model.new_int_var(
                -coordinate_limit, coordinate_limit, "min_y_%s" % net_id
            )
            model.add_max_equality(max_x, pin_x)
            model.add_min_equality(min_x, pin_x)
            model.add_max_equality(max_y, pin_y)
            model.add_min_equality(min_y, pin_y)
            weight = float(placedb.net_weights[net_id])
            if weight < 0 or not math.isclose(
                weight, round(weight), abs_tol=1e-12
            ):
                raise ValueError(
                    "CP-SAT requires integral net weights: %s" % net_name
                )
            integral_weight = int(round(weight))
            populated_net_weights.append(integral_weight)
            net_spans.append(
                integral_weight * (max_x - min_x + max_y - min_y)
            )

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
        if optimize_hpwl:
            model.minimize(hpwl_objective)
    if packing_objective == "hint-l1":
        if not packing_distance_terms:
            raise ValueError("hint-l1 packing objective requires site hints")
        model.minimize(sum(packing_distance_terms))
    return model, {
        "site_vars": site_vars,
        "site_choices": site_choices,
        "x_vars": x_vars,
        "y_vars": y_vars,
        "assignment": assignment_state,
        "fixed_x": fixed_x,
        "fixed_y": fixed_y,
        "hpwl_limit": hpwl_limit,
        "hpwl_limit_integer": hpwl_limit_integer,
        "hpwl_rounding_allowance_integer": rounding_allowance,
        "hpwl_rounding_allowance": rounding_allowance / integer_scale,
        "candidate_count": candidate_count,
        "controlled_node_count": len(constraint_by_node),
        "total_controlled_node_count": len(all_controlled_ids),
        "fixed_node_count": placedb.num_physical_nodes - len(constraint_by_node),
        "controlled_nonrectangle_count": sum(
            not shape["is_rectangle"]
            for shapes in controlled_shapes.values()
            for shape in shapes
        ),
        "controlled_nonrectangle_refdes": sorted(
            shape["name"]
            for shapes in controlled_shapes.values()
            for shape in shapes
            if not shape["is_rectangle"]
        ),
        "controlled_convex_piece_count": sum(
            len(shape["parts"])
            for shapes in controlled_shapes.values()
            for shape in shapes
        ),
        "fixed_nonrectangle_count": sum(
            not shape["is_rectangle"]
            for shapes in fixed_shapes.values()
            for shape in shapes
        ),
        "fixed_convex_piece_count": sum(
            len(shape["parts"])
            for shapes in fixed_shapes.values()
            for shape in shapes
        ),
        "collision_pair_constraint_count": collision_pair_constraint_count,
        "collision_component_pair_count": collision_component_pair_count,
        "collision_skipped_component_pair_count": (
            collision_skipped_component_pair_count
        ),
        "fixed_obstacle_pair_eliminated_count": (
            fixed_obstacle_pair_eliminated_count
        ),
        "relaxed_controlled_component_pair_count": (
            relaxed_controlled_component_pair_count
        ),
        "exact_controlled_component_pair_count": (
            exact_controlled_component_pair_count
        ),
        "controlled_collision_relaxation": (
            controlled_collision_relaxation
        ),
        "controlled_collision_pair_allowlist": [
            list(pair) for pair in sorted(controlled_collision_pairs)
        ],
        "nonrectangle_inner_slices": nonrectangle_inner_slices,
        "controlled_inner_rectangle_count": sum(
            row["rectangle_count"]
            for row in controlled_inner_rectangle_reports
        ),
        "controlled_inner_rectangles": (
            controlled_inner_rectangle_reports
        ),
        "inactive_controlled_collision_pair_count": len(
            inactive_controlled_collision_pairs
        ),
        "inactive_controlled_collision_pairs": [
            list(pair) for pair in inactive_controlled_collision_pairs
        ],
        "fixed_obstacle_pruning_enabled": bool(
            prune_fixed_obstacle_sites
        ),
        "fixed_obstacle_count": sum(
            len(rows) for rows in fixed_obstacles.values()
        ),
        "fixed_obstacle_candidate_count": fixed_obstacle_candidate_count,
        "fixed_obstacle_pruned_site_count": (
            fixed_obstacle_pruned_site_count
        ),
        "site_hint_remapped_count": site_hint_remapped_count,
        "site_hint_maximum_remap_distance": (
            site_hint_maximum_remap_distance
        ),
        "site_hint_remaps": site_hint_remaps,
        "fixed_hint_site_count": len(fixed_hint_refdes),
        "movable_refdes": sorted(set(movable_refdes or ())),
        "site_hint": site_hint_report,
        "candidate_limit_per_region": candidate_limit_per_region,
        "candidate_guide": candidate_guide_report,
        "hpwl_gate_enabled": bool(enforce_hpwl),
        "optimize_hpwl": bool(optimize_hpwl and enforce_hpwl),
        "packing_side": packing_side,
        "site_model": site_model,
        "packing_objective": packing_objective,
        "optimize_packing": packing_objective != "none",
    }


def _model_report(args, state, assignment_space):
    assignment_state = state["assignment"]
    return {
        "integer_scale": args.integer_scale,
        "constraint_grid_mm": args.grid_mm,
        "minimum_score": args.minimum_score,
        "objective_mode": (
            (
                "packing_hint_l1"
                if state["optimize_packing"]
                else "packing_only"
            )
            if not state["hpwl_gate_enabled"]
            else (
                "minimize_hpwl"
                if state["optimize_hpwl"]
                else "first_feasible"
            )
        ),
        "hpwl_gate_enabled": state["hpwl_gate_enabled"],
        "necessary_hpwl_limit": state["hpwl_limit"],
        "integer_hpwl_limit": state["hpwl_limit_integer"],
        "hpwl_rounding_allowance": state["hpwl_rounding_allowance"],
        "candidate_count": state["candidate_count"],
        "site_model": state["site_model"],
        "packing_objective": state["packing_objective"],
        "candidate_limit_per_region": state[
            "candidate_limit_per_region"
        ],
        "controlled_node_count": state["controlled_node_count"],
        "total_controlled_node_count": state["total_controlled_node_count"],
        "fixed_node_count": state["fixed_node_count"],
        "controlled_nonrectangle_count": state[
            "controlled_nonrectangle_count"
        ],
        "controlled_nonrectangle_refdes": state[
            "controlled_nonrectangle_refdes"
        ],
        "controlled_convex_piece_count": state[
            "controlled_convex_piece_count"
        ],
        "fixed_nonrectangle_count": state["fixed_nonrectangle_count"],
        "fixed_convex_piece_count": state["fixed_convex_piece_count"],
        "collision_pair_constraint_count": state[
            "collision_pair_constraint_count"
        ],
        "collision_component_pair_count": state[
            "collision_component_pair_count"
        ],
        "collision_skipped_component_pair_count": state[
            "collision_skipped_component_pair_count"
        ],
        "fixed_obstacle_pair_eliminated_count": state[
            "fixed_obstacle_pair_eliminated_count"
        ],
        "relaxed_controlled_component_pair_count": state[
            "relaxed_controlled_component_pair_count"
        ],
        "exact_controlled_component_pair_count": state[
            "exact_controlled_component_pair_count"
        ],
        "controlled_collision_relaxation": state[
            "controlled_collision_relaxation"
        ],
        "controlled_collision_pair_allowlist": state[
            "controlled_collision_pair_allowlist"
        ],
        "nonrectangle_inner_slices": state[
            "nonrectangle_inner_slices"
        ],
        "controlled_inner_rectangle_count": state[
            "controlled_inner_rectangle_count"
        ],
        "controlled_inner_rectangles": state[
            "controlled_inner_rectangles"
        ],
        "inactive_controlled_collision_pair_count": state[
            "inactive_controlled_collision_pair_count"
        ],
        "inactive_controlled_collision_pairs": state[
            "inactive_controlled_collision_pairs"
        ],
        "fixed_obstacle_pruning_enabled": state[
            "fixed_obstacle_pruning_enabled"
        ],
        "fixed_obstacle_count": state["fixed_obstacle_count"],
        "fixed_obstacle_candidate_count": state[
            "fixed_obstacle_candidate_count"
        ],
        "fixed_obstacle_pruned_site_count": state[
            "fixed_obstacle_pruned_site_count"
        ],
        "site_hint_remapped_count": state["site_hint_remapped_count"],
        "site_hint_maximum_remap_distance": state[
            "site_hint_maximum_remap_distance"
        ],
        "site_hint_remaps": state["site_hint_remaps"],
        "fixed_hint_site_count": state["fixed_hint_site_count"],
        "movable_refdes": state["movable_refdes"],
        "packing_side": state["packing_side"],
        "fixed_endpoint_mode": args.fixed_endpoint_mode,
        "manual_baseline_endpoint_overrides": sorted(
            set(args.manual_baseline_endpoint)
        ),
        "fixed_endpoint_coordinate_overrides": (
            args.fixed_endpoint_override_report
        ),
        "assignment_mode": assignment_space["mode"],
        "movable_subgroups": sorted(set(args.movable_subgroup)),
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
        "geometry_model": {
            "decomposed": (
                "exact footprints decomposed into deterministic convex parts"
            ),
            "convex": "legacy convex hulls and fixed PlaceDB boxes",
            "none": "collision constraints disabled for lower bound",
        }[args.collision_mode],
        "site_hint": state["site_hint"],
        "candidate_guide": state["candidate_guide"],
        "fix_site_hint": args.fix_site_hint,
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
    fixed_x, fixed_y, args.fixed_endpoint_override_report = (
        _override_fixed_endpoint_coordinates(
            context,
            placedb,
            fixed_x,
            fixed_y,
            args.fixed_endpoint_override,
        )
    )
    manual_overrides = set(args.manual_baseline_endpoint)
    coordinate_overrides = {
        row["refdes"] for row in args.fixed_endpoint_override_report
    }
    conflicting_overrides = sorted(
        manual_overrides & coordinate_overrides
    )
    if conflicting_overrides:
        raise ValueError(
            "fixed endpoints have both manual and coordinate overrides: %s"
            % ", ".join(conflicting_overrides)
        )
    site_hints = {}
    site_hint_report = None
    candidate_guides = {}
    candidate_guide_report = None
    hint_count = sum(
        (
            bool(args.use_packing_hint),
            args.site_hint_placement is not None,
            args.site_hint_result is not None,
        )
    )
    if hint_count > 1:
        raise ValueError("select only one site hint source")
    if args.fix_site_hint and hint_count != 1:
        raise ValueError("fixing site hints requires one site hint source")
    if args.movable_refdes:
        if hint_count != 1:
            raise ValueError("partial site fixing requires one site hint source")
        if args.fix_site_hint:
            raise ValueError(
                "partial site fixing and full site fixing are mutually exclusive"
            )
        if assignment_space["mode"] != "fixed":
            raise ValueError("partial site fixing requires a fixed assignment")
    if args.movable_subgroup:
        if not args.optimize_assignment:
            raise ValueError(
                "movable subgroups require optimized assignment"
            )
        if args.site_hint_result is None or hint_count != 1:
            raise ValueError(
                "movable subgroups require one structured result hint"
            )
    if args.packing_side:
        if not args.packing_only:
            raise ValueError("packing side requires packing-only mode")
        if assignment_space["mode"] != "fixed":
            raise ValueError("packing side requires a fixed assignment")
        if args.site_hint_result is None or hint_count != 1:
            raise ValueError(
                "packing side requires one structured result hint"
            )
        if args.movable_refdes:
            raise ValueError(
                "packing side and movable refdes are mutually exclusive"
            )
    if args.candidate_limit_per_region and hint_count != 1:
        raise ValueError("candidate limiting requires one site hint source")
    if args.packing_objective != "none":
        if not args.packing_only:
            raise ValueError("packing objectives require packing-only mode")
        if hint_count != 1:
            raise ValueError("packing objectives require one site hint source")
    if args.candidate_guide_placement is not None:
        if not args.candidate_limit_per_region:
            raise ValueError("candidate guides require candidate limiting")
        candidate_guides, candidate_guide_report = _load_candidate_guide(
            args, context
        )
    if args.site_hint_result is not None:
        site_hints, site_hint_report = _load_result_site_hint(
            args,
            placedb,
            context,
            assignment_space,
            baseline_x,
            baseline_y,
            fixed_x,
            fixed_y,
            baseline_hpwl,
            baseline_rsmt,
        )
    if args.site_hint_placement is not None:
        if assignment_space["mode"] != "fixed":
            raise ValueError("site hints require a fixed assignment")
        site_hints, site_hint_report = _load_site_hint(
            args,
            placedb,
            context,
            baseline_x,
            baseline_y,
            fixed_x,
            fixed_y,
            baseline_hpwl,
            baseline_rsmt,
        )
    if args.use_packing_hint:
        if assignment_space["mode"] != "fixed":
            raise ValueError("packing hints require a fixed assignment")
        site_hints, site_hint_report = _build_packing_hint(
            args,
            placedb,
            context,
            baseline_x,
            baseline_y,
            fixed_x,
            fixed_y,
            baseline_hpwl,
            baseline_rsmt,
        )
    assignment_space = _scoped_assignment_space(
        assignment_space, site_hints, args.movable_subgroup
    )
    model, state = _build_model(
        cp_model,
        placedb,
        context,
        baseline_x,
        baseline_y,
        fixed_x,
        fixed_y,
        args.minimum_score,
        baseline_hpwl,
        baseline_rsmt,
        args.integer_scale,
        args.collision_mode,
        assignment_space,
        args.capacity_scale,
        args.candidate_limit_per_region,
        site_hints,
        site_hint_report,
        candidate_guides,
        candidate_guide_report,
        not args.feasibility_only,
        args.movable_refdes,
        not args.packing_only,
        args.packing_side,
        args.site_model,
        args.packing_objective,
        args.prune_fixed_obstacle_sites,
        args.fix_site_hint,
        args.controlled_collision_relaxation,
        args.controlled_collision_pair,
        args.nonrectangle_inner_slices,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.time_limit
    solver.parameters.num_search_workers = args.workers
    solver.parameters.random_seed = args.seed
    solver.parameters.log_search_progress = args.log_search_progress
    solver.parameters.fix_variables_to_their_hinted_value = args.fix_site_hint
    solver.parameters.repair_hint = args.repair_hint
    solver.parameters.hint_conflict_limit = args.hint_conflict_limit
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
            if state["optimize_hpwl"]
            and status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None
        ),
        "best_objective_bound_hpwl": (
            solver.best_objective_bound / args.integer_scale
            if state["optimize_hpwl"]
            else None
        ),
        "objective_packing_l1": (
            solver.objective_value / args.integer_scale
            if state["optimize_packing"]
            and status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None
        ),
        "best_objective_bound_packing_l1": (
            solver.best_objective_bound / args.integer_scale
            if state["optimize_packing"]
            else None
        ),
        "wall_time_seconds": solver.wall_time,
        "branches": solver.num_branches,
        "conflicts": solver.num_conflicts,
        "workers": args.workers,
        "random_seed": args.seed,
        "repair_hint": args.repair_hint,
        "hint_conflict_limit": args.hint_conflict_limit,
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
        if node_id not in state["x_vars"]:
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
    for constraint in sorted(context.constraints, key=lambda item: item.refdes):
        node_id = constraint.node_id
        if node_id in state["x_vars"]:
            choices = state["site_choices"][node_id]
            if state["site_model"] == "element":
                site_index = int(
                    solver.value(state["site_vars"][node_id])
                )
            else:
                site_index = _coordinate_choice_index(
                    choices,
                    selected_regions[constraint.subgroup_id],
                    int(solver.value(state["x_vars"][node_id])),
                    int(solver.value(state["y_vars"][node_id])),
                )
            region_index = int(choices["region_indices"][site_index])
            region_id = choices["regions"][region_index]
            local_index = int(choices["local_indices"][site_index])
        else:
            if node_id not in site_hints:
                raise RuntimeError(
                    "unmodeled component has no site hint: %s"
                    % constraint.refdes
                )
            region_id, local_index = _site_hint_parts(site_hints[node_id])
            site_index = None
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
    if args.packing_side:
        result["packing_side_legality"] = _side_legality_report(
            legality, args.packing_side
        )
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
    acceptance_legality = result.get("packing_side_legality", legality)
    if (
        acceptance_legality["keepin_violation_count"]
        or acceptance_legality["overlap_pair_count"]
    ):
        raise RuntimeError("CP-SAT placement failed exact geometry validation")
    if (
        state["hpwl_gate_enabled"]
        and score_upper_bound + 1e-12 < args.minimum_score
    ):
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
        "--feasibility-only",
        action="store_true",
        help="return the first solution under the configured HPWL limit",
    )
    parser.add_argument(
        "--packing-only",
        action="store_true",
        help="diagnostic: omit HPWL variables and the score gate",
    )
    parser.add_argument(
        "--packing-side",
        choices=("TOP", "BOTTOM"),
        help="diagnostic: solve exact packing on only one board side",
    )
    parser.add_argument(
        "--site-model",
        choices=("element", "coordinate-table"),
        default="element",
        help="encode candidate sites by index elements or an (x, y, region) table",
    )
    parser.add_argument(
        "--packing-objective",
        choices=("none", "hint-l1"),
        default="none",
        help="optionally minimize total coordinate displacement from the hint",
    )
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
    parser.add_argument(
        "--fixed-endpoint-override",
        action="append",
        nargs=3,
        default=[],
        metavar=("REFDES", "X", "Y"),
        help="set one frozen endpoint lower-left coordinate explicitly",
    )
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
        choices=("decomposed", "convex", "none"),
        default="decomposed",
        help=(
            "'decomposed' matches exact footprints; 'convex' preserves the "
            "legacy over-conservative audit model; 'none' is a lower bound"
        ),
    )
    parser.add_argument(
        "--prune-fixed-obstacle-sites",
        action="store_true",
        help=(
            "remove exact candidate sites that overlap fixed obstacles "
            "before building decomposed collision constraints"
        ),
    )
    parser.add_argument(
        "--controlled-collision-relaxation",
        choices=("none", "mixed-nonrectangle", "all-nonrectangle"),
        default="none",
        help=(
            "diagnostic packing stage: omit mixed nonrectangle/rectangle "
            "pairs or every pair involving a nonrectangle"
        ),
    )
    parser.add_argument(
        "--controlled-collision-pair",
        action="append",
        nargs=2,
        default=[],
        metavar=("FIRST", "SECOND"),
        help=(
            "diagnostic: enforce one controlled nonrectangle-related pair "
            "and relax unlisted pairs; may be repeated"
        ),
    )
    parser.add_argument(
        "--nonrectangle-inner-slices",
        type=int,
        default=0,
        help=(
            "diagnostic: add exact-safe inner rectangle slices to global "
            "NoOverlap2D propagation"
        ),
    )
    parser.add_argument(
        "--use-packing-hint",
        action="store_true",
        help="seed a fixed-assignment solve with deterministic exact packing",
    )
    parser.add_argument(
        "--site-hint-placement",
        type=Path,
        help="seed a fixed-assignment solve from an exact-site Bookshelf PL",
    )
    parser.add_argument(
        "--snap-site-hint",
        action="store_true",
        help="explicitly snap a placement hint to its nearest feasible sites",
    )
    parser.add_argument(
        "--site-hint-result",
        type=Path,
        help="seed a fixed-assignment solve from selected_sites in a result",
    )
    parser.add_argument(
        "--fix-site-hint",
        action="store_true",
        help="diagnostic: fix all site variables to their hinted values",
    )
    parser.add_argument(
        "--movable-refdes",
        action="append",
        default=[],
        help=(
            "allow one controlled component to move while all other hinted "
            "sites remain fixed; may be repeated"
        ),
    )
    parser.add_argument(
        "--movable-subgroup",
        action="append",
        default=[],
        help=(
            "retain alternate regions for one subgroup while all other "
            "subgroups use their structured result-hint regions"
        ),
    )
    parser.add_argument(
        "--candidate-limit-per-region",
        type=int,
        default=0,
        help="diagnostic site subset size around each exact result hint",
    )
    parser.add_argument(
        "--candidate-guide-placement",
        type=Path,
        help="add a second candidate neighborhood around a Bookshelf PL",
    )
    parser.add_argument("--integer-scale", type=int, default=1000000)
    parser.add_argument("--capacity-scale", type=int, default=1000000)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--deterministic-time", type=float, default=300.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument(
        "--repair-hint",
        action="store_true",
        help="try to repair an infeasible hint before regular search",
    )
    parser.add_argument(
        "--hint-conflict-limit",
        type=int,
        default=10,
        help="conflict budget for the initial hint-guided search phase",
    )
    parser.add_argument("--log-search-progress", action="store_true")
    args = parser.parse_args()
    if args.packing_only and not args.feasibility_only:
        parser.error("packing-only requires feasibility-only")
    if args.packing_side and not args.packing_only:
        parser.error("packing-side requires packing-only")
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
    if args.site_hint_placement is not None:
        args.site_hint_placement = args.site_hint_placement.resolve()
    if args.site_hint_result is not None:
        args.site_hint_result = args.site_hint_result.resolve()
    if args.candidate_guide_placement is not None:
        args.candidate_guide_placement = args.candidate_guide_placement.resolve()
    if (
        args.integer_scale <= 0
        or args.capacity_scale <= 0
        or args.time_limit <= 0
        or args.workers <= 0
        or args.candidate_limit_per_region < 0
        or args.nonrectangle_inner_slices < 0
        or args.hint_conflict_limit <= 0
    ):
        parser.error(
            "scales, limits, time limit, and workers must be positive"
        )
    for path in (
        args.bookshelf_dir / "m336.aux",
        args.bookshelf_dir / "m336.baseline.pl",
        args.assignment,
        args.baseline_result,
    ):
        if not path.exists():
            parser.error("required input does not exist: %s" % path)
    if (
        args.site_hint_placement is not None
        and not args.site_hint_placement.exists()
    ):
        parser.error(
            "site hint placement does not exist: %s"
            % args.site_hint_placement
        )
    if args.site_hint_result is not None and not args.site_hint_result.exists():
        parser.error("site hint result does not exist: %s" % args.site_hint_result)
    if (
        args.candidate_guide_placement is not None
        and not args.candidate_guide_placement.exists()
    ):
        parser.error(
            "candidate guide placement does not exist: %s"
            % args.candidate_guide_placement
        )
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
                "packing_side_legality": result.get(
                    "packing_side_legality"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
