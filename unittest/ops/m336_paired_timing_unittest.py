#!/usr/bin/env python3
"""Focused contract tests for M336 N7 paired runtime measurement."""

import copy
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "experiments/m336/scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_matrix import (  # noqa: E402
    CONSENSUS_PER_STEP_CONTACT_POLICY,
    DEFAULT_M336_ASSIGNMENT,
    DEFAULT_M336_CHECKPOINT_PL,
    DEFAULT_M336_LEARNING_RATE,
    EXPERIMENTS,
    N7_CONSENSUS_ARM,
    N7_FEATURE_OFF_ARM,
    N7_REPORTED_TIMING_FIELDS,
    _n7_experiment_statistics,
    _n7_require_arm_artifact_isolation,
    constraint_config,
    n7_arm_command,
    n7_arm_directory,
    n7_environment_invalid_reasons,
    n7_invalid_attempt_action,
    n7_canonical_input_identity,
    n7_metric_statistics,
    n7_pair_order,
    n7_timing_record,
    n7_update_determinism,
    placement_config,
    render_n7_report,
    validate_n7_arm_config,
    validate_n7_config_equivalence,
    validate_n7_constraint_config,
    validate_n7_frozen_arguments,
    validate_n7_provenance,
)


class M336N7PairedTimingTest(unittest.TestCase):
    def _args(self, **overrides):
        values = {
            "experiments": ["E2", "E3"],
            "seeds": [1000],
            "iterations": 50,
            "n7_physical_gpu_index": 2,
            "learning_rate_scale": 1.0,
            "anchor_gradient_ratio": 0.1,
            "collision_gradient_ratio": 0.1,
            "collision_margin_mm": 0.0,
            "collision_tau_mm": 0.025,
            "exact_step_guard_backoff": 0.5,
            "exact_step_guard_max_retries": 4,
            "exact_contact_projection_max_iterations": 8,
            "exact_contact_projection_max_nodes": 32,
            "exact_contact_projection_max_cover_component_nodes": 16,
            "grid_mm": 0.05,
            "clearance_mm": 0.0,
            "keepin_margin_mm": 0.1,
            "keepin_margin_tau_mm": 0.05,
            "site_mm": 0.05,
            "gpu": True,
            "irregular_density": True,
            "initialization_track": "checkpoint_warm_start",
            "checkpoint_placement": DEFAULT_M336_CHECKPOINT_PL,
            "assignment": DEFAULT_M336_ASSIGNMENT,
            "python": sys.executable,
            "anchor_gradient_ratio_sweep": None,
            "resume": False,
            "reevaluate": False,
            "collision_pair_diagnostics": False,
            "footprint_collision": True,
            "exact_step_guard": True,
            "exact_contact_projection": True,
            "exact_contact_policy": CONSENSUS_PER_STEP_CONTACT_POLICY,
            "exact_contact_projection_mode": "component_consensus",
            "exact_contact_topology_tiebreak": False,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _configs(self, root):
        root = Path(root)
        common = {
            "spec": EXPERIMENTS["E2"],
            "seed": 1000,
            "iterations": 50,
            "gpu": True,
            "anchor_gradient_ratio": 0.1,
            "grid_mm": 0.05,
            "clearance_mm": 0.0,
            "margin_mm": 0.1,
            "margin_tau_mm": 0.05,
            "source_placement": root / "source.pl",
            "initial_placement": DEFAULT_M336_CHECKPOINT_PL,
            "irregular_density": True,
            "initialization_track": "checkpoint_warm_start",
            "feasible_domain_cache_dir": root / "cache",
            "learning_rate_scale": 1.0,
            "collision_gradient_ratio": 0.1,
            "collision_margin_mm": 0.0,
            "collision_tau_mm": 0.025,
            "exact_step_guard_backoff": 0.5,
            "exact_step_guard_max_retries": 4,
            "collision_pair_diagnostics": False,
            "exact_contact_projection_max_iterations": 8,
            "exact_contact_projection_max_nodes": 32,
            "exact_contact_projection_max_cover_component_nodes": 16,
        }
        configs = {}
        constraints = {}
        for arm in (N7_FEATURE_OFF_ARM, N7_CONSENSUS_ARM):
            arm_dir = root / arm
            constraints[arm] = constraint_config(
                arm_dir,
                EXPERIMENTS["E2"],
                DEFAULT_M336_ASSIGNMENT,
                0.05,
                0.0,
                0.1,
                0.05,
                arm_dir / "manual.pl",
                arm_dir / "runtime.pl",
            )
            configs[arm] = placement_config(
                run_dir=arm_dir,
                constraint_path=arm_dir / "anchor_keepin.json",
                aux_input=arm_dir / "m336.aux",
                footprint_collision=(arm == N7_CONSENSUS_ARM),
                exact_step_guard=(arm == N7_CONSENSUS_ARM),
                exact_contact_projection=(arm == N7_CONSENSUS_ARM),
                exact_contact_policy=(
                    N7_CONSENSUS_ARM if arm == N7_CONSENSUS_ARM else ""
                ),
                **common,
            )
        return configs, constraints

    def test_pair_order_alternates(self):
        self.assertEqual(
            n7_pair_order(1), [N7_FEATURE_OFF_ARM, N7_CONSENSUS_ARM]
        )
        self.assertEqual(
            n7_pair_order(2), [N7_CONSENSUS_ARM, N7_FEATURE_OFF_ARM]
        )
        self.assertEqual(n7_pair_order(5), n7_pair_order(1))
        with self.assertRaises(ValueError):
            n7_pair_order(0)

    def test_warmup_path_is_excluded_from_measured_pairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            warmup = n7_arm_directory(
                root, "E2", N7_FEATURE_OFF_ARM, warmup=True
            )
            measured = n7_arm_directory(
                root,
                "E2",
                N7_FEATURE_OFF_ARM,
                pair_index=1,
                warmup=False,
            )
            self.assertIn("warmup", warmup.parts)
            self.assertNotIn("warmup", measured.parts)
            self.assertIn("pair_01", measured.parts)

    def test_config_equivalence_removes_only_authorized_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            configs, constraints = self._configs(temporary)
            result = validate_n7_config_equivalence(
                configs[N7_FEATURE_OFF_ARM],
                configs[N7_CONSENSUS_ARM],
                constraints[N7_FEATURE_OFF_ARM],
                constraints[N7_CONSENSUS_ARM],
            )
            self.assertIn("placement_config_sha256", result)
            drifted = copy.deepcopy(configs[N7_CONSENSUS_ARM])
            drifted["target_density"] = 0.84
            with self.assertRaisesRegex(RuntimeError, "target_density"):
                validate_n7_config_equivalence(
                    configs[N7_FEATURE_OFF_ARM], drifted
                )

    def test_actual_arm_configs_match_frozen_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            configs, constraints = self._configs(temporary)
            validate_n7_arm_config(
                configs[N7_FEATURE_OFF_ARM], "E2", N7_FEATURE_OFF_ARM
            )
            validate_n7_arm_config(
                configs[N7_CONSENSUS_ARM], "E2", N7_CONSENSUS_ARM
            )
            validate_n7_constraint_config(
                constraints[N7_CONSENSUS_ARM]
            )
            configs[N7_CONSENSUS_ARM]["global_place_stages"][0][
                "learning_rate"
            ] = DEFAULT_M336_LEARNING_RATE * 2
            with self.assertRaisesRegex(RuntimeError, "learning_rate"):
                validate_n7_arm_config(
                    configs[N7_CONSENSUS_ARM], "E2", N7_CONSENSUS_ARM
                )

    def test_per_pair_ratios_and_distribution_statistics(self):
        stats = n7_metric_statistics(
            [1.0] * 5,
            [1.0, 2.0, 3.0, 4.0, 5.0],
        )
        self.assertEqual(stats["ratios"], [1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(stats["median"], 3.0)
        self.assertEqual(stats["median_absolute_deviation"], 1.0)
        self.assertAlmostEqual(
            stats["geometric_mean"], math.prod(range(1, 6)) ** 0.2
        )
        self.assertFalse(stats["passes_2x"])

    def test_experiment_statistics_do_not_include_warmup(self):
        pairs = []
        for index in range(5):
            pairs.append(
                {
                    "arms": {
                        N7_FEATURE_OFF_ARM: {
                            "gpu_optimization_seconds": 2.0,
                            "end_to_end_seconds": 10.0,
                        },
                        N7_CONSENSUS_ARM: {
                            "gpu_optimization_seconds": 3.0 + index * 0.0,
                            "end_to_end_seconds": 15.0,
                        },
                    }
                }
            )
        warmup = {
            "arms": {
                N7_FEATURE_OFF_ARM: {
                    "gpu_optimization_seconds": 1000.0,
                    "end_to_end_seconds": 1000.0,
                },
                N7_CONSENSUS_ARM: {
                    "gpu_optimization_seconds": 1.0,
                    "end_to_end_seconds": 1.0,
                },
            }
        }
        self.assertNotIn(warmup, pairs)
        stats = _n7_experiment_statistics(pairs)
        self.assertEqual(stats["gpu_optimization_seconds"]["median"], 1.5)
        self.assertEqual(stats["end_to_end_seconds"]["median"], 1.5)

    def test_partial_report_preserves_structured_failure_progress(self):
        identity = {
            "input_placement_sha256": "placement",
            "replayed_placement_sha256": "placement",
            "hpwl": 1.0,
            "rsmt": 2.0,
            "normalized_quality_score": 0.5,
            "final_effective_learning_rate": 0.01,
            "anchor_distance_mm": {"mean": 3.0, "p90": 4.0},
            "legality": {
                "fully_contained_components": 100,
                "keepin_violation_count": 0,
                "overlap_pair_count": 0,
                "overlap_area_mm2": 0.0,
            },
        }
        arms = {
            N7_FEATURE_OFF_ARM: {
                "gpu_optimization_seconds": 1.0,
                "end_to_end_seconds": 2.0,
            },
            N7_CONSENSUS_ARM: {
                "gpu_optimization_seconds": 1.5,
                "end_to_end_seconds": 2.5,
                "identity": identity,
                "correctness": {
                    "guard_accepted_step_count": 50,
                    "guard_rejected_attempt_count": 1,
                    "rollback_count": 1,
                },
            },
        }
        report = render_n7_report(
            {
                "status": "running",
                "decision": "pending",
                "source_state": {"git_sha": "abc"},
                "environment": {
                    "initial_gpu": {"physical_index": 2, "uuid": "GPU-test"}
                },
                "experiments": {
                    "E2": {
                        "pairs": [
                            {
                                "pair_index": 1,
                                "order": [N7_FEATURE_OFF_ARM, N7_CONSENSUS_ARM],
                                "arms": arms,
                            }
                        ],
                        "statistics": None,
                    }
                },
                "invalid_attempts": [],
            }
        )
        self.assertIn("Distribution statistics pending", report)

    def test_run_local_paths_and_command_are_isolated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arm_dir = root / "arm"
            config = {
                "anchor_keepin_config": str(arm_dir / "constraint.json"),
                "aux_input": str(arm_dir / "m336.aux"),
                "result_dir": str(arm_dir / "run"),
            }
            _n7_require_arm_artifact_isolation(
                arm_dir,
                arm_dir / "summary.json",
                arm_dir / "REPORT.md",
                {"config": config},
            )
            args = SimpleNamespace(
                python=sys.executable,
                checkpoint_placement=DEFAULT_M336_CHECKPOINT_PL,
                feasible_domain_cache_dir=root / "cache",
                placer=REPO_ROOT / "install/dreamplace/Placer.py",
                assignment=DEFAULT_M336_ASSIGNMENT,
                baseline_geometry=REPO_ROOT / "pcb_geometry.json",
                n7_physical_gpu_index=2,
            )
            command = n7_arm_command(args, "E2", N7_FEATURE_OFF_ARM, arm_dir)
            self.assertEqual(
                command[command.index("--summary-path") + 1],
                str((arm_dir / "summary.json").resolve()),
            )
            self.assertEqual(
                command[command.index("--report-path") + 1],
                str((arm_dir / "REPORT.md").resolve()),
            )
            self.assertNotIn("--resume", command)
            self.assertNotIn("--exact-contact-policy", command)

    def test_resume_and_parameter_drift_are_rejected(self):
        validate_n7_frozen_arguments(self._args())
        validate_n7_frozen_arguments(
            self._args(
                experiments=["E2"],
                footprint_collision=False,
                exact_step_guard=False,
                exact_contact_projection=False,
                exact_contact_policy="",
            ),
            child_arm=N7_FEATURE_OFF_ARM,
        )
        with self.assertRaisesRegex(ValueError, "resume"):
            validate_n7_frozen_arguments(self._args(resume=True))
        with self.assertRaisesRegex(ValueError, "learning-rate"):
            validate_n7_frozen_arguments(
                self._args(learning_rate_scale=2.0)
            )

    def test_source_install_and_input_drift_are_rejected(self):
        source = {
            "branch": "experiment",
            "git_sha": "abc",
            "tracked_diff_sha256": "diff",
            "dirty_paths": [" M DREAMPlace.log"],
            "implementation_sha256": {"source": "hash"},
            "source_install_mismatches": [],
        }
        reference = {"source_state": source, "input_sha256": None}
        result = {
            "source_state": copy.deepcopy(source),
            "input_sha256": {"input.json": "one"},
        }
        validate_n7_provenance(reference, result)
        result["input_sha256"]["input.json"] = "two"
        with self.assertRaisesRegex(RuntimeError, "input hash drift"):
            validate_n7_provenance(reference, result)
        result["input_sha256"]["input.json"] = "one"
        result["source_state"]["source_install_mismatches"] = ["drift"]
        with self.assertRaisesRegex(RuntimeError, "source/install drift"):
            validate_n7_provenance(reference, result)

    def test_path_only_manifests_are_not_pair_inputs(self):
        canonical = n7_canonical_input_identity(
            {
                "/run/a/m336.nodes": "nodes",
                "/run/a/manifest.json": "path-a",
                "/run/a/baseline_manifest.json": "path-b",
            }
        )
        self.assertEqual(canonical, {"bookshelf/m336.nodes": "nodes"})

    def test_foreign_process_invalidates_environment(self):
        snapshot = {
            "physical_index": 2,
            "uuid": "GPU-test",
            "driver_version": "550",
            "foreign_compute_processes": [
                {"pid": 42, "process_name": "foreign"}
            ],
        }
        reasons = n7_environment_invalid_reasons(
            [snapshot], 2, "GPU-test", "550"
        )
        self.assertEqual(reasons, ["foreign_compute_process:42:foreign"])

    def test_invalid_pair_has_one_replacement(self):
        self.assertEqual(n7_invalid_attempt_action(1), "replace")
        self.assertEqual(n7_invalid_attempt_action(2), "stop_incomplete")
        with self.assertRaises(ValueError):
            n7_invalid_attempt_action(3)

    def test_timing_boundary_identity_is_preserved(self):
        timing = {field: 0.0 for field in N7_REPORTED_TIMING_FIELDS}
        timing.update(
            {
                "optimization_wall_seconds": 3.0,
                "exact_step_guard_seconds": 0.5,
                "exact_overlap_diagnostic_seconds": 0.25,
                "gpu_optimization_seconds": 2.25,
                "end_to_end_seconds": 10.0,
            }
        )
        self.assertEqual(n7_timing_record(timing)["gpu_optimization_seconds"], 2.25)
        timing["gpu_optimization_seconds"] = 2.0
        with self.assertRaisesRegex(RuntimeError, "timing-boundary"):
            n7_timing_record(timing)

    def test_deterministic_candidate_hash_aggregation(self):
        references = {}
        record = {
            "arm": N7_CONSENSUS_ARM,
            "identity": {"placement_sha256": "same", "hpwl": 1.0},
        }
        n7_update_determinism(references, "E2", record)
        n7_update_determinism(references, "E2", copy.deepcopy(record))
        record["identity"]["placement_sha256"] = "different"
        with self.assertRaisesRegex(RuntimeError, "divergence"):
            n7_update_determinism(references, "E2", record)


if __name__ == "__main__":
    unittest.main()
