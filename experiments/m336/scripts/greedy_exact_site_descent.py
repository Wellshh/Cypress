#!/usr/bin/env python3
"""Run deterministic exact-legal one-component site descent for M336."""

from __future__ import annotations

import argparse
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
    moves = []
    started = time.perf_counter()
    completed_sweeps = 0
    stop_reason = "max_sweeps"
    for sweep in range(args.max_sweeps):
        sweep_moves = 0
        for constraint in constraints:
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
            best_index = int(np.argmin(total_hpwl))
            predicted_hpwl = float(total_hpwl[best_index])
            if predicted_hpwl >= current_hpwl - args.improvement_tolerance:
                continue
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
            selected_sites[constraint.refdes] = {
                "region_candidate_index": int(row["eligible"][best_index]),
                "center": new_center.tolist(),
            }
            moves.append(
                {
                    "sweep": sweep,
                    "refdes": constraint.refdes,
                    "side": constraint.side,
                    "old_center": old_center.tolist(),
                    "new_center": new_center.tolist(),
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
        if sweep_moves == 0:
            stop_reason = "one_optimum"
            break

    position = torch.from_numpy(np.concatenate((node_x, node_y)))
    legality = context.exact_report(position, placedb)
    if legality["keepin_violation_count"] or legality["overlap_pair_count"]:
        raise ValueError("greedy descent produced an illegal placement")
    baseline = json.loads(BASELINE_RESULT.read_text())
    baseline_hpwl = float(baseline["metrics"]["hpwl"])
    baseline_rsmt = float(baseline["metrics"]["rsmt"])
    score = 2.0 / (
        current_hpwl / baseline_hpwl + current_hpwl / baseline_rsmt
    )
    write_placement_atomic(placedb, args.placement, node_x, node_y)
    result = {
        "status": "FEASIBLE",
        "method": "deterministic_exact_one_opt_descent",
        "source_json": str(args.source),
        "assignment_json": source["assignment_json"],
        "grid_mm": float(source["grid_mm"]),
        "manual_baseline_endpoints": source.get(
            "manual_baseline_endpoints", []
        ),
        "candidate_domain_overlap_model_exact": True,
        "objective_mode": "greedy_hpwl",
        "certification_required": True,
        "area_epsilon": area_epsilon,
        "candidate_count": total_candidate_count,
        "candidate_counts": {
            refdes: len(row["centers"])
            for refdes, row in candidate_rows.items()
        },
        "max_sweeps": args.max_sweeps,
        "completed_sweeps": completed_sweeps,
        "stop_reason": stop_reason,
        "elapsed_seconds": time.perf_counter() - started,
        "move_count": len(moves),
        "moves": moves,
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
    parser.add_argument("--site-tolerance", type=float, default=1e-8)
    parser.add_argument("--improvement-tolerance", type=float, default=1e-9)
    parser.add_argument(
        "--bookshelf-dir",
        type=Path,
        default=ROOT / "results/m336/bookshelf",
    )
    args = parser.parse_args()
    if args.max_sweeps <= 0:
        parser.error("--max-sweeps must be positive")
    if args.site_tolerance < 0 or args.improvement_tolerance < 0:
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
