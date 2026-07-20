"""PyTorch losses for feature-gated PCB constraints."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as functional


class AnchorKeepInLoss(nn.Module):
    """Smooth-L1 loss on center distance to per-component anchor targets."""

    def __init__(
        self,
        node_ids,
        target_centers,
        node_size_x,
        node_size_y,
        num_nodes,
        board_diagonal,
        weights=None,
        beta=1.0,
    ):
        super().__init__()
        self.register_buffer("node_ids", torch.as_tensor(node_ids, dtype=torch.long))
        self.register_buffer(
            "target_centers", torch.as_tensor(target_centers, dtype=node_size_x.dtype)
        )
        self.register_buffer("node_size_x", node_size_x.detach().clone())
        self.register_buffer("node_size_y", node_size_y.detach().clone())
        if weights is None:
            weights = torch.ones(len(self.node_ids), dtype=node_size_x.dtype)
        self.register_buffer("weights", torch.as_tensor(weights, dtype=node_size_x.dtype))
        self.num_nodes = int(num_nodes)
        self.board_diagonal = float(board_diagonal)
        self.beta = float(beta)
        if self.board_diagonal <= 0:
            raise ValueError("board diagonal must be positive")
        if self.target_centers.shape != (len(self.node_ids), 2):
            raise ValueError("target_centers must have shape (N, 2)")

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
        return (losses * self.weights.to(device=pos.device, dtype=pos.dtype)).mean()


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
