#!/usr/bin/env python3
"""Probe exact M336 side-specific packing with deterministic CP-SAT."""

from __future__ import annotations

import hashlib
import json
import math
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
from solve_discrete_placement import (
    _convex_parts,
    _fixed_footprint_local,
    _hpwl_rounding_allowance_units,
    _scaled,
    _score_hpwl_limit,
)


def _resolved_path(value: str | Path) -> Path:
    """Canonicalize external paths before they enter result metadata."""
    return Path(value).expanduser().resolve()


ROOT = Path(__file__).resolve().parents[3]
SOURCE = _resolved_path(
    os.environ.get(
        "M336_SOURCE_JSON",
        ROOT / "results/m336/grid01_restored_bottom_1024_replay/result.json",
    )
)
GUIDE = _resolved_path(
    os.environ.get(
        "M336_GUIDE_JSON",
        ROOT / "results/m336/discrete_two_anchor/result-no-collision.json",
    )
)
ADDITIONAL_GUIDES = [
    _resolved_path(value)
    for value in os.environ.get("M336_ADDITIONAL_GUIDE_JSONS", "").split(",")
    if value
]
OUTPUT = _resolved_path(
    os.environ.get("M336_OUTPUT_JSON", "/tmp/m336_exact_site_cpsat.json")
)
PLACEMENT_OUTPUT = _resolved_path(
    os.environ.get("M336_PLACEMENT_OUTPUT", f"{OUTPUT}.pl")
)
PROGRESS = _resolved_path(
    os.environ.get("M336_PROGRESS_JSON", f"{OUTPUT}.progress")
)
ASSIGNMENT = _resolved_path(
    os.environ.get(
        "M336_ASSIGNMENT_JSON",
        ROOT
        / "results/m336/quality_assignment/"
        "m336_region_assignment.grid01.corrected.quality.json",
    )
)
GEOMETRY_EPSILON = 1e-10
DIVERSITY_SITE_TOLERANCE = 1e-8
PLACEMENT_SIDES = ("TOP", "BOTTOM")
CANDIDATE_COVERAGE_SCHEMA = "m336_candidate_coverage_v1"


def _context_output_dir(output: Path, override: str) -> Path:
    if override:
        return _resolved_path(override)
    return output.parent / f"{output.name}.context"


def _packing_sides(value: str) -> frozenset[str]:
    if value == "BOTH":
        return frozenset(PLACEMENT_SIDES)
    if value in PLACEMENT_SIDES:
        return frozenset((value,))
    raise ValueError(f"unknown packing side: {value}")


def _candidate_guide_weights(value: str, guide_count: int) -> tuple[int, ...]:
    if guide_count <= 0:
        raise ValueError("candidate selection requires at least one guide")
    if not value:
        return (1,) * guide_count
    parts = value.split(",")
    if len(parts) != guide_count:
        raise ValueError(
            "candidate guide weight count must match guide count"
        )
    weights = []
    for part in parts:
        try:
            weight = int(part)
        except ValueError as error:
            raise ValueError(
                "candidate guide weights must be integers"
            ) from error
        if str(weight) != part.strip() or weight <= 0:
            raise ValueError(
                "candidate guide weights must be positive integers"
            )
        weights.append(weight)
    return tuple(weights)


def _required_guide_support_indices(
    value: str, guide_count: int
) -> tuple[int, ...]:
    if guide_count <= 0:
        raise ValueError("guide support requires at least one guide")
    if not value:
        return ()
    indices = []
    for part in value.split(","):
        try:
            index = int(part)
        except ValueError as error:
            raise ValueError(
                "required guide support indices must be integers"
            ) from error
        if str(index) != part.strip() or not 0 <= index < guide_count:
            raise ValueError(
                "required guide support index is outside the guide range"
            )
        indices.append(index)
    if len(set(indices)) != len(indices):
        raise ValueError("required guide support indices must be unique")
    return tuple(sorted(indices))


def _candidate_guide_support_audit(
    fixed_reference_guide,
    fixed_reference_json,
    guides,
    guide_paths,
    modeled_refdes,
    movable_refdes,
    fix_guide,
    required_indices=(),
    center_tolerance=1e-8,
):
    if len(guides) != len(guide_paths) or not guides:
        raise ValueError("candidate guides and paths must align")
    if not math.isfinite(center_tolerance) or center_tolerance < 0:
        raise ValueError("guide support tolerance must be non-negative")
    modeled = tuple(sorted(set(modeled_refdes)))
    movable = frozenset(movable_refdes)
    required = frozenset(required_indices)
    if any(index < 0 or index >= len(guides) for index in required):
        raise ValueError("required guide support index is outside the guide range")
    missing_reference = sorted(set(modeled) - set(fixed_reference_guide))
    if missing_reference:
        raise ValueError(
            "fixed reference guide is missing modeled refdes: "
            + ", ".join(missing_reference)
        )

    guide_audits = []
    for guide_index, (guide, guide_path) in enumerate(
        zip(guides, guide_paths)
    ):
        missing = sorted(set(modeled) - set(guide))
        if missing:
            raise ValueError(
                f"candidate guide {guide_index} is missing modeled refdes: "
                + ", ".join(missing)
            )
        changed = []
        maximum_center_distance = 0.0
        for refdes in modeled:
            reference_center = np.asarray(
                fixed_reference_guide[refdes], dtype=np.float64
            )
            guide_center = np.asarray(guide[refdes], dtype=np.float64)
            if (
                reference_center.shape != (2,)
                or guide_center.shape != (2,)
                or not np.all(np.isfinite(reference_center))
                or not np.all(np.isfinite(guide_center))
            ):
                raise ValueError("guide centers must be finite 2D coordinates")
            distance = float(np.linalg.norm(guide_center - reference_center))
            maximum_center_distance = max(maximum_center_distance, distance)
            if distance > center_tolerance:
                changed.append(refdes)
        outside_movable = (
            sorted(set(changed) - movable) if fix_guide else []
        )
        guide_audits.append(
            {
                "guide_index": guide_index,
                "guide_json": str(guide_path),
                "required": guide_index in required,
                "changed_refdes_count": len(changed),
                "changed_refdes": changed,
                "outside_movable_refdes_count": len(outside_movable),
                "outside_movable_refdes": outside_movable,
                "maximum_center_distance": maximum_center_distance,
                "support_complete": not outside_movable,
            }
        )
    return {
        "center_tolerance": center_tolerance,
        "fixed_reference_json": str(fixed_reference_json),
        "modeled_refdes_count": len(modeled),
        "movable_refdes_count": len(movable),
        "restricted_by_fixed_equalities": bool(fix_guide),
        "required_guide_indices": sorted(required),
        "all_required_guides_supported": all(
            guide_audits[index]["support_complete"] for index in required
        ),
        "guides": guide_audits,
    }


def _search_branching_mode(value: str) -> str:
    modes = {
        "automatic",
        "fixed_guide_delta",
        "partial_fixed_guide_delta",
    }
    if value not in modes:
        raise ValueError(
            "search branching must be automatic, fixed_guide_delta, or "
            "partial_fixed_guide_delta"
        )
    return value


def _guide_delta_refdes_order(refdes_values, candidate_guide, fixed_hint):
    refdes_values = tuple(sorted(set(refdes_values)))
    missing_candidate = sorted(set(refdes_values) - set(candidate_guide))
    missing_hint = sorted(set(refdes_values) - set(fixed_hint))
    if missing_candidate or missing_hint:
        raise ValueError("guide-delta order is missing component coordinates")
    distances = {}
    for refdes in refdes_values:
        candidate_center = np.asarray(
            candidate_guide[refdes], dtype=np.float64
        )
        hint_center = np.asarray(fixed_hint[refdes], dtype=np.float64)
        if (
            candidate_center.shape != (2,)
            or hint_center.shape != (2,)
            or not np.all(np.isfinite(candidate_center))
            or not np.all(np.isfinite(hint_center))
        ):
            raise ValueError("guide centers must be finite 2D coordinates")
        distances[refdes] = float(
            np.linalg.norm(candidate_center - hint_center)
        )
    ordered = tuple(
        sorted(refdes_values, key=lambda refdes: (-distances[refdes], refdes))
    )
    return ordered, distances


def _optional_nonnegative_integer(value: str, label: str) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{label} must be an integer") from error
    if str(parsed) != value.strip() or parsed < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return parsed


def _weighted_candidate_selection(orders, weights, target_count):
    if len(orders) != len(weights) or not orders:
        raise ValueError("candidate orders and weights must align")
    if target_count < 0:
        raise ValueError("candidate target count must be non-negative")
    if any(weight <= 0 for weight in weights):
        raise ValueError("candidate guide weights must be positive")
    selected = []
    attributed_guide_indices = []
    seen = set()
    pointers = [0] * len(orders)
    while len(selected) < target_count:
        progressed = False
        for guide_index, current_order in enumerate(orders):
            accepted = 0
            while (
                accepted < weights[guide_index]
                and pointers[guide_index] < len(current_order)
            ):
                index = int(current_order[pointers[guide_index]])
                pointers[guide_index] += 1
                if index in seen:
                    continue
                seen.add(index)
                selected.append(index)
                attributed_guide_indices.append(guide_index)
                accepted += 1
                progressed = True
                if len(selected) >= target_count:
                    break
            if len(selected) >= target_count:
                break
        if not progressed:
            break
    if len(selected) != target_count:
        raise ValueError("candidate guide orders did not cover target count")
    return (
        np.asarray(selected, dtype=np.int64),
        np.asarray(attributed_guide_indices, dtype=np.int64),
    )


def _weighted_candidate_order(orders, weights, target_count):
    return _weighted_candidate_selection(orders, weights, target_count)[0]


def _candidate_domain_fingerprint(region_indices, centers):
    region_indices = np.asarray(region_indices, dtype="<i8")
    centers = np.asarray(centers, dtype="<f8")
    if (
        region_indices.ndim != 1
        or centers.ndim != 2
        or centers.shape != (len(region_indices), 2)
        or not len(region_indices)
        or len(set(map(int, region_indices))) != len(region_indices)
        or not np.all(np.isfinite(centers))
    ):
        raise ValueError("candidate coverage domain must be finite and unique")
    digest = hashlib.sha256()
    digest.update(CANDIDATE_COVERAGE_SCHEMA.encode("ascii"))
    digest.update(np.asarray(region_indices.shape, dtype="<i8").tobytes())
    digest.update(region_indices.tobytes())
    digest.update(np.asarray(centers.shape, dtype="<i8").tobytes())
    digest.update(centers.tobytes())
    return digest.hexdigest()


def _candidate_target_domain_coverage(
    constraint,
    obstacle_free_region_indices,
    guides,
    fixed_obstacles,
    site_tolerance=DIVERSITY_SITE_TOLERANCE,
    coordinate_units_per_mm=1.0,
    overlap_epsilon=1e-12,
):
    keepin_centers = np.asarray(
        constraint.domain.valid_centers, dtype=np.float64
    )
    obstacle_free_region_indices = np.asarray(
        obstacle_free_region_indices, dtype=np.int64
    )
    if (
        keepin_centers.ndim != 2
        or keepin_centers.shape[1:] != (2,)
        or not len(keepin_centers)
        or not np.all(np.isfinite(keepin_centers))
        or obstacle_free_region_indices.ndim != 1
        or not len(obstacle_free_region_indices)
        or len(set(map(int, obstacle_free_region_indices)))
        != len(obstacle_free_region_indices)
        or np.any(obstacle_free_region_indices < 0)
        or np.any(obstacle_free_region_indices >= len(keepin_centers))
        or not math.isfinite(site_tolerance)
        or site_tolerance < 0
        or not math.isfinite(coordinate_units_per_mm)
        or coordinate_units_per_mm <= 0
        or not math.isfinite(overlap_epsilon)
        or overlap_epsilon < 0
    ):
        raise ValueError("candidate coverage target domain is invalid")
    obstacle_refdes = [str(refdes) for refdes, _ in fixed_obstacles]
    if len(set(obstacle_refdes)) != len(obstacle_refdes):
        raise ValueError("candidate coverage fixed obstacles must be unique")

    obstacle_free_centers = keepin_centers[obstacle_free_region_indices]
    rows = []
    for guide_index, guide in enumerate(guides):
        if constraint.refdes not in guide:
            raise ValueError(
                f"candidate coverage guide {guide_index} is missing "
                f"{constraint.refdes}"
            )
        target = np.asarray(guide[constraint.refdes], dtype=np.float64)
        if target.shape != (2,) or not np.all(np.isfinite(target)):
            raise ValueError("candidate coverage targets must be finite 2D")

        keepin_distances = np.linalg.norm(keepin_centers - target, axis=1)
        keepin_position = int(np.argmin(keepin_distances))
        keepin_distance = float(keepin_distances[keepin_position])
        obstacle_free_distances = np.linalg.norm(
            obstacle_free_centers - target, axis=1
        )
        obstacle_free_position = int(np.argmin(obstacle_free_distances))
        obstacle_free_distance = float(
            obstacle_free_distances[obstacle_free_position]
        )
        obstacle_free_region_index = int(
            obstacle_free_region_indices[obstacle_free_position]
        )

        target_footprint = constraint.domain.footprint(target)
        overlaps = []
        for refdes, obstacle in fixed_obstacles:
            if not target_footprint.intersects(obstacle):
                continue
            area = float(target_footprint.intersection(obstacle).area)
            if area <= overlap_epsilon:
                continue
            overlaps.append(
                {
                    "refdes": str(refdes),
                    "area": area,
                    "area_mm2": (
                        area / coordinate_units_per_mm**2
                    ),
                }
            )
        overlaps.sort(key=lambda row: row["refdes"])

        rows.append(
            {
                "guide_index": guide_index,
                "target_contained_in_keepin": bool(
                    constraint.domain.contains(target)
                ),
                "keepin_candidate_count": len(keepin_centers),
                "nearest_keepin_region_index": keepin_position,
                "nearest_keepin_center": [
                    float(value) for value in keepin_centers[keepin_position]
                ],
                "minimum_keepin_target_distance": keepin_distance,
                "minimum_keepin_target_distance_mm": (
                    keepin_distance / coordinate_units_per_mm
                ),
                "exact_keepin_target_site_present": (
                    keepin_distance <= site_tolerance
                ),
                "obstacle_free_candidate_count": len(
                    obstacle_free_region_indices
                ),
                "nearest_obstacle_free_region_index": (
                    obstacle_free_region_index
                ),
                "nearest_obstacle_free_center": [
                    float(value)
                    for value in keepin_centers[obstacle_free_region_index]
                ],
                "minimum_obstacle_free_target_distance": (
                    obstacle_free_distance
                ),
                "minimum_obstacle_free_target_distance_mm": (
                    obstacle_free_distance / coordinate_units_per_mm
                ),
                "exact_obstacle_free_target_site_present": (
                    obstacle_free_distance <= site_tolerance
                ),
                "target_fixed_obstacle_overlap_count": len(overlaps),
                "target_fixed_obstacle_refdes": [
                    row["refdes"] for row in overlaps
                ],
                "target_fixed_obstacle_overlap_area": sum(
                    row["area"] for row in overlaps
                ),
                "target_fixed_obstacle_overlap_area_mm2": sum(
                    row["area_mm2"] for row in overlaps
                ),
                "target_fixed_obstacle_overlaps": overlaps,
            }
        )
    return rows


def _candidate_coverage_component(
    refdes,
    domain_sha256,
    region_indices,
    centers,
    attributed_guide_indices,
    guides,
    site_tolerance=DIVERSITY_SITE_TOLERANCE,
    coordinate_units_per_mm=1.0,
    domain_coverage=None,
):
    region_indices = np.asarray(region_indices, dtype=np.int64)
    centers = np.asarray(centers, dtype=np.float64)
    attributed_guide_indices = np.asarray(
        attributed_guide_indices, dtype=np.int64
    )
    if (
        not isinstance(domain_sha256, str)
        or len(domain_sha256) != 64
        or region_indices.ndim != 1
        or centers.shape != (len(region_indices), 2)
        or attributed_guide_indices.shape != region_indices.shape
        or not len(region_indices)
        or len(set(map(int, region_indices))) != len(region_indices)
        or not np.all(np.isfinite(centers))
        or not math.isfinite(site_tolerance)
        or site_tolerance < 0
        or not math.isfinite(coordinate_units_per_mm)
        or coordinate_units_per_mm <= 0
    ):
        raise ValueError("candidate coverage component is invalid")
    if np.any(attributed_guide_indices < 0) or np.any(
        attributed_guide_indices >= len(guides)
    ):
        raise ValueError("candidate coverage attribution is out of range")
    if domain_coverage is not None and (
        not isinstance(domain_coverage, list)
        or len(domain_coverage) != len(guides)
        or [row.get("guide_index") for row in domain_coverage]
        != list(range(len(guides)))
    ):
        raise ValueError("candidate coverage target domains do not align")

    guide_coverage = []
    for guide_index, guide in enumerate(guides):
        if refdes not in guide:
            raise ValueError(
                f"candidate coverage guide {guide_index} is missing {refdes}"
            )
        target = np.asarray(guide[refdes], dtype=np.float64)
        if target.shape != (2,) or not np.all(np.isfinite(target)):
            raise ValueError("candidate coverage targets must be finite 2D")
        distances = np.linalg.norm(centers - target, axis=1)
        minimum_distance = float(np.min(distances))
        row = {
            "guide_index": guide_index,
            "attributed_candidate_count": int(
                np.count_nonzero(attributed_guide_indices == guide_index)
            ),
            "minimum_target_distance": minimum_distance,
            "minimum_target_distance_mm": (
                minimum_distance / coordinate_units_per_mm
            ),
            "exact_target_site_present": (
                minimum_distance <= site_tolerance
            ),
        }
        if domain_coverage is not None:
            extra = dict(domain_coverage[guide_index])
            extra.pop("guide_index")
            if set(row) & set(extra):
                raise ValueError(
                    "candidate coverage target domain fields conflict"
                )
            row.update(extra)
        guide_coverage.append(row)

    candidate_indices = [int(value) for value in region_indices]
    return {
        "refdes": str(refdes),
        "domain_sha256": domain_sha256,
        "candidate_count": len(candidate_indices),
        "candidate_region_indices_sha256": _sha256_json(candidate_indices),
        "candidate_region_indices": candidate_indices,
        "guide_coverage": guide_coverage,
    }


def _resolve_unique_net_ids(placedb, requested_net_names, label):
    requested = tuple(requested_net_names)
    if len(set(requested)) != len(requested):
        raise ValueError(f"{label} net names must be unique")
    if not requested:
        return ()
    net_ids_by_name = {}
    for net_id, value in enumerate(placedb.net_names):
        net_ids_by_name.setdefault(_decode(value), []).append(net_id)
    result = []
    for net_name in requested:
        matches = net_ids_by_name.get(net_name, [])
        if len(matches) != 1:
            raise ValueError(
                f"{label} net {net_name!r} must resolve uniquely"
            )
        result.append(matches[0])
    return tuple(result)


def _candidate_coverage_net_endpoints(
    placedb, constraints, requested_net_names, scope_refdes
):
    requested = tuple(requested_net_names)
    net_ids = _resolve_unique_net_ids(
        placedb, requested, "candidate coverage"
    )
    if not requested:
        return {}
    node_refdes = {
        int(constraint.node_id): constraint.refdes
        for constraint in constraints
    }
    scope = frozenset(scope_refdes)
    result = {}
    for net_name, net_id in zip(requested, net_ids):
        endpoints = sorted(
            {
                node_refdes[node_id]
                for pin_id in placedb.net2pin_map[net_id]
                for node_id in (int(placedb.pin2node_map[pin_id]),)
                if node_id in node_refdes and node_refdes[node_id] in scope
            }
        )
        if not endpoints:
            raise ValueError(
                f"candidate coverage net {net_name!r} has no scoped endpoint"
            )
        result[net_name] = endpoints
    return result


def _candidate_set_comparison(components, reference_audit):
    if reference_audit is None:
        return {"configured": False}
    if (
        reference_audit.get("schema") != CANDIDATE_COVERAGE_SCHEMA
        or not reference_audit.get("enabled")
    ):
        raise ValueError("candidate coverage reference audit is incompatible")
    reference_components = reference_audit.get("components")
    if not isinstance(reference_components, dict):
        raise ValueError("candidate coverage reference has no components")
    if set(reference_components) != set(components):
        raise ValueError("candidate coverage scopes do not match")

    rows = []
    total_intersection = 0
    total_union = 0
    for refdes in sorted(components):
        current = components[refdes]
        reference = reference_components[refdes]
        if current["domain_sha256"] != reference.get("domain_sha256"):
            raise ValueError(
                f"candidate coverage domain changed for {refdes}"
            )
        current_sites = set(current["candidate_region_indices"])
        reference_sites = set(reference.get("candidate_region_indices", []))
        if (
            len(current_sites) != current["candidate_count"]
            or len(reference_sites) != reference.get("candidate_count")
            or _sha256_json(current["candidate_region_indices"])
            != current.get("candidate_region_indices_sha256")
            or _sha256_json(reference.get("candidate_region_indices", []))
            != reference.get("candidate_region_indices_sha256")
        ):
            raise ValueError("candidate coverage reference sites are invalid")
        intersection = len(current_sites & reference_sites)
        union = len(current_sites | reference_sites)
        total_intersection += intersection
        total_union += union
        rows.append(
            {
                "refdes": refdes,
                "current_candidate_count": len(current_sites),
                "reference_candidate_count": len(reference_sites),
                "intersection_count": intersection,
                "union_count": union,
                "jaccard": intersection / union,
            }
        )
    return {
        "configured": True,
        "component_count": len(rows),
        "intersection_count": total_intersection,
        "union_count": total_union,
        "jaccard": total_intersection / total_union,
        "components": rows,
    }


def _build_candidate_coverage_audit(
    components,
    guide_paths,
    endpoint_refdes_by_net,
    reference_audit=None,
    reference_json=None,
    reference_sha256=None,
    site_tolerance=DIVERSITY_SITE_TOLERANCE,
    coordinate_units_per_mm=1.0,
):
    if not components:
        raise ValueError("candidate coverage scope must not be empty")
    guide_count = len(guide_paths)
    if guide_count <= 0:
        raise ValueError("candidate coverage requires at least one guide")
    if (
        not math.isfinite(coordinate_units_per_mm)
        or coordinate_units_per_mm <= 0
    ):
        raise ValueError("candidate coverage coordinate scale must be positive")
    for refdes, component in components.items():
        if component.get("refdes") != refdes:
            raise ValueError("candidate coverage component identity mismatch")
        if len(component.get("guide_coverage", [])) != guide_count:
            raise ValueError("candidate coverage guide counts do not align")
    domain_field = "exact_obstacle_free_target_site_present"
    domain_field_presence = [
        domain_field in row
        for component in components.values()
        for row in component["guide_coverage"]
    ]
    if any(domain_field_presence) and not all(domain_field_presence):
        raise ValueError("candidate target domain coverage is incomplete")
    target_domain_coverage_enabled = all(domain_field_presence)

    guides = []
    for guide_index, guide_path in enumerate(guide_paths):
        coverage_rows = [
            components[refdes]["guide_coverage"][guide_index]
            for refdes in sorted(components)
        ]
        distances = [row["minimum_target_distance"] for row in coverage_rows]
        distances_mm = [
            row["minimum_target_distance_mm"] for row in coverage_rows
        ]
        attributed = [
            row["attributed_candidate_count"] for row in coverage_rows
        ]
        summary = {
            "guide_index": guide_index,
            "guide_json": str(guide_path),
            "attributed_candidate_count": sum(attributed),
            "component_count_with_attribution": sum(
                value > 0 for value in attributed
            ),
            "exact_target_component_count": sum(
                row["exact_target_site_present"] for row in coverage_rows
            ),
            "minimum_target_distance": min(distances),
            "maximum_target_distance": max(distances),
            "mean_target_distance": sum(distances) / len(distances),
            "minimum_target_distance_mm": min(distances_mm),
            "maximum_target_distance_mm": max(distances_mm),
            "mean_target_distance_mm": (
                sum(distances_mm) / len(distances_mm)
            ),
        }
        if target_domain_coverage_enabled:
            obstacle_free_distances = [
                row["minimum_obstacle_free_target_distance"]
                for row in coverage_rows
            ]
            obstacle_free_distances_mm = [
                row["minimum_obstacle_free_target_distance_mm"]
                for row in coverage_rows
            ]
            summary.update(
                {
                    "continuous_keepin_target_component_count": sum(
                        row["target_contained_in_keepin"]
                        for row in coverage_rows
                    ),
                    "exact_keepin_target_component_count": sum(
                        row["exact_keepin_target_site_present"]
                        for row in coverage_rows
                    ),
                    "exact_obstacle_free_target_component_count": sum(
                        row["exact_obstacle_free_target_site_present"]
                        for row in coverage_rows
                    ),
                    "fixed_obstacle_target_component_count": sum(
                        row["target_fixed_obstacle_overlap_count"] > 0
                        for row in coverage_rows
                    ),
                    "minimum_obstacle_free_target_distance": min(
                        obstacle_free_distances
                    ),
                    "maximum_obstacle_free_target_distance": max(
                        obstacle_free_distances
                    ),
                    "mean_obstacle_free_target_distance": (
                        sum(obstacle_free_distances)
                        / len(obstacle_free_distances)
                    ),
                    "minimum_obstacle_free_target_distance_mm": min(
                        obstacle_free_distances_mm
                    ),
                    "maximum_obstacle_free_target_distance_mm": max(
                        obstacle_free_distances_mm
                    ),
                    "mean_obstacle_free_target_distance_mm": (
                        sum(obstacle_free_distances_mm)
                        / len(obstacle_free_distances_mm)
                    ),
                }
            )
        guides.append(summary)

    net_coverage = []
    for net_name, endpoints in endpoint_refdes_by_net.items():
        missing = sorted(set(endpoints) - set(components))
        if missing:
            raise ValueError(
                f"candidate coverage net {net_name!r} has endpoints outside "
                "the audit scope: " + ", ".join(missing)
            )
        guide_rows = []
        for guide_index in range(guide_count):
            rows = [
                components[refdes]["guide_coverage"][guide_index]
                for refdes in endpoints
            ]
            distances = [row["minimum_target_distance"] for row in rows]
            distances_mm = [
                row["minimum_target_distance_mm"] for row in rows
            ]
            summary = {
                "guide_index": guide_index,
                "exact_target_endpoint_count": sum(
                    row["exact_target_site_present"] for row in rows
                ),
                "minimum_target_distance": min(distances),
                "maximum_target_distance": max(distances),
                "mean_target_distance": sum(distances) / len(distances),
                "minimum_target_distance_mm": min(distances_mm),
                "maximum_target_distance_mm": max(distances_mm),
                "mean_target_distance_mm": (
                    sum(distances_mm) / len(distances_mm)
                ),
            }
            if target_domain_coverage_enabled:
                obstacle_free_distances = [
                    row["minimum_obstacle_free_target_distance"]
                    for row in rows
                ]
                obstacle_free_distances_mm = [
                    row["minimum_obstacle_free_target_distance_mm"]
                    for row in rows
                ]
                summary.update(
                    {
                        "continuous_keepin_target_endpoint_count": sum(
                            row["target_contained_in_keepin"] for row in rows
                        ),
                        "exact_keepin_target_endpoint_count": sum(
                            row["exact_keepin_target_site_present"]
                            for row in rows
                        ),
                        "exact_obstacle_free_target_endpoint_count": sum(
                            row["exact_obstacle_free_target_site_present"]
                            for row in rows
                        ),
                        "fixed_obstacle_target_endpoint_count": sum(
                            row["target_fixed_obstacle_overlap_count"] > 0
                            for row in rows
                        ),
                        "minimum_obstacle_free_target_distance": min(
                            obstacle_free_distances
                        ),
                        "maximum_obstacle_free_target_distance": max(
                            obstacle_free_distances
                        ),
                        "mean_obstacle_free_target_distance": (
                            sum(obstacle_free_distances) / len(rows)
                        ),
                        "minimum_obstacle_free_target_distance_mm": min(
                            obstacle_free_distances_mm
                        ),
                        "maximum_obstacle_free_target_distance_mm": max(
                            obstacle_free_distances_mm
                        ),
                        "mean_obstacle_free_target_distance_mm": (
                            sum(obstacle_free_distances_mm) / len(rows)
                        ),
                    }
                )
            guide_rows.append(summary)
        net_coverage.append(
            {
                "net_name": net_name,
                "endpoint_count": len(endpoints),
                "endpoint_refdes": list(endpoints),
                "guides": guide_rows,
            }
        )

    comparison = _candidate_set_comparison(components, reference_audit)
    comparison["reference_json"] = (
        str(reference_json) if reference_json is not None else None
    )
    comparison["reference_sha256"] = reference_sha256
    return {
        "schema": CANDIDATE_COVERAGE_SCHEMA,
        "enabled": True,
        "site_tolerance": site_tolerance,
        "coordinate_units_per_mm": coordinate_units_per_mm,
        "target_domain_coverage_enabled": (
            target_domain_coverage_enabled
        ),
        "scope_count": len(components),
        "scope_refdes": sorted(components),
        "candidate_count": sum(
            row["candidate_count"] for row in components.values()
        ),
        "guide_count": guide_count,
        "guides": guides,
        "net_endpoint_coverage": net_coverage,
        "reference_comparison": comparison,
        "components": components,
    }


def _rows_by_side(rows) -> dict[str, list]:
    grouped = {side: [] for side in PLACEMENT_SIDES}
    for row in rows:
        side = row["constraint"].side
        if side not in grouped:
            raise ValueError(f"unknown constraint side: {side}")
        grouped[side].append(row)
    return grouped


def _decode(value) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _integral_net_weight(value) -> int:
    weight = float(value)
    if (
        not math.isfinite(weight)
        or weight < 0
        or not math.isclose(weight, round(weight), abs_tol=1e-12)
    ):
        raise ValueError("CP-SAT requires integral net weights")
    return int(round(weight))


def _effective_integer_hpwl_limit(
    necessary_hpwl_limit,
    integer_scale,
    rounding_allowance,
    integer_hpwl_ceiling,
):
    if integer_scale <= 0:
        raise ValueError("integer scale must be positive")
    if rounding_allowance < 0:
        raise ValueError("rounding allowance must be non-negative")
    limits = []
    if necessary_hpwl_limit is not None:
        if not math.isfinite(necessary_hpwl_limit) or necessary_hpwl_limit < 0:
            raise ValueError(
                "necessary HPWL limit must be finite and non-negative"
            )
        limits.append(
            math.floor(necessary_hpwl_limit * integer_scale)
            + rounding_allowance
        )
    if integer_hpwl_ceiling is not None:
        if isinstance(integer_hpwl_ceiling, bool) or integer_hpwl_ceiling <= 0:
            raise ValueError("integer HPWL ceiling must be positive")
        limits.append(int(integer_hpwl_ceiling))
    return min(limits) if limits else None


def _integer_hpwl_by_net(placedb, node_x, node_y, integer_scale):
    rows = []
    total = 0
    for net_id, pins in enumerate(placedb.net2pin_map):
        if not len(pins):
            continue
        pin_x = []
        pin_y = []
        for pin_id in pins:
            node_id = int(placedb.pin2node_map[pin_id])
            pin_x.append(
                _scaled(node_x[node_id], integer_scale)
                + _scaled(placedb.pin_offset_x[pin_id], integer_scale)
            )
            pin_y.append(
                _scaled(node_y[node_id], integer_scale)
                + _scaled(placedb.pin_offset_y[pin_id], integer_scale)
            )
        weight = _integral_net_weight(placedb.net_weights[net_id])
        hpwl = weight * (
            max(pin_x) - min(pin_x) + max(pin_y) - min(pin_y)
        )
        total += hpwl
        rows.append(
            {
                "net_id": net_id,
                "net_name": _decode(placedb.net_names[net_id]),
                "integer_hpwl": hpwl,
            }
        )
    return total, rows


def _candidate_coordinate_mismatches(rows, solver):
    mismatches = []
    for row in rows:
        if row["integer_node_lowers"] is None:
            continue
        selected = int(solver.value(row["site_var"]))
        expected = row["integer_node_lowers"][selected]
        actual = np.asarray(
            (
                solver.value(row["node_x_var"]),
                solver.value(row["node_y_var"]),
            ),
            dtype=np.int64,
        )
        if not np.array_equal(actual, expected):
            mismatches.append(
                {
                    "refdes": row["constraint"].refdes,
                    "candidate_count": len(row["centers"]),
                    "selected_candidate_index": selected,
                    "expected_integer_node_lower": expected.tolist(),
                    "solver_integer_node_lower": actual.tolist(),
                }
            )
    return mismatches


def _solver_integer_hpwl_by_net(solver, objective_rows):
    rows = []
    total = 0
    for row in objective_rows:
        hpwl = row["weight"] * (
            solver.value(row["max_x_var"])
            - solver.value(row["min_x_var"])
            + solver.value(row["max_y_var"])
            - solver.value(row["min_y_var"])
        )
        total += hpwl
        rows.append(
            {
                "net_id": row["net_id"],
                "net_name": row["net_name"],
                "integer_hpwl": hpwl,
            }
        )
    return total, rows


def _objective_replay_audit(
    solver,
    objective_value,
    rows,
    objective_rows,
    placedb,
    node_x,
    node_y,
    integer_scale,
    floating_hpwl,
    rounding_allowance,
    integer_hpwl_limit=None,
    response_objective_mode="hpwl",
    response_objective_net_ids=(),
):
    coordinate_mismatches = _candidate_coordinate_mismatches(rows, solver)
    solver_total, solver_nets = _solver_integer_hpwl_by_net(
        solver, objective_rows
    )
    replay_total, replay_nets = _integer_hpwl_by_net(
        placedb, node_x, node_y, integer_scale
    )
    if [row["net_id"] for row in solver_nets] != [
        row["net_id"] for row in replay_nets
    ]:
        raise ValueError("solver and replay net identities differ")
    net_mismatches = []
    for solver_net, replay_net in zip(solver_nets, replay_nets):
        delta = solver_net["integer_hpwl"] - replay_net["integer_hpwl"]
        if delta:
            net_mismatches.append(
                {
                    "net_id": solver_net["net_id"],
                    "net_name": solver_net["net_name"],
                    "solver_integer_hpwl": solver_net["integer_hpwl"],
                    "selected_site_integer_hpwl": replay_net[
                        "integer_hpwl"
                    ],
                    "delta_integer": delta,
                }
            )
    target_net_ids = tuple(int(value) for value in response_objective_net_ids)
    if len(set(target_net_ids)) != len(target_net_ids):
        raise ValueError("response objective net IDs must be unique")
    solver_nets_by_id = {row["net_id"]: row for row in solver_nets}
    replay_nets_by_id = {row["net_id"]: row for row in replay_nets}
    missing_target_net_ids = sorted(
        set(target_net_ids) - set(solver_nets_by_id)
    )
    if missing_target_net_ids:
        raise ValueError(
            "response objective nets are absent from the HPWL model: "
            + ", ".join(map(str, missing_target_net_ids))
        )
    if response_objective_mode == "target_net_span" and not target_net_ids:
        raise ValueError("target net-span replay requires objective net IDs")
    if response_objective_mode != "target_net_span" and target_net_ids:
        raise ValueError(
            "response objective net IDs require target_net_span mode"
        )
    target_solver_total = (
        sum(
            solver_nets_by_id[net_id]["integer_hpwl"]
            for net_id in target_net_ids
        )
        if target_net_ids
        else None
    )
    target_replay_total = (
        sum(
            replay_nets_by_id[net_id]["integer_hpwl"]
            for net_id in target_net_ids
        )
        if target_net_ids
        else None
    )
    response_objective_available = objective_value is not None
    response_objective_checked_as_hpwl = (
        response_objective_available and response_objective_mode == "hpwl"
    )
    response_objective_checked_as_target_net_span = (
        response_objective_available
        and response_objective_mode == "target_net_span"
    )
    response_objective_checked = (
        response_objective_checked_as_hpwl
        or response_objective_checked_as_target_net_span
    )
    response_solver_total = (
        target_solver_total
        if response_objective_checked_as_target_net_span
        else solver_total
    )
    response_replay_total = (
        target_replay_total
        if response_objective_checked_as_target_net_span
        else replay_total
    )
    rounded_response_objective = (
        int(round(objective_value))
        if response_objective_available
        else None
    )
    objective_is_integral = (
        math.isclose(
            objective_value, rounded_response_objective, abs_tol=1e-6
        )
        if response_objective_checked
        else None
    )
    rounded_objective = (
        rounded_response_objective
        if response_objective_checked
        else None
    )
    float_delta = replay_total / integer_scale - floating_hpwl
    float_within_allowance = (
        abs(float_delta) <= rounding_allowance / integer_scale + 1e-12
    )
    within_integer_hpwl_limit = (
        integer_hpwl_limit is None or replay_total <= integer_hpwl_limit
    )
    passed = (
        (
            not response_objective_checked
            or (
                objective_is_integral
                and rounded_objective == response_solver_total
                and response_solver_total == response_replay_total
            )
        )
        and solver_total == replay_total
        and not net_mismatches
        and not coordinate_mismatches
        and float_within_allowance
        and within_integer_hpwl_limit
    )
    return {
        "passed": passed,
        "response_objective_available": response_objective_available,
        "response_objective_mode": (
            response_objective_mode if response_objective_available else None
        ),
        "response_objective_checked_as_hpwl": (
            response_objective_checked_as_hpwl
        ),
        "response_objective_checked_as_target_net_span": (
            response_objective_checked_as_target_net_span
        ),
        "solver_objective_is_integral": objective_is_integral,
        "solver_objective_integer": rounded_objective,
        "solver_variable_objective_integer": response_solver_total,
        "selected_site_objective_integer": response_replay_total,
        "solver_minus_variable_integer": (
            rounded_objective - response_solver_total
            if response_objective_checked
            else None
        ),
        "solver_minus_selected_site_integer": (
            rounded_objective - response_replay_total
            if response_objective_checked
            else None
        ),
        "global_solver_hpwl_integer": solver_total,
        "global_selected_site_hpwl_integer": replay_total,
        "target_net_ids": list(target_net_ids),
        "target_net_names": [
            solver_nets_by_id[net_id]["net_name"]
            for net_id in target_net_ids
        ],
        "target_solver_span_integer": target_solver_total,
        "target_selected_site_span_integer": target_replay_total,
        "selected_site_minus_floating_hpwl": float_delta,
        "rounding_allowance_integer": rounding_allowance,
        "floating_hpwl_within_rounding_allowance": float_within_allowance,
        "integer_hpwl_limit": integer_hpwl_limit,
        "selected_site_within_integer_hpwl_limit": (
            within_integer_hpwl_limit
        ),
        "candidate_coordinate_mismatch_count": len(coordinate_mismatches),
        "candidate_coordinate_mismatches": coordinate_mismatches,
        "net_objective_mismatch_count": len(net_mismatches),
        "net_objective_mismatches": net_mismatches,
    }


def _set_model_objective(
    model,
    objective_mode,
    hpwl_objective,
    guide_rank_expression,
    target_net_span_objective=None,
):
    if objective_mode == "hpwl":
        if hpwl_objective is None:
            raise ValueError("HPWL objective expression is unavailable")
        expression = hpwl_objective
    elif objective_mode == "guide_rank":
        expression = guide_rank_expression
    elif objective_mode == "target_net_span":
        if target_net_span_objective is None:
            raise ValueError(
                "target net-span objective expression is unavailable"
            )
        expression = target_net_span_objective
    elif objective_mode in {"none", "hpwl_feasibility"}:
        return
    else:
        raise ValueError(f"unknown objective mode: {objective_mode}")
    model.minimize(expression)


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _comma_separated_values(value: str, label: str) -> tuple[str, ...]:
    if not value:
        return ()
    parts = tuple(part.strip() for part in value.split(","))
    if any(not part for part in parts):
        raise ValueError(f"{label} must not contain an empty value")
    if len(set(parts)) != len(parts):
        raise ValueError(f"{label} values must be unique")
    return parts


def _comma_separated_paths(value: str, label: str) -> tuple[Path, ...]:
    if not value:
        return ()
    parts = tuple(part.strip() for part in value.split(","))
    if any(not part for part in parts):
        raise ValueError(f"{label} must not contain an empty path")
    paths = tuple(_resolved_path(part) for part in parts)
    if len(set(paths)) != len(paths):
        raise ValueError(f"{label} paths must be unique")
    return paths


def _exact_reference_site_indices(
    rows, guide, label, tolerance=DIVERSITY_SITE_TOLERANCE
):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("diversity site tolerance must be non-negative")
    row_refdes = [row["constraint"].refdes for row in rows]
    if len(set(row_refdes)) != len(row_refdes):
        raise ValueError("diversity rows must have unique refdes")
    missing = sorted(set(row_refdes) - set(guide))
    if missing:
        raise ValueError(
            f"{label} is missing modeled refdes: " + ", ".join(missing)
        )

    indices = {}
    distances = {}
    for row in rows:
        refdes = row["constraint"].refdes
        centers = np.asarray(row["centers"], dtype=np.float64)
        center = np.asarray(guide[refdes], dtype=np.float64)
        if (
            centers.ndim != 2
            or centers.shape[1] != 2
            or not len(centers)
            or center.shape != (2,)
            or not np.all(np.isfinite(centers))
            or not np.all(np.isfinite(center))
        ):
            raise ValueError(
                f"{label} has invalid candidate coordinates for {refdes}"
            )
        all_distances = np.linalg.norm(centers - center, axis=1)
        matches = np.flatnonzero(all_distances <= tolerance)
        if not len(matches):
            nearest = float(all_distances.min())
            raise ValueError(
                f"{label} for {refdes} is not an exact candidate site; "
                f"nearest distance is {nearest:.12g}"
            )
        if len(matches) != 1:
            raise ValueError(
                f"{label} for {refdes} matches multiple candidate sites"
            )
        index = int(matches[0])
        indices[refdes] = index
        distances[refdes] = float(all_distances[index])
    return indices, distances


def _canonical_site_tuple(scope_rows, indices):
    return [
        {
            "refdes": row["constraint"].refdes,
            "site_index": int(indices[row["constraint"].refdes]),
            "center": row["centers"][
                indices[row["constraint"].refdes]
            ].tolist(),
        }
        for row in scope_rows
    ]


def _add_diversity_constraints(
    model,
    rows,
    reference=None,
    minimum_changed_sites=None,
    excluded_references=(),
    movable_refdes=(),
    fix_guide=False,
    site_tolerance=DIVERSITY_SITE_TOLERANCE,
):
    minimum_was_requested = minimum_changed_sites is not None
    minimum_changed_sites = (
        0 if minimum_changed_sites is None else minimum_changed_sites
    )
    if minimum_changed_sites < 0:
        raise ValueError("minimum changed sites must be non-negative")
    if (minimum_was_requested or excluded_references) and reference is None:
        raise ValueError(
            "diversity constraints require M336_DIVERSITY_REFERENCE_JSON"
        )
    if reference is None:
        return {
            "configured": False,
            "enabled": False,
            "passed": True,
            "solution_replay_available": False,
        }, None

    reference_indices, reference_distances = _exact_reference_site_indices(
        rows,
        reference["guide"],
        "diversity reference",
        site_tolerance,
    )
    movable = frozenset(movable_refdes)
    scope_rows = tuple(
        sorted(
            (
                row
                for row in rows
                if len(row["centers"]) > 1
                and (not fix_guide or row["constraint"].refdes in movable)
            ),
            key=lambda row: row["constraint"].refdes,
        )
    )
    scope_refdes = tuple(row["constraint"].refdes for row in scope_rows)
    scope_set = frozenset(scope_refdes)
    fixed_domain_refdes = sorted(
        row["constraint"].refdes
        for row in rows
        if row["constraint"].refdes in movable and len(row["centers"]) == 1
    )

    changed_vars = []
    if minimum_was_requested:
        for row in scope_rows:
            refdes = row["constraint"].refdes
            changed = model.new_bool_var(f"changed_from_reference_{refdes}")
            model.add(
                row["site_var"] != reference_indices[refdes]
            ).only_enforce_if(changed)
            model.add(
                row["site_var"] == reference_indices[refdes]
            ).only_enforce_if(changed.Not())
            changed_vars.append(changed)
        model.add(sum(changed_vars) >= minimum_changed_sites)

    excluded_metadata = []
    excluded_tuples = []
    seen_tuples = set()
    for excluded_index, excluded in enumerate(excluded_references):
        indices, distances = _exact_reference_site_indices(
            rows,
            excluded["guide"],
            f"excluded site tuple {excluded_index}",
            site_tolerance,
        )
        outside_scope = sorted(
            refdes
            for refdes, index in indices.items()
            if refdes not in scope_set and index != reference_indices[refdes]
        )
        if outside_scope:
            raise ValueError(
                f"excluded site tuple {excluded_index} changes components "
                "outside diversity scope: " + ", ".join(outside_scope)
            )
        site_tuple = tuple(indices[refdes] for refdes in scope_refdes)
        if not site_tuple:
            raise ValueError(
                "exact site no-goods require a non-empty diversity scope"
            )
        if site_tuple in seen_tuples:
            raise ValueError("excluded exact site tuples must be unique")
        seen_tuples.add(site_tuple)
        excluded_tuples.append(site_tuple)
        model.add_forbidden_assignments(
            [row["site_var"] for row in scope_rows], [site_tuple]
        )
        excluded_metadata.append(
            {
                "index": excluded_index,
                "json": excluded["json"],
                "sha256": excluded["sha256"],
                "site_tuple": _canonical_site_tuple(scope_rows, indices),
                "maximum_site_distance": max(distances.values(), default=0.0),
            }
        )

    audit = {
        "configured": True,
        "enabled": minimum_was_requested or bool(excluded_references),
        "reference_json": reference["json"],
        "reference_sha256": reference["sha256"],
        "site_tolerance": site_tolerance,
        "reference_mapping_passed": True,
        "reference_maximum_site_distance": max(
            reference_distances.values(), default=0.0
        ),
        "scope_count": len(scope_rows),
        "scope_refdes": list(scope_refdes),
        "fixed_domain_excluded_refdes": fixed_domain_refdes,
        "minimum_changed_sites_requested": minimum_was_requested,
        "minimum_changed_sites": minimum_changed_sites,
        "reference_site_tuple": _canonical_site_tuple(
            scope_rows, reference_indices
        ),
        "excluded_site_tuple_count": len(excluded_tuples),
        "excluded_site_tuples": excluded_metadata,
        "solution_replay_available": False,
        "passed": None,
    }
    state = {
        "scope_rows": scope_rows,
        "reference_indices": tuple(
            reference_indices[refdes] for refdes in scope_refdes
        ),
        "excluded_tuples": tuple(excluded_tuples),
    }
    return audit, state


def _diversity_replay_audit(solver, audit, state):
    if state is None:
        return dict(audit)
    result = dict(audit)
    selected = tuple(
        int(solver.value(row["site_var"])) for row in state["scope_rows"]
    )
    changed_refdes = [
        row["constraint"].refdes
        for row, selected_index, reference_index in zip(
            state["scope_rows"], selected, state["reference_indices"]
        )
        if selected_index != reference_index
    ]
    matched_no_goods = [
        index
        for index, excluded in enumerate(state["excluded_tuples"])
        if selected == excluded
    ]
    result.update(
        {
            "solution_replay_available": True,
            "actual_changed_site_count": len(changed_refdes),
            "actual_changed_refdes": changed_refdes,
            "selected_site_tuple": _canonical_site_tuple(
                state["scope_rows"],
                {
                    row["constraint"].refdes: index
                    for row, index in zip(state["scope_rows"], selected)
                },
            ),
            "matched_excluded_site_tuple_indices": matched_no_goods,
            "passed": len(changed_refdes)
            >= result["minimum_changed_sites"]
            and not matched_no_goods,
        }
    )
    return result


def _selected_site_in_region(selected_site, region_id):
    existing_region = selected_site.get("region_id")
    if existing_region is not None and existing_region != region_id:
        raise ValueError(
            "selected site region conflicts with fixed assignment"
        )
    result = dict(selected_site)
    result["region_id"] = region_id
    return result


def _guide_rank_replay_audit(
    solver, rows, objective_mode, objective_value, guide_rank_ceiling
):
    selected_rank = sum(
        int(solver.value(row["site_var"])) for row in rows
    )
    objective_available = (
        objective_mode == "guide_rank" and objective_value is not None
    )
    rounded_objective = (
        int(round(objective_value)) if objective_available else None
    )
    objective_is_integral = (
        math.isclose(objective_value, rounded_objective, abs_tol=1e-6)
        if objective_available
        else None
    )
    objective_matches_selected_rank = (
        objective_is_integral and rounded_objective == selected_rank
        if objective_available
        else None
    )
    within_ceiling = (
        guide_rank_ceiling is None or selected_rank <= guide_rank_ceiling
    )
    return {
        "passed": within_ceiling
        and (
            not objective_available or objective_matches_selected_rank
        ),
        "selected_guide_rank": selected_rank,
        "guide_rank_ceiling": guide_rank_ceiling,
        "selected_guide_rank_within_ceiling": within_ceiling,
        "response_objective_available": objective_available,
        "solver_objective_is_integral": objective_is_integral,
        "solver_objective_integer": rounded_objective,
        "solver_objective_matches_selected_guide_rank": (
            objective_matches_selected_rank
        ),
    }


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_placement_atomic(placedb, path: Path, node_x, node_y) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        placedb.write_pl(None, str(temporary), node_x, node_y)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
        output_dir=_context_output_dir(
            OUTPUT, os.environ.get("M336_CONTEXT_DIR", "")
        ),
        assignment=ASSIGNMENT,
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
    source_data = json.loads(SOURCE.read_text())
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

    packing_side = os.environ.get("M336_PACKING_SIDE", "TOP")
    packing_sides = _packing_sides(packing_side)
    controlled_ids = {constraint.node_id for constraint in context.constraints}
    obstacles_by_side = {side: [] for side in PLACEMENT_SIDES}
    fixed_obstacles_by_side = {side: [] for side in PLACEMENT_SIDES}
    for node_id in range(placedb.num_physical_nodes):
        node_side = (
            "TOP" if bool(placedb.node_side_flag[node_id]) else "BOTTOM"
        )
        if node_id in controlled_ids or node_side not in packing_sides:
            continue
        width = float(placedb.node_size_x[node_id])
        height = float(placedb.node_size_y[node_id])
        footprint = _fixed_footprint_local(
            context, placedb, node_id, "decomposed"
        )
        obstacle = affinity.translate(
            footprint,
            xoff=float(fixed_x[node_id]) + width / 2,
            yoff=float(fixed_y[node_id]) + height / 2,
        )
        obstacles_by_side[node_side].append(obstacle)
        fixed_obstacles_by_side[node_side].append(
            (_decode(placedb.node_names[node_id]), obstacle)
        )

    constraints = sorted(
        (row for row in context.constraints if row.side in packing_sides),
        key=lambda row: row.refdes,
    )
    constraint_counts_by_side = {
        side: sum(constraint.side == side for constraint in constraints)
        for side in PLACEMENT_SIDES
    }
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
    separate_hint_text = os.environ.get("M336_HINT_JSON", "")
    if separate_hint_text:
        hint_path = _resolved_path(separate_hint_text)
        hint_guide = load_guide(hint_path)
        hint_json = str(hint_path)
        hint_guide_index = None
        hint_source = "separate"
    else:
        hint_guide_index = int(
            os.environ.get("M336_HINT_GUIDE_INDEX", "0")
        )
        if hint_guide_index < 0 or hint_guide_index >= len(guides):
            raise ValueError(
                f"hint guide index {hint_guide_index} is outside "
                f"[0, {len(guides)})"
            )
        hint_guide = guides[hint_guide_index]
        hint_json = guide_paths[hint_guide_index]
        hint_source = "candidate_guide"
    diversity_reference_text = os.environ.get(
        "M336_DIVERSITY_REFERENCE_JSON", ""
    )
    minimum_changed_sites_text = os.environ.get(
        "M336_MIN_CHANGED_SITES", ""
    )
    minimum_changed_sites = _optional_nonnegative_integer(
        minimum_changed_sites_text, "minimum changed sites"
    )
    excluded_reference_paths = _comma_separated_paths(
        os.environ.get("M336_EXCLUDED_SITE_JSONS", ""),
        "excluded site JSON",
    )
    if (
        minimum_changed_sites_text or excluded_reference_paths
    ) and not diversity_reference_text:
        raise ValueError(
            "diversity constraints require M336_DIVERSITY_REFERENCE_JSON"
        )
    diversity_reference = None
    if diversity_reference_text:
        diversity_reference_path = _resolved_path(diversity_reference_text)
        diversity_reference = {
            "json": str(diversity_reference_path),
            "sha256": _sha256_file(diversity_reference_path),
            "guide": load_guide(diversity_reference_path),
        }
    excluded_references = []
    for excluded_reference_path in excluded_reference_paths:
        excluded_references.append(
            {
                "json": str(excluded_reference_path),
                "sha256": _sha256_file(excluded_reference_path),
                "guide": load_guide(excluded_reference_path),
            }
        )
    candidate_guide_weights = _candidate_guide_weights(
        os.environ.get("M336_CANDIDATE_GUIDE_WEIGHTS", ""), len(guides)
    )
    candidate_coverage_enabled = (
        os.environ.get("M336_AUDIT_CANDIDATE_COVERAGE", "0") == "1"
    )
    candidate_coverage_reference_text = os.environ.get(
        "M336_CANDIDATE_COVERAGE_REFERENCE_JSON", ""
    )
    candidate_coverage_net_names = _comma_separated_values(
        os.environ.get("M336_CANDIDATE_COVERAGE_NETS", ""),
        "candidate coverage net names",
    )
    if (
        candidate_coverage_reference_text or candidate_coverage_net_names
    ) and not candidate_coverage_enabled:
        raise ValueError(
            "candidate coverage reference/nets require "
            "M336_AUDIT_CANDIDATE_COVERAGE=1"
        )

    candidate_limit = int(os.environ.get("M336_CANDIDATE_LIMIT", "512"))
    expanded_limit = int(os.environ.get("M336_EXPANDED_CANDIDATE_LIMIT", "0"))
    expanded_refdes = frozenset(
        value
        for value in os.environ.get("M336_EXPANDED_REFDES", "").split(",")
        if value
    )
    integer_scale = int(os.environ.get("M336_INTEGER_SCALE", "1000000"))
    integer_hpwl_ceiling_text = os.environ.get(
        "M336_INTEGER_HPWL_CEILING", ""
    )
    integer_hpwl_ceiling = (
        int(integer_hpwl_ceiling_text)
        if integer_hpwl_ceiling_text
        else None
    )
    if integer_hpwl_ceiling is not None and integer_hpwl_ceiling <= 0:
        raise ValueError("integer HPWL ceiling must be positive")
    interval_inset = int(os.environ.get("M336_INTERVAL_INSET", "1"))
    if interval_inset < 0:
        raise ValueError("interval inset must be non-negative")
    optimize_hpwl = os.environ.get("M336_OPTIMIZE_HPWL", "0") == "1"
    target_net_span_names = _comma_separated_values(
        os.environ.get("M336_OPTIMIZE_NET_SPANS", ""),
        "target net-span",
    )
    target_net_span_ids = _resolve_unique_net_ids(
        placedb, target_net_span_names, "target net-span"
    )
    minimum_score = float(os.environ.get("M336_MINIMUM_SCORE", "0"))
    if minimum_score < 0:
        raise ValueError("minimum score must be non-negative")
    minimize_guide_rank = os.environ.get("M336_MINIMIZE_GUIDE_RANK", "0") == "1"
    if sum(
        (
            bool(optimize_hpwl),
            bool(minimize_guide_rank),
            bool(target_net_span_names),
        )
    ) > 1:
        raise ValueError(
            "HPWL, guide-rank, and target net-span objectives are "
            "mutually exclusive"
        )
    if target_net_span_names and integer_hpwl_ceiling is None:
        raise ValueError(
            "target net-span objective requires an explicit integer "
            "HPWL ceiling"
        )
    guide_rank_ceiling = _optional_nonnegative_integer(
        os.environ.get("M336_GUIDE_RANK_CEILING", ""),
        "guide-rank ceiling",
    )
    enforce_hpwl = (
        optimize_hpwl
        or bool(target_net_span_names)
        or minimum_score > 0
        or integer_hpwl_ceiling is not None
    )
    has_objective = (
        optimize_hpwl
        or minimize_guide_rank
        or bool(target_net_span_names)
    )
    if optimize_hpwl:
        objective_mode = "hpwl"
    elif minimize_guide_rank:
        objective_mode = "guide_rank"
    elif target_net_span_names:
        objective_mode = "target_net_span"
    else:
        objective_mode = "none"
    if objective_mode == "none" and enforce_hpwl:
        objective_mode = "hpwl_feasibility"
    search_branching = _search_branching_mode(
        os.environ.get("M336_SEARCH_BRANCHING", "automatic")
    )
    model = cp_model.CpModel()
    rows = []
    packed_node_vars = {}
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
    required_guide_support_indices = _required_guide_support_indices(
        os.environ.get("M336_REQUIRED_GUIDE_SUPPORT_INDICES", ""),
        len(guides),
    )
    candidate_guide_support_audit = _candidate_guide_support_audit(
        hint_guide,
        hint_json,
        guides,
        guide_paths,
        known_refdes,
        movable_refdes,
        fix_guide,
        required_guide_support_indices,
    )
    if not candidate_guide_support_audit["all_required_guides_supported"]:
        incomplete = [
            row
            for row in candidate_guide_support_audit["guides"]
            if row["required"] and not row["support_complete"]
        ]
        details = "; ".join(
            f'{row["guide_index"]}: '
            + ", ".join(row["outside_movable_refdes"])
            for row in incomplete
        )
        raise ValueError(
            "required candidate guide support is incomplete: " + details
        )
    candidate_coverage_scope = tuple(
        sorted(
            movable_refdes
            if fix_guide and movable_refdes
            else known_refdes
        )
    )
    candidate_coverage_reference_path = None
    candidate_coverage_reference_sha256 = None
    candidate_coverage_reference_audit = None
    if candidate_coverage_enabled and candidate_coverage_reference_text:
        candidate_coverage_reference_path = _resolved_path(
            candidate_coverage_reference_text
        )
        candidate_coverage_reference_sha256 = _sha256_file(
            candidate_coverage_reference_path
        )
        candidate_coverage_reference_data = json.loads(
            candidate_coverage_reference_path.read_text()
        )
        candidate_coverage_reference_audit = (
            candidate_coverage_reference_data.get(
                "candidate_coverage_audit"
            )
        )
        if not isinstance(candidate_coverage_reference_audit, dict):
            raise ValueError(
                "candidate coverage reference result has no audit"
            )
    candidate_coverage_endpoints = (
        _candidate_coverage_net_endpoints(
            placedb,
            constraints,
            candidate_coverage_net_names,
            candidate_coverage_scope,
        )
        if candidate_coverage_enabled
        else {}
    )
    candidate_coverage_components = {}
    fixed_assumption_refdes = {}
    fixed_assumptions = {}
    guide_site_distances = {}
    hint_site_indices = {}
    hint_site_distances = {}
    single_site_fixed_refdes = []
    build_started = time.perf_counter()

    for constraint in constraints:
        local = constraint.domain.footprint_local
        is_rectangle = _is_axis_aligned_rectangle(local)
        if not is_rectangle and nonrect_mode == "bbox":
            # A bounding box only removes solutions; it cannot admit a true
            # polygon overlap that NoOverlap2D would otherwise miss.
            conservative_bbox_refdes.append(constraint.refdes)
        eligible = _obstacle_free_candidate_indices(
            constraint, obstacles_by_side[constraint.side]
        )
        centers = constraint.domain.valid_centers[eligible]
        coverage_domain_sha256 = None
        coverage_target_domains = None
        if (
            candidate_coverage_enabled
            and constraint.refdes in candidate_coverage_scope
        ):
            coverage_domain_sha256 = _candidate_domain_fingerprint(
                eligible, centers
            )
            coverage_target_domains = _candidate_target_domain_coverage(
                constraint,
                eligible,
                guides,
                fixed_obstacles_by_side[constraint.side],
                coordinate_units_per_mm=abs(
                    float(context.alignment.scale)
                ),
            )
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
            attributed_guide_indices = np.zeros(
                len(order), dtype=np.int64
            )
        else:
            target_count = min(local_limit or len(eligible), len(eligible))
            order, attributed_guide_indices = _weighted_candidate_selection(
                orders, candidate_guide_weights, target_count
            )
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
        attributed_guide_indices = attributed_guide_indices[unique_indices]
        integer_node_lowers = None
        if enforce_hpwl:
            node_lowers = np.column_stack(
                (
                    centers[:, 0] - constraint.node_width / 2,
                    centers[:, 1] - constraint.node_height / 2,
                )
            )
            integer_node_lowers = np.rint(
                node_lowers * integer_scale
            ).astype(np.int64)
            node_quantization_error = np.max(
                np.abs(
                    integer_node_lowers / integer_scale - node_lowers
                ),
                initial=0.0,
            )
            max_quantization_error = max(
                max_quantization_error, node_quantization_error
            )
        guide_site_distances[constraint.refdes] = float(
            np.linalg.norm(
                centers[0]
                - np.asarray(guides[0][constraint.refdes], dtype=np.float64)
            )
        )
        hint_preferred = np.asarray(
            hint_guide[constraint.refdes], dtype=np.float64
        )
        hint_distances = np.square(centers - hint_preferred).sum(axis=1)
        hint_site_index = int(
            np.lexsort((eligible, hint_distances))[0]
        )
        hint_site_indices[constraint.refdes] = hint_site_index
        hint_site_distances[constraint.refdes] = float(
            np.sqrt(hint_distances[hint_site_index])
        )
        if (
            fix_guide
            and not core_chain
            and constraint.refdes not in movable_refdes
        ):
            selected = np.asarray([hint_site_index], dtype=np.int64)
            integer_starts = integer_starts[selected]
            centers = centers[selected]
            eligible = eligible[selected]
            attributed_guide_indices = attributed_guide_indices[selected]
            if integer_node_lowers is not None:
                integer_node_lowers = integer_node_lowers[selected]
            hint_site_index = 0
            hint_site_indices[constraint.refdes] = hint_site_index
            single_site_fixed_refdes.append(constraint.refdes)

        if coverage_domain_sha256 is not None:
            candidate_coverage_components[constraint.refdes] = (
                _candidate_coverage_component(
                    constraint.refdes,
                    coverage_domain_sha256,
                    eligible,
                    centers,
                    attributed_guide_indices,
                    guides,
                    coordinate_units_per_mm=abs(
                        float(context.alignment.scale)
                    ),
                    domain_coverage=coverage_target_domains,
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
        node_x_var = None
        node_y_var = None
        if enforce_hpwl:
            node_x_var = model.new_int_var(
                int(integer_node_lowers[:, 0].min()),
                int(integer_node_lowers[:, 0].max()),
                f"{constraint.refdes}_node_x",
            )
            node_y_var = model.new_int_var(
                int(integer_node_lowers[:, 1].min()),
                int(integer_node_lowers[:, 1].max()),
                f"{constraint.refdes}_node_y",
            )
            allowed = [
                (int(x), int(y), int(node_x), int(node_y), index)
                for index, ((x, y), (node_x, node_y)) in enumerate(
                    zip(integer_starts, integer_node_lowers)
                )
            ]
            model.add_allowed_assignments(
                [x_var, y_var, node_x_var, node_y_var, site_var],
                allowed,
            )
            model.add_hint(
                node_x_var,
                int(integer_node_lowers[hint_site_index, 0]),
            )
            model.add_hint(
                node_y_var,
                int(integer_node_lowers[hint_site_index, 1]),
            )
            packed_node_vars[constraint.node_id] = (
                node_x_var,
                node_y_var,
            )
        else:
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
        model.add_hint(x_var, int(integer_starts[hint_site_index, 0]))
        model.add_hint(y_var, int(integer_starts[hint_site_index, 1]))
        model.add_hint(site_var, hint_site_index)
        if fix_guide and constraint.refdes not in movable_refdes:
            assumption = model.new_bool_var(
                f"assume_fixed_{constraint.refdes}"
            )
            model.add_assumption(assumption)
            model.add(site_var == hint_site_index).only_enforce_if(assumption)
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
                "integer_node_lowers": integer_node_lowers,
                "node_x_var": node_x_var,
                "node_y_var": node_y_var,
                "width": width,
                "height": height,
                "x_interval": x_interval,
                "y_interval": y_interval,
            }
        )
        candidate_count += len(centers)
        candidate_counts[constraint.refdes] = len(centers)

    candidate_coverage_audit = (
        _build_candidate_coverage_audit(
            candidate_coverage_components,
            guide_paths,
            candidate_coverage_endpoints,
            reference_audit=candidate_coverage_reference_audit,
            reference_json=candidate_coverage_reference_path,
            reference_sha256=candidate_coverage_reference_sha256,
            coordinate_units_per_mm=abs(float(context.alignment.scale)),
        )
        if candidate_coverage_enabled
        else {
            "schema": CANDIDATE_COVERAGE_SCHEMA,
            "enabled": False,
        }
    )

    diversity_audit, diversity_state = _add_diversity_constraints(
        model,
        rows,
        diversity_reference,
        minimum_changed_sites,
        excluded_references,
        movable_refdes,
        fix_guide,
    )

    decision_strategy = {
        "enabled": search_branching != "automatic",
        "search_branching": search_branching,
        "primary_candidate_guide_index": 0,
        "refdes_order": [],
        "guide_delta_by_refdes": {},
        "candidate_count_by_refdes": {},
        "variable_count": 0,
        "variable_strategy": None,
        "domain_strategy": None,
        "order": None,
    }
    if search_branching != "automatic":
        strategy_rows = {
            row["constraint"].refdes: row
            for row in rows
            if len(row["centers"]) > 1
        }
        if not strategy_rows:
            raise ValueError(
                "guided fixed search requires a multi-site component"
            )
        strategy_order, strategy_distances = _guide_delta_refdes_order(
            strategy_rows, guides[0], hint_guide
        )
        model.add_decision_strategy(
            [strategy_rows[refdes]["site_var"] for refdes in strategy_order],
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MIN_VALUE,
        )
        decision_strategy = {
            "enabled": True,
            "search_branching": search_branching,
            "primary_candidate_guide_index": 0,
            "refdes_order": list(strategy_order),
            "guide_delta_by_refdes": {
                refdes: strategy_distances[refdes]
                for refdes in strategy_order
            },
            "candidate_count_by_refdes": {
                refdes: len(strategy_rows[refdes]["centers"])
                for refdes in strategy_order
            },
            "variable_count": len(strategy_order),
            "variable_strategy": "CHOOSE_FIRST",
            "domain_strategy": "SELECT_MIN_VALUE",
            "order": "primary_guide_delta_descending_then_refdes",
        }

    rows_by_side = _rows_by_side(rows)
    for side_rows in rows_by_side.values():
        no_overlap_rows = [
            row
            for row in side_rows
            if row["is_rectangle"] or nonrect_mode == "bbox"
        ]
        if no_overlap_rows:
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
        minimum_positive_area = None
        for side_rows in rows_by_side.values():
            rectangle_rows = [
                row for row in side_rows if row["is_rectangle"]
            ]
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
        for side_rows in rows_by_side.values():
            for first_index, first in enumerate(side_rows):
                for second in side_rows[first_index + 1 :]:
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
    hpwl_objective = None
    target_net_span_objective = None
    hpwl_objective_rows = []
    necessary_hpwl_limit = None
    integer_hpwl_limit = None
    hpwl_rounding_allowance = 0
    guide_rank_expression = sum(row["site_var"] for row in rows)
    if guide_rank_ceiling is not None:
        model.add(guide_rank_expression <= guide_rank_ceiling)
    if enforce_hpwl:
        constraint_by_node = {
            constraint.node_id: constraint for constraint in context.constraints
        }
        source_node_lowers = {}
        for constraint in context.constraints:
            if constraint.node_id in packed_node_vars:
                continue
            source_site = source_data["selected_sites"][constraint.refdes]
            center = np.asarray(source_site["center"], dtype=np.float64)
            source_node_lowers[constraint.node_id] = (
                float(center[0] - constraint.node_width / 2),
                float(center[1] - constraint.node_height / 2),
            )

        coordinate_limit = 2**50
        net_spans = []
        net_span_expressions = {}
        net_weights = []
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
                if node_id in packed_node_vars:
                    node_x_var, node_y_var = packed_node_vars[node_id]
                    pin_x.append(node_x_var + x_offset)
                    pin_y.append(node_y_var + y_offset)
                elif node_id in constraint_by_node:
                    lower_x, lower_y = source_node_lowers[node_id]
                    pin_x.append(_scaled(lower_x, integer_scale) + x_offset)
                    pin_y.append(_scaled(lower_y, integer_scale) + y_offset)
                else:
                    pin_x.append(
                        _scaled(fixed_x[node_id], integer_scale) + x_offset
                    )
                    pin_y.append(
                        _scaled(fixed_y[node_id], integer_scale) + y_offset
                    )
            if not pin_x:
                continue
            integral_weight = _integral_net_weight(
                placedb.net_weights[net_id]
            )
            net_weights.append(integral_weight)
            max_x_var = model.new_int_var(
                -coordinate_limit, coordinate_limit, f"net_{net_id}_max_x"
            )
            min_x_var = model.new_int_var(
                -coordinate_limit, coordinate_limit, f"net_{net_id}_min_x"
            )
            max_y_var = model.new_int_var(
                -coordinate_limit, coordinate_limit, f"net_{net_id}_max_y"
            )
            min_y_var = model.new_int_var(
                -coordinate_limit, coordinate_limit, f"net_{net_id}_min_y"
            )
            model.add_max_equality(max_x_var, pin_x)
            model.add_min_equality(min_x_var, pin_x)
            model.add_max_equality(max_y_var, pin_y)
            model.add_min_equality(min_y_var, pin_y)
            net_span_expression = integral_weight * (
                max_x_var - min_x_var + max_y_var - min_y_var
            )
            net_spans.append(net_span_expression)
            net_span_expressions[net_id] = net_span_expression
            hpwl_objective_rows.append(
                {
                    "net_id": net_id,
                    "net_name": _decode(placedb.net_names[net_id]),
                    "weight": integral_weight,
                    "max_x_var": max_x_var,
                    "min_x_var": min_x_var,
                    "max_y_var": max_y_var,
                    "min_y_var": min_y_var,
                }
            )
        hpwl_objective = sum(net_spans)
        if target_net_span_ids:
            missing_target_net_ids = sorted(
                set(target_net_span_ids) - set(net_span_expressions)
            )
            if missing_target_net_ids:
                raise ValueError(
                    "target net-span nets have no modeled pins: "
                    + ", ".join(map(str, missing_target_net_ids))
                )
            target_net_span_objective = sum(
                net_span_expressions[net_id]
                for net_id in target_net_span_ids
            )
        hpwl_rounding_allowance = _hpwl_rounding_allowance_units(net_weights)
        if minimum_score > 0:
            necessary_hpwl_limit = _score_hpwl_limit(
                baseline_hpwl, baseline_rsmt, minimum_score
            )
        integer_hpwl_limit = _effective_integer_hpwl_limit(
            necessary_hpwl_limit,
            integer_scale,
            hpwl_rounding_allowance,
            integer_hpwl_ceiling,
        )
        if integer_hpwl_limit is not None:
            model.add(hpwl_objective <= integer_hpwl_limit)
    _set_model_objective(
        model,
        objective_mode,
        hpwl_objective,
        guide_rank_expression,
        target_net_span_objective,
    )
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
    stop_after_first_solution = (
        os.environ.get("M336_STOP_AFTER_FIRST_SOLUTION", "0") == "1"
    )

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
        current_solver.parameters.stop_after_first_solution = (
            stop_after_first_solution
        )
        current_solver.parameters.search_branching = {
            "automatic": cp_model.AUTOMATIC_SEARCH,
            "fixed_guide_delta": cp_model.FIXED_SEARCH,
            "partial_fixed_guide_delta": cp_model.PARTIAL_FIXED_SEARCH,
        }[search_branching]
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
            "candidate_coverage_audit": candidate_coverage_audit,
            "candidate_guide_support_audit": (
                candidate_guide_support_audit
            ),
            "decision_strategy": decision_strategy,
            "diversity_audit": diversity_audit,
            "complete": complete,
            "core_chain_steps": core_chain_steps,
            "guide_jsons": guide_paths,
            "hint_json": hint_json,
            "hint_source": hint_source,
            "initial_movable_refdes": sorted(movable_refdes),
            "objective_mode": objective_mode,
            "output_json": str(OUTPUT),
            "released_refdes": sorted(released_refdes),
            "target_net_span_ids": list(target_net_span_ids),
            "target_net_span_names": list(target_net_span_names),
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
        has_incumbent = status_code in (cp_model.FEASIBLE, cp_model.OPTIMAL)
        objective_value = (
            float(solver.objective_value)
            if has_objective and has_incumbent
            else None
        )
        best_objective_bound = (
            float(solver.best_objective_bound)
            if has_objective
            else None
        )
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
            "solver_objective_value": objective_value,
            "solver_best_objective_bound": best_objective_bound,
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
    placement_output = None
    objective_replay_audit = None
    guide_rank_replay_audit = None
    diversity_replay_audit = diversity_audit
    if status_code in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        node_x = np.asarray(placedb.node_x, dtype=np.float64).copy()
        node_y = np.asarray(placedb.node_y, dtype=np.float64).copy()
        node_x[: placedb.num_physical_nodes] = baseline_x
        node_y[: placedb.num_physical_nodes] = baseline_y
        for node_id in range(placedb.num_physical_nodes):
            if node_id not in controlled_ids:
                node_x[node_id] = fixed_x[node_id]
                node_y[node_id] = fixed_y[node_id]
        packed_rows = {row["constraint"].refdes: row for row in rows}
        selected_sites = {}
        for constraint in context.constraints:
            source_site = source_data["selected_sites"][constraint.refdes]
            center = np.asarray(source_site["center"], dtype=np.float64)
            selected_site = _selected_site_in_region(
                source_site, constraint.region_id
            )
            if constraint.side in packing_sides:
                row = packed_rows[constraint.refdes]
                selected = int(solver.value(row["site_var"]))
                center = row["centers"][selected]
                selected_site = {
                    "candidate_index": selected,
                    "region_id": constraint.region_id,
                    "region_candidate_index": int(row["eligible"][selected]),
                    "center": center.tolist(),
                }
            selected_sites[constraint.refdes] = selected_site
            node_x[constraint.node_id] = center[0] - constraint.node_width / 2
            node_y[constraint.node_id] = center[1] - constraint.node_height / 2
        position = torch.from_numpy(np.concatenate((node_x, node_y)))
        legality = context.exact_report(position, placedb)
        hpwl = float(placedb.hpwl(node_x, node_y))
        if enforce_hpwl:
            objective_replay_audit = _objective_replay_audit(
                solver,
                objective_value,
                rows,
                hpwl_objective_rows,
                placedb,
                node_x,
                node_y,
                integer_scale,
                hpwl,
                hpwl_rounding_allowance,
                integer_hpwl_limit,
                response_objective_mode=objective_mode,
                response_objective_net_ids=target_net_span_ids,
            )
        guide_rank_replay_audit = _guide_rank_replay_audit(
            solver,
            rows,
            objective_mode,
            objective_value,
            guide_rank_ceiling,
        )
        diversity_replay_audit = _diversity_replay_audit(
            solver, diversity_audit, diversity_state
        )
        score = 2.0 / (hpwl / baseline_hpwl + hpwl / baseline_rsmt)
        write_placement_atomic(
            placedb, PLACEMENT_OUTPUT, node_x, node_y
        )
        placement_output = str(PLACEMENT_OUTPUT)
    else:
        PLACEMENT_OUTPUT.unlink(missing_ok=True)

    result = {
        "status": status,
        "assignment_json": str(ASSIGNMENT),
        "context_output_dir": str(args.output_dir),
        "packing_side": packing_side,
        "packing_sides": sorted(packing_sides),
        "constraint_counts_by_side": constraint_counts_by_side,
        "obstacle_counts_by_side": {
            side: len(obstacles_by_side[side]) for side in PLACEMENT_SIDES
        },
        "source_json": str(SOURCE),
        "guide_json": guide_paths[0],
        "guide_jsons": guide_paths,
        "candidate_guide_weights": list(candidate_guide_weights),
        "candidate_coverage_audit": candidate_coverage_audit,
        "candidate_guide_support_audit": candidate_guide_support_audit,
        "decision_strategy": decision_strategy,
        "hint_json": hint_json,
        "hint_source": hint_source,
        "manual_baseline_endpoints": sorted(manual_baseline_endpoints),
        "guide_site_distances": guide_site_distances,
        "hint_guide_index": hint_guide_index,
        "hint_site_indices": hint_site_indices,
        "hint_site_distances": hint_site_distances,
        "diversity_audit": diversity_replay_audit,
        "single_site_fixed_domain_count": len(single_site_fixed_refdes),
        "single_site_fixed_refdes": single_site_fixed_refdes,
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
        "objective_mode": objective_mode,
        "target_net_span_ids": list(target_net_span_ids),
        "target_net_span_names": list(target_net_span_names),
        "guide_rank_ceiling": guide_rank_ceiling,
        "minimum_score": minimum_score,
        "necessary_hpwl_limit": necessary_hpwl_limit,
        "integer_hpwl_ceiling": integer_hpwl_ceiling,
        "integer_hpwl_limit": integer_hpwl_limit,
        "hpwl_rounding_allowance_integer": hpwl_rounding_allowance,
        "hpwl_rounding_allowance": (
            hpwl_rounding_allowance / integer_scale
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
        "solver_objective_value": objective_value,
        "solver_best_objective_bound": best_objective_bound,
        "solver_objective_hpwl": (
            objective_value / integer_scale
            if objective_mode == "hpwl" and objective_value is not None
            else None
        ),
        "solver_best_objective_bound_hpwl": (
            best_objective_bound / integer_scale
            if objective_mode == "hpwl"
            and best_objective_bound is not None
            else None
        ),
        "solver_objective_target_net_span": (
            objective_value / integer_scale
            if objective_mode == "target_net_span"
            and objective_value is not None
            else None
        ),
        "solver_best_objective_bound_target_net_span": (
            best_objective_bound / integer_scale
            if objective_mode == "target_net_span"
            and best_objective_bound is not None
            else None
        ),
        "solver_parameters": {
            "audit_candidate_coverage": candidate_coverage_enabled,
            "candidate_coverage_nets": list(
                candidate_coverage_net_names
            ),
            "candidate_coverage_reference_json": (
                str(candidate_coverage_reference_path)
                if candidate_coverage_reference_path is not None
                else None
            ),
            "hint_conflict_limit": hint_conflict_limit,
            "hint_guide_index": hint_guide_index,
            "hint_json": hint_json,
            "hint_source": hint_source,
            "guide_rank_ceiling": guide_rank_ceiling,
            "max_deterministic_time": max_deterministic_time,
            "max_time_in_seconds": max_time_in_seconds,
            "minimum_score": minimum_score,
            "minimum_changed_sites": minimum_changed_sites,
            "minimize_guide_rank": minimize_guide_rank,
            "optimize_hpwl": optimize_hpwl,
            "optimize_net_spans": list(target_net_span_names),
            "num_search_workers": 1,
            "preprocess_threads": PREPROCESS_THREADS,
            "random_seed": random_seed,
            "repair_hint": repair_hint,
            "search_branching": search_branching,
            "stop_after_first_solution": stop_after_first_solution,
        },
        "solver_response_stats": solver.response_stats(),
        "objective_replay_audit": objective_replay_audit,
        "guide_rank_replay_audit": guide_rank_replay_audit,
        "legality": legality,
        "hpwl": hpwl,
        "normalized_score_upper_bound": score,
        "placement": placement_output,
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
                    "objective_replay_audit",
                    "guide_rank_replay_audit",
                    "diversity_audit",
                )
            },
            indent=2,
        )
    )
    if status_code not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return 2
    if objective_replay_audit is not None and not objective_replay_audit[
        "passed"
    ]:
        return 3
    if guide_rank_replay_audit is not None and not guide_rank_replay_audit[
        "passed"
    ]:
        return 4
    if not diversity_replay_audit["passed"]:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
