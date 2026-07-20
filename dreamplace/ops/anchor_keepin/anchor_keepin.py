"""PyTorch losses for feature-gated PCB constraints."""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as functional


class AnchorKeepInLoss(nn.Module):
    """Group-balanced Smooth-L1 distance to projected anchor targets."""

    def __init__(
        self,
        node_ids,
        target_centers,
        node_size_x,
        node_size_y,
        num_nodes,
        board_diagonal,
        group_ids=None,
        weights=None,
        beta=1.0,
    ):
        super().__init__()
        self.register_buffer("node_ids", torch.as_tensor(node_ids, dtype=torch.long))
        target_centers = torch.as_tensor(
            target_centers, dtype=node_size_x.dtype
        ).reshape(-1, 2)
        self.register_buffer("target_centers", target_centers)
        self.register_buffer("node_size_x", node_size_x.detach().clone())
        self.register_buffer("node_size_y", node_size_y.detach().clone())
        if weights is None:
            weights = torch.ones(len(self.node_ids), dtype=node_size_x.dtype)
        weights = torch.as_tensor(weights, dtype=node_size_x.dtype)
        if weights.shape != self.node_ids.shape:
            raise ValueError("weights must have shape (N,)")
        if not torch.isfinite(weights).all() or torch.any(weights < 0):
            raise ValueError("anchor weights must be finite and non-negative")
        self.register_buffer("weights", weights)
        self.num_nodes = int(num_nodes)
        self.board_diagonal = float(board_diagonal)
        self.beta = float(beta)
        if self.board_diagonal <= 0:
            raise ValueError("board diagonal must be positive")
        if self.target_centers.shape != (len(self.node_ids), 2):
            raise ValueError("target_centers must have shape (N, 2)")
        if group_ids is None:
            group_ids = ["all"] * len(self.node_ids)
        if len(group_ids) != len(self.node_ids):
            raise ValueError("group_ids must have shape (N,)")

        group_to_index = {}
        encoded_groups = []
        for group_id in group_ids:
            if group_id not in group_to_index:
                group_to_index[group_id] = len(group_to_index)
            encoded_groups.append(group_to_index[group_id])
        membership = torch.zeros(
            len(group_to_index),
            len(self.node_ids),
            dtype=node_size_x.dtype,
            device=weights.device,
        )
        for group_index in range(len(group_to_index)):
            members = [
                index
                for index, encoded_group in enumerate(encoded_groups)
                if encoded_group == group_index
            ]
            member_weights = weights[members]
            total_weight = member_weights.sum()
            if total_weight <= 0:
                raise ValueError("each anchor subgroup must have positive weight")
            membership[group_index, members] = member_weights / total_weight
        self.register_buffer("group_membership", membership)
        self.register_buffer(
            "coordinate_ids",
            torch.cat((self.node_ids, self.num_nodes + self.node_ids)),
        )
        self.group_labels = tuple(group_to_index)

    def forward(self, pos):
        if not len(self.node_ids):
            return pos.sum() * 0
        center_x = pos[self.node_ids] + self.node_size_x[self.node_ids] / 2
        center_y = (
            pos[self.num_nodes + self.node_ids]
            + self.node_size_y[self.node_ids] / 2
        )
        centers = torch.stack((center_x, center_y), dim=1)
        normalized_distance = torch.linalg.vector_norm(
            centers - self.target_centers.to(device=pos.device, dtype=pos.dtype), dim=1
        ) / self.board_diagonal
        losses = functional.smooth_l1_loss(
            normalized_distance,
            torch.zeros_like(normalized_distance),
            beta=self.beta,
            reduction="none",
        )
        membership = self.group_membership.to(device=pos.device, dtype=pos.dtype)
        # Keep board-size normalization without forcing a numerically huge lambda.
        return membership.matmul(losses).mean() * self.board_diagonal


class AdaptiveAnchorWeight:
    """Bounded EMA controller for an anchor-to-wirelength gradient ratio."""

    def __init__(
        self,
        target_ratio,
        update_interval,
        ema_decay,
        min_weight,
        max_weight,
        warmup_iterations,
        ramp_iterations,
    ):
        self.target_ratio = float(target_ratio)
        self.update_interval = int(update_interval)
        self.ema_decay = float(ema_decay)
        self.min_weight = float(min_weight)
        self.max_weight = float(max_weight)
        self.warmup_iterations = int(warmup_iterations)
        self.ramp_iterations = int(ramp_iterations)
        finite_parameters = (
            self.target_ratio,
            self.ema_decay,
            self.min_weight,
            self.max_weight,
        )
        if not all(math.isfinite(value) for value in finite_parameters):
            raise ValueError("anchor weight controller parameters must be finite")
        if self.target_ratio < 0:
            raise ValueError("anchor target gradient ratio must be non-negative")
        if self.update_interval <= 0:
            raise ValueError("anchor weight update interval must be positive")
        if not 0 <= self.ema_decay < 1:
            raise ValueError("anchor weight EMA decay must be in [0, 1)")
        if self.min_weight < 0 or self.max_weight < self.min_weight:
            raise ValueError("invalid anchor weight bounds")
        if self.warmup_iterations < 0 or self.ramp_iterations < 0:
            raise ValueError("anchor warm-up and ramp must be non-negative")
        self.ema_weight = None
        self.last_wirelength_gradient_l1 = None
        self.last_anchor_gradient_l1 = None
        self.last_raw_weight = None
        self.last_bounded_weight = None

    def needs_gradient_refresh(self, iteration):
        return self.ema_weight is None or iteration % self.update_interval == 0

    def _ramp(self, iteration):
        if iteration < self.warmup_iterations:
            return 0.0
        if self.ramp_iterations == 0:
            return 1.0
        return min(
            (iteration - self.warmup_iterations + 1) / self.ramp_iterations,
            1.0,
        )

    def step(
        self,
        iteration,
        wirelength_gradient_l1=None,
        anchor_gradient_l1=None,
        epsilon=1e-30,
    ):
        iteration = int(iteration)
        refreshed = self.needs_gradient_refresh(iteration)
        if refreshed:
            if wirelength_gradient_l1 is None or anchor_gradient_l1 is None:
                raise ValueError("gradient norms are required for an anchor refresh")
            wirelength_gradient_l1 = float(wirelength_gradient_l1)
            anchor_gradient_l1 = float(anchor_gradient_l1)
            if not math.isfinite(wirelength_gradient_l1) or not math.isfinite(
                anchor_gradient_l1
            ):
                raise FloatingPointError("non-finite anchor gradient norm")
            if wirelength_gradient_l1 < 0 or anchor_gradient_l1 < 0:
                raise ValueError("anchor gradient norms must be non-negative")
            if anchor_gradient_l1 <= epsilon:
                raw_weight = self.min_weight
            else:
                raw_weight = (
                    self.target_ratio
                    * wirelength_gradient_l1
                    / anchor_gradient_l1
                )
            bounded_weight = min(
                max(raw_weight, self.min_weight), self.max_weight
            )
            if self.ema_weight is None:
                self.ema_weight = bounded_weight
            else:
                self.ema_weight = (
                    self.ema_decay * self.ema_weight
                    + (1 - self.ema_decay) * bounded_weight
                )
            self.last_wirelength_gradient_l1 = wirelength_gradient_l1
            self.last_anchor_gradient_l1 = anchor_gradient_l1
            self.last_raw_weight = raw_weight
            self.last_bounded_weight = bounded_weight

        # EMA should delay an upward weight change, not preserve stale pressure
        # after the freshly matched weight drops.
        controlled_weight = min(self.ema_weight, self.last_bounded_weight)
        ramp = self._ramp(iteration)
        effective_weight = min(
            max(controlled_weight * ramp, 0.0), self.max_weight
        )
        if self.last_wirelength_gradient_l1 > epsilon:
            effective_ratio = (
                effective_weight
                * self.last_anchor_gradient_l1
                / self.last_wirelength_gradient_l1
            )
        else:
            effective_ratio = 0.0
        return {
            "iteration": iteration,
            "gradient_refreshed": refreshed,
            "target_ratio": self.target_ratio,
            "wirelength_gradient_l1": self.last_wirelength_gradient_l1,
            "anchor_gradient_l1": self.last_anchor_gradient_l1,
            "raw_weight": self.last_raw_weight,
            "bounded_weight": self.last_bounded_weight,
            "ema_weight": self.ema_weight,
            "controlled_weight": controlled_weight,
            "ramp": ramp,
            "effective_weight": effective_weight,
            "effective_ratio": effective_ratio,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
        }


class _InsideDistanceField(nn.Module):
    """Batched sampler for nodes sharing one footprint-aware feasible domain."""

    def __init__(self, constraints, dtype):
        super().__init__()
        domain = constraints[0].domain
        self.register_buffer(
            "node_ids",
            torch.as_tensor(
                [constraint.node_id for constraint in constraints], dtype=torch.long
            ),
        )
        self.register_buffer(
            "node_widths",
            torch.as_tensor(
                [constraint.node_width for constraint in constraints], dtype=dtype
            ),
        )
        self.register_buffer(
            "node_heights",
            torch.as_tensor(
                [constraint.node_height for constraint in constraints], dtype=dtype
            ),
        )
        self.register_buffer(
            "distance_field",
            torch.as_tensor(domain.inside_distance, dtype=dtype)[None, None].contiguous(),
        )
        x_span = float(domain.x_values[-1] - domain.x_values[0])
        y_span = float(domain.y_values[-1] - domain.y_values[0])
        self.x_origin = float(domain.x_values[0])
        self.y_origin = float(domain.y_values[0])
        self.x_scale = 2.0 / x_span if x_span > 0 else 0.0
        self.y_scale = 2.0 / y_span if y_span > 0 else 0.0

    def forward(self, pos, num_nodes):
        center_x = pos[self.node_ids] + self.node_widths / 2
        center_y = pos[num_nodes + self.node_ids] + self.node_heights / 2
        if self.x_scale:
            normalized_x = (center_x - self.x_origin) * self.x_scale - 1
        else:
            normalized_x = torch.zeros_like(center_x)
        if self.y_scale:
            normalized_y = (center_y - self.y_origin) * self.y_scale - 1
        else:
            normalized_y = torch.zeros_like(center_y)
        sampling_grid = torch.stack((normalized_x, normalized_y), dim=1).view(
            -1, 1, 1, 2
        )
        distances = functional.grid_sample(
            self.distance_field.expand(len(self.node_ids), -1, -1, -1),
            sampling_grid,
            mode="bilinear",
            padding_mode="zeros",
            align_corners=True,
        )
        return distances[:, 0, 0, 0]


class SoftKeepInLoss(nn.Module):
    """Differentiable interior-margin barrier over feasible-domain fields."""

    def __init__(self, constraints, num_nodes, margin, tau, dtype=torch.float32):
        super().__init__()
        constraints = tuple(constraints)
        self.num_nodes = int(num_nodes)
        self.margin = float(margin)
        self.tau = float(tau)
        if self.margin < 0:
            raise ValueError("soft keep-in margin must be non-negative")
        if self.tau <= 0:
            raise ValueError("soft keep-in tau must be positive")

        constraints_by_domain = {}
        for constraint in constraints:
            constraints_by_domain.setdefault(id(constraint.domain), []).append(
                constraint
            )
        self.distance_fields = nn.ModuleList(
            _InsideDistanceField(group, dtype)
            for group in constraints_by_domain.values()
        )

    def sampled_inside_distances(self, pos):
        if not self.distance_fields:
            return pos.new_empty(0)
        return torch.cat(
            [field(pos, self.num_nodes) for field in self.distance_fields]
        )

    def forward(self, pos):
        distances = self.sampled_inside_distances(pos)
        if not distances.numel():
            return pos.sum() * 0
        normalized_margin = (self.margin - distances) / self.tau
        return functional.softplus(normalized_margin).square().mean()


class FootprintCollisionLoss(nn.Module):
    """Side-local footprint clearance barrier sampled from a packed SDF atlas."""

    def __init__(
        self,
        atlas,
        first_node_ids,
        second_node_ids,
        active_node_ids,
        relative_signs,
        field_origins,
        atlas_offsets,
        field_sizes,
        node_size_x,
        node_size_y,
        num_nodes,
        grid,
        margin,
        tau,
        units_per_mm=1.0,
    ):
        super().__init__()
        dtype = node_size_x.dtype
        self.register_buffer("atlas", torch.as_tensor(atlas, dtype=dtype).contiguous())
        self.register_buffer(
            "first_node_ids", torch.as_tensor(first_node_ids, dtype=torch.long)
        )
        self.register_buffer(
            "second_node_ids", torch.as_tensor(second_node_ids, dtype=torch.long)
        )
        self.register_buffer(
            "relative_signs", torch.as_tensor(relative_signs, dtype=dtype)
        )
        self.register_buffer(
            "field_origins", torch.as_tensor(field_origins, dtype=dtype).reshape(-1, 2)
        )
        self.register_buffer(
            "atlas_offsets", torch.as_tensor(atlas_offsets, dtype=torch.long).reshape(-1, 2)
        )
        self.register_buffer(
            "field_sizes", torch.as_tensor(field_sizes, dtype=torch.long).reshape(-1, 2)
        )
        self.register_buffer("node_size_x", node_size_x.detach().clone())
        self.register_buffer("node_size_y", node_size_y.detach().clone())
        active_node_ids = torch.as_tensor(active_node_ids, dtype=torch.long)
        self.register_buffer("active_node_ids", active_node_ids)
        self.register_buffer(
            "coordinate_ids",
            torch.cat((active_node_ids, int(num_nodes) + active_node_ids)),
        )
        self.num_nodes = int(num_nodes)
        self.grid = float(grid)
        self.margin = float(margin)
        self.tau = float(tau)
        self.units_per_mm = float(units_per_mm)
        self.normalization_count = max(len(active_node_ids), 1)
        if self.grid <= 0:
            raise ValueError("collision SDF grid must be positive")
        if self.margin < 0:
            raise ValueError("collision margin must be non-negative")
        if self.tau <= 0:
            raise ValueError("collision tau must be positive")
        if self.units_per_mm <= 0:
            raise ValueError("collision units-per-mm scale must be positive")
        pair_count = len(self.first_node_ids)
        expected_pair_shapes = {
            "second_node_ids": self.second_node_ids.shape,
            "relative_signs": self.relative_signs.shape,
            "field_origins": self.field_origins.shape[:1],
            "atlas_offsets": self.atlas_offsets.shape[:1],
            "field_sizes": self.field_sizes.shape[:1],
        }
        invalid = [
            name
            for name, shape in expected_pair_shapes.items()
            if shape != (pair_count,)
        ]
        if invalid:
            raise ValueError("collision pair metadata has inconsistent shapes: %s" % invalid)
        if self.atlas.ndim != 2 or min(self.atlas.shape) < 2:
            raise ValueError("collision SDF atlas must be a two-dimensional grid")

    def _centers(self, pos, node_ids):
        return torch.stack(
            (
                pos[node_ids] + self.node_size_x[node_ids] / 2,
                pos[self.num_nodes + node_ids]
                + self.node_size_y[node_ids] / 2,
            ),
            dim=1,
        )

    def sampled_clearances(self, pos):
        if not len(self.first_node_ids):
            return pos.new_empty(0)
        relative = self._centers(pos, self.second_node_ids) - self._centers(
            pos, self.first_node_ids
        )
        relative = relative * self.relative_signs[:, None]
        local = (relative - self.field_origins) / self.grid
        field_widths = self.field_sizes[:, 0]
        field_heights = self.field_sizes[:, 1]
        inside = (
            (local[:, 0] >= 0)
            & (local[:, 0] <= field_widths - 1)
            & (local[:, 1] >= 0)
            & (local[:, 1] <= field_heights - 1)
        )

        atlas_x = local[:, 0] + self.atlas_offsets[:, 0]
        atlas_y = local[:, 1] + self.atlas_offsets[:, 1]
        floor_x = torch.floor(atlas_x)
        floor_y = torch.floor(atlas_y)
        fraction_x = atlas_x - floor_x
        fraction_y = atlas_y - floor_y
        column0 = floor_x.long().clamp(0, self.atlas.shape[1] - 1)
        row0 = floor_y.long().clamp(0, self.atlas.shape[0] - 1)
        column1 = (column0 + 1).clamp(max=self.atlas.shape[1] - 1)
        row1 = (row0 + 1).clamp(max=self.atlas.shape[0] - 1)
        flat_atlas = self.atlas.reshape(-1)
        atlas_width = self.atlas.shape[1]
        value00 = flat_atlas[row0 * atlas_width + column0]
        value10 = flat_atlas[row0 * atlas_width + column1]
        value01 = flat_atlas[row1 * atlas_width + column0]
        value11 = flat_atlas[row1 * atlas_width + column1]
        upper = value00 + fraction_x * (value10 - value00)
        lower = value01 + fraction_x * (value11 - value01)
        sampled = upper + fraction_y * (lower - upper)
        far_clearance = self.margin + 20 * self.tau
        return torch.where(inside, sampled, sampled.new_full((), far_clearance))

    def forward(self, pos):
        clearances = self.sampled_clearances(pos)
        if not clearances.numel():
            return pos.sum() * 0
        normalized_margin = (self.margin - clearances) / self.tau
        return functional.softplus(normalized_margin).square().sum() / (
            self.normalization_count
        )

    def diagnostics(self, pos):
        """Synchronize bounded barrier metrics outside the autograd path."""
        with torch.no_grad():
            clearances = self.sampled_clearances(pos)
            if not clearances.numel():
                return {
                    "evaluated_pair_count": 0,
                    "active_pair_count": 0,
                    "penetrating_pair_count": 0,
                    "minimum_clearance": None,
                    "minimum_clearance_mm": None,
                    "loss": 0.0,
                }
            normalized_margin = (self.margin - clearances) / self.tau
            loss = functional.softplus(normalized_margin).square().sum() / (
                self.normalization_count
            )
            minimum_clearance = float(clearances.min().item())
            return {
                "evaluated_pair_count": int(clearances.numel()),
                "active_pair_count": int(
                    torch.count_nonzero(
                        clearances < self.margin + 12 * self.tau
                    ).item()
                ),
                "penetrating_pair_count": int(
                    torch.count_nonzero(clearances < 0).item()
                ),
                "minimum_clearance": minimum_clearance,
                "minimum_clearance_mm": minimum_clearance / self.units_per_mm,
                "loss": float(loss.item()),
            }
