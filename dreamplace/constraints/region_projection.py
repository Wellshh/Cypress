"""Footprint-aware feasible-domain construction and hard projection."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely import affinity
from shapely.geometry import box
from shapely.prepared import prep


class InfeasibleDomainError(ValueError):
    pass


@dataclass
class FeasibleDomain:
    """Conservative site-grid domain for a component center."""

    region: object
    width: float
    height: float
    clearance: float
    grid: float
    x_values: np.ndarray
    y_values: np.ndarray
    valid_mask: np.ndarray
    valid_centers: np.ndarray
    outside_distance: np.ndarray
    _tree: cKDTree = field(repr=False)
    footprint_local: object = field(default=None, repr=False)

    @classmethod
    def build(
        cls,
        region,
        width: float,
        height: float,
        grid: float,
        clearance: float = 0.0,
        footprint_local=None,
    ):
        if grid <= 0 or width <= 0 or height <= 0 or clearance < 0:
            raise ValueError("invalid feasible-domain dimensions")
        effective_width = width + 2 * clearance
        effective_height = height + 2 * clearance
        if footprint_local is None:
            footprint_local = box(
                -width / 2, -height / 2, width / 2, height / 2
            )
        if clearance:
            footprint_local = footprint_local.buffer(
                clearance, cap_style=3, join_style=2
            )
        min_x, min_y, max_x, max_y = region.bounds
        local_min_x, local_min_y, local_max_x, local_max_y = footprint_local.bounds
        first_x = math.ceil((min_x - local_min_x) / grid - 1e-9) * grid
        last_x = math.floor((max_x - local_max_x) / grid + 1e-9) * grid
        first_y = math.ceil((min_y - local_min_y) / grid - 1e-9) * grid
        last_y = math.floor((max_y - local_max_y) / grid + 1e-9) * grid
        if first_x > last_x or first_y > last_y:
            raise InfeasibleDomainError(
                "footprint %.6gx%.6g has no bounding-box-feasible sites"
                % (effective_width, effective_height)
            )

        x_values = np.arange(
            first_x, last_x + grid * 0.5, grid, dtype=np.float64
        )
        y_values = np.arange(
            first_y, last_y + grid * 0.5, grid, dtype=np.float64
        )
        valid_mask = np.zeros((len(y_values), len(x_values)), dtype=bool)
        prepared_region = prep(region)
        for row, center_y in enumerate(y_values):
            for column, center_x in enumerate(x_values):
                footprint = affinity.translate(
                    footprint_local, xoff=center_x, yoff=center_y
                )
                valid_mask[row, column] = prepared_region.covers(footprint)

        valid_rows, valid_columns = np.nonzero(valid_mask)
        if not len(valid_rows):
            raise InfeasibleDomainError(
                "footprint %.6gx%.6g has no sites inside the assigned polygon"
                % (effective_width, effective_height)
            )
        valid_centers = np.column_stack(
            (x_values[valid_columns], y_values[valid_rows])
        )
        outside_distance = ndimage.distance_transform_edt(
            ~valid_mask, sampling=(grid, grid)
        )
        return cls(
            region=region,
            width=float(width),
            height=float(height),
            clearance=float(clearance),
            grid=float(grid),
            x_values=x_values,
            y_values=y_values,
            valid_mask=valid_mask,
            valid_centers=valid_centers,
            outside_distance=outside_distance,
            _tree=cKDTree(valid_centers),
            footprint_local=footprint_local,
        )

    @property
    def effective_width(self):
        return self.width + 2 * self.clearance

    @property
    def effective_height(self):
        return self.height + 2 * self.clearance

    def footprint(self, center):
        return affinity.translate(
            self.footprint_local, xoff=center[0], yoff=center[1]
        )

    def contains(self, center) -> bool:
        return bool(self.region.covers(self.footprint(center)))

    def project(self, center) -> Tuple[Point, float]:
        center = np.asarray(center, dtype=np.float64)
        if self.contains(center):
            return (float(center[0]), float(center[1])), 0.0
        distance, index = self._tree.query(center, k=1)
        projected = self.valid_centers[int(index)]
        return (float(projected[0]), float(projected[1])), float(distance)


Point = Tuple[float, float]


@dataclass(frozen=True)
class NodeConstraint:
    node_id: int
    refdes: str
    side: str
    group_id: str
    subgroup_id: str
    region_id: str
    domain: FeasibleDomain
    target_center: Point
    node_width: float
    node_height: float
    anchor_refdes: str = ""


@dataclass(frozen=True)
class ProjectionStats:
    projected_node_ids: Tuple[int, ...]
    projected_refdes: Tuple[str, ...]
    max_distance: float

    @property
    def count(self):
        return len(self.projected_node_ids)


class RegionProjector:
    """In-place projector for Cypress's concatenated lower-left position vector."""

    def __init__(
        self,
        num_nodes: int,
        constraints: Sequence[NodeConstraint],
        frozen_lower_left: Optional[Mapping[int, Point]] = None,
        enabled: bool = True,
    ):
        self.num_nodes = int(num_nodes)
        self.constraints = tuple(constraints)
        self.frozen_lower_left = dict(frozen_lower_left or {})
        self.enabled = bool(enabled)
        self.last_stats = ProjectionStats((), (), 0.0)
        self.total_projected = 0

    def __call__(self, pos):
        if not self.enabled and not self.frozen_lower_left:
            self.last_stats = ProjectionStats((), (), 0.0)
            return self.last_stats

        projected_ids = []
        projected_names = []
        max_distance = 0.0
        with torch.no_grad():
            for node_id, lower_left in self.frozen_lower_left.items():
                pos[node_id] = lower_left[0]
                pos[self.num_nodes + node_id] = lower_left[1]

            if self.enabled:
                for constraint in self.constraints:
                    node_id = constraint.node_id
                    center = (
                        float(pos[node_id].detach().cpu())
                        + constraint.node_width / 2,
                        float(pos[self.num_nodes + node_id].detach().cpu())
                        + constraint.node_height / 2,
                    )
                    if constraint.domain.contains(center):
                        continue
                    projected, distance = constraint.domain.project(center)
                    pos[node_id] = projected[0] - constraint.node_width / 2
                    pos[self.num_nodes + node_id] = (
                        projected[1] - constraint.node_height / 2
                    )
                    projected_ids.append(node_id)
                    projected_names.append(constraint.refdes)
                    max_distance = max(max_distance, distance)

        self.last_stats = ProjectionStats(
            tuple(projected_ids), tuple(projected_names), max_distance
        )
        self.total_projected += self.last_stats.count
        return self.last_stats


def zero_optimizer_state(optimizer, parameter, node_ids: Iterable[int], num_nodes: int):
    """Clear momentum/history entries for coordinates changed by projection."""
    node_ids = tuple(sorted(set(int(node_id) for node_id in node_ids)))
    if not node_ids:
        return
    coordinate_ids = torch.as_tensor(
        node_ids + tuple(num_nodes + node_id for node_id in node_ids),
        dtype=torch.long,
        device=parameter.device,
    )

    def clear_tensor(tensor):
        if tensor is not parameter and tensor.shape == parameter.shape:
            tensor.index_fill_(0, coordinate_ids, 0)

    state = optimizer.state.get(parameter, {})
    with torch.no_grad():
        for value in state.values():
            if torch.is_tensor(value):
                clear_tensor(value)
        for group in optimizer.param_groups:
            for key, value in group.items():
                if key == "params":
                    continue
                if torch.is_tensor(value):
                    clear_tensor(value)
                elif isinstance(value, list):
                    for item in value:
                        if torch.is_tensor(item):
                            clear_tensor(item)
