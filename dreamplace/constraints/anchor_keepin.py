"""Runtime assembly for feature-gated anchor/keep-in experiments."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
import torch
from scipy import ndimage, signal
from scipy.spatial import cKDTree
from shapely import affinity
from shapely.geometry import Point, box

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
from dreamplace.ops.anchor_keepin.anchor_keepin import (
    AnchorKeepInLoss,
    FootprintCollisionLoss,
    SoftKeepInLoss,
)


def _decode_name(name):
    return name.decode("utf-8") if isinstance(name, bytes) else str(name)


def _geometry_boundary_vertices(geometry):
    vertices = []
    exterior = getattr(geometry, "exterior", None)
    if exterior is not None:
        rings = [exterior, *getattr(geometry, "interiors", ())]
        for ring in rings:
            vertices.extend((float(row[0]), float(row[1])) for row in ring.coords)
    elif getattr(geometry, "geoms", None) is not None:
        for child in geometry.geoms:
            vertices.extend(_geometry_boundary_vertices(child))
    elif getattr(geometry, "coords", None) is not None:
        vertices.extend(
            (float(row[0]), float(row[1])) for row in geometry.coords
        )
    return tuple(sorted(set(vertices)))


def _distance_distribution(values):
    values = tuple(float(value) for value in values)
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p90": None,
            "max": None,
        }
    return {
        "count": len(values),
        "mean": float(np.mean(values)),
        "median": float(np.percentile(values, 50)),
        "p90": float(np.percentile(values, 90)),
        "max": float(np.max(values)),
    }


def _collision_shape_key(shape, precision):
    canonical = shapely.normalize(shapely.set_precision(shape, precision))
    if canonical.is_empty or canonical.area <= 0:
        raise ValueError("collision footprint became empty after normalization")
    return canonical.wkb_hex, canonical


def _rasterize_collision_footprint(shape, grid):
    # A half-cell guard makes sampled occupancy conservative at cell boundaries.
    guarded = shape.buffer(grid / 2, cap_style="square", join_style="mitre")
    min_x, min_y, max_x, max_y = guarded.bounds
    first_x = int(math.floor(min_x / grid)) - 2
    last_x = int(math.ceil(max_x / grid)) + 2
    first_y = int(math.floor(min_y / grid)) - 2
    last_y = int(math.ceil(max_y / grid)) + 2
    x_values = np.arange(first_x, last_x + 1, dtype=np.float64) * grid
    y_values = np.arange(first_y, last_y + 1, dtype=np.float64) * grid
    x_grid, y_grid = np.meshgrid(x_values, y_values)
    occupancy = shapely.intersects_xy(guarded, x_grid, y_grid)
    if not occupancy.any():
        raise ValueError("collision footprint rasterization produced no occupied cells")
    return occupancy, first_x, first_y


def _build_collision_sdf(first, second, grid, padding_cells):
    first_mask, first_x, first_y = first
    second_mask, second_x, second_y = second
    correlation = signal.fftconvolve(
        first_mask.astype(np.float32),
        second_mask[::-1, ::-1].astype(np.float32),
        mode="full",
    )
    collision_mask = np.pad(
        correlation > 0.5, padding_cells, constant_values=False
    )
    outside_distance = ndimage.distance_transform_edt(
        ~collision_mask, sampling=grid
    )
    inside_distance = ndimage.distance_transform_edt(
        collision_mask, sampling=grid
    )
    signed_distance = np.where(
        collision_mask,
        -np.maximum(inside_distance - grid / 2, 0.0),
        np.maximum(outside_distance - grid / 2, 0.0),
    ).astype(np.float32)
    origin = (
        (
            first_x
            - second_x
            - (second_mask.shape[1] - 1)
            - padding_cells
        )
        * grid,
        (
            first_y
            - second_y
            - (second_mask.shape[0] - 1)
            - padding_cells
        )
        * grid,
    )
    return signed_distance, origin


def _pack_collision_fields(fields, fill_value):
    if not fields:
        return np.full((2, 2), fill_value, dtype=np.float32), {}
    total_cells = sum(field.size for field, _ in fields.values())
    widest = max(field.shape[1] for field, _ in fields.values())
    target_width = max(widest, int(math.ceil(math.sqrt(total_cells))))
    atlas_width = 1 << int(math.ceil(math.log2(max(target_width, 2))))
    placements = {}
    cursor_x = 0
    cursor_y = 0
    row_height = 0
    ordered = sorted(
        fields.items(),
        key=lambda row: (-row[1][0].shape[0], -row[1][0].shape[1], row[0]),
    )
    for key, (field, _) in ordered:
        height, width = field.shape
        if cursor_x and cursor_x + width + 2 > atlas_width:
            cursor_y += row_height + 2
            cursor_x = 0
            row_height = 0
        placements[key] = (cursor_x, cursor_y)
        cursor_x += width + 2
        row_height = max(row_height, height)
    atlas_height = max(cursor_y + row_height, 2)
    atlas = np.full(
        (atlas_height, atlas_width), fill_value, dtype=np.float32
    )
    for key, (field, _) in fields.items():
        offset_x, offset_y = placements[key]
        height, width = field.shape
        atlas[offset_y : offset_y + height, offset_x : offset_x + width] = field
    return atlas, placements


def _build_footprint_collision_data(
    footprints,
    node_sides,
    active_node_ids,
    num_physical_nodes,
    grid,
    margin,
    tau,
):
    """Build deterministic side-local configuration-space SDF metadata."""
    grid = float(grid)
    margin = float(margin)
    tau = float(tau)
    if grid <= 0 or tau <= 0 or margin < 0:
        raise ValueError("invalid footprint collision field parameters")
    active_node_ids = tuple(sorted(set(int(node_id) for node_id in active_node_ids)))
    active_set = set(active_node_ids)
    invalid_active = [
        node_id
        for node_id in active_node_ids
        if node_id < 0 or node_id >= num_physical_nodes
    ]
    if invalid_active:
        raise ValueError("collision active nodes are not physical: %s" % invalid_active)
    missing = sorted(set(range(num_physical_nodes)) - set(footprints))
    if missing:
        raise ValueError("collision footprints are missing physical nodes: %s" % missing)

    precision = max(grid * 1e-6, 1e-9)
    shape_keys = {}
    shapes = {}
    for node_id in range(num_physical_nodes):
        key, canonical = _collision_shape_key(footprints[node_id], precision)
        shape_keys[node_id] = key
        shapes.setdefault(key, canonical)

    pairs = []
    pair_types = set()
    side_pair_counts = defaultdict(int)
    for first_node_id in range(num_physical_nodes):
        for second_node_id in range(first_node_id + 1, num_physical_nodes):
            if (
                first_node_id not in active_set
                and second_node_id not in active_set
            ):
                continue
            first_side = str(node_sides[first_node_id]).upper()
            second_side = str(node_sides[second_node_id]).upper()
            if first_side != second_side:
                continue
            first_key = shape_keys[first_node_id]
            second_key = shape_keys[second_node_id]
            if first_key <= second_key:
                field_key = (first_key, second_key)
                relative_sign = 1.0
            else:
                field_key = (second_key, first_key)
                relative_sign = -1.0
            pairs.append(
                (first_node_id, second_node_id, field_key, relative_sign)
            )
            pair_types.add(field_key)
            side_pair_counts[first_side] += 1

    padding_cells = int(math.ceil((margin + 12 * tau) / grid)) + 2
    rasterized = {
        key: _rasterize_collision_footprint(shape, grid)
        for key, shape in shapes.items()
    }
    fields = {
        key: _build_collision_sdf(
            rasterized[key[0]], rasterized[key[1]], grid, padding_cells
        )
        for key in sorted(pair_types)
    }
    far_clearance = margin + 20 * tau
    atlas, placements = _pack_collision_fields(fields, far_clearance)

    first_node_ids = []
    second_node_ids = []
    relative_signs = []
    field_origins = []
    atlas_offsets = []
    field_sizes = []
    for first_node_id, second_node_id, field_key, relative_sign in pairs:
        field, origin = fields[field_key]
        first_node_ids.append(first_node_id)
        second_node_ids.append(second_node_id)
        relative_signs.append(relative_sign)
        field_origins.append(origin)
        atlas_offsets.append(placements[field_key])
        field_sizes.append((field.shape[1], field.shape[0]))
    data = {
        "atlas": atlas,
        "first_node_ids": first_node_ids,
        "second_node_ids": second_node_ids,
        "active_node_ids": active_node_ids,
        "relative_signs": relative_signs,
        "field_origins": field_origins,
        "atlas_offsets": atlas_offsets,
        "field_sizes": field_sizes,
        "grid": grid,
        "margin": margin,
        "tau": tau,
    }
    diagnostics = {
        "active_node_count": len(active_node_ids),
        "physical_node_count": int(num_physical_nodes),
        "pair_count": len(pairs),
        "pair_count_by_side": dict(sorted(side_pair_counts.items())),
        "shape_type_count": len(shapes),
        "field_type_count": len(fields),
        "atlas_height": int(atlas.shape[0]),
        "atlas_width": int(atlas.shape[1]),
        "atlas_bytes": int(atlas.nbytes),
        "grid": grid,
        "raster_guard": grid / 2,
        "margin": margin,
        "tau": tau,
        "padding_cells": padding_cells,
        "model": "conservative_raster_configuration_space_sdf",
    }
    return data, diagnostics


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


def _load_placement_source(path, placedb):
    """Load a complete, identity-safe physical-node position source."""
    path = Path(path).resolve()
    names = [
        _decode_name(name)
        for name in placedb.node_names[: placedb.num_physical_nodes]
    ]
    expected = {name: node_id for node_id, name in enumerate(names)}
    orientations = [
        _decode_name(orientation)
        for orientation in placedb.node_orient[: placedb.num_physical_nodes]
    ]
    rows = {}
    unknown = []
    with path.open() as stream:
        for line_number, line in enumerate(stream, start=1):
            fields = line.split()
            if not fields or fields[0].startswith("#") or fields[0] == "UCLA":
                continue
            refdes = fields[0]
            if refdes not in expected:
                unknown.append(refdes)
                continue
            if refdes in rows:
                raise ValueError(
                    "duplicate endpoint source row for %s at line %d"
                    % (refdes, line_number)
                )
            if len(fields) < 3:
                raise ValueError(
                    "invalid endpoint source row at line %d" % line_number
                )
            try:
                lower_left = (float(fields[1]), float(fields[2]))
            except ValueError as error:
                raise ValueError(
                    "invalid endpoint source coordinates for %s" % refdes
                ) from error
            if not all(math.isfinite(value) for value in lower_left):
                raise ValueError(
                    "non-finite endpoint source coordinates for %s" % refdes
                )
            orientation = None
            if ":" in fields:
                marker = fields.index(":")
                if marker + 1 < len(fields):
                    orientation = fields[marker + 1]
            node_id = expected[refdes]
            if orientation != orientations[node_id]:
                raise ValueError(
                    "endpoint source orientation mismatch for %s: %s != %s"
                    % (refdes, orientation, orientations[node_id])
                )
            rows[refdes] = lower_left
    missing = sorted(set(expected) - set(rows))
    if missing or unknown:
        raise ValueError(
            "endpoint source identity mismatch: missing=%s unknown=%s"
            % (missing, sorted(set(unknown)))
        )
    return rows


_PLACEDB_SOURCE_QUANTIZATION_TOLERANCE_MM = 0.500001


def _audit_runtime_source(runtime_positions, runtime_position, placedb):
    """Verify a float PL against the integer-quantized native Bookshelf DB."""
    runtime_position = np.asarray(runtime_position)
    if runtime_position.shape != (placedb.num_nodes * 2,):
        raise ValueError("runtime_position has an invalid shape")

    mismatches = []
    max_abs_delta = 0.0
    quantized_components = 0
    names = [
        _decode_name(name)
        for name in placedb.node_names[: placedb.num_physical_nodes]
    ]
    for node_id, refdes in enumerate(names):
        expected_lower_left = runtime_positions[refdes]
        actual_lower_left = (
            float(runtime_position[node_id]),
            float(runtime_position[placedb.num_nodes + node_id]),
        )
        delta = max(
            abs(actual_lower_left[axis] - expected_lower_left[axis])
            for axis in (0, 1)
        )
        max_abs_delta = max(max_abs_delta, delta)
        if delta > 1e-3:
            quantized_components += 1
        if delta > _PLACEDB_SOURCE_QUANTIZATION_TOLERANCE_MM:
            mismatches.append(refdes)
    if mismatches:
        raise ValueError(
            "runtime endpoint source disagrees with PlaceDB beyond native "
            "Bookshelf quantization tolerance: %s" % sorted(mismatches)
        )
    return {
        "native_bookshelf_quantization_tolerance_mm": (
            _PLACEDB_SOURCE_QUANTIZATION_TOLERANCE_MM
        ),
        "max_abs_delta_mm": max_abs_delta,
        "quantized_component_count": quantized_components,
        "physical_component_count": len(names),
    }


def _parse_endpoint_policy(endpoint_config, anchor_refdes):
    """Validate explicit manual/runtime declarations for frozen anchors."""
    if not isinstance(endpoint_config, dict):
        raise ValueError("endpoint_policy must be an object")
    default_source = endpoint_config.get("default", "runtime")
    if default_source != "runtime":
        raise ValueError("endpoint_policy.default must be runtime")

    def endpoint_names(field):
        values = endpoint_config.get(field, [])
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value for value in values)
            or len(values) != len(set(values))
        ):
            raise ValueError(
                "endpoint_policy.%s must contain unique refdes" % field
            )
        return frozenset(values)

    manual_endpoints = endpoint_names("manual_endpoints")
    runtime_endpoints = endpoint_names("runtime_endpoints")
    if not manual_endpoints:
        raise ValueError("endpoint policy must declare a manual endpoint")
    if not runtime_endpoints:
        raise ValueError("endpoint policy must declare a runtime endpoint")
    if manual_endpoints & runtime_endpoints:
        raise ValueError("manual and runtime endpoint declarations overlap")
    unknown_endpoints = sorted(
        (manual_endpoints | runtime_endpoints) - set(anchor_refdes)
    )
    if unknown_endpoints:
        raise ValueError(
            "endpoint policy names non-anchor components: %s"
            % unknown_endpoints
        )
    return default_source, manual_endpoints, runtime_endpoints


def _native_alignment_targets(runtime_position, placedb):
    """Build geometry registration targets from the untouched native PlaceDB."""
    runtime_position = np.asarray(runtime_position)
    if runtime_position.shape != (placedb.num_nodes * 2,):
        raise ValueError("runtime_position has an invalid shape")
    targets = {}
    for node_id in range(placedb.num_physical_nodes):
        name = _decode_name(placedb.node_names[node_id])
        center = (
            float(runtime_position[node_id])
            + float(placedb.node_size_x[node_id]) / 2,
            float(runtime_position[placedb.num_nodes + node_id])
            + float(placedb.node_size_y[node_id]) / 2,
        )
        if not all(math.isfinite(value) for value in center):
            raise ValueError("non-finite native alignment target for %s" % name)
        targets[name] = center
    return targets


_DOMAIN_CACHE_SCHEMA = "m336_feasible_domain_cache_v1"


def _domain_cache_digest(
    input_hashes,
    endpoint_policy,
    side,
    region_id,
    region,
    width,
    height,
    grid,
    clearance,
    orientation,
    footprint_local,
):
    payload = {
        "schema": _DOMAIN_CACHE_SCHEMA,
        "input_sha256": dict(sorted(input_hashes.items())),
        "endpoint_policy": endpoint_policy,
        "side": side,
        "region_id": region_id,
        "region_sha256": hashlib.sha256(region.wkb).hexdigest(),
        "width": float(width),
        "height": float(height),
        "grid": float(grid),
        "clearance": float(clearance),
        "orientation": orientation,
        "footprint_sha256": hashlib.sha256(footprint_local.wkb).hexdigest(),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_cached_domain(
    path,
    digest,
    region,
    width,
    height,
    clearance,
    grid,
    footprint_local,
):
    try:
        with np.load(path, allow_pickle=False) as cached:
            schema = str(cached["schema"].item())
            cached_digest = str(cached["digest"].item())
            if schema != _DOMAIN_CACHE_SCHEMA or cached_digest != digest:
                raise ValueError("cache identity mismatch")
            x_values = cached["x_values"]
            y_values = cached["y_values"]
            valid_mask = cached["valid_mask"]
            valid_centers = cached["valid_centers"]
            inside_distance = cached["inside_distance"]
            outside_distance = cached["outside_distance"]
    except Exception as error:
        raise RuntimeError(
            "cannot load feasible-domain cache %s: %s" % (path, error)
        ) from error
    if (
        valid_mask.shape != (len(y_values), len(x_values))
        or inside_distance.shape != valid_mask.shape
        or outside_distance.shape != valid_mask.shape
        or valid_centers.ndim != 2
        or valid_centers.shape[1:] != (2,)
        or not len(valid_centers)
    ):
        raise RuntimeError("invalid feasible-domain cache arrays: %s" % path)
    return FeasibleDomain(
        region=region,
        width=float(width),
        height=float(height),
        clearance=float(clearance),
        grid=float(grid),
        x_values=x_values,
        y_values=y_values,
        valid_mask=valid_mask,
        valid_centers=valid_centers,
        inside_distance=inside_distance,
        outside_distance=outside_distance,
        _tree=cKDTree(valid_centers),
        footprint_local=footprint_local,
    )


def _write_cached_domain(path, digest, domain):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        "%s.%d.tmp.npz" % (path.name, os.getpid())
    )
    np.savez_compressed(
        temporary,
        schema=np.asarray(_DOMAIN_CACHE_SCHEMA),
        digest=np.asarray(digest),
        x_values=domain.x_values,
        y_values=domain.y_values,
        valid_mask=domain.valid_mask,
        valid_centers=domain.valid_centers,
        inside_distance=domain.inside_distance,
        outside_distance=domain.outside_distance,
    )
    os.replace(temporary, path)


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
        target = np.asarray(
            constraint.target_center
            if preferred_center is None
            else preferred_center
        )
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


def _is_axis_aligned_rectangle(shape, epsilon=1e-12):
    bounds = shape.bounds
    bounds_area = max(0.0, bounds[2] - bounds[0]) * max(
        0.0, bounds[3] - bounds[1]
    )
    return abs(shape.area - bounds_area) <= epsilon


def _candidate_bounds(constraint, candidates):
    local_min_x, local_min_y, local_max_x, local_max_y = (
        constraint.domain.footprint_local.bounds
    )
    return np.column_stack(
        (
            candidates[:, 0] + local_min_x,
            candidates[:, 1] + local_min_y,
            candidates[:, 0] + local_max_x,
            candidates[:, 1] + local_max_y,
        )
    )


def _bbox_overlap_metrics(candidate_bounds, other_bounds, epsilon=1e-12):
    if not len(other_bounds):
        return (
            np.zeros(len(candidate_bounds), dtype=np.int64),
            np.zeros(len(candidate_bounds), dtype=np.float64),
        )
    other_bounds = np.asarray(other_bounds, dtype=np.float64).reshape(-1, 4)
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
    overlap_area = overlap_x * overlap_y
    return (
        np.count_nonzero(overlap_area > epsilon, axis=1),
        np.sum(overlap_area, axis=1),
    )


def _greedy_pack(ordered, obstacles, candidate_mode, preferred_centers):
    occupied = list(obstacles)
    rectangle_fast_path = all(
        _is_axis_aligned_rectangle(constraint.domain.footprint_local)
        for constraint in ordered
    ) and all(_is_axis_aligned_rectangle(obstacle) for obstacle in obstacles)
    occupied_bounds = [obstacle.bounds for obstacle in obstacles]
    placements = {}
    footprints = []
    for index, constraint in enumerate(ordered):
        preferred = preferred_centers.get(constraint.node_id)
        selected = None
        candidate_indices = _ordered_candidate_indices(
            constraint, candidate_mode, preferred
        )
        if rectangle_fast_path:
            candidates = constraint.domain.valid_centers[candidate_indices]
            overlap_counts, _ = _bbox_overlap_metrics(
                _candidate_bounds(constraint, candidates), occupied_bounds
            )
            free = np.flatnonzero(overlap_counts == 0)
            if len(free):
                selected = candidates[free[0]]
                footprint = constraint.domain.footprint(selected)
        else:
            for candidate_index in candidate_indices:
                center = constraint.domain.valid_centers[candidate_index]
                footprint = constraint.domain.footprint(center)
                if not _has_overlap(footprint, occupied):
                    selected = center
                    break
        if selected is None:
            return None, index, placements, footprints
        occupied.append(footprint)
        occupied_bounds.append(footprint.bounds)
        footprints.append(footprint)
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


def _batch_overlap_metrics(footprints, others, epsilon=1e-12):
    """Score positive-area intersections for several candidate footprints."""
    footprints = tuple(footprints)
    others = tuple(others)
    counts = np.zeros(len(footprints), dtype=np.int64)
    areas = np.zeros(len(footprints), dtype=np.float64)
    if not footprints or not others:
        return counts, areas
    if not hasattr(shapely, "intersection"):
        metrics = [_overlap_metrics(footprint, others) for footprint in footprints]
        return (
            np.asarray([row[0] for row in metrics], dtype=np.int64),
            np.asarray([row[1] for row in metrics], dtype=np.float64),
        )

    footprint_bounds = np.asarray(
        [footprint.bounds for footprint in footprints], dtype=np.float64
    )
    other_bounds = np.asarray(
        [other.bounds for other in others], dtype=np.float64
    )
    overlap_width = np.minimum(
        footprint_bounds[:, None, 2], other_bounds[None, :, 2]
    ) - np.maximum(
        footprint_bounds[:, None, 0], other_bounds[None, :, 0]
    )
    overlap_height = np.minimum(
        footprint_bounds[:, None, 3], other_bounds[None, :, 3]
    ) - np.maximum(
        footprint_bounds[:, None, 1], other_bounds[None, :, 1]
    )
    candidate_rows, other_columns = np.nonzero(
        (overlap_width > epsilon) & (overlap_height > epsilon)
    )
    if not len(candidate_rows):
        return counts, areas

    footprint_array = np.asarray(footprints, dtype=object)
    other_array = np.asarray(others, dtype=object)
    intersection_areas = np.asarray(
        shapely.area(
            shapely.intersection(
                footprint_array[candidate_rows],
                other_array[other_columns],
            )
        ),
        dtype=np.float64,
    )
    positive = intersection_areas > epsilon
    positive_rows = candidate_rows[positive]
    counts += np.bincount(positive_rows, minlength=len(footprints))
    areas += np.bincount(
        positive_rows,
        weights=intersection_areas[positive],
        minlength=len(footprints),
    )
    return counts, areas


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
    return _bbox_overlap_metrics(
        _candidate_bounds(constraint, candidates), other_bounds
    )[1]


def _obstacle_free_candidate_indices(constraint, obstacles):
    candidates = constraint.domain.valid_centers
    if not obstacles:
        return np.arange(len(candidates), dtype=np.int64)
    obstacle_bounds = np.asarray(
        [obstacle.bounds for obstacle in obstacles], dtype=np.float64
    )
    bbox_counts, _ = _bbox_overlap_metrics(
        _candidate_bounds(constraint, candidates), obstacle_bounds
    )
    eligible = bbox_counts == 0
    for candidate_index in np.flatnonzero(~eligible):
        footprint = constraint.domain.footprint(candidates[candidate_index])
        if not _has_overlap(footprint, obstacles):
            eligible[candidate_index] = True
    return np.flatnonzero(eligible).astype(np.int64)


def _forward_check_rectangle_pack(
    constraints,
    obstacles,
    preferred_centers,
    candidate_limit=None,
    max_states=250000,
    time_limit=20.0,
):
    """Pack rectangle candidates with MRV and least-constraining propagation."""
    ordered = sorted(constraints, key=lambda item: item.refdes)
    if not ordered or not all(
        _is_axis_aligned_rectangle(constraint.domain.footprint_local)
        for constraint in ordered
    ) or not all(_is_axis_aligned_rectangle(obstacle) for obstacle in obstacles):
        return None, {"applicable": False}

    obstacle_bounds = [obstacle.bounds for obstacle in obstacles]
    candidates = []
    candidate_bounds = []
    for constraint in ordered:
        all_candidates = constraint.domain.valid_centers
        all_bounds = _candidate_bounds(constraint, all_candidates)
        overlap_counts, _ = _bbox_overlap_metrics(all_bounds, obstacle_bounds)
        available = np.flatnonzero(overlap_counts == 0)
        if not len(available):
            return None, {
                "applicable": True,
                "proven_infeasible": True,
                "reason": "%s has no obstacle-free candidate" % constraint.refdes,
            }
        preferred = np.asarray(
            preferred_centers.get(constraint.node_id, constraint.target_center)
        )
        distances = np.square(all_candidates[available] - preferred).sum(axis=1)
        candidate_order = np.lexsort((available, distances))
        if candidate_limit is not None:
            candidate_order = candidate_order[:candidate_limit]
        available = available[candidate_order]
        candidates.append(all_candidates[available])
        candidate_bounds.append(all_bounds[available])

    symmetry_predecessor = {}
    if candidate_limit is None:
        footprint_classes = defaultdict(list)
        for index, constraint in enumerate(ordered):
            footprint_classes[
                tuple(
                    round(value, 6)
                    for value in constraint.domain.footprint_local.bounds
                )
            ].append(index)
        for members in footprint_classes.values():
            if len(members) < 2:
                continue
            reference = candidates[members[0]][
                np.lexsort(
                    (
                        candidates[members[0]][:, 1],
                        candidates[members[0]][:, 0],
                    )
                )
            ]
            if not all(
                np.array_equal(
                    reference,
                    candidates[index][
                        np.lexsort(
                            (
                                candidates[index][:, 1],
                                candidates[index][:, 0],
                            )
                        )
                    ],
                )
                for index in members[1:]
            ):
                continue
            for previous, current in zip(members, members[1:]):
                symmetry_predecessor[current] = previous

    conflict_matrices = {}
    for first_index, first_bounds in enumerate(candidate_bounds):
        for second_index in range(first_index + 1, len(candidate_bounds)):
            second_bounds = candidate_bounds[second_index]
            overlap_x = np.maximum(
                0.0,
                np.minimum(
                    first_bounds[:, None, 2], second_bounds[None, :, 2]
                )
                - np.maximum(
                    first_bounds[:, None, 0], second_bounds[None, :, 0]
                ),
            )
            overlap_y = np.maximum(
                0.0,
                np.minimum(
                    first_bounds[:, None, 3], second_bounds[None, :, 3]
                )
                - np.maximum(
                    first_bounds[:, None, 1], second_bounds[None, :, 1]
                ),
            )
            conflict_matrices[(first_index, second_index)] = (
                overlap_x * overlap_y > 1e-12
            )

    domains = [np.ones(len(rows), dtype=bool) for rows in candidates]
    assigned = {}
    states = 0
    propagation_prunes = 0
    timed_out = False
    state_limit_reached = False
    started = time.perf_counter()

    def conflicts_with(candidate_index, first_index, second_index):
        if first_index < second_index:
            return conflict_matrices[(first_index, second_index)][
                candidate_index, :
            ]
        return conflict_matrices[(second_index, first_index)][
            :, candidate_index
        ]

    def oriented_conflicts(first_index, second_index):
        if first_index < second_index:
            return conflict_matrices[(first_index, second_index)]
        return conflict_matrices[(second_index, first_index)].T

    def propagate(unassigned):
        nonlocal propagation_prunes, timed_out
        changed = True
        while changed:
            if time.perf_counter() - started >= time_limit:
                timed_out = True
                return False
            changed = False
            for first_index in unassigned:
                for second_index in unassigned:
                    if first_index == second_index:
                        continue
                    matrix = oriented_conflicts(first_index, second_index)
                    support = np.any(
                        ~matrix[:, domains[second_index]], axis=1
                    )
                    new_domain = domains[first_index] & support
                    removed = int(
                        np.count_nonzero(domains[first_index])
                        - np.count_nonzero(new_domain)
                    )
                    if removed:
                        domains[first_index] = new_domain
                        propagation_prunes += removed
                        changed = True
                        if not np.any(new_domain):
                            return False
        return True

    def candidate_impacts(variable_index, unassigned):
        impacts = np.zeros(len(candidates[variable_index]), dtype=np.int64)
        for other_index in unassigned:
            if other_index == variable_index:
                continue
            if variable_index < other_index:
                matrix = conflict_matrices[(variable_index, other_index)]
                impacts += np.count_nonzero(
                    matrix[:, domains[other_index]], axis=1
                )
            else:
                matrix = conflict_matrices[(other_index, variable_index)]
                impacts += np.count_nonzero(
                    matrix[domains[other_index], :], axis=0
                )
        return impacts

    def visit():
        nonlocal states, state_limit_reached, timed_out
        if len(assigned) == len(ordered):
            return True
        if states >= max_states:
            state_limit_reached = True
            return False
        if time.perf_counter() - started >= time_limit:
            timed_out = True
            return False
        unassigned = [
            index for index in range(len(ordered)) if index not in assigned
        ]
        eligible = [
            index
            for index in unassigned
            if symmetry_predecessor.get(index) not in unassigned
        ]
        variable_index = min(
            eligible,
            key=lambda index: (
                int(np.count_nonzero(domains[index])),
                -ordered[index].domain.footprint_local.area,
                ordered[index].refdes,
            ),
        )
        remaining = np.flatnonzero(domains[variable_index])
        impacts = candidate_impacts(variable_index, unassigned)
        candidate_order = remaining[
            np.lexsort((remaining, impacts[remaining]))
        ]
        for candidate_index in candidate_order:
            states += 1
            assigned[variable_index] = int(candidate_index)
            snapshot = [domain.copy() for domain in domains]
            feasible = True
            for other_index in unassigned:
                if other_index == variable_index:
                    continue
                new_domain = domains[other_index] & ~conflicts_with(
                    candidate_index, variable_index, other_index
                )
                if symmetry_predecessor.get(other_index) == variable_index:
                    selected_center = candidates[variable_index][candidate_index]
                    other_centers = candidates[other_index]
                    canonical_after = (
                        other_centers[:, 0] > selected_center[0] + 1e-12
                    ) | (
                        np.isclose(
                            other_centers[:, 0],
                            selected_center[0],
                            atol=1e-12,
                            rtol=0.0,
                        )
                        & (other_centers[:, 1] > selected_center[1] + 1e-12)
                    )
                    new_domain &= canonical_after
                domains[other_index] = new_domain
                if not np.any(new_domain):
                    feasible = False
                    break
            remaining_unassigned = [
                index for index in unassigned if index != variable_index
            ]
            if feasible:
                feasible = propagate(remaining_unassigned)
            if feasible and visit():
                return True
            domains[:] = snapshot
            assigned.pop(variable_index, None)
            if timed_out or state_limit_reached:
                return False
        return False

    initial_unassigned = list(range(len(ordered)))
    success = propagate(initial_unassigned) and visit()
    stats = {
        "applicable": True,
        "candidate_limit": candidate_limit,
        "candidate_count": sum(len(rows) for rows in candidates),
        "conflict_pair_count": sum(
            int(np.count_nonzero(matrix))
            for matrix in conflict_matrices.values()
        ),
        "states": states,
        "propagation_prunes": propagation_prunes,
        "symmetry_constraint_count": len(symmetry_predecessor),
        "elapsed_seconds": time.perf_counter() - started,
        "timed_out": timed_out,
        "state_limit_reached": state_limit_reached,
        "proven_infeasible": (
            candidate_limit is None
            and not success
            and not timed_out
            and not state_limit_reached
        ),
    }
    if not success:
        return None, stats
    placements = {
        constraint.node_id: candidates[index][assigned[index]]
        for index, constraint in enumerate(ordered)
    }
    footprints = []
    for constraint in ordered:
        footprint = constraint.domain.footprint(placements[constraint.node_id])
        if _has_overlap(footprint, list(obstacles) + footprints):
            raise RuntimeError(
                "forward-check packing produced an overlap for %s"
                % constraint.refdes
            )
        footprints.append(footprint)
    return placements, stats


def _min_conflicts_pack(
    constraints,
    obstacles,
    preferred_centers,
    restart_count=8,
    max_steps=2500,
    exact_candidate_limit=48,
    random_walk_probability=0.0,
    breakout_probability=0.0,
):
    if not 0.0 <= random_walk_probability <= 1.0:
        raise ValueError(
            "random-walk probability must be between zero and one"
        )
    if not 0.0 <= breakout_probability <= 1.0:
        raise ValueError(
            "breakout probability must be between zero and one"
        )
    ordered = _ordered_constraints(constraints, "largest_area")
    seed_material = "|".join(item.refdes for item in ordered).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    obstacle_bounds = [row.bounds for row in obstacles]
    rectangle_fast_path = all(
        _is_axis_aligned_rectangle(constraint.domain.footprint_local)
        for constraint in ordered
    ) and all(_is_axis_aligned_rectangle(obstacle) for obstacle in obstacles)
    restart_summaries = []
    eligible_indices = {
        constraint.node_id: _obstacle_free_candidate_indices(
            constraint, obstacles
        )
        for constraint in ordered
    }
    eligible_candidate_counts = {
        constraint.refdes: len(eligible_indices[constraint.node_id])
        for constraint in ordered
    }
    empty_refdes = [
        constraint.refdes
        for constraint in ordered
        if not len(eligible_indices[constraint.node_id])
    ]
    if empty_refdes:
        return None, {
            "restart_count": 0,
            "max_steps": max_steps,
            "seed": seed,
            "random_walk_probability": random_walk_probability,
            "breakout_probability": breakout_probability,
            "obstacle_infeasible_refdes": empty_refdes,
            "restart_summaries": [],
        }

    for restart in range(restart_count):
        placements = {}
        placement_indices = {}
        footprints = {}
        for constraint in ordered:
            candidates = constraint.domain.valid_centers
            eligible = eligible_indices[constraint.node_id]
            if restart == 0:
                preferred = np.asarray(
                    preferred_centers.get(
                        constraint.node_id, constraint.target_center
                    )
                )
                candidate_index = int(
                    eligible[
                        np.argmin(
                            np.square(candidates[eligible] - preferred).sum(
                                axis=1
                            )
                        )
                    ]
                )
            else:
                candidate_index = int(
                    eligible[int(rng.integers(len(eligible)))]
                )
            center = candidates[candidate_index]
            placements[constraint.node_id] = center
            placement_indices[constraint.node_id] = candidate_index
            footprints[constraint.node_id] = constraint.domain.footprint(center)

        conflicts, obstacle_metrics, pair_areas = _initialize_conflicts(
            ordered, footprints, obstacles
        )
        best_key = None
        best_step = 0
        best_candidate_indices = None
        best_obstacle_conflicts = None
        best_component_conflicts = None
        random_walk_steps = 0
        breakout_steps = 0
        for step in range(max_steps):
            conflicted = [
                item for item in ordered if conflicts[item.node_id][0] > 0
            ]
            incident_count = sum(row[0] for row in conflicts.values())
            incident_area = sum(row[1] for row in conflicts.values())
            key = (len(conflicted), incident_count, incident_area)
            if best_key is None or key < best_key:
                best_key = key
                best_step = step
                best_candidate_indices = {
                    item.refdes: int(placement_indices[item.node_id])
                    for item in ordered
                }
                best_obstacle_conflicts = [
                    {
                        "refdes": item.refdes,
                        "count": obstacle_metrics[item.node_id][0],
                        "area": obstacle_metrics[item.node_id][1],
                    }
                    for item in ordered
                    if obstacle_metrics[item.node_id][0]
                ]
                refdes_by_node = {
                    item.node_id: item.refdes for item in ordered
                }
                best_component_conflicts = [
                    {
                        "first_refdes": refdes_by_node[first_id],
                        "second_refdes": refdes_by_node[second_id],
                        "area": area,
                    }
                    for (first_id, second_id), area in sorted(
                        pair_areas.items()
                    )
                    if area
                ]
            if not conflicted:
                return placements, {
                    "restart": restart,
                    "steps": step,
                    "seed": seed,
                    "random_walk_probability": random_walk_probability,
                    "random_walk_steps": random_walk_steps,
                    "breakout_probability": breakout_probability,
                    "breakout_steps": breakout_steps,
                    "obstacle_eligible_candidate_counts": (
                        eligible_candidate_counts
                    ),
                    "restart_summaries": restart_summaries,
                }
            conflicted.sort(
                key=lambda item: (
                    -conflicts[item.node_id][0],
                    -conflicts[item.node_id][1],
                    item.refdes,
                )
            )
            breakout = bool(
                breakout_probability
                and rng.random() < breakout_probability
            )
            if breakout:
                constraint = ordered[int(rng.integers(len(ordered)))]
                breakout_steps += 1
            else:
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
            bbox_counts, bbox_scores = _bbox_overlap_metrics(
                _candidate_bounds(constraint, candidates), other_bounds
            )
            preferred = np.asarray(
                preferred_centers.get(node_id, constraint.target_center)
            )
            distances = np.square(candidates - preferred).sum(axis=1)
            eligible = eligible_indices[node_id]
            bbox_free = eligible[bbox_counts[eligible] == 0]
            bbox_free = bbox_free[
                bbox_free != placement_indices[node_id]
            ]
            if len(bbox_free):
                candidate_index = int(
                    bbox_free[int(rng.integers(len(bbox_free)))]
                    if breakout
                    else bbox_free[np.argmin(distances[bbox_free])]
                )
                center = candidates[candidate_index]
                placements[node_id] = center
                placement_indices[node_id] = candidate_index
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

            if rectangle_fast_path:
                best_count = int(np.min(bbox_counts[eligible]))
                best_area = float(
                    np.min(
                        bbox_scores[eligible][
                            bbox_counts[eligible] == best_count
                        ]
                    )
                )
                ties = eligible[
                    (bbox_counts[eligible] == best_count)
                    & np.isclose(
                        bbox_scores[eligible],
                        best_area,
                        atol=1e-12,
                        rtol=0.0,
                    )
                ]
                tie_order = np.lexsort((ties, distances[ties]))
                ties = ties[tie_order[:8]]
                alternatives = ties[
                    ties != placement_indices[node_id]
                ]
                if len(alternatives):
                    ties = alternatives
                candidate_index = int(ties[int(rng.integers(len(ties)))])
                center = candidates[candidate_index]
                placements[node_id] = center
                placement_indices[node_id] = candidate_index
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

            candidate_order = eligible[
                np.lexsort((distances[eligible], bbox_scores[eligible]))
            ]
            pool = list(candidate_order[:exact_candidate_limit])
            if len(eligible) > exact_candidate_limit:
                pool.extend(
                    int(index)
                    for index in rng.choice(
                        eligible,
                        size=min(16, len(eligible)),
                        replace=False,
                    )
                )
            pool = [
                candidate_index
                for candidate_index in dict.fromkeys(pool)
                if candidate_index != placement_indices[node_id]
            ]
            if not pool:
                continue
            pool_footprints = [
                constraint.domain.footprint(candidates[candidate_index])
                for candidate_index in pool
            ]
            exact_counts, exact_areas = _batch_overlap_metrics(
                pool_footprints, other_footprints
            )
            scored = []
            for pool_index, (candidate_index, footprint) in enumerate(
                zip(pool, pool_footprints)
            ):
                center = candidates[candidate_index]
                scored.append(
                    (
                        int(exact_counts[pool_index]),
                        float(exact_areas[pool_index]),
                        bbox_scores[candidate_index],
                        distances[candidate_index],
                        candidate_index,
                        footprint,
                    )
            )
            scored.sort(key=lambda row: row[:5])
            random_walk = bool(
                random_walk_probability
                and rng.random() < random_walk_probability
            )
            if breakout or random_walk:
                selected = scored[int(rng.integers(len(scored)))]
                random_walk_steps += int(random_walk)
            else:
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
            placement_indices[node_id] = candidate_index
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
        restart_summaries.append(
            {
                "restart": restart,
                "best_step": best_step,
                "best_conflicted_node_count": best_key[0],
                "best_conflict_incident_count": best_key[1],
                "best_conflict_incident_area": best_key[2],
                "best_candidate_indices": best_candidate_indices,
                "best_obstacle_conflicts": best_obstacle_conflicts,
                "best_component_conflicts": best_component_conflicts,
                "final_conflicted_node_count": remaining,
                "random_walk_steps": random_walk_steps,
                "breakout_steps": breakout_steps,
            }
        )
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
        "random_walk_probability": random_walk_probability,
        "breakout_probability": breakout_probability,
        "obstacle_eligible_candidate_counts": eligible_candidate_counts,
        "restart_summaries": restart_summaries,
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
    forward_check_trials = []
    for candidate_limit in (32, 64):
        repaired, forward_check_stats = _forward_check_rectangle_pack(
            constraints,
            obstacles,
            preferred_centers,
            candidate_limit=candidate_limit,
            max_states=25000,
            time_limit=2.0,
        )
        forward_check_trials.append(forward_check_stats)
        if repaired is not None:
            return repaired, dict(
                forward_check_stats,
                ordering="forward_check",
                candidate_order="mrv_least_constraining",
                backtracking_states=forward_check_stats["states"],
            )
        if not forward_check_stats.get("applicable"):
            break
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
        "bounded packing exhausted deterministic strategies: "
        "forward_check=%s greedy=%s" % (forward_check_trials, failures)
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
        frozen_anchor_ids,
        frozen_fixed_ids,
        anchor_centers,
        resolved_members,
        input_paths,
        endpoint_policy,
        endpoint_records,
        domain_cache_stats,
        preprocessing_seconds,
        num_nodes,
        output_dir,
        projection_enabled,
        anchor_loss_enabled,
        soft_loss_enabled,
        exact_repair_enabled,
        initialization_mode,
        grid,
        keepin_margin,
        keepin_margin_tau,
        require_feasible_density_target=False,
    ):
        self.config = config
        self.geometry = geometry
        self.alignment = alignment
        self.regions = regions
        self.constraints = tuple(constraints)
        self.frozen_lower_left = dict(frozen_lower_left)
        self.frozen_anchor_ids = frozenset(frozen_anchor_ids)
        self.frozen_fixed_ids = frozenset(frozen_fixed_ids)
        self.anchor_centers = dict(anchor_centers)
        self.resolved_members = tuple(resolved_members)
        self.input_paths = dict(input_paths)
        self.endpoint_policy = dict(endpoint_policy)
        self.endpoint_records = tuple(endpoint_records)
        self.domain_cache_stats = dict(domain_cache_stats)
        self.timing = {
            "preprocessing_seconds": float(preprocessing_seconds),
            "cache_load_seconds": float(
                self.domain_cache_stats.get("load_seconds", 0.0)
            ),
            "domain_build_seconds": float(
                self.domain_cache_stats.get("build_seconds", 0.0)
            ),
            "cache_write_seconds": float(
                self.domain_cache_stats.get("write_seconds", 0.0)
            ),
            "initialization_seconds": 0.0,
            "gpu_optimization_seconds": 0.0,
            "exact_validation_seconds": 0.0,
            "bounded_repair_seconds": 0.0,
            "serialization_seconds": 0.0,
            "native_scoring_seconds": 0.0,
            "collision_preprocessing_seconds": 0.0,
        }
        self.num_nodes = int(num_nodes)
        self.output_dir = Path(output_dir)
        self.projection_enabled = bool(projection_enabled)
        self.anchor_loss_enabled = bool(anchor_loss_enabled)
        self.soft_loss_enabled = bool(soft_loss_enabled)
        self.exact_repair_enabled = bool(exact_repair_enabled)
        self.initialization_mode = str(initialization_mode)
        self.grid = float(grid)
        self.keepin_margin = float(keepin_margin)
        self.keepin_margin_tau = float(keepin_margin_tau)
        self.require_feasible_density_target = bool(
            require_feasible_density_target
        )
        self._density_capacity_cache = {}
        self._physical_footprint_local_cache = {}
        self._anchor_necessary_domain_cache = {}
        self.collision_barrier_diagnostics = None
        self.initial_legal_centers = {}
        self.projector = RegionProjector(
            num_nodes=self.num_nodes,
            constraints=self.constraints,
            frozen_lower_left=self.frozen_lower_left,
            enabled=self.projection_enabled,
        )

    @classmethod
    def from_params(cls, params, placedb, runtime_position=None):
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
        initialization_mode = str(
            getattr(params, "anchor_keepin_initialization", "anchor")
        ).lower()
        initialization_alias = {
            "anchor": "legacy_pack_all",
            "current": "legacy_pack_all_current",
        }
        initialization_mode = initialization_alias.get(
            initialization_mode, initialization_mode
        )
        valid_initialization_modes = {
            "legacy_pack_all",
            "legacy_pack_all_current",
            "preserve_legal",
            "project_illegal",
            "checkpoint_warm_start",
        }
        if initialization_mode not in valid_initialization_modes:
            raise ValueError(
                "anchor_keepin_initialization must be one of %s"
                % sorted(valid_initialization_modes)
            )
        if (
            initialization_mode == "checkpoint_warm_start"
            and not getattr(params, "initial_placement_file", "")
        ):
            raise ValueError(
                "checkpoint_warm_start requires initial_placement_file"
            )

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
        endpoint_config = config.get("endpoint_policy")
        anchor_refdes = {cluster.anchor_refdes for cluster in clusters}
        (
            default_endpoint_source,
            manual_endpoints,
            runtime_endpoints,
        ) = _parse_endpoint_policy(
            endpoint_config,
            anchor_refdes,
        )

        manual_path_value = endpoint_config.get("manual_placement_file")
        runtime_path_value = endpoint_config.get("runtime_placement_file")
        if not isinstance(manual_path_value, str) or not manual_path_value:
            raise ValueError("manual endpoint placement file is required")
        if not isinstance(runtime_path_value, str) or not runtime_path_value:
            raise ValueError("runtime endpoint placement file is required")
        manual_path = _resolve_path(config_path, manual_path_value)
        runtime_path = _resolve_path(config_path, runtime_path_value)
        manual_positions = _load_placement_source(manual_path, placedb)
        runtime_positions = _load_placement_source(runtime_path, placedb)
        if runtime_position is None:
            raise ValueError("runtime_position is required for endpoint resolution")
        runtime_source_audit = _audit_runtime_source(
            runtime_positions, runtime_position, placedb
        )
        logging.info(
            "runtime source audit: %d/%d coordinates preserve sub-mm detail; "
            "max native parser delta %.6g mm",
            runtime_source_audit["quantized_component_count"],
            runtime_source_audit["physical_component_count"],
            runtime_source_audit["max_abs_delta_mm"],
        )
        endpoint_policy = {
            "default": default_endpoint_source,
            "manual_endpoints": sorted(manual_endpoints),
            "runtime_endpoints": sorted(runtime_endpoints),
            "manual_placement_file": str(manual_path),
            "runtime_placement_file": str(runtime_path),
            "runtime_endpoint_model": "geometry_aligned_to_native_placedb",
            "runtime_source_audit": runtime_source_audit,
        }
        target_centers = _native_alignment_targets(runtime_position, placedb)
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
        runtime_aligned_positions = {}
        for node_id, name in enumerate(names[: placedb.num_physical_nodes]):
            center = alignment.transform_point(geometry.symbols[name].center_mm)
            runtime_aligned_positions[name] = (
                center[0] - float(placedb.node_size_x[node_id]) / 2,
                center[1] - float(placedb.node_size_y[node_id]) / 2,
            )
        logging.info(
            "anchor/keep-in preflight: alignment completed in %.3fs",
            time.perf_counter() - alignment_started,
        )

        grid_mm = float(getattr(params, "constraint_grid_mm", 0.1))
        clearance_mm = float(getattr(params, "keepin_clearance_mm", 0.0))
        keepin_margin_mm = float(getattr(params, "keepin_margin_mm", 0.1))
        keepin_margin_tau_mm = float(
            getattr(params, "keepin_margin_tau_mm", 0.05)
        )
        if keepin_margin_mm < 0:
            raise ValueError("keepin_margin_mm must be non-negative")
        if keepin_margin_tau_mm <= 0:
            raise ValueError("keepin_margin_tau_mm must be positive")
        grid = grid_mm * abs(alignment.scale)
        clearance = clearance_mm * abs(alignment.scale)
        keepin_margin = keepin_margin_mm * abs(alignment.scale)
        keepin_margin_tau = keepin_margin_tau_mm * abs(alignment.scale)
        input_paths = {
            "geometry": geometry_path,
            "clusters": cluster_path,
            "assignments": assignment_path,
            "manual_endpoint_placement": manual_path,
            "runtime_endpoint_placement": runtime_path,
        }
        input_hashes = {
            name: _sha256(path) for name, path in input_paths.items()
        }
        endpoint_policy.update(
            {
                "manual_placement_sha256": input_hashes[
                    "manual_endpoint_placement"
                ],
                "runtime_placement_sha256": input_hashes[
                    "runtime_endpoint_placement"
                ],
                "runtime_geometry_sha256": input_hashes["geometry"],
            }
        )
        cache_endpoint_policy = {
            "default": default_endpoint_source,
            "manual_endpoints": sorted(manual_endpoints),
            "runtime_endpoints": sorted(runtime_endpoints),
            "manual_sha256": input_hashes["manual_endpoint_placement"],
            "runtime_sha256": input_hashes["runtime_endpoint_placement"],
        }
        cache_dir_value = str(
            getattr(params, "feasible_domain_cache_dir", "") or ""
        )
        domain_cache_dir = (
            Path(cache_dir_value).expanduser().resolve()
            if cache_dir_value
            else None
        )
        domain_cache_stats = {
            "enabled": domain_cache_dir is not None,
            "directory": (
                str(domain_cache_dir) if domain_cache_dir is not None else None
            ),
            "hits": 0,
            "misses": 0,
            "load_seconds": 0.0,
            "build_seconds": 0.0,
            "write_seconds": 0.0,
            "schema": _DOMAIN_CACHE_SCHEMA,
        }
        domain_cache = {}
        constraints = []
        frozen_lower_left = {}
        frozen_anchor_ids = set()
        frozen_fixed_ids = set()
        anchor_centers = {}
        resolved_members = []
        infeasible = []
        constrained_nodes = set()
        domain_started = time.perf_counter()
        domain_count = 0
        logging.info("anchor/keep-in preflight: constructing feasible domains")

        endpoint_records = []
        for refdes in sorted(anchor_refdes):
            if refdes not in name_to_id:
                raise KeyError("cluster anchor missing from Cypress nodes: %s" % refdes)
            node_id = name_to_id[refdes]
            source = "manual" if refdes in manual_endpoints else "runtime"
            source_positions = (
                manual_positions
                if source == "manual"
                else runtime_aligned_positions
            )
            lower_left = source_positions[refdes]
            center = (
                lower_left[0] + float(placedb.node_size_x[node_id]) / 2,
                lower_left[1] + float(placedb.node_size_y[node_id]) / 2,
            )
            anchor_centers[refdes] = center
            endpoint_records.append(
                {
                    "refdes": refdes,
                    "source": source,
                    "source_key": (
                        "manual_endpoint_placement"
                        if source == "manual"
                        else "runtime_geometry_alignment"
                    ),
                    "source_path": str(
                        manual_path if source == "manual" else geometry_path
                    ),
                    "source_sha256": (
                        input_hashes["manual_endpoint_placement"]
                        if source == "manual"
                        else input_hashes["geometry"]
                    ),
                    "identity_audit_path": (
                        None if source == "manual" else str(runtime_path)
                    ),
                    "identity_audit_sha256": (
                        None
                        if source == "manual"
                        else input_hashes["runtime_endpoint_placement"]
                    ),
                    "lower_left": list(lower_left),
                    "center": list(center),
                }
            )
            if (
                getattr(params, "freeze_anchor_nodes", True)
                and node_id < placedb.num_movable_nodes
            ):
                frozen_lower_left[node_id] = lower_left
                frozen_anchor_ids.add(node_id)

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
                cache_key = _domain_cache_digest(
                    input_hashes=input_hashes,
                    endpoint_policy=cache_endpoint_policy,
                    side=subgroup.side,
                    region_id=assignment.region_id,
                    region=region,
                    width=footprint_width,
                    height=footprint_height,
                    grid=grid,
                    clearance=clearance,
                    orientation=orientation,
                    footprint_local=footprint_local,
                )
                if cache_key not in domain_cache:
                    cache_path = (
                        domain_cache_dir / (cache_key + ".npz")
                        if domain_cache_dir is not None
                        else None
                    )
                    if cache_path is not None and cache_path.exists():
                        cache_started = time.perf_counter()
                        domain_cache[cache_key] = _load_cached_domain(
                            cache_path,
                            cache_key,
                            region,
                            footprint_width,
                            footprint_height,
                            clearance,
                            grid,
                            footprint_local,
                        )
                        domain_cache_stats["load_seconds"] += (
                            time.perf_counter() - cache_started
                        )
                        domain_cache_stats["hits"] += 1
                    else:
                        domain_cache_stats["misses"] += 1
                        build_started = time.perf_counter()
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
                        domain_cache_stats["build_seconds"] += (
                            time.perf_counter() - build_started
                        )
                        if cache_path is not None:
                            write_started = time.perf_counter()
                            _write_cached_domain(
                                cache_path,
                                cache_key,
                                domain_cache[cache_key],
                            )
                            domain_cache_stats["write_seconds"] += (
                                time.perf_counter() - write_started
                            )
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

        fixed_components = config.get("fixed_components", [])
        if not isinstance(fixed_components, list) or any(
            not isinstance(refdes, str) or not refdes for refdes in fixed_components
        ):
            raise ValueError("fixed_components must be a list of non-empty refdes")
        if len(fixed_components) != len(set(fixed_components)):
            raise ValueError("fixed_components contains duplicate refdes")
        clustered_refdes = set(resolved_members)
        for refdes in sorted(fixed_components):
            if refdes in clustered_refdes:
                raise ValueError("fixed component is also clustered: %s" % refdes)
            if refdes not in name_to_id or refdes not in geometry.symbols:
                raise KeyError("fixed component missing from M336 inputs: %s" % refdes)
            node_id = name_to_id[refdes]
            if node_id >= placedb.num_physical_nodes:
                raise ValueError("fixed component is not physical: %s" % refdes)
            if node_id < placedb.num_movable_nodes:
                frozen_lower_left[node_id] = runtime_aligned_positions[refdes]
                frozen_fixed_ids.add(node_id)
        logging.info(
            "anchor/keep-in preflight: resolved %d domains in %.3fs",
            domain_count,
            time.perf_counter() - domain_started,
        )
        domain_cache_stats["unique_domain_count"] = len(domain_cache)
        domain_cache_stats["constraint_count"] = domain_count

        output_dir = config.get("reporting", {}).get("output_dir", "results")
        context = cls(
            config=config,
            geometry=geometry,
            alignment=alignment,
            regions=transformed_regions,
            constraints=constraints,
            frozen_lower_left=frozen_lower_left,
            frozen_anchor_ids=frozen_anchor_ids,
            frozen_fixed_ids=frozen_fixed_ids,
            anchor_centers=anchor_centers,
            resolved_members=resolved_members,
            input_paths=input_paths,
            endpoint_policy=endpoint_policy,
            endpoint_records=endpoint_records,
            domain_cache_stats=domain_cache_stats,
            preprocessing_seconds=time.perf_counter() - preflight_started,
            num_nodes=placedb.num_nodes,
            output_dir=output_dir,
            projection_enabled=getattr(params, "keepin_projection_flag", False),
            anchor_loss_enabled=getattr(params, "anchor_loss_flag", False),
            soft_loss_enabled=getattr(params, "keepin_soft_loss_flag", False),
            exact_repair_enabled=getattr(params, "exact_repair_flag", False),
            initialization_mode=initialization_mode,
            grid=grid,
            keepin_margin=keepin_margin,
            keepin_margin_tau=keepin_margin_tau,
            require_feasible_density_target=getattr(
                params,
                "irregular_density_require_feasible_target",
                False,
            ),
        )
        context.write_preflight(infeasible)
        return context

    def _anchor_necessary_center_domain(self, constraint):
        """Build an optimistic center set from necessary vertex containment."""
        cache_key = id(constraint.domain)
        cached = self._anchor_necessary_domain_cache.get(cache_key)
        if cached is not None:
            return cached

        vertices = _geometry_boundary_vertices(
            constraint.domain.footprint_local
        )
        if not vertices:
            raise ValueError(
                "component footprint has no boundary vertices: %s"
                % constraint.refdes
            )
        necessary_domain = None
        for offset_x, offset_y in vertices:
            shifted_region = affinity.translate(
                constraint.domain.region,
                xoff=-offset_x,
                yoff=-offset_y,
            )
            necessary_domain = (
                shifted_region
                if necessary_domain is None
                else necessary_domain.intersection(shifted_region)
            )
        if necessary_domain.is_empty:
            raise InfeasibleDomainError(
                "footprint vertex necessary domain is empty: %s"
                % constraint.refdes
            )
        cached = (necessary_domain, len(vertices))
        self._anchor_necessary_domain_cache[cache_key] = cached
        return cached

    def anchor_feasible_lower_bound_report(
        self, constraints=None, current_centers=None
    ):
        """Report independent physical-anchor floors without changing placement."""
        active_constraints = (
            self.constraints if constraints is None else tuple(constraints)
        )
        current_centers = current_centers or {}
        scale = abs(self.alignment.scale)
        rows = []
        lower_bounds = []
        lower_bounds_mm = []
        current_slack = []
        current_slack_mm = []
        for constraint in sorted(active_constraints, key=lambda row: row.refdes):
            anchor_center = self.anchor_centers.get(constraint.anchor_refdes)
            if anchor_center is None:
                continue
            necessary_domain, vertex_count = (
                self._anchor_necessary_center_domain(constraint)
            )
            lower_bound = float(
                necessary_domain.distance(Point(anchor_center))
            )
            target_witness = math.hypot(
                constraint.target_center[0] - anchor_center[0],
                constraint.target_center[1] - anchor_center[1],
            )
            row = {
                "refdes": constraint.refdes,
                "anchor_refdes": constraint.anchor_refdes,
                "side": constraint.side,
                "group_id": constraint.group_id,
                "subgroup_id": constraint.subgroup_id,
                "region_id": constraint.region_id,
                "necessary_vertex_count": vertex_count,
                "lower_bound": lower_bound,
                "lower_bound_mm": lower_bound / scale,
                "projected_target_witness": target_witness,
                "projected_target_witness_mm": target_witness / scale,
            }
            center = current_centers.get(constraint.node_id)
            if center is not None:
                current_distance = math.hypot(
                    center[0] - anchor_center[0],
                    center[1] - anchor_center[1],
                )
                slack = max(current_distance - lower_bound, 0.0)
                row.update(
                    {
                        "current_anchor_distance": current_distance,
                        "current_anchor_distance_mm": current_distance / scale,
                        "current_distance_above_lower_bound": slack,
                        "current_distance_above_lower_bound_mm": slack / scale,
                    }
                )
                current_slack.append(slack)
                current_slack_mm.append(slack / scale)
            rows.append(row)
            lower_bounds.append(lower_bound)
            lower_bounds_mm.append(lower_bound / scale)

        report = {
            "model": {
                "name": "footprint_vertex_necessary_center_domain",
                "optimistic": True,
                "independent_components": True,
                "continuous_coordinates": True,
                "guarantee": (
                    "lower bound for every exactly contained center in the "
                    "assigned keep-in"
                ),
                "relaxations": [
                    (
                        "tests footprint boundary vertices rather than every "
                        "edge point"
                    ),
                    "ignores component collisions",
                    "ignores density and wirelength objectives",
                    "ignores lattice quantization",
                ],
            },
            "distance": _distance_distribution(lower_bounds),
            "distance_mm": _distance_distribution(lower_bounds_mm),
            "per_component": rows,
        }
        if current_centers:
            report["current_distance_above_lower_bound"] = (
                _distance_distribution(current_slack)
            )
            report["current_distance_above_lower_bound_mm"] = (
                _distance_distribution(current_slack_mm)
            )
        return report

    def write_preflight(self, infeasible):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.alignment.dump(self.output_dir / "input_alignment.json")
        report = {
            "resolved_member_count": len(set(self.resolved_members)),
            "movable_non_anchor_constraint_count": len(self.constraints),
            "frozen_anchor_count": len(self.frozen_anchor_ids),
            "frozen_fixed_obstacle_count": len(self.frozen_fixed_ids),
            "infeasible_domains": infeasible,
            "input_sha256": {
                name: _sha256(path) for name, path in self.input_paths.items()
            },
            "input_paths": {
                name: str(path) for name, path in self.input_paths.items()
            },
            "endpoint_policy": self.endpoint_policy,
            "resolved_endpoints": list(self.endpoint_records),
            "domain_cache": self.domain_cache_stats,
            "timing": dict(self.timing),
            "alignment": self.alignment.to_dict(),
            "anchor_feasible_lower_bound": (
                self.anchor_feasible_lower_bound_report()
            ),
            "keepin_margin_mm": self.keepin_margin / abs(self.alignment.scale),
            "keepin_margin_tau_mm": self.keepin_margin_tau
            / abs(self.alignment.scale),
        }
        with (self.output_dir / "preflight.json").open("w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")

    @staticmethod
    def _position_value(value):
        if torch.is_tensor(value):
            return float(value.detach().cpu())
        return float(value)

    def _node_lower_left(self, position, node_id):
        return (
            self._position_value(position[node_id]),
            self._position_value(position[self.num_nodes + node_id]),
        )

    def _constraint_center(self, position, constraint):
        lower_left = self._node_lower_left(position, constraint.node_id)
        return (
            lower_left[0] + constraint.node_width / 2,
            lower_left[1] + constraint.node_height / 2,
        )

    def _set_constraint_center(self, position, constraint, center):
        position[constraint.node_id] = center[0] - constraint.node_width / 2
        position[self.num_nodes + constraint.node_id] = (
            center[1] - constraint.node_height / 2
        )

    def _physical_footprint_local(self, placedb, node_id):
        names = placedb.node_names
        refdes = _decode_name(names[node_id])
        if refdes not in self.geometry.symbols:
            return box(
                -float(placedb.node_size_x[node_id]) / 2,
                -float(placedb.node_size_y[node_id]) / 2,
                float(placedb.node_size_x[node_id]) / 2,
                float(placedb.node_size_y[node_id]) / 2,
            )
        if node_id not in self._physical_footprint_local_cache:
            symbol = self.geometry.symbols[refdes]
            source_center = self.alignment.transform_point(symbol.center_mm)
            transformed = self.alignment.transform_geometry(symbol.footprint_mm)
            self._physical_footprint_local_cache[node_id] = affinity.translate(
                transformed,
                xoff=-source_center[0],
                yoff=-source_center[1],
            )
        return self._physical_footprint_local_cache[node_id]

    def _physical_footprint(self, position, placedb, node_id):
        lower_left = self._node_lower_left(position, node_id)
        center = (
            lower_left[0] + float(placedb.node_size_x[node_id]) / 2,
            lower_left[1] + float(placedb.node_size_y[node_id]) / 2,
        )
        return affinity.translate(
            self._physical_footprint_local(placedb, node_id),
            xoff=center[0],
            yoff=center[1],
        )

    def _position_audit(self, position, placedb):
        """Return exact invalid/conflicting nodes using side-local STRtrees."""
        epsilon = float(
            self.config.get("reporting", {}).get("area_epsilon_mm2", 1e-5)
        ) * abs(self.alignment.scale) ** 2
        constraints_by_id = {
            constraint.node_id: constraint for constraint in self.constraints
        }
        constrained_rows = {"TOP": [], "BOTTOM": []}
        keepin_invalid = set()
        for constraint in self.constraints:
            footprint = constraint.domain.footprint(
                self._constraint_center(position, constraint)
            )
            constrained_rows[constraint.side].append((constraint, footprint))
            if footprint.difference(self.regions[constraint.region_id]).area > epsilon:
                keepin_invalid.add(constraint.node_id)

        fixed_rows = {"TOP": [], "BOTTOM": []}
        for node_id in range(placedb.num_physical_nodes):
            if node_id in constraints_by_id:
                continue
            side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            fixed_rows[side].append(
                (
                    node_id,
                    _decode_name(placedb.node_names[node_id]),
                    self._physical_footprint(position, placedb, node_id),
                )
            )

        fixed_conflicts = []
        pair_conflicts = []
        repair_ids = set(keepin_invalid)
        for side in ("TOP", "BOTTOM"):
            fixed_shapes = [row[2] for row in fixed_rows[side]]
            fixed_tree = shapely.STRtree(fixed_shapes) if fixed_shapes else None
            for constraint, footprint in constrained_rows[side]:
                if fixed_tree is not None:
                    for fixed_index in fixed_tree.query(footprint):
                        fixed_row = fixed_rows[side][int(fixed_index)]
                        area = footprint.intersection(fixed_row[2]).area
                        if area <= epsilon:
                            continue
                        repair_ids.add(constraint.node_id)
                        fixed_conflicts.append(
                            {
                                "refdes": constraint.refdes,
                                "fixed_refdes": fixed_row[1],
                                "overlap_area": float(area),
                            }
                        )

            rows = constrained_rows[side]
            shapes = [row[1] for row in rows]
            tree = shapely.STRtree(shapes) if shapes else None
            if tree is None:
                continue
            for first_index, (first, footprint) in enumerate(rows):
                for second_index in tree.query(footprint):
                    second_index = int(second_index)
                    if second_index <= first_index:
                        continue
                    second, second_footprint = rows[second_index]
                    area = footprint.intersection(second_footprint).area
                    if area <= epsilon:
                        continue
                    repair_ids.update((first.node_id, second.node_id))
                    pair_conflicts.append(
                        {
                            "first_refdes": first.refdes,
                            "second_refdes": second.refdes,
                            "overlap_area": float(area),
                        }
                    )

        id_to_refdes = {
            constraint.node_id: constraint.refdes
            for constraint in self.constraints
        }
        report = {
            "keepin_invalid_count": len(keepin_invalid),
            "keepin_invalid_refdes": [
                id_to_refdes[node_id] for node_id in sorted(keepin_invalid)
            ],
            "fixed_overlap_count": len(fixed_conflicts),
            "fixed_overlaps": fixed_conflicts,
            "constrained_overlap_count": len(pair_conflicts),
            "constrained_overlaps": pair_conflicts,
            "conflict_closure_count": len(repair_ids),
            "conflict_closure_refdes": [
                id_to_refdes[node_id] for node_id in sorted(repair_ids)
            ],
        }
        return report, repair_ids

    def exact_overlap_report(self, position, placedb):
        """Return lightweight exact collision metrics for optimizer diagnostics."""
        audit, _ = self._position_audit(position, placedb)
        scale_squared = abs(self.alignment.scale) ** 2
        fixed_area = sum(row["overlap_area"] for row in audit["fixed_overlaps"])
        constrained_area = sum(
            row["overlap_area"] for row in audit["constrained_overlaps"]
        )
        return {
            "keepin_violation_count": audit["keepin_invalid_count"],
            "fixed_overlap_count": audit["fixed_overlap_count"],
            "fixed_overlap_area_mm2": fixed_area / scale_squared,
            "constrained_overlap_count": audit["constrained_overlap_count"],
            "constrained_overlap_area_mm2": constrained_area / scale_squared,
            "overlap_pair_count": (
                audit["fixed_overlap_count"]
                + audit["constrained_overlap_count"]
            ),
            "overlap_area_mm2": (fixed_area + constrained_area) / scale_squared,
            "conflict_closure_count": audit["conflict_closure_count"],
        }

    def _pack_constraint_subset(
        self,
        position,
        placedb,
        repair_ids,
        prefer_current=True,
    ):
        repair_ids = set(repair_ids)
        constraints_by_id = {
            constraint.node_id: constraint for constraint in self.constraints
        }
        occupied = {"TOP": [], "BOTTOM": []}
        for node_id in range(placedb.num_physical_nodes):
            if node_id in repair_ids:
                continue
            constraint = constraints_by_id.get(node_id)
            if constraint is not None:
                occupied[constraint.side].append(
                    constraint.domain.footprint(
                        self._constraint_center(position, constraint)
                    )
                )
            else:
                side = "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
                occupied[side].append(
                    self._physical_footprint(position, placedb, node_id)
                )

        constraints_by_region = defaultdict(list)
        for node_id in sorted(repair_ids):
            constraint = constraints_by_id[node_id]
            constraints_by_region[(constraint.side, constraint.region_id)].append(
                constraint
            )

        placements = {}
        packing_stats = []
        original_centers = {
            node_id: self._constraint_center(position, constraints_by_id[node_id])
            for node_id in repair_ids
        }
        for (side, region_id), region_constraints in sorted(
            constraints_by_region.items()
        ):
            preferred_centers = None
            if prefer_current:
                preferred_centers = {
                    constraint.node_id: constraint.domain.project(
                        original_centers[constraint.node_id]
                    )[0]
                    for constraint in region_constraints
                }
            started = time.perf_counter()
            region_placements, stats = _pack_region(
                region_constraints,
                occupied[side],
                preferred_centers=preferred_centers,
            )
            elapsed = time.perf_counter() - started
            placements.update(region_placements)
            occupied[side].extend(
                constraint.domain.footprint(
                    region_placements[constraint.node_id]
                )
                for constraint in region_constraints
            )
            packing_stats.append(
                dict(
                    stats,
                    side=side,
                    region_id=region_id,
                    component_count=len(region_constraints),
                    elapsed_seconds=elapsed,
                )
            )

        moved_distances = []
        moved_refdes = []
        for node_id in sorted(repair_ids):
            constraint = constraints_by_id[node_id]
            selected = placements[node_id]
            distance = float(
                np.linalg.norm(np.subtract(selected, original_centers[node_id]))
            )
            moved_distances.append(distance)
            if distance > 1e-9:
                moved_refdes.append(constraint.refdes)
            self._set_constraint_center(position, constraint, selected)
        return {
            "component_count": len(repair_ids),
            "moved_component_count": len(moved_refdes),
            "moved_refdes": moved_refdes,
            "mean_displacement": (
                float(np.mean(moved_distances)) if moved_distances else 0.0
            ),
            "max_displacement": (
                float(np.max(moved_distances)) if moved_distances else 0.0
            ),
            "regions": packing_stats,
        }

    def write_timing(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with (self.output_dir / "timing.json").open("w") as stream:
            json.dump(self.timing, stream, indent=2, sort_keys=True)
            stream.write("\n")

    def initialize_positions(self, position, placedb):
        """Preserve exact-legal coordinates and repair only conflict closure."""
        started = time.perf_counter()
        endpoint_moved_refdes = []
        names = [_decode_name(name) for name in placedb.node_names]
        for node_id, lower_left in self.frozen_lower_left.items():
            current = self._node_lower_left(position, node_id)
            if max(
                abs(current[axis] - lower_left[axis]) for axis in (0, 1)
            ) > 1e-4:
                endpoint_moved_refdes.append(names[node_id])
            position[node_id] = lower_left[0]
            position[self.num_nodes + node_id] = lower_left[1]

        before, repair_ids = self._position_audit(position, placedb)
        projected_refdes = []
        touched_constraint_ids = set()
        if self.projection_enabled:
            if self.initialization_mode == "project_illegal":
                constraints_by_refdes = {
                    constraint.refdes: constraint
                    for constraint in self.constraints
                }
                for refdes in before["keepin_invalid_refdes"]:
                    constraint = constraints_by_refdes[refdes]
                    projected = constraint.domain.project(
                        self._constraint_center(position, constraint)
                    )[0]
                    self._set_constraint_center(position, constraint, projected)
                    projected_refdes.append(refdes)
                    touched_constraint_ids.add(constraint.node_id)
                _, repair_ids = self._position_audit(position, placedb)

            if self.initialization_mode in {
                "legacy_pack_all",
                "legacy_pack_all_current",
            }:
                repair_ids = {
                    constraint.node_id for constraint in self.constraints
                }
                prefer_current = (
                    self.initialization_mode == "legacy_pack_all_current"
                    or not self.anchor_loss_enabled
                )
            else:
                prefer_current = True
            touched_constraint_ids.update(repair_ids)
            repair_stats = self._pack_constraint_subset(
                position,
                placedb,
                repair_ids,
                prefer_current=prefer_current,
            )
        else:
            repair_stats = {
                "component_count": 0,
                "moved_component_count": 0,
                "moved_refdes": [],
                "mean_displacement": 0.0,
                "max_displacement": 0.0,
                "regions": [],
            }

        after, _ = self._position_audit(position, placedb)
        if self.projection_enabled and (
            after["keepin_invalid_count"]
            or after["fixed_overlap_count"]
            or after["constrained_overlap_count"]
        ):
            raise RuntimeError(
                "bounded initialization failed exact legality: %s" % after
            )
        if not (
            after["keepin_invalid_count"]
            or after["fixed_overlap_count"]
            or after["constrained_overlap_count"]
        ):
            self.initial_legal_centers = {
                constraint.node_id: self._constraint_center(position, constraint)
                for constraint in self.constraints
            }
        self.timing["initialization_seconds"] = (
            time.perf_counter() - started
        )
        report = {
            "schema": "m336_initialization_v2",
            "mode": self.initialization_mode,
            "endpoint_moved_count": len(endpoint_moved_refdes),
            "endpoint_moved_refdes": sorted(endpoint_moved_refdes),
            "projected_refdes": sorted(projected_refdes),
            "before": before,
            "after": after,
            "preserved_component_count": len(self.constraints)
            - len(touched_constraint_ids),
            "repair": repair_stats,
            "timing": dict(self.timing),
        }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with (self.output_dir / "initialization.json").open("w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        self.write_timing()

    def build_density_capacity_maps(
        self,
        placedb,
        num_bins_x,
        num_bins_y,
        target_density,
        dtype,
        device,
    ):
        """Build cached, side-isolated static occupancy for unusable space."""
        from dreamplace.constraints.irregular_density import (
            build_side_capacity_maps,
        )

        key = (
            float(placedb.xl),
            float(placedb.yl),
            float(placedb.xh),
            float(placedb.yh),
            int(num_bins_x),
            int(num_bins_y),
            float(target_density),
            str(dtype),
            str(device),
        )
        if key in self._density_capacity_cache:
            return self._density_capacity_cache[key], True

        if placedb.num_filler_nodes:
            raise ValueError(
                "irregular density does not support filler nodes"
            )
        constrained_ids = {constraint.node_id for constraint in self.constraints}
        frozen_ids = set(self.frozen_lower_left)
        overlap = sorted(constrained_ids & frozen_ids)
        if overlap:
            raise ValueError(
                "irregular density nodes cannot be constrained and frozen: %s"
                % overlap
            )
        unclassified = sorted(
            set(range(placedb.num_movable_nodes))
            - constrained_ids
            - frozen_ids
        )
        if unclassified:
            raise ValueError(
                "irregular density requires every movable node to be "
                "constrained or frozen: %s" % unclassified
            )

        regions_by_side = {"top": [], "btm": []}
        for region_id, polygon in self.regions.items():
            geometry_side = self.geometry.regions[region_id].side
            if geometry_side not in {"TOP", "BOTTOM"}:
                raise ValueError(
                    "unsupported density-capacity side: %s" % geometry_side
                )
            side = "top" if geometry_side == "TOP" else "btm"
            regions_by_side[side].append(polygon)
        obstacles_by_side = {"top": [], "btm": []}
        movable_ids_by_side = {"top": [], "btm": []}
        for node_id in sorted(constrained_ids):
            side = "top" if placedb.node_side_flag[node_id] else "btm"
            movable_ids_by_side[side].append(node_id)
        for node_id in range(placedb.num_physical_nodes):
            if node_id in constrained_ids:
                continue
            side = "top" if placedb.node_side_flag[node_id] else "btm"
            lower_left = self.frozen_lower_left.get(
                node_id,
                (placedb.node_x[node_id], placedb.node_y[node_id]),
            )
            obstacles_by_side[side].append(
                box(
                    float(lower_left[0]),
                    float(lower_left[1]),
                    float(lower_left[0] + placedb.node_size_x[node_id]),
                    float(lower_left[1] + placedb.node_size_y[node_id]),
                )
            )
        capacity_maps = build_side_capacity_maps(
            regions_by_side=regions_by_side,
            obstacles_by_side=obstacles_by_side,
            bounds=(placedb.xl, placedb.yl, placedb.xh, placedb.yh),
            num_bins_x=num_bins_x,
            num_bins_y=num_bins_y,
            target_density=target_density,
            dtype=dtype,
            device=device,
        )
        infeasible_sides = []
        for side in ("top", "btm"):
            node_ids = torch.as_tensor(
                movable_ids_by_side[side],
                dtype=torch.long,
                device=device,
            )
            movable_area = sum(
                float(placedb.node_size_x[node_id])
                * float(placedb.node_size_y[node_id])
                for node_id in movable_ids_by_side[side]
            )
            diagnostics = capacity_maps[side]["diagnostics"]
            diagnostics["movable_node_count"] = int(node_ids.numel())
            diagnostics["movable_area"] = movable_area
            usable_area = diagnostics["raster_usable_area"]
            raw_utilization = (
                movable_area / usable_area if usable_area else float("inf")
            )
            capacity_area = usable_area * float(target_density)
            unavoidable_overflow = max(0.0, movable_area - capacity_area)
            diagnostics["raw_area_utilization"] = raw_utilization
            diagnostics["target_density_feasible"] = bool(
                raw_utilization <= float(target_density) + 1e-12
            )
            diagnostics["unavoidable_area_overflow"] = (
                unavoidable_overflow
            )
            diagnostics["minimum_normalized_overflow"] = (
                unavoidable_overflow / capacity_area
                if capacity_area
                else (0.0 if not movable_area else float("inf"))
            )
            if not diagnostics["target_density_feasible"]:
                infeasible_sides.append(
                    (side, diagnostics["raw_area_utilization"])
                )
                logging.warning(
                    "irregular density target %.6f is below %s usable-area "
                    "utilization %.6f",
                    target_density,
                    side,
                    raw_utilization,
                )
            capacity_maps[side]["movable_node_ids"] = node_ids
        if (
            getattr(self, "require_feasible_density_target", False)
            and infeasible_sides
        ):
            details = ", ".join(
                "%s utilization %.6f" % item for item in infeasible_sides
            )
            raise ValueError(
                "irregular density target %.6f is infeasible: %s"
                % (target_density, details)
            )
        self._density_capacity_cache[key] = capacity_maps
        return capacity_maps, False

    def build_anchor_loss(self, data_collections, placedb):
        active_constraints = [
            constraint
            for constraint in self.constraints
            if constraint.node_id < placedb.num_movable_nodes
            and constraint.node_id not in self.frozen_lower_left
        ]
        node_ids = [constraint.node_id for constraint in active_constraints]
        targets = [constraint.target_center for constraint in active_constraints]
        subgroup_ids = [
            constraint.subgroup_id for constraint in active_constraints
        ]
        diagonal = math.hypot(placedb.xh - placedb.xl, placedb.yh - placedb.yl)
        loss = AnchorKeepInLoss(
            node_ids=node_ids,
            target_centers=targets,
            node_size_x=data_collections.node_size_x,
            node_size_y=data_collections.node_size_y,
            num_nodes=placedb.num_nodes,
            board_diagonal=diagonal,
            group_ids=subgroup_ids,
        ).to(data_collections.pos[0].device)
        logging.info(
            "anchor loss: %d active nodes in %d side-specific subgroups",
            len(active_constraints),
            len(loss.group_labels),
        )
        return loss

    def build_soft_loss(self, data_collections, placedb):
        loss = SoftKeepInLoss(
            constraints=self.constraints,
            num_nodes=placedb.num_nodes,
            margin=self.keepin_margin,
            tau=self.keepin_margin_tau,
            dtype=data_collections.pos[0].dtype,
        )
        scale = abs(self.alignment.scale)
        logging.info(
            "soft keep-in interior margin = %.6g mm, tau = %.6g mm, "
            "%d cached distance fields",
            self.keepin_margin / scale,
            self.keepin_margin_tau / scale,
            len(loss.distance_fields),
        )
        return loss

    def build_collision_loss(self, data_collections, placedb, params):
        started = time.perf_counter()
        constraints_by_id = {
            constraint.node_id: constraint for constraint in self.constraints
        }
        active_node_ids = [
            constraint.node_id
            for constraint in self.constraints
            if constraint.node_id < placedb.num_movable_nodes
            and constraint.node_id not in self.frozen_lower_left
        ]
        footprints = {
            node_id: (
                constraints_by_id[node_id].domain.footprint_local
                if node_id in constraints_by_id
                else self._physical_footprint_local(placedb, node_id)
            )
            for node_id in range(placedb.num_physical_nodes)
        }
        node_sides = {
            node_id: (
                "TOP" if placedb.node_side_flag[node_id] else "BOTTOM"
            )
            for node_id in range(placedb.num_physical_nodes)
        }
        scale = abs(self.alignment.scale)
        margin = float(getattr(params, "collision_margin_mm", 0.0)) * scale
        tau = float(getattr(params, "collision_tau_mm", 0.025)) * scale
        data, diagnostics = _build_footprint_collision_data(
            footprints=footprints,
            node_sides=node_sides,
            active_node_ids=active_node_ids,
            num_physical_nodes=placedb.num_physical_nodes,
            grid=self.grid,
            margin=margin,
            tau=tau,
        )
        loss = FootprintCollisionLoss(
            node_size_x=data_collections.node_size_x,
            node_size_y=data_collections.node_size_y,
            num_nodes=placedb.num_nodes,
            **data,
        ).to(data_collections.pos[0].device)
        elapsed = time.perf_counter() - started
        diagnostics.update(
            {
                "build_seconds": elapsed,
                "grid_mm": self.grid / scale,
                "raster_guard_mm": self.grid / (2 * scale),
                "margin_mm": margin / scale,
                "tau_mm": tau / scale,
            }
        )
        self.collision_barrier_diagnostics = diagnostics
        self.timing["collision_preprocessing_seconds"] = elapsed
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with (self.output_dir / "collision_barrier.json").open("w") as stream:
            json.dump(diagnostics, stream, indent=2, sort_keys=True)
            stream.write("\n")
        self.write_timing()
        logging.info(
            "footprint collision barrier: %s",
            json.dumps(diagnostics, sort_keys=True),
        )
        return loss

    def zero_frozen_gradients(self, gradient):
        if gradient is None or not self.frozen_lower_left:
            return
        node_ids = list(self.frozen_lower_left)
        gradient[node_ids] = 0
        gradient[[self.num_nodes + node_id for node_id in node_ids]] = 0

    def _restore_initial_legal_subset(self, position, placedb, repair_ids):
        """Try the same run's legal initialization before discrete repacking."""
        initial_repair_ids = set(repair_ids)
        restore_ids = set(initial_repair_ids)
        missing = sorted(restore_ids - self.initial_legal_centers.keys())
        if missing:
            return None, {
                "reason": "missing_initial_legal_coordinates",
                "missing_node_ids": missing,
            }

        constraints_by_id = {
            constraint.node_id: constraint for constraint in self.constraints
        }
        proposal_centers = {
            node_id: self._constraint_center(
                position, constraints_by_id[node_id]
            )
            for node_id in constraints_by_id
        }
        repair_config = self.config.get("repair", {})
        max_components = int(repair_config.get("max_restore_components", 64))
        max_rounds = int(repair_config.get("max_restore_rounds", 4))
        if max_components <= 0 or max_rounds <= 0:
            raise ValueError("restore component and round limits must be positive")

        audit = None
        expansions = []
        failure = None
        for round_index in range(1, max_rounds + 1):
            for node_id in sorted(restore_ids):
                self._set_constraint_center(
                    position,
                    constraints_by_id[node_id],
                    self.initial_legal_centers[node_id],
                )
            audit, remaining_ids = self._position_audit(position, placedb)
            if not remaining_ids:
                break
            expansion = set(remaining_ids) - restore_ids
            if not expansion:
                failure = {
                    "reason": "restore_made_no_progress",
                    "round": round_index,
                    "remaining_conflict_closure_refdes": audit[
                        "conflict_closure_refdes"
                    ],
                }
                break
            if len(restore_ids | expansion) > max_components:
                failure = {
                    "reason": "restore_component_limit",
                    "round": round_index,
                    "max_restore_components": max_components,
                    "proposed_component_count": len(restore_ids | expansion),
                    "remaining_conflict_closure_refdes": audit[
                        "conflict_closure_refdes"
                    ],
                }
                break
            restore_ids.update(expansion)
            expansions.append(
                {
                    "round": round_index,
                    "added_node_ids": sorted(expansion),
                    "added_refdes": sorted(
                        constraints_by_id[node_id].refdes
                        for node_id in expansion
                    ),
                }
            )
        else:
            failure = {
                "reason": "restore_round_limit",
                "max_restore_rounds": max_rounds,
                "remaining_conflict_closure_refdes": audit[
                    "conflict_closure_refdes"
                ],
            }

        if failure is not None:
            for node_id in sorted(restore_ids):
                self._set_constraint_center(
                    position,
                    constraints_by_id[node_id],
                    proposal_centers[node_id],
                )
            failure["initial_component_count"] = len(initial_repair_ids)
            failure["expanded_component_count"] = len(restore_ids)
            failure["expansions"] = expansions
            return None, failure

        moved_distances = {
            node_id: float(
                np.linalg.norm(
                    np.subtract(
                        self.initial_legal_centers[node_id],
                        proposal_centers[node_id],
                    )
                )
            )
            for node_id in restore_ids
        }
        moved_refdes = [
            constraints_by_id[node_id].refdes
            for node_id in sorted(restore_ids)
            if moved_distances[node_id] > 1e-9
        ]
        return {
            "strategy": "initial_legal_restore",
            "component_count": len(restore_ids),
            "initial_component_count": len(initial_repair_ids),
            "expanded_component_count": len(restore_ids),
            "expansions": expansions,
            "restore_round_count": len(expansions) + 1,
            "max_restore_components": max_components,
            "max_restore_rounds": max_rounds,
            "moved_component_count": len(moved_refdes),
            "moved_refdes": moved_refdes,
            "mean_displacement": (
                float(np.mean(list(moved_distances.values())))
                if moved_distances
                else 0.0
            ),
            "max_displacement": (
                float(np.max(list(moved_distances.values())))
                if moved_distances
                else 0.0
            ),
            "regions": [],
            "restore_audit": audit,
        }, None

    def repair_positions(self, pos, placedb):
        """Repair only the exact illegal/conflicting component closure."""
        started = time.perf_counter()
        before, repair_ids = self._position_audit(pos, placedb)
        with torch.no_grad():
            stats, restore_failure = self._restore_initial_legal_subset(
                pos, placedb, repair_ids
            )
            if stats is None:
                stats = self._pack_constraint_subset(
                    pos,
                    placedb,
                    repair_ids,
                    prefer_current=True,
                )
                stats["strategy"] = "bounded_pack"
                stats["restore_failure"] = restore_failure
            self.projector(pos)
        after, _ = self._position_audit(pos, placedb)
        if (
            after["keepin_invalid_count"]
            or after["fixed_overlap_count"]
            or after["constrained_overlap_count"]
        ):
            raise RuntimeError("bounded repair failed exact legality: %s" % after)
        elapsed = time.perf_counter() - started
        self.timing["bounded_repair_seconds"] += elapsed
        self.write_timing()
        stats.update(
            {
                "bounded_conflict_closure": True,
                "before": before,
                "after": after,
                "elapsed_seconds": elapsed,
            }
        )
        return stats

    def exact_report(self, pos, placedb, constraints=None):
        active_constraints = (
            self.constraints if constraints is None else tuple(constraints)
        )
        constrained = []
        for constraint in active_constraints:
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
        constrained_ids = {
            constraint.node_id for constraint in active_constraints
        }
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
        report["anchor_feasible_lower_bound"] = (
            self.anchor_feasible_lower_bound_report(
                active_constraints,
                {
                    constraint.node_id: component.center
                    for constraint, component in zip(
                        active_constraints, constrained
                    )
                },
            )
        )
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
            "%d frozen fixed obstacles, alignment max residual %.6g mm",
            len(self.constraints),
            len(self.frozen_anchor_ids),
            len(self.frozen_fixed_ids),
            self.alignment.max_residual_mm,
        )
