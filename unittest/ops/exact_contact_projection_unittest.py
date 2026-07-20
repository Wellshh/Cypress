import json
import unittest

import torch

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


if __name__ == "__main__":
    unittest.main()
