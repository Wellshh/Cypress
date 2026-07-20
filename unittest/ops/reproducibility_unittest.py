import os
import random
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
import torch

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.append(REPO_ROOT)

from dreamplace.NesterovAcceleratedGradientOptimizer import (
    NesterovAcceleratedGradientOptimizer,
)
from dreamplace.NonLinearPlace import (
    _CompositeProjector,
    _NativeDisplacementTracker,
)
from dreamplace.PlaceObj import PlaceObj
from dreamplace.Placer import seed_all
from dreamplace.BasicPlace import load_initial_placement
from dreamplace.constraints.region_projection import zero_optimizer_state
from dreamplace.ops.anchor_keepin.anchor_keepin import AdaptiveAnchorWeight
from tuner.tuner_worker import AutoDMPWorker


class ReproducibilityTest(unittest.TestCase):
    def test_composite_projector_preserves_proposal_and_accepted_snapshots(self):
        def board_projector(position):
            with torch.no_grad():
                position.clamp_(max=1.0)

        projector = _CompositeProjector(board_projector, None, num_nodes=2)
        position = torch.tensor([0.0, 0.0, 0.0, 0.0])
        projector.begin_step(position)
        with torch.no_grad():
            position.copy_(torch.tensor([2.0, 0.5, 0.0, 0.0]))

        projector(position)
        evidence = projector.finish_step()

        self.assertEqual(evidence["proposal"]["max_distance"], 2.0)
        self.assertTrue(
            torch.equal(
                evidence["proposal_position"],
                torch.tensor([2.0, 0.5, 0.0, 0.0]),
            )
        )
        self.assertTrue(
            torch.equal(
                evidence["accepted_position"],
                torch.tensor([1.0, 0.5, 0.0, 0.0]),
            )
        )

    def test_native_displacement_tracker_separates_path_and_net_motion(self):
        tracker = _NativeDisplacementTracker(
            3, {"movable": (0, 1), "constrained": (1,)}
        )
        origin = torch.tensor([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        first_proposal = torch.tensor([1.0, 2.0, 0.0, 0.0, 0.0, 0.0])
        first_accepted = torch.tensor([1.0, 0.5, 0.0, 0.0, 0.0, 0.0])
        second_proposal = torch.tensor([2.0, 0.5, 0.0, 0.0, 0.0, 0.0])
        second_accepted = torch.tensor([2.0, 1.5, 0.0, 0.0, 0.0, 0.0])

        first_step = tracker.record_step(
            origin, first_proposal, first_accepted
        )
        tracker.record_step(
            first_accepted, second_proposal, second_accepted
        )
        report = tracker.summary(units_per_mm=2.0)

        self.assertEqual(
            first_step["constrained"]["proposal"]["mean_distance"], 2.0
        )
        self.assertEqual(report["step_count"], 2)
        constrained = report["groups"]["constrained"]
        self.assertEqual(constrained["proposal_path"]["mean_distance"], 2.0)
        self.assertEqual(constrained["accepted_path"]["mean_distance"], 1.5)
        self.assertEqual(constrained["net_displacement"]["mean_distance"], 1.5)
        self.assertEqual(
            constrained["net_displacement_mm"]["mean_distance"], 0.75
        )

    def test_place_objective_is_pure_for_position(self):
        model = PlaceObj.__new__(PlaceObj)
        torch.nn.Module.__init__(model)
        model.params = SimpleNamespace(
            anchor_loss_flag=False,
            keepin_soft_loss_flag=False,
            macro_overlap_flag=False,
        )
        model.placedb = SimpleNamespace(regions=[])
        model.op_collections = SimpleNamespace(
            anchor_keepin_context=SimpleNamespace(
                projector=lambda _: self.fail("objective invoked projector")
            ),
            wirelength_op=lambda position: position.square().sum(),
            two_side_density_op=lambda position: position.sum() * 0,
        )
        model.net_crossing_enabled = False
        model.init_density = torch.tensor(1.0)
        model.quad_penalty = False
        model.density_weight = torch.tensor([0.0])
        model.density_factor = 1.0
        pos = torch.tensor([0.25, -0.5, 1.0, 2.0], requires_grad=True)
        original = pos.detach().clone()

        first_objective = model.obj_fn(pos)
        first_gradient = torch.autograd.grad(first_objective, pos)[0]
        second_objective = model.obj_fn(pos)
        second_gradient = torch.autograd.grad(second_objective, pos)[0]

        self.assertTrue(torch.equal(pos.detach(), original))
        self.assertTrue(torch.equal(first_objective, second_objective))
        self.assertTrue(torch.equal(first_gradient, second_gradient))

    def test_anchor_weight_refresh_is_explicit_and_position_pure(self):
        model = PlaceObj.__new__(PlaceObj)
        torch.nn.Module.__init__(model)
        model.anchor_weight_controller = AdaptiveAnchorWeight(
            target_ratio=0.1,
            update_interval=5,
            ema_decay=0.8,
            min_weight=0.0,
            max_weight=10.0,
            warmup_iterations=0,
            ramp_iterations=0,
        )
        model.anchor_weight_updates = []
        model._anchor_last_losses = None
        model.register_buffer("anchor_loss_weight", torch.zeros(()))

        def anchor_loss(position):
            return position[0].square()

        anchor_loss.coordinate_ids = torch.tensor([0, 2])
        model.op_collections = SimpleNamespace(
            wirelength_op=lambda position: position.square().sum(),
            anchor_loss_op=anchor_loss,
        )
        pos = torch.tensor([1.0, 2.0, 3.0, 4.0], requires_grad=True)
        original = pos.detach().clone()

        diagnostics = model.update_anchor_weight(pos, iteration=0)

        self.assertTrue(torch.equal(pos.detach(), original))
        self.assertEqual(len(model.anchor_weight_updates), 1)
        self.assertAlmostEqual(diagnostics["wirelength_gradient_l1"], 8.0)
        self.assertAlmostEqual(diagnostics["anchor_gradient_l1"], 2.0)
        self.assertAlmostEqual(model.anchor_loss_weight.item(), 0.4)

    def test_anchor_objective_does_not_refresh_weight(self):
        model = PlaceObj.__new__(PlaceObj)
        torch.nn.Module.__init__(model)
        model.params = SimpleNamespace(
            anchor_loss_flag=True,
            keepin_soft_loss_flag=False,
            macro_overlap_flag=False,
        )
        model.placedb = SimpleNamespace(regions=[])
        model.op_collections = SimpleNamespace(
            wirelength_op=lambda position: position.square().sum(),
            two_side_density_op=lambda position: position.sum() * 0,
            anchor_loss_op=lambda position: position.abs().mean(),
        )
        model.net_crossing_enabled = False
        model.init_density = torch.tensor(1.0)
        model.quad_penalty = False
        model.density_weight = torch.tensor([0.0])
        model.density_factor = 1.0
        model.anchor_weight_updates = []
        model.register_buffer("anchor_loss_weight", torch.tensor(0.25))
        pos = torch.tensor([0.25, -0.5, 1.0, 2.0], requires_grad=True)

        first = model.obj_fn(pos)
        second = model.obj_fn(pos)

        self.assertTrue(torch.equal(first, second))
        self.assertEqual(model.anchor_weight_updates, [])
        self.assertEqual(model.anchor_loss_weight.item(), 0.25)

    def test_learning_rate_candidate_is_explicitly_projected(self):
        model = SimpleNamespace(
            obj_and_grad_fn=lambda position: (
                position.square().sum(),
                2 * position,
            )
        )
        position = torch.tensor([0.5, -0.5], requires_grad=True)
        original = position.detach().clone()
        projected_candidates = []

        def projector(candidate):
            with torch.no_grad():
                candidate.clamp_(-0.75, 0.75)
            projected_candidates.append(candidate.detach().clone())

        PlaceObj.estimate_initial_learning_rate(
            model, position, 10.0, constraint_fn=projector
        )

        self.assertTrue(projected_candidates)
        self.assertTrue(
            all(candidate.abs().max() <= 0.75 for candidate in projected_candidates)
        )
        self.assertTrue(torch.equal(position.detach(), original))

    def test_importing_placer_does_not_create_a_log(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                filter(
                    None,
                    [
                        os.path.join(REPO_ROOT, "install"),
                        environment.get("PYTHONPATH"),
                    ],
                )
            )
            subprocess.run(
                [sys.executable, "-c", "import dreamplace.Placer"],
                cwd=directory,
                env=environment,
                check=True,
            )
            self.assertFalse(os.path.exists(os.path.join(directory, "DREAMPlace.log")))

    def test_initial_placement_is_strict_and_preserves_float_coordinates(self):
        placedb = SimpleNamespace(
            node_names=np.array([b"A", b"B"]),
            node_orient=np.array([b"N", b"FN"]),
            num_physical_nodes=2,
            num_nodes=2,
        )
        position = np.zeros(4, dtype=np.float32)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pl") as stream:
            stream.write(
                "UCLA pl 1.0\nA 1.125 2.25 : N\nB 3.375 4.5 : FN\n"
            )
            stream.flush()
            report = load_initial_placement(stream.name, placedb, position)
        self.assertEqual(report["loaded_node_count"], 2)
        np.testing.assert_allclose(position, [1.125, 3.375, 2.25, 4.5])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pl") as stream:
            stream.write("UCLA pl 1.0\nA 1 2 : N\n")
            stream.flush()
            with self.assertRaises(ValueError):
                load_initial_placement(stream.name, placedb, position)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pl") as stream:
            stream.write("UCLA pl 1.0\nA 1 2\nB 3 4 : FN\n")
            stream.flush()
            with self.assertRaises(ValueError):
                load_initial_placement(stream.name, placedb, position)

    def test_seed_all_resets_python_numpy_and_torch(self):
        seed_all(17, deterministic=True)
        first = (random.random(), np.random.random(), torch.rand(4))
        seed_all(17, deterministic=True)
        second = (random.random(), np.random.random(), torch.rand(4))

        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])
        self.assertTrue(torch.equal(first[2], second[2]))

    def test_replicate_seed_is_worker_and_order_independent(self):
        first_worker = AutoDMPWorker.__new__(AutoDMPWorker)
        second_worker = AutoDMPWorker.__new__(AutoDMPWorker)
        first_worker.study_seed = second_worker.study_seed = 23

        forward = [first_worker._seed_for_replicate(i) for i in range(3)]
        reverse = [second_worker._seed_for_replicate(i) for i in reversed(range(3))]
        self.assertEqual(forward, list(reversed(reverse)))
        self.assertEqual(len(set(forward)), len(forward))

    def test_configspace_sampling_order_is_seeded(self):
        first = AutoDMPWorker.get_configspace("", seed=31)
        second = AutoDMPWorker.get_configspace("", seed=31)
        first_samples = [dict(first.sample_configuration()) for _ in range(5)]
        second_samples = [dict(second.sample_configuration()) for _ in range(5)]
        self.assertEqual(first_samples, second_samples)

    def test_bb_step_handles_zero_gradient_delta(self):
        delta_position = torch.ones(4, dtype=torch.float32)
        delta_gradient = torch.zeros(4, dtype=torch.float32)
        step = NesterovAcceleratedGradientOptimizer._bounded_bb_step(
            delta_position, delta_gradient, 0.25
        )
        self.assertEqual(step.item(), 0.25)
        self.assertTrue(torch.isfinite(step))

    def test_nesterov_rejects_nonfinite_candidate_without_commit(self):
        parameter = torch.nn.Parameter(torch.tensor([1.0, -1.0]))
        initial = parameter.detach().clone()
        calls = 0

        def objective_and_gradient(position):
            nonlocal calls
            calls += 1
            if calls > 2:
                return torch.tensor(float("nan")), torch.full_like(position, float("nan"))
            return position.square().sum(), 2 * position

        optimizer = NesterovAcceleratedGradientOptimizer(
            [parameter], lr=0.1, obj_and_grad_fn=objective_and_gradient,
            constraint_fn=lambda _: None,
        )
        with self.assertRaises(FloatingPointError):
            optimizer.step()
        self.assertTrue(torch.equal(parameter.detach(), initial))

    def test_nesterov_accepts_finite_quadratic_step(self):
        parameter = torch.nn.Parameter(torch.tensor([1.0, -1.0]))

        def objective_and_gradient(position):
            return position.square().sum(), 2 * position

        optimizer = NesterovAcceleratedGradientOptimizer(
            [parameter], lr=0.1, obj_and_grad_fn=objective_and_gradient,
            constraint_fn=lambda _: None,
        )
        optimizer.step()
        self.assertTrue(torch.isfinite(parameter).all())
        self.assertLess(parameter.detach().norm().item(), 2 ** 0.5)

    def test_nesterov_projects_bootstrap_before_objective(self):
        parameter = torch.nn.Parameter(torch.tensor([2.0, -2.0]))
        evaluated_positions = []

        def objective_and_gradient(position):
            evaluated_positions.append(position.detach().clone())
            return position.square().sum(), 2 * position

        def projector(position):
            with torch.no_grad():
                position.clamp_(-1.0, 1.0)

        optimizer = NesterovAcceleratedGradientOptimizer(
            [parameter],
            lr=0.1,
            obj_and_grad_fn=objective_and_gradient,
            constraint_fn=projector,
            project_initial_state=True,
        )
        optimizer.step()

        self.assertTrue(evaluated_positions)
        self.assertTrue(
            all(position.abs().max() <= 1.0 for position in evaluated_positions)
        )

    def test_nesterov_legacy_mode_keeps_bootstrap_evaluation_order(self):
        parameter = torch.nn.Parameter(torch.tensor([2.0, -2.0]))
        evaluated_positions = []

        def objective_and_gradient(position):
            evaluated_positions.append(position.detach().clone())
            return position.square().sum(), 2 * position

        def projector(position):
            with torch.no_grad():
                position.clamp_(-1.0, 1.0)

        optimizer = NesterovAcceleratedGradientOptimizer(
            [parameter],
            lr=0.1,
            obj_and_grad_fn=objective_and_gradient,
            constraint_fn=projector,
        )
        optimizer.step()

        torch.testing.assert_close(
            evaluated_positions[0], torch.tensor([2.0, -2.0])
        )

    def test_nesterov_projection_reset_synchronizes_position_history(self):
        parameter = torch.nn.Parameter(torch.tensor([1.0, 2.0, 3.0, 4.0]))

        def objective_and_gradient(position):
            return position.square().sum(), 2 * position

        optimizer = NesterovAcceleratedGradientOptimizer(
            [parameter],
            lr=0.1,
            obj_and_grad_fn=objective_and_gradient,
            constraint_fn=lambda _: None,
        )
        optimizer.step()
        with torch.no_grad():
            parameter[[1, 3]] = torch.tensor([9.0, 10.0])

        zero_optimizer_state(optimizer, parameter, node_ids=[1], num_nodes=2)

        group = optimizer.param_groups[0]
        coordinate_ids = torch.tensor([1, 3])
        for key in ("u_k", "v_k_1", "v_kp1"):
            for history in group[key]:
                self.assertTrue(
                    torch.equal(
                        history.index_select(0, coordinate_ids),
                        parameter.index_select(0, coordinate_ids),
                    )
                )
        for key in ("g_k", "g_k_1"):
            for history in group[key]:
                self.assertTrue(
                    torch.equal(
                        history.index_select(0, coordinate_ids),
                        torch.zeros(2),
                    )
                )


if __name__ == "__main__":
    unittest.main()
