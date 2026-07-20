#!/usr/bin/env python3
"""Build a deterministic M336 guide from selected target components."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path


SCHEMA = "m336_hybrid_guide_v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validated_centers(data: dict, label: str) -> dict[str, list[float]]:
    selected_sites = data.get("selected_sites")
    if not isinstance(selected_sites, dict) or not selected_sites:
        raise ValueError(f"{label} is missing selected_sites")

    centers = {}
    for refdes, row in selected_sites.items():
        center = row.get("center") if isinstance(row, dict) else None
        if (
            not isinstance(refdes, str)
            or not refdes
            or not isinstance(center, list)
            or len(center) != 2
            or not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in center
            )
        ):
            raise ValueError(f"{label} has an invalid center for {refdes!r}")
        centers[refdes] = [float(center[0]), float(center[1])]
    return centers


def build_hybrid_guide(
    source_path: Path,
    target_path: Path,
    selected_refdes: list[str],
) -> dict:
    """Use target centers only for selected components and source elsewhere."""
    source_path = Path(source_path)
    target_path = Path(target_path)
    source = json.loads(source_path.read_text())
    target = json.loads(target_path.read_text())
    source_centers = _validated_centers(source, "source")
    target_centers = _validated_centers(target, "target")
    if set(source_centers) != set(target_centers):
        missing = sorted(set(source_centers) - set(target_centers))
        extra = sorted(set(target_centers) - set(source_centers))
        raise ValueError(
            f"guide component identities differ; missing={missing}, extra={extra}"
        )
    if not selected_refdes:
        raise ValueError("at least one target refdes is required")
    if len(selected_refdes) != len(set(selected_refdes)):
        raise ValueError("target refdes must be unique")
    unknown = sorted(set(selected_refdes) - set(source_centers))
    if unknown:
        raise ValueError("unknown target refdes: " + ", ".join(unknown))

    selected = frozenset(selected_refdes)
    selected_sites = {}
    displacements = []
    for refdes in sorted(source_centers):
        source_center = source_centers[refdes]
        target_center = target_centers[refdes]
        center = target_center if refdes in selected else source_center
        selected_sites[refdes] = {"center": list(center)}
        if refdes in selected:
            distance = math.dist(source_center, target_center)
            if distance == 0.0:
                raise ValueError(f"target center is unchanged for {refdes}")
            displacements.append(
                {
                    "refdes": refdes,
                    "source_center": list(source_center),
                    "target_center": list(target_center),
                    "distance": distance,
                }
            )

    return {
        "schema": SCHEMA,
        "source_json": str(source_path),
        "source_sha256": _sha256_file(source_path),
        "target_json": str(target_path),
        "target_sha256": _sha256_file(target_path),
        "selected_refdes": sorted(selected),
        "displacements": displacements,
        "selected_sites": selected_sites,
    }


def write_json_atomic(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--refdes",
        action="append",
        required=True,
        help="Component to take from the target; repeat for each component.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    guide = build_hybrid_guide(args.source, args.target, args.refdes)
    write_json_atomic(args.output, guide)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "selected_refdes": guide["selected_refdes"],
                "source_sha256": guide["source_sha256"],
                "target_sha256": guide["target_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
