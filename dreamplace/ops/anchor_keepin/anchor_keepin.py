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

        ramp = self._ramp(iteration)
        effective_weight = min(
            max(self.ema_weight * ramp, 0.0), self.max_weight
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
