"""Bounded candidate-side projection for exact contact crossings."""

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


class ExactContactProjector:
    """Project crossing contact components onto shared proposal motion.

    The node budget limits active coordinates that may be corrected. Inactive
    endpoints only provide authoritative motion and do not consume that budget.
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

    def _component_displacement(self, reference, origin, component):
        inactive = [
            node_id
            for node_id in component
            if node_id not in self.active_node_ids
        ]
        source_ids = inactive if inactive else list(component)
        index = torch.as_tensor(
            source_ids, dtype=torch.long, device=reference.device
        )
        displacement = torch.stack(
            (
                reference.index_select(0, index)
                - origin.index_select(0, index),
                reference.index_select(0, self.num_nodes + index)
                - origin.index_select(0, self.num_nodes + index),
            ),
            dim=1,
        )
        return displacement.mean(dim=0)

    def _apply_consensus(self, reference, origin, position, components):
        for component in components:
            active = [
                node_id
                for node_id in component
                if node_id in self.active_node_ids
            ]
            if not active:
                continue
            displacement = self._component_displacement(
                reference, origin, component
            )
            index = torch.as_tensor(
                active, dtype=torch.long, device=position.device
            )
            position.index_copy_(
                0,
                index,
                origin.index_select(0, index) + displacement[0],
            )
            position.index_copy_(
                0,
                self.num_nodes + index,
                origin.index_select(0, self.num_nodes + index)
                + displacement[1],
            )

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
        protected_edges = set()
        iterations = []
        initial_report = None
        final_report = None
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
                if len(active_contact_node_ids) > self.max_contact_nodes:
                    reason = "contact_node_limit"
                    break

                components = _contact_components(protected_edges)
                candidate_before = position.detach().clone()
                self._apply_consensus(reference, origin, position, components)
                hard_projector(position)
                correction = _correction_statistics(
                    candidate_before, position, self.num_nodes
                )
                iterations.append(
                    {
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
                        "active_contact_node_count": len(
                            active_contact_node_ids
                        ),
                        "component_count": len(components),
                        "correction": correction,
                    }
                )
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
            "contact_node_limit_basis": "active_nodes",
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
            "component_count": len(components),
            "maximum_component_node_count": max(
                component_node_counts, default=0
            ),
            "maximum_active_component_node_count": max(
                active_component_node_counts, default=0
            ),
            "contact_components": [
                {
                    "node_ids": list(component),
                    "refdes": [
                        self.node_id_to_refdes.get(node_id, str(node_id))
                        for node_id in component
                    ],
                    "active_node_count": sum(
                        node_id in self.active_node_ids for node_id in component
                    ),
                }
                for component in components
            ],
            "correction": correction,
            "iterations": iterations,
        }
