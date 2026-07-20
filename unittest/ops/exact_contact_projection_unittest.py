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
    )


class ExactContactProjectionTest(unittest.TestCase):
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
        self.assertEqual(result["contact_node_limit_basis"], "active_nodes")
        self.assertEqual(result["contact_node_count"], 4)
        self.assertEqual(result["active_contact_node_count"], 2)
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
            _aabb_validator(
                ("A", "B", "C"),
                (1.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
                ((0, 1), (1, 2)),
            )(candidate)["overlap_pair_count"],
            0,
        )

    def test_contact_node_limit_leaves_candidate_for_guard_rejection(self):
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
        before = candidate.clone()

        result = projector(origin, candidate, lambda position: None)

        self.assertFalse(result["converged"])
        self.assertEqual(result["reason"], "contact_node_limit")
        self.assertEqual(result["contact_node_limit_basis"], "active_nodes")
        self.assertEqual(result["contact_node_count"], 3)
        self.assertEqual(result["active_contact_node_count"], 3)
        self.assertTrue(torch.equal(candidate, before))

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
            [0.0, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
        )
        cpu_candidate = torch.tensor(
            [0.4, 1.0, 2.1, 0.0, 0.0, 0.0], dtype=torch.float64
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


if __name__ == "__main__":
    unittest.main()
