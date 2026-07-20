import json
import unittest

import torch
from shapely import affinity
from shapely.geometry import Polygon, box

from dreamplace.constraints.exact_contact_projection import ExactContactProjector


def _aabb_validator(names, widths, heights, pairs):
    num_nodes = len(names)

    def validator(position):
        rows = []
        total_area = 0.0
        for first_node_id, second_node_id in pairs:
            first_x = float(position[first_node_id].detach().cpu().item())
            first_y = float(
                position[num_nodes + first_node_id].detach().cpu().item()
            )
            second_x = float(position[second_node_id].detach().cpu().item())
            second_y = float(
                position[num_nodes + second_node_id].detach().cpu().item()
            )
            overlap_x = min(
                first_x + widths[first_node_id],
                second_x + widths[second_node_id],
            ) - max(first_x, second_x)
            overlap_y = min(
                first_y + heights[first_node_id],
                second_y + heights[second_node_id],
            ) - max(first_y, second_y)
            area = max(overlap_x, 0.0) * max(overlap_y, 0.0)
            if area > 1e-12:
                total_area += area
                rows.append(
                    {
                        "kind": "constrained_constrained",
                        "first_refdes": names[first_node_id],
                        "second_refdes": names[second_node_id],
                        "overlap_area_mm2": area,
                    }
                )
        return {
            "keepin_violation_count": 0,
            "overlap_pair_count": len(rows),
            "overlap_area_mm2": total_area,
            "overlap_pairs": rows,
        }

    return validator


def _aabb_component_validator(widths, heights):
    def validator(lower_left_by_node_id, edges):
        overlap_edges = []
        total_area = 0.0
        for first_node_id, second_node_id in edges:
            first_x, first_y = lower_left_by_node_id[first_node_id]
            second_x, second_y = lower_left_by_node_id[second_node_id]
            overlap_x = min(
                first_x + widths[first_node_id],
                second_x + widths[second_node_id],
            ) - max(first_x, second_x)
            overlap_y = min(
                first_y + heights[first_node_id],
                second_y + heights[second_node_id],
            ) - max(first_y, second_y)
            area = max(overlap_x, 0.0) * max(overlap_y, 0.0)
            if area <= 1e-12:
                continue
            overlap_edges.append((first_node_id, second_node_id))
            total_area += area
        return {
            "keepin_violation_count": 0,
            "overlap_pair_count": len(overlap_edges),
            "overlap_edges": overlap_edges,
            "overlap_area_mm2": total_area,
        }

    return validator


def _identity_component_projector(lower_left_by_node_id, active_node_ids):
    return {
        "coordinates": dict(lower_left_by_node_id),
        "projected_node_ids": [],
        "mean_distance": 0.0,
        "max_distance": 0.0,
    }


def _projector(
    names,
    widths,
    heights,
    pairs,
    active_node_ids=None,
    max_iterations=8,
    max_contact_nodes=32,
    mode="component_consensus",
    max_cover_component_nodes=16,
    max_authority_states=4096,
    component_projector=_identity_component_projector,
):
    if active_node_ids is None:
        active_node_ids = range(len(names))
    return ExactContactProjector(
        validator=_aabb_validator(names, widths, heights, pairs),
        refdes_to_node_id={name: index for index, name in enumerate(names)},
        active_node_ids=active_node_ids,
        num_nodes=len(names),
        max_iterations=max_iterations,
        max_contact_nodes=max_contact_nodes,
        mode=mode,
        max_cover_component_nodes=max_cover_component_nodes,
        component_validator=_aabb_component_validator(widths, heights),
        component_projector=component_projector,
        max_authority_states=max_authority_states,
    )


class ExactContactProjectionTest(unittest.TestCase):
    def test_minimum_cover_configuration_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown exact contact"):
            _projector(
                ("A", "B"),
                (1.0, 1.0),
                (1.0, 1.0),
                ((0, 1),),
                mode="greedy",
            )
        with self.assertRaisesRegex(ValueError, "cover component"):
            _projector(
                ("A", "B"),
                (1.0, 1.0),
                (1.0, 1.0),
                ((0, 1),),
                max_cover_component_nodes=1,
            )
        with self.assertRaisesRegex(ValueError, "authority state"):
            _projector(
                ("A", "B"),
                (1.0, 1.0),
                (1.0, 1.0),
                ((0, 1),),
                mode="proposal_authority_search",
                max_authority_states=0,
            )
        with self.assertRaisesRegex(ValueError, "component validator"):
            ExactContactProjector(
                validator=_aabb_validator(
                    ("A", "B"), (1.0, 1.0), (1.0, 1.0), ((0, 1),)
                ),
                refdes_to_node_id={"A": 0, "B": 1},
                active_node_ids=(0, 1),
                num_nodes=2,
                mode="proposal_authority_search",
            )
        with self.assertRaisesRegex(ValueError, "component projector"):
            ExactContactProjector(
                validator=_aabb_validator(
                    ("A", "B"), (1.0, 1.0), (1.0, 1.0), ((0, 1),)
                ),
                component_validator=_aabb_component_validator(
                    (1.0, 1.0), (1.0, 1.0)
                ),
                refdes_to_node_id={"A": 0, "B": 1},
                active_node_ids=(0, 1),
                num_nodes=2,
                mode="proposal_authority_search",
            )

    def test_authority_search_preserves_one_native_two_body_motion(self):
        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            mode="proposal_authority_search",
        )
        origin = torch.tensor([0.0, 1.25, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor(
            [0.375, 1.3125, 0.0, 0.0], dtype=torch.float64
        )
        origin_rollback = candidate.clone()
        origin_rollback[1] = origin[1]

        self.assertEqual(
            _aabb_validator(
                ("A", "B"),
                (1.0, 1.0),
                (1.0, 1.0),
                ((0, 1),),
            )(origin_rollback)["overlap_pair_count"],
            1,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.375, 1.625, 0.0, 0.0], dtype=torch.float64
            ),
            rtol=0,
            atol=1e-15,
        )
        self.assertEqual(result["corrected_contact_node_ids"], [1])
        component = result["contact_components"][0]
        self.assertEqual(component["authority_state_count"], 4)
        self.assertEqual(component["authority_exact_test_count"], 4)
        self.assertEqual(
            component["authority_assignments"],
            [
                {
                    "node_id": 0,
                    "refdes": "A",
                    "authority_node_id": 0,
                    "authority_refdes": "A",
                },
                {
                    "node_id": 1,
                    "refdes": "B",
                    "authority_node_id": 0,
                    "authority_refdes": "A",
                },
            ],
        )

    def test_authority_search_leaves_legal_candidate_byte_identical(self):
        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            mode="proposal_authority_search",
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([-0.1, 1.1, 0.0, 0.0], dtype=torch.float64)
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["reason"], "legal")
        self.assertEqual(result["authority_exact_test_count"], 0)
        self.assertTrue(torch.equal(candidate, before))

    def test_protected_authority_closes_current_edge_cycle(self):
        names = ("A", "B", "C")
        pairs = ((0, 1), (1, 2))
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        proposal = torch.tensor(
            [0.2, 1.2, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        current_edge_projector = _projector(
            names,
            (1.0,) * 3,
            (1.0,) * 3,
            pairs,
            active_node_ids=(0, 1),
            max_iterations=4,
            mode="proposal_authority_search",
        )
        current_edge_candidate = proposal.clone()

        current_edge_result = current_edge_projector(
            origin, current_edge_candidate, lambda position: None
        )

        self.assertFalse(current_edge_result["converged"])
        self.assertEqual(current_edge_result["reason"], "iteration_limit")
        self.assertEqual(
            [
                [tuple(edge["node_ids"]) for edge in row["current_contact_edges"]]
                for row in current_edge_result["iterations"]
            ],
            [[(1, 2)], [(0, 1)], [(1, 2)], [(0, 1)]],
        )

        protected_projector = _projector(
            names,
            (1.0,) * 3,
            (1.0,) * 3,
            pairs,
            active_node_ids=(0, 1),
            max_iterations=4,
            mode="protected_proposal_authority_search",
        )
        protected_candidate = proposal.clone()

        protected_result = protected_projector(
            origin, protected_candidate, lambda position: None
        )

        self.assertTrue(protected_result["converged"])
        self.assertEqual(protected_result["reason"], "legal")
        torch.testing.assert_close(
            protected_candidate, origin, rtol=0, atol=0
        )
        self.assertEqual(
            protected_result["corrected_contact_node_ids"], [0, 1]
        )
        self.assertEqual(len(protected_result["iterations"]), 2)
        second = protected_result["iterations"][1]
        self.assertEqual(second["affected_protected_component_count"], 1)
        self.assertEqual(second["untouched_protected_component_count"], 0)
        self.assertEqual(
            [
                tuple(edge["node_ids"])
                for edge in second["validated_contact_edges"]
            ],
            [(0, 1), (1, 2)],
        )
        self.assertEqual(
            second["contact_components"][0]["authority_state_count"], 9
        )
        self.assertEqual(protected_result["protected_edge_reopened_count"], 0)
        self.assertTrue(protected_result["monotonic_progress"])

    def test_protected_authority_merges_protected_components(self):
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 3.0] + [0.0] * 4, dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.0, 2.0, 2.8] + [0.0] * 4, dtype=torch.float64
        )
        projector = _projector(
            ("A", "B", "C", "D"),
            (1.0,) * 4,
            (1.0,) * 4,
            ((0, 1), (1, 2), (2, 3)),
            mode="protected_proposal_authority_search",
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        torch.testing.assert_close(candidate, origin, rtol=0, atol=0)
        self.assertEqual(len(result["iterations"]), 2)
        first, merged = result["iterations"]
        self.assertEqual(first["component_count"], 2)
        self.assertEqual(first["selected_contact_node_ids"], [1, 3])
        self.assertEqual(merged["component_count"], 1)
        self.assertEqual(
            merged["contact_components"][0]["node_ids"], [0, 1, 2, 3]
        )
        self.assertEqual(
            [
                tuple(edge["node_ids"])
                for edge in merged["validated_contact_edges"]
            ],
            [(0, 1), (1, 2), (2, 3)],
        )
        self.assertEqual(
            [
                row["cumulative_corrected_contact_node_count"]
                for row in result["iterations"]
            ],
            [2, 3],
        )
        self.assertEqual(result["corrected_contact_node_ids"], [0, 1, 3])
        self.assertTrue(result["monotonic_progress"])

    def test_protected_authority_skips_untouched_components(self):
        names = ("A", "B", "C", "D", "E")
        pairs = ((0, 1), (1, 2), (3, 4))
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 4.0, 5.25] + [0.0] * 5,
            dtype=torch.float64,
        )
        candidate = torch.tensor(
            [0.2, 1.2, 2.0, 4.375, 5.3125] + [0.0] * 5,
            dtype=torch.float64,
        )
        projector = _projector(
            names,
            (1.0,) * 5,
            (1.0,) * 5,
            pairs,
            active_node_ids=(0, 1, 3, 4),
            mode="protected_proposal_authority_search",
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(len(result["iterations"]), 2)
        second = result["iterations"][1]
        self.assertEqual(second["affected_protected_component_count"], 1)
        self.assertEqual(second["untouched_protected_component_count"], 1)
        self.assertEqual(
            [tuple(edge["node_ids"]) for edge in second["validated_contact_edges"]],
            [(0, 1), (1, 2)],
        )
        self.assertEqual(
            [component["node_ids"] for component in second["contact_components"]],
            [[0, 1, 2]],
        )

    def test_protected_authority_detects_reopened_edge(self):
        names = ("A", "B")
        full_validator = _aabb_validator(
            names, (1.0, 1.0), (1.0, 1.0), ((0, 1),)
        )

        def inconsistent_component_validator(coordinates, edges):
            return {
                "keepin_violation_count": 0,
                "overlap_pair_count": 0,
                "overlap_edges": [],
                "overlap_area_mm2": 0.0,
            }

        projector = ExactContactProjector(
            validator=full_validator,
            component_validator=inconsistent_component_validator,
            component_projector=_identity_component_projector,
            refdes_to_node_id={"A": 0, "B": 1},
            active_node_ids=(0, 1),
            num_nodes=2,
            mode="protected_proposal_authority_search",
        )
        origin = torch.tensor([0.0, 1.25, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor(
            [0.375, 1.3125, 0.0, 0.0], dtype=torch.float64
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "protected_edge_reopened")
        self.assertEqual(result["protected_edge_reopened_count"], 1)
        self.assertFalse(result["monotonic_progress"])
        self.assertEqual(
            result["protected_edge_reopened_edges"][0]["node_ids"], [0, 1]
        )

    def test_protected_authority_checks_expanded_component_limit(self):
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.2, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        projector = _projector(
            ("A", "B", "C"),
            (1.0,) * 3,
            (1.0,) * 3,
            ((0, 1), (1, 2)),
            active_node_ids=(0, 1),
            mode="protected_proposal_authority_search",
            max_cover_component_nodes=2,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "authority_component_limit")
        self.assertEqual(
            [row["applied"] for row in result["iterations"]], [True, False]
        )
        self.assertEqual(result["maximum_component_node_count"], 3)
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.2, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
            ),
            rtol=0,
            atol=0,
        )

    def test_protected_authority_checks_expanded_state_limit(self):
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.2, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        projector = _projector(
            ("A", "B", "C"),
            (1.0,) * 3,
            (1.0,) * 3,
            ((0, 1), (1, 2)),
            active_node_ids=(0, 1),
            mode="protected_proposal_authority_search",
            max_authority_states=8,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "authority_state_limit")
        self.assertEqual(
            [row["applied"] for row in result["iterations"]], [True, False]
        )
        self.assertEqual(
            result["maximum_authority_component_state_count"], 9
        )
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.2, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
            ),
            rtol=0,
            atol=0,
        )

    def test_authority_search_uses_mixed_exact_legal_authorities(self):
        projector = _projector(
            ("CENTER", "RIGHT", "TOP"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (0, 2)),
            mode="proposal_authority_search",
        )
        origin = torch.tensor(
            [0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.0, 0.0, 0.2, 0.0, 1.1], dtype=torch.float64
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.0, 1.0, 0.0, 0.1, 0.0, 1.1], dtype=torch.float64
            ),
            rtol=0,
            atol=1e-15,
        )
        self.assertEqual(result["corrected_contact_node_ids"], [0])
        iteration = result["iterations"][0]
        self.assertEqual(
            iteration["component_consensus_selected_contact_node_count"], 2
        )
        component = iteration["contact_components"][0]
        self.assertEqual(component["authority_state_count"], 27)
        self.assertEqual(
            {
                row["authority_node_id"]
                for row in component["authority_assignments"]
            },
            {1, 2},
        )

    def test_authority_state_limit_fails_before_mutation(self):
        projector = _projector(
            ("CENTER", "RIGHT", "TOP"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (0, 2)),
            mode="proposal_authority_search",
            max_authority_states=26,
        )
        origin = torch.tensor(
            [0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.0, 0.0, 0.2, 0.0, 1.1], dtype=torch.float64
        )
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "authority_state_limit")
        self.assertEqual(result["corrected_contact_node_count"], 0)
        self.assertEqual(
            result["maximum_authority_component_state_count"], 27
        )
        self.assertTrue(torch.equal(candidate, before))

    def test_authority_search_uses_inactive_motion_without_moving_it(self):
        projector = _projector(
            ("ACTIVE", "FIXED"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            active_node_ids=(0,),
            mode="proposal_authority_search",
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([0.2, 1.0, 0.0, 0.0], dtype=torch.float64)
        fixed_before = candidate[1].clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertTrue(torch.equal(candidate[1], fixed_before))
        self.assertEqual(result["corrected_contact_node_ids"], [0])
        assignment = result["contact_components"][0][
            "authority_assignments"
        ][0]
        self.assertEqual(assignment["authority_node_id"], 1)

    def test_authority_component_limit_fails_without_mutation(self):
        projector = _projector(
            ("CENTER", "RIGHT", "TOP"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (0, 2)),
            mode="proposal_authority_search",
            max_cover_component_nodes=2,
        )
        origin = torch.tensor(
            [0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.0, 0.0, 0.2, 0.0, 1.0], dtype=torch.float64
        )
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "authority_component_limit")
        self.assertEqual(result["corrected_contact_node_count"], 0)
        self.assertEqual(result["maximum_component_node_count"], 3)
        self.assertEqual(
            result["contact_components"][0]["planning_reason"],
            "authority_component_limit",
        )
        self.assertFalse(result["iterations"][0]["applied"])
        self.assertTrue(torch.equal(candidate, before))

    def test_authority_search_projects_scratch_assignment_before_validation(self):
        def bounded_projector(coordinates, active_node_ids):
            projected = dict(coordinates)
            projected_node_ids = []
            distances = []
            for node_id in active_node_ids:
                x, y = projected[node_id]
                bounded_x = min(x, 1.5)
                projected[node_id] = (bounded_x, y)
                if bounded_x != x:
                    projected_node_ids.append(node_id)
                    distances.append(x - bounded_x)
            return {
                "coordinates": projected,
                "projected_node_ids": projected_node_ids,
                "mean_distance": sum(distances) / len(distances)
                if distances
                else 0.0,
                "max_distance": max(distances, default=0.0),
            }

        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            mode="proposal_authority_search",
            component_projector=bounded_projector,
        )
        origin = torch.tensor([0.0, 1.25, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor(
            [0.375, 1.3125, 0.0, 0.0], dtype=torch.float64
        )

        def hard_projector(position):
            position[:2].clamp_(max=1.5)

        result = projector(origin, candidate, hard_projector)

        self.assertTrue(result["converged"])
        torch.testing.assert_close(
            candidate,
            torch.tensor([0.375, 1.5, 0.0, 0.0], dtype=torch.float64),
            rtol=0,
            atol=0,
        )
        iteration = result["iterations"][0]
        self.assertEqual(iteration["selected_contact_node_ids"], [1])
        self.assertEqual(iteration["authority_corrected_node_ids"], [1])
        self.assertEqual(
            iteration["authority_hard_projected_node_ids"], [1]
        )
        self.assertEqual(
            iteration["hard_projection_correction"]["changed_node_ids"], []
        )
        self.assertEqual(result["corrected_contact_node_ids"], [1])

    def test_authority_search_fails_closed_on_runtime_projection_mismatch(self):
        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            mode="proposal_authority_search",
        )
        origin = torch.tensor([0.0, 1.25, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor(
            [0.375, 1.3125, 0.0, 0.0], dtype=torch.float64
        )
        before = candidate.clone()

        def mismatched_hard_projector(position):
            position[0] = 0.25

        result = projector(origin, candidate, mismatched_hard_projector)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "authority_projection_mismatch")
        self.assertEqual(result["corrected_contact_node_count"], 0)
        self.assertEqual(
            result["iterations"][0][
                "authority_projection_mismatch_node_ids"
            ],
            [0],
        )
        self.assertTrue(torch.equal(candidate, before))

    def test_authority_search_handles_four_approach_directions(self):
        cases = (
            ([0.0, 1.25, 0.0, 0.0], [0.375, 1.3125, 0.0, 0.0]),
            ([0.0, -1.25, 0.0, 0.0], [-0.375, -1.3125, 0.0, 0.0]),
            ([0.0, 0.0, 0.0, 1.25], [0.0, 0.0, 0.375, 1.3125]),
            ([0.0, 0.0, 0.0, -1.25], [0.0, 0.0, -0.375, -1.3125]),
        )
        for origin_values, candidate_values in cases:
            projector = _projector(
                ("A", "B"),
                (1.0, 1.0),
                (1.0, 1.0),
                ((0, 1),),
                mode="proposal_authority_search",
            )
            origin = torch.tensor(origin_values, dtype=torch.float64)
            candidate = torch.tensor(candidate_values, dtype=torch.float64)

            result = projector(origin, candidate, lambda position: None)

            self.assertTrue(result["converged"])
            self.assertEqual(result["corrected_contact_node_count"], 1)
            self.assertEqual(
                _aabb_validator(
                    ("A", "B"),
                    (1.0, 1.0),
                    (1.0, 1.0),
                    ((0, 1),),
                )(candidate)["overlap_pair_count"],
                0,
            )

    def test_authority_search_handles_unequal_footprints(self):
        projector = _projector(
            ("WIDE", "NARROW"),
            (2.0, 0.5),
            (1.0, 0.5),
            ((0, 1),),
            mode="proposal_authority_search",
        )
        origin = torch.tensor([0.0, 2.25, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([0.4, 2.3, 0.0, 0.0], dtype=torch.float64)

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["corrected_contact_node_count"], 1)
        self.assertEqual(
            _aabb_validator(
                ("WIDE", "NARROW"),
                (2.0, 0.5),
                (1.0, 0.5),
                ((0, 1),),
            )(candidate)["overlap_pair_count"],
            0,
        )

    def test_authority_search_preserves_concave_corner_tangency(self):
        names = ("CONCAVE", "SQUARE")
        local_shapes = (
            Polygon(
                ((0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2))
            ),
            box(0, 0, 1, 1),
        )

        def intersection_area(coordinates):
            shapes = [
                affinity.translate(
                    local_shapes[node_id],
                    xoff=coordinates[node_id][0],
                    yoff=coordinates[node_id][1],
                )
                for node_id in range(2)
            ]
            return shapes[0].intersection(shapes[1]).area

        def validator(position):
            coordinates = {
                node_id: (
                    float(position[node_id]),
                    float(position[2 + node_id]),
                )
                for node_id in range(2)
            }
            area = intersection_area(coordinates)
            rows = (
                [
                    {
                        "kind": "constrained_constrained",
                        "first_refdes": names[0],
                        "second_refdes": names[1],
                        "overlap_area_mm2": area,
                    }
                ]
                if area > 1e-12
                else []
            )
            return {
                "keepin_violation_count": 0,
                "overlap_pair_count": len(rows),
                "overlap_area_mm2": area,
                "overlap_pairs": rows,
            }

        def component_validator(coordinates, edges):
            area = intersection_area(coordinates)
            return {
                "keepin_violation_count": 0,
                "overlap_pair_count": int(area > 1e-12),
                "overlap_edges": list(edges) if area > 1e-12 else [],
                "overlap_area_mm2": area,
            }

        projector = ExactContactProjector(
            validator=validator,
            component_validator=component_validator,
            component_projector=_identity_component_projector,
            refdes_to_node_id={"CONCAVE": 0, "SQUARE": 1},
            active_node_ids=(0, 1),
            num_nodes=2,
            mode="proposal_authority_search",
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 1.0], dtype=torch.float64)
        candidate = torch.tensor([0.2, 1.0, 0.2, 1.0], dtype=torch.float64)

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertAlmostEqual(
            intersection_area(
                {0: (candidate[0].item(), candidate[2].item()),
                 1: (candidate[1].item(), candidate[3].item())}
            ),
            0.0,
        )
        self.assertEqual(result["corrected_contact_node_count"], 1)

    def test_authority_new_component_cannot_reset_cumulative_budget(self):
        names = ("A", "B", "C", "D", "E", "F")
        full_reports = (((0, 1), (2, 3)), ((4, 5),), ())
        validator_call_count = 0

        def validator(position):
            nonlocal validator_call_count
            pairs = full_reports[
                min(validator_call_count, len(full_reports) - 1)
            ]
            validator_call_count += 1
            rows = [
                {
                    "kind": "constrained_constrained",
                    "first_refdes": names[first_node_id],
                    "second_refdes": names[second_node_id],
                    "overlap_area_mm2": 0.25,
                }
                for first_node_id, second_node_id in pairs
            ]
            return {
                "keepin_violation_count": 0,
                "overlap_pair_count": len(rows),
                "overlap_area_mm2": 0.25 * len(rows),
                "overlap_pairs": rows,
            }

        projector = ExactContactProjector(
            validator=validator,
            component_validator=_aabb_component_validator(
                (1.0,) * 6, (1.0,) * 6
            ),
            component_projector=_identity_component_projector,
            refdes_to_node_id={name: index for index, name in enumerate(names)},
            active_node_ids=range(6),
            num_nodes=6,
            max_contact_nodes=2,
            mode="proposal_authority_search",
        )
        origin = torch.tensor(
            [0.0, 1.25, 3.0, 4.25, 6.0, 7.25] + [0.0] * 6,
            dtype=torch.float64,
        )
        candidate = torch.tensor(
            [0.375, 1.3125, 3.375, 4.3125, 6.375, 7.3125]
            + [0.0] * 6,
            dtype=torch.float64,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "contact_node_limit")
        self.assertEqual(result["corrected_contact_node_count"], 2)
        self.assertEqual(result["required_corrected_contact_node_count"], 3)
        self.assertEqual(
            [row["applied"] for row in result["iterations"]], [True, False]
        )

    def test_minimum_cover_rolls_back_one_center_for_two_crossings(self):
        projector = _projector(
            ("CENTER", "RIGHT", "TOP"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (0, 2)),
            mode="minimum_cover_rollback",
        )
        origin = torch.tensor(
            [0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.375, 1.25, 0.25, 0.375, 0.25, 1.25],
            dtype=torch.float64,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["mode"], "minimum_cover_rollback")
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.0, 1.25, 0.25, 0.0, 0.25, 1.25],
                dtype=torch.float64,
            ),
            rtol=0,
            atol=0,
        )
        self.assertEqual(result["corrected_contact_node_ids"], [0])
        iteration = result["iterations"][0]
        self.assertEqual(iteration["selected_contact_node_ids"], [0])
        self.assertEqual(
            iteration["component_consensus_selected_contact_node_count"], 2
        )
        self.assertEqual(
            iteration["contact_components"][0]["minimum_cover_size"], 1
        )
        self.assertEqual(
            iteration["contact_components"][0]["selectable_node_ids"],
            [0, 1, 2],
        )
        self.assertEqual(iteration["cover_search_state_count"], 8)

    def test_minimum_cover_equal_cost_uses_smallest_node_id(self):
        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            mode="minimum_cover_rollback",
        )
        origin = torch.tensor([0.0, 1.25, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([0.25, 1.0, 0.0, 0.0], dtype=torch.float64)

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["corrected_contact_node_ids"], [0])
        torch.testing.assert_close(
            candidate,
            torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64),
            rtol=0,
            atol=0,
        )

    def test_minimum_cover_never_selects_noop_endpoint(self):
        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            mode="minimum_cover_rollback",
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([0.25, 1.0, 0.0, 0.0], dtype=torch.float64)

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        component = result["contact_components"][0]
        self.assertEqual(component["selectable_node_ids"], [0])
        self.assertEqual(component["mandatory_node_ids"], [0])
        self.assertEqual(result["corrected_contact_node_ids"], [0])

    def test_minimum_cover_inactive_endpoint_makes_active_mandatory(self):
        projector = _projector(
            ("ACTIVE", "INACTIVE"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            active_node_ids=(0,),
            mode="minimum_cover_rollback",
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([0.25, 1.0, 0.0, 0.0], dtype=torch.float64)
        inactive_before = candidate[1].clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertTrue(torch.equal(candidate[1], inactive_before))
        self.assertEqual(result["corrected_contact_node_ids"], [0])
        component = result["contact_components"][0]
        self.assertEqual(component["authority_kind"], "accepted_origin_cover")
        self.assertEqual(component["inactive_node_count"], 1)
        self.assertEqual(component["mandatory_node_ids"], [0])

    def test_minimum_cover_residual_edge_adds_opposite_endpoint(self):
        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            mode="minimum_cover_rollback",
        )
        origin = torch.tensor([0.0, 1.25, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor(
            [0.375, 1.3125, 0.0, 0.0], dtype=torch.float64
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertTrue(torch.equal(candidate, origin))
        self.assertEqual(result["corrected_contact_node_ids"], [0, 1])
        self.assertEqual(len(result["iterations"]), 2)
        self.assertEqual(
            [row["selected_contact_node_ids"] for row in result["iterations"]],
            [[1], [0]],
        )
        self.assertEqual(
            [
                row["cumulative_corrected_contact_node_count"]
                for row in result["iterations"]
            ],
            [1, 2],
        )
        self.assertEqual(result["validator_call_count"], 3)

    def test_minimum_cover_cumulative_limit_fails_before_second_write(self):
        projector = _projector(
            ("A", "B", "C", "D"),
            (1.0, 1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0, 1.0),
            ((0, 1), (2, 3)),
            max_contact_nodes=2,
            mode="minimum_cover_rollback",
        )
        origin = torch.tensor(
            [0.0, 1.25, 3.0, 4.25, 0.0, 0.0, 0.0, 0.0],
            dtype=torch.float64,
        )
        candidate = torch.tensor(
            [0.375, 1.3125, 3.25, 4.0, 0.0, 0.0, 0.0, 0.0],
            dtype=torch.float64,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "contact_node_limit")
        self.assertEqual(result["corrected_contact_node_ids"], [1, 2])
        self.assertEqual(result["required_corrected_contact_node_count"], 3)
        self.assertEqual(
            [row["applied"] for row in result["iterations"]], [True, False]
        )
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.375, 1.25, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0],
                dtype=torch.float64,
            ),
            rtol=0,
            atol=0,
        )

    def test_minimum_cover_new_edge_merge_retains_cumulative_ids(self):
        names = ("A", "B", "C", "D")
        reports = (
            ((0, 1), (2, 3)),
            ((1, 2),),
            (),
        )
        validator_call_count = 0

        def validator(position):
            nonlocal validator_call_count
            pairs = reports[min(validator_call_count, len(reports) - 1)]
            validator_call_count += 1
            rows = [
                {
                    "kind": "constrained_constrained",
                    "first_refdes": names[first_node_id],
                    "second_refdes": names[second_node_id],
                    "overlap_area_mm2": 1.0,
                }
                for first_node_id, second_node_id in pairs
            ]
            return {
                "keepin_violation_count": 0,
                "overlap_pair_count": len(rows),
                "overlap_area_mm2": float(len(rows)),
                "overlap_pairs": rows,
            }

        projector = ExactContactProjector(
            validator=validator,
            refdes_to_node_id={name: index for index, name in enumerate(names)},
            active_node_ids=range(4),
            num_nodes=4,
            max_contact_nodes=3,
            mode="minimum_cover_rollback",
        )
        origin = torch.zeros(8, dtype=torch.float64)
        candidate = torch.tensor(
            [1.0, 2.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0],
            dtype=torch.float64,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["protected_pair_count"], 3)
        self.assertEqual(result["component_count"], 1)
        self.assertEqual(result["corrected_contact_node_ids"], [0, 1, 2])
        self.assertEqual(
            [
                row["cumulative_corrected_contact_node_count"]
                for row in result["iterations"]
            ],
            [2, 3],
        )
        self.assertEqual(
            [row["selected_contact_node_ids"] for row in result["iterations"]],
            [[0, 2], [1]],
        )

    def test_minimum_cover_component_limit_fails_without_mutation(self):
        projector = _projector(
            ("CENTER", "RIGHT", "TOP"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (0, 2)),
            mode="minimum_cover_rollback",
            max_cover_component_nodes=2,
        )
        origin = torch.tensor(
            [0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.0, 0.0, 0.2, 0.0, 1.0], dtype=torch.float64
        )
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "cover_component_limit")
        self.assertEqual(result["corrected_contact_node_count"], 0)
        self.assertFalse(result["iterations"][0]["applied"])
        self.assertTrue(torch.equal(candidate, before))

    def test_minimum_cover_and_hard_projection_statistics_are_separate(self):
        projector = _projector(
            ("A", "B", "C"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1),),
            mode="minimum_cover_rollback",
        )
        origin = torch.tensor(
            [0.0, 1.0, 3.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.25, 1.0, 3.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )

        def hard_projector(position):
            position[2] = 3.125

        result = projector(origin, candidate, hard_projector)

        self.assertTrue(result["converged"])
        iteration = result["iterations"][0]
        self.assertEqual(
            iteration["rollback_correction"]["changed_node_ids"], [0]
        )
        self.assertEqual(
            iteration["hard_projection_correction"]["changed_node_ids"], [2]
        )
        self.assertEqual(iteration["correction"]["changed_node_ids"], [0, 2])
        self.assertEqual(result["corrected_contact_node_ids"], [0])

    def test_two_body_consensus_handles_four_crossing_directions(self):
        projector = _projector(
            ("A", "B"), (1.0, 1.0), (1.0, 1.0), ((0, 1),)
        )
        cases = (
            ([0.0, 1.0, 0.0, 0.0], [0.2, 1.0, 0.0, 0.0]),
            ([0.0, -1.0, 0.0, 0.0], [-0.2, -1.0, 0.0, 0.0]),
            ([0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.2, 1.0]),
            ([0.0, 0.0, 0.0, -1.0], [0.0, 0.0, -0.2, -1.0]),
        )
        for origin_values, candidate_values in cases:
            origin = torch.tensor(origin_values, dtype=torch.float64)
            candidate = torch.tensor(candidate_values, dtype=torch.float64)

            result = projector(origin, candidate, lambda position: None)

            self.assertTrue(result["converged"])
            self.assertEqual(result["reason"], "legal")
            torch.testing.assert_close(
                candidate[1] - candidate[0],
                origin[1] - origin[0],
                rtol=0,
                atol=1e-12,
            )
            torch.testing.assert_close(
                candidate[3] - candidate[2],
                origin[3] - origin[2],
                rtol=0,
                atol=1e-12,
            )
            self.assertEqual(result["corrected_contact_node_count"], 1)
            self.assertEqual(
                result["contact_components"][0]["representative_node_id"], 0
            )

    def test_movable_to_frozen_contact_uses_frozen_motion(self):
        projector = _projector(
            ("A", "B"),
            (1.0, 1.0),
            (1.0, 1.0),
            ((0, 1),),
            active_node_ids=(0,),
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([0.2, 1.0, 0.0, 0.0], dtype=torch.float64)

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertTrue(torch.equal(candidate, origin))
        self.assertEqual(
            result["contact_components"][0]["active_node_count"], 1
        )
        self.assertEqual(
            result["contact_components"][0]["authority_kind"],
            "inactive_mean",
        )
        self.assertEqual(result["corrected_contact_node_count"], 1)

    def test_inactive_references_do_not_consume_active_node_budget(self):
        projector = _projector(
            ("A", "B", "C", "D"),
            (1.0, 1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0, 1.0),
            ((0, 1), (2, 3)),
            active_node_ids=(0, 2),
            max_contact_nodes=2,
        )
        origin = torch.tensor(
            [0.0, 1.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0],
            dtype=torch.float64,
        )
        candidate = torch.tensor(
            [0.2, 1.0, 3.2, 4.0, 0.0, 0.0, 0.0, 0.0],
            dtype=torch.float64,
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(
            result["contact_node_limit_basis"],
            "cumulative_corrected_active_nodes",
        )
        self.assertEqual(result["contact_node_count"], 4)
        self.assertEqual(result["active_contact_node_count"], 2)
        self.assertEqual(result["corrected_contact_node_count"], 2)
        self.assertEqual(result["required_corrected_contact_node_count"], 2)
        self.assertEqual(result["component_count"], 2)
        self.assertEqual(result["maximum_component_node_count"], 2)
        self.assertEqual(result["maximum_active_component_node_count"], 1)
        self.assertTrue(torch.equal(candidate, origin))

    def test_multi_contact_chain_uses_one_shared_displacement(self):
        projector = _projector(
            ("A", "B", "C"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (1, 2)),
        )
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.0, 1.8, 0.0, 0.0, 0.0], dtype=torch.float64
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        torch.testing.assert_close(candidate, origin, rtol=0, atol=1e-15)
        self.assertEqual(result["protected_pair_count"], 2)
        self.assertEqual(len(result["contact_components"]), 1)
        self.assertEqual(result["active_contact_node_count"], 3)
        self.assertEqual(result["corrected_contact_node_count"], 2)
        self.assertEqual(
            result["contact_components"][0]["representative_node_id"], 1
        )
        self.assertEqual(
            result["contact_components"][0]["corrected_node_ids"], [0, 2]
        )

    def test_component_preserves_minimum_cost_native_representative(self):
        projector = _projector(
            ("A", "B", "C"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (1, 2)),
        )
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.3, 1.1, 1.5, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        representative_before = candidate[1].clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertTrue(torch.equal(candidate[1], representative_before))
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.1, 1.1, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
            ),
            rtol=0,
            atol=1e-15,
        )
        component = result["contact_components"][0]
        self.assertEqual(component["authority_kind"], "active_representative")
        self.assertEqual(component["representative_node_id"], 1)
        self.assertEqual(component["corrected_node_ids"], [0, 2])

    def test_iterative_closure_adds_new_contact_without_losing_old_pair(self):
        projector = _projector(
            ("A", "B", "C"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (1, 2)),
        )
        origin = torch.tensor(
            [0.0, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.4, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["protected_pair_count"], 2)
        self.assertEqual(len(result["iterations"]), 2)
        self.assertEqual(
            [row["new_contact_pair_count"] for row in result["iterations"]],
            [1, 1],
        )
        self.assertEqual(
            [
                row["cumulative_corrected_contact_node_count"]
                for row in result["iterations"]
            ],
            [1, 3],
        )
        self.assertEqual(result["corrected_contact_node_ids"], [0, 1, 2])
        self.assertEqual(
            _aabb_validator(
                ("A", "B", "C"),
                (1.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
                ((0, 1), (1, 2)),
            )(candidate)["overlap_pair_count"],
            0,
        )

    def test_iterative_closure_cannot_reset_cumulative_correction_budget(self):
        projector = _projector(
            ("A", "B", "C"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (1, 2)),
            max_contact_nodes=2,
        )
        origin = torch.tensor(
            [0.0, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.4, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "contact_node_limit")
        self.assertEqual(result["corrected_contact_node_count"], 1)
        self.assertEqual(result["required_corrected_contact_node_count"], 3)
        self.assertEqual(
            [row["applied"] for row in result["iterations"]], [True, False]
        )
        torch.testing.assert_close(
            candidate,
            torch.tensor(
                [0.4, 1.4, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
            ),
            rtol=0,
            atol=1e-15,
        )

    def test_three_node_component_fits_two_correction_budget(self):
        projector = _projector(
            ("A", "B", "C"),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            ((0, 1), (1, 2)),
            max_contact_nodes=2,
        )
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        candidate = torch.tensor(
            [0.2, 1.0, 1.8, 0.0, 0.0, 0.0], dtype=torch.float64
        )

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["active_contact_node_count"], 3)
        self.assertEqual(result["corrected_contact_node_count"], 2)
        self.assertEqual(result["required_corrected_contact_node_count"], 2)
        self.assertTrue(torch.equal(candidate, origin))

    def test_four_node_component_exceeding_correction_budget_is_unchanged(self):
        projector = _projector(
            ("A", "B", "C", "D"),
            (1.0, 1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0, 1.0),
            ((0, 1), (1, 2), (2, 3)),
            max_contact_nodes=2,
        )
        origin = torch.tensor(
            [0.0, 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 0.0],
            dtype=torch.float64,
        )
        candidate = torch.tensor(
            [0.3, 1.1, 1.9, 2.7, 0.0, 0.0, 0.0, 0.0],
            dtype=torch.float64,
        )
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "contact_node_limit")
        self.assertEqual(
            result["contact_node_limit_basis"],
            "cumulative_corrected_active_nodes",
        )
        self.assertEqual(result["contact_node_count"], 4)
        self.assertEqual(result["active_contact_node_count"], 4)
        self.assertEqual(result["corrected_contact_node_count"], 0)
        self.assertEqual(result["required_corrected_contact_node_count"], 3)
        self.assertTrue(torch.equal(candidate, before))

    def test_disconnected_pairs_keep_endpoint_pressure_separate(self):
        names = tuple("ABCDEFGH")
        pairs = ((0, 1), (2, 3), (4, 5), (6, 7))
        projector = _projector(
            names,
            (1.0,) * 8,
            (1.0,) * 8,
            pairs,
            max_contact_nodes=4,
        )
        origin = torch.tensor(
            [0.0, 1.0, 3.0, 4.0, 6.0, 7.0, 9.0, 10.0] + [0.0] * 8,
            dtype=torch.float64,
        )
        candidate = origin.clone()
        candidate[torch.tensor([0, 2, 4, 6])] += 0.2

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["active_contact_node_count"], 8)
        self.assertEqual(result["corrected_contact_node_count"], 4)
        self.assertEqual(result["corrected_contact_node_ids"], [1, 3, 5, 7])
        self.assertEqual(result["component_count"], 4)
        json.dumps(result, sort_keys=True)

    def test_inactive_authorities_charge_every_active_member(self):
        projector = _projector(
            ("A", "B", "C", "D", "E", "F"),
            (1.0,) * 6,
            (1.0,) * 6,
            ((0, 1), (2, 3), (4, 5)),
            active_node_ids=(0, 2, 4),
            max_contact_nodes=2,
        )
        origin = torch.tensor(
            [0.0, 1.0, 3.0, 4.0, 6.0, 7.0] + [0.0] * 6,
            dtype=torch.float64,
        )
        candidate = origin.clone()
        candidate[torch.tensor([0, 2, 4])] += 0.2
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "contact_node_limit")
        self.assertEqual(result["active_contact_node_count"], 3)
        self.assertEqual(result["corrected_contact_node_count"], 0)
        self.assertEqual(result["required_corrected_contact_node_count"], 3)
        self.assertTrue(torch.equal(candidate, before))

    def test_consensus_and_hard_projection_statistics_are_separate(self):
        projector = _projector(
            ("A", "B"), (1.0, 1.0), (1.0, 1.0), ((0, 1),)
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([0.2, 1.0, 0.0, 0.0], dtype=torch.float64)

        def hard_projector(position):
            position[0] = 0.1

        result = projector(origin, candidate, hard_projector)

        self.assertTrue(result["converged"])
        iteration = result["iterations"][0]
        self.assertEqual(
            iteration["consensus_correction"]["changed_node_ids"], [1]
        )
        self.assertEqual(
            iteration["hard_projection_correction"]["changed_node_ids"], [0]
        )
        self.assertEqual(iteration["correction"]["changed_node_ids"], [0, 1])
        self.assertEqual(result["corrected_contact_node_ids"], [1])

    def test_legal_candidate_is_unchanged(self):
        projector = _projector(
            ("A", "B"), (1.0, 1.0), (1.0, 1.0), ((0, 1),)
        )
        origin = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        candidate = torch.tensor([-0.1, 1.1, 0.0, 0.0], dtype=torch.float64)
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertTrue(result["converged"])
        self.assertEqual(result["protected_pair_count"], 0)
        self.assertTrue(torch.equal(candidate, before))

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_cpu_gpu_projection_is_identical(self):
        for dtype in (torch.float32, torch.float64):
            cpu_projector = _projector(
                ("A", "B", "C"),
                (1.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
                ((0, 1), (1, 2)),
            )
            gpu_projector = _projector(
                ("A", "B", "C"),
                (1.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
                ((0, 1), (1, 2)),
            )
            origin = torch.tensor(
                [0.0, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=dtype
            )
            cpu_candidate = torch.tensor(
                [0.4, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=dtype
            )
            gpu_origin = origin.cuda()
            gpu_candidate = cpu_candidate.cuda()

            cpu_result = cpu_projector(
                origin, cpu_candidate, lambda position: None
            )
            gpu_result = gpu_projector(
                gpu_origin, gpu_candidate, lambda position: None
            )

            self.assertTrue(torch.equal(cpu_candidate, gpu_candidate.cpu()))
            self.assertEqual(cpu_result["reason"], gpu_result["reason"])
            self.assertEqual(
                cpu_result["contact_components"],
                gpu_result["contact_components"],
            )
            self.assertEqual(
                cpu_result["corrected_contact_node_ids"],
                gpu_result["corrected_contact_node_ids"],
            )
            self.assertEqual(
                cpu_result["required_corrected_contact_node_count"],
                gpu_result["required_corrected_contact_node_count"],
            )

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_minimum_cover_cpu_gpu_tie_break_is_identical(self):
        for dtype in (torch.float32, torch.float64):
            cpu_projector = _projector(
                ("A", "B"),
                (1.0, 1.0),
                (1.0, 1.0),
                ((0, 1),),
                mode="minimum_cover_rollback",
            )
            gpu_projector = _projector(
                ("A", "B"),
                (1.0, 1.0),
                (1.0, 1.0),
                ((0, 1),),
                mode="minimum_cover_rollback",
            )
            origin = torch.tensor([0.0, 1.25, 0.0, 0.0], dtype=dtype)
            cpu_candidate = torch.tensor(
                [0.25, 1.0, 0.0, 0.0], dtype=dtype
            )
            gpu_origin = origin.cuda()
            gpu_candidate = cpu_candidate.cuda()

            cpu_result = cpu_projector(
                origin, cpu_candidate, lambda position: None
            )
            gpu_result = gpu_projector(
                gpu_origin, gpu_candidate, lambda position: None
            )

            self.assertTrue(torch.equal(cpu_candidate, gpu_candidate.cpu()))
            self.assertEqual(
                cpu_result["corrected_contact_node_ids"],
                gpu_result["corrected_contact_node_ids"],
            )
            self.assertEqual(
                cpu_result["iterations"][0]["contact_components"],
                gpu_result["iterations"][0]["contact_components"],
            )

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_authority_search_cpu_gpu_assignment_is_identical(self):
        for dtype in (torch.float32, torch.float64):
            cpu_projector = _projector(
                ("CENTER", "RIGHT", "TOP"),
                (1.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
                ((0, 1), (0, 2)),
                mode="proposal_authority_search",
            )
            gpu_projector = _projector(
                ("CENTER", "RIGHT", "TOP"),
                (1.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
                ((0, 1), (0, 2)),
                mode="proposal_authority_search",
            )
            origin = torch.tensor(
                [0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=dtype
            )
            cpu_candidate = torch.tensor(
                [0.2, 1.0, 0.0, 0.2, 0.0, 1.1], dtype=dtype
            )
            gpu_origin = origin.cuda()
            gpu_candidate = cpu_candidate.cuda()

            cpu_result = cpu_projector(
                origin, cpu_candidate, lambda position: None
            )
            gpu_result = gpu_projector(
                gpu_origin, gpu_candidate, lambda position: None
            )

            self.assertTrue(torch.equal(cpu_candidate, gpu_candidate.cpu()))
            self.assertEqual(
                cpu_result["corrected_contact_node_ids"],
                gpu_result["corrected_contact_node_ids"],
            )
            self.assertEqual(
                cpu_result["contact_components"],
                gpu_result["contact_components"],
            )

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_protected_authority_cpu_gpu_closure_is_identical(self):
        for dtype in (torch.float32, torch.float64):
            cpu_projector = _projector(
                ("A", "B", "C"),
                (1.0,) * 3,
                (1.0,) * 3,
                ((0, 1), (1, 2)),
                active_node_ids=(0, 1),
                mode="protected_proposal_authority_search",
            )
            gpu_projector = _projector(
                ("A", "B", "C"),
                (1.0,) * 3,
                (1.0,) * 3,
                ((0, 1), (1, 2)),
                active_node_ids=(0, 1),
                mode="protected_proposal_authority_search",
            )
            origin = torch.tensor(
                [0.0, 1.0, 2.0, 0.0, 0.0, 0.0], dtype=dtype
            )
            cpu_candidate = torch.tensor(
                [0.2, 1.2, 2.0, 0.0, 0.0, 0.0], dtype=dtype
            )
            gpu_origin = origin.cuda()
            gpu_candidate = cpu_candidate.cuda()

            cpu_result = cpu_projector(
                origin, cpu_candidate, lambda position: None
            )
            gpu_result = gpu_projector(
                gpu_origin, gpu_candidate, lambda position: None
            )

            self.assertTrue(torch.equal(cpu_candidate, gpu_candidate.cpu()))
            self.assertEqual(
                cpu_result["corrected_contact_node_ids"],
                gpu_result["corrected_contact_node_ids"],
            )
            self.assertEqual(
                [row["contact_components"] for row in cpu_result["iterations"]],
                [row["contact_components"] for row in gpu_result["iterations"]],
            )
            self.assertEqual(
                cpu_result["protected_closure_validation"],
                gpu_result["protected_closure_validation"],
            )


if __name__ == "__main__":
    unittest.main()
