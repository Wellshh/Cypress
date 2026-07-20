import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import torch
from shapely import affinity
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
    AnchorKeepInContext,
    _audit_runtime_source,
    _batch_overlap_metrics,
    _build_footprint_collision_data,
    _domain_cache_digest,
    _forward_check_rectangle_pack,
    _load_cached_domain,
    _min_conflicts_pack,
    _native_alignment_targets,
    _obstacle_free_candidate_indices,
    _ordered_candidate_indices,
    _overlap_metrics,
    _pack_region,
    _parse_endpoint_policy,
    _write_cached_domain,
)
from dreamplace.ops.anchor_keepin.anchor_keepin import (
    AdaptiveAnchorWeight,
    AnchorKeepInLoss,
    FootprintCollisionLoss,
    SoftKeepInLoss,
)


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

    def test_runtime_source_audit_allows_only_native_bookshelf_quantization(self):
        placedb = SimpleNamespace(
            num_nodes=2,
            num_physical_nodes=2,
            node_names=np.array([b"A", b"B"]),
        )
        runtime_positions = {"A": (1.5, 3.2), "B": (2.1, 4.0)}
        runtime_position = np.array([1.0, 2.0, 3.0, 4.0])

        audit = _audit_runtime_source(
            runtime_positions, runtime_position, placedb
        )

        self.assertEqual(audit["quantized_component_count"], 2)
        self.assertAlmostEqual(audit["max_abs_delta_mm"], 0.5)
        runtime_positions["A"] = (1.50001, 3.2)
        with self.assertRaisesRegex(ValueError, "quantization tolerance"):
            _audit_runtime_source(runtime_positions, runtime_position, placedb)

    def test_endpoint_policy_requires_explicit_valid_sources(self):
        valid = {
            "default": "runtime",
            "manual_endpoints": ["EMI601"],
            "runtime_endpoints": ["Q601"],
        }

        default_source, manual, runtime = _parse_endpoint_policy(
            valid, {"EMI601", "Q601"}
        )

        self.assertEqual(default_source, "runtime")
        self.assertEqual(manual, {"EMI601"})
        self.assertEqual(runtime, {"Q601"})
        for field in ("manual_endpoints", "runtime_endpoints"):
            invalid = dict(valid, **{field: []})
            with self.assertRaisesRegex(ValueError, "declare"):
                _parse_endpoint_policy(invalid, {"EMI601", "Q601"})
        with self.assertRaisesRegex(ValueError, "unique"):
            _parse_endpoint_policy(
                dict(valid, runtime_endpoints=["Q601", "Q601"]),
                {"EMI601", "Q601"},
            )
        with self.assertRaisesRegex(ValueError, "non-anchor"):
            _parse_endpoint_policy(
                dict(valid, runtime_endpoints=["UNKNOWN"]),
                {"EMI601", "Q601"},
            )

    def test_alignment_targets_use_untouched_native_placedb_snapshot(self):
        placedb = SimpleNamespace(
            num_nodes=3,
            num_physical_nodes=2,
            node_names=np.array([b"A", b"B", b"FILLER"]),
            node_size_x=np.array([2.0, 4.0, 0.0]),
            node_size_y=np.array([6.0, 8.0, 0.0]),
        )
        runtime_position = np.array(
            [10.0, 20.0, 0.0, 30.0, 40.0, 0.0]
        )

        targets = _native_alignment_targets(runtime_position, placedb)

        self.assertEqual(targets, {"A": (11.0, 33.0), "B": (22.0, 44.0)})
        with self.assertRaisesRegex(ValueError, "invalid shape"):
            _native_alignment_targets(runtime_position[:-1], placedb)

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

    @staticmethod
    def _collision_loss(device="cpu", second_side="TOP", second_shape=None):
        if second_shape is None:
            second_shape = box(-0.5, -0.5, 0.5, 0.5)
        footprints = {
            0: box(-0.5, -0.5, 0.5, 0.5),
            1: second_shape,
        }
        data, diagnostics = _build_footprint_collision_data(
            footprints=footprints,
            node_sides={0: "TOP", 1: second_side},
            active_node_ids=[0],
            num_physical_nodes=2,
            grid=0.05,
            margin=0.0,
            tau=0.025,
        )
        widths = torch.tensor(
            [shape.bounds[2] - shape.bounds[0] for shape in footprints.values()],
            dtype=torch.float64,
        )
        heights = torch.tensor(
            [shape.bounds[3] - shape.bounds[1] for shape in footprints.values()],
            dtype=torch.float64,
        )
        loss = FootprintCollisionLoss(
            node_size_x=widths,
            node_size_y=heights,
            num_nodes=2,
            **data,
        ).to(device)
        return loss, diagnostics

    def test_collision_barrier_has_separating_contact_and_overlap_gradients(self):
        loss_op, diagnostics = self._collision_loss()
        self.assertEqual(diagnostics["pair_count"], 1)
        self.assertEqual(diagnostics["pair_count_by_side"], {"TOP": 1})
        for second_x, second_y in (
            (1.0, 0.0),
            (-1.0, 0.0),
            (0.0, 1.0),
            (0.0, -1.0),
            (0.975, 0.0),
        ):
            pos = torch.tensor(
                [0.0, second_x, 0.0, second_y],
                dtype=torch.float64,
                requires_grad=True,
            )
            loss = loss_op(pos)
            loss.backward()
            self.assertTrue(torch.isfinite(loss))
            self.assertTrue(torch.isfinite(pos.grad).all())
            self.assertGreater(loss.item(), 0.0)
            descent = -torch.stack((pos.grad[1], pos.grad[3]))
            relative_center = torch.tensor(
                [second_x, second_y], dtype=torch.float64
            )
            self.assertGreater(torch.dot(descent, relative_center).item(), 0.0)

    def test_collision_field_agrees_with_exact_contact_and_penetration(self):
        loss_op, _ = self._collision_loss()
        first = box(0.0, 0.0, 1.0, 1.0)
        for second_x in (0.975, 1.0, 1.1):
            pos = torch.tensor(
                [0.0, second_x, 0.0, 0.0], dtype=torch.float64
            )
            clearance = loss_op.sampled_clearances(pos).item()
            second = box(second_x, 0.0, second_x + 1.0, 1.0)
            overlap_area = first.intersection(second).area
            if overlap_area > 1e-12:
                self.assertLessEqual(clearance, 0.0)
            elif math.isclose(second_x, 1.0):
                self.assertLessEqual(clearance, 0.0)
            else:
                self.assertGreater(clearance, 0.0)

    def test_collision_field_is_symmetric_under_component_reversal(self):
        footprints = {
            0: box(-0.5, -0.5, 0.5, 0.5),
            1: box(-1.0, -0.25, 1.0, 0.25),
        }

        def build(shapes):
            data, _ = _build_footprint_collision_data(
                footprints=shapes,
                node_sides={0: "TOP", 1: "TOP"},
                active_node_ids=[0, 1],
                num_physical_nodes=2,
                grid=0.05,
                margin=0.0,
                tau=0.025,
            )
            widths = torch.tensor(
                [shape.bounds[2] - shape.bounds[0] for shape in shapes.values()],
                dtype=torch.float64,
            )
            heights = torch.tensor(
                [shape.bounds[3] - shape.bounds[1] for shape in shapes.values()],
                dtype=torch.float64,
            )
            return FootprintCollisionLoss(
                node_size_x=widths,
                node_size_y=heights,
                num_nodes=2,
                **data,
            )

        forward = build(footprints)
        reversed_loss = build({0: footprints[1], 1: footprints[0]})
        forward_pos = torch.tensor(
            [0.0, 0.6, 0.0, 0.25], dtype=torch.float64
        )
        reversed_pos = torch.tensor(
            [0.6, 0.0, 0.25, 0.0], dtype=torch.float64
        )

        self.assertAlmostEqual(
            forward.sampled_clearances(forward_pos).item(),
            reversed_loss.sampled_clearances(reversed_pos).item(),
            places=12,
        )
        self.assertAlmostEqual(
            forward(forward_pos).item(), reversed_loss(reversed_pos).item(), places=12
        )

    def test_collision_barrier_excludes_cross_side_pairs(self):
        loss_op, diagnostics = self._collision_loss(second_side="BOTTOM")
        pos = torch.tensor(
            [0.0, 0.0, 0.0, 0.0], dtype=torch.float64, requires_grad=True
        )

        loss_op(pos).backward()

        self.assertEqual(diagnostics["pair_count"], 0)
        self.assertEqual(loss_op(pos).item(), 0.0)
        self.assertTrue(torch.equal(pos.grad, torch.zeros_like(pos)))

    def test_collision_barrier_forward_does_not_query_cpu_geometry(self):
        loss_op, _ = self._collision_loss()
        pos = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        with mock.patch(
            "shapely.intersects_xy",
            side_effect=AssertionError("forward queried CPU geometry"),
        ):
            self.assertTrue(torch.isfinite(loss_op(pos)))

    def test_collision_barrier_preserves_nonrectangular_footprint_void(self):
        frame = Polygon(
            [
                (-2.0, -2.0),
                (2.0, -2.0),
                (2.0, 2.0),
                (-2.0, 2.0),
            ],
            holes=[
                [
                    (-1.0, -1.0),
                    (-1.0, 1.0),
                    (1.0, 1.0),
                    (1.0, -1.0),
                ]
            ],
        )
        loss_op, _ = self._collision_loss(second_shape=frame)
        separated = torch.tensor(
            [-0.5, -2.0, -0.5, -2.0], dtype=torch.float64
        )
        colliding = torch.tensor(
            [-0.5, -0.5, -0.5, -2.0], dtype=torch.float64
        )

        self.assertLess(loss_op(separated).item(), loss_op(colliding).item())

    def test_concave_unequal_collision_samples_have_no_false_negative(self):
        frame = Polygon(
            [(-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0)],
            holes=[
                [(-1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (1.0, -1.0)]
            ],
        )
        loss_op, diagnostics = self._collision_loss(second_shape=frame)
        samples = (
            (0.75, 0.0),
            (1.0, 0.0),
            (1.25, 0.0),
            (2.25, 0.0),
            (0.0, 1.25),
            (1.25, 1.25),
            (2.25, 2.25),
            (-2.25, 0.0),
        )
        for center_x, center_y in samples:
            exact_area = box(-0.5, -0.5, 0.5, 0.5).intersection(
                affinity.translate(frame, xoff=center_x, yoff=center_y)
            ).area
            self.assertGreater(exact_area, 0.0)
            pos = torch.tensor(
                [-0.5, center_x - 2.0, -0.5, center_y - 2.0],
                dtype=torch.float64,
            )
            self.assertLessEqual(loss_op.sampled_clearances(pos).item(), 0.0)
        self.assertEqual(diagnostics["pair_count"], 1)

    def test_collision_pair_list_is_a_conservative_full_broadphase(self):
        footprints = {
            node_id: box(-0.5, -0.5, 0.5, 0.5) for node_id in range(4)
        }
        _, diagnostics = _build_footprint_collision_data(
            footprints=footprints,
            node_sides={0: "TOP", 1: "TOP", 2: "TOP", 3: "BOTTOM"},
            active_node_ids=[0, 1],
            num_physical_nodes=4,
            grid=0.05,
            margin=0.0,
            tau=0.025,
        )

        # Every TOP pair containing an active node is retained; no distance
        # broadphase can omit a future near-contact pair.
        self.assertEqual(diagnostics["pair_count"], 3)
        self.assertEqual(diagnostics["pair_count_by_side"], {"TOP": 3})

    def test_collision_diagnostics_report_clearance_and_active_pairs(self):
        loss_op, _ = self._collision_loss()
        pos = torch.tensor([0.0, 0.975, 0.0, 0.0], dtype=torch.float64)

        diagnostics = loss_op.diagnostics(pos)

        self.assertEqual(diagnostics["evaluated_pair_count"], 1)
        self.assertEqual(diagnostics["active_pair_count"], 1)
        self.assertEqual(diagnostics["penetrating_pair_count"], 1)
        self.assertLess(diagnostics["minimum_clearance"], 0.0)
        self.assertGreater(diagnostics["loss"], 0.0)

    def test_collision_contact_normals_match_finite_difference(self):
        loss_op, _ = self._collision_loss()
        for second_x, second_y, expected in (
            (1.0, 0.0, (1.0, 0.0)),
            (-1.0, 0.0, (-1.0, 0.0)),
            (0.0, 1.0, (0.0, 1.0)),
            (0.0, -1.0, (0.0, -1.0)),
        ):
            pos = torch.tensor(
                [0.0, second_x, 0.0, second_y], dtype=torch.float64
            )
            _, gradients, normals, valid = (
                loss_op.sampled_clearances_and_normals(pos)
            )
            self.assertTrue(valid.item())
            np.testing.assert_allclose(
                normals.numpy(), [expected], atol=1e-12, rtol=0
            )

        pos = torch.tensor([0.0, 1.075, 0.0, 0.0], dtype=torch.float64)
        _, gradients, _, _ = loss_op.sampled_clearances_and_normals(pos)
        epsilon = 1e-6
        offset = torch.tensor([0.0, epsilon, 0.0, 0.0], dtype=pos.dtype)
        finite_difference = (
            loss_op.sampled_clearances(pos + offset)
            - loss_op.sampled_clearances(pos - offset)
        ) / (2 * epsilon)
        self.assertAlmostEqual(
            gradients[0, 0].item(), finite_difference.item(), places=7
        )

    def test_pairwise_diagnostics_measure_local_gradient_and_proposal_drive(self):
        loss_op, _ = self._collision_loss()
        pos = torch.tensor([0.0, 1.0, 0.0, 0.0], dtype=torch.float64)
        base_gradient = torch.tensor([-1.0, 0.0, 0.0, 0.0], dtype=pos.dtype)
        collision_gradient = -base_gradient
        proposal = torch.tensor([0.01, 1.0, 0.0, 0.0], dtype=pos.dtype)
        accepted = torch.tensor([-0.01, 1.0, 0.0, 0.0], dtype=pos.dtype)

        diagnostics = loss_op.pairwise_diagnostics(
            pos,
            base_raw_gradient=base_gradient,
            collision_raw_gradient=collision_gradient,
            total_raw_gradient=base_gradient + collision_gradient,
            optimizer_gradient=base_gradient,
            proposal=proposal,
            accepted=accepted,
        )

        self.assertEqual(diagnostics["pair_indices"].tolist(), [0])
        self.assertEqual(diagnostics["first_active"].tolist(), [True])
        self.assertEqual(diagnostics["second_active"].tolist(), [False])
        self.assertLess(diagnostics["base_raw_normal_descent"].item(), 0.0)
        self.assertGreater(
            diagnostics["collision_raw_normal_descent"].item(), 0.0
        )
        self.assertLess(
            diagnostics["proposal_normal_displacement"].item(), 0.0
        )
        np.testing.assert_allclose(
            diagnostics["proposal_relative_displacement"].numpy(),
            [[-0.01, 0.0]],
            atol=1e-12,
            rtol=0,
        )
        self.assertLess(
            diagnostics["proposal_clearances"].item(),
            diagnostics["clearances"].item(),
        )
        self.assertTrue(diagnostics["proposal_normal_valid"].item())
        self.assertGreater(
            diagnostics["accepted_normal_displacement"].item(), 0.0
        )
        self.assertGreater(
            diagnostics["accepted_clearances"].item(),
            diagnostics["clearances"].item(),
        )

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_collision_barrier_cpu_gpu_consistency(self):
        cpu_loss, _ = self._collision_loss()
        gpu_loss, _ = self._collision_loss(device="cuda")
        cpu_pos = torch.tensor(
            [0.0, 0.975, 0.0, 0.0], dtype=torch.float64, requires_grad=True
        )
        gpu_pos = cpu_pos.detach().clone().cuda().requires_grad_(True)

        cpu_value = cpu_loss(cpu_pos)
        gpu_value = gpu_loss(gpu_pos)
        cpu_value.backward()
        gpu_value.backward()

        self.assertAlmostEqual(cpu_value.item(), gpu_value.item(), places=10)
        np.testing.assert_allclose(
            cpu_pos.grad.numpy(), gpu_pos.grad.cpu().numpy(), atol=1e-10, rtol=1e-10
        )
        cpu_field = cpu_loss.sampled_clearances_and_normals(cpu_pos)
        gpu_field = gpu_loss.sampled_clearances_and_normals(gpu_pos)
        for cpu_value, gpu_value in zip(cpu_field, gpu_field):
            self.assertTrue(torch.equal(cpu_value, gpu_value.cpu()))

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_collision_barrier_cuda_repeat_is_byte_identical(self):
        loss_op, _ = self._collision_loss(device="cuda")

        def evaluate():
            pos = torch.tensor(
                [0.0, 0.975, 0.0, 0.0],
                dtype=torch.float64,
                device="cuda",
                requires_grad=True,
            )
            value = loss_op(pos)
            value.backward()
            return value.detach().clone(), pos.grad.detach().clone()

        first_value, first_gradient = evaluate()
        second_value, second_gradient = evaluate()

        self.assertTrue(torch.equal(first_value, second_value))
        self.assertTrue(torch.equal(first_gradient, second_gradient))

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

    @staticmethod
    def _initialization_context(output_dir, positions_overlap=False):
        region = box(0.0, 0.0, 4.0, 1.0)
        domain = FeasibleDomain.build(
            region, width=1.0, height=1.0, grid=0.5
        )
        constraints = tuple(
            NodeConstraint(
                node_id=node_id,
                refdes="U%d" % (node_id + 1),
                side="TOP",
                group_id="G",
                subgroup_id="G__top",
                region_id="top_0",
                domain=domain,
                target_center=(node_id + 0.5, 0.5),
                node_width=1.0,
                node_height=1.0,
                anchor_refdes="A1",
            )
            for node_id in range(3)
        )
        context = AnchorKeepInContext(
            config={"reporting": {"area_epsilon_mm2": 1e-9}},
            geometry=SimpleNamespace(symbols={}),
            alignment=SimpleNamespace(scale=1.0),
            regions={"top_0": region},
            constraints=constraints,
            frozen_lower_left={},
            frozen_anchor_ids=set(),
            frozen_fixed_ids=set(),
            anchor_centers={"A1": (0.5, 0.5)},
            resolved_members=("U1", "U2", "U3"),
            input_paths={},
            endpoint_policy={"default": "runtime"},
            endpoint_records=(),
            domain_cache_stats={},
            preprocessing_seconds=0.0,
            num_nodes=4,
            output_dir=output_dir,
            projection_enabled=True,
            anchor_loss_enabled=False,
            soft_loss_enabled=False,
            exact_repair_enabled=False,
            initialization_mode="preserve_legal",
            grid=0.5,
            keepin_margin=0.0,
            keepin_margin_tau=0.1,
        )
        placedb = SimpleNamespace(
            num_nodes=4,
            num_physical_nodes=4,
            node_names=np.asarray([b"U1", b"U2", b"U3", b"FIX"]),
            node_side_flag=np.ones(4, dtype=np.int32),
            node_size_x=np.ones(4),
            node_size_y=np.ones(4),
        )
        x_positions = [0.0, 0.0 if positions_overlap else 1.0, 2.0, 10.0]
        position = np.asarray(x_positions + [0.0] * 4, dtype=np.float64)
        return context, placedb, position

    def test_preserve_legal_initialization_is_coordinate_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            context, placedb, position = self._initialization_context(
                directory
            )
            expected = position.copy()

            context.initialize_positions(position, placedb)

            np.testing.assert_array_equal(position, expected)
            report = json.loads(
                (Path(directory) / "initialization.json").read_text()
            )
            self.assertEqual(report["preserved_component_count"], 3)
            self.assertEqual(report["repair"]["component_count"], 0)

    def test_anchor_feasible_lower_bound_is_optimistic_and_serialized(self):
        with tempfile.TemporaryDirectory() as directory:
            context, placedb, position = self._initialization_context(directory)
            context.anchor_centers["A1"] = (-1.0, 0.5)

            report = context.exact_report(
                torch.as_tensor(position), placedb
            )

        lower_bound = report["anchor_feasible_lower_bound"]
        self.assertEqual(
            lower_bound["model"]["name"],
            "footprint_vertex_necessary_center_domain",
        )
        self.assertTrue(lower_bound["model"]["optimistic"])
        self.assertEqual(lower_bound["distance_mm"]["count"], 3)
        self.assertAlmostEqual(lower_bound["distance_mm"]["mean"], 1.5)
        self.assertAlmostEqual(
            lower_bound["current_distance_above_lower_bound_mm"]["mean"],
            1.0,
        )
        self.assertEqual(
            [row["refdes"] for row in lower_bound["per_component"]],
            ["U1", "U2", "U3"],
        )
        self.assertTrue(
            all(
                row["lower_bound"] <= row["current_anchor_distance"]
                for row in lower_bound["per_component"]
            )
        )

    def test_exact_overlap_report_uses_exact_constrained_and_fixed_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            context, placedb, position = self._initialization_context(
                directory, positions_overlap=True
            )
            position[3] = 2.5

            report = context.exact_overlap_report(
                torch.as_tensor(position), placedb
            )

        self.assertEqual(report["keepin_violation_count"], 0)
        self.assertEqual(report["constrained_overlap_count"], 1)
        self.assertAlmostEqual(report["constrained_overlap_area_mm2"], 1.0)
        self.assertEqual(report["fixed_overlap_count"], 1)
        self.assertAlmostEqual(report["fixed_overlap_area_mm2"], 0.5)
        self.assertEqual(report["overlap_pair_count"], 2)
        self.assertAlmostEqual(report["overlap_area_mm2"], 1.5)
        self.assertEqual(report["conflict_closure_count"], 3)

    def test_preserve_legal_repairs_only_overlap_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            context, placedb, position = self._initialization_context(
                directory, positions_overlap=True
            )
            third_before = position[2]

            context.initialize_positions(position, placedb)

            report = json.loads(
                (Path(directory) / "initialization.json").read_text()
            )
            self.assertEqual(report["before"]["conflict_closure_count"], 2)
            self.assertEqual(report["repair"]["component_count"], 2)
            self.assertEqual(report["preserved_component_count"], 1)
            self.assertEqual(position[2], third_before)
            self.assertEqual(report["after"]["constrained_overlap_count"], 0)

    def test_e4_repair_restores_only_same_run_conflict_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            context, placedb, initial = self._initialization_context(directory)
            context.initialize_positions(initial, placedb)
            expected = torch.as_tensor(initial.copy())
            proposal = expected.clone()
            proposal[0] = 0.2

            stats = context.repair_positions(proposal, placedb)

            self.assertEqual(stats["strategy"], "initial_legal_restore")
            self.assertEqual(stats["component_count"], 2)
            self.assertEqual(stats["moved_component_count"], 1)
            self.assertTrue(torch.equal(proposal, expected))
            self.assertEqual(stats["after"]["conflict_closure_count"], 0)

    def test_e4_repair_expands_restore_closure_until_legal(self):
        with tempfile.TemporaryDirectory() as directory:
            context, placedb, initial = self._initialization_context(directory)
            context.initialize_positions(initial, placedb)
            proposal = torch.as_tensor(initial.copy())
            proposal[:3] = torch.as_tensor([0.2, 0.8, 1.9])

            stats = context.repair_positions(proposal, placedb)

            self.assertEqual(stats["strategy"], "initial_legal_restore")
            self.assertEqual(stats["initial_component_count"], 2)
            self.assertEqual(stats["expanded_component_count"], 3)
            self.assertEqual(stats["restore_round_count"], 2)
            self.assertEqual(stats["expansions"][0]["added_refdes"], ["U3"])
            self.assertEqual(stats["after"]["conflict_closure_count"], 0)
            np.testing.assert_array_equal(proposal.numpy(), initial)

    def test_e4_restore_respects_component_limit_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            context, placedb, initial = self._initialization_context(directory)
            context.initialize_positions(initial, placedb)
            context.config["repair"] = {
                "max_restore_components": 2,
                "max_restore_rounds": 4,
            }
            proposal = torch.as_tensor(initial.copy())
            proposal[:3] = torch.as_tensor([0.2, 0.8, 1.9])
            expected = proposal.clone()

            stats, failure = context._restore_initial_legal_subset(
                proposal, placedb, {0, 1}
            )

            self.assertIsNone(stats)
            self.assertEqual(failure["reason"], "restore_component_limit")
            self.assertEqual(failure["proposed_component_count"], 3)
            self.assertTrue(torch.equal(proposal, expected))

    def test_feasible_domain_cache_round_trip_is_identity_safe(self):
        region = box(0.0, 0.0, 2.0, 2.0)
        footprint = box(-0.25, -0.25, 0.25, 0.25)
        domain = FeasibleDomain.build(
            region,
            width=0.5,
            height=0.5,
            grid=0.1,
            footprint_local=footprint,
        )
        digest = _domain_cache_digest(
            input_hashes={"geometry": "abc"},
            endpoint_policy={"default": "runtime"},
            side="TOP",
            region_id="top_0",
            region=region,
            width=0.5,
            height=0.5,
            grid=0.1,
            clearance=0.0,
            orientation="N",
            footprint_local=footprint,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (digest + ".npz")
            _write_cached_domain(path, digest, domain)
            loaded = _load_cached_domain(
                path,
                digest,
                region,
                0.5,
                0.5,
                0.0,
                0.1,
                footprint,
            )

        np.testing.assert_array_equal(loaded.valid_mask, domain.valid_mask)
        np.testing.assert_allclose(loaded.valid_centers, domain.valid_centers)
        self.assertEqual(loaded.project((3.0, 3.0)), domain.project((3.0, 3.0)))

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

    def test_anchor_loss_retains_length_scale_after_normalization(self):
        sizes = torch.zeros(1)
        loss_op = AnchorKeepInLoss(
            node_ids=[0],
            target_centers=[[0.0, 0.0]],
            node_size_x=sizes,
            node_size_y=sizes,
            num_nodes=1,
            board_diagonal=10.0,
        )

        loss = loss_op(torch.tensor([1.0, 0.0]))

        self.assertAlmostEqual(loss.item(), 0.05)

    def test_anchor_loss_balances_side_specific_subgroups(self):
        sizes = torch.zeros(4)
        pos = torch.tensor([1.0, 0.0, 0.0, 0.0] + [0.0] * 4)
        loss_op = AnchorKeepInLoss(
            node_ids=[0, 1, 2, 3],
            target_centers=[[0.0, 0.0]] * 4,
            node_size_x=sizes,
            node_size_y=sizes,
            num_nodes=4,
            board_diagonal=1.0,
            group_ids=[
                "small__top",
                "large__bottom",
                "large__bottom",
                "large__bottom",
            ],
        )

        self.assertAlmostEqual(loss_op(pos).item(), 0.25)
        self.assertEqual(loss_op.group_labels, ("small__top", "large__bottom"))
        self.assertTrue(
            torch.equal(
                loss_op.coordinate_ids,
                torch.tensor([0, 1, 2, 3, 4, 5, 6, 7]),
            )
        )

    def test_anchor_loss_normalizes_member_weights_within_each_subgroup(self):
        sizes = torch.zeros(3)
        loss_op = AnchorKeepInLoss(
            node_ids=[0, 1, 2],
            target_centers=[[0.0, 0.0]] * 3,
            node_size_x=sizes,
            node_size_y=sizes,
            num_nodes=3,
            board_diagonal=1.0,
            group_ids=["first__top", "second__bottom", "second__bottom"],
            weights=[1.0, 1.0, 3.0],
        )
        pos = torch.tensor([1.0, 1.0, 0.0] + [0.0] * 3)

        self.assertAlmostEqual(loss_op(pos).item(), 0.3125)

    def test_context_excludes_frozen_and_fixed_anchor_coordinates(self):
        domain = FeasibleDomain.build(box(0, 0, 2, 2), 0.5, 0.5, 0.1)
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
                node_width=0.5,
                node_height=0.5,
            )
            for node_id in range(3)
        ]
        context = object.__new__(AnchorKeepInContext)
        context.constraints = constraints
        context.frozen_lower_left = {1: (0.0, 0.0)}
        data_collections = SimpleNamespace(
            node_size_x=torch.full((3,), 0.5),
            node_size_y=torch.full((3,), 0.5),
            pos=[torch.zeros(6)],
        )
        placedb = SimpleNamespace(
            num_movable_nodes=2,
            num_nodes=3,
            xl=0.0,
            yl=0.0,
            xh=2.0,
            yh=2.0,
        )

        loss_op = context.build_anchor_loss(data_collections, placedb)

        self.assertTrue(torch.equal(loss_op.node_ids, torch.tensor([0])))
        self.assertTrue(torch.equal(loss_op.coordinate_ids, torch.tensor([0, 3])))

    def test_adaptive_anchor_weight_is_ramped_bounded_and_smoothed(self):
        controller = AdaptiveAnchorWeight(
            target_ratio=0.1,
            update_interval=2,
            ema_decay=0.5,
            min_weight=0.0,
            max_weight=10.0,
            warmup_iterations=1,
            ramp_iterations=2,
        )

        first = controller.step(0, 100.0, 1.0)
        ramped = controller.step(1)
        refreshed = controller.step(2, 10.0, 10.0)

        self.assertTrue(first["gradient_refreshed"])
        self.assertEqual(first["raw_weight"], 10.0)
        self.assertEqual(first["effective_weight"], 0.0)
        self.assertFalse(ramped["gradient_refreshed"])
        self.assertEqual(ramped["effective_weight"], 5.0)
        self.assertEqual(refreshed["bounded_weight"], 0.1)
        self.assertEqual(refreshed["ema_weight"], 5.05)
        self.assertEqual(refreshed["controlled_weight"], 0.1)
        self.assertEqual(refreshed["effective_weight"], 0.1)
        self.assertAlmostEqual(refreshed["effective_ratio"], 0.1)
        self.assertLessEqual(refreshed["effective_weight"], 10.0)

    def test_adaptive_anchor_weight_rejects_nonfinite_configuration(self):
        with self.assertRaisesRegex(ValueError, "must be finite"):
            AdaptiveAnchorWeight(
                target_ratio=float("nan"),
                update_interval=1,
                ema_decay=0.5,
                min_weight=0.0,
                max_weight=10.0,
                warmup_iterations=0,
                ramp_iterations=1,
            )

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
