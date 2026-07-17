#!/usr/bin/env python3
"""Generate a deterministic minimal Bookshelf benchmark from M336 geometry."""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def _safe_token(value):
    return "_".join(str(value).split())


def _write(path, content):
    path.write_text(content.rstrip() + "\n")


def generate(geometry_path, cluster_path, output_dir, site_mm):
    geometry_path = Path(geometry_path)
    cluster_path = Path(cluster_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(geometry_path.read_text())
    clusters = json.loads(cluster_path.read_text())
    dbu_per_mm = float(data["export_meta"]["dbu_per_user_unit"])
    if site_mm <= 0:
        raise ValueError("site-mm must be positive")

    symbols = {
        row["refdes"]: row for row in data["symbols"] if row.get("refdes", "").strip()
    }
    if len(symbols) != 140:
        raise ValueError("expected 140 unique named symbols, found %d" % len(symbols))
    clustered_members = {
        member for cluster in clusters["clusters"] for member in cluster["members"]
    }
    missing = clustered_members - symbols.keys()
    if missing:
        raise ValueError("cluster members missing from symbols: %s" % sorted(missing))

    footprint_bboxes = {}
    footprint_sources = defaultdict(int)
    for refdes, symbol in symbols.items():
        side = symbol["layer"].upper()
        expected_layer = "PLACE_BOUND_%s" % side
        place_bounds = [
            child["b_box"]
            for child in symbol.get("children", [])
            if child.get("obj_type", "").lower() == "shape"
            and (
                expected_layer in child.get("layer", "").upper()
                or child.get("layer", "").upper().endswith("/PLACE_BOUND")
            )
        ]
        if place_bounds:
            footprint_bboxes[refdes] = [
                min(row[0] for row in place_bounds),
                min(row[1] for row in place_bounds),
                max(row[2] for row in place_bounds),
                max(row[3] for row in place_bounds),
            ]
            footprint_sources["package_place_bound"] += 1
        else:
            footprint_bboxes[refdes] = symbol["b_box"]
            footprint_sources["symbol_b_box"] += 1

    outline_bbox_dbu = data["design_outline"]["b_box"]
    container_bbox_dbu = [
        min([outline_bbox_dbu[0]] + [row[0] for row in footprint_bboxes.values()]),
        min([outline_bbox_dbu[1]] + [row[1] for row in footprint_bboxes.values()]),
        max([outline_bbox_dbu[2]] + [row[2] for row in footprint_bboxes.values()]),
        max([outline_bbox_dbu[3]] + [row[3] for row in footprint_bboxes.values()]),
    ]
    container_bbox = [value / dbu_per_mm for value in container_bbox_dbu]
    # Ceiled node dimensions can extend half a site past the source bounds.
    # Keep one full guard site around the generated global placement rows.
    origin_x = math.floor(container_bbox[0] / site_mm) * site_mm - site_mm
    origin_y = math.floor(container_bbox[1] / site_mm) * site_mm - site_mm
    width_sites = int(math.ceil((container_bbox[2] - origin_x) / site_mm)) + 1
    height_sites = int(math.ceil((container_bbox[3] - origin_y) / site_mm)) + 1

    nodes = []
    placements = []
    centers = {}
    for refdes in sorted(symbols):
        symbol = symbols[refdes]
        bbox_dbu = footprint_bboxes[refdes]
        bbox = [value / dbu_per_mm for value in bbox_dbu]
        center_mm = tuple(value / dbu_per_mm for value in symbol["xy"])
        width = max(1, int(math.ceil((bbox[2] - bbox[0]) / site_mm)))
        height = max(1, int(math.ceil((bbox[3] - bbox[1]) / site_mm)))
        center = (
            (center_mm[0] - origin_x) / site_mm,
            (center_mm[1] - origin_y) / site_mm,
        )
        centers[refdes] = center
        lower_left = (center[0] - width / 2, center[1] - height / 2)
        orientation = "FN" if symbol["layer"].upper() == "BOTTOM" else "N"
        nodes.append("%s %d %d" % (refdes, width, height))
        placements.append(
            "%s %.8f %.8f : %s"
            % (refdes, lower_left[0], lower_left[1], orientation)
        )

    pins_by_net = defaultdict(list)
    for refdes in sorted(symbols):
        for pin in symbols[refdes].get("pins", []):
            net = pin.get("net", "").strip()
            if not net:
                continue
            pin_xy = [value / dbu_per_mm for value in pin["xy"]]
            pin_center = (
                (pin_xy[0] - origin_x) / site_mm,
                (pin_xy[1] - origin_y) / site_mm,
            )
            offset_x = pin_center[0] - centers[refdes][0]
            offset_y = pin_center[1] - centers[refdes][1]
            pins_by_net[net].append((refdes, offset_x, offset_y))

    benchmark = "m336"
    _write(
        output_dir / (benchmark + ".aux"),
        "RowBasedPlacement : m336.nodes m336.nets m336.pl m336.scl",
    )
    _write(
        output_dir / (benchmark + ".nodes"),
        "\n".join(
            [
                "UCLA nodes 1.0",
                "",
                "NumNodes : %d" % len(nodes),
                "NumTerminals : 0",
                "",
            ]
            + nodes
        ),
    )
    _write(
        output_dir / (benchmark + ".pl"),
        "\n".join(["UCLA pl 1.0", ""] + placements),
    )

    net_rows = []
    pin_count = 0
    for net_name in sorted(pins_by_net):
        pins = pins_by_net[net_name]
        pin_count += len(pins)
        net_rows.append("NetDegree : %d %s" % (len(pins), _safe_token(net_name)))
        net_rows.extend(
            "\t%s I : %.8f %.8f" % pin for pin in pins
        )
    _write(
        output_dir / (benchmark + ".nets"),
        "\n".join(
            [
                "UCLA nets 1.0",
                "",
                "NumNets : %d" % len(pins_by_net),
                "NumPins : %d" % pin_count,
                "",
            ]
            + net_rows
        ),
    )

    rows = []
    for row in range(height_sites):
        rows.extend(
            [
                "CoreRow Horizontal",
                "    Coordinate   : %d" % row,
                "    Height       : 1",
                "    Sitewidth    : 1",
                "    Sitespacing  : 1",
                "    Siteorient   : %d" % (row % 2),
                "    Sitesymmetry : 1",
                "    SubrowOrigin : 0  NumSites : %d" % width_sites,
                "End",
                "",
            ]
        )
    _write(
        output_dir / (benchmark + ".scl"),
        "\n".join(
            ["UCLA scl 1.0", "", "NumRows : %d" % height_sites, ""] + rows
        ),
    )

    manifest = {
        "schema": "m336_generated_bookshelf_v1",
        "source_geometry": str(geometry_path),
        "source_clusters": str(cluster_path),
        "site_mm": site_mm,
        "origin_mm": [origin_x, origin_y],
        "layout_sites": [width_sites, height_sites],
        "node_count": len(nodes),
        "net_count": len(pins_by_net),
        "pin_count": pin_count,
        "clustered_member_count": len(clustered_members),
        "footprint_sources": dict(sorted(footprint_sources.items())),
    }
    _write(output_dir / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--geometry",
        default="experiments/m336/input/pcb_geometry_keepin.json",
    )
    parser.add_argument(
        "--clusters", default="experiments/m336/input/m336_clusters.json"
    )
    parser.add_argument("--output", default="results/m336/bookshelf")
    parser.add_argument("--site-mm", type=float, default=0.1)
    args = parser.parse_args()
    manifest = generate(args.geometry, args.clusters, args.output, args.site_mm)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
