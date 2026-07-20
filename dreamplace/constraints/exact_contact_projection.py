"""Bounded candidate-side projection for exact contact crossings."""

import math
import time

import torch


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
    """Project crossing contact components onto shared proposal motion.

    The node budget limits the cumulative active coordinates selected for
    consensus correction. Inactive endpoints only provide authoritative motion
    and do not consume that budget.
    """

    def __init__(
        self,
        validator,
        refdes_to_node_id,
        active_node_ids,
        num_nodes,
        max_iterations=8,
        max_contact_nodes=32,
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
        if self.num_nodes <= 0:
            raise ValueError("contact projection requires a positive node count")
        if self.max_iterations <= 0:
            raise ValueError("contact projection iterations must be positive")
        if self.max_contact_nodes < 2:
            raise ValueError("contact projection node limit must be at least two")
        invalid_active = sorted(
            node_id
            for node_id in self.active_node_ids
            if node_id < 0 or node_id >= self.num_nodes
        )
        if invalid_active:
            raise ValueError("contact projection has invalid active node ids")

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

    def _serialize_component_plan(self, plan):
        representative_node_id = plan["representative_node_id"]
        return {
            "node_ids": list(plan["node_ids"]),
            "refdes": [
                self.node_id_to_refdes.get(node_id, str(node_id))
                for node_id in plan["node_ids"]
            ],
            "active_node_count": len(plan["active_node_ids"]),
            "inactive_node_count": len(plan["inactive_node_ids"]),
            "authority_kind": plan["authority_kind"],
            "authority_node_ids": list(plan["inactive_node_ids"]),
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

    def __call__(self, origin, position, hard_projector):
        if origin.shape != position.shape:
            raise ValueError("contact projection position shapes do not match")
        if origin.device != position.device or origin.dtype != position.dtype:
            raise ValueError("contact projection tensors must share device and dtype")
        if position.numel() < 2 * self.num_nodes:
            raise ValueError("contact projection position vector is too short")

        started = time.perf_counter()
        validator_seconds = 0.0
        validator_call_count = 0
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
        displacement_values = tuple(
            (float(row[0]), float(row[1]))
            for row in reference_displacement.detach().cpu().tolist()
        )
        protected_edges = set()
        corrected_contact_node_ids = set()
        iterations = []
        initial_report = None
        final_report = None
        last_component_plans = ()
        required_corrected_contact_node_count = 0
        maximum_corrected_component_node_count = 0
        reason = "iteration_limit"
        converged = False

        with torch.no_grad():
            for iteration in range(self.max_iterations + 1):
                validation_started = time.perf_counter()
                report = self.validator(position)
                validator_call_count += 1
                validator_seconds += time.perf_counter() - validation_started
                if initial_report is None:
                    initial_report = report
                final_report = report
                if int(report.get("keepin_violation_count", 0)):
                    reason = "keepin_violation"
                    break
                if int(report.get("overlap_pair_count", 0)) == 0:
                    reason = "legal"
                    converged = True
                    break
                if iteration == self.max_iterations:
                    break

                current_edges = self._overlap_edges(report)
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
                components = _contact_components(protected_edges)
                component_plans = self._component_plans(
                    reference,
                    position,
                    reference_displacement,
                    displacement_values,
                    components,
                )
                last_component_plans = component_plans
                selected_contact_node_ids = sorted(
                    {
                        node_id
                        for plan in component_plans
                        for node_id in plan["corrected_node_ids"]
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
                            for plan in component_plans
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
                    "applied": False,
                }
                if len(required_contact_node_ids) > self.max_contact_nodes:
                    reason = "contact_node_limit"
                    iterations.append(iteration_record)
                    break

                candidate_before = position.detach().clone()
                self._apply_consensus(
                    reference, origin, position, component_plans
                )
                after_consensus = position.detach().clone()
                consensus_correction = _correction_statistics(
                    candidate_before, after_consensus, self.num_nodes
                )
                hard_projector(position)
                hard_projection_correction = _correction_statistics(
                    after_consensus, position, self.num_nodes
                )
                correction = _correction_statistics(
                    candidate_before, position, self.num_nodes
                )
                corrected_contact_node_ids.update(selected_contact_node_ids)
                iteration_record.update(
                    {
                        "applied": True,
                        "cumulative_corrected_contact_node_count": len(
                            corrected_contact_node_ids
                        ),
                        "consensus_correction": consensus_correction,
                        "hard_projection_correction": (
                            hard_projection_correction
                        ),
                        "correction": correction,
                    }
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
        return {
            "enabled": True,
            "converged": converged,
            "reason": reason,
            "max_iterations": self.max_iterations,
            "max_contact_nodes": self.max_contact_nodes,
            "contact_node_limit_basis": "cumulative_corrected_active_nodes",
            "validator_call_count": validator_call_count,
            "validator_seconds": validator_seconds,
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
