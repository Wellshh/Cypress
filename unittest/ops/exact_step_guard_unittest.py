import unittest

import torch

from dreamplace.NesterovAcceleratedGradientOptimizer import (
    NesterovAcceleratedGradientOptimizer,
)
from dreamplace.constraints.exact_step_guard import (
    ExactAcceptedStepGuard,
    ExactStepGuardFailure,
    ExactValidationProvenance,
    OptimizerTransitionSnapshot,
    optimizer_transition_sha256,
    tensor_sha256,
)


def _threshold_validator(position, limit=0.5):
    value = float(position.detach().reshape(-1)[0].cpu().item())
    illegal = value > limit
    return {
        "keepin_violation_count": 0,
        "overlap_pair_count": int(illegal),
        "overlap_area_mm2": max(value - limit, 0.0),
        "overlap_pairs": (
            [
                {
                    "kind": "constrained_constrained",
                    "first_refdes": "A",
                    "second_refdes": "B",
                    "overlap_area_mm2": value - limit,
                }
            ]
            if illegal
            else []
        ),
    }


class ExactStepGuardTest(unittest.TestCase):
    def test_exact_provenance_skips_matching_validator_calls(self):
        devices = [torch.device("cpu")]
        if torch.cuda.is_available():
            devices.append(torch.device("cuda"))
        for device in devices:
            for dtype in (torch.float32, torch.float64):
                with self.subTest(device=device, dtype=dtype):
                    position = torch.nn.Parameter(
                        torch.tensor([0.0], dtype=dtype, device=device)
                    )
                    optimizer = torch.optim.SGD([position], lr=0.1)
                    position.grad = torch.zeros_like(position)
                    validator_calls = []

                    def validator(candidate):
                        validator_calls.append(tensor_sha256(candidate))
                        return _threshold_validator(candidate)

                    def attempt():
                        origin = position.detach().clone()
                        optimizer.step()
                        proposal = position.detach().clone()
                        report = _threshold_validator(proposal)
                        return {
                            "origin_position": origin,
                            "proposal_position": proposal,
                            "accepted_position": proposal,
                            "proposal_validation_provenance": (
                                ExactValidationProvenance.capture(
                                    proposal, report, "contact_initial"
                                )
                            ),
                            "accepted_validation_provenance": (
                                ExactValidationProvenance.capture(
                                    proposal, report, "contact_final"
                                )
                            ),
                        }

                    result = ExactAcceptedStepGuard(validator).run(
                        position, optimizer, attempt
                    )

                    self.assertEqual(len(validator_calls), 1)
                    accepted = result["attempts"][0]
                    self.assertTrue(
                        accepted["proposal_validation_cache_hit"]
                    )
                    self.assertTrue(
                        accepted["accepted_validation_cache_hit"]
                    )
                    self.assertEqual(
                        accepted["proposal_validation_source"],
                        "contact_initial",
                    )
                    self.assertEqual(
                        accepted["accepted_validation_source"],
                        "contact_final",
                    )

    def test_accepted_provenance_allows_fresh_proposal_validation(self):
        position = torch.nn.Parameter(
            torch.tensor([0.0], dtype=torch.float64)
        )
        optimizer = torch.optim.SGD([position], lr=0.2)
        position.grad = torch.tensor([-1.0], dtype=torch.float64)
        validator_calls = []

        def validator(candidate):
            validator_calls.append(float(candidate[0]))
            return _threshold_validator(candidate)

        def attempt():
            origin = position.detach().clone()
            optimizer.step()
            proposal = position.detach().clone()
            accepted = proposal.clamp(max=0.1)
            with torch.no_grad():
                position.copy_(accepted)
            return {
                "origin_position": origin,
                "proposal_position": proposal,
                "accepted_position": accepted,
                "accepted_validation_provenance": (
                    ExactValidationProvenance.capture(
                        accepted,
                        _threshold_validator(accepted),
                        "contact_final",
                    )
                ),
            }

        result = ExactAcceptedStepGuard(validator).run(
            position, optimizer, attempt
        )

        self.assertEqual(len(validator_calls), 2)
        accepted = result["attempts"][0]
        self.assertFalse(accepted["proposal_validation_cache_hit"])
        self.assertTrue(accepted["accepted_validation_cache_hit"])
        self.assertAlmostEqual(position.item(), 0.1)

    def test_stale_validation_provenance_rolls_back_transaction(self):
        mismatches = ["coordinate", "shape", "dtype", "malformed"]
        if torch.cuda.is_available():
            mismatches.append("device")
        for mismatch in mismatches:
            with self.subTest(mismatch=mismatch):
                position = torch.nn.Parameter(
                    torch.tensor([0.0], dtype=torch.float64)
                )
                optimizer = torch.optim.SGD([position], lr=0.1)
                position.grad = torch.tensor([-1.0], dtype=torch.float64)
                expected_optimizer = optimizer_transition_sha256(optimizer)

                def attempt():
                    origin = position.detach().clone()
                    optimizer.step()
                    proposal = position.detach().clone()
                    snapshot = proposal
                    if mismatch == "coordinate":
                        snapshot = proposal + 1.0
                    elif mismatch == "shape":
                        snapshot = proposal.repeat(2)
                    elif mismatch == "dtype":
                        snapshot = proposal.float()
                    elif mismatch == "device":
                        snapshot = proposal.cuda()
                    provenance = (
                        {"position": snapshot}
                        if mismatch == "malformed"
                        else ExactValidationProvenance.capture(
                            snapshot,
                            _threshold_validator(snapshot),
                            "stale",
                        )
                    )
                    return {
                        "origin_position": origin,
                        "proposal_position": proposal,
                        "accepted_position": proposal,
                        "accepted_validation_provenance": provenance,
                    }

                guard = ExactAcceptedStepGuard(_threshold_validator)
                with self.assertRaises(ExactStepGuardFailure) as caught:
                    guard.run(position, optimizer, attempt)

                self.assertEqual(caught.exception.reason, "attempt_exception")
                self.assertTrue(
                    caught.exception.attempts[0]["rollback"][
                        "position_restored"
                    ]
                )
                self.assertTrue(
                    caught.exception.attempts[0]["rollback"][
                        "optimizer_restored"
                    ]
                )
                self.assertEqual(position.item(), 0.0)
                self.assertEqual(
                    optimizer_transition_sha256(optimizer),
                    expected_optimizer,
                )

    def test_cached_illegal_retry_uses_fresh_attempt_provenance(self):
        position = torch.nn.Parameter(
            torch.tensor([0.0], dtype=torch.float64)
        )
        optimizer = torch.optim.SGD([position], lr=1.0)
        position.grad = torch.tensor([-1.0], dtype=torch.float64)
        attempt_count = 0

        def attempt():
            nonlocal attempt_count
            attempt_count += 1
            origin = position.detach().clone()
            optimizer.step()
            proposal = position.detach().clone()
            report = _threshold_validator(proposal, limit=0.5)
            source = "attempt_%d" % attempt_count
            return {
                "origin_position": origin,
                "proposal_position": proposal,
                "accepted_position": proposal,
                "proposal_validation_provenance": (
                    ExactValidationProvenance.capture(
                        proposal, report, source + "_initial"
                    )
                ),
                "accepted_validation_provenance": (
                    ExactValidationProvenance.capture(
                        proposal, report, source + "_final"
                    )
                ),
            }

        result = ExactAcceptedStepGuard(
            _threshold_validator,
            backoff=0.5,
            max_retries=1,
        ).run(position, optimizer, attempt)

        self.assertEqual(len(result["attempts"]), 2)
        self.assertFalse(result["attempts"][0]["accepted"])
        self.assertEqual(
            result["attempts"][0]["accepted_validation_source"],
            "attempt_1_final",
        )
        self.assertTrue(result["attempts"][1]["accepted"])
        self.assertEqual(
            result["attempts"][1]["accepted_validation_source"],
            "attempt_2_final",
        )
        self.assertAlmostEqual(position.item(), 0.5)

    def test_proposal_provenance_requires_accepted_pair(self):
        position = torch.nn.Parameter(
            torch.tensor([0.0], dtype=torch.float64)
        )
        optimizer = torch.optim.SGD([position], lr=0.1)
        position.grad = torch.zeros_like(position)

        def attempt():
            origin = position.detach().clone()
            optimizer.step()
            proposal = position.detach().clone()
            return {
                "origin_position": origin,
                "proposal_position": proposal,
                "accepted_position": proposal,
                "proposal_validation_provenance": (
                    ExactValidationProvenance.capture(
                        proposal,
                        _threshold_validator(proposal),
                        "incomplete",
                    )
                ),
            }

        with self.assertRaises(ExactStepGuardFailure) as caught:
            ExactAcceptedStepGuard(_threshold_validator).run(
                position, optimizer, attempt
            )

        self.assertEqual(caught.exception.reason, "attempt_exception")
        self.assertIn(
            "requires accepted provenance",
            caught.exception.attempts[0]["exception"],
        )

    def test_adam_snapshot_restores_position_gradient_and_moments(self):
        position = torch.nn.Parameter(torch.tensor([1.0], dtype=torch.float64))
        optimizer = torch.optim.Adam([position], lr=0.1)
        position.grad = torch.tensor([0.25], dtype=torch.float64)
        optimizer.step()
        position.grad = torch.tensor([-0.5], dtype=torch.float64)
        snapshot = OptimizerTransitionSnapshot(optimizer, position)
        expected_position = tensor_sha256(position)
        expected_optimizer = optimizer_transition_sha256(optimizer)

        optimizer.step()
        report = snapshot.restore(optimizer, position)

        self.assertTrue(report["position_restored"])
        self.assertTrue(report["optimizer_restored"])
        self.assertEqual(tensor_sha256(position), expected_position)
        self.assertEqual(optimizer_transition_sha256(optimizer), expected_optimizer)
        self.assertTrue(torch.equal(position.grad, torch.tensor([-0.5], dtype=torch.float64)))

    def test_custom_nesterov_snapshot_preserves_parameter_alias(self):
        position = torch.nn.Parameter(torch.tensor([1.0], dtype=torch.float64))

        def objective_and_gradient(candidate):
            if candidate.grad is not None:
                candidate.grad.zero_()
            objective = candidate.square().sum()
            objective.backward()
            return objective, candidate.grad

        optimizer = NesterovAcceleratedGradientOptimizer(
            [position],
            lr=torch.tensor(0.1, dtype=torch.float64),
            obj_and_grad_fn=objective_and_gradient,
        )
        optimizer.step()
        snapshot = OptimizerTransitionSnapshot(optimizer, position)
        expected_position = tensor_sha256(position)
        expected_optimizer = optimizer_transition_sha256(optimizer)

        optimizer.step()
        report = snapshot.restore(optimizer, position)

        self.assertTrue(report["position_restored"])
        self.assertTrue(report["optimizer_restored"])
        self.assertEqual(tensor_sha256(position), expected_position)
        self.assertEqual(optimizer_transition_sha256(optimizer), expected_optimizer)
        self.assertIs(optimizer.param_groups[0]["v_k"][0], position)
        optimizer.step()
        self.assertTrue(torch.isfinite(position).all())

    def test_crossing_step_rolls_back_and_accepts_backed_off_retry(self):
        position = torch.nn.Parameter(torch.tensor([0.0], dtype=torch.float64))
        optimizer = torch.optim.SGD([position], lr=1.0)
        position.grad = torch.tensor([-1.0], dtype=torch.float64)

        def attempt():
            origin = position.detach().clone()
            optimizer.step()
            proposal = position.detach().clone()
            return {
                "origin_position": origin,
                "proposal_position": proposal,
                "accepted_position": proposal,
            }

        guard = ExactAcceptedStepGuard(
            _threshold_validator,
            backoff=0.5,
            max_retries=4,
        )
        result = guard.run(position, optimizer, attempt)

        self.assertEqual(len(result["attempts"]), 2)
        self.assertFalse(result["attempts"][0]["accepted"])
        self.assertTrue(result["attempts"][0]["rollback"]["position_restored"])
        self.assertTrue(result["attempts"][0]["rollback"]["optimizer_restored"])
        self.assertTrue(result["attempts"][1]["accepted"])
        self.assertEqual(result["attempts"][1]["retry_index"], 1)
        self.assertAlmostEqual(position.item(), 0.5)
        self.assertAlmostEqual(optimizer.param_groups[0]["lr"], 0.5)

    def test_retry_exhaustion_restores_original_transition(self):
        position = torch.nn.Parameter(torch.tensor([0.0], dtype=torch.float64))
        optimizer = torch.optim.SGD([position], lr=1.0)
        position.grad = torch.tensor([-1.0], dtype=torch.float64)
        expected_optimizer = optimizer_transition_sha256(optimizer)

        def attempt():
            origin = position.detach().clone()
            optimizer.step()
            proposal = position.detach().clone()
            return {
                "origin_position": origin,
                "proposal_position": proposal,
                "accepted_position": proposal,
            }

        guard = ExactAcceptedStepGuard(
            lambda candidate: _threshold_validator(candidate, limit=0.1),
            backoff=0.5,
            max_retries=1,
        )
        with self.assertRaises(ExactStepGuardFailure) as caught:
            guard.run(position, optimizer, attempt)

        self.assertEqual(caught.exception.reason, "retry_exhausted")
        self.assertEqual(len(caught.exception.attempts), 2)
        self.assertAlmostEqual(position.item(), 0.0)
        self.assertEqual(optimizer_transition_sha256(optimizer), expected_optimizer)

    def test_identical_projection_and_accepted_start_reuse_exact_reports(self):
        position = torch.nn.Parameter(torch.tensor([0.0], dtype=torch.float64))
        optimizer = torch.optim.SGD([position], lr=0.1)
        position.grad = torch.zeros_like(position)
        validator_calls = []

        def validator(candidate):
            validator_calls.append(tensor_sha256(candidate))
            return _threshold_validator(candidate)

        def attempt():
            origin = position.detach().clone()
            optimizer.step()
            proposal = position.detach().clone()
            return {
                "origin_position": origin,
                "proposal_position": proposal,
                "accepted_position": proposal,
            }

        guard = ExactAcceptedStepGuard(validator)
        first = guard.run(position, optimizer, attempt)
        self.assertEqual(len(validator_calls), 2)
        self.assertNotIn(
            "proposal_validation_cache_hit", first["attempts"][0]
        )
        self.assertNotIn(
            "accepted_validation_cache_hit", first["attempts"][0]
        )

        guard.run(position, optimizer, attempt)
        self.assertEqual(len(validator_calls), 3)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_cuda_adam_snapshot_is_byte_consistent(self):
        position = torch.nn.Parameter(
            torch.tensor([1.0, -2.0], dtype=torch.float64, device="cuda")
        )
        optimizer = torch.optim.Adam([position], lr=0.1)
        position.grad = torch.tensor(
            [0.25, -0.5], dtype=torch.float64, device="cuda"
        )
        optimizer.step()
        position.grad = torch.tensor(
            [-0.75, 0.125], dtype=torch.float64, device="cuda"
        )
        snapshot = OptimizerTransitionSnapshot(optimizer, position)

        optimizer.step()
        report = snapshot.restore(optimizer, position)

        self.assertTrue(report["position_restored"])
        self.assertTrue(report["optimizer_restored"])


if __name__ == "__main__":
    unittest.main()
