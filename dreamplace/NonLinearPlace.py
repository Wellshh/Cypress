# Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

##
# @file   NonLinearPlace.py
# @author Yibo Lin
# @date   Jul 2018
# @brief  Nonlinear placement engine to be called with parameters and placement database
#

import os
import sys
import time
import pickle
import numpy as np
import logging
import torch
from torch.optim.lr_scheduler import ExponentialLR
import gzip
import copy
import json
import math
import matplotlib.pyplot as plt

if sys.version_info[0] < 3:
    import cPickle as pickle
else:
    import _pickle as pickle
import dreamplace.BasicPlace as BasicPlace
import dreamplace.PlaceObj as PlaceObj
import dreamplace.NesterovAcceleratedGradientOptimizer as NesterovAcceleratedGradientOptimizer
import dreamplace.EvalMetrics as EvalMetrics
import pdb
import dreamplace.ops.fence_region.fence_region as fence_region
import dreamplace.ops.place_io.place_io_cpp as place_io_cpp
from dreamplace.constraints.exact_step_guard import (
    ExactAcceptedStepGuard,
    ExactStepGuardFailure,
    ExactValidationProvenance,
)
from dreamplace.constraints.exact_contact_projection import (
    AUTHORITY_SEARCH_STRATEGIES,
    EXHAUSTIVE_AUTHORITY_SEARCH,
    PAIRWISE_FACTORIZED_AUTHORITY_SEARCH,
    CONTACT_PROJECTION_MODES,
    PROPOSAL_AUTHORITY_MODES,
    ExactContactProjector,
)


def _placement_displacement_stats(
    before, after, num_nodes, include_node_ids=True
):
    """Measure per-node Euclidean displacement in a concatenated position tensor."""
    with torch.no_grad():
        delta_x = after[:num_nodes] - before[:num_nodes]
        delta_y = after[num_nodes : num_nodes * 2] - before[
            num_nodes : num_nodes * 2
        ]
        distances = torch.sqrt(delta_x.square() + delta_y.square())
        changed = torch.nonzero(distances > 0, as_tuple=False).flatten()
        if not changed.numel():
            return {
                "changed_node_count": 0,
                "mean_distance": 0.0,
                "max_distance": 0.0,
                "node_ids": (),
            }
        changed_distances = distances.index_select(0, changed)
        return {
            "changed_node_count": int(changed.numel()),
            "mean_distance": float(changed_distances.mean().item()),
            "max_distance": float(changed_distances.max().item()),
            "node_ids": (
                tuple(int(node_id) for node_id in changed.cpu().tolist())
                if include_node_ids
                else ()
            ),
        }


def _placement_distance_vector(before, after, num_nodes):
    """Return Euclidean displacement for every node."""
    with torch.no_grad():
        delta_x = after[:num_nodes] - before[:num_nodes]
        delta_y = after[num_nodes : num_nodes * 2] - before[
            num_nodes : num_nodes * 2
        ]
        return torch.sqrt(delta_x.square() + delta_y.square())


def _distance_vector_summary(distances, node_ids, include_quantiles=False):
    """Summarize a distance vector over one stable node group."""
    if not node_ids:
        return {
            "node_count": 0,
            "changed_node_count": 0,
            "mean_distance": 0.0,
            "max_distance": 0.0,
        }
    indices = torch.as_tensor(
        node_ids, dtype=torch.long, device=distances.device
    )
    selected = distances.index_select(0, indices).double()
    result = {
        "node_count": len(node_ids),
        "changed_node_count": int(torch.count_nonzero(selected).item()),
        "mean_distance": float(selected.mean().item()),
        "max_distance": float(selected.max().item()),
    }
    if include_quantiles:
        values = selected.detach().cpu().numpy()
        result.update(
            {
                "total_distance": float(values.sum()),
                "median_distance": float(np.percentile(values, 50)),
                "p90_distance": float(np.percentile(values, 90)),
            }
        )
    return result


def _scale_distance_summary(summary, scale):
    return {
        key: (
            value / scale
            if key.endswith("_distance") and value is not None
            else value
        )
        for key, value in summary.items()
    }


def _serialize_collision_pair_diagnostics(data, placedb, units_per_mm):
    """Convert bounded tensor contact diagnostics into stable JSON rows."""
    units_per_mm = float(units_per_mm)
    if units_per_mm <= 0:
        raise ValueError("collision diagnostic scale must be positive")
    host = {
        key: value.detach().cpu().tolist() if torch.is_tensor(value) else value
        for key, value in data.items()
    }

    def node_name(node_id):
        value = placedb.node_names[int(node_id)]
        return value.decode() if isinstance(value, bytes) else str(value)

    def optional_value(key, index):
        values = host[key]
        return float(values[index]) if values else None

    def optional_vector(key, index):
        values = host[key]
        return [float(value) for value in values[index]] if values else None

    rows = []
    for index, pair_index in enumerate(host["pair_indices"]):
        first_node_id = int(host["first_node_ids"][index])
        second_node_id = int(host["second_node_ids"][index])
        proposal_displacement = optional_value(
            "proposal_normal_displacement", index
        )
        accepted_displacement = optional_value(
            "accepted_normal_displacement", index
        )
        proposal_clearance = optional_value("proposal_clearances", index)
        accepted_clearance = optional_value("accepted_clearances", index)
        clearance = float(host["clearances"][index])
        rows.append(
            {
                "pair_index": int(pair_index),
                "first_node_id": first_node_id,
                "first_refdes": node_name(first_node_id),
                "first_active": bool(host["first_active"][index]),
                "second_node_id": second_node_id,
                "second_refdes": node_name(second_node_id),
                "second_active": bool(host["second_active"][index]),
                "clearance": clearance,
                "clearance_mm": clearance / units_per_mm,
                "clearance_gradient": [
                    float(value)
                    for value in host["clearance_gradients"][index]
                ],
                "normal": [float(value) for value in host["normals"][index]],
                "normal_valid": bool(host["normal_valid"][index]),
                "base_raw_normal_descent": optional_value(
                    "base_raw_normal_descent", index
                ),
                "collision_raw_normal_descent": optional_value(
                    "collision_raw_normal_descent", index
                ),
                "total_raw_normal_descent": optional_value(
                    "total_raw_normal_descent", index
                ),
                "optimizer_gradient_normal_descent": optional_value(
                    "optimizer_gradient_normal_descent", index
                ),
                "proposal_normal_displacement": proposal_displacement,
                "proposal_normal_displacement_mm": (
                    proposal_displacement / units_per_mm
                    if proposal_displacement is not None
                    else None
                ),
                "proposal_relative_displacement": optional_vector(
                    "proposal_relative_displacement", index
                ),
                "proposal_relative_displacement_mm": (
                    [
                        value / units_per_mm
                        for value in host["proposal_relative_displacement"][
                            index
                        ]
                    ]
                    if host["proposal_relative_displacement"]
                    else None
                ),
                "proposal_clearance": proposal_clearance,
                "proposal_clearance_mm": (
                    proposal_clearance / units_per_mm
                    if proposal_clearance is not None
                    else None
                ),
                "proposal_normal": optional_vector(
                    "proposal_normals", index
                ),
                "proposal_normal_valid": (
                    bool(host["proposal_normal_valid"][index])
                    if host["proposal_normal_valid"]
                    else None
                ),
                "accepted_normal_displacement": accepted_displacement,
                "accepted_normal_displacement_mm": (
                    accepted_displacement / units_per_mm
                    if accepted_displacement is not None
                    else None
                ),
                "accepted_relative_displacement": optional_vector(
                    "accepted_relative_displacement", index
                ),
                "accepted_relative_displacement_mm": (
                    [
                        value / units_per_mm
                        for value in host["accepted_relative_displacement"][
                            index
                        ]
                    ]
                    if host["accepted_relative_displacement"]
                    else None
                ),
                "accepted_clearance": accepted_clearance,
                "accepted_clearance_mm": (
                    accepted_clearance / units_per_mm
                    if accepted_clearance is not None
                    else None
                ),
                "accepted_normal": optional_vector(
                    "accepted_normals", index
                ),
                "accepted_normal_valid": (
                    bool(host["accepted_normal_valid"][index])
                    if host["accepted_normal_valid"]
                    else None
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            row["proposal_normal_displacement"] is None,
            row["proposal_normal_displacement"] or 0.0,
            row["first_refdes"],
            row["second_refdes"],
        )
    )
    proposal_values = [
        row["proposal_normal_displacement"]
        for row in rows
        if row["proposal_normal_displacement"] is not None
    ]
    accepted_values = [
        row["accepted_normal_displacement"]
        for row in rows
        if row["accepted_normal_displacement"] is not None
    ]
    return {
        "active_pair_count": len(rows),
        "valid_normal_count": sum(row["normal_valid"] for row in rows),
        "inward_proposal_pair_count": sum(
            value < 0 for value in proposal_values
        ),
        "minimum_proposal_normal_displacement": (
            min(proposal_values) if proposal_values else None
        ),
        "minimum_proposal_normal_displacement_mm": (
            min(proposal_values) / units_per_mm if proposal_values else None
        ),
        "inward_accepted_pair_count": sum(
            value < 0 for value in accepted_values
        ),
        "minimum_accepted_normal_displacement": (
            min(accepted_values) if accepted_values else None
        ),
        "minimum_accepted_normal_displacement_mm": (
            min(accepted_values) / units_per_mm if accepted_values else None
        ),
        "pairs": rows,
    }


class _NativeDisplacementTracker:
    """Accumulate optimizer proposal paths and accepted net displacement."""

    def __init__(self, num_nodes, node_groups):
        self.num_nodes = int(num_nodes)
        self.node_groups = {
            str(name): tuple(int(node_id) for node_id in node_ids)
            for name, node_ids in node_groups.items()
        }
        self.step_count = 0
        self._initial_position = None
        self._latest_position = None
        self._proposal_path = None
        self._accepted_path = None

    def record_step(self, origin, proposal, accepted):
        if origin is None or proposal is None or accepted is None:
            raise RuntimeError(
                "optimizer step is missing proposal/projection coordinates"
            )
        proposal_distances = _placement_distance_vector(
            origin, proposal, self.num_nodes
        )
        accepted_distances = _placement_distance_vector(
            origin, accepted, self.num_nodes
        )
        if self._initial_position is None:
            self._initial_position = origin.detach().clone()
            self._proposal_path = torch.zeros_like(proposal_distances)
            self._accepted_path = torch.zeros_like(accepted_distances)
        self._proposal_path.add_(proposal_distances)
        self._accepted_path.add_(accepted_distances)
        self._latest_position = accepted.detach().clone()
        self.step_count += 1
        return {
            name: {
                "proposal": _distance_vector_summary(
                    proposal_distances, node_ids
                ),
                "accepted": _distance_vector_summary(
                    accepted_distances, node_ids
                ),
            }
            for name, node_ids in self.node_groups.items()
        }

    def summary(self, units_per_mm=None):
        if self._initial_position is None:
            net_displacement = torch.zeros(self.num_nodes, dtype=torch.float64)
            proposal_path = net_displacement.clone()
            accepted_path = net_displacement.clone()
        else:
            net_displacement = _placement_distance_vector(
                self._initial_position,
                self._latest_position,
                self.num_nodes,
            )
            proposal_path = self._proposal_path
            accepted_path = self._accepted_path
        groups = {}
        for name, node_ids in self.node_groups.items():
            group = {
                "proposal_path": _distance_vector_summary(
                    proposal_path, node_ids, include_quantiles=True
                ),
                "accepted_path": _distance_vector_summary(
                    accepted_path, node_ids, include_quantiles=True
                ),
                "net_displacement": _distance_vector_summary(
                    net_displacement, node_ids, include_quantiles=True
                ),
            }
            if units_per_mm is not None:
                group.update(
                    {
                        "%s_mm" % key: _scale_distance_summary(value, units_per_mm)
                        for key, value in group.items()
                    }
                )
            groups[name] = group
        return {
            "step_count": self.step_count,
            "coordinate_units": "cypress",
            "units_per_mm": units_per_mm,
            "groups": groups,
        }


class _CompositeProjector:
    """Apply board and footprint constraints at explicit optimizer boundaries."""

    def __init__(
        self,
        board_projector,
        region_projector,
        num_nodes,
        contact_projector=None,
    ):
        self.board_projector = board_projector
        self.region_projector = region_projector
        self.num_nodes = int(num_nodes)
        self.contact_projector = contact_projector
        self._proposal_origin = None
        self.reset_step()

    def reset_step(self):
        self._proposal_origin = None
        self._proposal_position = None
        self._accepted_position = None
        self._last_proposal = {
            "changed_node_count": 0,
            "mean_distance": 0.0,
            "max_distance": 0.0,
            "node_ids": (),
        }
        self._last_correction = dict(self._last_proposal)
        self._last_contact_projection = None
        self._proposal_validation_provenance = None
        self._accepted_validation_provenance = None
        self._projected_node_ids = set()
        self._projection_event_count = 0
        self._projection_distance_sum = 0.0
        self._projection_max_distance = 0.0

    def begin_step(self, position):
        self.reset_step()
        self._proposal_origin = position.detach().clone()

    def _apply_hard_constraints(self, position):
        self.board_projector(position)
        if self.region_projector is not None:
            return self.region_projector(position)
        return None

    def __call__(self, position):
        track_step = self._proposal_origin is not None
        before_projection = position.detach().clone() if track_step else None
        if track_step:
            self._last_proposal = _placement_displacement_stats(
                self._proposal_origin,
                before_projection,
                self.num_nodes,
                include_node_ids=False,
            )
            self._proposal_position = before_projection

        region_stats = self._apply_hard_constraints(position)

        if not track_step:
            return region_stats
        if self.contact_projector is not None:
            contact_input = position.detach().clone()
            self._last_contact_projection = self.contact_projector(
                self._proposal_origin,
                position,
                self._apply_hard_constraints,
            )
            consume_provenance = getattr(
                self.contact_projector,
                "consume_validation_provenance",
                None,
            )
            provenance = (
                consume_provenance()
                if consume_provenance is not None
                else None
            )
            if provenance is not None:
                if not isinstance(provenance, dict) or set(provenance) != {
                    "initial",
                    "final",
                }:
                    raise RuntimeError(
                        "contact validation provenance is malformed"
                    )
                initial = provenance["initial"]
                final = provenance["final"]
                if not isinstance(
                    initial, ExactValidationProvenance
                ) or not isinstance(final, ExactValidationProvenance):
                    raise RuntimeError(
                        "contact validation provenance has invalid entries"
                    )
                if (
                    initial.position.shape != contact_input.shape
                    or initial.position.dtype != contact_input.dtype
                    or initial.position.device != contact_input.device
                    or not torch.equal(initial.position, contact_input)
                ):
                    raise RuntimeError(
                        "contact initial validation provenance is stale"
                    )
                if (
                    final.position.shape != position.shape
                    or final.position.dtype != position.dtype
                    or final.position.device != position.device
                    or not torch.equal(final.position, position)
                ):
                    raise RuntimeError(
                        "contact final validation provenance is stale"
                    )
                if torch.equal(before_projection, contact_input):
                    self._proposal_validation_provenance = initial
                self._accepted_validation_provenance = final
        correction = _placement_displacement_stats(
            before_projection, position.detach(), self.num_nodes
        )
        self._last_correction = correction
        self._projected_node_ids.update(correction["node_ids"])
        self._projection_event_count += correction["changed_node_count"]
        self._projection_distance_sum += (
            correction["mean_distance"] * correction["changed_node_count"]
        )
        self._projection_max_distance = max(
            self._projection_max_distance, correction["max_distance"]
        )
        self._accepted_position = position.detach().clone()
        return region_stats

    def finish_step(self):
        summary = {
            "proposal": self._last_proposal,
            "accepted_projection": self._last_correction,
            "projected_node_ids": tuple(sorted(self._projected_node_ids)),
            "projection_event_count": self._projection_event_count,
            "projection_mean_distance": (
                self._projection_distance_sum / self._projection_event_count
                if self._projection_event_count
                else 0.0
            ),
            "projection_max_distance": self._projection_max_distance,
            "contact_projection": self._last_contact_projection,
            "proposal_validation_provenance": (
                self._proposal_validation_provenance
            ),
            "accepted_validation_provenance": (
                self._accepted_validation_provenance
            ),
            "origin_position": self._proposal_origin,
            "proposal_position": self._proposal_position,
            "accepted_position": self._accepted_position,
        }
        self.reset_step()
        return summary


class NonLinearPlace(BasicPlace.BasicPlace):
    """
    @brief Nonlinear placement engine.
    It takes parameters and placement database and runs placement flow.
    """

    def __init__(self, params, placedb):
        """
        @brief initialization.
        @param params parameters
        @param placedb placement database
        """
        super(NonLinearPlace, self).__init__(params, placedb)

    def __call__(self, params, placedb):
        """
        @brief Top API to solve placement.
        @param params parameters
        @param placedb placement database
        """
        iteration = 0
        all_metrics = []
        lrs = []
        scheduler = None
        plot_frequency = 100
        native_models = []
        native_execution = {
            "nonlinear_place_executed": bool(params.global_place_flag),
            "place_obj_executed": False,
            "backward_call_count": 0,
            "optimizer_names": [],
            "optimizer_step_count": 0,
            "optimizer_changed_step_count": 0,
            "proposal_changed_node_events": 0,
            "proposal_max_distance": 0.0,
            "projection_node_events": 0,
            "projection_search_node_events": 0,
            "projection_max_distance": 0.0,
            "learning_rate_updates": [],
            "optimizer_steps": [],
            "device": str(self.data_collections.pos[0].device),
        }
        displacement_groups = {
            "movable": tuple(range(placedb.num_movable_nodes)),
        }
        if self.anchor_keepin_context is not None:
            displacement_groups["constrained"] = tuple(
                constraint.node_id
                for constraint in self.anchor_keepin_context.constraints
            )
        displacement_tracker = _NativeDisplacementTracker(
            placedb.num_nodes, displacement_groups
        )
        net_crossing_enabled = bool(
            params.net_crossing_flag and float(params.net_crossing_weight) != 0.0
        )
        exact_overlap_interval = int(
            getattr(params, "exact_overlap_diagnostic_interval", 0)
        )
        exact_step_guard_enabled = bool(
            getattr(params, "exact_step_guard_flag", False)
        )
        exact_step_guard_backoff = float(
            getattr(params, "exact_step_guard_backoff", 0.5)
        )
        exact_step_guard_max_retries = int(
            getattr(params, "exact_step_guard_max_retries", 4)
        )
        collision_pair_diagnostics_enabled = bool(
            getattr(params, "collision_pair_diagnostics_flag", False)
        )
        exact_contact_projection_enabled = bool(
            getattr(params, "exact_contact_projection_flag", False)
        )
        exact_contact_projection_mode = str(
            getattr(
                params,
                "exact_contact_projection_mode",
                "component_consensus",
            )
        )
        exact_contact_projection_max_iterations = int(
            getattr(params, "exact_contact_projection_max_iterations", 8)
        )
        exact_contact_projection_max_nodes = int(
            getattr(params, "exact_contact_projection_max_nodes", 32)
        )
        exact_contact_projection_max_cover_component_nodes = int(
            getattr(
                params,
                "exact_contact_projection_max_cover_component_nodes",
                16,
            )
        )
        exact_contact_projection_max_authority_states = int(
            getattr(
                params,
                "exact_contact_projection_max_authority_states",
                4096,
            )
        )
        exact_contact_projection_authority_search_strategy = str(
            getattr(
                params,
                "exact_contact_projection_authority_search_strategy",
                EXHAUSTIVE_AUTHORITY_SEARCH,
            )
        )
        exact_contact_topology_tiebreak_enabled = bool(
            getattr(params, "exact_contact_topology_tiebreak_flag", False)
        )
        exact_contact_topology_min_net_degree = int(
            getattr(params, "exact_contact_topology_min_net_degree", 32)
        )
        if exact_overlap_interval < 0:
            raise ValueError("exact overlap diagnostic interval must be non-negative")
        if exact_overlap_interval and self.anchor_keepin_context is None:
            raise ValueError(
                "exact overlap diagnostics require anchor/keep-in context"
            )
        if exact_step_guard_enabled:
            if self.anchor_keepin_context is None:
                raise ValueError("exact step guard requires anchor/keep-in context")
            if not getattr(params, "footprint_collision_loss_flag", False):
                raise ValueError("exact step guard requires footprint collision loss")
            if getattr(params, "enable_rotation", False):
                raise ValueError("exact step guard does not support rotation")
            if (
                not math.isfinite(exact_step_guard_backoff)
                or not 0 < exact_step_guard_backoff < 1
            ):
                raise ValueError("exact step guard backoff must be in (0, 1)")
            if exact_step_guard_max_retries < 0:
                raise ValueError("exact step guard retries must be non-negative")
            native_execution.update(
                {
                    "exact_step_guard_enabled": True,
                    "exact_step_guard_backoff": exact_step_guard_backoff,
                    "exact_step_guard_max_retries": exact_step_guard_max_retries,
                    "exact_step_guard_attempts": [],
                    "exact_step_guard_accepted_step_count": 0,
                    "exact_step_guard_rejected_attempt_count": 0,
                    "exact_step_guard_overhead_seconds": 0.0,
                    "exact_step_guard_optimizer_attempt_seconds": 0.0,
                }
            )
        if collision_pair_diagnostics_enabled and not exact_step_guard_enabled:
            raise ValueError(
                "collision pair diagnostics require the exact step guard"
            )
        if exact_contact_projection_enabled and not exact_step_guard_enabled:
            raise ValueError(
                "exact contact projection requires the exact step guard"
            )
        if exact_contact_projection_max_iterations <= 0:
            raise ValueError(
                "exact contact projection iterations must be positive"
            )
        if exact_contact_projection_max_nodes < 2:
            raise ValueError(
                "exact contact projection node limit must be at least two"
            )
        if exact_contact_projection_mode not in CONTACT_PROJECTION_MODES:
            raise ValueError(
                "unknown exact contact projection mode: %s"
                % exact_contact_projection_mode
            )
        if exact_contact_projection_max_cover_component_nodes < 2:
            raise ValueError(
                "exact contact projection cover component limit must be at "
                "least two"
            )
        if (
            exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES
            and exact_contact_projection_max_authority_states <= 0
        ):
            raise ValueError(
                "exact contact projection authority state limit must be positive"
            )
        if (
            exact_contact_projection_authority_search_strategy
            not in AUTHORITY_SEARCH_STRATEGIES
        ):
            raise ValueError(
                "unknown exact contact projection authority search strategy: %s"
                % exact_contact_projection_authority_search_strategy
            )
        if (
            exact_contact_projection_authority_search_strategy
            != EXHAUSTIVE_AUTHORITY_SEARCH
            and exact_contact_projection_mode not in PROPOSAL_AUTHORITY_MODES
        ):
            raise ValueError(
                "factorized authority search requires proposal authority mode"
            )
        if exact_contact_topology_min_net_degree < 2:
            raise ValueError(
                "exact contact topology minimum net degree must be at least two"
            )
        if exact_contact_topology_tiebreak_enabled:
            if not exact_contact_projection_enabled:
                raise ValueError(
                    "contact topology tie-break requires exact contact projection"
                )
            if (
                exact_contact_projection_mode
                != "protected_proposal_authority_search"
            ):
                raise ValueError(
                    "contact topology tie-break requires protected proposal "
                    "authority mode"
                )
        if exact_contact_projection_enabled:
            native_execution.update(
                {
                    "exact_contact_projection_enabled": True,
                    "exact_contact_projection_mode": (
                        exact_contact_projection_mode
                    ),
                    "exact_contact_projection_max_iterations": (
                        exact_contact_projection_max_iterations
                    ),
                    "exact_contact_projection_max_nodes": (
                        exact_contact_projection_max_nodes
                    ),
                    "exact_contact_projection_max_cover_component_nodes": (
                        exact_contact_projection_max_cover_component_nodes
                    ),
                    "exact_contact_projection_node_limit_basis": (
                        "cumulative_corrected_active_nodes"
                    ),
                }
            )
            if exact_contact_projection_mode in PROPOSAL_AUTHORITY_MODES:
                native_execution[
                    "exact_contact_projection_max_authority_states"
                ] = exact_contact_projection_max_authority_states
                if (
                    exact_contact_projection_authority_search_strategy
                    != EXHAUSTIVE_AUTHORITY_SEARCH
                ):
                    native_execution[
                        "exact_contact_projection_authority_search_strategy"
                    ] = exact_contact_projection_authority_search_strategy
            if exact_contact_topology_tiebreak_enabled:
                native_execution.update(
                    {
                        "exact_contact_topology_tiebreak_enabled": True,
                        "exact_contact_topology_min_net_degree": (
                            exact_contact_topology_min_net_degree
                        ),
                    }
                )
        if exact_overlap_interval:
            native_execution.update(
                {
                    "exact_overlap_diagnostic_interval": exact_overlap_interval,
                    "exact_overlap_diagnostic_seconds": 0.0,
                    "exact_overlap_checkpoints": [],
                }
            )

        def record_exact_overlap(
            stage, accepted_iteration, phase, report=None
        ):
            if report is None:
                started = time.perf_counter()
                report = self.anchor_keepin_context.exact_overlap_report(
                    self.data_collections.pos[0], placedb
                )
                elapsed = time.perf_counter() - started
                source = "diagnostic"
            else:
                elapsed = 0.0
                source = "exact_step_guard"
            checkpoint = {
                "stage": int(stage),
                "iteration": int(accepted_iteration),
                "step": native_execution["optimizer_step_count"],
                "phase": phase,
                "source": source,
                "elapsed_seconds": elapsed,
                **report,
            }
            native_execution["exact_overlap_checkpoints"].append(checkpoint)
            native_execution["exact_overlap_diagnostic_seconds"] += elapsed
            timing = self.anchor_keepin_context.timing
            timing["exact_overlap_diagnostic_seconds"] = (
                timing.get("exact_overlap_diagnostic_seconds", 0.0) + elapsed
            )
            logging.info(
                "exact overlap checkpoint: step=%d overlaps=%d area=%.6g mm^2 "
                "closure=%d keepin_violations=%d",
                checkpoint["step"],
                checkpoint["overlap_pair_count"],
                checkpoint["overlap_area_mm2"],
                checkpoint["conflict_closure_count"],
                checkpoint["keepin_violation_count"],
            )

        optimization_started = time.perf_counter()
        # global placement
        if params.global_place_flag:
            # global placement may run in multiple stages according to user specification
            for stage_index, global_place_params in enumerate(
                params.global_place_stages
            ):

                # we formulate each stage as a 3-nested optimization problem
                # f_gamma(g_density(h(x) ; density weight) ; gamma)
                # Lgamma      Llambda        Lsub
                # When optimizing an inner problem, the outer parameters are fixed.
                # This is a generalization to the eplace/RePlAce approach

                # As global placement may easily diverge, we record the position of best overflow
                best_metric = [None]
                best_pos = [None]

                if params.gpu:
                    torch.cuda.synchronize()
                tt = time.time()
                # construct model and optimizer
                density_weight = 0.0
                # construct placement model
                model = PlaceObj.PlaceObj(
                    density_weight,
                    params,
                    placedb,
                    self.data_collections,
                    self.op_collections,
                    global_place_params,
                ).to(self.data_collections.pos[0].device)
                native_models.append(model)
                native_execution["place_obj_executed"] = True
                optimizer_name = global_place_params["optimizer"]
                native_execution["optimizer_names"].append(optimizer_name.lower())

                # determine optimizer
                position = []
                orient_logits = []
                for name, param in self.named_parameters():
                    if "orient_logits" in name:
                        orient_logits.append(param)
                    else:
                        position.append(param)

                guard_validator = None
                if exact_step_guard_enabled:

                    def guard_validator(candidate):
                        return self.anchor_keepin_context.exact_overlap_report(
                            candidate, placedb
                        )

                contact_projector = None
                if exact_contact_projection_enabled:
                    node_names = [
                        value.decode() if isinstance(value, bytes) else str(value)
                        for value in placedb.node_names[
                            : placedb.num_physical_nodes
                        ]
                    ]
                    collision_op = (
                        self.op_collections.footprint_collision_loss_op
                    )
                    component_validator = None
                    component_edge_validator = None
                    component_projector = None
                    topology_evaluator = None
                    topology_net_ids = ()
                    topology_net_degrees = ()
                    if (
                        exact_contact_projection_mode
                        in PROPOSAL_AUTHORITY_MODES
                    ):
                        constraint_context = self.anchor_keepin_context

                        def component_validator(coordinates, edges):
                            return constraint_context.exact_contact_component_report(
                                coordinates, edges, placedb
                            )

                        def component_edge_validator(coordinates, edges):
                            return constraint_context.exact_contact_component_report(
                                coordinates, edges, placedb
                            )

                        def component_projector(coordinates, active_node_ids):
                            return constraint_context.project_contact_component(
                                coordinates, active_node_ids
                            )

                        if exact_contact_topology_tiebreak_enabled:
                            netpin_start = np.asarray(
                                placedb.flat_net2pin_start_map,
                                dtype=np.int64,
                            )
                            net_degrees = np.diff(netpin_start)
                            topology_net_ids = tuple(
                                int(net_id)
                                for net_id, degree in enumerate(net_degrees)
                                if degree
                                >= exact_contact_topology_min_net_degree
                                and degree < int(params.ignore_net_degree)
                            )
                            topology_net_degrees = tuple(
                                int(net_degrees[net_id])
                                for net_id in topology_net_ids
                            )

                            if topology_net_ids:

                                def topology_evaluator(candidate):
                                    with torch.no_grad():
                                        hpwl_by_net = (
                                            self.op_collections.hpwl_op(
                                                candidate, reduction=False
                                            )
                                        )
                                        rsmt_by_net = (
                                            self.op_collections.rsmt_wl_op(
                                                candidate, reduction=False
                                            )
                                        )
                                        hpwl_index = torch.as_tensor(
                                            topology_net_ids,
                                            dtype=torch.long,
                                            device=hpwl_by_net.device,
                                        )
                                        rsmt_index = torch.as_tensor(
                                            topology_net_ids,
                                            dtype=torch.long,
                                            device=rsmt_by_net.device,
                                        )
                                        return {
                                            "hpwl": float(
                                                hpwl_by_net.index_select(
                                                    0, hpwl_index
                                                )
                                                .sum()
                                                .detach()
                                                .cpu()
                                            ),
                                            "rsmt": float(
                                                rsmt_by_net.index_select(
                                                    0, rsmt_index
                                                )
                                                .sum()
                                                .detach()
                                                .cpu()
                                            ),
                                        }

                            native_execution[
                                "exact_contact_topology_selected_nets"
                            ] = [
                                {"net_id": net_id, "degree": degree}
                                for net_id, degree in zip(
                                    topology_net_ids,
                                    topology_net_degrees,
                                )
                            ]

                    contact_projector = ExactContactProjector(
                        validator=guard_validator,
                        component_validator=component_validator,
                        component_edge_validator=component_edge_validator,
                        component_projector=component_projector,
                        refdes_to_node_id={
                            refdes: node_id
                            for node_id, refdes in enumerate(node_names)
                        },
                        active_node_ids=(
                            collision_op.active_node_ids.detach().cpu().tolist()
                        ),
                        num_nodes=placedb.num_nodes,
                        max_iterations=(
                            exact_contact_projection_max_iterations
                        ),
                        max_contact_nodes=exact_contact_projection_max_nodes,
                        mode=exact_contact_projection_mode,
                        max_cover_component_nodes=(
                            exact_contact_projection_max_cover_component_nodes
                        ),
                        max_authority_states=(
                            exact_contact_projection_max_authority_states
                        ),
                        authority_search_strategy=(
                            exact_contact_projection_authority_search_strategy
                        ),
                        authority_factorization_compatible=(
                            exact_contact_projection_authority_search_strategy
                            == PAIRWISE_FACTORIZED_AUTHORITY_SEARCH
                        ),
                        topology_tiebreak=(
                            exact_contact_topology_tiebreak_enabled
                        ),
                        topology_evaluator=topology_evaluator,
                        topology_net_ids=topology_net_ids,
                        topology_net_degrees=topology_net_degrees,
                        validation_provenance_cache=(
                            exact_contact_projection_authority_search_strategy
                            == PAIRWISE_FACTORIZED_AUTHORITY_SEARCH
                        ),
                    )

                constraint_projector = _CompositeProjector(
                    self.op_collections.move_boundary_op,
                    (
                        self.op_collections.move_region_boundary_op
                        if self.anchor_keepin_context is not None
                        else None
                    ),
                    placedb.num_nodes,
                    contact_projector=contact_projector,
                )

                if optimizer_name.lower() == "adam":
                    optimizer = torch.optim.Adam(position, lr=0)
                elif optimizer_name.lower() == "sgd":
                    optimizer = torch.optim.SGD(position, lr=0)
                elif optimizer_name.lower() == "sgd_momentum":
                    optimizer = torch.optim.SGD(
                        position, lr=0, momentum=0.9, nesterov=False
                    )
                elif optimizer_name.lower() == "sgd_nesterov":
                    optimizer = torch.optim.SGD(
                        position, lr=0, momentum=0.9, nesterov=True
                    )
                elif optimizer_name.lower() == "nesterov":
                    optimizer = NesterovAcceleratedGradientOptimizer.NesterovAcceleratedGradientOptimizer(
                        position,
                        lr=0,
                        obj_and_grad_fn=model.obj_and_grad_fn,
                        constraint_fn=constraint_projector,
                        project_initial_state=(
                            self.anchor_keepin_context is not None
                        ),
                    )
                else:
                    assert 0, "unknown optimizer %s" % (optimizer_name)

                exact_step_guard = None
                if exact_step_guard_enabled:

                    def guard_barrier_diagnostics(candidate):
                        diagnostics = dict(
                            self.op_collections.footprint_collision_loss_op.diagnostics(
                                candidate
                            )
                        )
                        if model.collision_weight_updates:
                            latest = model.collision_weight_updates[-1]
                            diagnostics.update(
                                {
                                    "gradient_l1": latest[
                                        "collision_gradient_l1"
                                    ],
                                    "effective_weight": latest[
                                        "effective_weight"
                                    ],
                                    "effective_gradient_ratio": latest[
                                        "effective_ratio"
                                    ],
                                }
                            )
                        return diagnostics

                    def guard_attempt_metadata(evidence):
                        origin = evidence["origin_position"]
                        proposal_position = evidence["proposal_position"]
                        accepted_position = evidence["accepted_position"]

                        def without_node_ids(statistics):
                            return {
                                key: value
                                for key, value in statistics.items()
                                if key != "node_ids"
                            }

                        metadata = {
                            "proposal_displacement": without_node_ids(
                                _placement_displacement_stats(
                                    origin,
                                    proposal_position,
                                    placedb.num_nodes,
                                )
                            ),
                            "accepted_displacement": without_node_ids(
                                _placement_displacement_stats(
                                    origin,
                                    accepted_position,
                                    placedb.num_nodes,
                                )
                            ),
                            "projection": {
                                "changed_node_count": evidence[
                                    "accepted_projection"
                                ]["changed_node_count"],
                                "mean_distance": evidence[
                                    "accepted_projection"
                                ]["mean_distance"],
                                "max_distance": evidence[
                                    "accepted_projection"
                                ]["max_distance"],
                                "event_count": evidence[
                                    "projection_event_count"
                                ],
                            },
                        }
                        if evidence["contact_projection"] is not None:
                            metadata["contact_projection"] = evidence[
                                "contact_projection"
                            ]
                        if collision_pair_diagnostics_enabled:
                            gradient_components = (
                                model.collision_pair_gradient_components
                            )
                            if gradient_components is None:
                                raise RuntimeError(
                                    "exact guard lacks collision gradient components"
                                )
                            pair_data = self.op_collections.footprint_collision_loss_op.pairwise_diagnostics(
                                origin,
                                proposal=proposal_position,
                                accepted=accepted_position,
                                **gradient_components,
                            )
                            metadata["pair_contacts"] = (
                                _serialize_collision_pair_diagnostics(
                                    pair_data,
                                    placedb,
                                    self.op_collections.footprint_collision_loss_op.units_per_mm,
                                )
                            )
                        return metadata

                    exact_step_guard = ExactAcceptedStepGuard(
                        validator=guard_validator,
                        backoff=exact_step_guard_backoff,
                        max_retries=exact_step_guard_max_retries,
                        barrier_diagnostics=guard_barrier_diagnostics,
                        attempt_metadata=guard_attempt_metadata,
                    )

                if params.enable_rotation:
                    # rot_optimizer = torch.optim.SGD(orient_logits, lr=0)
                    rot_optimizer = torch.optim.Adam(orient_logits, lr=0)
                    # rot_optimizer = NesterovAcceleratedGradientOptimizer.NesterovAcceleratedGradientOptimizer(
                    #     orient_logits,
                    #     lr=0,
                    #     obj_and_grad_fn=model.obj_and_grad_fn,
                    #     constraint_fn=self.op_collections.move_boundary_op,
                    # )

                logging.info("use %s optimizer" % (optimizer_name))
                model.train()
                # defining evaluation ops
                eval_ops = {
                    # "wirelength" : self.op_collections.wirelength_op,
                    # "density" : self.op_collections.density_op,
                    # "objective" : model.obj_fn,
                    # "weight_hpwl": self.op_collections.weight_hpwl_op,
                    "hpwl": self.op_collections.hpwl_op,
                    "overflow": self.op_collections.two_side_density_overflow_op,
                }
                if net_crossing_enabled:
                    eval_ops["net_crossing"] = self.op_collections.net_crossing_op
                if params.routability_opt_flag:
                    eval_ops.update(
                        {
                            "route_utilization": self.op_collections.route_utilization_map_op,
                            "pin_utilization": self.op_collections.pin_utilization_map_op,
                        }
                    )
                if params.macro_overlap_flag:
                    eval_ops.update(
                        {"macro_overlap": self.op_collections.macro_overlap_op}
                    )
                if len(placedb.regions) > 0:
                    eval_ops.update(
                        {
                            "density": self.op_collections.fence_region_density_merged_op,
                            "overflow": self.op_collections.fence_region_density_overflow_merged_op,
                            "goverflow": self.op_collections.density_overflow_op,
                        }
                    )

                # a function to initialize learning rate
                def initialize_learning_rate(pos, reason):
                    constraint_projector(pos)
                    constraint_projector.reset_step()
                    learning_rate = model.estimate_initial_learning_rate(
                        pos,
                        global_place_params["learning_rate"],
                        constraint_fn=constraint_projector,
                    )
                    constraint_projector.reset_step()
                    # update learning rate
                    for param_group in optimizer.param_groups:
                        param_group["lr"] = learning_rate.data
                    lrs.append(optimizer.param_groups[0]["lr"])
                    native_execution["learning_rate_updates"].append(
                        {
                            "stage": stage_index,
                            "reason": reason,
                            "optimizer": optimizer_name.lower(),
                            "requested_learning_rate": float(
                                global_place_params["learning_rate"]
                            ),
                            "effective_learning_rate": float(
                                learning_rate.detach().cpu().item()
                            ),
                        }
                    )

                if iteration == 0:
                    if params.gp_noise_ratio > 0.0 and params.random_center_init_flag:
                        logging.info("add %g%% noise" % (params.gp_noise_ratio * 100))
                        model.op_collections.noise_op(
                            model.data_collections.pos[0], params.gp_noise_ratio
                        )
                    initialize_learning_rate(
                        model.data_collections.pos[0], "initial"
                    )
                    if (
                        exact_overlap_interval
                        and not native_execution["exact_overlap_checkpoints"]
                    ):
                        record_exact_overlap(stage_index, iteration, "initial")
                    if (
                        optimizer_name.lower()
                        in [
                            "sgd",
                            "adam",
                            "sgd_momentum",
                            "sgd_nesterov",
                        ]
                        and "learning_rate_decay" in global_place_params
                    ):
                        scheduler = ExponentialLR(
                            optimizer,
                            gamma=global_place_params["learning_rate_decay"],
                        )
                # the state must be saved after setting learning rate
                initial_state = copy.deepcopy(optimizer.state_dict())

                if params.gpu:
                    torch.cuda.synchronize()
                logging.info(
                    "%s initialization takes %g seconds"
                    % (optimizer_name, (time.time() - tt))
                )

                # as nesterov requires line search, we cannot follow the convention of other solvers
                if optimizer_name.lower() in {
                    "sgd",
                    "adam",
                    "sgd_momentum",
                    "sgd_nesterov",
                }:
                    model.obj_and_grad_fn(model.data_collections.pos[0])
                elif optimizer_name.lower() != "nesterov":
                    assert 0, "unsupported optimizer %s" % (optimizer_name)

                # stopping criteria
                def Lgamma_stop_criterion(Lgamma_step, metrics, stop_mask=None):
                    with torch.no_grad():
                        if len(metrics) > 1:
                            cur_metric = metrics[-1][-1][-1]
                            prev_metric = metrics[-2][-1][-1]
                            ### update stop mask for each fence region
                            # if(stop_mask is not None):
                            #     stop_mask.copy_(cur_metric.overflow < params.stop_overflow)

                            if Lgamma_step > 100 and (
                                ### for fence region, the outer cell overflow decides the stopping of GP
                                (
                                    cur_metric.overflow[-1] < params.stop_overflow
                                    and cur_metric.hpwl > prev_metric.hpwl
                                )
                                or cur_metric.max_density[-1] < params.target_density
                            ):
                                logging.info(
                                    "Lgamma stopping criteria: %d > 100 and (( %g < 0.1 and %g > %g ) or %g < 1.0)"
                                    % (
                                        Lgamma_step,
                                        cur_metric.overflow[-1],
                                        cur_metric.hpwl,
                                        prev_metric.hpwl,
                                        cur_metric.max_density[-1],
                                    )
                                )
                                return True
                            if (
                                len(placedb.regions) > 0
                                and model.update_mask.sum() == 0
                            ):
                                logging.info(
                                    "All regions stop updating, finish global placement"
                                )
                                return True
                        # a heuristic to detect divergence and stop early
                        """
                        # remove another heuristics
                        if len(metrics) > 50:
                            cur_metric = metrics[-1][-1][-1]
                            prev_metric = metrics[-50][-1][-1]
                            # record HPWL and overflow increase, and check divergence
                            if (
                                cur_metric.overflow[-1] > prev_metric.overflow[-1]
                                and cur_metric.hpwl > best_metric[0].hpwl * 2
                            ):
                                return True
                        """
                        # stop when there is nan or inf numbers, because it will never get better
                        if torch.isinf(metrics[-1][-1][-1].objective) or torch.isnan(
                            metrics[-1][-1][-1].objective
                        ):
                            return True

                        return False

                def Llambda_stop_criterion(
                    Lgamma_step, Llambda_density_weight_step, metrics
                ):
                    with torch.no_grad():
                        if len(metrics) > 1:
                            cur_metric = metrics[-1][-1]
                            prev_metric = metrics[-2][-1]
                            ### for fence regions, the outer cell overflow and max_density decides whether to stop
                            if (
                                cur_metric.overflow[-1] < params.stop_overflow
                                and cur_metric.hpwl > prev_metric.hpwl
                            ) or cur_metric.max_density[-1] < 1.0:
                            # if cur_metric.net_crossing < 1e4:
                                logging.info(
                                    "Llambda stopping criteria: %d and (( %g < 0.1 and %g > %g ) or %g < 1.0)"
                                    % (
                                        Llambda_density_weight_step,
                                        cur_metric.overflow[-1],
                                        cur_metric.hpwl,
                                        prev_metric.hpwl,
                                        cur_metric.max_density[-1],
                                    )
                                )
                                return True
                    return False

                # use a moving average window for stopping criteria, for an example window of 3
                # 0, 1, 2, 3, 4, 5, 6
                #    window2
                #             window1
                moving_avg_window = max(min(model.Lsub_iteration // 2, 3), 1)

                def Lsub_stop_criterion(
                    Lgamma_step, Llambda_density_weight_step, Lsub_step, metrics
                ):
                    with torch.no_grad():
                        if len(metrics) >= moving_avg_window * 2:
                            cur_avg_obj = 0
                            prev_avg_obj = 0
                            for i in range(moving_avg_window):
                                cur_avg_obj += metrics[-1 - i].objective
                                prev_avg_obj += metrics[
                                    -1 - moving_avg_window - i
                                ].objective
                            cur_avg_obj /= moving_avg_window
                            prev_avg_obj /= moving_avg_window
                            threshold = 0.999
                            if cur_avg_obj >= prev_avg_obj * threshold:
                                logging.info(
                                    "Lsub stopping criteria: %d and %g > %g * %g"
                                    % (Lsub_step, cur_avg_obj, prev_avg_obj, threshold)
                                )
                                return True
                    return False

                def one_descent_step(
                    Lgamma_step,
                    Llambda_density_weight_step,
                    Lsub_step,
                    iteration,
                    metrics,
                    stop_mask=None,
                ):
                    t0 = time.time()

                    # metric for this iteration
                    cur_metric = EvalMetrics.EvalMetrics(
                        iteration, (Lgamma_step, Llambda_density_weight_step, Lsub_step)
                    )
                    cur_metric.gamma = model.gamma.data
                    cur_metric.density_weight = model.density_weight.data
                    if net_crossing_enabled:
                        cur_metric.net_crossing_weight = model.net_crossing_weight
                    if params.macro_overlap_flag:
                        cur_metric.macro_overlap_weight = (
                            model.macro_overlap_weight.data
                        )
                    metrics.append(cur_metric)
                    pos = model.data_collections.pos[0]

                    # move any out-of-bound cell back to placement region
                    constraint_projector(pos)
                    constraint_projector.reset_step()

                    # handle multiple density weights for multi-electric field
                    if torch.eq(model.density_weight.mean(), 0.0):
                        model.initialize_density_weight(params, placedb)
                        if model.density_weight.size(0) == 1:
                            logging.info(
                                "density_weight = %.6E" % (model.density_weight.data)
                            )
                        else:
                            logging.info(
                                "density_weight = [%s]"
                                % ", ".join(
                                    [
                                        "%.3E" % i
                                        for i in model.density_weight.cpu()
                                        .numpy()
                                        .tolist()
                                    ]
                                )
                            )

                    # initialize macro overlap weight
                    if params.macro_overlap_flag and torch.eq(
                        model.macro_overlap_weight, 0.0
                    ):
                        model.initialize_macro_overlap_weight(params, placedb)
                        logging.info(
                            "macro_overlap_weight = %.6E"
                            % (model.macro_overlap_weight.data)
                        )

                    optimizer.zero_grad()
                    model.update_anchor_weight(pos, iteration)
                    model.update_collision_weight(pos, iteration)

                    update_orient_cond = (
                        iteration >= 500 and iteration % 100 == 0
                    )
                    
                    if params.enable_rotation and update_orient_cond:
                        best_wl = model.wirelength.data
                        best_nc = (
                            model.net_crossing.data if net_crossing_enabled else None
                        )
                        for _ in range(100):
                            model.op_collections.pin_pos_op.use_best_theta = False
                            model.freeze_pos = True
                            obj_rot, grad_rot = model.obj_and_grad_fn(pos, orient_logits=self.orient_logits)
                            # with torch.no_grad():
                                # grad_rot[1:,:] = 0
                                # grad_rot = 0
                            rot_optimizer.step()
                            # with torch.no_grad():
                                # self.orient_logits -= 1e-5 * grad_rot
                            # if model.wirelength.data < best_wl or model.net_crossing.data < best_nc:
                            net_crossing_improved = (
                                not net_crossing_enabled
                                or model.net_crossing.data < best_nc
                            )
                            if model.wirelength.data < best_wl and net_crossing_improved:
                            # if model.wirelength.data < best_wl:
                                logging.info("update best theta")
                                self.update_best_theta()
                                best_wl = model.wirelength.data
                                if net_crossing_enabled:
                                    best_nc = model.net_crossing.data
                            model.freeze_pos = False
                            model.op_collections.pin_pos_op.use_best_theta = True
                    else:
                        model.op_collections.pin_pos_op.use_best_theta = True
                        model.freeze_pos = False

                    # t1 = time.time()
                    cur_metric.evaluate(placedb, eval_ops, pos, model.data_collections)
                    model.overflow = cur_metric.overflow.data.clone()
                    # logging.debug("evaluation %.3f ms" % ((time.time()-t1)*1000))
                    # t2 = time.time()

                    # as nesterov requires line search, we cannot follow the convention of other solvers
                    if optimizer_name.lower() in [
                        "sgd",
                        "adam",
                        "sgd_momentum",
                        "sgd_nesterov",
                    ]:
                        obj, grad = model.obj_and_grad_fn(pos)
                        cur_metric.objective = obj.data.clone()
                    elif optimizer_name.lower() != "nesterov":
                        assert 0, "unsupported optimizer %s" % (optimizer_name)

                    # plot placement
                    if params.plot_flag and iteration % plot_frequency == 0:
                        cur_pos = self.pos[0].data.clone().cpu().numpy()
                        self.plot(params, placedb, iteration, cur_pos)

                    #### stop updating fence regions that are marked stop, exclude the outer cell !
                    t3 = time.time()
                    optimizer_stepped = (
                        model.update_mask is not None or not model.freeze_pos
                    )
                    guard_result = None

                    def perform_optimizer_attempt():
                        constraint_projector.begin_step(pos)
                        if model.update_mask is not None:
                            pos_bk = pos.data.clone()
                            optimizer.step()

                            for region_id, fence_region_update_flag in enumerate(
                                model.update_mask
                            ):
                                if fence_region_update_flag == 0:
                                    ### don't update cell location in that region
                                    mask = self.op_collections.fence_region_density_ops[
                                        region_id
                                    ].pos_mask
                                    pos.data.masked_scatter_(mask, pos_bk[mask])
                        else:
                            optimizer.step()

                        if optimizer_name.lower() != "nesterov":
                            constraint_projector(pos)
                        evidence = constraint_projector.finish_step()
                        if self.anchor_keepin_context is not None:
                            from dreamplace.constraints.region_projection import (
                                zero_optimizer_state,
                            )

                            zero_optimizer_state(
                                optimizer,
                                pos,
                                evidence["projected_node_ids"],
                                placedb.num_nodes,
                            )
                        return evidence

                    if optimizer_stepped and exact_step_guard is not None:
                        try:
                            guard_result = exact_step_guard.run(
                                pos, optimizer, perform_optimizer_attempt
                            )
                        except ExactStepGuardFailure as error:
                            failure = {
                                "status": "failed",
                                "reason": error.reason,
                                "stage": stage_index,
                                "iteration": iteration,
                                "next_accepted_step": (
                                    native_execution["optimizer_step_count"] + 1
                                ),
                                "optimizer": optimizer_name.lower(),
                                "backoff": exact_step_guard_backoff,
                                "max_retries": exact_step_guard_max_retries,
                                "before": error.before,
                                "attempts": error.attempts,
                                "timing": error.timing,
                            }
                            failure_path = (
                                self.anchor_keepin_context.output_dir
                                / "exact_step_guard_failure.json"
                            )
                            failure_path.parent.mkdir(parents=True, exist_ok=True)
                            with failure_path.open("w") as stream:
                                json.dump(failure, stream, indent=2, sort_keys=True)
                                stream.write("\n")
                            logging.error(
                                "exact accepted-step guard failed: %s",
                                json.dumps(failure, sort_keys=True),
                            )
                            raise RuntimeError(
                                "exact accepted-step guard failed closed: %s"
                                % failure_path
                            ) from error
                        step_evidence = guard_result["step_evidence"]
                        guarded_step = native_execution["optimizer_step_count"] + 1
                        for attempt in guard_result["attempts"]:
                            attempt.update(
                                {
                                    "stage": stage_index,
                                    "iteration": iteration,
                                    "accepted_step": guarded_step,
                                    "optimizer": optimizer_name.lower(),
                                }
                            )
                        native_execution["exact_step_guard_attempts"].extend(
                            guard_result["attempts"]
                        )
                        native_execution[
                            "exact_step_guard_accepted_step_count"
                        ] += 1
                        native_execution[
                            "exact_step_guard_rejected_attempt_count"
                        ] += sum(
                            not attempt["accepted"]
                            for attempt in guard_result["attempts"]
                        )
                        native_execution[
                            "exact_step_guard_overhead_seconds"
                        ] += guard_result["timing"]["guard_overhead_seconds"]
                        native_execution[
                            "exact_step_guard_optimizer_attempt_seconds"
                        ] += guard_result["timing"]["optimizer_attempt_seconds"]
                        logging.info(
                            "exact step guard: step=%d attempts=%d rejected=%d "
                            "overhead=%.6g seconds",
                            guarded_step,
                            len(guard_result["attempts"]),
                            sum(
                                not attempt["accepted"]
                                for attempt in guard_result["attempts"]
                            ),
                            guard_result["timing"]["guard_overhead_seconds"],
                        )
                    elif optimizer_stepped:
                        step_evidence = perform_optimizer_attempt()
                    else:
                        constraint_projector.begin_step(pos)
                        step_evidence = constraint_projector.finish_step()

                    if optimizer_stepped:
                        proposal = step_evidence["proposal"]
                        projection = step_evidence["accepted_projection"]
                        trajectory = displacement_tracker.record_step(
                            step_evidence["origin_position"],
                            step_evidence["proposal_position"],
                            step_evidence["accepted_position"],
                        )
                        native_execution["optimizer_step_count"] += 1
                        native_execution["proposal_changed_node_events"] += proposal[
                            "changed_node_count"
                        ]
                        native_execution["proposal_max_distance"] = max(
                            native_execution["proposal_max_distance"],
                            proposal["max_distance"],
                        )
                        native_execution["projection_node_events"] += projection[
                            "changed_node_count"
                        ]
                        native_execution["projection_search_node_events"] += (
                            step_evidence["projection_event_count"]
                        )
                        native_execution["projection_max_distance"] = max(
                            native_execution["projection_max_distance"],
                            step_evidence["projection_max_distance"],
                        )
                        if proposal["changed_node_count"]:
                            native_execution["optimizer_changed_step_count"] += 1
                        native_execution["optimizer_steps"].append(
                            {
                                "step": native_execution["optimizer_step_count"],
                                "stage": stage_index,
                                "optimizer": optimizer_name.lower(),
                                "learning_rate": float(
                                    optimizer.param_groups[0]["lr"]
                                ),
                                "proposal": {
                                    key: value
                                    for key, value in proposal.items()
                                    if key != "node_ids"
                                },
                                "displacement_by_group": trajectory,
                                "projection": {
                                    "changed_node_count": projection[
                                        "changed_node_count"
                                    ],
                                    "mean_distance": projection["mean_distance"],
                                    "max_distance": projection["max_distance"],
                                },
                            }
                        )
                        if (
                            exact_overlap_interval
                            and native_execution["optimizer_step_count"]
                            % exact_overlap_interval
                            == 0
                        ):
                            record_exact_overlap(
                                stage_index,
                                iteration,
                                "accepted_step",
                                (
                                    guard_result["accepted_report"]
                                    if guard_result is not None
                                    else None
                                ),
                            )
                        logging.info(
                            "native optimizer evidence: optimizer=%s step=%d "
                            "device=%s proposal_changed_nodes=%d "
                            "proposal_mean_distance=%.6g "
                            "proposal_max_distance=%.6g projected_nodes=%d "
                            "projection_mean_distance=%.6g "
                            "projection_max_distance=%.6g",
                            optimizer_name.lower(),
                            native_execution["optimizer_step_count"],
                            pos.device,
                            proposal["changed_node_count"],
                            proposal["mean_distance"],
                            proposal["max_distance"],
                            projection["changed_node_count"],
                            projection["mean_distance"],
                            projection["max_distance"],
                        )

                    logging.info("optimizer step %.3f ms" % ((time.time() - t3) * 1000))

                    # nesterov has already computed the objective of the next step
                    if optimizer_name.lower() == "nesterov":
                        # import ipdb; ipdb.set_trace()
                        cur_metric.objective = optimizer.param_groups[0]["obj_k_1"][
                            0
                        ].data.clone()

                    # actually reports the metric before step
                    logging.info(cur_metric)
                    # record the best outer cell overflow
                    if (
                        best_metric[0] is None
                        or best_metric[0].overflow[-1] > cur_metric.overflow[-1]
                    ):
                        best_metric[0] = cur_metric
                        if best_pos[0] is None:
                            best_pos[0] = self.pos[0].data.clone()
                        else:
                            best_pos[0].data.copy_(self.pos[0].data)

                    logging.info("full step %.3f ms" % ((time.time() - t0) * 1000))

                def check_plateau(x, window=10, threshold=0.001):
                    if len(x) < window:
                        return False
                    x = x[-window:]
                    return (np.max(x) - np.min(x)) / np.mean(x) < threshold

                def check_divergence(x, window=50, threshold=0.05):
                    if len(x) < window or best_metric[0] is None:
                        return False
                    x = np.array(x[-window:])
                    overflow_mean = np.mean(x[:, 1])
                    overflow_diff = np.maximum(0, np.sign(x[1:, 1] - x[:-1, 1])).astype(
                        np.float32
                    )
                    overflow_diff = np.sum(overflow_diff) / overflow_diff.shape[0]
                    overflow_range = np.max(x[:, 1]) - np.min(x[:, 1])
                    wl_mean = np.mean(x[:, 0])
                    wl_ratio, overflow_ratio = (
                        wl_mean - best_metric[0].hpwl.item()
                    ) / best_metric[0].hpwl.item(), (
                        overflow_mean
                        - max(params.stop_overflow, best_metric[0].overflow.item())
                    ) / best_metric[
                        0
                    ].overflow.item()
                    if wl_ratio > threshold * 1.2:
                        if overflow_ratio > threshold:
                            logging.warn(
                                f"Divergence detected: overflow increases too much than best overflow ({overflow_ratio:.4f} > {threshold:.4f})"
                            )
                            return True
                        elif overflow_range / overflow_mean < threshold:
                            logging.warn(
                                f"Divergence detected: overflow plateau ({overflow_range/overflow_mean:.4f} < {threshold:.4f})"
                            )
                            return True
                        elif overflow_diff > 0.6:
                            logging.warn(
                                f"Divergence detected: overflow fluctuate too frequently ({overflow_diff:.2f} > 0.6)"
                            )
                            return True
                        else:
                            return False
                    else:
                        return False

                def entropy_injection(
                    pos,
                    placedb,
                    shrink_factor=1,
                    noise_intensity=1,
                    mode="random",
                    iteration=1,
                ):
                    if mode == "random":
                        # print(pos[: placedb.num_movable_nodes].mean())
                        xc = pos[: placedb.num_movable_nodes].data.mean()
                        yc = pos.data[
                            placedb.num_nodes : placedb.num_nodes
                            + placedb.num_movable_nodes
                        ].mean()
                        num_movable_nodes = placedb.num_movable_nodes
                        num_nodes = placedb.num_nodes
                        num_filler_nodes = placedb.num_filler_nodes
                        num_fixed_nodes = (
                            num_nodes - num_movable_nodes - num_filler_nodes
                        )

                        fixed_pos_x = pos.data[
                            num_movable_nodes : num_movable_nodes + num_fixed_nodes
                        ].clone()
                        fixed_pos_y = pos.data[
                            num_nodes
                            + num_movable_nodes : num_nodes
                            + num_movable_nodes
                            + num_fixed_nodes
                        ].clone()
                        if shrink_factor != 1:
                            pos.data[:num_nodes] = (
                                pos.data[:num_nodes] - xc
                            ) * shrink_factor + xc
                            pos.data[num_nodes:] = (
                                pos.data[num_nodes:] - yc
                            ) * shrink_factor + yc
                        if noise_intensity > 0.01:
                            # pos.data.add_(noise_intensity * torch.rand(num_nodes*2, device=pos.device).sub_(0.5))
                            pos.data.add_(
                                noise_intensity
                                * torch.randn(num_nodes * 2, device=pos.device)
                            )

                        pos.data[
                            num_movable_nodes : num_movable_nodes + num_fixed_nodes
                        ] = fixed_pos_x
                        pos.data[
                            num_nodes
                            + num_movable_nodes : num_nodes
                            + num_movable_nodes
                            + num_fixed_nodes
                        ] = fixed_pos_y
                        # print(pos[: placedb.num_movable_nodes].mean())
                    else:
                        raise NotImplementedError

                Lgamma_metrics = all_metrics

                if params.routability_opt_flag:
                    adjust_area_flag = True
                    adjust_route_area_flag = (
                        params.adjust_nctugr_area_flag or params.adjust_rudy_area_flag
                    )
                    adjust_pin_area_flag = params.adjust_pin_area_flag
                    num_area_adjust = 0

                Llambda_flat_iteration = 0

                ### preparation for self-adaptive divergence check
                overflow_list = [1]
                divergence_list = []
                min_perturb_interval = 50
                stop_placement = 0
                last_perturb_iter = -min_perturb_interval
                perturb_counter = 0

                # reduce iterations
                model.Lgamma_iteration /= (
                    model.Llambda_density_weight_iteration * model.Lsub_iteration
                )
                model.Lgamma_iteration = int(model.Lgamma_iteration)

                for Lgamma_step in range(model.Lgamma_iteration):
                    Lgamma_metrics.append([])
                    Llambda_metrics = Lgamma_metrics[-1]
                    for Llambda_density_weight_step in range(
                        model.Llambda_density_weight_iteration
                    ):
                        Llambda_metrics.append([])
                        Lsub_metrics = Llambda_metrics[-1]
                        for Lsub_step in range(model.Lsub_iteration):
                            ## divergence threshold should decrease as overflow decreases
                            ## only detect divergence when overflow is relatively low but not too low
                            """
                            # this heuristics makes placement unstable
                            if (
                                len(placedb.regions) == 0
                                and params.stop_overflow * 1.1 < overflow_list[-1] < params.stop_overflow * 4
                                and check_divergence(
                                    divergence_list, window=3, threshold=0.01 * overflow_list[-1]
                                )
                            ):
                                self.pos[0].data.copy_(best_pos[0].data)
                                stop_placement = 1

                                logging.error(
                                    "possible DIVERGENCE detected, roll back to the best position recorded"
                                )
                            """

                            one_descent_step(
                                Lgamma_step,
                                Llambda_density_weight_step,
                                Lsub_step,
                                iteration,
                                Lsub_metrics,
                            )

                            if len(placedb.regions) == 0:
                                overflow_list.append(
                                    Llambda_metrics[-1][-1].overflow.data.item()
                                )
                                divergence_list.append(
                                    [
                                        Llambda_metrics[-1][-1].hpwl.data.item(),
                                        Llambda_metrics[-1][-1].overflow.data.item(),
                                    ]
                                )

                            ## quadratic penalty and entropy injection
                            """
                            # This heuristics makes placement unstable
                            if (
                                len(placedb.regions) == 0
                                and iteration - last_perturb_iter > min_perturb_interval
                                and check_plateau(overflow_list, window=15, threshold=0.001)
                            ):
                                if overflow_list[-1] > 0.9:  # stuck at high overflow
                                    model.quad_penalty = True
                                    model.density_factor *= 2
                                    logging.info(
                                        f"Stuck at early stage. Turn on quadratic penalty with double density factor to accelerate convergence"
                                    )
                                    if overflow_list[-1] > 0.95:  # stuck at very high overflow
                                        noise_intensity = min(
                                            max(40 + (120 - 40) * (overflow_list[-1] - 0.95) * 10, 40), 90
                                        )
                                        entropy_injection(
                                            self.pos[0],
                                            placedb,
                                            shrink_factor=0.996,
                                            noise_intensity=noise_intensity,
                                            mode="random",
                                        )
                                        logging.info(
                                            f"Stuck at very early stage. Turn on entropy injection with noise intensity = {noise_intensity} to help convergence"
                                        )
                                    last_perturb_iter = iteration
                                    perturb_counter += 1
                            """
                            iteration += 1
                            # stopping criteria
                            if Lsub_stop_criterion(
                                Lgamma_step,
                                Llambda_density_weight_step,
                                Lsub_step,
                                Lsub_metrics,
                            ):
                                break
                        Llambda_flat_iteration += 1

                        # update density weight
                        if Llambda_flat_iteration > 1:
                            model.op_collections.update_density_weight_op(
                                Llambda_metrics[-1][-1],
                                Llambda_metrics[-2][-1]
                                if len(Llambda_metrics) > 1
                                else Lgamma_metrics[-2][-1][-1],
                                Llambda_flat_iteration,
                            )
                        # logging.debug("update density weight %.3f ms" % ((time.time()-t2)*1000))

                        # update macro overlap weight
                        if Llambda_flat_iteration > 1 and params.macro_overlap_flag:
                            model.op_collections.update_macro_overlap_weight_op(
                                Llambda_metrics[-1][-1],
                                Llambda_metrics[-2][-1]
                                if len(Llambda_metrics) > 1
                                else Lgamma_metrics[-2][-1][-1],
                                Llambda_flat_iteration,
                            )

                        # update net crossing weight
                        if Llambda_flat_iteration > 1 and net_crossing_enabled:
                            model.op_collections.update_net_crossing_weight_op(
                                Llambda_metrics[-1][-1],
                                Llambda_metrics[-2][-1]
                                if len(Llambda_metrics) > 1
                                else Lgamma_metrics[-2][-1][-1],
                                Llambda_flat_iteration,
                            )

                        if Llambda_stop_criterion(
                            Lgamma_step, Llambda_density_weight_step, Llambda_metrics
                        ):
                            break

                        # for routability optimization
                        if (
                            params.routability_opt_flag
                            and num_area_adjust < params.max_num_area_adjust
                            and Llambda_metrics[-1][-1].overflow
                            < params.node_area_adjust_overflow
                        ):
                            content = (
                                "routability optimization round %d: adjust area flags = (%d, %d, %d)"
                                % (
                                    num_area_adjust,
                                    adjust_area_flag,
                                    adjust_route_area_flag,
                                    adjust_pin_area_flag,
                                )
                            )
                            pos = model.data_collections.pos[0]

                            route_utilization_map = None
                            pin_utilization_map = None
                            if adjust_route_area_flag:
                                if params.adjust_nctugr_area_flag:
                                    route_utilization_map = (
                                        model.op_collections.nctugr_congestion_map_op(
                                            pos
                                        )
                                    )
                                else:
                                    route_utilization_map = (
                                        model.op_collections.route_utilization_map_op(
                                            pos
                                        )
                                    )
                                if params.plot_flag:
                                    path = "%s/%s" % (
                                        params.result_dir,
                                        params.design_name(),
                                    )
                                    figname = "%s/plot/route%d.png" % (
                                        path,
                                        num_area_adjust,
                                    )
                                    os.system(
                                        "mkdir -p %s" % (os.path.dirname(figname))
                                    )
                                    plt.imsave(
                                        figname,
                                        route_utilization_map.data.cpu().numpy().T,
                                        origin="lower",
                                    )
                            if adjust_pin_area_flag:
                                pin_utilization_map = (
                                    model.op_collections.pin_utilization_map_op(pos)
                                )
                                if params.plot_flag:
                                    path = "%s/%s" % (
                                        params.result_dir,
                                        params.design_name(),
                                    )
                                    figname = "%s/plot/pin%d.png" % (
                                        path,
                                        num_area_adjust,
                                    )
                                    os.system(
                                        "mkdir -p %s" % (os.path.dirname(figname))
                                    )
                                    plt.imsave(
                                        figname,
                                        pin_utilization_map.data.cpu().numpy().T,
                                        origin="lower",
                                    )
                            (
                                adjust_area_flag,
                                adjust_route_area_flag,
                                adjust_pin_area_flag,
                            ) = model.op_collections.adjust_node_area_op(
                                pos, route_utilization_map, pin_utilization_map
                            )
                            content += " -> (%d, %d, %d)" % (
                                adjust_area_flag,
                                adjust_route_area_flag,
                                adjust_pin_area_flag,
                            )
                            logging.info(content)
                            if adjust_area_flag:
                                num_area_adjust += 1
                                # restart Llambda
                                model.op_collections.top_density_op.reset()
                                model.op_collections.btm_density_op.reset()
                                model.op_collections.pin_utilization_map_op.reset()
                                model.initialize_density_weight(params, placedb)
                                model.density_weight.mul_(0.1 / params.density_weight)
                                logging.info(
                                    "density_weight = %.6E"
                                    % (model.density_weight.data)
                                )
                                # load state to restart the optimizer
                                optimizer.load_state_dict(initial_state)
                                # must after loading the state
                                initialize_learning_rate(
                                    pos, "routability_restart"
                                )
                                # increase iterations of the sub problem to slow down the search
                                model.Lsub_iteration = model.routability_Lsub_iteration

                                # reset best metric
                                best_metric[0] = None
                                best_pos[0] = None
                                break

                    # gradually reduce gamma to tradeoff smoothness and accuracy
                    if (
                        len(placedb.regions) > 0
                        and Llambda_metrics[-1][-1].goverflow is not None
                    ):
                        model.op_collections.update_gamma_op(
                            Lgamma_step, Llambda_metrics[-1][-1].goverflow
                        )
                    elif (
                        len(placedb.regions) == 0
                        and Llambda_metrics[-1][-1].overflow is not None
                    ):
                        model.op_collections.update_gamma_op(
                            Lgamma_step, Llambda_metrics[-1][-1].overflow
                        )
                    else:
                        model.op_collections.precondition_op.set_overflow(
                            Llambda_metrics[-1][-1].overflow
                        )
                    if (
                        Lgamma_stop_criterion(Lgamma_step, Lgamma_metrics)
                        or stop_placement == 1
                    ):
                        break

                    # update learning rate
                    if optimizer_name.lower() in [
                        "sgd",
                        "adam",
                        "sgd_momentum",
                        "sgd_nesterov",
                        "cg",
                    ]:
                        if "learning_rate_decay" in global_place_params:
                            scheduler.step()
                            lrs.append(optimizer.param_groups[0]["lr"])

                # in case of divergence, use the best metric
                # last_metric = all_metrics[-1][-1][-1]
                # if (
                #     last_metric.overflow[-1] > max(params.stop_overflow, best_metric[0].overflow[-1])
                #     and last_metric.hpwl > best_metric[0].hpwl
                # ):
                #     all_metrics.append([best_metric])

                logging.info(
                    "optimizer %s takes %.3f seconds"
                    % (optimizer_name, time.time() - tt)
                )


            # log best theta
            if params.enable_rotation:
                logging.info("Best theta: " + str(self.data_collections.best_theta.data))

            # recover node size and pin offset for legalization, since node size is adjusted in global placement
            if params.routability_opt_flag:
                with torch.no_grad():
                    # convert lower left to centers
                    self.pos[0][: placedb.num_movable_nodes].add_(
                        self.data_collections.node_size_x[: placedb.num_movable_nodes]
                        / 2
                    )
                    self.pos[0][
                        placedb.num_nodes : placedb.num_nodes
                        + placedb.num_movable_nodes
                    ].add_(
                        self.data_collections.node_size_y[: placedb.num_movable_nodes]
                        / 2
                    )
                    self.data_collections.node_size_x.copy_(
                        self.data_collections.original_node_size_x
                    )
                    self.data_collections.node_size_y.copy_(
                        self.data_collections.original_node_size_y
                    )
                    # use fixed centers as the anchor
                    self.pos[0][: placedb.num_movable_nodes].sub_(
                        self.data_collections.node_size_x[: placedb.num_movable_nodes]
                        / 2
                    )
                    self.pos[0][
                        placedb.num_nodes : placedb.num_nodes
                        + placedb.num_movable_nodes
                    ].sub_(
                        self.data_collections.node_size_y[: placedb.num_movable_nodes]
                        / 2
                    )
                    self.data_collections.pin_offset_x.copy_(
                        self.data_collections.original_pin_offset_x
                    )
                    self.data_collections.pin_offset_y.copy_(
                        self.data_collections.original_pin_offset_y
                    )

        if params.plot_flag:
            self.plot(params, placedb, 9999, self.pos[0].data.clone().cpu().numpy())

        # recover node sizes, pins shifts, and positions of macros
        if params.macro_halo_x >= 0 and params.macro_halo_y >= 0:
            with torch.no_grad():
                # node sizes
                self.data_collections.node_size_x[placedb.movable_macro_idx] -= (
                    2 * params.macro_halo_x
                )
                self.data_collections.node_size_y[placedb.movable_macro_idx] -= (
                    2 * params.macro_halo_y
                )
                # self.data_collections.node_size_x[placedb.fixed_macro_idx] -= (
                #     2 * params.macro_halo_x
                # )
                # self.data_collections.node_size_y[placedb.fixed_macro_idx] -= (
                #     2 * params.macro_halo_y
                # )

                # pin offsets
                self.data_collections.pin_offset_x[
                    placedb.movable_macro_pins
                ] -= params.macro_halo_x
                self.data_collections.pin_offset_y[
                    placedb.movable_macro_pins
                ] -= params.macro_halo_y
                # self.data_collections.pin_offset_x[
                #     placedb.fixed_macro_pins
                # ] -= params.macro_halo_x
                # self.data_collections.pin_offset_y[
                #     placedb.fixed_macro_pins
                # ] -= params.macro_halo_y

                # macro locations
                self.pos[0][placedb.movable_slice][
                    placedb.movable_macro_mask
                ] += params.macro_halo_x
                self.pos[0][
                    placedb.num_nodes : placedb.num_nodes + placedb.num_movable_nodes
                ][placedb.movable_macro_mask] += params.macro_halo_y
                self.pos[0][placedb.fixed_slice][
                    placedb.fixed_macro_mask
                ] += params.macro_halo_x
                self.pos[0][
                    placedb.num_nodes
                    + placedb.num_movable_nodes : placedb.num_nodes
                    + placedb.num_movable_nodes
                    + placedb.num_terminals
                ][placedb.fixed_macro_mask] += params.macro_halo_y

        # rescale everything
        cur_scale_factor = self.data_collections.fp_info.scale_factor
        gcd_site_scale_factor = 1 / math.gcd(
            placedb.pydb.site_width, placedb.pydb.row_height
        )
        if cur_scale_factor != gcd_site_scale_factor:
            logging.warn(
                f"Rescaling by GCD(site_width, row_height) = {gcd_site_scale_factor} before legalization and detailed placement"
            )
            params.scale_factor = gcd_site_scale_factor
            rescale_factor = gcd_site_scale_factor / cur_scale_factor
            with torch.no_grad():
                self.pos[0].mul_(rescale_factor).round_()
                self.data_collections.node_size_x.mul_(rescale_factor).round_()
                self.data_collections.node_size_y.mul_(rescale_factor).round_()
                self.data_collections.flat_region_boxes.mul_(rescale_factor).round_()
                self.data_collections.pin_offset_x.mul_(rescale_factor)
                self.data_collections.pin_offset_y.mul_(rescale_factor)
                # self.data_collections.node_areas.mul_(rescale_factor * rescale_factor)
                self.data_collections.fp_info.scale(rescale_factor)
                self.data_collections.fp_info.scale_factor = gcd_site_scale_factor
                # TODO: rescale fence regions

        # dump global placement solution for legalization
        if params.dump_global_place_solution_flag:
            self.dump(
                params,
                placedb,
                self.pos[0].cpu(),
                "%s.lg.pklz" % (params.design_name()),
            )

        # process metrics
        flatten = lambda l: sum(map(flatten, l), []) if isinstance(l, list) else [l]
        metrics = flatten(all_metrics)
        objectives = [metric.objective.data.item() for metric in metrics]
        hpwls = [metric.hpwl.data.item() for metric in metrics]
        overflows = [metric.overflow.data.item() for metric in metrics]
        densities = [metric.max_density.data.item() for metric in metrics]
        if net_crossing_enabled:
            net_crossing = [metric.net_crossing.data.item() for metric in metrics]
        processed_metrics = {
            "objective": objectives,
            "hpwl": hpwls,
            "overflow": overflows,
            "density": densities,
        }
        native_execution["backward_call_count"] = sum(
            model.backward_call_count for model in native_models
        )
        native_execution["anchor_weight_updates"] = [
            update
            for model in native_models
            for update in model.anchor_weight_updates
        ]
        native_execution["collision_weight_updates"] = [
            update
            for model in native_models
            for update in model.collision_weight_updates
        ]
        native_execution["irregular_density_capacity"] = [
            diagnostics
            for model in native_models
            for diagnostics in model.irregular_density_diagnostics
        ]
        native_execution["density_overflow_by_side"] = [
            model.latest_density_overflow_by_side
            for model in native_models
            if model.latest_density_overflow_by_side is not None
        ]
        native_execution["displacement"] = displacement_tracker.summary(
            units_per_mm=(
                abs(self.anchor_keepin_context.alignment.scale)
                if self.anchor_keepin_context is not None
                else None
            )
        )
        if exact_step_guard_enabled:
            guard_artifact = {
                "status": "completed",
                "backoff": exact_step_guard_backoff,
                "max_retries": exact_step_guard_max_retries,
                "accepted_step_count": native_execution[
                    "exact_step_guard_accepted_step_count"
                ],
                "rejected_attempt_count": native_execution[
                    "exact_step_guard_rejected_attempt_count"
                ],
                "guard_overhead_seconds": native_execution[
                    "exact_step_guard_overhead_seconds"
                ],
                "optimizer_attempt_seconds": native_execution[
                    "exact_step_guard_optimizer_attempt_seconds"
                ],
                "attempts": native_execution["exact_step_guard_attempts"],
            }
            guard_path = (
                self.anchor_keepin_context.output_dir / "exact_step_guard.json"
            )
            guard_path.parent.mkdir(parents=True, exist_ok=True)
            with guard_path.open("w") as stream:
                json.dump(guard_artifact, stream, indent=2, sort_keys=True)
                stream.write("\n")
            self.anchor_keepin_context.timing["exact_step_guard_seconds"] = (
                native_execution["exact_step_guard_overhead_seconds"]
            )
        processed_metrics["native_execution"] = native_execution
        logging.info(
            "native execution summary: %s",
            json.dumps(native_execution, sort_keys=True),
        )
        if self.anchor_keepin_context is not None:
            if params.gpu:
                torch.cuda.synchronize()
            self.anchor_keepin_context.timing["gpu_optimization_seconds"] = (
                time.perf_counter() - optimization_started
                - native_execution.get("exact_overlap_diagnostic_seconds", 0.0)
                - native_execution.get("exact_step_guard_overhead_seconds", 0.0)
            )
        if net_crossing_enabled:
            processed_metrics["net_crossing"] = net_crossing

        # plot losses
        if params.plot_flag:
            self.plot(
                params, placedb, iteration, self.pos[0].data.clone().cpu().numpy()
            )
            epochs = np.arange(len(objectives))
            num_subplots = 4
            if len(lrs) >= len(epochs):
                lrs = [float(lr) for lr in lrs]
                num_subplots += 1
            if params.macro_overlap_flag:
                macro_overlaps = [
                    metric.macro_overlap.data.item() for metric in metrics
                ]
                num_subplots += 1
            fig, axis = plt.subplots(1, num_subplots, figsize=(5 * num_subplots, 5))
            axis[0].plot(epochs, np.log10(objectives), color="red")
            axis[0].set_title("Obj")
            axis[1].plot(epochs, np.log10(hpwls), color="blue")
            axis[1].set_title("HPWL")
            axis[2].plot(epochs, overflows, color="green")
            axis[2].set_title("Ovflw")
            # axis[3].plot(epochs, densities, color="orange")
            # axis[3].set_title("MaxDens")
            # axis[3].plot(epochs, net_crossing, color="orange")
            # axis[3].set_title("NetCross")
            plotted = 3
            if len(lrs) >= len(epochs):
                axis[plotted].plot(
                    epochs, np.log10(lrs[0 : len(epochs)]), color="black"
                )
                axis[plotted].set_title("Lr")
                plotted += 1
            if params.macro_overlap_flag:
                axis[plotted].plot(epochs, macro_overlaps, color="purple")
                axis[plotted].set_title("MacroOvlp")
            fig.tight_layout(pad=2.0)
            path = "%s/%s" % (params.result_dir, params.design_name())
            figname = os.path.join(path, f"{params.design_name()}.loss.png")
            plt.savefig(figname)

        last_metric = copy.deepcopy(all_metrics)
        for idx in [-1, -1, -1]:
            try:
                last_metric = last_metric[idx]
            except IndexError:
                last_metric = False
                break

        if not last_metric:
            cur_metric = EvalMetrics.EvalMetrics(iteration)
            all_metrics.append(cur_metric)
            cur_metric.evaluate(
                placedb, {"hpwl": self.op_collections.hpwl_op}, self.pos[0]
            )
            logging.info(cur_metric)

        # High overflow may still be useful for an explicitly bounded diagnostic.
        if last_metric:
            high_overflow = last_metric.overflow[-1] > params.stop_overflow
            invalid_objective = torch.isinf(
                last_metric.objective
            ) or torch.isnan(last_metric.objective)
            continue_high_overflow = bool(
                getattr(
                    params,
                    "diagnostic_validation_on_high_overflow_flag",
                    False,
                )
                and self.anchor_keepin_context is not None
            )
            if invalid_objective or (
                high_overflow and not continue_high_overflow
            ):
                logging.warning(
                    "overflow is significant %.3f or objective is infinity "
                    "or nan; skip validation and post-placement steps",
                    last_metric.overflow[-1],
                )
                self.plot(
                    params,
                    placedb,
                    9999,
                    self.pos[0].data.clone().cpu().numpy(),
                )
                return float("inf"), float("inf"), processed_metrics
            if high_overflow:
                logging.warning(
                    "overflow is significant %.3f; explicit diagnostic mode "
                    "continues exact validation and native scoring",
                    last_metric.overflow[-1],
                )

        # legalization
        if params.legalize_flag:
            tt = time.time()
            self.pos[0].data.copy_(self.op_collections.legalize_op(self.pos[0], self.data_collections.best_orient_choice))
            if self.anchor_keepin_context is not None:
                self.op_collections.move_region_boundary_op(self.pos[0])
            logging.info("legalization takes %.3f seconds" % (time.time() - tt))
            cur_metric = EvalMetrics.EvalMetrics(iteration)
            all_metrics.append(cur_metric)
            cur_metric.evaluate(
                placedb, {"hpwl": self.op_collections.hpwl_op}, self.pos[0]
            )
            logging.info(cur_metric)
            iteration += 1

        # plot placement
        if params.plot_flag:
            self.plot(
                params, placedb, iteration, self.pos[0].data.clone().cpu().numpy()
            )

        # dump legalization solution for detailed placement
        if params.dump_legalize_solution_flag:
            self.dump(
                params,
                placedb,
                self.pos[0].cpu(),
                "%s.dp.pklz" % (params.design_name()),
            )

        # detailed placement
        if params.detailed_place_flag:
            tt = time.time()
            self.pos[0].data.copy_(self.op_collections.detailed_place_op(self.pos[0]))
            if self.anchor_keepin_context is not None:
                self.op_collections.move_region_boundary_op(self.pos[0])
            macro_orients = self.op_collections.macro_refinement_op(self.pos[0])
            logging.info("detailed placement takes %.3f seconds" % (time.time() - tt))
            cur_metric = EvalMetrics.EvalMetrics(iteration)
            all_metrics.append(cur_metric)
            cur_metric.evaluate(
                placedb, {"hpwl": self.op_collections.hpwl_op}, self.pos[0]
            )
            logging.info(cur_metric)
            iteration += 1

        if self.anchor_keepin_context is not None:
            context = self.anchor_keepin_context
            repair_report = None
            validation_seconds = 0.0
            if context.exact_repair_enabled:
                validation_started = time.perf_counter()
                exact_before = context.exact_report(self.pos[0], placedb)
                validation_seconds += time.perf_counter() - validation_started
                hpwl_before = float(self.op_collections.hpwl_op(self.pos[0]))
                already_legal = (
                    exact_before["keepin_violation_count"] == 0
                    and exact_before["overlap_pair_count"] == 0
                )
                repair_stats = (
                    {
                        "component_count": len(context.constraints),
                        "moved_component_count": 0,
                        "mean_displacement": 0.0,
                        "max_displacement": 0.0,
                        "regions": [],
                        "skipped_already_legal": True,
                    }
                    if already_legal
                    else context.repair_positions(self.pos[0], placedb)
                )
                validation_started = time.perf_counter()
                exact_after = context.exact_report(self.pos[0], placedb)
                validation_seconds += time.perf_counter() - validation_started
                hpwl_after = float(self.op_collections.hpwl_op(self.pos[0]))
                repair_report = {
                    "before": exact_before,
                    "after": exact_after,
                    "hpwl_before": hpwl_before,
                    "hpwl_after": hpwl_after,
                    "hpwl_delta": hpwl_after - hpwl_before,
                    "stats": repair_stats,
                }
                with (context.output_dir / "repair.json").open("w") as stream:
                    json.dump(repair_report, stream, indent=2, sort_keys=True)
                    stream.write("\n")
                logging.info(
                    "anchor/keep-in repair: overlaps %d -> %d, HPWL %.6g -> %.6g",
                    exact_before["overlap_pair_count"],
                    exact_after["overlap_pair_count"],
                    hpwl_before,
                    hpwl_after,
                )
            validation_started = time.perf_counter()
            exact_report = context.exact_report(self.pos[0], placedb)
            validation_seconds += time.perf_counter() - validation_started
            context.timing["exact_validation_seconds"] += validation_seconds
            exact_report["total_projected_nodes"] = context.projector.total_projected
            processed_metrics["anchor_keepin"] = {
                "total_projected_nodes": context.projector.total_projected,
                "exact_legality": exact_report,
            }
            if repair_report is not None:
                processed_metrics["anchor_keepin"]["repair"] = repair_report
            report_path = context.output_dir / "legality.json"
            with report_path.open("w") as stream:
                json.dump(exact_report, stream, indent=2, sort_keys=True)
                stream.write("\n")
            logging.info(
                "anchor/keep-in exact check: %d violations, %d overlaps",
                exact_report["keepin_violation_count"],
                exact_report["overlap_pair_count"],
            )
            context.write_timing()

        # save results
        cur_pos = self.pos[0].data.clone().cpu().numpy()
        # apply position solution/ will also update movable node orientations based on row
        placedb.apply(
            params,
            cur_pos[0 : placedb.num_movable_nodes],
            cur_pos[placedb.num_nodes : placedb.num_nodes + placedb.num_movable_nodes],
        )

        # apply macro orientations solution
        if params.detailed_place_flag:
            orients_map = {
                "N": 0,
                "S": 1,
                "W": 2,
                "E": 3,
                "FN": 4,
                "FS": 5,
                "FW": 6,
                "FE": 7,
                "UNKNOWN": 8,
            }
            for macro, orient in macro_orients:
                placedb.rawdb.setNodeOrient(
                    int(macro), place_io_cpp.OrientEnum.OrientType(orients_map[orient])
                )

        # reset net weights
        self.data_collections.net_weights.fill_(1.0)

        # plot placement
        # if params.plot_flag:
        self.plot(params, placedb, iteration, cur_pos)

        scoring_started = time.perf_counter()
        # run RSMT
        with torch.no_grad():
            tt = time.time()
            rsmt_wl = self.op_collections.rsmt_wl_op(self.pos[0])
            logging.info("rsmt computation takes %.3f seconds" % (time.time() - tt))
            logging.info("flute rsmt %.6E" % rsmt_wl)

        # get HPWL
        with torch.no_grad():
            hpwl = self.op_collections.hpwl_op(self.pos[0])
            logging.info("unweighted hpwl %.6E" % hpwl)

        if self.anchor_keepin_context is not None:
            context = self.anchor_keepin_context
            context.timing["native_scoring_seconds"] += (
                time.perf_counter() - scoring_started
            )
            context.write_timing()
            processed_metrics["timing"] = dict(context.timing)

        # get net crossing
        with torch.no_grad():
            if net_crossing_enabled:
                net_crossing = self.op_collections.net_crossing_op(self.pos[0])
                logging.info("net crossing %d" % net_crossing)
                return float(rsmt_wl), float(hpwl), float(net_crossing), processed_metrics

        return float(rsmt_wl), float(hpwl), processed_metrics
