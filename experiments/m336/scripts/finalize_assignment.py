#!/usr/bin/env python3
"""Create a capacity-feasible, side-preserving M336 subgroup assignment."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from shapely import affinity
from shapely.geometry import Point
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dreamplace.constraints.pcb_geometry import load_pcb_geometry
from dreamplace.constraints.region_assignment import load_clusters, split_side_subgroups
from dreamplace.constraints.region_projection import FeasibleDomain, InfeasibleDomainError


DEFAULT_CAPACITY_RATIOS = {
    "bottom_0": 0.68,
    "bottom_1": 0.65,
    "bottom_2": 0.50,
    "top_0": 0.75,
}

PACKING_EXCLUSIONS = {
    ("page_86_U8601__bottom", "bottom_2"): {
        "grid_mm_values": (0.1,),
        "reason": (
            "exact discrete NoOverlap2D preflight is infeasible at 0.1 mm "
            "with the frozen U8601 anchor"
        ),
    }
}


def packing_exclusion_reason(subgroup_id, region_id, grid_mm):
    """Return an evidence-backed joint-packing exclusion for this grid."""
    rule = PACKING_EXCLUSIONS.get((subgroup_id, region_id))
    if rule is None:
        return None
    if not any(
        abs(float(grid_mm) - float(value)) <= 1e-12
        for value in rule["grid_mm_values"]
    ):
        return None
    return rule["reason"]


def finalize(geometry_path, cluster_path, seed_path, output_path, grid_mm):
    geometry = load_pcb_geometry(geometry_path)
    clusters = load_clusters(cluster_path)
    subgroups = split_side_subgroups(
        clusters, {name: symbol.side for name, symbol in geometry.symbols.items()}
    )
    seed_data = json.loads(Path(seed_path).read_text())
    seed_rows = {row["subgroup_id"]: row for row in seed_data["assignments"]}
    anchor_refdes = {cluster.anchor_refdes for cluster in clusters}
    anchor_obstacles = {"TOP": [], "BOTTOM": []}
    for refdes in sorted(anchor_refdes):
        symbol = geometry.symbols[refdes]
        anchor_obstacles[symbol.side].append((refdes, symbol.footprint_mm))
    free_region_area = {}
    for region_id, region in geometry.regions.items():
        obstacles = unary_union(
            [shape for _, shape in anchor_obstacles[region.side]]
        )
        free_region_area[region_id] = region.polygon_mm.difference(obstacles).area

    variables = []
    diagnostics = []
    group_areas = {}
    for group_index, subgroup in enumerate(subgroups):
        members = [
            refdes for refdes in subgroup.members if refdes != subgroup.anchor_refdes
        ]
        group_area = sum(
            geometry.symbols[refdes].footprint_mm.area for refdes in members
        )
        group_areas[subgroup.subgroup_id] = group_area
        anchor = Point(geometry.symbols[subgroup.anchor_refdes].center_mm)
        candidate_rows = []
        for region_id, region_data in sorted(geometry.regions.items()):
            if region_data.side != subgroup.side:
                continue
            reason = packing_exclusion_reason(
                subgroup.subgroup_id, region_id, grid_mm
            )
            feasible = reason is None
            for refdes in members if feasible else ():
                symbol = geometry.symbols[refdes]
                footprint_local = affinity.translate(
                    symbol.footprint_mm,
                    xoff=-symbol.center_mm[0],
                    yoff=-symbol.center_mm[1],
                )
                try:
                    domain = FeasibleDomain.build(
                        region=region_data.polygon_mm,
                        width=symbol.width_mm,
                        height=symbol.height_mm,
                        grid=grid_mm,
                        footprint_local=footprint_local,
                    )
                except InfeasibleDomainError as error:
                    feasible = False
                    reason = "%s: %s" % (refdes, error)
                    break
                has_unblocked_site = any(
                    all(
                        domain.footprint(center).intersection(obstacle).area <= 1e-12
                        for obstacle_refdes, obstacle in anchor_obstacles[subgroup.side]
                        if obstacle_refdes != refdes
                    )
                    for center in domain.valid_centers
                )
                if not has_unblocked_site:
                    feasible = False
                    reason = "%s: all feasible sites overlap a frozen anchor" % refdes
                    break
            distance = float(anchor.distance(region_data.polygon_mm))
            candidate_rows.append(
                {
                    "region_id": region_id,
                    "feasible": feasible,
                    "anchor_distance_mm": distance,
                    "reason": reason,
                }
            )
            if feasible:
                seed_region = seed_rows[subgroup.subgroup_id]["proposed_region_id"]
                variables.append(
                    {
                        "group_index": group_index,
                        "subgroup_id": subgroup.subgroup_id,
                        "region_id": region_id,
                        "area": group_area,
                        "cost": distance + (0.05 if region_id != seed_region else 0.0),
                    }
                )
        if not any(row["feasible"] for row in candidate_rows):
            raise InfeasibleDomainError(
                "subgroup has no feasible same-side region: %s" % subgroup.subgroup_id
            )
        diagnostics.append(
            {
                "subgroup_id": subgroup.subgroup_id,
                "member_area_mm2": group_area,
                "candidates": candidate_rows,
            }
        )

    subgroup_ids = [subgroup.subgroup_id for subgroup in subgroups]
    region_ids = sorted(geometry.regions)
    matrix_rows = []
    lower = []
    upper = []
    for subgroup_id in subgroup_ids:
        matrix_rows.append(
            [1.0 if item["subgroup_id"] == subgroup_id else 0.0 for item in variables]
        )
        lower.append(1.0)
        upper.append(1.0)
    for region_id in region_ids:
        matrix_rows.append(
            [item["area"] if item["region_id"] == region_id else 0.0 for item in variables]
        )
        lower.append(0.0)
        ratio = DEFAULT_CAPACITY_RATIOS[region_id]
        upper.append(free_region_area[region_id] * ratio)

    result = milp(
        c=np.asarray([item["cost"] for item in variables]),
        integrality=np.ones(len(variables)),
        bounds=Bounds(np.zeros(len(variables)), np.ones(len(variables))),
        constraints=LinearConstraint(
            np.asarray(matrix_rows), np.asarray(lower), np.asarray(upper)
        ),
        options={"disp": False},
    )
    if not result.success:
        raise RuntimeError("assignment MILP failed: %s" % result.message)

    selected = {}
    for value, item in zip(result.x, variables):
        if value > 0.5:
            selected[item["subgroup_id"]] = item["region_id"]
    if selected.keys() != set(subgroup_ids):
        raise RuntimeError("assignment MILP did not select exactly one region per subgroup")

    output_rows = []
    region_area = {region_id: 0.0 for region_id in region_ids}
    for row in seed_data["assignments"]:
        output = dict(row)
        region_id = selected[row["subgroup_id"]]
        output["proposed_region_id"] = region_id
        output["proposal_method"] = "side_feasible_capacity_constrained_milp"
        output["status"] = "validated_fixed_assignment"
        output_rows.append(output)
        region_area[region_id] += group_areas[row["subgroup_id"]]

    output_data = dict(seed_data)
    output_data["schema"] = "m336_region_assignment_v2"
    output_data["status"] = "validated_fixed_assignment"
    output_data["method"] = {
        "name": "side_feasible_capacity_constrained_milp",
        "grid_mm": grid_mm,
        "capacity_ratios": DEFAULT_CAPACITY_RATIOS,
        "packing_exclusions": {
            "%s:%s" % key: rule["reason"]
            for key, rule in sorted(PACKING_EXCLUSIONS.items())
            if packing_exclusion_reason(key[0], key[1], grid_mm) is not None
        },
        "packing_exclusion_rules": {
            "%s:%s" % key: rule
            for key, rule in sorted(PACKING_EXCLUSIONS.items())
        },
        "runtime_reassignment": False,
    }
    output_data["assignments"] = output_rows
    output_data["capacity_diagnostics"] = {
        region_id: {
            "member_area_mm2": region_area[region_id],
            "region_area_mm2": geometry.regions[region_id].polygon_mm.area,
            "free_area_after_anchors_mm2": free_region_area[region_id],
            "utilization": region_area[region_id]
            / geometry.regions[region_id].polygon_mm.area,
            "free_area_utilization": region_area[region_id]
            / free_region_area[region_id],
        }
        for region_id in region_ids
    }
    output_data["candidate_diagnostics"] = diagnostics
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_data, indent=2, sort_keys=True) + "\n")
    return output_data["capacity_diagnostics"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--geometry", default="experiments/m336/input/pcb_geometry_keepin.json"
    )
    parser.add_argument(
        "--clusters", default="experiments/m336/input/m336_clusters.json"
    )
    parser.add_argument(
        "--seed", default="experiments/m336/input/m336_region_assignment.seed.json"
    )
    parser.add_argument(
        "--output", default="results/m336/m336_region_assignment.final.json"
    )
    parser.add_argument("--grid-mm", type=float, default=0.1)
    args = parser.parse_args()
    diagnostics = finalize(
        args.geometry, args.clusters, args.seed, args.output, args.grid_mm
    )
    print(json.dumps(diagnostics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
