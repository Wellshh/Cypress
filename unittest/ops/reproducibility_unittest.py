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
from dreamplace.Placer import seed_all
from dreamplace.BasicPlace import load_initial_placement
from tuner.tuner_worker import AutoDMPWorker


class ReproducibilityTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
