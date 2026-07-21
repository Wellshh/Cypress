"""Bounded candidate-side projection for exact contact crossings."""

import itertools
import math
import time

import torch

from dreamplace.constraints.exact_step_guard import (
    ExactValidationProvenance,
)


COMPONENT_CONSENSUS = "component_consensus"
MINIMUM_COVER_ROLLBACK = "minimum_cover_rollback"
PROPOSAL_AUTHORITY_SEARCH = "proposal_authority_search"
PROTECTED_PROPOSAL_AUTHORITY_SEARCH = (
    "protected_proposal_authority_search"
)
PROPOSAL_AUTHORITY_MODES = (
    PROPOSAL_AUTHORITY_SEARCH,
    PROTECTED_PROPOSAL_AUTHORITY_SEARCH,
)
CONTACT_PROJECTION_MODES = (
    COMPONENT_CONSENSUS,
    MINIMUM_COVER_ROLLBACK,
    *PROPOSAL_AUTHORITY_MODES,
)
EXHAUSTIVE_AUTHORITY_SEARCH = "exhaustive"
PAIRWISE_FACTORIZED_AUTHORITY_SEARCH = "pairwise_factorized"
AUTHORITY_SEARCH_STRATEGIES = (
    EXHAUSTIVE_AUTHORITY_SEARCH,
    PAIRWISE_FACTORIZED_AUTHORITY_SEARCH,
)
AUTHORITY_TOPOLOGY_CANDIDATE = "proposal_authority"
CONSENSUS_TOPOLOGY_CANDIDATE = "component_consensus"


def _contact_components(edges):
    parent = {}

    def find(node_id):
        parent.setdefault(node_id, node_id)
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    for first_node_id, second_node_id in sorted(edges):
        first_root = find(first_node_id)
        second_root = find(second_node_id)
        if first_root != second_root:
            parent[max(first_root, second_root)] = min(first_root, second_root)

    groups = {}
    for node_id in sorted(parent):
        groups.setdefault(find(node_id), []).append(node_id)
    return tuple(tuple(node_ids) for _, node_ids in sorted(groups.items()))


def _correction_statistics(before, after, num_nodes):
    displacement = torch.stack(
        (
            after[:num_nodes] - before[:num_nodes],
            after[num_nodes : 2 * num_nodes]
            - before[num_nodes : 2 * num_nodes],
        ),
        dim=1,
    )
    distances = torch.linalg.vector_norm(displacement, dim=1)
    changed = distances > 0
    changed_ids = torch.nonzero(changed, as_tuple=False).flatten()
    changed_distances = distances.index_select(0, changed_ids)
    return {
        "changed_node_count": int(changed_ids.numel()),
        "changed_node_ids": [int(value) for value in changed_ids.tolist()],
        "mean_distance": (
            float(changed_distances.mean().item())
            if changed_ids.numel()
            else 0.0
        ),
        "max_distance": (
            float(changed_distances.max().item())
            if changed_ids.numel()
            else 0.0
        ),
    }


def _representative_node_id(displacements, node_ids):
    """Choose the proposal medoid, with node ID as the deterministic tie-break."""
    best = None
    for candidate_node_id in node_ids:
        candidate_x, candidate_y = displacements[candidate_node_id]
        cost = math.fsum(
            (candidate_x - displacements[other_node_id][0]) ** 2
            + (candidate_y - displacements[other_node_id][1]) ** 2
            for other_node_id in node_ids
        )
        if not math.isfinite(cost):
            raise ValueError("contact projection received non-finite motion")
        key = (cost, candidate_node_id)
        if best is None or key < best:
            best = key
    if best is None:
        raise ValueError("contact projection cannot represent an empty component")
    return best[1]


class ExactContactProjector:
    """Apply bounded correction to exact-crossing contact components.

    The node budget limits the cumulative active coordinates selected for
    contact correction. Inactive endpoints do not consume that budget.
    """

    def __init__(
        self,
        validator,
        refdes_to_node_id,
        active_node_ids,
        num_nodes,
        max_iterations=8,
        max_contact_nodes=32,
        mode=COMPONENT_CONSENSUS,
        max_cover_component_nodes=16,
        component_validator=None,
        component_edge_validator=None,
        component_projector=None,
        max_authority_states=4096,
        authority_search_strategy=EXHAUSTIVE_AUTHORITY_SEARCH,
        authority_factorization_compatible=False,
        topology_tiebreak=False,
        topology_evaluator=None,
        topology_net_ids=(),
        topology_net_degrees=(),
        validation_provenance_cache=False,
    ):
        self.validator = validator
        self.refdes_to_node_id = {
            str(refdes): int(node_id)
            for refdes, node_id in refdes_to_node_id.items()
        }
        self.node_id_to_refdes = {
            node_id: refdes
            for refdes, node_id in self.refdes_to_node_id.items()
        }
        self.active_node_ids = frozenset(int(value) for value in active_node_ids)
        self.num_nodes = int(num_nodes)
        self.max_iterations = int(max_iterations)
        self.max_contact_nodes = int(max_contact_nodes)
        self.mode = str(mode)
        self.max_cover_component_nodes = int(max_cover_component_nodes)
        self.component_validator = component_validator
        self.component_edge_validator = component_edge_validator
        self.component_projector = component_projector
        self.max_authority_states = int(max_authority_states)
        self.authority_search_strategy = str(authority_search_strategy)
        self.authority_factorization_compatible = bool(
            authority_factorization_compatible
        )
        self.topology_tiebreak = bool(topology_tiebreak)
        self.topology_evaluator = topology_evaluator
        self.topology_net_ids = tuple(int(value) for value in topology_net_ids)
        self.topology_net_degrees = tuple(
            int(value) for value in topology_net_degrees
        )
        self.validation_provenance_cache = bool(
            validation_provenance_cache
        )
        validate_with_state = getattr(validator, "validate_with_state", None)
        validate_delta = getattr(validator, "validate_delta", None)
        has_state_validator = callable(validate_with_state)
        has_delta_validator = callable(validate_delta)
        if has_state_validator != has_delta_validator:
            raise ValueError(
                "incremental exact validator requires full and delta methods"
            )
        self.incremental_validator = (
            validator if has_state_validator else None
        )
        self._validation_provenance = None
        if self.num_nodes <= 0:
            raise ValueError("contact projection requires a positive node count")
        if self.max_iterations <= 0:
            raise ValueError("contact projection iterations must be positive")
        if self.max_contact_nodes < 2:
            raise ValueError("contact projection node limit must be at least two")
        if self.mode not in CONTACT_PROJECTION_MODES:
            raise ValueError("unknown exact contact projection mode: %s" % self.mode)
        if self.max_cover_component_nodes < 2:
            raise ValueError(
                "contact projection cover component limit must be at least two"
            )
        if (
            self.mode in PROPOSAL_AUTHORITY_MODES
            and self.max_authority_states <= 0
        ):
            raise ValueError(
                "contact projection authority state limit must be positive"
            )
        if (
            self.mode in PROPOSAL_AUTHORITY_MODES
            and self.component_validator is None
        ):
            raise ValueError(
                "proposal authority search requires an exact component validator"
            )
        if (
            self.mode in PROPOSAL_AUTHORITY_MODES
            and self.component_projector is None
        ):
            raise ValueError(
                "proposal authority search requires a hard component projector"
            )
        if self.authority_search_strategy not in AUTHORITY_SEARCH_STRATEGIES:
            raise ValueError(
                "unknown authority search strategy: %s"
                % self.authority_search_strategy
            )
        if (
            self.authority_search_strategy
            != EXHAUSTIVE_AUTHORITY_SEARCH
            and self.mode not in PROPOSAL_AUTHORITY_MODES
        ):
            raise ValueError(
                "factorized authority search requires proposal authority mode"
            )
        if (
            self.authority_search_strategy
            == PAIRWISE_FACTORIZED_AUTHORITY_SEARCH
        ):
            if not self.authority_factorization_compatible:
                raise ValueError(
                    "factorized authority search requires explicitly compatible "
                    "callbacks"
                )
            if self.component_edge_validator is None:
                raise ValueError(
                    "factorized authority search requires an exact edge validator"
                )
        if self.topology_tiebreak:
            if self.mode != PROTECTED_PROPOSAL_AUTHORITY_SEARCH:
                raise ValueError(
                    "topology tie-break requires protected proposal authority mode"
                )
            if len(self.topology_net_ids) != len(self.topology_net_degrees):
                raise ValueError(
                    "topology tie-break net ids and degrees must align"
                )
            if len(set(self.topology_net_ids)) != len(self.topology_net_ids):
                raise ValueError("topology tie-break net ids must be unique")
            if any(value < 0 for value in self.topology_net_ids):
                raise ValueError(
                    "topology tie-break net ids must be non-negative"
                )
            if any(value < 2 for value in self.topology_net_degrees):
                raise ValueError(
                    "topology tie-break net degrees must be at least two"
                )
            if self.topology_net_ids and self.topology_evaluator is None:
                raise ValueError(
                    "topology tie-break selected nets require an evaluator"
                )
        elif (
            self.topology_evaluator is not None
            or self.topology_net_ids
            or self.topology_net_degrees
        ):
            raise ValueError(
                "topology evaluator inputs require the topology tie-break"
            )
        invalid_active = sorted(
            node_id
            for node_id in self.active_node_ids
            if node_id < 0 or node_id >= self.num_nodes
        )
        if invalid_active:
            raise ValueError("contact projection has invalid active node ids")

    def consume_validation_provenance(self):
        provenance = self._validation_provenance
        self._validation_provenance = None
        return provenance

    def _overlap_edges(self, report):
        edges = set()
        for row in report.get("overlap_pairs", ()):
            try:
                first_node_id = self.refdes_to_node_id[row["first_refdes"]]
                second_node_id = self.refdes_to_node_id[row["second_refdes"]]
            except KeyError as error:
                raise KeyError(
                    "contact projection cannot map exact overlap endpoint: %s"
                    % error.args[0]
                ) from error
            if first_node_id == second_node_id:
                raise ValueError("contact projection received a self-overlap")
            edges.add(tuple(sorted((first_node_id, second_node_id))))
        return edges

    def _component_plan(
        self,
        reference,
        position,
        reference_displacement,
        displacement_values,
        component,
    ):
        active = tuple(
            node_id
            for node_id in component
            if node_id in self.active_node_ids
        )
        inactive = tuple(
            node_id
            for node_id in component
            if node_id not in self.active_node_ids
        )
        if not active:
            raise ValueError("contact component has no active endpoint")

        if inactive:
            displacement = reference.new_tensor(
                (
                    math.fsum(
                        displacement_values[node_id][0] for node_id in inactive
                    )
                    / len(inactive),
                    math.fsum(
                        displacement_values[node_id][1] for node_id in inactive
                    )
                    / len(inactive),
                )
            )
            authority_kind = "inactive_mean"
            representative_node_id = None
            corrected_node_ids = active
        else:
            representative_node_id = _representative_node_id(
                displacement_values, active
            )
            displacement = reference_displacement[representative_node_id]
            authority_kind = "active_representative"
            corrected_node_ids = tuple(
                node_id
                for node_id in active
                if node_id != representative_node_id
            )
            representative_changed = not (
                torch.equal(
                    position[representative_node_id : representative_node_id + 1],
                    reference[
                        representative_node_id : representative_node_id + 1
                    ],
                )
                and torch.equal(
                    position[
                        self.num_nodes
                        + representative_node_id : self.num_nodes
                        + representative_node_id
                        + 1
                    ],
                    reference[
                        self.num_nodes
                        + representative_node_id : self.num_nodes
                        + representative_node_id
                        + 1
                    ],
                )
            )
            if representative_changed:
                corrected_node_ids = tuple(
                    sorted(corrected_node_ids + (representative_node_id,))
                )

        return {
            "node_ids": tuple(component),
            "active_node_ids": active,
            "inactive_node_ids": inactive,
            "authority_kind": authority_kind,
            "representative_node_id": representative_node_id,
            "corrected_node_ids": corrected_node_ids,
            "displacement": displacement,
        }

    def _component_plans(
        self,
        reference,
        position,
        reference_displacement,
        displacement_values,
        components,
    ):
        return tuple(
            self._component_plan(
                reference,
                position,
                reference_displacement,
                displacement_values,
                component,
            )
            for component in components
        )

    def _minimum_cover_component_plan(
        self,
        component,
        component_edges,
        current_displacement_values,
        proposal_displacement_values,
        corrected_contact_node_ids,
    ):
        active = tuple(
            node_id
            for node_id in component
            if node_id in self.active_node_ids
        )
        inactive = tuple(
            node_id
            for node_id in component
            if node_id not in self.active_node_ids
        )
        selectable = frozenset(
            node_id
            for node_id in active
            if current_displacement_values[node_id] != (0.0, 0.0)
        )
        plan = {
            "node_ids": tuple(component),
            "active_node_ids": active,
            "inactive_node_ids": inactive,
            "authority_kind": "accepted_origin_cover",
            "representative_node_id": None,
            "corrected_node_ids": (),
            "selectable_node_ids": tuple(sorted(selectable)),
            "mandatory_node_ids": (),
            "newly_selected_node_ids": (),
            "minimum_cover_size": 0,
            "search_state_count": 0,
        }
        if not active:
            plan["planning_reason"] = "immutable_overlap"
            return plan, plan["planning_reason"]
        if len(component) > self.max_cover_component_nodes:
            plan["planning_reason"] = "cover_component_limit"
            return plan, plan["planning_reason"]

        mandatory = set()
        for first_node_id, second_node_id in component_edges:
            selectable_endpoints = tuple(
                node_id
                for node_id in (first_node_id, second_node_id)
                if node_id in selectable
            )
            if not selectable_endpoints:
                plan["mandatory_node_ids"] = tuple(sorted(mandatory))
                plan["planning_reason"] = "unresolvable_overlap"
                return plan, plan["planning_reason"]
            if len(selectable_endpoints) == 1:
                mandatory.add(selectable_endpoints[0])

        optional = tuple(sorted(selectable.difference(mandatory)))
        best_key = None
        best_selection = None
        search_state_count = 0
        for selection_mask in range(1 << len(optional)):
            search_state_count += 1
            selected = set(mandatory)
            selected.update(
                node_id
                for bit, node_id in enumerate(optional)
                if selection_mask & (1 << bit)
            )
            if not all(
                first_node_id in selected or second_node_id in selected
                for first_node_id, second_node_id in component_edges
            ):
                continue
            selected_tuple = tuple(sorted(selected))
            removed_motion = math.fsum(
                proposal_displacement_values[node_id][0] ** 2
                + proposal_displacement_values[node_id][1] ** 2
                for node_id in selected_tuple
            )
            if not math.isfinite(removed_motion):
                raise ValueError("contact projection received non-finite motion")
            key = (
                len(selected.difference(corrected_contact_node_ids)),
                removed_motion,
                selected_tuple,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_selection = selected_tuple

        if best_selection is None:
            plan["mandatory_node_ids"] = tuple(sorted(mandatory))
            plan["search_state_count"] = search_state_count
            plan["planning_reason"] = "unresolvable_overlap"
            return plan, plan["planning_reason"]
        newly_selected = tuple(
            node_id
            for node_id in best_selection
            if node_id not in corrected_contact_node_ids
        )
        plan.update(
            {
                "corrected_node_ids": best_selection,
                "mandatory_node_ids": tuple(sorted(mandatory)),
                "newly_selected_node_ids": newly_selected,
                "minimum_cover_size": len(best_selection),
                "search_state_count": search_state_count,
                "planning_reason": None,
            }
        )
        return plan, None

    def _minimum_cover_plans(
        self,
        components,
        current_edges,
        current_displacement_values,
        proposal_displacement_values,
        corrected_contact_node_ids,
    ):
        plans = []
        for component in components:
            component_set = frozenset(component)
            component_edges = tuple(
                edge
                for edge in sorted(current_edges)
                if edge[0] in component_set
            )
            plan, reason = self._minimum_cover_component_plan(
                component,
                component_edges,
                current_displacement_values,
                proposal_displacement_values,
                corrected_contact_node_ids,
            )
            plans.append(plan)
            if reason is not None:
                return tuple(plans), reason
        return tuple(plans), None

    def _proposal_authority_component_plan_exhaustive(
        self,
        component,
        component_edges,
        origin_coordinate_values,
        reference_coordinate_values,
        current_coordinate_values,
        proposal_displacement_values,
        proposal_displacement_keys,
        proposal_coordinate_keys,
        coordinate_template,
        corrected_contact_node_ids,
    ):
        active = tuple(
            node_id
            for node_id in component
            if node_id in self.active_node_ids
        )
        inactive = tuple(
            node_id
            for node_id in component
            if node_id not in self.active_node_ids
        )
        plan = {
            "node_ids": tuple(component),
            "active_node_ids": active,
            "inactive_node_ids": inactive,
            "authority_kind": self.mode,
            "representative_node_id": None,
            "corrected_node_ids": (),
            "available_authority_node_ids": (),
            "authority_assignments": (),
            "authority_state_count": 0,
            "authority_exact_test_count": 0,
            "valid_authority_state_count": 0,
            "correction_energy": 0.0,
            "authority_corrected_node_ids": (),
            "hard_projected_node_ids": (),
            "hard_projection_max_distance": 0.0,
            "authority_projection_seconds": 0.0,
            "authority_validator_seconds": 0.0,
        }
        if not active:
            plan["planning_reason"] = "immutable_overlap"
            return plan, plan["planning_reason"]
        if len(component) > self.max_cover_component_nodes:
            plan["planning_reason"] = "authority_component_limit"
            return plan, plan["planning_reason"]

        authority_by_key = {}
        for node_id in component:
            key = proposal_displacement_keys[node_id]
            authority_by_key.setdefault(
                key,
                {
                    "node_id": node_id,
                    "displacement": proposal_displacement_values[node_id],
                    "key": key,
                },
            )
        authorities = tuple(
            sorted(authority_by_key.values(), key=lambda row: row["node_id"])
        )
        plan["available_authority_node_ids"] = tuple(
            row["node_id"] for row in authorities
        )
        state_count = len(authorities) ** len(active)
        plan["authority_state_count"] = state_count
        if state_count > self.max_authority_states:
            plan["planning_reason"] = "authority_state_limit"
            return plan, plan["planning_reason"]

        best_key = None
        best = None
        exact_test_count = 0
        valid_state_count = 0
        projection_seconds = 0.0
        validator_seconds = 0.0
        for authority_indices in itertools.product(
            range(len(authorities)), repeat=len(active)
        ):
            assignment = tuple(
                (node_id, authorities[authority_index])
                for node_id, authority_index in zip(
                    active, authority_indices
                )
            )
            raw_coordinate_values = {
                node_id: current_coordinate_values[node_id]
                for node_id in component
            }
            assignment_key = []
            for node_id, authority in assignment:
                displacement = authority["displacement"]
                assignment_key.append((node_id, authority["node_id"]))
                if authority["key"] == proposal_displacement_keys[node_id]:
                    raw_coordinate_values[node_id] = (
                        reference_coordinate_values[node_id]
                    )
                    continue
                origin_x, origin_y = origin_coordinate_values[node_id]
                raw_coordinate_values[node_id] = (
                    origin_x + displacement[0],
                    origin_y + displacement[1],
                )

            node_ids = tuple(sorted(raw_coordinate_values))
            raw_coordinates = coordinate_template.new_tensor(
                tuple(raw_coordinate_values[node_id] for node_id in node_ids)
            )
            raw_coordinate_values = {
                node_id: (float(row[0]), float(row[1]))
                for node_id, row in zip(node_ids, raw_coordinates.tolist())
            }
            projection_started = time.perf_counter()
            projection = self.component_projector(raw_coordinate_values, active)
            projection_seconds += time.perf_counter() - projection_started
            projected_coordinate_values = {
                int(node_id): (float(value[0]), float(value[1]))
                for node_id, value in projection.get("coordinates", {}).items()
            }
            if set(projected_coordinate_values) != set(component):
                raise ValueError(
                    "hard component projector changed the coordinate scope"
                )
            projected_coordinates = coordinate_template.new_tensor(
                tuple(
                    projected_coordinate_values[node_id]
                    for node_id in node_ids
                )
            )
            projected_coordinate_values = {
                node_id: (float(row[0]), float(row[1]))
                for node_id, row in zip(
                    node_ids, projected_coordinates.tolist()
                )
            }

            raw_keys = {
                node_id: row.contiguous().numpy().tobytes()
                for node_id, row in zip(node_ids, raw_coordinates)
            }
            projected_keys = {
                node_id: row.contiguous().numpy().tobytes()
                for node_id, row in zip(node_ids, projected_coordinates)
            }
            hard_projected_node_ids = tuple(
                node_id
                for node_id in active
                if projected_keys[node_id] != raw_keys[node_id]
            )
            reported_projected_node_ids = tuple(
                sorted(
                    int(node_id)
                    for node_id in projection.get("projected_node_ids", ())
                )
            )
            if hard_projected_node_ids != reported_projected_node_ids:
                raise ValueError(
                    "hard component projector reported inconsistent node ids"
                )

            corrected_node_ids = tuple(
                node_id
                for node_id in active
                if projected_keys[node_id]
                != proposal_coordinate_keys[node_id]
            )
            authority_corrected_node_ids = tuple(
                node_id
                for node_id in active
                if raw_keys[node_id] != proposal_coordinate_keys[node_id]
            )
            correction_terms = []
            for node_id in corrected_node_ids:
                proposal_x, proposal_y = reference_coordinate_values[node_id]
                selected_x, selected_y = projected_coordinate_values[node_id]
                correction_terms.append(
                    (selected_x - proposal_x) ** 2
                    + (selected_y - proposal_y) ** 2
                )

            validation_started = time.perf_counter()
            report = self.component_validator(
                projected_coordinate_values, component_edges
            )
            validator_seconds += time.perf_counter() - validation_started
            exact_test_count += 1
            if int(report.get("keepin_violation_count", 0)):
                continue
            if int(report.get("overlap_pair_count", 0)):
                continue
            valid_state_count += 1
            correction_energy = math.fsum(correction_terms)
            if not math.isfinite(correction_energy):
                raise ValueError(
                    "contact projection received non-finite correction"
                )
            key = (
                len(
                    set(corrected_node_ids).difference(
                        corrected_contact_node_ids
                    )
                ),
                correction_energy,
                tuple(assignment_key),
            )
            if best_key is None or key < best_key:
                best_key = key
                best = {
                    "corrected_node_ids": corrected_node_ids,
                    "authority_assignments": tuple(
                        (node_id, authority["node_id"])
                        for node_id, authority in assignment
                    ),
                    "assigned_coordinates": tuple(
                        (node_id, projected_coordinate_values[node_id])
                        for node_id, _ in assignment
                    ),
                    "correction_energy": correction_energy,
                    "authority_corrected_node_ids": (
                        authority_corrected_node_ids
                    ),
                    "hard_projected_node_ids": hard_projected_node_ids,
                    "hard_projection_max_distance": float(
                        projection.get("max_distance", 0.0)
                    ),
                }

        plan["authority_exact_test_count"] = exact_test_count
        plan["valid_authority_state_count"] = valid_state_count
        plan["authority_projection_seconds"] = projection_seconds
        plan["authority_validator_seconds"] = validator_seconds
        if best is None:
            plan["planning_reason"] = "unresolvable_authority"
            return plan, plan["planning_reason"]
        plan.update(best)
        plan["newly_selected_node_ids"] = tuple(
            node_id
            for node_id in best["corrected_node_ids"]
            if node_id not in corrected_contact_node_ids
        )
        plan["planning_reason"] = None
        return plan, None

    def _proposal_authority_component_plan_factorized(
        self,
        component,
        component_edges,
        origin_coordinate_values,
        reference_coordinate_values,
        current_coordinate_values,
        proposal_displacement_values,
        proposal_displacement_keys,
        proposal_coordinate_keys,
        coordinate_template,
        corrected_contact_node_ids,
    ):
        active = tuple(
            node_id
            for node_id in component
            if node_id in self.active_node_ids
        )
        inactive = tuple(
            node_id
            for node_id in component
            if node_id not in self.active_node_ids
        )
        plan = {
            "node_ids": tuple(component),
            "active_node_ids": active,
            "inactive_node_ids": inactive,
            "authority_kind": self.mode,
            "representative_node_id": None,
            "corrected_node_ids": (),
            "available_authority_node_ids": (),
            "authority_assignments": (),
            "authority_state_count": 0,
            "authority_exact_test_count": 0,
            "valid_authority_state_count": 0,
            "correction_energy": 0.0,
            "authority_corrected_node_ids": (),
            "hard_projected_node_ids": (),
            "hard_projection_max_distance": 0.0,
            "authority_projection_seconds": 0.0,
            "authority_validator_seconds": 0.0,
            "authority_search_strategy": self.authority_search_strategy,
            "authority_unique_state_count": 0,
            "authority_duplicate_state_prune_count": 0,
            "authority_node_infeasible_state_count": 0,
            "authority_pairwise_pruned_state_count": 0,
            "authority_objective_pruned_state_count": 0,
            "authority_admissibly_pruned_state_count": 0,
            "authority_node_candidate_count": 0,
            "authority_node_exact_test_count": 0,
            "authority_pair_exact_test_count": 0,
            "authority_pair_cache_hit_count": 0,
            "authority_full_exact_test_count": 0,
        }
        if not active:
            plan["planning_reason"] = "immutable_overlap"
            return plan, plan["planning_reason"]
        if len(component) > self.max_cover_component_nodes:
            plan["planning_reason"] = "authority_component_limit"
            return plan, plan["planning_reason"]

        authority_by_key = {}
        for node_id in component:
            key = proposal_displacement_keys[node_id]
            authority_by_key.setdefault(
                key,
                {
                    "node_id": node_id,
                    "displacement": proposal_displacement_values[node_id],
                    "key": key,
                },
            )
        authorities = tuple(
            sorted(authority_by_key.values(), key=lambda row: row["node_id"])
        )
        plan["available_authority_node_ids"] = tuple(
            row["node_id"] for row in authorities
        )
        state_count = len(authorities) ** len(active)
        plan["authority_state_count"] = state_count
        if state_count > self.max_authority_states:
            plan["planning_reason"] = "authority_state_limit"
            return plan, plan["planning_reason"]

        projection_seconds = 0.0
        validator_seconds = 0.0
        node_exact_test_count = 0
        candidate_rows = {}
        canonical_current = {}
        for node_id in component:
            row = coordinate_template.new_tensor(
                (current_coordinate_values[node_id],)
            )[0]
            canonical_current[node_id] = (float(row[0]), float(row[1]))

        for node_id in active:
            rows = []
            for authority in authorities:
                if authority["key"] == proposal_displacement_keys[node_id]:
                    raw_value = reference_coordinate_values[node_id]
                else:
                    origin_x, origin_y = origin_coordinate_values[node_id]
                    displacement_x, displacement_y = authority["displacement"]
                    raw_value = (
                        origin_x + displacement_x,
                        origin_y + displacement_y,
                    )
                raw_row = coordinate_template.new_tensor((raw_value,))[0]
                raw_value = (float(raw_row[0]), float(raw_row[1]))
                raw_key = raw_row.contiguous().numpy().tobytes()
                raw_coordinates = dict(canonical_current)
                raw_coordinates[node_id] = raw_value

                projection_started = time.perf_counter()
                projection = self.component_projector(
                    raw_coordinates, (node_id,)
                )
                projection_seconds += time.perf_counter() - projection_started
                projected_values = {
                    int(projected_node_id): (
                        float(value[0]),
                        float(value[1]),
                    )
                    for projected_node_id, value in projection.get(
                        "coordinates", {}
                    ).items()
                }
                if set(projected_values) != set(component):
                    raise ValueError(
                        "hard component projector changed the coordinate scope"
                    )
                projected_tensor = coordinate_template.new_tensor(
                    tuple(projected_values[value] for value in component)
                )
                projected_values = {
                    value: (float(row[0]), float(row[1]))
                    for value, row in zip(component, projected_tensor)
                }
                projected_keys = {
                    value: row.contiguous().numpy().tobytes()
                    for value, row in zip(component, projected_tensor)
                }
                unchanged_other_nodes = all(
                    projected_values[value] == canonical_current[value]
                    for value in component
                    if value != node_id
                )
                if not unchanged_other_nodes:
                    raise ValueError(
                        "factorized authority projector is not node-separable"
                    )
                hard_projected = (
                    projected_keys[node_id] != raw_key
                )
                reported_projected_node_ids = tuple(
                    sorted(
                        int(value)
                        for value in projection.get("projected_node_ids", ())
                    )
                )
                expected_projected_node_ids = (
                    (node_id,) if hard_projected else ()
                )
                if reported_projected_node_ids != expected_projected_node_ids:
                    raise ValueError(
                        "hard component projector reported inconsistent node ids"
                    )

                validation_started = time.perf_counter()
                node_report = self.component_edge_validator(
                    {node_id: projected_values[node_id]}, ()
                )
                validator_seconds += time.perf_counter() - validation_started
                node_exact_test_count += 1
                rows.append(
                    {
                        "authority_node_id": authority["node_id"],
                        "raw_key": raw_key,
                        "projected_key": projected_keys[node_id],
                        "projected_value": projected_values[node_id],
                        "hard_projected": hard_projected,
                        "hard_projection_max_distance": float(
                            projection.get("max_distance", 0.0)
                        ),
                        "keepin_legal": not int(
                            node_report.get("keepin_violation_count", 0)
                        ),
                    }
                )
            candidate_rows[node_id] = tuple(rows)

        pair_cache = {}
        pair_exact_test_count = 0
        pair_cache_hit_count = 0

        def pair_is_legal(edge, first_row, second_row):
            nonlocal pair_exact_test_count, pair_cache_hit_count
            nonlocal validator_seconds
            first_node_id, second_node_id = edge
            first_key = first_row["projected_key"]
            second_key = second_row["projected_key"]
            cache_key = (edge, first_key, second_key)
            if cache_key in pair_cache:
                pair_cache_hit_count += 1
                return pair_cache[cache_key]
            validation_started = time.perf_counter()
            report = self.component_edge_validator(
                {
                    first_node_id: first_row["projected_value"],
                    second_node_id: second_row["projected_value"],
                },
                (edge,),
            )
            validator_seconds += time.perf_counter() - validation_started
            pair_exact_test_count += 1
            legal = not int(report.get("keepin_violation_count", 0)) and not int(
                report.get("overlap_pair_count", 0)
            )
            pair_cache[cache_key] = legal
            return legal

        inactive_rows = {}
        for node_id in inactive:
            row = coordinate_template.new_tensor(
                (canonical_current[node_id],)
            )[0]
            inactive_rows[node_id] = {
                "authority_node_id": node_id,
                "raw_key": row.contiguous().numpy().tobytes(),
                "projected_key": row.contiguous().numpy().tobytes(),
                "projected_value": (float(row[0]), float(row[1])),
                "hard_projected": False,
                "hard_projection_max_distance": 0.0,
                "keepin_legal": True,
            }

        seen_states = {}
        best_key = None
        best = None
        valid_state_count = 0
        duplicate_state_count = 0
        node_infeasible_state_count = 0
        pairwise_pruned_state_count = 0
        valid_unique_state_count = 0
        for authority_indices in itertools.product(
            range(len(authorities)), repeat=len(active)
        ):
            selected = {
                node_id: candidate_rows[node_id][authority_index]
                for node_id, authority_index in zip(active, authority_indices)
            }
            coordinate_key = tuple(
                selected[node_id]["projected_key"] for node_id in active
            )
            if coordinate_key in seen_states:
                duplicate_state_count += 1
                if seen_states[coordinate_key]:
                    valid_state_count += 1
                continue

            keepin_legal = all(
                row["keepin_legal"] for row in selected.values()
            )
            legal = keepin_legal
            if keepin_legal:
                for edge in component_edges:
                    first_node_id, second_node_id = edge
                    first_row = selected.get(
                        first_node_id, inactive_rows.get(first_node_id)
                    )
                    second_row = selected.get(
                        second_node_id, inactive_rows.get(second_node_id)
                    )
                    if first_row is None or second_row is None:
                        raise ValueError(
                            "factorized authority edge left the component"
                        )
                    if not pair_is_legal(edge, first_row, second_row):
                        legal = False
                        break
            seen_states[coordinate_key] = legal
            if not legal:
                if keepin_legal:
                    pairwise_pruned_state_count += 1
                else:
                    node_infeasible_state_count += 1
                continue

            valid_state_count += 1
            valid_unique_state_count += 1
            corrected_node_ids = tuple(
                node_id
                for node_id in active
                if selected[node_id]["projected_key"]
                != proposal_coordinate_keys[node_id]
            )
            correction_terms = []
            for node_id in corrected_node_ids:
                proposal_x, proposal_y = reference_coordinate_values[node_id]
                selected_x, selected_y = selected[node_id]["projected_value"]
                correction_terms.append(
                    (selected_x - proposal_x) ** 2
                    + (selected_y - proposal_y) ** 2
                )
            correction_energy = math.fsum(correction_terms)
            if not math.isfinite(correction_energy):
                raise ValueError(
                    "contact projection received non-finite correction"
                )
            assignment_key = tuple(
                (node_id, selected[node_id]["authority_node_id"])
                for node_id in active
            )
            key = (
                len(
                    set(corrected_node_ids).difference(
                        corrected_contact_node_ids
                    )
                ),
                correction_energy,
                assignment_key,
            )
            if best_key is not None and key >= best_key:
                continue
            best_key = key
            best = {
                "corrected_node_ids": corrected_node_ids,
                "authority_assignments": assignment_key,
                "assigned_coordinates": tuple(
                    (node_id, selected[node_id]["projected_value"])
                    for node_id in active
                ),
                "correction_energy": correction_energy,
                "authority_corrected_node_ids": tuple(
                    node_id
                    for node_id in active
                    if selected[node_id]["raw_key"]
                    != proposal_coordinate_keys[node_id]
                ),
                "hard_projected_node_ids": tuple(
                    node_id
                    for node_id in active
                    if selected[node_id]["hard_projected"]
                ),
                "hard_projection_max_distance": max(
                    (
                        selected[node_id]["hard_projection_max_distance"]
                        for node_id in active
                    ),
                    default=0.0,
                ),
            }

        plan["authority_projection_seconds"] = projection_seconds
        plan["authority_validator_seconds"] = validator_seconds
        plan["authority_unique_state_count"] = len(seen_states)
        plan["authority_duplicate_state_prune_count"] = duplicate_state_count
        plan["authority_node_infeasible_state_count"] = (
            node_infeasible_state_count
        )
        plan["authority_pairwise_pruned_state_count"] = (
            pairwise_pruned_state_count
        )
        plan["authority_objective_pruned_state_count"] = max(
            valid_unique_state_count - (1 if best is not None else 0), 0
        )
        plan["authority_node_candidate_count"] = len(active) * len(authorities)
        plan["authority_node_exact_test_count"] = node_exact_test_count
        plan["authority_pair_exact_test_count"] = pair_exact_test_count
        plan["authority_pair_cache_hit_count"] = pair_cache_hit_count
        plan["valid_authority_state_count"] = valid_state_count
        plan["authority_admissibly_pruned_state_count"] = (
            duplicate_state_count
            + node_infeasible_state_count
            + pairwise_pruned_state_count
            + plan["authority_objective_pruned_state_count"]
        )
        if best is None:
            plan["planning_reason"] = "unresolvable_authority"
            return plan, plan["planning_reason"]

        selected_coordinates = dict(canonical_current)
        selected_coordinates.update(dict(best["assigned_coordinates"]))
        validation_started = time.perf_counter()
        report = self.component_validator(
            selected_coordinates, component_edges
        )
        full_validation_seconds = time.perf_counter() - validation_started
        plan["authority_validator_seconds"] += full_validation_seconds
        plan["authority_exact_test_count"] = 1
        plan["authority_full_exact_test_count"] = 1
        if int(report.get("keepin_violation_count", 0)) or int(
            report.get("overlap_pair_count", 0)
        ):
            plan["planning_reason"] = "authority_factorization_mismatch"
            return plan, plan["planning_reason"]

        plan.update(best)
        plan["newly_selected_node_ids"] = tuple(
            node_id
            for node_id in best["corrected_node_ids"]
            if node_id not in corrected_contact_node_ids
        )
        plan["planning_reason"] = None
        return plan, None

    def _proposal_authority_component_plan(
        self,
        component,
        component_edges,
        origin_coordinate_values,
        reference_coordinate_values,
        current_coordinate_values,
        proposal_displacement_values,
        proposal_displacement_keys,
        proposal_coordinate_keys,
        coordinate_template,
        corrected_contact_node_ids,
    ):
        arguments = (
            component,
            component_edges,
            origin_coordinate_values,
            reference_coordinate_values,
            current_coordinate_values,
            proposal_displacement_values,
            proposal_displacement_keys,
            proposal_coordinate_keys,
            coordinate_template,
            corrected_contact_node_ids,
        )
        if (
            self.authority_search_strategy
            == PAIRWISE_FACTORIZED_AUTHORITY_SEARCH
        ):
            return self._proposal_authority_component_plan_factorized(
                *arguments
            )
        return self._proposal_authority_component_plan_exhaustive(*arguments)

    def _proposal_authority_plans(
        self,
        components,
        current_edges,
        origin_coordinate_values,
        reference_coordinate_values,
        current_coordinate_values,
        proposal_displacement_values,
        proposal_displacement_keys,
        proposal_coordinate_keys,
        coordinate_template,
        corrected_contact_node_ids,
    ):
        plans = []
        for component in components:
            component_set = frozenset(component)
            component_edges = tuple(
                edge
                for edge in sorted(current_edges)
                if edge[0] in component_set
            )
            plan, reason = self._proposal_authority_component_plan(
                component,
                component_edges,
                origin_coordinate_values,
                reference_coordinate_values,
                current_coordinate_values,
                proposal_displacement_values,
                proposal_displacement_keys,
                proposal_coordinate_keys,
                coordinate_template,
                corrected_contact_node_ids,
            )
            plans.append(plan)
            if reason is not None:
                return tuple(plans), reason
        return tuple(plans), None

    def _apply_consensus(self, reference, origin, position, plans):
        for plan in plans:
            corrected_node_ids = plan["corrected_node_ids"]
            if not corrected_node_ids:
                continue
            representative_node_id = plan["representative_node_id"]
            motion_node_ids = tuple(
                node_id
                for node_id in corrected_node_ids
                if node_id != representative_node_id
            )
            if motion_node_ids:
                index = torch.as_tensor(
                    motion_node_ids, dtype=torch.long, device=position.device
                )
                position.index_copy_(
                    0,
                    index,
                    origin.index_select(0, index) + plan["displacement"][0],
                )
                position.index_copy_(
                    0,
                    self.num_nodes + index,
                    origin.index_select(0, self.num_nodes + index)
                    + plan["displacement"][1],
                )
            if representative_node_id in corrected_node_ids:
                position[representative_node_id].copy_(
                    reference[representative_node_id]
                )
                position[self.num_nodes + representative_node_id].copy_(
                    reference[self.num_nodes + representative_node_id]
                )

    def _apply_origin_rollback(self, origin, position, plans):
        corrected_node_ids = tuple(
            sorted(
                {
                    node_id
                    for plan in plans
                    for node_id in plan["corrected_node_ids"]
                }
            )
        )
        if not corrected_node_ids:
            return
        index = torch.as_tensor(
            corrected_node_ids, dtype=torch.long, device=position.device
        )
        position.index_copy_(0, index, origin.index_select(0, index))
        position.index_copy_(
            0,
            self.num_nodes + index,
            origin.index_select(0, self.num_nodes + index),
        )

    def _apply_proposal_authorities(self, position, plans):
        assignments = tuple(
            assignment
            for plan in plans
            for assignment in plan.get("assigned_coordinates", ())
        )
        if not assignments:
            return
        node_ids = tuple(node_id for node_id, _ in assignments)
        index = torch.as_tensor(
            node_ids, dtype=torch.long, device=position.device
        )
        coordinates = position.new_tensor(
            tuple(value for _, value in assignments)
        )
        position.index_copy_(
            0,
            index,
            coordinates[:, 0],
        )
        position.index_copy_(
            0,
            self.num_nodes + index,
            coordinates[:, 1],
        )

    def _consensus_topology_candidate(
        self,
        reference,
        origin,
        position,
        plans,
        components,
        validated_contact_edges,
    ):
        started = time.perf_counter()
        candidate = position.detach().clone()
        self._apply_consensus(reference, origin, candidate, plans)
        candidate_cpu = candidate.detach().cpu().contiguous()
        projected_node_ids = set()
        projection_seconds = 0.0
        validator_seconds = 0.0
        validator_call_count = 0
        projection_max_distance = 0.0

        for component in components:
            component = tuple(component)
            component_set = frozenset(component)
            active = tuple(
                node_id
                for node_id in component
                if node_id in self.active_node_ids
            )
            coordinate_values = {
                node_id: (
                    float(candidate_cpu[node_id]),
                    float(candidate_cpu[self.num_nodes + node_id]),
                )
                for node_id in component
            }
            projection_started = time.perf_counter()
            projection = self.component_projector(coordinate_values, active)
            projection_seconds += time.perf_counter() - projection_started
            projected_values = {
                int(node_id): (float(value[0]), float(value[1]))
                for node_id, value in projection.get("coordinates", {}).items()
            }
            if set(projected_values) != component_set:
                raise ValueError(
                    "topology consensus projector changed the coordinate scope"
                )
            canonical = candidate_cpu.new_tensor(
                tuple(projected_values[node_id] for node_id in component)
            )
            canonical_values = {
                node_id: (float(row[0]), float(row[1]))
                for node_id, row in zip(component, canonical)
            }
            changed = tuple(
                node_id
                for node_id in component
                if canonical_values[node_id] != coordinate_values[node_id]
            )
            if any(node_id not in self.active_node_ids for node_id in changed):
                raise ValueError(
                    "topology consensus projector changed an inactive node"
                )
            reported = tuple(
                sorted(
                    int(node_id)
                    for node_id in projection.get("projected_node_ids", ())
                )
            )
            if tuple(sorted(changed)) != reported:
                raise ValueError(
                    "topology consensus projector reported inconsistent node ids"
                )
            projected_node_ids.update(changed)
            projection_max_distance = max(
                projection_max_distance,
                float(projection.get("max_distance", 0.0)),
            )
            for node_id, row in zip(component, canonical):
                candidate_cpu[node_id] = row[0]
                candidate_cpu[self.num_nodes + node_id] = row[1]

            component_edges = tuple(
                edge
                for edge in sorted(validated_contact_edges)
                if edge[0] in component_set and edge[1] in component_set
            )
            validation_started = time.perf_counter()
            report = self.component_validator(
                canonical_values, component_edges
            )
            validator_seconds += time.perf_counter() - validation_started
            validator_call_count += 1
            if int(report.get("keepin_violation_count", 0)):
                return None, {
                    "eligible": False,
                    "ineligible_reason": "keepin_violation",
                    "projected_node_ids": sorted(projected_node_ids),
                    "projection_max_distance": projection_max_distance,
                    "projection_seconds": projection_seconds,
                    "validator_call_count": validator_call_count,
                    "validator_seconds": validator_seconds,
                    "generation_seconds": time.perf_counter() - started,
                }
            if int(report.get("overlap_pair_count", 0)):
                return None, {
                    "eligible": False,
                    "ineligible_reason": "protected_edge_reopened",
                    "projected_node_ids": sorted(projected_node_ids),
                    "projection_max_distance": projection_max_distance,
                    "projection_seconds": projection_seconds,
                    "validator_call_count": validator_call_count,
                    "validator_seconds": validator_seconds,
                    "generation_seconds": time.perf_counter() - started,
                }

        candidate.copy_(candidate_cpu.to(candidate.device))
        return candidate, {
            "eligible": True,
            "ineligible_reason": None,
            "projected_node_ids": sorted(projected_node_ids),
            "projection_max_distance": projection_max_distance,
            "projection_seconds": projection_seconds,
            "validator_call_count": validator_call_count,
            "validator_seconds": validator_seconds,
            "generation_seconds": time.perf_counter() - started,
        }

    def _evaluate_topology_candidate(self, candidate):
        started = time.perf_counter()
        score = self.topology_evaluator(candidate)
        elapsed = time.perf_counter() - started
        if not isinstance(score, dict):
            raise ValueError("topology evaluator must return a dictionary")
        hpwl = float(score["hpwl"])
        rsmt = float(score["rsmt"])
        if not math.isfinite(hpwl) or not math.isfinite(rsmt):
            raise ValueError("topology evaluator returned a non-finite score")
        return {
            "selected_net_hpwl": hpwl,
            "selected_net_rsmt": rsmt,
            "scoring_seconds": elapsed,
        }

    def _select_topology_candidate(
        self,
        reference,
        origin,
        position,
        authority_plans,
        consensus_plans,
        components,
        validated_contact_edges,
    ):
        started = time.perf_counter()
        authority_candidate = position.detach().clone()
        self._apply_proposal_authorities(
            authority_candidate, authority_plans
        )
        if not self.topology_net_ids:
            decision = {
                "enabled": True,
                "selected_candidate": AUTHORITY_TOPOLOGY_CANDIDATE,
                "selection_reason": "no_topology_sensitive_nets",
                "selected_nets": [],
                "score_call_count": 0,
                "scoring_seconds": 0.0,
                "elapsed_seconds": time.perf_counter() - started,
                "candidates": {
                    AUTHORITY_TOPOLOGY_CANDIDATE: {
                        "eligible": True,
                        "ineligible_reason": None,
                    },
                    CONSENSUS_TOPOLOGY_CANDIDATE: {
                        "eligible": False,
                        "ineligible_reason": "no_topology_sensitive_nets",
                        "projected_node_ids": [],
                        "projection_max_distance": 0.0,
                        "projection_seconds": 0.0,
                        "validator_call_count": 0,
                        "validator_seconds": 0.0,
                        "generation_seconds": 0.0,
                    },
                },
            }
            return authority_candidate, authority_plans, decision
        consensus_candidate, consensus = self._consensus_topology_candidate(
            reference,
            origin,
            position,
            consensus_plans,
            components,
            validated_contact_edges,
        )
        candidates = {
            AUTHORITY_TOPOLOGY_CANDIDATE: {
                "eligible": True,
                "ineligible_reason": None,
            },
            CONSENSUS_TOPOLOGY_CANDIDATE: consensus,
        }
        score_call_count = 0
        selected = AUTHORITY_TOPOLOGY_CANDIDATE
        selection_reason = "no_topology_sensitive_nets"
        if self.topology_net_ids:
            candidates[AUTHORITY_TOPOLOGY_CANDIDATE].update(
                self._evaluate_topology_candidate(authority_candidate)
            )
            score_call_count += 1
            if consensus["eligible"]:
                candidates[CONSENSUS_TOPOLOGY_CANDIDATE].update(
                    self._evaluate_topology_candidate(consensus_candidate)
                )
                score_call_count += 1
                authority_key = (
                    candidates[AUTHORITY_TOPOLOGY_CANDIDATE][
                        "selected_net_hpwl"
                    ],
                    candidates[AUTHORITY_TOPOLOGY_CANDIDATE][
                        "selected_net_rsmt"
                    ],
                    0,
                )
                consensus_key = (
                    candidates[CONSENSUS_TOPOLOGY_CANDIDATE][
                        "selected_net_hpwl"
                    ],
                    candidates[CONSENSUS_TOPOLOGY_CANDIDATE][
                        "selected_net_rsmt"
                    ],
                    1,
                )
                if consensus_key < authority_key:
                    selected = CONSENSUS_TOPOLOGY_CANDIDATE
                if consensus_key[0] < authority_key[0]:
                    selection_reason = "consensus_lower_hpwl"
                elif consensus_key[0] > authority_key[0]:
                    selection_reason = "authority_lower_hpwl"
                elif consensus_key[1] < authority_key[1]:
                    selection_reason = "consensus_lower_rsmt"
                elif consensus_key[1] > authority_key[1]:
                    selection_reason = "authority_lower_rsmt"
                else:
                    selection_reason = "exact_tie_authority"
            else:
                selection_reason = "consensus_ineligible"
        if score_call_count > 2:
            raise RuntimeError("topology tie-break exceeded its score-call bound")
        selected_candidate = (
            consensus_candidate
            if selected == CONSENSUS_TOPOLOGY_CANDIDATE
            else authority_candidate
        )
        selected_plans = (
            consensus_plans
            if selected == CONSENSUS_TOPOLOGY_CANDIDATE
            else authority_plans
        )
        scoring_seconds = math.fsum(
            float(row.get("scoring_seconds", 0.0))
            for row in candidates.values()
        )
        decision = {
            "enabled": True,
            "selected_candidate": selected,
            "selection_reason": selection_reason,
            "selected_nets": [
                {"net_id": net_id, "degree": degree}
                for net_id, degree in zip(
                    self.topology_net_ids, self.topology_net_degrees
                )
            ],
            "score_call_count": score_call_count,
            "scoring_seconds": scoring_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "candidates": candidates,
        }
        return selected_candidate, selected_plans, decision

    def _serialize_component_plan(self, plan):
        representative_node_id = plan["representative_node_id"]
        authority_node_ids = (
            plan["inactive_node_ids"]
            if plan["authority_kind"] == "inactive_mean"
            else ()
        )
        serialized = {
            "node_ids": list(plan["node_ids"]),
            "refdes": [
                self.node_id_to_refdes.get(node_id, str(node_id))
                for node_id in plan["node_ids"]
            ],
            "active_node_count": len(plan["active_node_ids"]),
            "inactive_node_count": len(plan["inactive_node_ids"]),
            "inactive_node_ids": list(plan["inactive_node_ids"]),
            "authority_kind": plan["authority_kind"],
            "authority_node_ids": list(authority_node_ids),
            "representative_node_id": representative_node_id,
            "representative_refdes": (
                self.node_id_to_refdes.get(
                    representative_node_id, str(representative_node_id)
                )
                if representative_node_id is not None
                else None
            ),
            "corrected_node_count": len(plan["corrected_node_ids"]),
            "corrected_node_ids": list(plan["corrected_node_ids"]),
            "corrected_refdes": [
                self.node_id_to_refdes.get(node_id, str(node_id))
                for node_id in plan["corrected_node_ids"]
            ],
        }
        if "selectable_node_ids" in plan:
            serialized.update(
                {
                    "selectable_node_ids": list(plan["selectable_node_ids"]),
                    "selectable_refdes": [
                        self.node_id_to_refdes.get(node_id, str(node_id))
                        for node_id in plan["selectable_node_ids"]
                    ],
                    "mandatory_node_ids": list(plan["mandatory_node_ids"]),
                    "mandatory_refdes": [
                        self.node_id_to_refdes.get(node_id, str(node_id))
                        for node_id in plan["mandatory_node_ids"]
                    ],
                    "newly_selected_node_ids": list(
                        plan["newly_selected_node_ids"]
                    ),
                    "minimum_cover_size": plan["minimum_cover_size"],
                    "search_state_count": plan["search_state_count"],
                    "planning_reason": plan.get("planning_reason"),
                }
            )
        if "available_authority_node_ids" in plan:
            serialized.update(
                {
                    "available_authority_node_ids": list(
                        plan["available_authority_node_ids"]
                    ),
                    "available_authority_refdes": [
                        self.node_id_to_refdes.get(node_id, str(node_id))
                        for node_id in plan["available_authority_node_ids"]
                    ],
                    "authority_assignments": [
                        {
                            "node_id": node_id,
                            "refdes": self.node_id_to_refdes.get(
                                node_id, str(node_id)
                            ),
                            "authority_node_id": authority_node_id,
                            "authority_refdes": self.node_id_to_refdes.get(
                                authority_node_id, str(authority_node_id)
                            ),
                        }
                        for node_id, authority_node_id in plan[
                            "authority_assignments"
                        ]
                    ],
                    "authority_state_count": plan[
                        "authority_state_count"
                    ],
                    "authority_exact_test_count": plan[
                        "authority_exact_test_count"
                    ],
                    "valid_authority_state_count": plan[
                        "valid_authority_state_count"
                    ],
                    "newly_selected_node_ids": list(
                        plan.get("newly_selected_node_ids", ())
                    ),
                    "authority_corrected_node_ids": list(
                        plan["authority_corrected_node_ids"]
                    ),
                    "hard_projected_node_ids": list(
                        plan["hard_projected_node_ids"]
                    ),
                    "hard_projection_max_distance": plan[
                        "hard_projection_max_distance"
                    ],
                    "correction_energy": plan["correction_energy"],
                    "planning_reason": plan.get("planning_reason"),
                }
            )
        if "authority_search_strategy" in plan:
            serialized.update(
                {
                    "authority_search_strategy": plan[
                        "authority_search_strategy"
                    ],
                    "authority_unique_state_count": plan[
                        "authority_unique_state_count"
                    ],
                    "authority_duplicate_state_prune_count": plan[
                        "authority_duplicate_state_prune_count"
                    ],
                    "authority_node_infeasible_state_count": plan[
                        "authority_node_infeasible_state_count"
                    ],
                    "authority_pairwise_pruned_state_count": plan[
                        "authority_pairwise_pruned_state_count"
                    ],
                    "authority_objective_pruned_state_count": plan[
                        "authority_objective_pruned_state_count"
                    ],
                    "authority_admissibly_pruned_state_count": plan[
                        "authority_admissibly_pruned_state_count"
                    ],
                    "authority_node_candidate_count": plan[
                        "authority_node_candidate_count"
                    ],
                    "authority_node_exact_test_count": plan[
                        "authority_node_exact_test_count"
                    ],
                    "authority_pair_exact_test_count": plan[
                        "authority_pair_exact_test_count"
                    ],
                    "authority_pair_cache_hit_count": plan[
                        "authority_pair_cache_hit_count"
                    ],
                    "authority_full_exact_test_count": plan[
                        "authority_full_exact_test_count"
                    ],
                }
            )
        return serialized

    def _serialize_contact_edges(self, edges):
        return [
            {
                "node_ids": list(edge),
                "refdes": [
                    self.node_id_to_refdes.get(node_id, str(node_id))
                    for node_id in edge
                ],
            }
            for edge in sorted(edges)
        ]

    def __call__(self, origin, position, hard_projector):
        self._validation_provenance = None
        if origin.shape != position.shape:
            raise ValueError("contact projection position shapes do not match")
        if origin.device != position.device or origin.dtype != position.dtype:
            raise ValueError("contact projection tensors must share device and dtype")
        if position.numel() < 2 * self.num_nodes:
            raise ValueError("contact projection position vector is too short")

        started = time.perf_counter()
        validator_seconds = 0.0
        validator_call_count = 0
        incremental_validator_attempt_count = 0
        incremental_validator_hit_count = 0
        incremental_validator_fallback_count = 0
        incremental_validator_changed_node_count = 0
        validator_modes = []
        incremental_validation_state = None
        reference = position.detach().clone()
        before = position.detach().clone()
        reference_displacement = torch.stack(
            (
                reference[: self.num_nodes] - origin[: self.num_nodes],
                reference[self.num_nodes : 2 * self.num_nodes]
                - origin[self.num_nodes : 2 * self.num_nodes],
            ),
            dim=1,
        )
        reference_displacement_cpu = (
            reference_displacement.detach().cpu().contiguous()
        )
        displacement_values = tuple(
            (float(row[0]), float(row[1]))
            for row in reference_displacement_cpu.tolist()
        )
        displacement_keys = None
        origin_coordinate_values = None
        reference_coordinate_values = None
        reference_coordinate_keys = None
        reference_cpu = None
        if self.mode in PROPOSAL_AUTHORITY_MODES:
            displacement_keys = tuple(
                row.contiguous().numpy().tobytes()
                for row in reference_displacement_cpu
            )
            origin_cpu = origin.detach().cpu().contiguous()
            origin_coordinate_values = tuple(
                (
                    float(origin_cpu[node_id]),
                    float(origin_cpu[self.num_nodes + node_id]),
                )
                for node_id in range(self.num_nodes)
            )
            reference_cpu = reference.detach().cpu().contiguous()
            reference_coordinates = torch.stack(
                (
                    reference_cpu[: self.num_nodes],
                    reference_cpu[self.num_nodes : 2 * self.num_nodes],
                ),
                dim=1,
            )
            reference_coordinate_values = tuple(
                (float(row[0]), float(row[1]))
                for row in reference_coordinates.tolist()
            )
            reference_coordinate_keys = tuple(
                row.contiguous().numpy().tobytes()
                for row in reference_coordinates
            )
        protected_edges = set()
        protected_closure_validation = []
        protected_edge_reopened_edges = set()
        corrected_contact_node_ids = set()
        iterations = []
        initial_report = None
        final_report = None
        initial_validation_provenance = None
        final_validation_provenance = None
        last_component_plans = ()
        required_corrected_contact_node_count = 0
        maximum_corrected_component_node_count = 0
        maximum_component_consensus_selected_contact_node_count = 0
        cover_search_state_count = 0
        maximum_cover_search_state_count = 0
        authority_search_state_count = 0
        authority_exact_test_count = 0
        valid_authority_state_count = 0
        maximum_authority_component_state_count = 0
        authority_projection_seconds = 0.0
        authority_validator_seconds = 0.0
        authority_unique_state_count = 0
        authority_duplicate_state_prune_count = 0
        authority_node_infeasible_state_count = 0
        authority_pairwise_pruned_state_count = 0
        authority_objective_pruned_state_count = 0
        authority_admissibly_pruned_state_count = 0
        authority_node_candidate_count = 0
        authority_node_exact_test_count = 0
        authority_pair_exact_test_count = 0
        authority_pair_cache_hit_count = 0
        authority_full_exact_test_count = 0
        topology_tiebreak_pass_count = 0
        topology_tiebreak_score_call_count = 0
        topology_tiebreak_authority_selection_count = 0
        topology_tiebreak_consensus_selection_count = 0
        topology_tiebreak_consensus_ineligible_count = 0
        topology_tiebreak_seconds = 0.0
        reason = "iteration_limit"
        converged = False

        with torch.no_grad():
            for iteration in range(self.max_iterations + 1):
                validation_started = time.perf_counter()
                delta_metadata = None
                if self.incremental_validator is None:
                    report = self.validator(position)
                    validation_mode = "full"
                elif incremental_validation_state is None:
                    report, incremental_validation_state = (
                        self.incremental_validator.validate_with_state(position)
                    )
                    validation_mode = "full"
                else:
                    report, incremental_validation_state, delta_metadata = (
                        self.incremental_validator.validate_delta(
                            incremental_validation_state, position
                        )
                    )
                    incremental_validator_attempt_count += 1
                    incremental_validator_changed_node_count += int(
                        delta_metadata.get("changed_node_count", 0)
                    )
                    if delta_metadata.get("used_delta"):
                        incremental_validator_hit_count += 1
                        validation_mode = "delta"
                    else:
                        incremental_validator_fallback_count += 1
                        validation_mode = "full_fallback"
                validator_call_count += 1
                validator_seconds += time.perf_counter() - validation_started
                validator_modes.append(
                    {
                        "iteration": iteration,
                        "mode": validation_mode,
                        "changed_node_count": (
                            int(delta_metadata.get("changed_node_count", 0))
                            if delta_metadata is not None
                            else None
                        ),
                        "fallback_reason": (
                            delta_metadata.get("fallback_reason")
                            if delta_metadata is not None
                            else None
                        ),
                    }
                )
                if self.validation_provenance_cache:
                    validation_provenance = (
                        ExactValidationProvenance.capture(
                            position,
                            report,
                            "exact_contact_iteration_%d" % iteration,
                        )
                    )
                    if initial_validation_provenance is None:
                        initial_validation_provenance = validation_provenance
                    final_validation_provenance = validation_provenance
                if initial_report is None:
                    initial_report = report
                final_report = report
                if int(report.get("keepin_violation_count", 0)):
                    reason = "keepin_violation"
                    break
                overlap_pair_count = int(report.get("overlap_pair_count", 0))
                current_edges = (
                    self._overlap_edges(report) if overlap_pair_count else set()
                )
                if self.mode == PROTECTED_PROPOSAL_AUTHORITY_SEARCH:
                    reopened_edges = current_edges.intersection(
                        protected_edges
                    )
                    new_edges = current_edges.difference(protected_edges)
                    protected_closure_validation.append(
                        {
                            "iteration": iteration,
                            "current_contact_edges": sorted(current_edges),
                            "new_contact_edges": sorted(new_edges),
                            "protected_contact_edges_before": sorted(
                                protected_edges
                            ),
                            "reopened_contact_edges": sorted(
                                reopened_edges
                            ),
                            "monotonic_progress": not reopened_edges,
                        }
                    )
                    if reopened_edges:
                        protected_edge_reopened_edges.update(reopened_edges)
                        reason = "protected_edge_reopened"
                        break
                if overlap_pair_count == 0:
                    reason = "legal"
                    converged = True
                    break
                if iteration == self.max_iterations:
                    break

                if not current_edges:
                    reason = "missing_overlap_pairs"
                    break
                if any(
                    first_node_id not in self.active_node_ids
                    and second_node_id not in self.active_node_ids
                    for first_node_id, second_node_id in current_edges
                ):
                    reason = "immutable_overlap"
                    break
                if self.mode != PROTECTED_PROPOSAL_AUTHORITY_SEARCH:
                    new_edges = current_edges - protected_edges
                protected_edges.update(current_edges)
                contact_node_ids = sorted(
                    {
                        node_id
                        for edge in protected_edges
                        for node_id in edge
                    }
                )
                active_contact_node_ids = [
                    node_id
                    for node_id in contact_node_ids
                    if node_id in self.active_node_ids
                ]
                current_contact_node_ids = sorted(
                    {
                        node_id
                        for edge in current_edges
                        for node_id in edge
                    }
                )
                current_active_contact_node_ids = [
                    node_id
                    for node_id in current_contact_node_ids
                    if node_id in self.active_node_ids
                ]
                planning_reason = None
                component_consensus_selected_contact_node_ids = []
                iteration_authority_state_count = 0
                iteration_authority_exact_test_count = 0
                iteration_valid_authority_state_count = 0
                iteration_authority_projection_seconds = 0.0
                iteration_authority_validator_seconds = 0.0
                iteration_authority_factorization = {}
                topology_decision = None
                topology_selected_candidate = None
                validated_contact_edges = current_edges
                affected_protected_component_count = 0
                untouched_protected_component_count = 0
                if self.mode == COMPONENT_CONSENSUS:
                    components = _contact_components(protected_edges)
                    component_plans = self._component_plans(
                        reference,
                        position,
                        reference_displacement,
                        displacement_values,
                        components,
                    )
                elif self.mode == MINIMUM_COVER_ROLLBACK:
                    components = _contact_components(current_edges)
                    current_displacement = torch.stack(
                        (
                            position[: self.num_nodes]
                            - origin[: self.num_nodes],
                            position[self.num_nodes : 2 * self.num_nodes]
                            - origin[self.num_nodes : 2 * self.num_nodes],
                        ),
                        dim=1,
                    )
                    current_displacement_values = tuple(
                        (float(row[0]), float(row[1]))
                        for row in current_displacement.detach().cpu().tolist()
                    )
                    component_plans, planning_reason = (
                        self._minimum_cover_plans(
                            components,
                            current_edges,
                            current_displacement_values,
                            displacement_values,
                            corrected_contact_node_ids,
                        )
                    )
                    comparison_plans = self._component_plans(
                        reference,
                        position,
                        reference_displacement,
                        displacement_values,
                        components,
                    )
                    component_consensus_selected_contact_node_ids = sorted(
                        {
                            node_id
                            for plan in comparison_plans
                            for node_id in plan["corrected_node_ids"]
                        }
                    )
                    maximum_component_consensus_selected_contact_node_count = max(
                        maximum_component_consensus_selected_contact_node_count,
                        len(component_consensus_selected_contact_node_ids),
                    )
                    iteration_search_state_count = sum(
                        plan["search_state_count"] for plan in component_plans
                    )
                    cover_search_state_count += iteration_search_state_count
                    maximum_cover_search_state_count = max(
                        maximum_cover_search_state_count,
                        iteration_search_state_count,
                    )
                else:
                    if self.mode == PROTECTED_PROPOSAL_AUTHORITY_SEARCH:
                        protected_components = _contact_components(
                            protected_edges
                        )
                        current_node_ids = {
                            node_id
                            for edge in current_edges
                            for node_id in edge
                        }
                        components = tuple(
                            component
                            for component in protected_components
                            if current_node_ids.intersection(component)
                        )
                        affected_protected_component_count = len(components)
                        untouched_protected_component_count = (
                            len(protected_components) - len(components)
                        )
                        affected_node_ids = {
                            node_id
                            for component in components
                            for node_id in component
                        }
                        validated_contact_edges = {
                            edge
                            for edge in protected_edges
                            if edge[0] in affected_node_ids
                            and edge[1] in affected_node_ids
                        }
                    else:
                        components = _contact_components(current_edges)
                    position_cpu = position.detach().cpu()
                    current_coordinate_values = tuple(
                        (
                            float(position_cpu[node_id]),
                            float(position_cpu[self.num_nodes + node_id]),
                        )
                        for node_id in range(self.num_nodes)
                    )
                    component_plans, planning_reason = (
                        self._proposal_authority_plans(
                            components,
                            validated_contact_edges,
                            origin_coordinate_values,
                            reference_coordinate_values,
                            current_coordinate_values,
                            displacement_values,
                            displacement_keys,
                            reference_coordinate_keys,
                            reference_cpu,
                            corrected_contact_node_ids,
                        )
                    )
                    comparison_plans = self._component_plans(
                        reference,
                        position,
                        reference_displacement,
                        displacement_values,
                        components,
                    )
                    component_consensus_selected_contact_node_ids = sorted(
                        {
                            node_id
                            for plan in comparison_plans
                            for node_id in plan["corrected_node_ids"]
                        }
                    )
                    maximum_component_consensus_selected_contact_node_count = max(
                        maximum_component_consensus_selected_contact_node_count,
                        len(component_consensus_selected_contact_node_ids),
                    )
                    iteration_authority_state_count = sum(
                        plan["authority_state_count"]
                        for plan in component_plans
                    )
                    iteration_authority_exact_test_count = sum(
                        plan["authority_exact_test_count"]
                        for plan in component_plans
                    )
                    iteration_valid_authority_state_count = sum(
                        plan["valid_authority_state_count"]
                        for plan in component_plans
                    )
                    iteration_authority_projection_seconds = math.fsum(
                        plan["authority_projection_seconds"]
                        for plan in component_plans
                    )
                    iteration_authority_validator_seconds = math.fsum(
                        plan["authority_validator_seconds"]
                        for plan in component_plans
                    )
                    if (
                        self.authority_search_strategy
                        == PAIRWISE_FACTORIZED_AUTHORITY_SEARCH
                    ):
                        factorized_fields = (
                            "authority_unique_state_count",
                            "authority_duplicate_state_prune_count",
                            "authority_node_infeasible_state_count",
                            "authority_pairwise_pruned_state_count",
                            "authority_objective_pruned_state_count",
                            "authority_admissibly_pruned_state_count",
                            "authority_node_candidate_count",
                            "authority_node_exact_test_count",
                            "authority_pair_exact_test_count",
                            "authority_pair_cache_hit_count",
                            "authority_full_exact_test_count",
                        )
                        iteration_authority_factorization = {
                            field: sum(plan[field] for plan in component_plans)
                            for field in factorized_fields
                        }
                    authority_search_state_count += (
                        iteration_authority_state_count
                    )
                    authority_exact_test_count += (
                        iteration_authority_exact_test_count
                    )
                    valid_authority_state_count += (
                        iteration_valid_authority_state_count
                    )
                    authority_projection_seconds += (
                        iteration_authority_projection_seconds
                    )
                    authority_validator_seconds += (
                        iteration_authority_validator_seconds
                    )
                    if iteration_authority_factorization:
                        authority_unique_state_count += (
                            iteration_authority_factorization[
                                "authority_unique_state_count"
                            ]
                        )
                        authority_duplicate_state_prune_count += (
                            iteration_authority_factorization[
                                "authority_duplicate_state_prune_count"
                            ]
                        )
                        authority_node_infeasible_state_count += (
                            iteration_authority_factorization[
                                "authority_node_infeasible_state_count"
                            ]
                        )
                        authority_pairwise_pruned_state_count += (
                            iteration_authority_factorization[
                                "authority_pairwise_pruned_state_count"
                            ]
                        )
                        authority_objective_pruned_state_count += (
                            iteration_authority_factorization[
                                "authority_objective_pruned_state_count"
                            ]
                        )
                        authority_admissibly_pruned_state_count += (
                            iteration_authority_factorization[
                                "authority_admissibly_pruned_state_count"
                            ]
                        )
                        authority_node_candidate_count += (
                            iteration_authority_factorization[
                                "authority_node_candidate_count"
                            ]
                        )
                        authority_node_exact_test_count += (
                            iteration_authority_factorization[
                                "authority_node_exact_test_count"
                            ]
                        )
                        authority_pair_exact_test_count += (
                            iteration_authority_factorization[
                                "authority_pair_exact_test_count"
                            ]
                        )
                        authority_pair_cache_hit_count += (
                            iteration_authority_factorization[
                                "authority_pair_cache_hit_count"
                            ]
                        )
                        authority_full_exact_test_count += (
                            iteration_authority_factorization[
                                "authority_full_exact_test_count"
                            ]
                        )
                    maximum_authority_component_state_count = max(
                        maximum_authority_component_state_count,
                        max(
                            (
                                plan["authority_state_count"]
                                for plan in component_plans
                            ),
                            default=0,
                        ),
                    )
                last_component_plans = component_plans
                selected_component_plans = component_plans
                if self.topology_tiebreak and planning_reason is None:
                    (
                        topology_selected_candidate,
                        selected_component_plans,
                        topology_decision,
                    ) = self._select_topology_candidate(
                        reference,
                        origin,
                        position,
                        component_plans,
                        comparison_plans,
                        components,
                        validated_contact_edges,
                    )
                    topology_tiebreak_pass_count += 1
                    topology_tiebreak_score_call_count += topology_decision[
                        "score_call_count"
                    ]
                    topology_tiebreak_seconds += topology_decision[
                        "elapsed_seconds"
                    ]
                    if (
                        topology_decision["selected_candidate"]
                        == AUTHORITY_TOPOLOGY_CANDIDATE
                    ):
                        topology_tiebreak_authority_selection_count += 1
                    else:
                        topology_tiebreak_consensus_selection_count += 1
                    if not topology_decision["candidates"][
                        CONSENSUS_TOPOLOGY_CANDIDATE
                    ]["eligible"]:
                        topology_tiebreak_consensus_ineligible_count += 1
                selected_contact_node_ids = sorted(
                    {
                        node_id
                        for plan in selected_component_plans
                        for node_id in plan["corrected_node_ids"]
                    }
                )
                authority_corrected_node_ids = sorted(
                    {
                        node_id
                        for plan in component_plans
                        for node_id in plan.get(
                            "authority_corrected_node_ids", ()
                        )
                    }
                )
                authority_hard_projected_node_ids = sorted(
                    {
                        node_id
                        for plan in component_plans
                        for node_id in plan.get("hard_projected_node_ids", ())
                    }
                )
                required_contact_node_ids = corrected_contact_node_ids.union(
                    selected_contact_node_ids
                )
                required_corrected_contact_node_count = max(
                    required_corrected_contact_node_count,
                    len(required_contact_node_ids),
                )
                maximum_corrected_component_node_count = max(
                    maximum_corrected_component_node_count,
                    max(
                        (
                            len(plan["corrected_node_ids"])
                            for plan in selected_component_plans
                        ),
                        default=0,
                    ),
                )
                iteration_record = {
                    "iteration": iteration,
                    "overlap_pair_count": int(
                        report.get("overlap_pair_count", 0)
                    ),
                    "overlap_area_mm2": float(
                        report.get("overlap_area_mm2", 0.0)
                    ),
                    "new_contact_pair_count": len(new_edges),
                    "protected_pair_count": len(protected_edges),
                    "contact_node_count": len(contact_node_ids),
                    "active_contact_node_count": len(active_contact_node_ids),
                    "current_contact_pair_count": len(current_edges),
                    "current_contact_node_count": len(
                        current_contact_node_ids
                    ),
                    "current_active_contact_node_count": len(
                        current_active_contact_node_ids
                    ),
                    "selected_contact_node_count": len(
                        selected_contact_node_ids
                    ),
                    "selected_contact_node_ids": selected_contact_node_ids,
                    "cumulative_corrected_contact_node_count": len(
                        corrected_contact_node_ids
                    ),
                    "required_corrected_contact_node_count": len(
                        required_contact_node_ids
                    ),
                    "component_count": len(components),
                    "contact_components": [
                        self._serialize_component_plan(plan)
                        for plan in component_plans
                    ],
                    "component_consensus_selected_contact_node_count": len(
                        component_consensus_selected_contact_node_ids
                    ),
                    "component_consensus_selected_contact_node_ids": (
                        component_consensus_selected_contact_node_ids
                    ),
                    "cover_search_state_count": sum(
                        plan.get("search_state_count", 0)
                        for plan in component_plans
                    ),
                    "applied": False,
                }
                if self.mode in PROPOSAL_AUTHORITY_MODES:
                    iteration_record.update(
                        {
                            "authority_state_count": (
                                iteration_authority_state_count
                            ),
                            "authority_exact_test_count": (
                                iteration_authority_exact_test_count
                            ),
                            "valid_authority_state_count": (
                                iteration_valid_authority_state_count
                            ),
                            "authority_corrected_node_ids": (
                                authority_corrected_node_ids
                            ),
                            "authority_hard_projected_node_ids": (
                                authority_hard_projected_node_ids
                            ),
                            "authority_projection_seconds": (
                                iteration_authority_projection_seconds
                            ),
                            "authority_validator_seconds": (
                                iteration_authority_validator_seconds
                            ),
                            "current_contact_edges": (
                                self._serialize_contact_edges(current_edges)
                            ),
                            "protected_contact_edges": (
                                self._serialize_contact_edges(protected_edges)
                            ),
                        }
                    )
                    if self.mode == PROTECTED_PROPOSAL_AUTHORITY_SEARCH:
                        iteration_record.update(
                            {
                                "validated_contact_edges": (
                                    self._serialize_contact_edges(
                                        validated_contact_edges
                                    )
                                ),
                                "affected_protected_component_count": (
                                    affected_protected_component_count
                                ),
                                "untouched_protected_component_count": (
                                    untouched_protected_component_count
                                ),
                            }
                        )
                    if iteration_authority_factorization:
                        iteration_record.update(
                            {
                                "authority_search_strategy": (
                                    self.authority_search_strategy
                                ),
                                **iteration_authority_factorization,
                            }
                        )
                    if topology_decision is not None:
                        iteration_record["topology_tiebreak"] = (
                            topology_decision
                        )
                if planning_reason is not None:
                    reason = planning_reason
                    iterations.append(iteration_record)
                    break
                if len(required_contact_node_ids) > self.max_contact_nodes:
                    reason = "contact_node_limit"
                    iterations.append(iteration_record)
                    break

                candidate_before = position.detach().clone()
                if topology_selected_candidate is not None:
                    position.copy_(topology_selected_candidate)
                elif self.mode == COMPONENT_CONSENSUS:
                    self._apply_consensus(
                        reference, origin, position, component_plans
                    )
                elif self.mode == MINIMUM_COVER_ROLLBACK:
                    self._apply_origin_rollback(
                        origin, position, component_plans
                    )
                else:
                    self._apply_proposal_authorities(
                        position, component_plans
                    )
                after_contact_correction = position.detach().clone()
                contact_correction = _correction_statistics(
                    candidate_before,
                    after_contact_correction,
                    self.num_nodes,
                )
                hard_projector(position)
                hard_projection_correction = _correction_statistics(
                    after_contact_correction, position, self.num_nodes
                )
                correction = _correction_statistics(
                    candidate_before, position, self.num_nodes
                )
                if (
                    self.mode in PROPOSAL_AUTHORITY_MODES
                    and hard_projection_correction["changed_node_count"]
                ):
                    position.copy_(candidate_before)
                    selected_topology_candidate = (
                        topology_decision["selected_candidate"]
                        if topology_decision is not None
                        else AUTHORITY_TOPOLOGY_CANDIDATE
                    )
                    reason = (
                        "topology_candidate_replay_mismatch"
                        if selected_topology_candidate
                        == CONSENSUS_TOPOLOGY_CANDIDATE
                        else "authority_projection_mismatch"
                    )
                    mismatch_key = (
                        "topology_candidate_replay_mismatch_node_ids"
                        if selected_topology_candidate
                        == CONSENSUS_TOPOLOGY_CANDIDATE
                        else "authority_projection_mismatch_node_ids"
                    )
                    iteration_record.update(
                        {
                            "contact_correction": contact_correction,
                            "hard_projection_correction": (
                                hard_projection_correction
                            ),
                            "correction": correction,
                            mismatch_key: (
                                hard_projection_correction["changed_node_ids"]
                            ),
                        }
                    )
                    iterations.append(iteration_record)
                    break
                corrected_contact_node_ids.update(selected_contact_node_ids)
                iteration_record.update(
                    {
                        "applied": True,
                        "cumulative_corrected_contact_node_count": len(
                            corrected_contact_node_ids
                        ),
                        "contact_correction": contact_correction,
                        "hard_projection_correction": (
                            hard_projection_correction
                        ),
                        "correction": correction,
                    }
                )
                if self.mode == COMPONENT_CONSENSUS:
                    iteration_record["consensus_correction"] = (
                        contact_correction
                    )
                elif self.mode == MINIMUM_COVER_ROLLBACK:
                    iteration_record["rollback_correction"] = contact_correction
                elif (
                    topology_decision is not None
                    and topology_decision["selected_candidate"]
                    == CONSENSUS_TOPOLOGY_CANDIDATE
                ):
                    iteration_record["consensus_correction"] = (
                        contact_correction
                    )
                else:
                    iteration_record["authority_correction"] = (
                        contact_correction
                    )
                iterations.append(iteration_record)
                if not new_edges and torch.equal(candidate_before, position):
                    reason = "stalled"
                    break

        initial_report = initial_report or {}
        final_report = final_report or {}
        correction = _correction_statistics(before, position, self.num_nodes)
        contact_node_ids = sorted(
            {node_id for edge in protected_edges for node_id in edge}
        )
        components = _contact_components(protected_edges)
        active_contact_node_count = sum(
            node_id in self.active_node_ids for node_id in contact_node_ids
        )
        component_node_counts = [len(component) for component in components]
        active_component_node_counts = [
            sum(node_id in self.active_node_ids for node_id in component)
            for component in components
        ]
        result = {
            "enabled": True,
            "mode": self.mode,
            "converged": converged,
            "reason": reason,
            "max_iterations": self.max_iterations,
            "max_contact_nodes": self.max_contact_nodes,
            "max_cover_component_nodes": self.max_cover_component_nodes,
            "contact_node_limit_basis": "cumulative_corrected_active_nodes",
            "validator_call_count": validator_call_count,
            "validator_seconds": validator_seconds,
            "validator_modes": validator_modes,
            "incremental_validator_attempt_count": (
                incremental_validator_attempt_count
            ),
            "incremental_validator_hit_count": (
                incremental_validator_hit_count
            ),
            "incremental_validator_fallback_count": (
                incremental_validator_fallback_count
            ),
            "incremental_validator_changed_node_count": (
                incremental_validator_changed_node_count
            ),
            "elapsed_seconds": time.perf_counter() - started,
            "initial_overlap_pair_count": int(
                initial_report.get("overlap_pair_count", 0)
            ),
            "initial_overlap_area_mm2": float(
                initial_report.get("overlap_area_mm2", 0.0)
            ),
            "final_overlap_pair_count": int(
                final_report.get("overlap_pair_count", 0)
            ),
            "final_overlap_area_mm2": float(
                final_report.get("overlap_area_mm2", 0.0)
            ),
            "protected_pair_count": len(protected_edges),
            "contact_node_count": len(contact_node_ids),
            "active_contact_node_count": active_contact_node_count,
            "corrected_contact_node_count": len(corrected_contact_node_ids),
            "corrected_contact_node_ids": sorted(corrected_contact_node_ids),
            "corrected_contact_refdes": [
                self.node_id_to_refdes.get(node_id, str(node_id))
                for node_id in sorted(corrected_contact_node_ids)
            ],
            "required_corrected_contact_node_count": (
                required_corrected_contact_node_count
            ),
            "cover_search_state_count": cover_search_state_count,
            "maximum_cover_search_state_count": (
                maximum_cover_search_state_count
            ),
            "maximum_component_consensus_selected_contact_node_count": (
                maximum_component_consensus_selected_contact_node_count
            ),
            "component_count": len(components),
            "maximum_component_node_count": max(
                component_node_counts, default=0
            ),
            "maximum_active_component_node_count": max(
                active_component_node_counts, default=0
            ),
            "maximum_corrected_component_node_count": (
                maximum_corrected_component_node_count
            ),
            "contact_components": [
                self._serialize_component_plan(plan)
                for plan in last_component_plans
            ],
            "correction": correction,
            "iterations": iterations,
        }
        if self.mode in PROPOSAL_AUTHORITY_MODES:
            result.update(
                {
                    "max_authority_states": self.max_authority_states,
                    "authority_search_state_count": (
                        authority_search_state_count
                    ),
                    "authority_exact_test_count": authority_exact_test_count,
                    "valid_authority_state_count": (
                        valid_authority_state_count
                    ),
                    "authority_projection_seconds": (
                        authority_projection_seconds
                    ),
                    "authority_validator_seconds": (
                        authority_validator_seconds
                    ),
                    "maximum_authority_component_state_count": (
                        maximum_authority_component_state_count
                    ),
                    "protected_contact_edges": (
                        self._serialize_contact_edges(protected_edges)
                    ),
                }
            )
            if (
                self.authority_search_strategy
                == PAIRWISE_FACTORIZED_AUTHORITY_SEARCH
            ):
                result.update(
                    {
                        "authority_search_strategy": (
                            self.authority_search_strategy
                        ),
                        "authority_unique_state_count": (
                            authority_unique_state_count
                        ),
                        "authority_duplicate_state_prune_count": (
                            authority_duplicate_state_prune_count
                        ),
                        "authority_node_infeasible_state_count": (
                            authority_node_infeasible_state_count
                        ),
                        "authority_pairwise_pruned_state_count": (
                            authority_pairwise_pruned_state_count
                        ),
                        "authority_objective_pruned_state_count": (
                            authority_objective_pruned_state_count
                        ),
                        "authority_admissibly_pruned_state_count": (
                            authority_admissibly_pruned_state_count
                        ),
                        "authority_node_candidate_count": (
                            authority_node_candidate_count
                        ),
                        "authority_node_exact_test_count": (
                            authority_node_exact_test_count
                        ),
                        "authority_pair_exact_test_count": (
                            authority_pair_exact_test_count
                        ),
                        "authority_pair_cache_hit_count": (
                            authority_pair_cache_hit_count
                        ),
                        "authority_full_exact_test_count": (
                            authority_full_exact_test_count
                        ),
                    }
                )
        if self.mode == PROTECTED_PROPOSAL_AUTHORITY_SEARCH:
            result.update(
                {
                    "protected_closure_validation": [
                        {
                            "iteration": row["iteration"],
                            "current_contact_edges": (
                                self._serialize_contact_edges(
                                    row["current_contact_edges"]
                                )
                            ),
                            "new_contact_edges": (
                                self._serialize_contact_edges(
                                    row["new_contact_edges"]
                                )
                            ),
                            "protected_contact_edges_before": (
                                self._serialize_contact_edges(
                                    row["protected_contact_edges_before"]
                                )
                            ),
                            "reopened_contact_edges": (
                                self._serialize_contact_edges(
                                    row["reopened_contact_edges"]
                                )
                            ),
                            "monotonic_progress": row[
                                "monotonic_progress"
                            ],
                        }
                        for row in protected_closure_validation
                    ],
                    "protected_edge_reopened_count": len(
                        protected_edge_reopened_edges
                    ),
                    "protected_edge_reopened_edges": (
                        self._serialize_contact_edges(
                            protected_edge_reopened_edges
                        )
                    ),
                    "monotonic_progress": not (
                        protected_edge_reopened_edges
                    ),
                }
            )
            if self.topology_tiebreak:
                result["topology_tiebreak"] = {
                    "enabled": True,
                    "selected_nets": [
                        {"net_id": net_id, "degree": degree}
                        for net_id, degree in zip(
                            self.topology_net_ids,
                            self.topology_net_degrees,
                        )
                    ],
                    "pass_count": topology_tiebreak_pass_count,
                    "score_call_count": (
                        topology_tiebreak_score_call_count
                    ),
                    "authority_selection_count": (
                        topology_tiebreak_authority_selection_count
                    ),
                    "consensus_selection_count": (
                        topology_tiebreak_consensus_selection_count
                    ),
                    "consensus_ineligible_count": (
                        topology_tiebreak_consensus_ineligible_count
                    ),
                    "elapsed_seconds": topology_tiebreak_seconds,
                }
        if self.validation_provenance_cache and converged:
            if (
                initial_validation_provenance is None
                or final_validation_provenance is None
            ):
                raise RuntimeError(
                    "contact validation provenance is incomplete"
                )
            self._validation_provenance = {
                "initial": initial_validation_provenance,
                "final": final_validation_provenance,
            }
        return result
