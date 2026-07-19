import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "experiments" / "m336" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from prepare_baseline import (  # noqa: E402
    BaselineCompatibilityError,
    direct_hpwl_mm,
    prepare_baseline,
    validate_bookshelf_pin_alignment,
    validate_compatibility,
)
from analyze_quality_bound import (  # noqa: E402
    _bound_for_ranges,
    _override_manual_baseline_endpoints,
    _runtime_fixed_positions,
    _select_fixed_endpoints,
    minimum_interval_span,
)
from finalize_assignment import packing_exclusion_reason  # noqa: E402
from optimize_assignment import (  # noqa: E402
    _candidate_domains,
    solve_interval_assignment,
)
from solve_discrete_placement import (  # noqa: E402
    _assumption_core_refdes,
    _candidate_indices_without_obstacle_overlap,
    _capacity_integer_bounds,
    _capacity_units_with_hint_floor,
    _coordinate_choice_index,
    _convex_parts,
    _exact_site_index,
    _fixed_hint_candidate_indices,
    _guide_site_indices,
    _hpwl_rounding_allowance_units,
    _hinted_group_regions,
    _horizontal_inner_rectangles,
    _hpwl_model_configuration,
    _inactive_controlled_collision_pairs,
    _nearest_site_index,
    _limited_candidate_indices,
    _normalize_controlled_collision_pairs,
    _override_fixed_endpoint_coordinates,
    _partial_fix_refdes,
    _quantized_rectangle_intervals,
    _quantized_swept_bbox,
    _rectangle_interval_overlap_area_bound,
    _selected_assignment_data,
    _score_hpwl_limit,
    _scaled_inner_rectangles,
    _scoped_assignment_space,
    _side_legality_report,
    _site_hint_parts,
    _swept_bboxes_may_overlap,
)
from analyze_shared_box_bound import solve_shared_box_assignment  # noqa: E402
from greedy_exact_site_descent import (  # noqa: E402
    _best_pair_move,
    _candidate_total_hpwl,
    _escape_hold_refdes,
    _escape_sweep_order,
    _pair_total_hpwl,
    _select_candidate,
    _select_guided_threshold_candidate,
)
from probe_exact_site_cpsat import (  # noqa: E402
    _candidate_coordinate_mismatches,
    _candidate_guide_support_audit,
    _candidate_guide_weights,
    _context_output_dir,
    _effective_integer_hpwl_limit,
    _guide_rank_replay_audit,
    _guide_delta_refdes_order,
    _integer_hpwl_by_net,
    _objective_replay_audit,
    _optional_nonnegative_integer,
    _packing_sides,
    _rows_by_side,
    _required_guide_support_indices,
    _search_branching_mode,
    _selected_site_in_region,
    _set_model_objective,
    _solver_integer_hpwl_by_net,
    _weighted_candidate_order,
)
from score_exact_site_result import (  # noqa: E402
    _manual_baseline_endpoints,
    _require_objective_replay_audit,
)
from dreamplace.constraints.region_projection import (  # noqa: E402
    FeasibleDomain,
    NodeConstraint,
)


def make_symbol(refdes, center, side, pin_delta):
    cx, cy = center
    suffix = side.upper()
    return {
        "refdes": refdes,
        "name": "PKG",
        "type": "PACKAGE",
        "layer": suffix,
        "xy": [cx, cy],
        "rotation": 0.0,
        "is_mirrored": suffix == "BOTTOM",
        "b_box": [cx - 20000, cy - 20000, cx + 20000, cy + 20000],
        "component": {"package": "PKG", "device_type": "DEVICE"},
        "children": [
            {
                "obj_type": "shape",
                "layer": "PACKAGE GEOMETRY/PLACE_BOUND_%s" % suffix,
                "b_box": [cx - 20000, cy - 20000, cx + 20000, cy + 20000],
                "vertices": [
                    [[cx - 20000, cy - 20000], 0],
                    [[cx + 20000, cy - 20000], 0],
                    [[cx + 20000, cy + 20000], 0],
                    [[cx - 20000, cy + 20000], 0],
                ],
                "voids": [],
            }
        ],
        "pins": [
            {
                "number": "1",
                "name": "P1",
                "net": "N1",
                "xy": [cx + pin_delta[0], cy + pin_delta[1]],
                "rel_xy": list(pin_delta),
                "rel_rotation": 0.0,
                "start_end": None,
                "is_through": False,
            }
        ],
    }


def make_geometry(top_center=(0, 0), bottom_center=(100000, 0)):
    return {
        "export_meta": {"dbu_per_user_unit": 10000},
        "symbols": [
            make_symbol("T1", top_center, "TOP", (10000, 20000)),
            make_symbol("B1", bottom_center, "BOTTOM", (-10000, 20000)),
        ],
        "nets": [{"name": "N1"}],
    }


class M336BaselineTest(unittest.TestCase):
    def test_manual_endpoint_metadata_supports_legacy_model_field(self):
        self.assertEqual(
            _manual_baseline_endpoints(
                {
                    "model": {
                        "manual_baseline_endpoint_overrides": ["EMI601"]
                    }
                }
            ),
            ["EMI601"],
        )
        self.assertEqual(
            _manual_baseline_endpoints(
                {
                    "manual_baseline_endpoints": ["EMI601"],
                    "model": {
                        "manual_baseline_endpoint_overrides": ["EMI601"]
                    },
                }
            ),
            ["EMI601"],
        )
        with self.assertRaisesRegex(ValueError, "metadata is inconsistent"):
            _manual_baseline_endpoints(
                {
                    "manual_baseline_endpoints": ["EMI601"],
                    "model": {
                        "manual_baseline_endpoint_overrides": ["J201"]
                    },
                }
            )

    def test_scorer_requires_hpwl_feasibility_audit(self):
        with self.assertRaisesRegex(ValueError, "objective replay audit"):
            _require_objective_replay_audit(
                {"objective_mode": "hpwl_feasibility"}
            )
        with self.assertRaisesRegex(ValueError, "objective replay audit"):
            _require_objective_replay_audit(
                {
                    "objective_mode": "hpwl_feasibility",
                    "objective_replay_audit": {"passed": False},
                }
            )
        _require_objective_replay_audit(
            {
                "objective_mode": "hpwl_feasibility",
                "objective_replay_audit": {"passed": True},
            }
        )

    def test_effective_integer_hpwl_limit_uses_strictest_bound(self):
        self.assertEqual(
            _effective_integer_hpwl_limit(12.25, 100, 3, None), 1228
        )
        self.assertEqual(
            _effective_integer_hpwl_limit(None, 100, 3, 1200), 1200
        )
        self.assertEqual(
            _effective_integer_hpwl_limit(12.25, 100, 3, 1200), 1200
        )
        self.assertIsNone(
            _effective_integer_hpwl_limit(None, 100, 3, None)
        )
        with self.assertRaisesRegex(ValueError, "ceiling must be positive"):
            _effective_integer_hpwl_limit(None, 100, 3, 0)

    def test_zero_minimum_score_disables_only_the_hpwl_gate(self):
        self.assertEqual(
            _hpwl_model_configuration(0.0, True, True), (True, False)
        )
        self.assertEqual(
            _hpwl_model_configuration(0.0, False, True), (False, False)
        )
        self.assertEqual(
            _hpwl_model_configuration(1.0, False, True), (True, True)
        )
        self.assertEqual(
            _hpwl_model_configuration(1.0, True, False), (False, False)
        )
        self.assertEqual(
            _hpwl_model_configuration(0.0, False, True, 100),
            (True, False),
        )
        with self.assertRaisesRegex(ValueError, "non-negative"):
            _hpwl_model_configuration(-1.0, True, True)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            _hpwl_model_configuration(float("nan"), True, True)
        with self.assertRaisesRegex(ValueError, "positive"):
            _score_hpwl_limit(10.0, 11.0, 0.0)
        with self.assertRaisesRegex(ValueError, "ceiling must be positive"):
            _hpwl_model_configuration(0.0, False, True, 0)

    def test_rectangle_intervals_quantize_complete_bounds_once(self):
        starts, width, height = _quantized_rectangle_intervals(
            np.asarray([[625.9327706224885, 195.97895054633835]]),
            (
                -3.4996241168988718,
                -6.49930193138357,
                3.4996241168989854,
                6.499301931383798,
            ),
            1_000_000,
            1,
        )
        self.assertEqual(starts.tolist(), [[622433148, 189479650]])
        self.assertEqual((width, height), (6999246, 12998602))
        self.assertEqual(
            _quantized_swept_bbox(
                np.asarray([[625.9327706224885, 195.97895054633835]]),
                (
                    -3.4996241168988718,
                    -6.49930193138357,
                    3.4996241168989854,
                    6.499301931383798,
                ),
                1_000_000,
            ),
            (622433146, 189479648, 629432395, 202478253),
        )
        self.assertLess(
            _rectangle_interval_overlap_area_bound(321.0, 1_000_000, 1),
            0.003999,
        )
        with self.assertRaisesRegex(ValueError, "inset non-negative"):
            _quantized_rectangle_intervals(
                np.asarray([[0.0, 0.0]]), (0.0, 0.0, 1.0, 1.0), 1, -1
            )

    def test_candidate_guide_weights_are_explicit_and_strict(self):
        self.assertEqual(_candidate_guide_weights("", 3), (1, 1, 1))
        self.assertEqual(_candidate_guide_weights("1,7", 2), (1, 7))
        with self.assertRaisesRegex(ValueError, "weight count"):
            _candidate_guide_weights("1", 2)
        with self.assertRaisesRegex(ValueError, "must be integers"):
            _candidate_guide_weights("1,x", 2)
        with self.assertRaisesRegex(ValueError, "positive integers"):
            _candidate_guide_weights("1,0", 2)

    def test_candidate_guide_support_is_audited_and_gated(self):
        source = {"A": [0.0, 0.0], "B": [1.0, 0.0], "C": [2.0, 0.0]}
        guides = [
            {"A": [1.0, 0.0], "B": [1.0, 0.0], "C": [2.0, 0.0]},
            {"A": [0.0, 0.0], "B": [1.0, 1.0], "C": [2.0, 1.0]},
        ]
        audit = _candidate_guide_support_audit(
            source,
            "source.json",
            guides,
            ["first.json", "second.json"],
            ["A", "B", "C"],
            ["A", "B"],
            True,
            (0,),
        )
        self.assertTrue(audit["all_required_guides_supported"])
        self.assertTrue(audit["guides"][0]["support_complete"])
        self.assertEqual(
            audit["guides"][1]["outside_movable_refdes"], ["C"]
        )
        self.assertFalse(audit["guides"][1]["support_complete"])
        self.assertFalse(
            _candidate_guide_support_audit(
                source,
                "source.json",
                guides,
                ["first.json", "second.json"],
                ["A", "B", "C"],
                ["A", "B"],
                True,
                (1,),
            )["all_required_guides_supported"]
        )
        self.assertEqual(audit["fixed_reference_json"], "source.json")
        self.assertTrue(
            _candidate_guide_support_audit(
                guides[0],
                "first.json",
                guides,
                ["first.json", "second.json"],
                ["A", "B", "C"],
                [],
                True,
                (0,),
            )["all_required_guides_supported"]
        )

    def test_required_guide_support_indices_are_strict(self):
        self.assertEqual(_required_guide_support_indices("", 2), ())
        self.assertEqual(_required_guide_support_indices("1,0", 2), (0, 1))
        with self.assertRaisesRegex(ValueError, "must be integers"):
            _required_guide_support_indices("x", 2)
        with self.assertRaisesRegex(ValueError, "outside the guide range"):
            _required_guide_support_indices("2", 2)
        with self.assertRaisesRegex(ValueError, "must be unique"):
            _required_guide_support_indices("1,1", 2)

    def test_guide_delta_order_is_descending_and_stable(self):
        order, distances = _guide_delta_refdes_order(
            ["C", "A", "B"],
            {"A": [0.0, 1.0], "B": [2.0, 0.0], "C": [0.0, -1.0]},
            {"A": [0.0, 0.0], "B": [0.0, 0.0], "C": [0.0, 0.0]},
        )
        self.assertEqual(order, ("B", "A", "C"))
        self.assertEqual(distances, {"A": 1.0, "B": 2.0, "C": 1.0})
        with self.assertRaisesRegex(ValueError, "missing component"):
            _guide_delta_refdes_order(
                ["A", "B"], {"A": [0.0, 0.0]}, {"A": [0.0, 0.0]}
            )

    def test_search_branching_mode_is_explicit(self):
        for mode in (
            "automatic",
            "fixed_guide_delta",
            "partial_fixed_guide_delta",
        ):
            self.assertEqual(_search_branching_mode(mode), mode)
        with self.assertRaisesRegex(ValueError, "search branching"):
            _search_branching_mode("fixed")

    def test_exact_site_context_directory_is_isolated_by_output(self):
        first = _context_output_dir(Path("/tmp/first.json"), "")
        second = _context_output_dir(Path("/tmp/second.json"), "")
        self.assertEqual(first, Path("/tmp/first.json.context"))
        self.assertEqual(second, Path("/tmp/second.json.context"))
        self.assertNotEqual(first, second)
        self.assertEqual(
            _context_output_dir(Path("/tmp/result.json"), "custom/context"),
            Path("custom/context"),
        )

    def test_optional_nonnegative_integer_is_strict(self):
        self.assertIsNone(_optional_nonnegative_integer("", "limit"))
        self.assertEqual(_optional_nonnegative_integer("0", "limit"), 0)
        self.assertEqual(_optional_nonnegative_integer("17", "limit"), 17)
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            _optional_nonnegative_integer("x", "limit")
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            _optional_nonnegative_integer("-1", "limit")
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            _optional_nonnegative_integer("01", "limit")

    def test_guide_rank_replay_checks_objective_and_ceiling(self):
        solver = SimpleNamespace(value=lambda variable: variable)
        rows = [{"site_var": 2}, {"site_var": 3}]
        audit = _guide_rank_replay_audit(
            solver, rows, "guide_rank", 5.0, 5
        )
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["selected_guide_rank"], 5)
        self.assertTrue(
            audit["solver_objective_matches_selected_guide_rank"]
        )

        self.assertFalse(
            _guide_rank_replay_audit(
                solver, rows, "guide_rank", 4.0, None
            )["passed"]
        )
        hpwl_audit = _guide_rank_replay_audit(
            solver, rows, "hpwl", 123.0, 4
        )
        self.assertFalse(hpwl_audit["passed"])
        self.assertFalse(hpwl_audit["response_objective_available"])

    def test_guide_rank_objective_survives_hpwl_model_construction(self):
        minimized = []
        model = SimpleNamespace(minimize=minimized.append)
        _set_model_objective(model, "guide_rank", "hpwl", "rank")
        self.assertEqual(minimized, ["rank"])

        minimized.clear()
        _set_model_objective(model, "hpwl", "hpwl", "rank")
        self.assertEqual(minimized, ["hpwl"])

        minimized.clear()
        _set_model_objective(model, "hpwl_feasibility", "hpwl", "rank")
        self.assertEqual(minimized, [])

    def test_selected_site_region_is_explicit_and_consistent(self):
        selected = _selected_site_in_region(
            {"center": [1.0, 2.0], "region_candidate_index": 3},
            "bottom_0",
        )
        self.assertEqual(selected["region_id"], "bottom_0")
        self.assertEqual(selected["center"], [1.0, 2.0])
        self.assertEqual(
            _selected_site_in_region(selected, "bottom_0"), selected
        )
        with self.assertRaisesRegex(ValueError, "conflicts"):
            _selected_site_in_region(selected, "bottom_1")

    def test_weighted_candidate_order_is_deterministic(self):
        order = _weighted_candidate_order(
            (
                np.asarray([0, 1, 2, 3]),
                np.asarray([4, 5, 6, 7]),
            ),
            (1, 2),
            6,
        )
        np.testing.assert_array_equal(order, [0, 4, 5, 1, 6, 7])

        deduplicated = _weighted_candidate_order(
            (np.asarray([0, 1, 2]), np.asarray([0, 3, 4])),
            (1, 2),
            5,
        )
        np.testing.assert_array_equal(deduplicated, [0, 3, 4, 1, 2])

    def test_greedy_pair_hpwl_recomputes_joint_net_extrema(self):
        placedb = SimpleNamespace(
            net2pin_map=[np.asarray([0, 1, 2])],
            pin2node_map=np.asarray([0, 1, 2]),
            pin_offset_x=np.zeros(3),
            pin_offset_y=np.zeros(3),
            net_weights=np.asarray([1.0]),
        )

        def net_hpwl(node_x, node_y, net_id):
            pins = placedb.net2pin_map[net_id]
            nodes = placedb.pin2node_map[pins]
            return float(
                node_x[nodes].max()
                - node_x[nodes].min()
                + node_y[nodes].max()
                - node_y[nodes].min()
            )

        placedb.net_hpwl = net_hpwl
        first = SimpleNamespace(node_id=0, node_width=0.0, node_height=0.0)
        second = SimpleNamespace(node_id=1, node_width=0.0, node_height=0.0)
        pair_hpwl = _pair_total_hpwl(
            placedb,
            first,
            np.asarray([[0.0, 0.0], [3.0, 0.0]]),
            second,
            np.asarray([[4.0, 0.0], [8.0, 0.0]]),
            np.asarray([0.0, 4.0, 10.0]),
            np.zeros(3),
            {0},
            current_hpwl=10.0,
        )
        np.testing.assert_allclose(pair_hpwl, [[10.0, 10.0], [7.0, 7.0]])

    def test_greedy_plateau_move_is_lexicographically_improving(self):
        centers = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        selected, move_type = _select_candidate(
            np.asarray([10.0, 10.0, 11.0]),
            np.asarray([True, True, True]),
            centers,
            current_center=centers[0],
            current_hpwl=10.0,
            guide_center=centers[2],
            improvement_tolerance=1e-9,
            equality_tolerance=1e-9,
            guide_tolerance=1e-12,
        )
        self.assertEqual((selected, move_type), (1, "plateau"))

        selected, move_type = _select_candidate(
            np.asarray([10.0, 10.0, 9.0]),
            np.asarray([True, True, True]),
            centers,
            current_center=centers[0],
            current_hpwl=10.0,
            guide_center=centers[0],
            improvement_tolerance=1e-9,
            equality_tolerance=1e-9,
            guide_tolerance=1e-12,
        )
        self.assertEqual((selected, move_type), (2, "strict"))

    def test_guided_threshold_move_is_bounded_and_deterministic(self):
        centers = np.asarray(
            [[0.0, 0.0], [2.0, 1.0], [2.0, -1.0], [3.0, 0.0]]
        )
        arguments = dict(
            legal=np.asarray([True, True, True, False]),
            centers=centers,
            current_center=centers[0],
            current_hpwl=10.0,
            guide_center=centers[3],
            region_candidate_indices=np.asarray([0, 9, 4, 3]),
            improvement_tolerance=1e-9,
            equality_tolerance=1e-9,
            guide_tolerance=1e-12,
            site_tolerance=1e-8,
        )
        selected, move_type = _select_guided_threshold_candidate(
            total_hpwl=np.asarray([10.0, 10.5, 10.5, 9.0]),
            hpwl_ceiling=10.5,
            **arguments,
        )
        self.assertEqual((selected, move_type), (2, "uphill"))

        selected, move_type = _select_guided_threshold_candidate(
            total_hpwl=np.asarray([10.0, 10.5, 10.5, 9.0]),
            hpwl_ceiling=10.4,
            **arguments,
        )
        self.assertEqual((selected, move_type), (None, None))

        selected, move_type = _select_guided_threshold_candidate(
            total_hpwl=np.asarray([10.0, 10.5, 10.5, 9.0]),
            hpwl_ceiling=11.0,
            max_move_rise=0.4,
            **arguments,
        )
        self.assertEqual((selected, move_type), (None, None))

        selected, move_type = _select_guided_threshold_candidate(
            total_hpwl=np.asarray([10.0, 10.5, 10.5, 9.0]),
            hpwl_ceiling=11.0,
            max_move_rise=0.5,
            **arguments,
        )
        self.assertEqual((selected, move_type), (2, "uphill"))

        arguments["legal"] = np.asarray([True, True, False, False])
        selected, move_type = _select_guided_threshold_candidate(
            total_hpwl=np.asarray([10.0, 9.5, 10.5, 9.0]),
            hpwl_ceiling=10.0,
            **arguments,
        )
        self.assertEqual((selected, move_type), (1, "strict"))

    def test_escape_hold_only_keeps_unreverted_uphill_moves(self):
        escape_moves = [
            {"refdes": "U1", "move_type": "uphill"},
            {"refdes": "U2", "move_type": "uphill"},
            {"refdes": "P1", "move_type": "plateau"},
        ]
        initial = {
            "U1": np.asarray([0.0, 0.0]),
            "U2": np.asarray([1.0, 1.0]),
            "P1": np.asarray([2.0, 2.0]),
        }
        current = {
            "U1": np.asarray([0.0, 1.0]),
            "U2": np.asarray([1.0, 1.0 + 1e-10]),
            "P1": np.asarray([3.0, 2.0]),
        }
        self.assertEqual(
            _escape_hold_refdes(
                escape_moves, current, initial, site_tolerance=1e-8
            ),
            frozenset({"U1"}),
        )

    def test_escape_sweep_order_is_seeded_without_changing_default(self):
        constraints = [
            SimpleNamespace(refdes=refdes)
            for refdes in ("A", "B", "C", "D")
        ]
        self.assertEqual(
            [row.refdes for row in _escape_sweep_order(constraints, None)],
            ["A", "B", "C", "D"],
        )

        first_rng = np.random.default_rng(1000)
        second_rng = np.random.default_rng(1000)
        first_orders = [
            [
                row.refdes
                for row in _escape_sweep_order(constraints, first_rng)
            ]
            for _ in range(3)
        ]
        second_orders = [
            [
                row.refdes
                for row in _escape_sweep_order(constraints, second_rng)
            ]
            for _ in range(3)
        ]
        self.assertEqual(first_orders, second_orders)
        self.assertTrue(
            any(order != ["A", "B", "C", "D"] for order in first_orders)
        )
        self.assertEqual(
            [row.refdes for row in constraints], ["A", "B", "C", "D"]
        )

    def test_pair_search_excludes_held_components(self):
        footprint = box(-0.5, -0.5, 0.5, 0.5)
        constraints = [
            SimpleNamespace(
                refdes=refdes,
                node_id=node_id,
                side="TOP",
                domain=SimpleNamespace(footprint_local=footprint),
            )
            for node_id, refdes in enumerate(("A", "B"))
        ]
        candidate_rows = {
            "A": {
                "centers": np.asarray([[0.0, 0.0]]),
                "eligible": np.asarray([0]),
            },
            "B": {
                "centers": np.asarray([[2.0, 0.0]]),
                "eligible": np.asarray([0]),
            },
        }
        move, diagnostics = _best_pair_move(
            placedb=None,
            constraints=constraints,
            candidate_rows=candidate_rows,
            current_centers={
                "A": np.asarray([0.0, 0.0]),
                "B": np.asarray([2.0, 0.0]),
            },
            node_x=None,
            node_y=None,
            node_nets={},
            current_hpwl=10.0,
            area_epsilon=1e-5,
            improvement_tolerance=1e-9,
            excluded_refdes=frozenset({"A"}),
        )
        self.assertIsNone(move)
        self.assertEqual(diagnostics["evaluated_pair_count"], 0)

    def test_greedy_candidate_hpwl_only_replaces_incident_nets(self):
        placedb = SimpleNamespace(
            net2pin_map=[np.asarray([0, 1]), np.asarray([2, 3])],
            pin2node_map=np.asarray([0, 1, 2, 3]),
            pin_offset_x=np.zeros(4),
            pin_offset_y=np.zeros(4),
            net_weights=np.asarray([1.0, 1.0]),
        )

        def net_hpwl(node_x, node_y, net_id):
            pins = placedb.net2pin_map[net_id]
            nodes = placedb.pin2node_map[pins]
            return float(
                node_x[nodes].max()
                - node_x[nodes].min()
                + node_y[nodes].max()
                - node_y[nodes].min()
            )

        placedb.net_hpwl = net_hpwl
        constraint = SimpleNamespace(
            node_id=0,
            node_width=0.0,
            node_height=0.0,
        )
        node_x = np.asarray([0.0, 4.0, 10.0, 12.0])
        node_y = np.zeros(4)
        candidate_hpwl = _candidate_total_hpwl(
            placedb,
            constraint,
            np.asarray([[0.0, 0.0], [3.0, 0.0], [6.0, 0.0]]),
            node_x,
            node_y,
            {0},
            current_hpwl=6.0,
        )
        np.testing.assert_allclose(candidate_hpwl, [6.0, 3.0, 4.0])

    def test_objective_replay_handles_heterogeneous_candidate_domains(self):
        class FakeSolver:
            def __init__(self, values):
                self.values = values

            def value(self, variable):
                return self.values[variable]

        small_lowers = np.arange(128, dtype=np.int64).reshape(64, 2)
        expanded_lowers = np.arange(3072, dtype=np.int64).reshape(1536, 2)
        rows = [
            {
                "constraint": SimpleNamespace(refdes="K64"),
                "centers": np.zeros((64, 2)),
                "site_var": "small_site",
                "node_x_var": "small_x",
                "node_y_var": "small_y",
                "integer_node_lowers": small_lowers,
            },
            {
                "constraint": SimpleNamespace(refdes="K1536"),
                "centers": np.zeros((1536, 2)),
                "site_var": "expanded_site",
                "node_x_var": "expanded_x",
                "node_y_var": "expanded_y",
                "integer_node_lowers": expanded_lowers,
            },
        ]
        values = {
            "small_site": 63,
            "small_x": int(small_lowers[63, 0]),
            "small_y": int(small_lowers[63, 1]),
            "expanded_site": 1535,
            "expanded_x": int(expanded_lowers[1535, 0]),
            "expanded_y": int(expanded_lowers[1535, 1]),
        }
        solver = FakeSolver(values)
        self.assertEqual(_candidate_coordinate_mismatches(rows, solver), [])
        values["expanded_x"] += 1
        mismatches = _candidate_coordinate_mismatches(rows, solver)
        self.assertEqual([row["refdes"] for row in mismatches], ["K1536"])

    def test_integer_hpwl_replay_matches_solved_net_spans(self):
        class FakeSolver:
            def value(self, variable):
                return {
                    "max_x": 2250,
                    "min_x": 500,
                    "max_y": 2500,
                    "min_y": 1000,
                }[variable]

        placedb = SimpleNamespace(
            net2pin_map=[np.asarray([0, 1])],
            pin2node_map=np.asarray([0, 1]),
            pin_offset_x=np.asarray([0.25, -0.5]),
            pin_offset_y=np.asarray([0.0, 0.5]),
            net_weights=np.asarray([2.0]),
            net_names=np.asarray([b"N1"]),
        )
        replay_total, replay_nets = _integer_hpwl_by_net(
            placedb,
            np.asarray([0.25, 2.75]),
            np.asarray([1.0, 2.0]),
            1000,
        )
        objective_rows = [
            {
                "net_id": 0,
                "net_name": "N1",
                "weight": 2,
                "max_x_var": "max_x",
                "min_x_var": "min_x",
                "max_y_var": "max_y",
                "min_y_var": "min_y",
            }
        ]
        solver_total, solver_nets = _solver_integer_hpwl_by_net(
            FakeSolver(), objective_rows
        )
        self.assertEqual(replay_total, 6500)
        self.assertEqual(solver_total, replay_total)
        self.assertEqual(solver_nets, replay_nets)

    def test_feasibility_hpwl_replay_without_response_objective(self):
        class FakeSolver:
            def value(self, variable):
                return {
                    "site": 0,
                    "node_x": 250,
                    "node_y": 1000,
                    "max_x": 2250,
                    "min_x": 500,
                    "max_y": 2500,
                    "min_y": 1000,
                }[variable]

        placedb = SimpleNamespace(
            net2pin_map=[np.asarray([0, 1])],
            pin2node_map=np.asarray([0, 1]),
            pin_offset_x=np.asarray([0.25, -0.5]),
            pin_offset_y=np.asarray([0.0, 0.5]),
            net_weights=np.asarray([2.0]),
            net_names=np.asarray([b"N1"]),
        )
        rows = [
            {
                "constraint": SimpleNamespace(refdes="A"),
                "site_var": "site",
                "node_x_var": "node_x",
                "node_y_var": "node_y",
                "integer_node_lowers": np.asarray([[250, 1000]]),
                "centers": np.zeros((1, 2)),
            }
        ]
        objective_rows = [
            {
                "net_id": 0,
                "net_name": "N1",
                "weight": 2,
                "max_x_var": "max_x",
                "min_x_var": "min_x",
                "max_y_var": "max_y",
                "min_y_var": "min_y",
            }
        ]
        arguments = (
            FakeSolver(),
            None,
            rows,
            objective_rows,
            placedb,
            np.asarray([0.25, 2.75]),
            np.asarray([1.0, 2.0]),
            1000,
            6.5,
            4,
        )
        audit = _objective_replay_audit(*arguments, 6500)
        self.assertTrue(audit["passed"])
        self.assertFalse(audit["response_objective_available"])
        self.assertIsNone(audit["solver_objective_integer"])
        self.assertTrue(audit["selected_site_within_integer_hpwl_limit"])

        audit = _objective_replay_audit(*arguments, 6499)
        self.assertFalse(audit["passed"])
        self.assertFalse(audit["selected_site_within_integer_hpwl_limit"])

        rank_arguments = list(arguments)
        rank_arguments[1] = 2.0
        audit = _objective_replay_audit(
            *rank_arguments,
            6500,
            response_objective_mode="guide_rank",
        )
        self.assertTrue(audit["passed"])
        self.assertTrue(audit["response_objective_available"])
        self.assertEqual(audit["response_objective_mode"], "guide_rank")
        self.assertFalse(audit["response_objective_checked_as_hpwl"])
        self.assertIsNone(audit["solver_objective_integer"])

    def test_objective_replay_rejects_canceling_net_mismatches(self):
        class FakeSolver:
            def value(self, variable):
                return {
                    "first_max_x": 11,
                    "first_min_x": 0,
                    "first_max_y": 0,
                    "first_min_y": 0,
                    "second_max_x": 19,
                    "second_min_x": 0,
                    "second_max_y": 0,
                    "second_min_y": 0,
                }[variable]

        placedb = SimpleNamespace(
            net2pin_map=[np.asarray([0, 1]), np.asarray([2, 3])],
            pin2node_map=np.asarray([0, 1, 2, 3]),
            pin_offset_x=np.zeros(4),
            pin_offset_y=np.zeros(4),
            net_weights=np.ones(2),
            net_names=np.asarray([b"N1", b"N2"]),
        )
        objective_rows = []
        for prefix, net_id in (("first", 0), ("second", 1)):
            objective_rows.append(
                {
                    "net_id": net_id,
                    "net_name": f"N{net_id + 1}",
                    "weight": 1,
                    "max_x_var": f"{prefix}_max_x",
                    "min_x_var": f"{prefix}_min_x",
                    "max_y_var": f"{prefix}_max_y",
                    "min_y_var": f"{prefix}_min_y",
                }
            )
        audit = _objective_replay_audit(
            FakeSolver(),
            30,
            [],
            objective_rows,
            placedb,
            np.asarray([0.0, 10.0, 0.0, 20.0]),
            np.zeros(4),
            1,
            30.0,
            0,
            30,
        )
        self.assertFalse(audit["passed"])
        self.assertEqual(audit["net_objective_mismatch_count"], 2)

    def test_exact_site_rows_are_partitioned_by_physical_side(self):
        self.assertEqual(_packing_sides("TOP"), frozenset(("TOP",)))
        self.assertEqual(_packing_sides("BOTTOM"), frozenset(("BOTTOM",)))
        self.assertEqual(
            _packing_sides("BOTH"), frozenset(("TOP", "BOTTOM"))
        )
        with self.assertRaisesRegex(ValueError, "unknown packing side"):
            _packing_sides("LEFT")

        top = {"constraint": SimpleNamespace(side="TOP")}
        bottom = {"constraint": SimpleNamespace(side="BOTTOM")}
        grouped = _rows_by_side((bottom, top))
        self.assertEqual(grouped["TOP"], [top])
        self.assertEqual(grouped["BOTTOM"], [bottom])
        with self.assertRaisesRegex(ValueError, "unknown constraint side"):
            _rows_by_side(({"constraint": SimpleNamespace(side="LEFT")},))

    def test_scoped_assignment_only_retains_named_region_choices(self):
        assignment_space = {
            "mode": "optimized",
            "node_groups": {1: "g1", 2: "g2"},
            "group_options": {
                "g1": ("left", "right"),
                "g2": ("left", "right"),
                "empty": ("left", "right"),
            },
            "group_nodes": {"g1": (1,), "g2": (2,), "empty": ()},
            "preferred_regions": {
                "g1": "left",
                "g2": "left",
                "empty": "left",
            },
        }
        hints = {
            1: {"region_id": "left", "site_index": 1},
            2: {"region_id": "right", "site_index": 2},
        }
        scoped = _scoped_assignment_space(assignment_space, hints, ["g1"])
        self.assertEqual(scoped["mode"], "optimized_scoped")
        self.assertEqual(scoped["group_options"]["g1"], ("left", "right"))
        self.assertEqual(scoped["group_options"]["g2"], ("right",))
        self.assertEqual(scoped["group_options"]["empty"], ("left",))
        self.assertEqual(
            assignment_space["group_options"]["g2"], ("left", "right")
        )
        with self.assertRaises(ValueError):
            _scoped_assignment_space(assignment_space, hints, ["unknown"])
        with self.assertRaises(ValueError):
            _scoped_assignment_space(
                dict(assignment_space, mode="fixed"), hints, ["g1"]
            )
        with self.assertRaises(ValueError):
            _scoped_assignment_space(
                assignment_space, {1: hints[1]}, ["g1"]
            )

    def test_structured_site_hints_preserve_subgroup_region_coherence(self):
        assignment_space = {
            "node_groups": {1: "g", 2: "g"},
            "group_options": {"g": ("left", "right")},
        }
        hints = {
            1: {"region_id": "right", "site_index": 4},
            2: {"region_id": "right", "site_index": 7},
        }
        self.assertEqual(
            _hinted_group_regions(hints, assignment_space),
            {"g": "right"},
        )
        self.assertEqual(_site_hint_parts(hints[1]), ("right", 4))
        hints[2]["region_id"] = "left"
        with self.assertRaises(ValueError):
            _hinted_group_regions(hints, assignment_space)
        with self.assertRaises(ValueError):
            _site_hint_parts(4)

    def test_collision_pair_pruning_only_skips_disjoint_swept_boxes(self):
        first = {"swept_bbox": (0, 0, 10, 10)}
        self.assertFalse(
            _swept_bboxes_may_overlap(
                first, {"swept_bbox": (10, 2, 20, 8)}
            )
        )
        self.assertFalse(
            _swept_bboxes_may_overlap(
                first, {"swept_bbox": (-20, -20, -1, -1)}
            )
        )
        self.assertTrue(
            _swept_bboxes_may_overlap(
                first, {"swept_bbox": (9, 9, 20, 20)}
            )
        )

    def test_partial_site_fix_releases_only_named_components(self):
        constraints = [
            SimpleNamespace(refdes="A"),
            SimpleNamespace(refdes="B"),
            SimpleNamespace(refdes="C"),
        ]
        self.assertEqual(
            _partial_fix_refdes(constraints, ["B", "B"]),
            frozenset(("A", "C")),
        )
        self.assertEqual(_partial_fix_refdes(constraints, []), frozenset())
        with self.assertRaises(ValueError):
            _partial_fix_refdes(constraints, ["UNKNOWN"])

    def test_partial_site_fix_enumerates_only_the_fixed_hint(self):
        selected = _fixed_hint_candidate_indices(
            ("left", "right"), "right", 17
        )
        np.testing.assert_array_equal(selected[0], [])
        np.testing.assert_array_equal(selected[1], [17])
        self.assertEqual(sum(len(indices) for indices in selected), 1)
        with self.assertRaises(ValueError):
            _fixed_hint_candidate_indices(("left",), "right", 17)

    def test_controlled_collision_pairs_are_canonical_and_distinct(self):
        self.assertEqual(
            _normalize_controlled_collision_pairs(
                (("B", "A"), ("A", "B"), ("C", "A"))
            ),
            frozenset((("A", "B"), ("A", "C"))),
        )
        with self.assertRaises(ValueError):
            _normalize_controlled_collision_pairs((("A", "A"),))
        with self.assertRaises(ValueError):
            _normalize_controlled_collision_pairs((("A",),))

    def test_collision_pairs_outside_local_domains_are_inactive(self):
        requested = frozenset((("A", "B"), ("A", "C")))
        available = frozenset((("A", "B"), ("B", "C")))
        self.assertEqual(
            _inactive_controlled_collision_pairs(requested, available),
            frozenset((("A", "C"),)),
        )

    def test_assumption_core_literals_map_to_refdes(self):
        self.assertEqual(
            _assumption_core_refdes((5, 3, -4, 5), {3: "A", 5: "B"}),
            ["A", "B"],
        )
        with self.assertRaises(ValueError):
            _assumption_core_refdes((7,), {3: "A"})

    def test_rotated_footprint_inner_slices_are_exact_and_disjoint(self):
        footprint = Polygon(((0, 1), (2, 0), (0, -1), (-2, 0)))
        rectangles = _horizontal_inner_rectangles(footprint, 16)
        self.assertEqual(len(rectangles), 16)
        self.assertGreater(
            sum(rectangle.area for rectangle in rectangles)
            / footprint.area,
            0.8,
        )
        self.assertTrue(
            all(footprint.covers(rectangle) for rectangle in rectangles)
        )
        self.assertAlmostEqual(
            unary_union(rectangles).area,
            sum(rectangle.area for rectangle in rectangles),
        )
        scaled = _scaled_inner_rectangles(
            footprint, 4.0, 2.0, 1000000, 16
        )
        self.assertGreaterEqual(len(scaled), 14)
        self.assertLessEqual(len(scaled), len(rectangles))
        scaled_rectangles = []
        for low_x, low_y, width, height in scaled:
            rectangle = box(
                low_x / 1000000 - 2.0,
                low_y / 1000000 - 1.0,
                (low_x + width) / 1000000 - 2.0,
                (low_y + height) / 1000000 - 1.0,
            )
            self.assertTrue(footprint.covers(rectangle))
            scaled_rectangles.append(rectangle)
        self.assertAlmostEqual(
            unary_union(scaled_rectangles).area,
            sum(rectangle.area for rectangle in scaled_rectangles),
        )
        with self.assertRaises(ValueError):
            _scaled_inner_rectangles(
                Polygon(((0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2))),
                2.0,
                2.0,
                1000000,
                16,
            )

    def test_coordinate_solution_identifies_one_candidate_site(self):
        choices = {
            "regions": ("left", "right"),
            "region_indices": np.asarray([0, 0, 1]),
            "x_values": np.asarray([10, 20, 10]),
            "y_values": np.asarray([30, 40, 30]),
        }
        self.assertEqual(
            _coordinate_choice_index(choices, "right", 10, 30), 2
        )
        with self.assertRaises(ValueError):
            _coordinate_choice_index(choices, "missing", 10, 30)
        with self.assertRaises(ValueError):
            _coordinate_choice_index(choices, "left", 99, 30)

    def test_coordinate_override_only_updates_frozen_endpoints(self):
        context = SimpleNamespace(frozen_lower_left={1: (2.0, 3.0)})
        placedb = SimpleNamespace(node_names=np.asarray([b"A", b"B"]))
        x, y, report = _override_fixed_endpoint_coordinates(
            context,
            placedb,
            np.asarray([1.0, 2.0]),
            np.asarray([3.0, 4.0]),
            [("B", "20.5", "30.5"), ("B", 20.5, 30.5)],
        )
        np.testing.assert_array_equal(x, [1.0, 20.5])
        np.testing.assert_array_equal(y, [3.0, 30.5])
        self.assertEqual(
            report, [{"refdes": "B", "lower_left": [20.5, 30.5]}]
        )
        with self.assertRaises(ValueError):
            _override_fixed_endpoint_coordinates(
                context, placedb, x, y, [("A", 1.0, 2.0)]
            )
        with self.assertRaises(ValueError):
            _override_fixed_endpoint_coordinates(
                context,
                placedb,
                x,
                y,
                [("B", 1.0, 2.0), ("B", 2.0, 3.0)],
            )
        with self.assertRaises(ValueError):
            _override_fixed_endpoint_coordinates(
                context, placedb, x, y, [("B", float("nan"), 2.0)]
            )

    def test_side_legality_report_filters_other_side(self):
        legality = {
            "violations": [
                {"side": "TOP", "violation_area": 2.0},
                {"side": "BOTTOM", "violation_area": 3.0},
            ],
            "overlap_pairs": [
                {"side": "TOP", "overlap_area": 5.0},
                {"side": "BOTTOM", "overlap_area": 7.0},
            ],
        }
        report = _side_legality_report(legality, "TOP")
        self.assertEqual(report["keepin_violation_count"], 1)
        self.assertEqual(report["keepin_violation_area"], 2.0)
        self.assertEqual(report["overlap_pair_count"], 1)
        self.assertEqual(report["overlap_area"], 5.0)

    def test_concave_footprint_decomposition_is_exact_and_deterministic(self):
        footprint = Polygon(
            ((0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4))
        )
        first = _convex_parts(footprint)
        second = _convex_parts(footprint)
        self.assertEqual(len(first), 4)
        self.assertEqual(
            [part.wkb_hex for part in first],
            [part.wkb_hex for part in second],
        )
        self.assertAlmostEqual(
            unary_union(first).symmetric_difference(footprint).area,
            0.0,
        )
        self.assertAlmostEqual(sum(part.area for part in first), footprint.area)
        for part in first:
            self.assertAlmostEqual(part.convex_hull.area, part.area)

    def test_discrete_packing_hint_requires_an_exact_site(self):
        centers = np.asarray([[0.0, 0.0], [1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(_exact_site_index(centers, [1.0, 2.0]), 1)
        index, distance = _nearest_site_index(centers, [1.1, 2.0])
        self.assertEqual(index, 1)
        self.assertAlmostEqual(distance, 0.1)
        with self.assertRaises(ValueError):
            _exact_site_index(centers, [1.1, 2.0])

    def test_discrete_candidate_limit_is_deterministic_and_keeps_hint(self):
        centers = np.asarray([[0.0, 0.0], [2.0, 0.0], [1.0, 0.0], [3.0, 0.0]])
        indices = _limited_candidate_indices(centers, 2, preferred_index=1)
        np.testing.assert_array_equal(indices, [1, 2])
        np.testing.assert_array_equal(
            _limited_candidate_indices(centers, 0), [0, 1, 2, 3]
        )
        np.testing.assert_array_equal(
            _limited_candidate_indices(
                centers, 2, preferred_index=0, guide_indices=(3,)
            ),
            [0, 3],
        )
        np.testing.assert_array_equal(
            _limited_candidate_indices(
                centers,
                2,
                preferred_index=2,
                eligible_indices=(0, 1, 3),
            ),
            [0, 1],
        )
        with self.assertRaises(ValueError):
            _limited_candidate_indices(
                centers, 2, preferred_index=0, eligible_indices=(1, 1)
            )

    def test_fixed_obstacle_pruning_uses_exact_positive_overlap(self):
        footprint = box(-0.25, -0.25, 0.25, 0.25)
        concave_obstacle = Polygon(
            ((0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3))
        )
        centers = np.asarray(
            [
                [2.0, 2.0],
                [0.5, 0.5],
                [3.25, 0.5],
            ]
        )
        np.testing.assert_array_equal(
            _candidate_indices_without_obstacle_overlap(
                footprint, centers, [concave_obstacle]
            ),
            [0, 2],
        )

    def test_candidate_guide_is_projected_in_each_region(self):
        domains = (
            SimpleNamespace(
                valid_centers=np.asarray([[0.0, 0.0], [2.0, 0.0]])
            ),
            SimpleNamespace(
                valid_centers=np.asarray([[10.0, 0.0], [12.0, 0.0]])
            ),
        )
        self.assertEqual(_guide_site_indices(domains, [3.0, 0.0]), (1, 0))

    def test_shared_box_fixed_endpoint_mode_is_explicit(self):
        context = SimpleNamespace(frozen_lower_left={1: (20.0, 30.0)})
        baseline_x = np.asarray([1.0, 2.0, 3.0])
        baseline_y = np.asarray([4.0, 5.0, 6.0])
        runtime_x, runtime_y = _select_fixed_endpoints(
            context, baseline_x, baseline_y, "runtime"
        )
        manual_x, manual_y = _select_fixed_endpoints(
            context, baseline_x, baseline_y, "manual-baseline"
        )
        np.testing.assert_array_equal(runtime_x, [1.0, 20.0, 3.0])
        np.testing.assert_array_equal(runtime_y, [4.0, 30.0, 6.0])
        np.testing.assert_array_equal(manual_x, baseline_x)
        np.testing.assert_array_equal(manual_y, baseline_y)
        manual_x[0] = 100.0
        self.assertEqual(baseline_x[0], 1.0)
        with self.assertRaises(ValueError):
            _select_fixed_endpoints(context, baseline_x, baseline_y, "invalid")

    def test_shared_box_can_override_one_runtime_frozen_endpoint(self):
        context = SimpleNamespace(frozen_lower_left={1: (20.0, 30.0)})
        placedb = SimpleNamespace(node_names=np.asarray([b"A", b"B", b"C"]))
        baseline_x = np.asarray([1.0, 2.0, 3.0])
        baseline_y = np.asarray([4.0, 5.0, 6.0])
        fixed_x = np.asarray([1.0, 20.0, 3.0])
        fixed_y = np.asarray([4.0, 30.0, 6.0])
        output_x, output_y = _override_manual_baseline_endpoints(
            context,
            placedb,
            baseline_x,
            baseline_y,
            fixed_x,
            fixed_y,
            ["B", "B"],
        )
        np.testing.assert_array_equal(output_x, baseline_x)
        np.testing.assert_array_equal(output_y, baseline_y)
        with self.assertRaises(ValueError):
            _override_manual_baseline_endpoints(
                context,
                placedb,
                baseline_x,
                baseline_y,
                fixed_x,
                fixed_y,
                ["A"],
            )

    def test_shared_coordinate_box_milp_uses_pin_offsets_and_fixed_pins(self):
        selected, coordinates, result = solve_shared_box_assignment(
            {"g": ("r",)},
            {"g": 1.0},
            {},
            {0: "g"},
            {(0, "r"): (2.0, 4.0, 0.0, 0.0)},
            [
                {
                    "name": "n:x",
                    "axis": "x",
                    "weight": 1.0,
                    "pins": [
                        {"node_id": 0, "offset": 1.0},
                        {"fixed": 0.0},
                    ],
                }
            ],
        )
        self.assertEqual(selected, {"g": "r"})
        self.assertAlmostEqual(coordinates[0]["x"], 2.0)
        self.assertAlmostEqual(result["relaxed_hpwl"], 3.0)

    def test_shared_coordinate_box_milp_couples_node_positions(self):
        group_options = {"g1": ("left", "right"), "g2": ("left", "right")}
        node_ranges = {
            (0, "left"): (0.0, 1.0, 0.0, 0.0),
            (0, "right"): (10.0, 11.0, 0.0, 0.0),
            (1, "left"): (0.0, 1.0, 0.0, 0.0),
            (1, "right"): (10.0, 11.0, 0.0, 0.0),
        }
        net_axes = [
            {
                "name": "n1:x",
                "axis": "x",
                "weight": 1.0,
                "pins": [
                    {"node_id": 0, "offset": 0.0},
                    {"node_id": 1, "offset": 0.0},
                ],
            }
        ]
        _, _, unconstrained = solve_shared_box_assignment(
            group_options,
            {"g1": 1.0, "g2": 1.0},
            {},
            {0: "g1", 1: "g2"},
            node_ranges,
            net_axes,
        )
        self.assertAlmostEqual(unconstrained["relaxed_hpwl"], 0.0)
        selected, _, constrained = solve_shared_box_assignment(
            group_options,
            {"g1": 1.0, "g2": 1.0},
            {"left": 1.0, "right": 1.0},
            {0: "g1", 1: "g2"},
            node_ranges,
            net_axes,
        )
        self.assertNotEqual(selected["g1"], selected["g2"])
        self.assertAlmostEqual(constrained["relaxed_hpwl"], 9.0)

    def test_assignment_search_capacity_scaling_is_conservative(self):
        area, capacity = _capacity_integer_bounds(
            {"g": 1.0000001}, {"r": 2.9999999}, 1000000
        )
        self.assertEqual(area, {"g": 1000001})
        self.assertEqual(capacity, {"r": 2999999})

    def test_legal_hint_capacity_floor_preserves_incumbent_load(self):
        effective, floors, overrides = _capacity_units_with_hint_floor(
            {"g1": 3, "g2": 4},
            {"r1": 5, "r2": 10},
            {"g1": "r1", "g2": "r1"},
            True,
        )
        self.assertEqual(effective, {"r1": 7, "r2": 10})
        self.assertEqual(floors, {"r1": 7, "r2": 0})
        self.assertEqual(
            overrides,
            {"r1": {"configured": 5, "hint_floor": 7, "effective": 7}},
        )
        disabled, disabled_floors, disabled_overrides = (
            _capacity_units_with_hint_floor(
                {"g1": 3}, {"r1": 2}, {"g1": "r1"}, False
            )
        )
        self.assertEqual(disabled, {"r1": 2})
        self.assertEqual(disabled_floors, {"r1": 0})
        self.assertEqual(disabled_overrides, {})

    def test_selected_assignment_data_updates_rows_and_candidates(self):
        template = {
            "assignments": [
                {"subgroup_id": "g", "proposed_region_id": "left"}
            ],
            "candidate_diagnostics": [
                {
                    "subgroup_id": "g",
                    "candidates": [
                        {"region_id": "left", "selected": True},
                        {"region_id": "right", "selected": False},
                    ],
                }
            ],
            "capacity_diagnostics": {
                "left": {
                    "region_area_mm2": 10.0,
                    "free_area_after_anchors_mm2": 8.0,
                },
                "right": {
                    "region_area_mm2": 20.0,
                    "free_area_after_anchors_mm2": 16.0,
                },
            },
        }
        output = _selected_assignment_data(
            template,
            {"g": "right"},
            {
                "status": "FEASIBLE",
                "model": {"assignment_group_areas": {"g": 2.0}},
            },
        )
        self.assertEqual(output["schema"], "m336_region_assignment_v4")
        self.assertEqual(
            output["assignments"][0]["proposed_region_id"], "right"
        )
        self.assertEqual(
            [row["selected"] for row in output["candidate_diagnostics"][0]["candidates"]],
            [False, True],
        )
        self.assertEqual(
            output["capacity_diagnostics"]["left"]["member_area_mm2"],
            0.0,
        )
        self.assertEqual(
            output["capacity_diagnostics"]["right"]["member_area_mm2"],
            2.0,
        )
        self.assertEqual(
            output["capacity_diagnostics"]["right"][
                "free_area_utilization"
            ],
            0.125,
        )

    def test_candidate_domains_do_not_apply_clearance_twice(self):
        region = box(0, 0, 10, 10)
        source_domain = FeasibleDomain.build(
            region, width=1.0, height=1.0, grid=1.0, clearance=1.0
        )
        constraint = NodeConstraint(
            node_id=0,
            refdes="U1",
            side="TOP",
            group_id="g",
            subgroup_id="g__top",
            region_id="top_0",
            domain=source_domain,
            target_center=(5.0, 5.0),
            node_width=1.0,
            node_height=1.0,
        )
        context = SimpleNamespace(
            constraints=[constraint],
            geometry=SimpleNamespace(
                regions={"top_0": SimpleNamespace(side="TOP")}
            ),
            regions={"top_0": region},
            grid=1.0,
            alignment=SimpleNamespace(scale=1.0),
        )
        template = {
            "assignments": [
                {
                    "subgroup_id": "g__top",
                    "member_refdes": ["U1"],
                    "placement_side": "TOP",
                }
            ],
            "candidate_diagnostics": [
                {
                    "subgroup_id": "g__top",
                    "member_area_mm2": 1.0,
                    "candidates": [
                        {"region_id": "top_0", "feasible": True}
                    ],
                }
            ],
        }
        _, _, _, domains = _candidate_domains(
            context, template, clearance_mm=1.0
        )
        self.assertEqual(
            domains[(0, "top_0")].footprint_local.bounds,
            source_domain.footprint_local.bounds,
        )
        with self.assertRaises(ValueError):
            _candidate_domains(context, template, clearance_mm=0.5)

    def test_score_hpwl_limit_is_a_necessary_combined_quality_gate(self):
        baseline_hpwl = 10.0
        baseline_rsmt = 20.0
        self.assertAlmostEqual(
            _score_hpwl_limit(baseline_hpwl, baseline_rsmt, 1.0),
            40.0 / 3.0,
        )
        self.assertAlmostEqual(
            _score_hpwl_limit(baseline_hpwl, baseline_rsmt, 2.0),
            20.0 / 3.0,
        )
        self.assertEqual(_hpwl_rounding_allowance_units([1, 2, 0]), 12)
        with self.assertRaises(ValueError):
            _hpwl_rounding_allowance_units([0.5])

    def test_joint_packing_exclusion_depends_on_grid_resolution(self):
        subgroup_id = "page_86_U8601__bottom"
        self.assertIsNotNone(
            packing_exclusion_reason(subgroup_id, "bottom_2", 0.1)
        )
        self.assertIsNone(
            packing_exclusion_reason(subgroup_id, "bottom_2", 0.05)
        )
        self.assertIsNone(
            packing_exclusion_reason(subgroup_id, "bottom_2", 0.2)
        )

    def test_minimum_interval_span_is_a_relaxed_range_bound(self):
        self.assertEqual(minimum_interval_span([(0, 2), (1, 3)]), 0.0)
        self.assertEqual(minimum_interval_span([(0, 1), (4, 5), (6, 9)]), 5.0)
        with self.assertRaises(ValueError):
            minimum_interval_span([(2, 1)])

    def test_quality_bound_uses_supplied_positions_for_uncontrolled_nodes(self):
        placedb = SimpleNamespace(
            net2pin_map=[[0, 1]],
            pin2node_map=np.asarray([0, 1]),
            pin_offset_x=np.zeros(2),
            pin_offset_y=np.zeros(2),
            node_x=np.asarray([0.0, 100.0]),
            node_y=np.zeros(2),
            net_weights=np.ones(1),
            net_names=np.asarray([b"N1"]),
            net_hpwl=lambda x, y, net_id: float(abs(x[1] - x[0])),
        )
        constraint = SimpleNamespace(node_width=0.0, node_height=0.0)
        bound, _ = _bound_for_ranges(
            placedb,
            {0: constraint},
            {0: (0.0, 0.0, 0.0, 0.0)},
            np.asarray([0.0, 10.0]),
            np.asarray([0.0, 0.0]),
        )
        self.assertEqual(bound, 10.0)

    def test_runtime_fixed_positions_override_manual_baseline(self):
        context = SimpleNamespace(frozen_lower_left={1: (20.0, 30.0)})
        fixed_x, fixed_y = _runtime_fixed_positions(
            context,
            np.asarray([1.0, 2.0, 3.0]),
            np.asarray([4.0, 5.0, 6.0]),
        )
        np.testing.assert_array_equal(fixed_x, [1.0, 20.0, 3.0])
        np.testing.assert_array_equal(fixed_y, [4.0, 30.0, 6.0])

    def test_quality_assignment_milp_uses_span_then_secondary_cost(self):
        group_options = {"g1": ("left", "right"), "g2": ("left", "right")}

        def pin(group_id):
            return {
                "group_id": group_id,
                "intervals": {"left": (0, 1), "right": (10, 11)},
            }

        net_axes = [
            {
                "name": "n1:x",
                "weight": 1.0,
                "pins": [pin("g1"), pin("g2")],
            }
        ]
        costs = {
            ("g1", "left"): 0.0,
            ("g1", "right"): 2.0,
            ("g2", "left"): 0.0,
            ("g2", "right"): 1.0,
        }
        selected, diagnostics = solve_interval_assignment(
            group_options,
            {"g1": 1.0, "g2": 1.0},
            {"left": 2.0, "right": 2.0},
            net_axes,
            costs,
        )
        self.assertEqual(selected, {"g1": "left", "g2": "left"})
        self.assertAlmostEqual(diagnostics["primary_relaxed_hpwl"], 0.0)

        capacity_selected, diagnostics = solve_interval_assignment(
            group_options,
            {"g1": 1.0, "g2": 1.0},
            {"left": 1.0, "right": 1.0},
            net_axes,
            costs,
        )
        self.assertNotEqual(
            capacity_selected["g1"], capacity_selected["g2"]
        )
        self.assertAlmostEqual(diagnostics["primary_relaxed_hpwl"], 9.0)

    def test_compatible_geometry_may_only_move_centers(self):
        source = make_geometry()
        baseline = make_geometry((20000, 30000), (120000, 30000))
        report = validate_compatibility(source, baseline)
        self.assertTrue(report["compatible"])
        self.assertEqual(report["named_symbol_count"], 2)
        self.assertEqual(report["moved_component_count"], 2)
        self.assertAlmostEqual(direct_hpwl_mm(baseline), 8.0)

    def test_side_or_pin_change_is_rejected(self):
        source = make_geometry()
        baseline = copy.deepcopy(source)
        baseline["symbols"][1]["layer"] = "TOP"
        with self.assertRaises(BaselineCompatibilityError):
            validate_compatibility(source, baseline)

        baseline = copy.deepcopy(source)
        baseline["symbols"][1]["pins"][0]["rel_xy"][0] += 1
        with self.assertRaises(BaselineCompatibilityError):
            validate_compatibility(source, baseline)

    def test_bottom_pin_offset_is_preflipped(self):
        geometry = make_geometry()
        with tempfile.TemporaryDirectory() as directory:
            nets = Path(directory) / "m336.nets"
            nets.write_text(
                "UCLA nets 1.0\nNumNets : 1\nNumPins : 2\n"
                "NetDegree : 2 N1\n"
                "\tB1 I : 1.00000000 2.00000000\n"
                "\tT1 I : 1.00000000 2.00000000\n"
            )
            report = validate_bookshelf_pin_alignment(geometry, nets, 1.0)
            self.assertEqual(report["connected_pin_count"], 2)
            self.assertLess(report["max_residual_mm"], 1e-12)

            nets.write_text(nets.read_text().replace("B1 I : 1.0", "B1 I : -1.0"))
            with self.assertRaises(BaselineCompatibilityError):
                validate_bookshelf_pin_alignment(geometry, nets, 1.0)

    def test_prepare_baseline_writes_compatible_aux_and_manifest(self):
        source = make_geometry()
        baseline = make_geometry((20000, 30000), (120000, 30000))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.json"
            baseline_path = root / "baseline.json"
            source_path.write_text(json.dumps(source))
            baseline_path.write_text(json.dumps(baseline))
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "site_mm": 1.0,
                        "origin_mm": [-10.0, -10.0],
                        "layout_sites": [40, 40],
                    }
                )
            )
            (root / "m336.nodes").write_text(
                "UCLA nodes 1.0\nNumNodes : 2\nNumTerminals : 0\nB1 4 4\nT1 4 4\n"
            )
            (root / "m336.nets").write_text(
                "UCLA nets 1.0\nNumNets : 1\nNumPins : 2\n"
                "NetDegree : 2 N1\n"
                "\tB1 I : 1.00000000 2.00000000\n"
                "\tT1 I : 1.00000000 2.00000000\n"
            )
            report = prepare_baseline(source_path, baseline_path, root)
            self.assertTrue(report["compatibility"]["compatible"])
            self.assertTrue((root / "m336.baseline.pl").exists())
            self.assertEqual(
                (root / "m336.baseline.aux").read_text(),
                "RowBasedPlacement : m336.nodes m336.nets m336.baseline.pl m336.scl\n",
            )


if __name__ == "__main__":
    unittest.main()
