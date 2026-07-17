"""Small PyTorch reference losses for feature-gated PCB constraints."""

from __future__ import annotations

import math

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


class SoftKeepInLoss(nn.Module):
    """Piecewise differentiable distance penalty outside feasible domains."""

    def __init__(self, constraints, num_nodes, tau):
        super().__init__()
        self.constraints = tuple(constraints)
        self.num_nodes = int(num_nodes)
        self.tau = float(tau)
        if self.tau <= 0:
            raise ValueError("soft keep-in tau must be positive")

    def forward(self, pos):
        losses = []
        for constraint in self.constraints:
            node_id = constraint.node_id
            center = torch.stack(
                (
                    pos[node_id] + constraint.node_width / 2,
                    pos[self.num_nodes + node_id] + constraint.node_height / 2,
                )
            )
            detached_center = tuple(center.detach().cpu().tolist())
            if constraint.domain.contains(detached_center):
                losses.append(center.sum() * 0)
                continue
            projected, _ = constraint.domain.project(detached_center)
            target = center.new_tensor(projected)
            distance = torch.linalg.vector_norm(center - target)
            stabilized = functional.softplus(distance / self.tau) - math.log(2.0)
            losses.append(stabilized.square())
        if not losses:
            return pos.sum() * 0
        return torch.stack(losses).mean()
