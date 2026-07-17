"""Runtime assembly for feature-gated anchor/keep-in experiments."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from shapely import affinity
from shapely.geometry import box

from dreamplace.constraints.pcb_geometry import GeometryAlignment, load_pcb_geometry
from dreamplace.constraints.region_assignment import (
    load_clusters,
    load_region_assignments,
    split_side_subgroups,
)
from dreamplace.constraints.region_projection import (
    FeasibleDomain,
    InfeasibleDomainError,
    NodeConstraint,
    RegionProjector,
)
from dreamplace.constraints.region_validation import (
    ComponentPlacement,
    validate_placement,
)
from dreamplace.ops.anchor_keepin.anchor_keepin import AnchorKeepInLoss, SoftKeepInLoss


def _decode_name(name):
    return name.decode("utf-8") if isinstance(name, bytes) else str(name)


def _resolve_path(config_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate
    config_candidate = config_path.parent / path
    if config_candidate.exists():
        return config_candidate
    raise FileNotFoundError("configured M336 input does not exist: %s" % value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ordered_constraints(constraints, mode):
    if mode == "fewest_sites":
        key = lambda item: (
            len(item.domain.valid_centers),
            -(item.domain.width * item.domain.height),
            item.refdes,
        )
    elif mode == "largest_area":
        key = lambda item: (
            -(item.domain.width * item.domain.height),
            len(item.domain.valid_centers),
            item.refdes,
        )
    elif mode == "largest_span":
        key = lambda item: (
            -max(item.domain.width, item.domain.height),
            -(item.domain.width * item.domain.height),
            len(item.domain.valid_centers),
            item.refdes,
        )
    else:
        raise ValueError("unknown constraint ordering: %s" % mode)
    return sorted(constraints, key=key)


def _ordered_candidate_indices(constraint, mode, preferred_center=None):
    candidates = constraint.domain.valid_centers
    x_values = candidates[:, 0]
    y_values = candidates[:, 1]
    if mode == "preferred":
        target = np.asarray(preferred_center or constraint.target_center)
        return np.argsort(
            np.square(candidates - target).sum(axis=1), kind="stable"
        )

    primary, secondary = mode.split("_")
    primary_values = {
        "left": x_values,
        "right": -x_values,
        "bottom": y_values,
        "top": -y_values,
    }[primary]
    secondary_values = {
        "left": x_values,
        "right": -x_values,
        "bottom": y_values,
        "top": -y_values,
    }[secondary]
    return np.lexsort((secondary_values, primary_values))


def _has_overlap(footprint, occupied, epsilon=1e-12):
    for other in occupied:
        if footprint.intersects(other) and footprint.intersection(other).area > epsilon:
            return True
    return False


def _greedy_pack(ordered, obstacles, candidate_mode, preferred_centers):
    occupied = list(obstacles)
    placements = {}
    footprints = []
    for index, constraint in enumerate(ordered):
        preferred = preferred_centers.get(constraint.node_id)
        selected = None
        for candidate_index in _ordered_candidate_indices(
            constraint, candidate_mode, preferred
        ):
            center = constraint.domain.valid_centers[candidate_index]
            footprint = constraint.domain.footprint(center)
            if not _has_overlap(footprint, occupied):
                selected = center
                occupied.append(footprint)
                footprints.append(footprint)
                break
        if selected is None:
            return None, index, placements, footprints
        placements[constraint.node_id] = selected
    return placements, None, placements, footprints


def _bounded_tail_search(
    ordered,
    obstacles,
    candidate_mode,
    preferred_centers,
    greedy_placements,
    greedy_footprints,
    failed_index,
    window,
    max_states,
    branch_limit,
):
    prefix_length = max(0, failed_index - window)
    placements = {
        constraint.node_id: greedy_placements[constraint.node_id]
        for constraint in ordered[:prefix_length]
    }
    occupied = list(obstacles) + list(greedy_footprints[:prefix_length])
    states = 0

    def visit(index):
        nonlocal states
        if index == len(ordered):
            return True
        if states >= max_states:
            return False
        constraint = ordered[index]
        preferred = preferred_centers.get(constraint.node_id)
        alternatives = []
        minimum_separation = max(
            constraint.domain.grid,
            min(constraint.domain.width, constraint.domain.height) * 0.35,
        )
        for candidate_index in _ordered_candidate_indices(
            constraint, candidate_mode, preferred
        ):
            center = constraint.domain.valid_centers[candidate_index]
            if alternatives and any(
                np.linalg.norm(center - other) < minimum_separation
                for other in alternatives
            ):
                continue
            footprint = constraint.domain.footprint(center)
            if _has_overlap(footprint, occupied):
                continue
            alternatives.append(center)
            occupied.append(footprint)
            placements[constraint.node_id] = center
            states += 1
            if visit(index + 1):
                return True
            placements.pop(constraint.node_id, None)
            occupied.pop()
            if len(alternatives) >= branch_limit or states >= max_states:
                break
        return False

    success = visit(prefix_length)
    return (dict(placements) if success else None), states


def _positive_overlap_area(first, second, epsilon=1e-12):
    first_bounds = first.bounds
    second_bounds = second.bounds
    overlap_width = min(first_bounds[2], second_bounds[2]) - max(
        first_bounds[0], second_bounds[0]
    )
    overlap_height = min(first_bounds[3], second_bounds[3]) - max(
        first_bounds[1], second_bounds[1]
    )
    if overlap_width <= epsilon or overlap_height <= epsilon:
        return 0.0
    area = first.intersection(second).area
    return area if area > epsilon else 0.0


def _overlap_metrics(footprint, others):
    count = 0
    area = 0.0
    for other in others:
        overlap_area = _positive_overlap_area(footprint, other)
        if overlap_area:
            count += 1
            area += overlap_area
    return count, area


def _initialize_conflicts(constraints, footprints, obstacles):
    conflicts = {constraint.node_id: [0, 0.0] for constraint in constraints}
    obstacle_metrics = {}
    pair_areas = {}
    for constraint in constraints:
        node_id = constraint.node_id
        count, area = _overlap_metrics(footprints[node_id], obstacles)
        obstacle_metrics[node_id] = (count, area)
        conflicts[node_id][0] += count
        conflicts[node_id][1] += area
    for index, first in enumerate(constraints):
        first_id = first.node_id
        for second in constraints[index + 1 :]:
            second_id = second.node_id
            area = _positive_overlap_area(
                footprints[first_id], footprints[second_id]
            )
            pair_areas[tuple(sorted((first_id, second_id)))] = area
            if area:
                conflicts[first_id][0] += 1
                conflicts[first_id][1] += area
                conflicts[second_id][0] += 1
                conflicts[second_id][1] += area
    return conflicts, obstacle_metrics, pair_areas


def _update_conflicts(
    moved_constraint,
    constraints,
    footprints,
    obstacles,
    conflicts,
    obstacle_metrics,
    pair_areas,
):
    node_id = moved_constraint.node_id
    old_count, old_area = obstacle_metrics[node_id]
    conflicts[node_id][0] -= old_count
    conflicts[node_id][1] -= old_area
    new_count, new_area = _overlap_metrics(footprints[node_id], obstacles)
    obstacle_metrics[node_id] = (new_count, new_area)
    conflicts[node_id][0] += new_count
    conflicts[node_id][1] += new_area

    for other in constraints:
        other_id = other.node_id
        if other_id == node_id:
            continue
        pair = tuple(sorted((node_id, other_id)))
        old_area = pair_areas[pair]
        if old_area:
            conflicts[node_id][0] -= 1
            conflicts[node_id][1] -= old_area
            conflicts[other_id][0] -= 1
            conflicts[other_id][1] -= old_area
        new_area = _positive_overlap_area(
            footprints[node_id], footprints[other_id]
        )
        pair_areas[pair] = new_area
        if new_area:
            conflicts[node_id][0] += 1
            conflicts[node_id][1] += new_area
            conflicts[other_id][0] += 1
            conflicts[other_id][1] += new_area


def _bbox_overlap_scores(constraint, candidates, other_bounds):
    if not len(other_bounds):
        return np.zeros(len(candidates), dtype=np.float64)
    local_min_x, local_min_y, local_max_x, local_max_y = (
        constraint.domain.footprint_local.bounds
    )
    candidate_bounds = np.column_stack(
        (
            candidates[:, 0] + local_min_x,
            candidates[:, 1] + local_min_y,
            candidates[:, 0] + local_max_x,
            candidates[:, 1] + local_max_y,
        )
    )
    overlap_x = np.maximum(
        0.0,
        np.minimum(candidate_bounds[:, None, 2], other_bounds[None, :, 2])
        - np.maximum(candidate_bounds[:, None, 0], other_bounds[None, :, 0]),
    )
    overlap_y = np.maximum(
        0.0,
        np.minimum(candidate_bounds[:, None, 3], other_bounds[None, :, 3])
        - np.maximum(candidate_bounds[:, None, 1], other_bounds[None, :, 1]),
    )
    return np.sum(overlap_x * overlap_y, axis=1)


def _min_conflicts_pack(
    constraints,
    obstacles,
    preferred_centers,
    restart_count=8,
    max_steps=2500,
    exact_candidate_limit=48,
):
    ordered = _ordered_constraints(constraints, "largest_area")
    seed_material = "|".join(item.refdes for item in ordered).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    obstacle_bounds = [row.bounds for row in obstacles]

    for restart in range(restart_count):
        placements = {}
        footprints = {}
        for constraint in ordered:
            candidates = constraint.domain.valid_centers
            if restart == 0:
                preferred = np.asarray(
                    preferred_centers.get(
                        constraint.node_id, constraint.target_center
                    )
                )
                candidate_index = int(
                    np.argmin(np.square(candidates - preferred).sum(axis=1))
                )
            else:
                candidate_index = int(rng.integers(len(candidates)))
            center = candidates[candidate_index]
            placements[constraint.node_id] = center
            footprints[constraint.node_id] = constraint.domain.footprint(center)

        conflicts, obstacle_metrics, pair_areas = _initialize_conflicts(
            ordered, footprints, obstacles
        )
        for step in range(max_steps):
            conflicted = [
                item for item in ordered if conflicts[item.node_id][0] > 0
            ]
            if not conflicted:
                return placements, {
                    "restart": restart,
                    "steps": step,
                    "seed": seed,
                }
            conflicted.sort(
                key=lambda item: (
                    -conflicts[item.node_id][0],
                    -conflicts[item.node_id][1],
                    item.refdes,
                )
            )
            top_count = min(4, len(conflicted))
            constraint = conflicted[int(rng.integers(top_count))]
            node_id = constraint.node_id
            other_footprints = list(obstacles) + [
                footprints[item.node_id]
                for item in ordered
                if item.node_id != node_id
            ]
            other_bounds = np.asarray(
                obstacle_bounds
                + [
                    footprints[item.node_id].bounds
                    for item in ordered
                    if item.node_id != node_id
                ],
                dtype=np.float64,
            )
            candidates = constraint.domain.valid_centers
            bbox_scores = _bbox_overlap_scores(
                constraint, candidates, other_bounds
            )
            preferred = np.asarray(
                preferred_centers.get(node_id, constraint.target_center)
            )
            distances = np.square(candidates - preferred).sum(axis=1)
            bbox_free = np.flatnonzero(bbox_scores <= 1e-12)
            if len(bbox_free):
                candidate_index = int(
                    bbox_free[np.argmin(distances[bbox_free])]
                )
                center = candidates[candidate_index]
                placements[node_id] = center
                footprints[node_id] = constraint.domain.footprint(center)
                _update_conflicts(
                    constraint,
                    ordered,
                    footprints,
                    obstacles,
                    conflicts,
                    obstacle_metrics,
                    pair_areas,
                )
                continue

            candidate_order = np.lexsort((distances, bbox_scores))
            pool = list(candidate_order[:exact_candidate_limit])
            if len(candidates) > exact_candidate_limit:
                pool.extend(
                    int(index)
                    for index in rng.choice(
                        len(candidates),
                        size=min(16, len(candidates)),
                        replace=False,
                    )
                )
            scored = []
            for candidate_index in dict.fromkeys(pool):
                center = candidates[candidate_index]
                footprint = constraint.domain.footprint(center)
                count, area = _overlap_metrics(footprint, other_footprints)
                scored.append(
                    (
                        count,
                        area,
                        bbox_scores[candidate_index],
                        distances[candidate_index],
                        candidate_index,
                        footprint,
                    )
                )
            scored.sort(key=lambda row: row[:5])
            best_count = scored[0][0]
            best_area = scored[0][1]
            ties = [
                row
                for row in scored[:8]
                if row[0] == best_count
                and math.isclose(row[1], best_area, abs_tol=1e-12)
            ]
            selected = ties[int(rng.integers(len(ties)))]
            candidate_index = selected[4]
            placements[node_id] = candidates[candidate_index]
            footprints[node_id] = selected[5]
            _update_conflicts(
                constraint,
                ordered,
                footprints,
                obstacles,
                conflicts,
                obstacle_metrics,
                pair_areas,
            )
        remaining = sum(row[0] > 0 for row in conflicts.values())
        logging.info(
            "anchor/keep-in min-conflicts restart %d/%d ended with %d "
            "conflicted nodes",
            restart + 1,
            restart_count,
            remaining,
        )
    return None, {
        "restart_count": restart_count,
        "max_steps": max_steps,
        "seed": seed,
    }


def _pack_region(constraints, obstacles, preferred_centers=None):
    preferred_centers = preferred_centers or {}
    ordering_modes = ("fewest_sites", "largest_area", "largest_span")
    candidate_modes = (
        "preferred",
        "bottom_left",
        "bottom_right",
        "top_left",
        "top_right",
        "left_bottom",
        "right_bottom",
        "left_top",
        "right_top",
    )
    trials = []
    for ordering_mode in ordering_modes:
        ordered = _ordered_constraints(constraints, ordering_mode)
        for candidate_mode in candidate_modes:
            result, failed_index, greedy, footprints = _greedy_pack(
                ordered, obstacles, candidate_mode, preferred_centers
            )
            if result is not None:
                return result, {
                    "ordering": ordering_mode,
                    "candidate_order": candidate_mode,
                    "backtracking_states": 0,
                }
            trials.append(
                (
                    failed_index,
                    ordering_mode,
                    candidate_mode,
                    ordered,
                    greedy,
                    footprints,
                )
            )
    repaired, min_conflicts_stats = _min_conflicts_pack(
        constraints, obstacles, preferred_centers
    )
    if repaired is not None:
        return repaired, dict(
            min_conflicts_stats,
            ordering="min_conflicts",
            candidate_order="bbox_prefilter_exact_polygon",
            backtracking_states=0,
        )
    trials.sort(key=lambda item: (-item[0], item[1], item[2]))
    for (
        failed_index,
        ordering_mode,
        candidate_mode,
        ordered,
        greedy,
        footprints,
    ) in trials[:4]:
        for window in (6, 12):
            repaired, states = _bounded_tail_search(
                ordered=ordered,
                obstacles=obstacles,
                candidate_mode=candidate_mode,
                preferred_centers=preferred_centers,
                greedy_placements=greedy,
                greedy_footprints=footprints,
                failed_index=failed_index,
                window=window,
                max_states=1000,
                branch_limit=6,
            )
            if repaired is not None:
                return repaired, {
                    "ordering": ordering_mode,
                    "candidate_order": candidate_mode,
                    "backtracking_window": window,
                    "backtracking_states": states,
                }
    failures = [
        {
            "ordering": ordering_mode,
            "candidate_order": candidate_mode,
            "failed_refdes": ordered[failed_index].refdes,
            "placed_count": failed_index,
        }
        for (
            failed_index,
            ordering_mode,
            candidate_mode,
            ordered,
            _,
            _,
        ) in trials
    ]
    raise InfeasibleDomainError(
        "bounded packing exhausted deterministic strategies: %s" % failures
    )


class AnchorKeepInContext:
    """Resolved geometry and node constraints shared by placement stages."""

    def __init__(
        self,
        config,
        geometry,
        alignment,
        regions,
        constraints,
        frozen_lower_left,
        anchor_centers,
        resolved_members,
        input_paths,
        num_nodes,
        output_dir,
        projection_enabled,
        anchor_loss_enabled,
        soft_loss_enabled,
        exact_repair_enabled,
        grid,
    ):
        self.config = config
        self.geometry = geometry
        self.alignment = alignment
        self.regions = regions
        self.constraints = tuple(constraints)
        self.frozen_lower_left = dict(frozen_lower_left)
        self.anchor_centers = dict(anchor_centers)
        self.resolved_members = tuple(resolved_members)
        self.input_paths = dict(input_paths)
        self.num_nodes = int(num_nodes)
        self.output_dir = Path(output_dir)
        self.projection_enabled = bool(projection_enabled)
        self.anchor_loss_enabled = bool(anchor_loss_enabled)
        self.soft_loss_enabled = bool(soft_loss_enabled)
        self.exact_repair_enabled = bool(exact_repair_enabled)
        self.grid = float(grid)
        self.projector = RegionProjector(
            num_nodes=self.num_nodes,
            constraints=self.constraints,
            frozen_lower_left=self.frozen_lower_left,
            enabled=self.projection_enabled,
        )

    @classmethod
    def from_params(cls, params, placedb):
        preflight_started = time.perf_counter()
        if getattr(params, "enable_rotation", False):
            raise ValueError("anchor/keep-in phase 1 requires enable_rotation=false")
        config_path = Path(params.anchor_keepin_config)
        if not config_path.exists():
            raise FileNotFoundError(
                "anchor_keepin_flag requires anchor_keepin_config: %s" % config_path
            )
        with config_path.open() as stream:
            config = json.load(stream)
        if not config.get("enabled", False):
            raise ValueError("anchor/keep-in config is not enabled")

        geometry_path = _resolve_path(config_path, config["geometry_file"])
        cluster_path = _resolve_path(config_path, config["cluster_file"])
        assignment_path = _resolve_path(config_path, config["region_assignment_file"])
        logging.info("anchor/keep-in preflight: loading geometry and assignments")
        geometry = load_pcb_geometry(geometry_path)
        clusters = load_clusters(cluster_path)
        component_sides = {
            refdes: symbol.side for refdes, symbol in geometry.symbols.items()
        }
        subgroups = split_side_subgroups(clusters, component_sides)
        region_sides = {
            region_id: region.side for region_id, region in geometry.regions.items()
        }
        assignments = load_region_assignments(
            assignment_path, subgroups, region_sides
        )
        logging.info(
            "anchor/keep-in preflight: loaded inputs in %.3fs",
            time.perf_counter() - preflight_started,
        )

        names = [_decode_name(name) for name in placedb.node_names]
        name_to_id = {name: node_id for node_id, name in enumerate(names)}
        target_centers = {
            name: (
                float(placedb.node_x[node_id] + placedb.node_size_x[node_id] / 2),
                float(placedb.node_y[node_id] + placedb.node_size_y[node_id] / 2),
            )
            for node_id, name in enumerate(names[: placedb.num_physical_nodes])
        }
        alignment_limit = float(
            config.get("geometry", {}).get("alignment_max_residual_mm", 0.05)
        )
        alignment_started = time.perf_counter()
        logging.info("anchor/keep-in preflight: fitting coordinate alignment")
        alignment = GeometryAlignment.fit(
            geometry.symbol_centers_mm,
            target_centers,
            min_points=3,
            max_residual_mm=alignment_limit,
        )
        transformed_regions = {
            region_id: alignment.transform_geometry(region.polygon_mm)
            for region_id, region in geometry.regions.items()
        }
        logging.info(
            "anchor/keep-in preflight: alignment completed in %.3fs",
            time.perf_counter() - alignment_started,
        )

        grid_mm = float(getattr(params, "constraint_grid_mm", 0.1))
        clearance_mm = float(getattr(params, "keepin_clearance_mm", 0.0))
        grid = grid_mm * abs(alignment.scale)
        clearance = clearance_mm * abs(alignment.scale)
        domain_cache = {}
        constraints = []
        frozen_lower_left = {}
        anchor_centers = {}
        resolved_members = []
        infeasible = []
        constrained_nodes = set()
        domain_started = time.perf_counter()
        domain_count = 0
        logging.info("anchor/keep-in preflight: constructing feasible domains")

        anchor_refdes = {cluster.anchor_refdes for cluster in clusters}
        for refdes in sorted(anchor_refdes):
            if refdes not in name_to_id:
                raise KeyError("cluster anchor missing from Cypress nodes: %s" % refdes)
            node_id = name_to_id[refdes]
            center = alignment.transform_point(geometry.symbols[refdes].center_mm)
            anchor_centers[refdes] = center
            if (
                getattr(params, "freeze_anchor_nodes", True)
                and node_id < placedb.num_movable_nodes
            ):
                frozen_lower_left[node_id] = (
                    center[0] - float(placedb.node_size_x[node_id]) / 2,
                    center[1] - float(placedb.node_size_y[node_id]) / 2,
                )

        for assignment in assignments:
            subgroup = assignment.subgroup
            region = transformed_regions[assignment.region_id]
            physical_anchor = anchor_centers[subgroup.anchor_refdes]
            for refdes in subgroup.members:
                if refdes not in name_to_id:
                    raise KeyError("cluster member missing from Cypress nodes: %s" % refdes)
                node_id = name_to_id[refdes]
                symbol = geometry.symbols[refdes]
                cypress_side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
                if cypress_side != subgroup.side or symbol.side != subgroup.side:
                    raise ValueError(
                        "side mismatch for %s: subgroup=%s geometry=%s Cypress=%s"
                        % (refdes, subgroup.side, symbol.side, cypress_side)
                    )
                resolved_members.append(refdes)
                if refdes == subgroup.anchor_refdes:
                    continue

                source_center = alignment.transform_point(symbol.center_mm)
                footprint_at_source = alignment.transform_geometry(symbol.footprint_mm)
                footprint_local = affinity.translate(
                    footprint_at_source,
                    xoff=-source_center[0],
                    yoff=-source_center[1],
                )
                footprint_bounds = footprint_local.bounds
                footprint_width = footprint_bounds[2] - footprint_bounds[0]
                footprint_height = footprint_bounds[3] - footprint_bounds[1]
                orientation = _decode_name(placedb.node_orient[node_id])
                cache_key = (
                    subgroup.side,
                    assignment.region_id,
                    int(math.ceil(footprint_width / grid)),
                    int(math.ceil(footprint_height / grid)),
                    orientation,
                    int(round(clearance / grid)),
                    footprint_local.wkb_hex,
                )
                if cache_key not in domain_cache:
                    try:
                        domain_cache[cache_key] = FeasibleDomain.build(
                            region=region,
                            width=footprint_width,
                            height=footprint_height,
                            grid=grid,
                            clearance=clearance,
                            footprint_local=footprint_local,
                        )
                    except InfeasibleDomainError as error:
                        infeasible.append(
                            {
                                "refdes": refdes,
                                "side": subgroup.side,
                                "region_id": assignment.region_id,
                                "width": footprint_width,
                                "height": footprint_height,
                                "orientation": orientation,
                                "reason": str(error),
                            }
                        )
                        continue
                domain = domain_cache[cache_key]
                domain_count += 1
                if domain_count % 10 == 0:
                    logging.info(
                        "anchor/keep-in preflight: resolved %d feasible domains "
                        "in %.3fs",
                        domain_count,
                        time.perf_counter() - domain_started,
                    )
                target, _ = domain.project(physical_anchor)
                if node_id < placedb.num_movable_nodes:
                    if node_id in constrained_nodes:
                        raise ValueError("node assigned more than once: %s" % refdes)
                    constrained_nodes.add(node_id)
                    constraints.append(
                        NodeConstraint(
                            node_id=node_id,
                            refdes=refdes,
                            side=subgroup.side,
                            group_id=subgroup.group_id,
                            subgroup_id=subgroup.subgroup_id,
                            region_id=assignment.region_id,
                            domain=domain,
                            target_center=target,
                            node_width=float(placedb.node_size_x[node_id]),
                            node_height=float(placedb.node_size_y[node_id]),
                            anchor_refdes=subgroup.anchor_refdes,
                        )
                    )

        if infeasible and not getattr(params, "allow_region_reassignment", False):
            details = "; ".join(
                "%s/%s: %s" % (row["refdes"], row["region_id"], row["reason"])
                for row in infeasible
            )
            raise InfeasibleDomainError("infeasible assigned domains: " + details)
        logging.info(
            "anchor/keep-in preflight: resolved %d domains in %.3fs",
            domain_count,
            time.perf_counter() - domain_started,
        )

        output_dir = config.get("reporting", {}).get("output_dir", "results")
        context = cls(
            config=config,
            geometry=geometry,
            alignment=alignment,
            regions=transformed_regions,
            constraints=constraints,
            frozen_lower_left=frozen_lower_left,
            anchor_centers=anchor_centers,
            resolved_members=resolved_members,
            input_paths={
                "geometry": geometry_path,
                "clusters": cluster_path,
                "assignments": assignment_path,
            },
            num_nodes=placedb.num_nodes,
            output_dir=output_dir,
            projection_enabled=getattr(params, "keepin_projection_flag", False),
            anchor_loss_enabled=getattr(params, "anchor_loss_flag", False),
            soft_loss_enabled=getattr(params, "keepin_soft_loss_flag", False),
            exact_repair_enabled=getattr(params, "exact_repair_flag", False),
            grid=grid,
        )
        context.write_preflight(infeasible)
        return context

    def write_preflight(self, infeasible):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.alignment.dump(self.output_dir / "input_alignment.json")
        report = {
            "resolved_member_count": len(set(self.resolved_members)),
            "movable_non_anchor_constraint_count": len(self.constraints),
            "frozen_anchor_count": len(self.frozen_lower_left),
            "infeasible_domains": infeasible,
            "input_sha256": {
                name: _sha256(path) for name, path in self.input_paths.items()
            },
            "alignment": self.alignment.to_dict(),
        }
        with (self.output_dir / "preflight.json").open("w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")

    def initialize_positions(self, position, placedb):
        """Place constrained nodes on non-overlapping feasible sites near anchors."""
        for node_id, lower_left in self.frozen_lower_left.items():
            position[node_id] = lower_left[0]
            position[self.num_nodes + node_id] = lower_left[1]
        if not self.projection_enabled:
            return

        occupied = {"TOP": [], "BOTTOM": []}
        fixed_end = placedb.num_physical_nodes
        for node_id in range(placedb.num_movable_nodes, fixed_end):
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            occupied[side].append(
                box(
                    position[node_id],
                    position[self.num_nodes + node_id],
                    position[node_id] + placedb.node_size_x[node_id],
                    position[self.num_nodes + node_id] + placedb.node_size_y[node_id],
                )
            )
        for node_id, lower_left in self.frozen_lower_left.items():
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            occupied[side].append(
                box(
                    lower_left[0],
                    lower_left[1],
                    lower_left[0] + placedb.node_size_x[node_id],
                    lower_left[1] + placedb.node_size_y[node_id],
                )
            )

        constraints_by_region = defaultdict(list)
        for constraint in self.constraints:
            constraints_by_region[(constraint.side, constraint.region_id)].append(
                constraint
            )

        placements = {}
        packing_stats = []
        for (side, region_id), region_constraints in sorted(
            constraints_by_region.items()
        ):
            logging.info(
                "anchor/keep-in packing %s/%s (%d components)",
                side,
                region_id,
                len(region_constraints),
            )
            preferred_centers = None
            if not self.anchor_loss_enabled:
                preferred_centers = {}
                for constraint in region_constraints:
                    current_center = (
                        float(position[constraint.node_id])
                        + constraint.node_width / 2,
                        float(position[self.num_nodes + constraint.node_id])
                        + constraint.node_height / 2,
                    )
                    preferred_centers[constraint.node_id], _ = (
                        constraint.domain.project(current_center)
                    )
            region_placements, stats = _pack_region(
                region_constraints,
                occupied[side],
                preferred_centers=preferred_centers,
            )
            placements.update(region_placements)
            packing_stats.append(
                dict(
                    stats,
                    side=side,
                    region_id=region_id,
                    component_count=len(region_constraints),
                )
            )
            logging.info(
                "anchor/keep-in packed %s/%s with %s/%s",
                side,
                region_id,
                stats["ordering"],
                stats["candidate_order"],
            )

        for constraint in self.constraints:
            selected = placements[constraint.node_id]
            position[constraint.node_id] = selected[0] - constraint.node_width / 2
            position[self.num_nodes + constraint.node_id] = (
                selected[1] - constraint.node_height / 2
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with (self.output_dir / "initialization.json").open("w") as stream:
            json.dump(packing_stats, stream, indent=2, sort_keys=True)
            stream.write("\n")

    def build_anchor_loss(self, data_collections, placedb):
        node_ids = [constraint.node_id for constraint in self.constraints]
        targets = [constraint.target_center for constraint in self.constraints]
        diagonal = math.hypot(placedb.xh - placedb.xl, placedb.yh - placedb.yl)
        return AnchorKeepInLoss(
            node_ids=node_ids,
            target_centers=targets,
            node_size_x=data_collections.node_size_x,
            node_size_y=data_collections.node_size_y,
            num_nodes=placedb.num_nodes,
            board_diagonal=diagonal,
        ).to(data_collections.pos[0].device)

    def build_soft_loss(self, placedb):
        return SoftKeepInLoss(
            constraints=self.constraints,
            num_nodes=placedb.num_nodes,
            tau=max(self.grid, np.finfo(float).eps),
        )

    def zero_frozen_gradients(self, gradient):
        if gradient is None or not self.frozen_lower_left:
            return
        node_ids = list(self.frozen_lower_left)
        gradient[node_ids] = 0
        gradient[[self.num_nodes + node_id for node_id in node_ids]] = 0

    def repair_positions(self, pos, placedb):
        """Repack constrained components on exact feasible sites near GP output."""
        occupied = {"TOP": [], "BOTTOM": []}
        constrained_ids = {constraint.node_id for constraint in self.constraints}
        for node_id in range(placedb.num_physical_nodes):
            if node_id in constrained_ids:
                continue
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            lower_left_x = float(pos[node_id].detach().cpu())
            lower_left_y = float(pos[self.num_nodes + node_id].detach().cpu())
            occupied[side].append(
                box(
                    lower_left_x,
                    lower_left_y,
                    lower_left_x + placedb.node_size_x[node_id],
                    lower_left_y + placedb.node_size_y[node_id],
                )
            )

        preferred_centers = {
            constraint.node_id: (
                float(pos[constraint.node_id].detach().cpu())
                + constraint.node_width / 2,
                float(pos[self.num_nodes + constraint.node_id].detach().cpu())
                + constraint.node_height / 2,
            )
            for constraint in self.constraints
        }
        constraints_by_region = defaultdict(list)
        for constraint in self.constraints:
            constraints_by_region[(constraint.side, constraint.region_id)].append(
                constraint
            )

        placements = {}
        region_stats = []
        for (side, region_id), region_constraints in sorted(
            constraints_by_region.items()
        ):
            region_placements, stats = _pack_region(
                region_constraints,
                occupied[side],
                preferred_centers=preferred_centers,
            )
            placements.update(region_placements)
            occupied[side].extend(
                constraint.domain.footprint(
                    region_placements[constraint.node_id]
                )
                for constraint in region_constraints
            )
            region_stats.append(
                dict(
                    stats,
                    side=side,
                    region_id=region_id,
                    component_count=len(region_constraints),
                )
            )

        moved_distances = []
        with torch.no_grad():
            for constraint in self.constraints:
                selected = placements[constraint.node_id]
                moved_distances.append(
                    float(
                        np.linalg.norm(
                            np.subtract(
                                selected, preferred_centers[constraint.node_id]
                            )
                        )
                    )
                )
                pos[constraint.node_id] = selected[0] - constraint.node_width / 2
                pos[self.num_nodes + constraint.node_id] = (
                    selected[1] - constraint.node_height / 2
                )
            self.projector(pos)

        return {
            "component_count": len(self.constraints),
            "moved_component_count": sum(distance > 1e-9 for distance in moved_distances),
            "mean_displacement": float(np.mean(moved_distances)),
            "max_displacement": float(np.max(moved_distances)),
            "regions": region_stats,
        }

    def exact_report(self, pos, placedb):
        constrained = []
        for constraint in self.constraints:
            center = (
                float(pos[constraint.node_id].detach().cpu()) + constraint.node_width / 2,
                float(pos[self.num_nodes + constraint.node_id].detach().cpu())
                + constraint.node_height / 2,
            )
            constrained.append(
                ComponentPlacement(
                    refdes=constraint.refdes,
                    side=constraint.side,
                    center=center,
                    width=constraint.domain.width,
                    height=constraint.domain.height,
                    region_id=constraint.region_id,
                    group_id=constraint.group_id,
                    subgroup_id=constraint.subgroup_id,
                    anchor_center=self.anchor_centers.get(constraint.anchor_refdes),
                    projected_anchor_center=constraint.target_center,
                    footprint_local=constraint.domain.footprint_local,
                )
            )

        fixed = []
        names = [_decode_name(name) for name in placedb.node_names]
        constrained_ids = {constraint.node_id for constraint in self.constraints}
        fixed_ids = set(range(placedb.num_physical_nodes)) - constrained_ids
        for node_id in sorted(fixed_ids):
            refdes = names[node_id]
            if not refdes:
                continue
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            center = (
                float(pos[node_id].detach().cpu())
                + float(placedb.node_size_x[node_id]) / 2,
                float(pos[self.num_nodes + node_id].detach().cpu())
                + float(placedb.node_size_y[node_id]) / 2,
            )
            if refdes in self.geometry.symbols:
                symbol = self.geometry.symbols[refdes]
                source_center = self.alignment.transform_point(symbol.center_mm)
                footprint_local = affinity.translate(
                    self.alignment.transform_geometry(symbol.footprint_mm),
                    xoff=-source_center[0],
                    yoff=-source_center[1],
                )
                bounds = footprint_local.bounds
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
            else:
                width = float(placedb.node_size_x[node_id])
                height = float(placedb.node_size_y[node_id])
                footprint_local = None
            fixed.append(
                ComponentPlacement(
                    refdes=refdes,
                    side=side,
                    center=center,
                    width=width,
                    height=height,
                    fixed=True,
                    footprint_local=footprint_local,
                )
            )

        scale = abs(self.alignment.scale)
        area_epsilon_mm2 = float(
            self.config.get("reporting", {}).get("area_epsilon_mm2", 1e-5)
        )
        report = validate_placement(
            constrained,
            self.regions,
            fixed=fixed,
            epsilon=area_epsilon_mm2 * scale * scale,
        )
        report["area_epsilon_mm2"] = area_epsilon_mm2
        report["validated_obstacle_component_count"] = len(fixed)
        report["keepin_violation_area_mm2"] = (
            report["keepin_violation_area"] / (scale * scale)
        )
        report["overlap_area_mm2"] = report["overlap_area"] / (scale * scale)
        report["anchor_distance_mm"] = {
            key: (value / scale if value is not None and key != "count" else value)
            for key, value in report["anchor_distance"].items()
        }
        report["projected_anchor_distance_mm"] = {
            key: (value / scale if value is not None and key != "count" else value)
            for key, value in report["projected_anchor_distance"].items()
        }
        for row in report["per_group"]:
            row["mean_anchor_distance_mm"] = row["mean_anchor_distance"] / scale
            row["max_anchor_distance_mm"] = row["max_anchor_distance"] / scale
        return report

    def log_summary(self):
        logging.info(
            "anchor/keep-in: %d constrained movable nodes, %d frozen anchors, "
            "alignment max residual %.6g mm",
            len(self.constraints),
            len(self.frozen_lower_left),
            self.alignment.max_residual_mm,
        )
