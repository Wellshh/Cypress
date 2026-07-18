#!/usr/bin/env python3
"""Validate and convert a manual PCB placement into the M336 Bookshelf frame."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


class BaselineCompatibilityError(ValueError):
    """Raised when the manual board is not the same placement problem."""


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n")


def _load_json(path):
    with Path(path).open() as stream:
        return json.load(stream)


def _dbu_per_mm(data):
    value = float(data.get("export_meta", {}).get("dbu_per_user_unit", 0))
    if not math.isfinite(value) or value <= 0:
        raise BaselineCompatibilityError("invalid export_meta.dbu_per_user_unit")
    return value


def _named_symbols(data, label):
    symbols = {}
    for symbol in data.get("symbols", []):
        refdes = str(symbol.get("refdes", "")).strip()
        if not refdes:
            continue
        if refdes in symbols:
            raise BaselineCompatibilityError(
                "%s contains duplicate refdes %s" % (label, refdes)
            )
        symbols[refdes] = symbol
    return symbols


def _round_mm(value, dbu_per_mm):
    return round(float(value) / dbu_per_mm, 9)


def _relative_bbox(bbox, center, dbu_per_mm):
    return tuple(
        _round_mm(value - center[index % 2], dbu_per_mm)
        for index, value in enumerate(bbox)
    )


def _shape_signature(shape, center, dbu_per_mm):
    vertices = []
    for vertex in shape.get("vertices", []):
        point = vertex[0]
        arc = vertex[1] if len(vertex) > 1 else 0
        vertices.append(
            (
                _round_mm(point[0] - center[0], dbu_per_mm),
                _round_mm(point[1] - center[1], dbu_per_mm),
                _round_mm(arc, dbu_per_mm),
            )
        )
    voids = sorted(
        (_shape_signature(void, center, dbu_per_mm) for void in shape.get("voids", [])),
        key=repr,
    )
    return (
        bool(shape.get("is_hole", False)),
        bool(shape.get("is_rect", False)),
        _relative_bbox(shape.get("b_box", [*center, *center]), center, dbu_per_mm),
        tuple(vertices),
        tuple(voids),
    )


def _footprint_signature(symbol, dbu_per_mm):
    side = str(symbol.get("layer", "")).upper()
    expected_layer = "PLACE_BOUND_%s" % side
    center = symbol["xy"]
    shapes = [
        child
        for child in symbol.get("children", [])
        if str(child.get("obj_type", "")).lower() == "shape"
        and (
            expected_layer in str(child.get("layer", "")).upper()
            or str(child.get("layer", "")).upper().endswith("/PLACE_BOUND")
        )
    ]
    if not shapes:
        return ("bbox", _relative_bbox(symbol["b_box"], center, dbu_per_mm))
    signatures = sorted(
        (_shape_signature(shape, center, dbu_per_mm) for shape in shapes), key=repr
    )
    return ("place_bound", tuple(signatures))


def _pin_signatures(symbol, dbu_per_mm):
    signatures = {}
    center = symbol["xy"]
    for pin in symbol.get("pins", []):
        key = (str(pin.get("number", "")), str(pin.get("name", "")))
        if key in signatures:
            raise BaselineCompatibilityError(
                "%s has duplicate pin identity %s" % (symbol["refdes"], key)
            )
        rel_xy = pin.get("rel_xy")
        if rel_xy is None:
            rel_xy = [pin["xy"][0] - center[0], pin["xy"][1] - center[1]]
        signatures[key] = (
            str(pin.get("net", "")).strip(),
            tuple(_round_mm(value, dbu_per_mm) for value in rel_xy),
            round(float(pin.get("rel_rotation", 0.0)), 9),
            tuple(pin.get("start_end") or []),
            bool(pin.get("is_through", False)),
        )
    return signatures


def _net_topology(symbols):
    topology = defaultdict(list)
    for refdes, symbol in symbols.items():
        for pin in symbol.get("pins", []):
            net = str(pin.get("net", "")).strip()
            if net:
                topology[net].append(
                    (refdes, str(pin.get("number", "")), str(pin.get("name", "")))
                )
    return {name: tuple(sorted(pins)) for name, pins in topology.items()}


def _net_names(data):
    names = [str(net.get("name", "")).strip() for net in data.get("nets", [])]
    if any(not name for name in names) or len(names) != len(set(names)):
        raise BaselineCompatibilityError("net names must be non-empty and unique")
    return tuple(sorted(names))


def _record_mismatch(mismatches, refdes, field, source, baseline):
    mismatches.append(
        {
            "refdes": refdes,
            "field": field,
            "source": repr(source),
            "baseline": repr(baseline),
        }
    )


def validate_compatibility(source, baseline):
    """Prove that two JSON files differ only in absolute component placement."""
    source_dbu = _dbu_per_mm(source)
    baseline_dbu = _dbu_per_mm(baseline)
    source_symbols = _named_symbols(source, "source")
    baseline_symbols = _named_symbols(baseline, "baseline")
    if set(source_symbols) != set(baseline_symbols):
        missing = sorted(set(source_symbols) - set(baseline_symbols))
        extra = sorted(set(baseline_symbols) - set(source_symbols))
        raise BaselineCompatibilityError(
            "refdes mismatch: missing=%s extra=%s" % (missing, extra)
        )

    mismatches = []
    moved_distances = []
    for refdes in sorted(source_symbols):
        source_symbol = source_symbols[refdes]
        baseline_symbol = baseline_symbols[refdes]
        scalar_fields = {
            "name": str,
            "type": str,
            "layer": lambda value: str(value).upper(),
            "rotation": lambda value: round(float(value), 9),
            "is_mirrored": bool,
        }
        for field, normalize in scalar_fields.items():
            source_value = normalize(source_symbol.get(field, False if field == "is_mirrored" else ""))
            baseline_value = normalize(baseline_symbol.get(field, False if field == "is_mirrored" else ""))
            if source_value != baseline_value:
                _record_mismatch(
                    mismatches, refdes, field, source_value, baseline_value
                )

        for field in ("package", "device_type"):
            source_value = source_symbol.get("component", {}).get(field)
            baseline_value = baseline_symbol.get("component", {}).get(field)
            if source_value != baseline_value:
                _record_mismatch(
                    mismatches, refdes, "component.%s" % field, source_value, baseline_value
                )

        source_footprint = _footprint_signature(source_symbol, source_dbu)
        baseline_footprint = _footprint_signature(baseline_symbol, baseline_dbu)
        if source_footprint != baseline_footprint:
            _record_mismatch(
                mismatches, refdes, "place_bound", source_footprint, baseline_footprint
            )

        source_pins = _pin_signatures(source_symbol, source_dbu)
        baseline_pins = _pin_signatures(baseline_symbol, baseline_dbu)
        if source_pins != baseline_pins:
            _record_mismatch(mismatches, refdes, "pins", source_pins, baseline_pins)

        source_xy = [value / source_dbu for value in source_symbol["xy"]]
        baseline_xy = [value / baseline_dbu for value in baseline_symbol["xy"]]
        moved_distances.append(math.dist(source_xy, baseline_xy))

    source_topology = _net_topology(source_symbols)
    baseline_topology = _net_topology(baseline_symbols)
    if source_topology != baseline_topology:
        _record_mismatch(
            mismatches, "<design>", "net_topology", source_topology, baseline_topology
        )
    source_net_names = _net_names(source)
    baseline_net_names = _net_names(baseline)
    if source_net_names != baseline_net_names:
        _record_mismatch(
            mismatches, "<design>", "net_names", source_net_names, baseline_net_names
        )

    if mismatches:
        sample = "; ".join(
            "%s:%s" % (row["refdes"], row["field"]) for row in mismatches[:12]
        )
        raise BaselineCompatibilityError(
            "%d compatibility mismatches (%s)" % (len(mismatches), sample)
        )

    connected_pin_count = sum(len(pins) for pins in source_topology.values())
    return {
        "compatible": True,
        "named_symbol_count": len(source_symbols),
        "symbol_pin_count": sum(
            len(symbol.get("pins", [])) for symbol in source_symbols.values()
        ),
        "connected_pin_count": connected_pin_count,
        "net_count": len(source_net_names),
        "moved_component_count": sum(distance > 1e-12 for distance in moved_distances),
        "unchanged_component_count": sum(
            distance <= 1e-12 for distance in moved_distances
        ),
        "max_center_displacement_mm": max(moved_distances, default=0.0),
    }


def direct_hpwl_mm(data):
    """Compute an independent source-coordinate HPWL cross-check."""
    dbu_per_mm = _dbu_per_mm(data)
    symbols = _named_symbols(data, "geometry")
    points_by_net = defaultdict(list)
    for symbol in symbols.values():
        for pin in symbol.get("pins", []):
            net = str(pin.get("net", "")).strip()
            if net:
                points_by_net[net].append(
                    tuple(float(value) / dbu_per_mm for value in pin["xy"])
                )
    return sum(
        max(point[0] for point in points) - min(point[0] for point in points)
        + max(point[1] for point in points) - min(point[1] for point in points)
        for points in points_by_net.values()
        if points
    )


def _parse_nodes(path):
    nodes = {}
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[0] in {"UCLA", "NumNodes", "NumTerminals"}:
            continue
        try:
            width, height = int(fields[1]), int(fields[2])
        except ValueError:
            continue
        if fields[0] in nodes or width <= 0 or height <= 0:
            raise BaselineCompatibilityError("invalid node row: %s" % line)
        nodes[fields[0]] = (width, height)
    return nodes


def _safe_token(value):
    return "_".join(str(value).split())


def _parse_bookshelf_nets(path):
    pins_by_net = defaultdict(list)
    current_net = None
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "NetDegree":
            if len(fields) < 4:
                raise BaselineCompatibilityError("invalid NetDegree row: %s" % line)
            current_net = fields[3]
            continue
        if current_net is None or fields[0] in {"UCLA", "NumNets", "NumPins"}:
            continue
        if len(fields) < 5 or fields[2] != ":":
            raise BaselineCompatibilityError("invalid net pin row: %s" % line)
        pins_by_net[current_net].append(
            (fields[0], float(fields[3]), float(fields[4]))
        )
    return dict(pins_by_net)


def validate_bookshelf_pin_alignment(data, nets_path, site_mm):
    """Reconstruct board pin coordinates through PlaceIO's N/FN convention."""
    dbu_per_mm = _dbu_per_mm(data)
    symbols = _named_symbols(data, "baseline")
    actual = _parse_bookshelf_nets(nets_path)
    expected = defaultdict(list)
    for refdes in sorted(symbols):
        symbol = symbols[refdes]
        side = str(symbol["layer"]).upper()
        center_x = float(symbol["xy"][0]) / dbu_per_mm
        center_y = float(symbol["xy"][1]) / dbu_per_mm
        for pin in symbol.get("pins", []):
            net = str(pin.get("net", "")).strip()
            if not net:
                continue
            pin_x = float(pin["xy"][0]) / dbu_per_mm
            pin_y = float(pin["xy"][1]) / dbu_per_mm
            offset_x = (pin_x - center_x) / site_mm
            offset_y = (pin_y - center_y) / site_mm
            if side == "BOTTOM":
                offset_x = -offset_x
            expected[_safe_token(net)].append(
                (refdes, offset_x, offset_y, side, center_x, center_y, pin_x, pin_y)
            )

    if set(actual) != set(expected):
        raise BaselineCompatibilityError(
            "Bookshelf net mismatch: missing=%s extra=%s"
            % (sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected)))
        )

    residuals = []
    for net in sorted(expected):
        actual_pins = actual[net]
        expected_pins = expected[net]
        if len(actual_pins) != len(expected_pins):
            raise BaselineCompatibilityError(
                "%s pin count mismatch: %d != %d"
                % (net, len(actual_pins), len(expected_pins))
            )
        for actual_pin, expected_pin in zip(actual_pins, expected_pins):
            refdes, encoded_x, encoded_y = actual_pin
            (
                expected_refdes,
                expected_x,
                expected_y,
                side,
                center_x,
                center_y,
                pin_x,
                pin_y,
            ) = expected_pin
            if refdes != expected_refdes or not math.isclose(
                encoded_x, expected_x, abs_tol=1e-6
            ) or not math.isclose(encoded_y, expected_y, abs_tol=1e-6):
                raise BaselineCompatibilityError(
                    "%s/%s encoded pin offset mismatch" % (net, expected_refdes)
                )
            decoded_x = -encoded_x if side == "BOTTOM" else encoded_x
            reconstructed = (
                center_x + decoded_x * site_mm,
                center_y + encoded_y * site_mm,
            )
            residuals.append(math.dist(reconstructed, (pin_x, pin_y)))

    max_residual = max(residuals, default=0.0)
    if max_residual > 1e-7:
        raise BaselineCompatibilityError(
            "Bookshelf pin residual %.9g mm exceeds tolerance" % max_residual
        )
    return {
        "connected_pin_count": len(residuals),
        "max_residual_mm": max_residual,
    }


def prepare_baseline(source_path, baseline_path, bookshelf_dir):
    source_path = Path(source_path)
    baseline_path = Path(baseline_path)
    bookshelf_dir = Path(bookshelf_dir)
    source = _load_json(source_path)
    baseline = _load_json(baseline_path)
    compatibility = validate_compatibility(source, baseline)

    manifest_path = bookshelf_dir / "manifest.json"
    nodes_path = bookshelf_dir / "m336.nodes"
    if not manifest_path.exists() or not nodes_path.exists():
        raise FileNotFoundError("generate the M336 Bookshelf database first")
    manifest = _load_json(manifest_path)
    site_mm = float(manifest["site_mm"])
    origin_x, origin_y = (float(value) for value in manifest["origin_mm"])
    layout_width, layout_height = (int(value) for value in manifest["layout_sites"])
    nodes = _parse_nodes(nodes_path)
    symbols = _named_symbols(baseline, "baseline")
    if set(nodes) != set(symbols):
        raise BaselineCompatibilityError(
            "Bookshelf node/refdes mismatch: missing=%s extra=%s"
            % (sorted(set(symbols) - set(nodes)), sorted(set(nodes) - set(symbols)))
        )

    dbu_per_mm = _dbu_per_mm(baseline)
    placement_rows = []
    for refdes in sorted(symbols):
        symbol = symbols[refdes]
        width, height = nodes[refdes]
        center_x = (float(symbol["xy"][0]) / dbu_per_mm - origin_x) / site_mm
        center_y = (float(symbol["xy"][1]) / dbu_per_mm - origin_y) / site_mm
        lower_left_x = center_x - width / 2
        lower_left_y = center_y - height / 2
        if (
            lower_left_x < -1e-6
            or lower_left_y < -1e-6
            or lower_left_x + width > layout_width + 1e-6
            or lower_left_y + height > layout_height + 1e-6
        ):
            raise BaselineCompatibilityError(
                "%s falls outside generated placement rows" % refdes
            )
        orientation = "FN" if str(symbol["layer"]).upper() == "BOTTOM" else "N"
        placement_rows.append(
            "%s %.8f %.8f : %s"
            % (refdes, lower_left_x, lower_left_y, orientation)
        )

    baseline_pl = bookshelf_dir / "m336.baseline.pl"
    baseline_aux = bookshelf_dir / "m336.baseline.aux"
    _write(baseline_pl, "\n".join(["UCLA pl 1.0", ""] + placement_rows))
    _write(
        baseline_aux,
        "RowBasedPlacement : m336.nodes m336.nets m336.baseline.pl m336.scl",
    )
    report = {
        "schema": "m336_manual_baseline_manifest_v1",
        "source_geometry": str(source_path),
        "baseline_geometry": str(baseline_path),
        "bookshelf_manifest": str(manifest_path),
        "baseline_aux": str(baseline_aux),
        "baseline_pl": str(baseline_pl),
        "site_mm": site_mm,
        "origin_mm": [origin_x, origin_y],
        "compatibility": compatibility,
        "pin_alignment": validate_bookshelf_pin_alignment(
            baseline, bookshelf_dir / "m336.nets", site_mm
        ),
        "direct_hpwl_mm": {
            "source": direct_hpwl_mm(source),
            "baseline": direct_hpwl_mm(baseline),
        },
        "sha256": {
            "source_geometry": _sha256(source_path),
            "baseline_geometry": _sha256(baseline_path),
            "bookshelf_manifest": _sha256(manifest_path),
            "baseline_aux": _sha256(baseline_aux),
            "baseline_pl": _sha256(baseline_pl),
        },
    }
    _write(
        bookshelf_dir / "baseline_manifest.json",
        json.dumps(report, indent=2, sort_keys=True),
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="experiments/m336/input/pcb_geometry_keepin.json",
    )
    parser.add_argument("--baseline", default="pcb_geometry.json")
    parser.add_argument("--bookshelf-dir", default="results/m336/bookshelf")
    args = parser.parse_args()
    report = prepare_baseline(args.source, args.baseline, args.bookshelf_dir)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
