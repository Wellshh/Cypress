import math
import os
import sys
import unittest
from unittest import mock

import numpy as np
import torch
from shapely.geometry import Polygon, box

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dreamplace.constraints.pcb_geometry import (
    GeometryAlignment,
    conservative_region_boxes,
    dbu_to_mm,
    load_pcb_geometry,
    polygon_from_segments,
)
from dreamplace.constraints.region_assignment import (
    load_clusters,
    split_side_subgroups,
)
from dreamplace.constraints.region_projection import (
    FeasibleDomain,
    NodeConstraint,
    RegionProjector,
    zero_optimizer_state,
)
from dreamplace.constraints.region_validation import (
    ComponentPlacement,
    validate_placement,
)
from dreamplace.constraints.anchor_keepin import (
    _batch_overlap_metrics,
    _forward_check_rectangle_pack,
    _min_conflicts_pack,
    _obstacle_free_candidate_indices,
    _ordered_candidate_indices,
    _overlap_metrics,
    _pack_region,
)
from dreamplace.ops.anchor_keepin.anchor_keepin import AnchorKeepInLoss, SoftKeepInLoss


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_DIR = os.path.join(REPO_ROOT, "experiments", "m336", "input")


class AnchorKeepInTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry = load_pcb_geometry(
            os.path.join(INPUT_DIR, "pcb_geometry_keepin.json")
        )

    def test_cluster_manifest_integrity(self):
        clusters = load_clusters(os.path.join(INPUT_DIR, "m336_clusters.json"))
        members = [member for cluster in clusters for member in cluster.members]
        self.assertEqual(len(clusters), 25)
        self.assertEqual(len(members), 125)
        self.assertEqual(len(set(members)), 125)
        subgroups = split_side_subgroups(
            clusters,
            {name: symbol.side for name, symbol in self.geometry.symbols.items()},
        )
        self.assertEqual(len(subgroups), 31)

    def test_geometry_dbu_to_mm(self):
        np.testing.assert_allclose(dbu_to_mm([10000, -2500], 10000), [1.0, -0.25])

    def test_geometry_alignment(self):
        source = {
            "A": (0.0, 0.0),
            "B": (2.0, 0.0),
            "C": (0.0, 3.0),
            "D": (2.0, 3.0),
        }
        target = {
            name: (4.0 * point[0] + 7.0, -4.0 * point[1] - 2.0)
            for name, point in source.items()
        }
        alignment = GeometryAlignment.fit(source, target, max_residual_mm=1e-9)
        self.assertTrue(alignment.flip_y)
        self.assertAlmostEqual(alignment.scale, 4.0)
        self.assertLess(alignment.max_residual_mm, 1e-12)

    def test_arc_polygon_reconstruction(self):
        segments = [
            {"obj_type": "line", "start_end": [[0, 0], [10000, 0]]},
            {
                "obj_type": "arc",
                "start_end": [[10000, 0], [20000, 10000]],
                "center": [10000, 10000],
                "radius": 10000,
                "is_clockwise": False,
            },
            {"obj_type": "line", "start_end": [[20000, 10000], [20000, 20000]]},
            {"obj_type": "line", "start_end": [[20000, 20000], [0, 20000]]},
            {"obj_type": "line", "start_end": [[0, 20000], [0, 0]]},
        ]
        polygon = polygon_from_segments(segments, 10000, chord_error_mm=0.0001)
        self.assertAlmostEqual(polygon.area, 3.0 + math.pi / 4, places=3)

    def test_region_decomposition_is_conservative(self):
        region = Polygon([(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)])
        boxes = conservative_region_boxes(region, 0.25)
        decomposed = [box(*bounds) for bounds in boxes]
        self.assertTrue(decomposed)
        self.assertLessEqual(sum(piece.difference(region).area for piece in decomposed), 1e-12)

    def test_region_boxes_are_non_overlapping(self):
        region = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        pieces = [box(*bounds) for bounds in conservative_region_boxes(region, 0.5)]
        for index, first in enumerate(pieces):
            for second in pieces[index + 1 :]:
                self.assertLessEqual(first.intersection(second).area, 1e-12)

    def test_component_feasible_domain(self):
        region = Polygon([(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)])
        domain = FeasibleDomain.build(region, width=0.8, height=0.8, grid=0.1)
        self.assertTrue(domain.contains((0.5, 2.0)))
        self.assertFalse(domain.contains((1.5, 1.5)))
        self.assertGreater(len(domain.valid_centers), 0)
        self.assertEqual(domain.inside_distance.shape, domain.valid_mask.shape)
        self.assertGreater(domain.inside_distance[domain.valid_mask].min(), 0)

    @staticmethod
    def _soft_keepin_loss(device="cpu"):
        domain = FeasibleDomain.build(box(0, 0, 4, 4), 0.4, 0.4, 0.1)
        constraint = NodeConstraint(
            node_id=0,
            refdes="U1",
            side="TOP",
            group_id="G",
            subgroup_id="G__top",
            region_id="top_0",
            domain=domain,
            target_center=(2.0, 2.0),
            node_width=0.4,
            node_height=0.4,
        )
        return SoftKeepInLoss(
            constraints=[constraint],
            num_nodes=1,
            margin=0.3,
            tau=0.05,
            dtype=torch.float64,
        ).to(device)

    def test_soft_keepin_margin_is_inward_and_negligible_deep_inside(self):
        loss_op = self._soft_keepin_loss()
        deep = torch.tensor([1.8, 1.8], dtype=torch.float64, requires_grad=True)
        near = torch.tensor([0.0, 1.8], dtype=torch.float64, requires_grad=True)

        deep_loss = loss_op(deep)
        near_loss = loss_op(near)
        outside_loss = loss_op(
            torch.tensor([-0.1, 1.8], dtype=torch.float64)
        )
        near_loss.backward()

        self.assertLess(deep_loss.item(), 1e-12)
        self.assertGreater(near_loss.item(), 1.0)
        self.assertGreater(outside_loss.item(), near_loss.item())
        self.assertTrue(torch.isfinite(near.grad).all())
        self.assertLess(near.grad[0].item(), 0.0)
        self.assertAlmostEqual(near.grad[1].item(), 0.0, places=10)

    def test_soft_keepin_forward_does_not_query_cpu_geometry(self):
        loss_op = self._soft_keepin_loss()
        pos = torch.tensor([0.05, 1.8], dtype=torch.float64)
        with mock.patch.object(
            FeasibleDomain,
            "contains",
            side_effect=AssertionError("forward queried exact geometry"),
        ), mock.patch.object(
            FeasibleDomain,
            "project",
            side_effect=AssertionError("forward projected on CPU"),
        ):
            self.assertTrue(torch.isfinite(loss_op(pos)))

    def test_soft_keepin_margin_matches_finite_difference(self):
        loss_op = self._soft_keepin_loss()
        pos = torch.tensor([0.05, 1.8], dtype=torch.float64, requires_grad=True)
        loss_op(pos).backward()
        analytical = pos.grad[0].item()
        epsilon = 1e-6
        with torch.no_grad():
            offset = torch.tensor([epsilon, 0.0], dtype=pos.dtype)
            upper = loss_op(pos + offset).item()
            lower = loss_op(pos - offset).item()
        finite_difference = (upper - lower) / (2 * epsilon)
        self.assertAlmostEqual(analytical, finite_difference, places=5)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_soft_keepin_margin_cpu_gpu_consistency(self):
        cpu_op = self._soft_keepin_loss()
        gpu_op = self._soft_keepin_loss("cuda")
        cpu_pos = torch.tensor(
            [0.05, 1.8], dtype=torch.float64, requires_grad=True
        )
        gpu_pos = cpu_pos.detach().clone().cuda().requires_grad_(True)

        cpu_loss = cpu_op(cpu_pos)
        gpu_loss = gpu_op(gpu_pos)
        cpu_loss.backward()
        gpu_loss.backward()

        self.assertAlmostEqual(cpu_loss.item(), gpu_loss.item(), places=10)
        np.testing.assert_allclose(
            cpu_pos.grad.detach().numpy(),
            gpu_pos.grad.detach().cpu().numpy(),
            rtol=1e-9,
            atol=1e-9,
        )

    def test_projected_anchor_target(self):
        domain = FeasibleDomain.build(box(0, 0, 2, 2), 0.5, 0.5, 0.1)
        projected, distance = domain.project((-1.0, 1.0))
        self.assertTrue(domain.contains(projected))
        self.assertGreater(distance, 1.0)

    def test_hard_projector_inside_domain(self):
        domain = FeasibleDomain.build(box(0, 0, 2, 2), 0.5, 0.5, 0.1)
        constraint = NodeConstraint(
            node_id=0,
            refdes="U1",
            side="TOP",
            group_id="G",
            subgroup_id="G__top",
            region_id="top_0",
            domain=domain,
            target_center=(0.5, 0.5),
            node_width=0.5,
            node_height=0.5,
        )
        pos = torch.tensor([-2.0, 0.75])
        stats = RegionProjector(1, [constraint])(pos)
        center = (float(pos[0]) + 0.25, float(pos[1]) + 0.25)
        self.assertEqual(stats.count, 1)
        self.assertGreater(stats.max_distance, 0.0)
        self.assertEqual(stats.mean_distance, stats.max_distance)
        self.assertEqual(stats.total_distance, stats.max_distance)
        self.assertTrue(domain.contains(center))

    def test_rectangle_packer_resolves_colliding_preferences(self):
        domain = FeasibleDomain.build(box(0, 0, 2, 1), 1.0, 1.0, 0.5)
        constraints = [
            NodeConstraint(
                node_id=node_id,
                refdes="U%d" % node_id,
                side="TOP",
                group_id="G",
                subgroup_id="G__top",
                region_id="top_0",
                domain=domain,
                target_center=(0.5, 0.5),
                node_width=1.0,
                node_height=1.0,
            )
            for node_id in range(2)
        ]
        placements, _ = _pack_region(
            constraints,
            obstacles=[],
            preferred_centers={0: (0.5, 0.5), 1: (0.5, 0.5)},
        )
        first = domain.footprint(placements[0])
        second = domain.footprint(placements[1])
        self.assertLessEqual(first.intersection(second).area, 1e-12)

        forward_placements, stats = _forward_check_rectangle_pack(
            constraints,
            obstacles=[],
            preferred_centers={0: (0.5, 0.5), 1: (0.5, 0.5)},
        )
        self.assertFalse(stats["proven_infeasible"])
        first = domain.footprint(forward_placements[0])
        second = domain.footprint(forward_placements[1])
        self.assertLessEqual(first.intersection(second).area, 1e-12)

        limited, limited_stats = _forward_check_rectangle_pack(
            constraints,
            obstacles=[],
            preferred_centers={0: (0.5, 0.5), 1: (0.5, 0.5)},
            candidate_limit=1,
        )
        self.assertIsNone(limited)
        self.assertFalse(limited_stats["proven_infeasible"])

        preferred = np.asarray((1.5, 0.5))
        expected = np.argsort(
            np.square(domain.valid_centers - preferred).sum(axis=1),
            kind="stable",
        )
        np.testing.assert_array_equal(
            _ordered_candidate_indices(
                constraints[0], "preferred", preferred
            ),
            expected,
        )
        obstacle_free = _obstacle_free_candidate_indices(
            constraints[0], [box(0, 0, 1, 1)]
        )
        np.testing.assert_allclose(
            domain.valid_centers[obstacle_free], [[1.5, 0.5]]
        )

    def test_batch_overlap_metrics_match_scalar_exact_geometry(self):
        candidates = [
            box(0, 0, 2, 2),
            Polygon(((0, 0), (2, 0), (1, 2))),
            box(3, 0, 4, 1),
        ]
        others = [box(1, 1, 3, 3), box(2, 0, 3, 1)]
        expected = [_overlap_metrics(row, others) for row in candidates]
        counts, areas = _batch_overlap_metrics(candidates, others)
        np.testing.assert_array_equal(counts, [row[0] for row in expected])
        np.testing.assert_allclose(areas, [row[1] for row in expected])

    def test_min_conflicts_rejects_invalid_escape_probabilities(self):
        with self.assertRaises(ValueError):
            _min_conflicts_pack(
                [], [], {}, random_walk_probability=1.01
            )
        with self.assertRaises(ValueError):
            _min_conflicts_pack(
                [], [], {}, breakout_probability=-0.01
            )

    def test_exact_validator_detects_violation(self):
        component = ComponentPlacement(
            refdes="U1",
            side="TOP",
            center=(1.9, 1.0),
            width=0.5,
            height=0.5,
            region_id="top_0",
        )
        report = validate_placement([component], {"top_0": box(0, 0, 2, 2)})
        self.assertEqual(report["keepin_violation_count"], 1)
        self.assertGreater(report["keepin_violation_area"], 0)

    def test_anchor_loss_zero_at_target(self):
        sizes = torch.tensor([2.0])
        loss_op = AnchorKeepInLoss(
            node_ids=[0],
            target_centers=[[3.0, 4.0]],
            node_size_x=sizes,
            node_size_y=sizes,
            num_nodes=1,
            board_diagonal=10.0,
        )
        pos = torch.tensor([2.0, 3.0], requires_grad=True)
        self.assertEqual(loss_op(pos).item(), 0.0)

    def test_anchor_loss_gradient_direction(self):
        sizes = torch.tensor([1.0])
        loss_op = AnchorKeepInLoss(
            node_ids=[0],
            target_centers=[[0.5, 0.5]],
            node_size_x=sizes,
            node_size_y=sizes,
            num_nodes=1,
            board_diagonal=10.0,
        )
        pos = torch.tensor([1.0, 0.0], requires_grad=True)
        loss_op(pos).backward()
        self.assertGreater(pos.grad[0].item(), 0.0)
        self.assertAlmostEqual(pos.grad[1].item(), 0.0)

    def test_feature_flag_off_is_noop(self):
        pos = torch.tensor([-1.0, 3.0])
        original = pos.clone()
        projector = RegionProjector(num_nodes=1, constraints=(), enabled=False)
        self.assertEqual(projector(pos).count, 0)
        self.assertTrue(torch.equal(pos, original))

    def test_optimizer_state_reset_does_not_modify_position(self):
        pos = torch.nn.Parameter(torch.tensor([1.0, 2.0, 3.0, 4.0]))
        optimizer = torch.optim.Adam([pos], lr=0.1)
        pos.grad = torch.ones_like(pos)
        optimizer.step()
        expected = pos.detach().clone()

        zero_optimizer_state(optimizer, pos, node_ids=[1], num_nodes=2)

        self.assertTrue(torch.equal(pos.detach(), expected))
        for name in ("exp_avg", "exp_avg_sq"):
            state = optimizer.state[pos][name]
            self.assertEqual(state[1].item(), 0.0)
            self.assertEqual(state[3].item(), 0.0)
            self.assertNotEqual(state[0].item(), 0.0)
            self.assertNotEqual(state[2].item(), 0.0)


if __name__ == "__main__":
    unittest.main()
