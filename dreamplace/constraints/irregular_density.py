"""Conservative usable-capacity maps for irregular placement regions."""

from __future__ import annotations

import math
import time

import numpy as np
import torch
from shapely.geometry import box
from shapely.ops import unary_union


def rasterize_usable_area(
    polygons,
    bounds,
    num_bins_x,
    num_bins_y,
    blocked_polygons=(),
):
    """Return conservative per-bin usable area and auditable diagnostics."""
    xl, yl, xh, yh = (float(value) for value in bounds)
    num_bins_x = int(num_bins_x)
    num_bins_y = int(num_bins_y)
    if not (xh > xl and yh > yl):
        raise ValueError("density bounds must have positive area")
    if num_bins_x <= 0 or num_bins_y <= 0:
        raise ValueError("density bin counts must be positive")

    bin_size_x = (xh - xl) / num_bins_x
    bin_size_y = (yh - yl) / num_bins_y
    bin_area = bin_size_x * bin_size_y
    board = box(xl, yl, xh, yh)
    keepin = unary_union(tuple(polygons)) if polygons else None
    clipped_keepin = (
        keepin.intersection(board) if keepin is not None else None
    )
    blocked = (
        unary_union(tuple(blocked_polygons)) if blocked_polygons else None
    )
    if clipped_keepin is None:
        usable_geometry = None
        exact_keepin_area = 0.0
        blocked_keepin_area = 0.0
    else:
        exact_keepin_area = clipped_keepin.area
        blocked_keepin_area = (
            0.0
            if blocked is None
            else clipped_keepin.intersection(blocked).area
        )
        usable_geometry = (
            clipped_keepin
            if blocked is None
            else clipped_keepin.difference(blocked)
        )
    exact_usable_area = (
        0.0 if usable_geometry is None else usable_geometry.area
    )
    tolerance = np.finfo(np.float64).eps * max(bin_area, 1.0) * 16
    usable_area = np.zeros((num_bins_x, num_bins_y), dtype=np.float64)

    if usable_geometry is not None and not usable_geometry.is_empty:
        for bin_x in range(num_bins_x):
            bin_xl = xl + bin_x * bin_size_x
            bin_xh = bin_xl + bin_size_x
            for bin_y in range(num_bins_y):
                bin_yl = yl + bin_y * bin_size_y
                bin_yh = bin_yl + bin_size_y
                bin_polygon = box(bin_xl, bin_yl, bin_xh, bin_yh)
                intersection_area = usable_geometry.intersection(bin_polygon).area
                usable_area[bin_x, bin_y] = max(
                    0.0,
                    min(bin_area, intersection_area - tolerance),
                )

    outside_area = np.maximum(bin_area - usable_area, 0.0)
    area_tolerance = max(tolerance * num_bins_x * num_bins_y, 1e-12)
    raster_usable_area = float(usable_area.sum())
    if raster_usable_area > exact_usable_area + area_tolerance:
        raise RuntimeError("usable-capacity rasterization is not conservative")

    fully_blocked = usable_area <= tolerance
    fully_usable = outside_area <= tolerance
    partial = ~(fully_blocked | fully_usable)
    diagnostics = {
        "board_area": (xh - xl) * (yh - yl),
        "bin_area": bin_area,
        "bin_size_x": bin_size_x,
        "bin_size_y": bin_size_y,
        "exact_keepin_area": float(exact_keepin_area),
        "blocked_keepin_area": float(blocked_keepin_area),
        "exact_usable_area": float(exact_usable_area),
        "raster_usable_area": raster_usable_area,
        "conservative_area_loss": float(exact_usable_area - raster_usable_area),
        "outside_area": float(outside_area.sum()),
        "usable_fraction": raster_usable_area / ((xh - xl) * (yh - yl)),
        "fully_blocked_bin_count": int(fully_blocked.sum()),
        "fully_usable_bin_count": int(fully_usable.sum()),
        "partial_bin_count": int(partial.sum()),
        "num_bins_x": num_bins_x,
        "num_bins_y": num_bins_y,
    }
    return usable_area, outside_area, diagnostics


def build_side_capacity_maps(
    regions_by_side,
    obstacles_by_side,
    bounds,
    num_bins_x,
    num_bins_y,
    target_density,
    dtype,
    device,
):
    """Build TOP/BOTTOM usable-area and static-density tensors."""
    target_density = float(target_density)
    if not math.isfinite(target_density) or not 0 < target_density <= 1:
        raise ValueError("target density must be finite and in (0, 1]")

    started = time.perf_counter()
    result = {}
    for side in ("top", "btm"):
        side_started = time.perf_counter()
        usable_area, outside_area, diagnostics = rasterize_usable_area(
            regions_by_side.get(side, ()),
            bounds,
            num_bins_x,
            num_bins_y,
            blocked_polygons=obstacles_by_side.get(side, ()),
        )
        diagnostics["side"] = side
        diagnostics["target_density"] = target_density
        diagnostics["obstacle_count"] = len(
            obstacles_by_side.get(side, ())
        )
        diagnostics["usable_capacity_area"] = float(
            usable_area.sum() * target_density
        )
        diagnostics["static_density_area"] = float(
            outside_area.sum() * target_density
        )
        diagnostics["build_seconds"] = time.perf_counter() - side_started
        result[side] = {
            "usable_area_map": torch.as_tensor(
                usable_area, dtype=dtype, device=device
            ),
            "usable_capacity_map": torch.as_tensor(
                usable_area * target_density,
                dtype=dtype,
                device=device,
            ),
            "static_density_map": torch.as_tensor(
                outside_area * target_density,
                dtype=dtype,
                device=device,
            ),
            "diagnostics": diagnostics,
        }
    elapsed = time.perf_counter() - started
    for side in result:
        result[side]["diagnostics"]["total_build_seconds"] = elapsed
    return result
