import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
from shapely.geometry import Polygon, box


sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dreamplace.constraints.irregular_density import (  # noqa: E402
    build_side_capacity_maps,
    rasterize_usable_area,
)
from dreamplace.constraints.anchor_keepin import AnchorKeepInContext  # noqa: E402
from dreamplace.PlaceObj import PlaceObj  # noqa: E402
from dreamplace.ops.electric_potential.electric_overflow import (  # noqa: E402
    ElectricOverflow,
)
from dreamplace.ops.electric_potential.electric_potential import (  # noqa: E402
    ElectricPotential,
)


class IrregularDensityTest(unittest.TestCase):
    @staticmethod
    def _operator(operator_type, static_density_map=None, device="cpu"):
        dtype = torch.float64
        bin_centers = torch.arange(
            0.5, 4.0, 1.0, dtype=dtype, device=device
        )
        return operator_type(
            node_size_x=torch.tensor([0.5], dtype=dtype, device=device),
            node_size_y=torch.tensor([0.5], dtype=dtype, device=device),
            bin_center_x=bin_centers,
            bin_center_y=bin_centers,
            target_density=0.7,
            xl=0.0,
            yl=0.0,
            xh=4.0,
            yh=4.0,
            bin_size_x=1.0,
            bin_size_y=1.0,
            num_movable_nodes=1,
            num_terminals=0,
            num_filler_nodes=0,
            padding=0,
            deterministic_flag=True,
            sorted_node_map=torch.tensor(
                [0], dtype=torch.int32, device=device
            ),
            static_density_map=static_density_map,
        )

    def test_usable_area_raster_is_conservative(self):
        keepin = Polygon(
            ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0),
             (1.0, 1.0), (1.0, 2.0), (0.0, 2.0))
        )

        usable, outside, diagnostics = rasterize_usable_area(
            [keepin], (0.0, 0.0, 2.0, 2.0), 2, 2
        )

        self.assertLessEqual(usable.sum(), keepin.area)
        self.assertGreater(usable.sum(), keepin.area - 1e-10)
        self.assertEqual(diagnostics["fully_blocked_bin_count"], 1)
        self.assertEqual(diagnostics["fully_usable_bin_count"], 3)
        self.assertAlmostEqual(outside[1, 1], 1.0)
        np.testing.assert_allclose(usable + outside, np.ones((2, 2)))

    def test_side_capacity_maps_are_isolated_and_complementary(self):
        maps = build_side_capacity_maps(
            regions_by_side={
                "top": [box(0.0, 0.0, 2.0, 1.0)],
                "btm": [box(2.0, 0.0, 4.0, 1.0)],
            },
            obstacles_by_side={"top": [], "btm": []},
            bounds=(0.0, 0.0, 4.0, 1.0),
            num_bins_x=4,
            num_bins_y=1,
            target_density=0.7,
            dtype=torch.float64,
            device="cpu",
        )

        top_static = maps["top"]["static_density_map"][:, 0]
        btm_static = maps["btm"]["static_density_map"][:, 0]
        self.assertLess(top_static[0].item(), 1e-12)
        self.assertGreater(top_static[-1].item(), 0.699999)
        self.assertGreater(btm_static[0].item(), 0.699999)
        self.assertLess(btm_static[-1].item(), 1e-12)
        for side in ("top", "btm"):
            capacity = maps[side]["usable_capacity_map"]
            static = maps[side]["static_density_map"]
            torch.testing.assert_close(
                capacity + static,
                torch.full_like(capacity, 0.7),
            )

    def test_frozen_obstacles_reduce_capacity_before_rasterization(self):
        maps = build_side_capacity_maps(
            regions_by_side={
                "top": [box(0.0, 0.0, 4.0, 1.0)],
                "btm": [],
            },
            obstacles_by_side={
                "top": [box(1.0, 0.0, 2.0, 1.0)],
                "btm": [],
            },
            bounds=(0.0, 0.0, 4.0, 1.0),
            num_bins_x=4,
            num_bins_y=1,
            target_density=0.7,
            dtype=torch.float64,
            device="cpu",
        )

        diagnostics = maps["top"]["diagnostics"]
        self.assertAlmostEqual(diagnostics["exact_keepin_area"], 4.0)
        self.assertAlmostEqual(diagnostics["blocked_keepin_area"], 1.0)
        self.assertAlmostEqual(diagnostics["exact_usable_area"], 3.0)
        self.assertGreater(
            maps["top"]["static_density_map"][1, 0].item(), 0.699999
        )

    def test_context_partitions_constrained_nodes_from_frozen_obstacles(self):
        context = object.__new__(AnchorKeepInContext)
        context.constraints = (
            SimpleNamespace(node_id=0),
            SimpleNamespace(node_id=1),
        )
        context.frozen_lower_left = {2: (0.0, 0.0), 3: (3.0, 0.0)}
        context.regions = {
            "top_region": box(0.0, 0.0, 2.0, 1.0),
            "btm_region": box(2.0, 0.0, 4.0, 1.0),
        }
        context.geometry = SimpleNamespace(
            regions={
                "top_region": SimpleNamespace(side="TOP"),
                "btm_region": SimpleNamespace(side="BOTTOM"),
            }
        )
        context._density_capacity_cache = {}
        placedb = SimpleNamespace(
            xl=0.0,
            yl=0.0,
            xh=4.0,
            yh=1.0,
            num_movable_nodes=4,
            num_physical_nodes=4,
            num_filler_nodes=0,
            node_side_flag=np.array([1, 0, 1, 0]),
            node_x=np.zeros(4),
            node_y=np.zeros(4),
            node_size_x=np.ones(4),
            node_size_y=np.ones(4),
        )

        maps, cache_hit = context.build_density_capacity_maps(
            placedb=placedb,
            num_bins_x=4,
            num_bins_y=1,
            target_density=0.7,
            dtype=torch.float64,
            device="cpu",
        )

        self.assertFalse(cache_hit)
        torch.testing.assert_close(
            maps["top"]["movable_node_ids"], torch.tensor([0])
        )
        torch.testing.assert_close(
            maps["btm"]["movable_node_ids"], torch.tensor([1])
        )
        self.assertEqual(maps["top"]["diagnostics"]["obstacle_count"], 1)
        self.assertEqual(maps["btm"]["diagnostics"]["obstacle_count"], 1)
        for side in ("top", "btm"):
            diagnostics = maps[side]["diagnostics"]
            self.assertFalse(diagnostics["target_density_feasible"])
            self.assertAlmostEqual(
                diagnostics["raw_area_utilization"], 1.0
            )
            self.assertAlmostEqual(
                diagnostics["unavoidable_area_overflow"], 0.3
            )
            self.assertAlmostEqual(
                diagnostics["minimum_normalized_overflow"], 3.0 / 7.0
            )

        context._density_capacity_cache = {}
        context.require_feasible_density_target = True
        with self.assertRaisesRegex(ValueError, "target 0.700000 is infeasible"):
            context.build_density_capacity_maps(
                placedb=placedb,
                num_bins_x=4,
                num_bins_y=1,
                target_density=0.7,
                dtype=torch.float64,
                device="cpu",
            )

    def test_potential_and_overflow_consume_identical_static_density(self):
        static = torch.zeros((4, 4), dtype=torch.float64)
        static[2:, :] = 0.7
        pos = torch.tensor([1.75, 1.75], dtype=torch.float64)
        potential = self._operator(ElectricPotential, static)
        overflow = self._operator(ElectricOverflow, static)

        potential(pos)
        overflow(pos)

        torch.testing.assert_close(potential.initial_density_map, static)
        torch.testing.assert_close(overflow.initial_density_map, static)

    def test_outside_static_density_produces_inward_gradient(self):
        static = torch.zeros((4, 4), dtype=torch.float64)
        static[2:, :] = 0.7
        potential = self._operator(ElectricPotential, static)
        pos = torch.tensor(
            [1.75, 1.75], dtype=torch.float64, requires_grad=True
        )

        potential(pos).backward()

        self.assertTrue(torch.isfinite(pos.grad).all())
        self.assertGreater(pos.grad[0].item(), 0.0)
        self.assertAlmostEqual(pos.grad[1].item(), 0.0, places=9)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is required")
    def test_cuda_static_density_gradient_is_finite_and_inward(self):
        static = torch.zeros((4, 4), dtype=torch.float64, device="cuda")
        static[2:, :] = 0.7
        potential = self._operator(
            ElectricPotential, static, device="cuda"
        )
        pos = torch.tensor(
            [1.75, 1.75],
            dtype=torch.float64,
            device="cuda",
            requires_grad=True,
        )

        potential(pos).backward()

        self.assertTrue(torch.isfinite(pos.grad).all().item())
        self.assertGreater(pos.grad[0].item(), 0.0)

    def test_feature_off_retains_zero_initial_density(self):
        overflow = self._operator(ElectricOverflow)
        pos = torch.tensor([1.75, 1.75], dtype=torch.float64)

        overflow(pos)

        self.assertEqual(
            torch.count_nonzero(overflow.initial_density_map).item(), 0
        )

    def test_feature_off_side_overflow_excludes_fillers(self):
        model = PlaceObj.__new__(PlaceObj)
        model.irregular_density_capacity_maps = None
        placedb = SimpleNamespace(
            xl=0.0,
            yl=0.0,
            xh=4.0,
            yh=4.0,
            num_movable_nodes=1,
            num_top_movable_nodes=1,
            num_top_fixed_nodes=1,
            num_top_filler_nodes=1,
            top_nodes_idx=torch.tensor([0, 1, 2]),
        )
        data_collections = SimpleNamespace(
            node_size_x=torch.ones(3),
            node_size_y=torch.ones(3),
            target_density=torch.tensor(0.7),
            sorted_top_node_map=torch.tensor([0], dtype=torch.int32),
            movable_macro_mask=torch.zeros(3, dtype=torch.bool),
            bin_center_x_padded=lambda *_: torch.arange(0.5, 4.0),
            bin_center_y_padded=lambda *_: torch.arange(0.5, 4.0),
        )

        with patch(
            "dreamplace.PlaceObj.electric_overflow.ElectricOverflow"
        ) as constructor:
            model.build_electric_overflow(
                SimpleNamespace(deterministic_flag=True),
                placedb,
                data_collections,
                4,
                4,
                side="top",
            )

        self.assertEqual(constructor.call_args.kwargs["num_filler_nodes"], 0)


if __name__ == "__main__":
    unittest.main()
