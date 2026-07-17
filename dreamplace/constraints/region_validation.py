"""Exact polygon containment, overlap, and anchor-distance reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

import numpy as np
from shapely import affinity
from shapely.geometry import box


Point = Tuple[float, float]


@dataclass(frozen=True)
class ComponentPlacement:
    refdes: str
    side: str
    center: Point
    width: float
    height: float
    region_id: Optional[str] = None
    group_id: Optional[str] = None
    subgroup_id: Optional[str] = None
    anchor_center: Optional[Point] = None
    projected_anchor_center: Optional[Point] = None
    fixed: bool = False
    footprint_local: object = None

    @property
    def footprint(self):
        if self.footprint_local is not None:
            return affinity.translate(
                self.footprint_local, xoff=self.center[0], yoff=self.center[1]
            )
        return box(
            self.center[0] - self.width / 2,
            self.center[1] - self.height / 2,
            self.center[0] + self.width / 2,
            self.center[1] + self.height / 2,
        )


def _percentile(values, percentile):
    return float(np.percentile(values, percentile)) if values else None


def validate_placement(
    constrained: Sequence[ComponentPlacement],
    regions: Mapping[str, object],
    fixed: Sequence[ComponentPlacement] = (),
    epsilon: float = 1e-9,
):
    violations = []
    contained = 0
    total_violation_area = 0.0
    for component in constrained:
        if component.region_id not in regions:
            raise KeyError("unknown assigned region: %s" % component.region_id)
        region = regions[component.region_id]
        violation_area = float(component.footprint.difference(region).area)
        if violation_area <= epsilon:
            contained += 1
        else:
            total_violation_area += violation_area
            violations.append(
                {
                    "refdes": component.refdes,
                    "group_id": component.group_id,
                    "subgroup_id": component.subgroup_id,
                    "side": component.side,
                    "region_id": component.region_id,
                    "center": list(component.center),
                    "violation_area": violation_area,
                }
            )

    overlap_pairs = []
    overlap_area = 0.0
    for index, first in enumerate(constrained):
        peers = list(constrained[index + 1 :]) + list(fixed)
        for second in peers:
            if first.side != second.side or first.refdes == second.refdes:
                continue
            area = float(first.footprint.intersection(second.footprint).area)
            if area <= epsilon:
                continue
            overlap_area += area
            overlap_pairs.append(
                {
                    "first_refdes": first.refdes,
                    "second_refdes": second.refdes,
                    "side": first.side,
                    "overlap_area": area,
                    "second_is_fixed": bool(second.fixed),
                }
            )

    anchor_distances = []
    projected_anchor_distances = []
    per_group = {}
    for component in constrained:
        if component.anchor_center is None:
            continue
        distance = float(np.linalg.norm(np.subtract(component.center, component.anchor_center)))
        anchor_distances.append(distance)
        if component.projected_anchor_center is not None:
            projected_anchor_distances.append(
                float(
                    np.linalg.norm(
                        np.subtract(component.center, component.projected_anchor_center)
                    )
                )
            )
        group = per_group.setdefault(component.subgroup_id or component.group_id, [])
        group.append((component.refdes, distance))

    group_metrics = []
    for group_id, rows in sorted(per_group.items()):
        distances = [distance for _, distance in rows]
        group_metrics.append(
            {
                "group_id": group_id,
                "component_count": len(rows),
                "mean_anchor_distance": float(np.mean(distances)),
                "max_anchor_distance": float(np.max(distances)),
                "worst_refdes": max(rows, key=lambda row: row[1])[0],
            }
        )

    return {
        "constrained_component_count": len(constrained),
        "full_containment_count": contained,
        "keepin_violation_count": len(violations),
        "keepin_violation_area": total_violation_area,
        "overlap_pair_count": len(overlap_pairs),
        "overlap_area": overlap_area,
        "violations": violations,
        "overlap_pairs": overlap_pairs,
        "anchor_distance": {
            "count": len(anchor_distances),
            "mean": float(np.mean(anchor_distances)) if anchor_distances else None,
            "median": _percentile(anchor_distances, 50),
            "p90": _percentile(anchor_distances, 90),
            "max": float(np.max(anchor_distances)) if anchor_distances else None,
        },
        "projected_anchor_distance": {
            "count": len(projected_anchor_distances),
            "mean": (
                float(np.mean(projected_anchor_distances))
                if projected_anchor_distances
                else None
            ),
            "median": _percentile(projected_anchor_distances, 50),
            "p90": _percentile(projected_anchor_distances, 90),
            "max": (
                float(np.max(projected_anchor_distances))
                if projected_anchor_distances
                else None
            ),
        },
        "per_group": group_metrics,
    }
