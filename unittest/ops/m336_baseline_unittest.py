import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np


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
    _runtime_fixed_positions,
    minimum_interval_span,
)
from finalize_assignment import packing_exclusion_reason  # noqa: E402
from optimize_assignment import solve_interval_assignment  # noqa: E402
from solve_discrete_placement import (  # noqa: E402
    _hpwl_rounding_allowance_units,
    _score_hpwl_limit,
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
