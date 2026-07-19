#!/usr/bin/env python3
"""Run deterministic exact-legal local site descent for M336."""

from __future__ import annotations

import argparse
import copy
import json
import os
import time
from argparse import Namespace
from pathlib import Path

for thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[thread_variable] = "1"

import numpy as np
import torch
from shapely import affinity

from analyze_quality_bound import _load_context
from dreamplace.constraints.anchor_keepin import (
    _obstacle_free_candidate_indices,
)
from probe_exact_site_cpsat import (
    acceptance_overlap_mask,
    load_guide,
    write_json_atomic,
    write_placement_atomic,
)
from score_exact_site_result import _result_positions
from solve_discrete_placement import _fixed_footprint_local


ROOT = Path(__file__).resolve().parents[3]
BASELINE_RESULT = (
    ROOT
    / "results/m336/baseline_warmstart_smoke/baseline/baseline-result.json"
)
PLACEMENT_SIDES = ("TOP", "BOTTOM")


def _node_incident_nets(placedb, controlled_ids):
    result = {node_id: set() for node_id in controlled_ids}
    for net_id, pins in enumerate(placedb.net2pin_map):
        for pin_id in pins:
            node_id = int(placedb.pin2node_map[pin_id])
            if node_id in result:
                result[node_id].add(net_id)
    return result


def _candidate_total_hpwl(
    placedb,
    constraint,
    centers,
    node_x,
    node_y,
    incident_nets,
    current_hpwl,
):
    candidate_incident_hpwl = np.zeros(len(centers), dtype=np.float64)
    current_incident_hpwl = 0.0
    node_lower_x = centers[:, 0] - constraint.node_width / 2
    node_lower_y = centers[:, 1] - constraint.node_height / 2
    for net_id in sorted(incident_nets):
        pins = placedb.net2pin_map[net_id]
        moving_pins = [
            pin_id
            for pin_id in pins
            if int(placedb.pin2node_map[pin_id]) == constraint.node_id
        ]
        fixed_pins = [
            pin_id
            for pin_id in pins
            if int(placedb.pin2node_map[pin_id]) != constraint.node_id
        ]
        moving_x = node_lower_x[:, None] + np.asarray(
            [placedb.pin_offset_x[pin_id] for pin_id in moving_pins],
            dtype=np.float64,
        )
        moving_y = node_lower_y[:, None] + np.asarray(
            [placedb.pin_offset_y[pin_id] for pin_id in moving_pins],
            dtype=np.float64,
        )
        maximum_x = moving_x.max(axis=1)
        minimum_x = moving_x.min(axis=1)
        maximum_y = moving_y.max(axis=1)
        minimum_y = moving_y.min(axis=1)
        if fixed_pins:
            fixed_pin_x = np.asarray(
                [
                    node_x[int(placedb.pin2node_map[pin_id])]
                    + placedb.pin_offset_x[pin_id]
                    for pin_id in fixed_pins
                ],
                dtype=np.float64,
            )
            fixed_pin_y = np.asarray(
                [
                    node_y[int(placedb.pin2node_map[pin_id])]
                    + placedb.pin_offset_y[pin_id]
                    for pin_id in fixed_pins
                ],
                dtype=np.float64,
            )
            maximum_x = np.maximum(maximum_x, fixed_pin_x.max())
            minimum_x = np.minimum(minimum_x, fixed_pin_x.min())
            maximum_y = np.maximum(maximum_y, fixed_pin_y.max())
            minimum_y = np.minimum(minimum_y, fixed_pin_y.min())
        weight = float(placedb.net_weights[net_id])
        candidate_incident_hpwl += weight * (
            maximum_x - minimum_x + maximum_y - minimum_y
        )
        current_incident_hpwl += float(
            placedb.net_hpwl(node_x, node_y, net_id)
        )
    return current_hpwl - current_incident_hpwl + candidate_incident_hpwl


def _legal_candidate_mask(
    constraint,
    centers,
    side_constraints,
    current_centers,
    area_epsilon,
):
    legal = np.ones(len(centers), dtype=bool)
    for other in side_constraints:
        if other.node_id == constraint.node_id:
            continue
        other_center = current_centers[other.refdes]
        legal &= ~acceptance_overlap_mask(
            constraint.domain.footprint_local,
            other.domain.footprint_local,
            centers[:, 0] - other_center[0],
            centers[:, 1] - other_center[1],
            area_epsilon,
        )
        if not np.any(legal):
            break
    return legal


def _select_candidate(
    total_hpwl,
    legal,
    centers,
    current_center,
    current_hpwl,
    guide_center,
    improvement_tolerance,
    equality_tolerance,
    guide_tolerance,
):
    legal_indices = np.flatnonzero(legal)
    best_hpwl = float(np.min(total_hpwl[legal_indices]))
    if best_hpwl < current_hpwl - improvement_tolerance:
        tied = legal_indices[
            np.abs(total_hpwl[legal_indices] - best_hpwl)
            <= equality_tolerance
        ]
        if guide_center is None:
            return int(tied[0]), "strict"
        distance = np.square(centers[tied] - guide_center).sum(axis=1)
        return int(tied[np.lexsort((tied, distance))[0]]), "strict"
    if guide_center is None:
        return None, None
    plateau = legal_indices[
        np.abs(total_hpwl[legal_indices] - current_hpwl)
        <= equality_tolerance
    ]
    if not len(plateau):
        return None, None
    distance = np.square(centers[plateau] - guide_center).sum(axis=1)
    selected = int(plateau[np.lexsort((plateau, distance))[0]])
    current_distance = float(np.square(current_center - guide_center).sum())
    if (
        float(np.square(centers[selected] - guide_center).sum())
        >= current_distance - guide_tolerance
    ):
        return None, None
    return selected, "plateau"


def _select_guided_threshold_candidate(
    total_hpwl,
    legal,
    centers,
    current_center,
    current_hpwl,
    guide_center,
    hpwl_ceiling,
    region_candidate_indices,
    improvement_tolerance,
    equality_tolerance,
    guide_tolerance,
    site_tolerance,
    max_move_rise=None,
):
    """Select the cheapest legal move that progresses toward the guide."""
    guide_distance = np.square(centers - guide_center).sum(axis=1)
    current_guide_distance = float(
        np.square(current_center - guide_center).sum()
    )
    site_distance = np.square(centers - current_center).sum(axis=1)
    move_hpwl_ceiling = (
        np.inf
        if max_move_rise is None
        else current_hpwl + max_move_rise
    )
    eligible = np.flatnonzero(
        legal
        & (site_distance > site_tolerance**2)
        & (guide_distance < current_guide_distance - guide_tolerance)
        & (total_hpwl <= hpwl_ceiling + equality_tolerance)
        & (total_hpwl <= move_hpwl_ceiling + equality_tolerance)
    )
    if not len(eligible):
        return None, None
    best_hpwl = float(np.min(total_hpwl[eligible]))
    tied = eligible[
        np.abs(total_hpwl[eligible] - best_hpwl) <= equality_tolerance
    ]
    selected = int(
        tied[
            np.lexsort(
                (
                    region_candidate_indices[tied],
                    guide_distance[tied],
                )
            )[0]
        ]
    )
    selected_hpwl = float(total_hpwl[selected])
    if selected_hpwl < current_hpwl - improvement_tolerance:
        move_type = "strict"
    elif selected_hpwl > current_hpwl + equality_tolerance:
        move_type = "uphill"
    else:
        move_type = "plateau"
    return selected, move_type


def _escape_hold_refdes(
    escape_moves, current_centers, initial_centers, site_tolerance
):
    uphill_refdes = {
        move["refdes"]
        for move in escape_moves
        if move["move_type"] == "uphill"
    }
    return frozenset(
        refdes
        for refdes in uphill_refdes
        if float(
            np.linalg.norm(
                current_centers[refdes] - initial_centers[refdes]
            )
        )
        > site_tolerance
    )


def _escape_sweep_order(constraints, rng):
    if rng is None:
        return list(constraints)
    return [
        constraints[int(index)]
        for index in rng.permutation(len(constraints))
    ]


def _pair_total_hpwl(
    placedb,
    first,
    first_centers,
    second,
    second_centers,
    node_x,
    node_y,
    incident_nets,
    current_hpwl,
):
    current_incident_hpwl = sum(
        float(placedb.net_hpwl(node_x, node_y, net_id))
        for net_id in incident_nets
    )
    total = np.full(
        (len(first_centers), len(second_centers)),
        current_hpwl - current_incident_hpwl,
        dtype=np.float64,
    )
    first_lower_x = first_centers[:, 0] - first.node_width / 2
    first_lower_y = first_centers[:, 1] - first.node_height / 2
    second_lower_x = second_centers[:, 0] - second.node_width / 2
    second_lower_y = second_centers[:, 1] - second.node_height / 2
    for net_id in sorted(incident_nets):
        pins = placedb.net2pin_map[net_id]
        first_pins = [
            pin_id
            for pin_id in pins
            if int(placedb.pin2node_map[pin_id]) == first.node_id
        ]
        second_pins = [
            pin_id
            for pin_id in pins
            if int(placedb.pin2node_map[pin_id]) == second.node_id
        ]
        fixed_pins = [
            pin_id
            for pin_id in pins
            if int(placedb.pin2node_map[pin_id])
            not in (first.node_id, second.node_id)
        ]
        maximum_x = np.full(total.shape, -np.inf)
        minimum_x = np.full(total.shape, np.inf)
        maximum_y = np.full(total.shape, -np.inf)
        minimum_y = np.full(total.shape, np.inf)
        if first_pins:
            pin_x = first_lower_x[:, None] + np.asarray(
                [placedb.pin_offset_x[pin_id] for pin_id in first_pins]
            )
            pin_y = first_lower_y[:, None] + np.asarray(
                [placedb.pin_offset_y[pin_id] for pin_id in first_pins]
            )
            maximum_x = np.maximum(maximum_x, pin_x.max(axis=1)[:, None])
            minimum_x = np.minimum(minimum_x, pin_x.min(axis=1)[:, None])
            maximum_y = np.maximum(maximum_y, pin_y.max(axis=1)[:, None])
            minimum_y = np.minimum(minimum_y, pin_y.min(axis=1)[:, None])
        if second_pins:
            pin_x = second_lower_x[:, None] + np.asarray(
                [placedb.pin_offset_x[pin_id] for pin_id in second_pins]
            )
            pin_y = second_lower_y[:, None] + np.asarray(
                [placedb.pin_offset_y[pin_id] for pin_id in second_pins]
            )
            maximum_x = np.maximum(maximum_x, pin_x.max(axis=1)[None, :])
            minimum_x = np.minimum(minimum_x, pin_x.min(axis=1)[None, :])
            maximum_y = np.maximum(maximum_y, pin_y.max(axis=1)[None, :])
            minimum_y = np.minimum(minimum_y, pin_y.min(axis=1)[None, :])
        if fixed_pins:
            fixed_pin_x = np.asarray(
                [
                    node_x[int(placedb.pin2node_map[pin_id])]
                    + placedb.pin_offset_x[pin_id]
                    for pin_id in fixed_pins
                ]
            )
            fixed_pin_y = np.asarray(
                [
                    node_y[int(placedb.pin2node_map[pin_id])]
                    + placedb.pin_offset_y[pin_id]
                    for pin_id in fixed_pins
                ]
            )
            maximum_x = np.maximum(maximum_x, fixed_pin_x.max())
            minimum_x = np.minimum(minimum_x, fixed_pin_x.min())
            maximum_y = np.maximum(maximum_y, fixed_pin_y.max())
            minimum_y = np.minimum(minimum_y, fixed_pin_y.min())
        total += float(placedb.net_weights[net_id]) * (
            maximum_x - minimum_x + maximum_y - minimum_y
        )
    return total


def _candidate_blockers(
    constraints, candidate_rows, current_centers, area_epsilon
):
    constraint_indices = {
        constraint.refdes: index
        for index, constraint in enumerate(constraints)
    }
    blockers = {}
    for constraint in constraints:
        centers = candidate_rows[constraint.refdes]["centers"]
        count = np.zeros(len(centers), dtype=np.int16)
        single = np.full(len(centers), -1, dtype=np.int16)
        for other in constraints:
            if (
                other.side != constraint.side
                or other.node_id == constraint.node_id
            ):
                continue
            other_center = current_centers[other.refdes]
            conflicts = acceptance_overlap_mask(
                constraint.domain.footprint_local,
                other.domain.footprint_local,
                centers[:, 0] - other_center[0],
                centers[:, 1] - other_center[1],
                area_epsilon,
            )
            newly_blocked = conflicts & (count == 0)
            single[newly_blocked] = constraint_indices[other.refdes]
            count[conflicts] += 1
        blockers[constraint.refdes] = {
            "count": count,
            "single": single,
        }
    return blockers


def _best_pair_move(
    placedb,
    constraints,
    candidate_rows,
    current_centers,
    node_x,
    node_y,
    node_nets,
    current_hpwl,
    area_epsilon,
    improvement_tolerance,
    excluded_refdes=frozenset(),
):
    blockers = _candidate_blockers(
        constraints, candidate_rows, current_centers, area_epsilon
    )
    best = None
    evaluated_pairs = 0
    evaluated_combinations = 0
    for first_index, first in enumerate(constraints):
        if first.refdes in excluded_refdes:
            continue
        first_row = candidate_rows[first.refdes]
        first_blockers = blockers[first.refdes]
        for second_index in range(first_index + 1, len(constraints)):
            second = constraints[second_index]
            if second.refdes in excluded_refdes:
                continue
            second_row = candidate_rows[second.refdes]
            second_blockers = blockers[second.refdes]
            shared_nets = node_nets[first.node_id] & node_nets[second.node_id]
            same_side = first.side == second.side
            first_released = same_side and np.any(
                (first_blockers["count"] == 1)
                & (first_blockers["single"] == second_index)
            )
            second_released = same_side and np.any(
                (second_blockers["count"] == 1)
                & (second_blockers["single"] == first_index)
            )
            if not shared_nets and not first_released and not second_released:
                continue
            if same_side:
                first_mask = (first_blockers["count"] == 0) | (
                    (first_blockers["count"] == 1)
                    & (first_blockers["single"] == second_index)
                )
                second_mask = (second_blockers["count"] == 0) | (
                    (second_blockers["count"] == 1)
                    & (second_blockers["single"] == first_index)
                )
            else:
                first_mask = first_blockers["count"] == 0
                second_mask = second_blockers["count"] == 0
            first_candidates = np.flatnonzero(first_mask)
            second_candidates = np.flatnonzero(second_mask)
            first_centers = first_row["centers"][first_candidates]
            second_centers = second_row["centers"][second_candidates]
            legal_pair = np.ones(
                (len(first_candidates), len(second_candidates)), dtype=bool
            )
            if same_side:
                displacement_x = (
                    first_centers[:, None, 0]
                    - second_centers[None, :, 0]
                )
                displacement_y = (
                    first_centers[:, None, 1]
                    - second_centers[None, :, 1]
                )
                legal_pair &= ~acceptance_overlap_mask(
                    first.domain.footprint_local,
                    second.domain.footprint_local,
                    displacement_x.ravel(),
                    displacement_y.ravel(),
                    area_epsilon,
                ).reshape(displacement_x.shape)
            incident_nets = node_nets[first.node_id] | node_nets[second.node_id]
            total_hpwl = _pair_total_hpwl(
                placedb,
                first,
                first_centers,
                second,
                second_centers,
                node_x,
                node_y,
                incident_nets,
                current_hpwl,
            )
            total_hpwl[~legal_pair] = np.inf
            flat_index = int(np.argmin(total_hpwl))
            first_local, second_local = np.unravel_index(
                flat_index, total_hpwl.shape
            )
            candidate_hpwl = float(total_hpwl[first_local, second_local])
            evaluated_pairs += 1
            evaluated_combinations += int(total_hpwl.size)
            if candidate_hpwl >= current_hpwl - improvement_tolerance:
                continue
            first_candidate = int(first_candidates[first_local])
            second_candidate = int(second_candidates[second_local])
            candidate = {
                "first": first,
                "second": second,
                "first_candidate": first_candidate,
                "second_candidate": second_candidate,
                "first_center": first_row["centers"][first_candidate],
                "second_center": second_row["centers"][second_candidate],
                "first_region_candidate_index": int(
                    first_row["eligible"][first_candidate]
                ),
                "second_region_candidate_index": int(
                    second_row["eligible"][second_candidate]
                ),
                "hpwl": candidate_hpwl,
                "same_side": same_side,
                "shared_nets": sorted(shared_nets),
                "pair_candidate_count": int(total_hpwl.size),
                "legal_pair_count": int(np.count_nonzero(legal_pair)),
            }
            key = (
                candidate_hpwl,
                first.refdes,
                second.refdes,
                candidate["first_region_candidate_index"],
                candidate["second_region_candidate_index"],
            )
            if best is None or key < best["key"]:
                candidate["key"] = key
                best = candidate
    diagnostics = {
        "evaluated_pair_count": evaluated_pairs,
        "evaluated_combination_count": evaluated_combinations,
    }
    return best, diagnostics


def _fixed_obstacles(placedb, context, controlled_ids, node_x, node_y):
    obstacles = {side: [] for side in PLACEMENT_SIDES}
    for node_id in range(placedb.num_physical_nodes):
        if node_id in controlled_ids:
            continue
        side = "TOP" if bool(placedb.node_side_flag[node_id]) else "BOTTOM"
        footprint = _fixed_footprint_local(
            context, placedb, node_id, "decomposed"
        )
        obstacles[side].append(
            affinity.translate(
                footprint,
                xoff=float(node_x[node_id])
                + float(placedb.node_size_x[node_id]) / 2,
                yoff=float(node_y[node_id])
                + float(placedb.node_size_y[node_id]) / 2,
            )
        )
    return obstacles


def descend(args) -> dict:
    source = json.loads(args.source.read_text())
    context_args = Namespace(
        output_dir=args.output.parent / f".{args.output.stem}-context",
        assignment=Path(source["assignment_json"]),
        grid_mm=float(source["grid_mm"]),
        clearance_mm=0.0,
        bookshelf_dir=args.bookshelf_dir,
    )
    placedb, context = _load_context(context_args)
    node_x, node_y = _result_positions(
        source, placedb, context, args.bookshelf_dir
    )
    constraints = sorted(context.constraints, key=lambda row: row.refdes)
    constraints_by_side = {
        side: [row for row in constraints if row.side == side]
        for side in PLACEMENT_SIDES
    }
    controlled_ids = {constraint.node_id for constraint in constraints}
    node_nets = _node_incident_nets(placedb, controlled_ids)
    area_epsilon = float(
        context.config.get("reporting", {}).get(
            "area_epsilon_mm2", 1e-5
        )
    ) * abs(float(context.alignment.scale)) ** 2
    obstacles = _fixed_obstacles(
        placedb, context, controlled_ids, node_x, node_y
    )
    candidate_rows = {}
    total_candidate_count = 0
    for constraint in constraints:
        eligible = _obstacle_free_candidate_indices(
            constraint, obstacles[constraint.side]
        )
        centers = constraint.domain.valid_centers[eligible]
        if not len(centers):
            raise ValueError(f"no candidate sites for {constraint.refdes}")
        candidate_rows[constraint.refdes] = {
            "eligible": eligible,
            "centers": centers,
        }
        total_candidate_count += len(centers)

    selected_sites = {
        refdes: dict(row) for refdes, row in source["selected_sites"].items()
    }
    plateau_guide = (
        load_guide(args.plateau_guide) if args.plateau_guide else None
    )
    if plateau_guide is not None:
        expected_refdes = {constraint.refdes for constraint in constraints}
        if set(plateau_guide) != expected_refdes:
            raise ValueError("plateau guide component identities differ")
    current_centers = {
        refdes: np.asarray(row["center"], dtype=np.float64)
        for refdes, row in selected_sites.items()
    }
    for constraint in constraints:
        centers = candidate_rows[constraint.refdes]["centers"]
        distance = np.linalg.norm(
            centers - current_centers[constraint.refdes], axis=1
        )
        if float(distance.min()) > args.site_tolerance:
            raise ValueError(
                f"source is not an exact site for {constraint.refdes}"
            )

    initial_hpwl = float(placedb.hpwl(node_x, node_y))
    current_hpwl = initial_hpwl
    baseline = json.loads(BASELINE_RESULT.read_text())
    baseline_hpwl = float(baseline["metrics"]["hpwl"])
    baseline_rsmt = float(baseline["metrics"]["rsmt"])
    started = time.perf_counter()
    initial_node_x = node_x.copy()
    initial_node_y = node_y.copy()
    initial_centers = {
        refdes: center.copy() for refdes, center in current_centers.items()
    }
    initial_selected_sites = copy.deepcopy(selected_sites)
    escape_enabled = args.max_escape_sweeps > 0
    escape_hpwl_ceiling = initial_hpwl + args.escape_hpwl_budget
    escape_moves = []
    escape_order_rng = (
        np.random.default_rng(args.escape_order_seed)
        if args.escape_order_seed is not None
        else None
    )
    escape_sweep_orders = []
    completed_escape_sweeps = 0
    escape_peak_hpwl = initial_hpwl
    escape_stop_reason = "disabled"
    if escape_enabled:
        escape_stop_reason = "max_escape_sweeps"
        for escape_sweep in range(args.max_escape_sweeps):
            sweep_moves = 0
            strict_improvement = False
            sweep_constraints = _escape_sweep_order(
                constraints, escape_order_rng
            )
            escape_sweep_orders.append(
                [constraint.refdes for constraint in sweep_constraints]
            )
            for constraint in sweep_constraints:
                row = candidate_rows[constraint.refdes]
                centers = row["centers"]
                legal = _legal_candidate_mask(
                    constraint,
                    centers,
                    constraints_by_side[constraint.side],
                    current_centers,
                    area_epsilon,
                )
                total_hpwl = _candidate_total_hpwl(
                    placedb,
                    constraint,
                    centers,
                    node_x,
                    node_y,
                    node_nets[constraint.node_id],
                    current_hpwl,
                )
                guide_center = np.asarray(
                    plateau_guide[constraint.refdes], dtype=np.float64
                )
                selected, move_type = _select_guided_threshold_candidate(
                    total_hpwl,
                    legal,
                    centers,
                    current_centers[constraint.refdes],
                    current_hpwl,
                    guide_center,
                    escape_hpwl_ceiling,
                    row["eligible"],
                    args.improvement_tolerance,
                    args.equality_tolerance,
                    args.guide_tolerance,
                    args.site_tolerance,
                    args.max_escape_move_rise,
                )
                if selected is None:
                    continue
                old_center = current_centers[constraint.refdes].copy()
                new_center = centers[selected].copy()
                before_hpwl = current_hpwl
                predicted_hpwl = float(total_hpwl[selected])
                node_x[constraint.node_id] = (
                    new_center[0] - constraint.node_width / 2
                )
                node_y[constraint.node_id] = (
                    new_center[1] - constraint.node_height / 2
                )
                current_centers[constraint.refdes] = new_center
                current_hpwl = float(placedb.hpwl(node_x, node_y))
                if abs(current_hpwl - predicted_hpwl) > 1e-8:
                    raise ValueError(
                        "guided candidate HPWL replay failed for "
                        f"{constraint.refdes}"
                    )
                if current_hpwl > (
                    escape_hpwl_ceiling + args.equality_tolerance
                ):
                    raise ValueError("guided move exceeded HPWL ceiling")
                selected_sites[constraint.refdes] = {
                    "region_candidate_index": int(row["eligible"][selected]),
                    "center": new_center.tolist(),
                }
                escape_moves.append(
                    {
                        "sweep": escape_sweep,
                        "refdes": constraint.refdes,
                        "side": constraint.side,
                        "move_type": move_type,
                        "old_center": old_center.tolist(),
                        "new_center": new_center.tolist(),
                        "guide_distance_before": float(
                            np.linalg.norm(old_center - guide_center)
                        ),
                        "guide_distance_after": float(
                            np.linalg.norm(new_center - guide_center)
                        ),
                        "region_candidate_index": int(
                            row["eligible"][selected]
                        ),
                        "legal_candidate_count": int(
                            np.count_nonzero(legal)
                        ),
                        "hpwl_before": before_hpwl,
                        "hpwl_after": current_hpwl,
                        "hpwl_delta": current_hpwl - before_hpwl,
                    }
                )
                escape_peak_hpwl = max(escape_peak_hpwl, current_hpwl)
                sweep_moves += 1
                if (
                    current_hpwl
                    < initial_hpwl - args.improvement_tolerance
                ):
                    escape_stop_reason = "strict_improvement"
                    strict_improvement = True
                    break
            completed_escape_sweeps += 1
            if strict_improvement:
                break
            if not sweep_moves:
                escape_stop_reason = "no_guided_candidate"
                break
    escape_final_hpwl = current_hpwl
    escape_held_refdes = _escape_hold_refdes(
        escape_moves,
        current_centers,
        initial_centers,
        args.site_tolerance,
    )
    if args.escape_state_output is not None:
        escape_position = torch.from_numpy(
            np.concatenate((node_x.copy(), node_y.copy()))
        )
        escape_legality = context.exact_report(escape_position, placedb)
        if (
            escape_legality["keepin_violation_count"]
            or escape_legality["overlap_pair_count"]
        ):
            raise ValueError("guided escape state is illegal")
        escape_score = 2.0 / (
            current_hpwl / baseline_hpwl
            + current_hpwl / baseline_rsmt
        )
        write_placement_atomic(
            placedb,
            args.escape_state_placement,
            node_x,
            node_y,
        )
        write_json_atomic(
            args.escape_state_output,
            {
                "status": "FEASIBLE",
                "method": "deterministic_exact_guided_escape_seed",
                "source_json": str(args.source),
                "assignment_json": source["assignment_json"],
                "grid_mm": float(source["grid_mm"]),
                "manual_baseline_endpoints": source.get(
                    "manual_baseline_endpoints", []
                ),
                "candidate_domain_overlap_model_exact": True,
                "objective_mode": "guided_escape_hpwl",
                "certification_required": True,
                "search_seed_only": True,
                "plateau_guide_json": str(args.plateau_guide),
                "area_epsilon": area_epsilon,
                "candidate_count": total_candidate_count,
                "candidate_counts": {
                    refdes: len(row["centers"])
                    for refdes, row in candidate_rows.items()
                },
                "max_escape_sweeps": args.max_escape_sweeps,
                "escape_order_seed": args.escape_order_seed,
                "escape_order_rng": (
                    "numpy.default_rng/PCG64"
                    if args.escape_order_seed is not None
                    else None
                ),
                "escape_order_numpy_version": (
                    np.__version__
                    if args.escape_order_seed is not None
                    else None
                ),
                "escape_sweep_orders": copy.deepcopy(escape_sweep_orders),
                "escape_hpwl_budget": args.escape_hpwl_budget,
                "escape_hpwl_ceiling": escape_hpwl_ceiling,
                "max_escape_move_rise": args.max_escape_move_rise,
                "completed_escape_sweeps": completed_escape_sweeps,
                "escape_stop_reason": escape_stop_reason,
                "escape_move_count": len(escape_moves),
                "escape_moves": copy.deepcopy(escape_moves),
                "escape_held_refdes": sorted(escape_held_refdes),
                "source_hpwl": initial_hpwl,
                "hpwl": current_hpwl,
                "hpwl_rise": current_hpwl - initial_hpwl,
                "normalized_score_upper_bound": escape_score,
                "legality": escape_legality,
                "placement": str(args.escape_state_placement),
                "selected_sites": copy.deepcopy(selected_sites),
            },
        )
    moves = []
    pair_moves = []
    pair_searches = []
    completed_sweeps = 0
    completed_escape_hold_sweeps = 0
    escape_hold_terminated = False
    escape_hold_stop_reason = (
        "max_hold_sweeps"
        if args.escape_hold_sweeps and escape_held_refdes
        else "no_held_refdes"
        if args.escape_hold_sweeps
        else "disabled"
    )
    stop_reason = "max_sweeps"
    while completed_sweeps < args.max_sweeps:
        sweep = completed_sweeps
        sweep_moves = 0
        hold_active = (
            escape_enabled
            and sweep < args.escape_hold_sweeps
            and bool(escape_held_refdes)
            and not escape_hold_terminated
        )
        for constraint in constraints:
            if hold_active and constraint.refdes in escape_held_refdes:
                continue
            row = candidate_rows[constraint.refdes]
            centers = row["centers"]
            legal = _legal_candidate_mask(
                constraint,
                centers,
                constraints_by_side[constraint.side],
                current_centers,
                area_epsilon,
            )
            if not np.any(legal):
                raise ValueError(
                    f"no collision-free sites for {constraint.refdes}"
                )
            total_hpwl = _candidate_total_hpwl(
                placedb,
                constraint,
                centers,
                node_x,
                node_y,
                node_nets[constraint.node_id],
                current_hpwl,
            )
            total_hpwl[~legal] = np.inf
            guide_center = (
                np.asarray(
                    plateau_guide[constraint.refdes], dtype=np.float64
                )
                if plateau_guide is not None
                else None
            )
            best_index, move_type = _select_candidate(
                total_hpwl,
                legal,
                centers,
                current_centers[constraint.refdes],
                current_hpwl,
                guide_center,
                args.improvement_tolerance,
                args.equality_tolerance,
                args.guide_tolerance,
            )
            if best_index is None:
                continue
            predicted_hpwl = float(total_hpwl[best_index])
            old_center = current_centers[constraint.refdes].copy()
            new_center = centers[best_index].copy()
            before_hpwl = current_hpwl
            node_x[constraint.node_id] = (
                new_center[0] - constraint.node_width / 2
            )
            node_y[constraint.node_id] = (
                new_center[1] - constraint.node_height / 2
            )
            current_centers[constraint.refdes] = new_center
            current_hpwl = float(placedb.hpwl(node_x, node_y))
            if abs(current_hpwl - predicted_hpwl) > 1e-8:
                raise ValueError(
                    f"candidate HPWL replay failed for {constraint.refdes}"
                )
            if current_hpwl > before_hpwl + args.equality_tolerance:
                raise ValueError("plateau move increased HPWL")
            selected_sites[constraint.refdes] = {
                "region_candidate_index": int(row["eligible"][best_index]),
                "center": new_center.tolist(),
            }
            moves.append(
                {
                    "sweep": sweep,
                    "refdes": constraint.refdes,
                    "side": constraint.side,
                    "move_type": move_type,
                    "old_center": old_center.tolist(),
                    "new_center": new_center.tolist(),
                    "guide_distance_before": (
                        float(np.linalg.norm(old_center - guide_center))
                        if guide_center is not None
                        else None
                    ),
                    "guide_distance_after": (
                        float(np.linalg.norm(new_center - guide_center))
                        if guide_center is not None
                        else None
                    ),
                    "region_candidate_index": int(
                        row["eligible"][best_index]
                    ),
                    "legal_candidate_count": int(np.count_nonzero(legal)),
                    "hpwl_before": before_hpwl,
                    "hpwl_after": current_hpwl,
                    "hpwl_delta": current_hpwl - before_hpwl,
                }
            )
            sweep_moves += 1
        completed_sweeps += 1
        if hold_active:
            completed_escape_hold_sweeps += 1
        if sweep_moves:
            continue
        pair_excluded_refdes = (
            escape_held_refdes if hold_active else frozenset()
        )
        if len(pair_moves) < args.max_pair_moves:
            pair_started = time.perf_counter()
            pair_move, pair_diagnostics = _best_pair_move(
                placedb,
                constraints,
                candidate_rows,
                current_centers,
                node_x,
                node_y,
                node_nets,
                current_hpwl,
                area_epsilon,
                args.improvement_tolerance,
                excluded_refdes=pair_excluded_refdes,
            )
            pair_diagnostics["hold_active"] = hold_active
            pair_diagnostics["excluded_refdes"] = sorted(
                pair_excluded_refdes
            )
            pair_diagnostics["elapsed_seconds"] = (
                time.perf_counter() - pair_started
            )
            pair_searches.append(pair_diagnostics)
            if pair_move is not None:
                before_hpwl = current_hpwl
                first = pair_move.pop("first")
                second = pair_move.pop("second")
                pair_move.pop("key")
                first_old_center = current_centers[first.refdes].copy()
                second_old_center = current_centers[second.refdes].copy()
                for constraint, center, region_index in (
                    (
                        first,
                        pair_move["first_center"],
                        pair_move["first_region_candidate_index"],
                    ),
                    (
                        second,
                        pair_move["second_center"],
                        pair_move["second_region_candidate_index"],
                    ),
                ):
                    node_x[constraint.node_id] = (
                        center[0] - constraint.node_width / 2
                    )
                    node_y[constraint.node_id] = (
                        center[1] - constraint.node_height / 2
                    )
                    current_centers[constraint.refdes] = center.copy()
                    selected_sites[constraint.refdes] = {
                        "region_candidate_index": region_index,
                        "center": center.tolist(),
                    }
                current_hpwl = float(placedb.hpwl(node_x, node_y))
                if abs(current_hpwl - pair_move["hpwl"]) > 1e-8:
                    raise ValueError("pair HPWL replay failed")
                pair_move.update(
                    {
                        "after_sweep": sweep,
                        "first_refdes": first.refdes,
                        "second_refdes": second.refdes,
                        "first_old_center": first_old_center.tolist(),
                        "second_old_center": second_old_center.tolist(),
                        "first_center": pair_move["first_center"].tolist(),
                        "second_center": pair_move["second_center"].tolist(),
                        "hpwl_before": before_hpwl,
                        "hpwl_after": current_hpwl,
                        "hpwl_delta": current_hpwl - before_hpwl,
                    }
                )
                pair_moves.append(pair_move)
                continue
        if hold_active:
            escape_hold_terminated = True
            escape_hold_stop_reason = "no_adaptation_move"
            continue
        if args.max_pair_moves and len(pair_moves) >= args.max_pair_moves:
            stop_reason = "max_pair_moves"
            break
        if args.max_pair_moves:
            stop_reason = (
                "lexicographic_two_optimum"
                if plateau_guide is not None
                else "two_optimum"
            )
        else:
            stop_reason = (
                "lexicographic_optimum"
                if plateau_guide is not None
                else "one_optimum"
            )
        break

    search_stop_reason = stop_reason
    returned_to_source = False
    if (
        escape_enabled
        and current_hpwl
        >= initial_hpwl - args.improvement_tolerance
    ):
        node_x = initial_node_x.copy()
        node_y = initial_node_y.copy()
        current_centers = {
            refdes: center.copy()
            for refdes, center in initial_centers.items()
        }
        selected_sites = copy.deepcopy(initial_selected_sites)
        current_hpwl = initial_hpwl
        returned_to_source = True
        stop_reason = f"restored_source_after_{search_stop_reason}"

    position = torch.from_numpy(np.concatenate((node_x, node_y)))
    legality = context.exact_report(position, placedb)
    if legality["keepin_violation_count"] or legality["overlap_pair_count"]:
        raise ValueError("greedy descent produced an illegal placement")
    score = 2.0 / (
        current_hpwl / baseline_hpwl + current_hpwl / baseline_rsmt
    )
    write_placement_atomic(placedb, args.placement, node_x, node_y)
    attempted_move_count = (
        len(escape_moves) + len(moves) + 2 * len(pair_moves)
    )
    attempted_strict_move_count = (
        sum(move["move_type"] == "strict" for move in escape_moves)
        + sum(move["move_type"] == "strict" for move in moves)
    )
    attempted_plateau_move_count = (
        sum(move["move_type"] == "plateau" for move in escape_moves)
        + sum(move["move_type"] == "plateau" for move in moves)
    )
    attempted_uphill_move_count = sum(
        move["move_type"] == "uphill" for move in escape_moves
    )
    result = {
        "status": "FEASIBLE",
        "method": (
            "deterministic_exact_guided_threshold_two_opt_search"
            if escape_enabled and args.max_pair_moves
            else "deterministic_exact_guided_threshold_site_search"
            if escape_enabled
            else "deterministic_exact_lexicographic_two_opt_descent"
            if plateau_guide is not None and args.max_pair_moves
            else "deterministic_exact_two_opt_descent"
            if args.max_pair_moves
            else "deterministic_exact_lexicographic_site_descent"
            if plateau_guide is not None
            else "deterministic_exact_one_opt_descent"
        ),
        "source_json": str(args.source),
        "assignment_json": source["assignment_json"],
        "grid_mm": float(source["grid_mm"]),
        "manual_baseline_endpoints": source.get(
            "manual_baseline_endpoints", []
        ),
        "candidate_domain_overlap_model_exact": True,
        "objective_mode": "greedy_hpwl",
        "certification_required": True,
        "plateau_guide_json": (
            str(args.plateau_guide) if args.plateau_guide else None
        ),
        "area_epsilon": area_epsilon,
        "candidate_count": total_candidate_count,
        "candidate_counts": {
            refdes: len(row["centers"])
            for refdes, row in candidate_rows.items()
        },
        "max_sweeps": args.max_sweeps,
        "max_pair_moves": args.max_pair_moves,
        "max_escape_sweeps": args.max_escape_sweeps,
        "escape_order_seed": args.escape_order_seed,
        "escape_order_rng": (
            "numpy.default_rng/PCG64"
            if args.escape_order_seed is not None
            else None
        ),
        "escape_order_numpy_version": (
            np.__version__ if args.escape_order_seed is not None else None
        ),
        "escape_sweep_orders": escape_sweep_orders,
        "escape_hold_sweeps": args.escape_hold_sweeps,
        "completed_escape_hold_sweeps": completed_escape_hold_sweeps,
        "escape_hold_stop_reason": escape_hold_stop_reason,
        "escape_held_refdes": sorted(escape_held_refdes),
        "escape_hpwl_budget": args.escape_hpwl_budget,
        "escape_hpwl_ceiling": escape_hpwl_ceiling,
        "max_escape_move_rise": args.max_escape_move_rise,
        "completed_escape_sweeps": completed_escape_sweeps,
        "escape_stop_reason": escape_stop_reason,
        "escape_peak_hpwl": escape_peak_hpwl,
        "escape_peak_hpwl_rise": escape_peak_hpwl - initial_hpwl,
        "escape_final_hpwl": escape_final_hpwl,
        "escape_move_count": len(escape_moves),
        "escape_strict_move_count": sum(
            move["move_type"] == "strict" for move in escape_moves
        ),
        "escape_plateau_move_count": sum(
            move["move_type"] == "plateau" for move in escape_moves
        ),
        "escape_uphill_move_count": sum(
            move["move_type"] == "uphill" for move in escape_moves
        ),
        "escape_moves": escape_moves,
        "completed_sweeps": completed_sweeps,
        "stop_reason": stop_reason,
        "search_stop_reason": search_stop_reason,
        "returned_to_source": returned_to_source,
        "elapsed_seconds": time.perf_counter() - started,
        "attempted_move_count": attempted_move_count,
        "attempted_strict_move_count": attempted_strict_move_count,
        "attempted_plateau_move_count": attempted_plateau_move_count,
        "attempted_uphill_move_count": attempted_uphill_move_count,
        "attempted_pair_move_count": len(pair_moves),
        "move_count": 0 if returned_to_source else attempted_move_count,
        "strict_move_count": (
            0 if returned_to_source else attempted_strict_move_count
        ),
        "plateau_move_count": (
            0 if returned_to_source else attempted_plateau_move_count
        ),
        "uphill_move_count": (
            0 if returned_to_source else attempted_uphill_move_count
        ),
        "moves": moves,
        "pair_move_count": 0 if returned_to_source else len(pair_moves),
        "pair_moves": pair_moves,
        "pair_searches": pair_searches,
        "initial_hpwl": initial_hpwl,
        "hpwl": current_hpwl,
        "hpwl_improvement": initial_hpwl - current_hpwl,
        "normalized_score_upper_bound": score,
        "legality": legality,
        "placement": str(args.placement),
        "selected_sites": selected_sites,
    }
    write_json_atomic(args.output, result)
    return result


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--placement", type=Path, required=True)
    parser.add_argument("--max-sweeps", type=int, default=20)
    parser.add_argument("--max-pair-moves", type=int, default=0)
    parser.add_argument("--max-escape-sweeps", type=int, default=0)
    parser.add_argument("--escape-order-seed", type=int)
    parser.add_argument("--escape-hpwl-budget", type=float, default=0.0)
    parser.add_argument("--max-escape-move-rise", type=float)
    parser.add_argument("--escape-hold-sweeps", type=int, default=0)
    parser.add_argument("--escape-state-output", type=Path)
    parser.add_argument("--escape-state-placement", type=Path)
    parser.add_argument("--plateau-guide", type=Path)
    parser.add_argument("--site-tolerance", type=float, default=1e-8)
    parser.add_argument("--improvement-tolerance", type=float, default=1e-9)
    parser.add_argument("--equality-tolerance", type=float, default=1e-9)
    parser.add_argument("--guide-tolerance", type=float, default=1e-12)
    parser.add_argument(
        "--bookshelf-dir",
        type=Path,
        default=ROOT / "results/m336/bookshelf",
    )
    args = parser.parse_args()
    if args.max_sweeps <= 0:
        parser.error("--max-sweeps must be positive")
    if args.max_pair_moves < 0:
        parser.error("--max-pair-moves must be non-negative")
    if args.max_escape_sweeps < 0:
        parser.error("--max-escape-sweeps must be non-negative")
    if args.escape_order_seed is not None and args.escape_order_seed < 0:
        parser.error("--escape-order-seed must be non-negative")
    if args.escape_hpwl_budget < 0:
        parser.error("--escape-hpwl-budget must be non-negative")
    if (
        args.max_escape_move_rise is not None
        and args.max_escape_move_rise < 0
    ):
        parser.error("--max-escape-move-rise must be non-negative")
    if args.escape_hold_sweeps < 0:
        parser.error("--escape-hold-sweeps must be non-negative")
    if args.max_escape_sweeps and args.plateau_guide is None:
        parser.error("--max-escape-sweeps requires --plateau-guide")
    if args.escape_hold_sweeps and not args.max_escape_sweeps:
        parser.error("--escape-hold-sweeps requires --max-escape-sweeps")
    if (args.escape_state_output is None) != (
        args.escape_state_placement is None
    ):
        parser.error(
            "--escape-state-output and --escape-state-placement are paired"
        )
    if args.escape_state_output is not None and not args.max_escape_sweeps:
        parser.error("escape-state output requires --max-escape-sweeps")
    if any(
        tolerance < 0
        for tolerance in (
            args.site_tolerance,
            args.improvement_tolerance,
            args.equality_tolerance,
            args.guide_tolerance,
        )
    ):
        parser.error("tolerances must be non-negative")
    return args


def main() -> int:
    args = parse_args()
    result = descend(args)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "stop_reason",
                    "escape_stop_reason",
                    "escape_move_count",
                    "escape_peak_hpwl_rise",
                    "returned_to_source",
                    "completed_sweeps",
                    "move_count",
                    "initial_hpwl",
                    "hpwl",
                    "hpwl_improvement",
                    "normalized_score_upper_bound",
                    "legality",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
