"""Lossless PCB geometry ingestion and coordinate alignment helpers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple

import numpy as np
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


Point = Tuple[float, float]


def dbu_to_mm(value, dbu_per_mm: float):
    """Convert scalar or array-like integer DBU coordinates to millimeters."""
    converted = np.asarray(value, dtype=np.float64) / float(dbu_per_mm)
    return float(converted) if converted.ndim == 0 else converted


def _arc_points(segment: Mapping, dbu_per_mm: float, chord_error_mm: float):
    start, end = dbu_to_mm(segment["start_end"], dbu_per_mm)
    center = dbu_to_mm(segment["center"], dbu_per_mm)
    radius = float(segment.get("radius", 0.0)) / dbu_per_mm
    if radius <= 0:
        return [tuple(start), tuple(end)]

    start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
    end_angle = math.atan2(end[1] - center[1], end[0] - center[0])
    delta = end_angle - start_angle
    if segment.get("is_clockwise", False):
        while delta >= 0:
            delta -= 2 * math.pi
    else:
        while delta <= 0:
            delta += 2 * math.pi

    error = min(max(chord_error_mm, 1e-9), radius)
    max_step = 2 * math.acos(max(-1.0, 1.0 - error / radius))
    if not math.isfinite(max_step) or max_step <= 0:
        max_step = math.pi / 180.0
    steps = max(1, int(math.ceil(abs(delta) / max_step)))
    angles = np.linspace(start_angle, start_angle + delta, steps + 1)
    points = np.column_stack(
        (center[0] + radius * np.cos(angles), center[1] + radius * np.sin(angles))
    )
    points[0] = start
    points[-1] = end
    return [tuple(point) for point in points]


def polygon_from_segments(
    segments: Sequence[Mapping],
    dbu_per_mm: float,
    chord_error_mm: float = 0.002,
):
    """Reconstruct a polygon boundary from ordered line and circular-arc segments."""
    points = []
    for segment in segments:
        kind = segment.get("obj_type", "").lower()
        if kind == "arc":
            segment_points = _arc_points(segment, dbu_per_mm, chord_error_mm)
        elif kind == "line":
            segment_points = [
                tuple(point) for point in dbu_to_mm(segment["start_end"], dbu_per_mm)
            ]
        else:
            raise ValueError("unsupported PCB boundary segment: %s" % kind)

        if points and not np.allclose(points[-1], segment_points[0], atol=1e-9):
            points.append(segment_points[0])
        points.extend(segment_points if not points else segment_points[1:])

    if len(points) < 3:
        raise ValueError("a PCB region boundary requires at least three points")
    if not np.allclose(points[0], points[-1], atol=1e-9):
        points.append(points[0])

    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.area <= 0:
        raise ValueError("PCB region reconstruction produced an empty polygon")
    return polygon


def _shape_polygon(shape: Mapping, dbu_per_mm: float, chord_error_mm: float):
    polygon = polygon_from_segments(
        shape["segments"], dbu_per_mm, chord_error_mm=chord_error_mm
    )
    void_polygons = []
    for void in shape.get("voids", []):
        if isinstance(void, Mapping) and void.get("segments"):
            void_polygons.append(
                polygon_from_segments(
                    void["segments"], dbu_per_mm, chord_error_mm=chord_error_mm
                )
            )
    if void_polygons:
        polygon = polygon.difference(unary_union(void_polygons))
    return polygon


@dataclass(frozen=True)
class SymbolGeometry:
    refdes: str
    side: str
    center_mm: Point
    width_mm: float
    height_mm: float
    rotation: float
    footprint_mm: object
    footprint_source: str


@dataclass(frozen=True)
class RegionGeometry:
    region_id: str
    side: str
    polygon_mm: object
    source_index: int


@dataclass(frozen=True)
class GeometryAlignment:
    """Uniform source-mm to Cypress-coordinate transform."""

    model: str
    scale: float
    translate_x: float
    translate_y: float
    flip_y: bool
    matched_refdes: Tuple[str, ...]
    mean_residual_mm: float
    max_residual_mm: float

    def transform_points(self, points: Iterable[Point]):
        points = np.asarray(points, dtype=np.float64)
        transformed = points.copy()
        transformed[:, 0] *= self.scale
        transformed[:, 1] *= -self.scale if self.flip_y else self.scale
        transformed[:, 0] += self.translate_x
        transformed[:, 1] += self.translate_y
        return transformed

    def transform_point(self, point: Point) -> Point:
        return tuple(self.transform_points([point])[0])

    def transform_geometry(self, geometry):
        y_scale = -self.scale if self.flip_y else self.scale
        return affinity.affine_transform(
            geometry,
            [self.scale, 0.0, 0.0, y_scale, self.translate_x, self.translate_y],
        )

    def to_dict(self):
        return {
            "model": self.model,
            "scale_cypress_units_per_mm": self.scale,
            "translate_x": self.translate_x,
            "translate_y": self.translate_y,
            "flip_y": self.flip_y,
            "registration_count": len(self.matched_refdes),
            "matched_refdes": list(self.matched_refdes),
            "mean_residual_mm": self.mean_residual_mm,
            "max_residual_mm": self.max_residual_mm,
        }

    def dump(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as stream:
            json.dump(self.to_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")

    @classmethod
    def fit(
        cls,
        source_centers_mm: Mapping[str, Point],
        target_centers: Mapping[str, Point],
        min_points: int = 3,
        max_residual_mm: float = 0.05,
    ):
        common = tuple(
            sorted(
                refdes
                for refdes in source_centers_mm.keys() & target_centers.keys()
                if refdes
            )
        )
        if len(common) < min_points:
            raise ValueError(
                "coordinate alignment requires at least %d common refdes; found %d"
                % (min_points, len(common))
            )

        source = np.asarray([source_centers_mm[name] for name in common], dtype=float)
        target = np.asarray([target_centers[name] for name in common], dtype=float)
        candidates = []
        for flip_y in (False, True):
            adjusted = source.copy()
            if flip_y:
                adjusted[:, 1] *= -1
            src_center = adjusted.mean(axis=0)
            dst_center = target.mean(axis=0)

            for model, scale in (("translation", 1.0), ("uniform_scale", None)):
                if scale is None:
                    centered_source = adjusted - src_center
                    centered_target = target - dst_center
                    denominator = np.square(centered_source).sum()
                    if denominator <= np.finfo(float).eps:
                        continue
                    scale = float((centered_source * centered_target).sum() / denominator)
                    if not math.isfinite(scale) or scale <= 0:
                        continue
                translation = dst_center - scale * src_center
                prediction = adjusted * scale + translation
                residual_target = np.linalg.norm(prediction - target, axis=1)
                residual_mm = residual_target / abs(scale)
                candidates.append(
                    (
                        float(residual_mm.max()),
                        float(residual_mm.mean()),
                        cls(
                            model=model + ("_y_flip" if flip_y else ""),
                            scale=float(scale),
                            translate_x=float(translation[0]),
                            translate_y=float(translation[1]),
                            flip_y=flip_y,
                            matched_refdes=common,
                            mean_residual_mm=float(residual_mm.mean()),
                            max_residual_mm=float(residual_mm.max()),
                        ),
                    )
                )

        if not candidates:
            raise ValueError("coordinate alignment could not fit a valid transform")
        alignment = min(candidates, key=lambda item: (item[0], item[1]))[2]
        if alignment.max_residual_mm > max_residual_mm:
            raise ValueError(
                "coordinate alignment residual %.6f mm exceeds %.6f mm"
                % (alignment.max_residual_mm, max_residual_mm)
            )
        return alignment


@dataclass(frozen=True)
class PCBGeometry:
    schema: str
    dbu_per_mm: float
    symbols: Dict[str, SymbolGeometry]
    regions: Dict[str, RegionGeometry]

    @property
    def symbol_centers_mm(self):
        return {name: symbol.center_mm for name, symbol in self.symbols.items()}


def load_pcb_geometry(path, chord_error_mm: float = 0.002) -> PCBGeometry:
    """Load component symbols and exact placeable polygons from an export JSON."""
    with Path(path).open() as stream:
        data = json.load(stream)
    metadata = data.get("export_meta", {})
    if metadata.get("schema") != "pcb_geometry_lossless_v1":
        raise ValueError("unsupported PCB geometry schema: %r" % metadata.get("schema"))
    dbu_per_mm = float(metadata["dbu_per_user_unit"])

    symbols = {}
    for raw_symbol in data.get("symbols", []):
        refdes = raw_symbol.get("refdes", "").strip()
        if not refdes:
            continue
        if refdes in symbols:
            raise ValueError("duplicate non-empty symbol refdes: %s" % refdes)
        side = raw_symbol["layer"].upper()
        bbox_mm = dbu_to_mm(raw_symbol["b_box"], dbu_per_mm)
        place_bound_shapes = []
        expected_layer = "PLACE_BOUND_%s" % side
        for child in raw_symbol.get("children", []):
            layer = child.get("layer", "").upper()
            if child.get("obj_type", "").lower() != "shape":
                continue
            if expected_layer not in layer and not layer.endswith("/PLACE_BOUND"):
                continue
            if child.get("segments"):
                place_bound_shapes.append(
                    _shape_polygon(child, dbu_per_mm, chord_error_mm)
                )
        if place_bound_shapes:
            footprint = unary_union(place_bound_shapes)
            footprint_source = "package_place_bound"
        else:
            footprint = box(*bbox_mm)
            footprint_source = "symbol_b_box"
        footprint_bounds = footprint.bounds
        center_mm = dbu_to_mm(raw_symbol["xy"], dbu_per_mm)
        symbols[refdes] = SymbolGeometry(
            refdes=refdes,
            side=side,
            center_mm=(float(center_mm[0]), float(center_mm[1])),
            width_mm=float(footprint_bounds[2] - footprint_bounds[0]),
            height_mm=float(footprint_bounds[3] - footprint_bounds[1]),
            rotation=float(raw_symbol.get("rotation", 0.0)),
            footprint_mm=footprint,
            footprint_source=footprint_source,
        )

    side_counts = {}
    regions = {}
    source_index = 0
    for region_group in data.get("component_placeable_regions", []):
        side = region_group["placement_side"].upper()
        for shape in region_group.get("shapes", []):
            side_index = side_counts.get(side, 0)
            region_id = "%s_%d" % (side.lower(), side_index)
            side_counts[side] = side_index + 1
            regions[region_id] = RegionGeometry(
                region_id=region_id,
                side=side,
                polygon_mm=_shape_polygon(shape, dbu_per_mm, chord_error_mm),
                source_index=source_index,
            )
            source_index += 1

    if not regions:
        raise ValueError(
            "component_placeable_regions is empty; refusing board-bbox fallback"
        )
    return PCBGeometry(
        schema=metadata["schema"],
        dbu_per_mm=dbu_per_mm,
        symbols=symbols,
        regions=regions,
    )


def conservative_region_boxes(region, grid: float):
    """Rasterize a polygon into non-overlapping boxes fully covered by it."""
    if grid <= 0:
        raise ValueError("grid must be positive")
    min_x, min_y, max_x, max_y = region.bounds
    start_x = math.floor(min_x / grid) * grid
    start_y = math.floor(min_y / grid) * grid
    count_x = int(math.ceil((max_x - start_x) / grid))
    count_y = int(math.ceil((max_y - start_y) / grid))
    boxes = []
    for row in range(count_y):
        y0 = start_y + row * grid
        run_start = None
        for column in range(count_x + 1):
            x0 = start_x + column * grid
            covered = column < count_x and region.covers(
                box(x0, y0, x0 + grid, y0 + grid)
            )
            if covered and run_start is None:
                run_start = x0
            elif not covered and run_start is not None:
                boxes.append((run_start, y0, x0, y0 + grid))
                run_start = None
    return boxes
