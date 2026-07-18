#!/usr/bin/env python3
"""Compute relaxed HPWL and score bounds for M336 keep-in assignments."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from dreamplace import Params, PlaceDB
from dreamplace.constraints.anchor_keepin import AnchorKeepInContext
from dreamplace.constraints.region_projection import (
    FeasibleDomain,
    InfeasibleDomainError,
)

from run_matrix import (
    EXPERIMENTS,
    REPO_ROOT,
    constraint_config,
    parse_placement,
    placement_config,
    repo_path,
    sha256_file,
    write_json,
)


def minimum_interval_span(intervals):
    """Return the minimum range after choosing one point from each interval."""
    intervals = tuple((float(lower), float(upper)) for lower, upper in intervals)
    if not intervals:
        return 0.0
    if any(not math.isfinite(value) for interval in intervals for value in interval):
        raise ValueError("interval endpoints must be finite")
    if any(lower > upper for lower, upper in intervals):
        raise ValueError("interval lower endpoint exceeds upper endpoint")
    return max(
        0.0,
        max(lower for lower, _ in intervals)
        - min(upper for _, upper in intervals),
    )


def _decode(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _load_context(args):
    run_dir = args.output_dir / "context"
    constraint_path = run_dir / "anchor_keepin.json"
    write_json(
        constraint_path,
        constraint_config(
            run_dir,
            EXPERIMENTS["E4"],
            args.assignment,
            args.grid_mm,
            args.clearance_mm,
        ),
    )
    config = placement_config(
        run_dir,
        constraint_path,
        EXPERIMENTS["E4"],
        seed=1000,
        iterations=0,
        gpu=False,
        anchor_weight=1.0,
        grid_mm=args.grid_mm,
        clearance_mm=args.clearance_mm,
        aux_input=args.bookshelf_dir / "m336.aux",
    )
    params = Params.Params()
    params.update(config)
    placedb = PlaceDB.PlaceDB()
    placedb.read(params)
    placedb.initialize_from_rawdb(params)
    placedb.initialize(params)
    return placedb, AnchorKeepInContext.from_params(params, placedb)


def _fixed_assignment_ranges(context):
    ranges = {}
    diagnostics = {}
    for constraint in context.constraints:
        centers = constraint.domain.valid_centers
        ranges[constraint.node_id] = (
            float(np.min(centers[:, 0])),
            float(np.max(centers[:, 0])),
            float(np.min(centers[:, 1])),
            float(np.max(centers[:, 1])),
        )
        diagnostics[constraint.refdes] = {
            "regions": [constraint.region_id],
            "candidate_count": int(len(centers)),
        }
    return ranges, diagnostics


def _any_same_side_ranges(context, clearance_mm):
    ranges = {}
    diagnostics = {}
    region_sides = {
        region_id: region.side
        for region_id, region in context.geometry.regions.items()
    }
    clearance = float(clearance_mm) * abs(context.alignment.scale)
    cache = {}
    for constraint in context.constraints:
        center_clouds = []
        feasible_regions = []
        for region_id, region in sorted(context.regions.items()):
            if region_sides[region_id] != constraint.side:
                continue
            key = (region_id, constraint.domain.footprint_local.wkb_hex)
            try:
                if key not in cache:
                    cache[key] = FeasibleDomain.build(
                        region=region,
                        width=constraint.domain.width,
                        height=constraint.domain.height,
                        grid=context.grid,
                        clearance=clearance,
                        footprint_local=constraint.domain.footprint_local,
                    )
            except InfeasibleDomainError:
                continue
            center_clouds.append(cache[key].valid_centers)
            feasible_regions.append(region_id)
        if not center_clouds:
            raise InfeasibleDomainError(
                "component has no feasible same-side region: %s"
                % constraint.refdes
            )
        centers = np.concatenate(center_clouds, axis=0)
        ranges[constraint.node_id] = (
            float(np.min(centers[:, 0])),
            float(np.max(centers[:, 0])),
            float(np.min(centers[:, 1])),
            float(np.max(centers[:, 1])),
        )
        diagnostics[constraint.refdes] = {
            "regions": feasible_regions,
            "candidate_count": int(len(centers)),
        }
    return ranges, diagnostics


def _baseline_positions(placedb, baseline_pl):
    placement = parse_placement(Path(baseline_pl))
    names = [_decode(name) for name in placedb.node_names]
    physical_names = names[: placedb.num_physical_nodes]
    missing = sorted(set(physical_names) - set(placement))
    if missing:
        raise ValueError("baseline placement is missing nodes: %s" % missing)
    return (
        np.asarray([placement[name][0] for name in physical_names]),
        np.asarray([placement[name][1] for name in physical_names]),
    )


def _bound_for_ranges(placedb, constraints, center_ranges, baseline_x, baseline_y):
    per_net = []
    total = 0.0
    for net_id, pins in enumerate(placedb.net2pin_map):
        x_intervals = []
        y_intervals = []
        for pin_id in pins:
            node_id = int(placedb.pin2node_map[pin_id])
            if node_id in constraints:
                constraint = constraints[node_id]
                min_x, max_x, min_y, max_y = center_ranges[node_id]
                x_offset = (
                    -constraint.node_width / 2
                    + float(placedb.pin_offset_x[pin_id])
                )
                y_offset = (
                    -constraint.node_height / 2
                    + float(placedb.pin_offset_y[pin_id])
                )
                x_intervals.append((min_x + x_offset, max_x + x_offset))
                y_intervals.append((min_y + y_offset, max_y + y_offset))
            else:
                x = float(placedb.node_x[node_id] + placedb.pin_offset_x[pin_id])
                y = float(placedb.node_y[node_id] + placedb.pin_offset_y[pin_id])
                x_intervals.append((x, x))
                y_intervals.append((y, y))
        lower_bound = (
            minimum_interval_span(x_intervals)
            + minimum_interval_span(y_intervals)
        ) * float(placedb.net_weights[net_id])
        total += lower_bound
        per_net.append(
            {
                "net_id": net_id,
                "net_name": _decode(placedb.net_names[net_id]),
                "pin_count": int(len(pins)),
                "hpwl_lower_bound": lower_bound,
                "baseline_hpwl": float(
                    placedb.net_hpwl(baseline_x, baseline_y, net_id)
                ),
            }
        )
    return total, per_net


def _summarize_mode(
    placedb,
    constraints,
    center_ranges,
    domain_diagnostics,
    baseline_x,
    baseline_y,
    baseline_hpwl,
    baseline_rsmt,
):
    hpwl_lower_bound, per_net = _bound_for_ranges(
        placedb, constraints, center_ranges, baseline_x, baseline_y
    )
    hpwl_ratio = hpwl_lower_bound / baseline_hpwl
    # Every rectilinear tree must span each net's x and y ranges, so RSMT is
    # bounded below by the same relaxed HPWL sum.
    rsmt_ratio = hpwl_lower_bound / baseline_rsmt
    return {
        "hpwl_lower_bound": hpwl_lower_bound,
        "hpwl_lower_bound_ratio": hpwl_ratio,
        "rsmt_lower_bound": hpwl_lower_bound,
        "rsmt_lower_bound_ratio": rsmt_ratio,
        "normalized_quality_score_upper_bound": 2.0 / (hpwl_ratio + rsmt_ratio),
        "domain_diagnostics": domain_diagnostics,
        "per_net": per_net,
        "largest_net_lower_bounds": sorted(
            per_net,
            key=lambda row: (-row["hpwl_lower_bound"], row["net_name"]),
        )[:15],
    }


def analyze(args):
    baseline_result = json.loads(args.baseline_result.read_text())
    baseline_metrics = baseline_result["metrics"]
    baseline_hpwl = float(baseline_metrics["hpwl"])
    baseline_rsmt = float(baseline_metrics["rsmt"])
    placedb, context = _load_context(args)
    baseline_x, baseline_y = _baseline_positions(
        placedb, args.bookshelf_dir / "m336.baseline.pl"
    )
    independent_hpwl = float(placedb.hpwl(baseline_x, baseline_y))
    if not math.isclose(independent_hpwl, baseline_hpwl, abs_tol=1e-3):
        raise ValueError(
            "baseline HPWL mismatch: PlaceDB %.9g != result %.9g"
            % (independent_hpwl, baseline_hpwl)
        )

    constraints = {constraint.node_id: constraint for constraint in context.constraints}
    fixed_ranges, fixed_diagnostics = _fixed_assignment_ranges(context)
    any_ranges, any_diagnostics = _any_same_side_ranges(
        context, args.clearance_mm
    )
    result = {
        "schema": "m336_quality_lower_bound_v1",
        "baseline": {
            "hpwl": baseline_hpwl,
            "rsmt": baseline_rsmt,
            "result": repo_path(args.baseline_result),
        },
        "input_sha256": {
            "assignment": sha256_file(args.assignment),
            "baseline_result": sha256_file(args.baseline_result),
            "baseline_placement": sha256_file(
                args.bookshelf_dir / "m336.baseline.pl"
            ),
        },
        "proof_relaxations": [
            "ignore component overlap and region capacity",
            "allow each pin axis to choose any point in its domain interval",
            "ignore shared component positions across pins and nets",
            "ignore discrete x/y and polygon coupling inside interval bounds",
        ],
        "fixed_assignment": _summarize_mode(
            placedb,
            constraints,
            fixed_ranges,
            fixed_diagnostics,
            baseline_x,
            baseline_y,
            baseline_hpwl,
            baseline_rsmt,
        ),
        "any_same_side_region": _summarize_mode(
            placedb,
            constraints,
            any_ranges,
            any_diagnostics,
            baseline_x,
            baseline_y,
            baseline_hpwl,
            baseline_rsmt,
        ),
    }
    write_json(args.output_dir / "quality-lower-bound.json", result)
    return result


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
        default=REPO_ROOT / "results/m336/quality_bound",
    )
    parser.add_argument("--grid-mm", type=float, default=0.1)
    parser.add_argument("--clearance-mm", type=float, default=0.0)
    args = parser.parse_args()
    args.bookshelf_dir = args.bookshelf_dir.resolve()
    args.assignment = args.assignment.resolve()
    args.baseline_result = args.baseline_result.resolve()
    args.output_dir = args.output_dir.resolve()
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
                "fixed_assignment": {
                    key: value
                    for key, value in result["fixed_assignment"].items()
                    if key not in {"domain_diagnostics", "per_net"}
                },
                "any_same_side_region": {
                    key: value
                    for key, value in result["any_same_side_region"].items()
                    if key not in {"domain_diagnostics", "per_net"}
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
