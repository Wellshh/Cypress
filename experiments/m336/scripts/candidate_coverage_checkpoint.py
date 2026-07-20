#!/usr/bin/env python3
"""Export a portable M336 exact-site candidate-coverage reference."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AUDIT_SCHEMA = "m336_candidate_coverage_v1"
CHECKPOINT_SCHEMA = "m336_candidate_coverage_checkpoint_v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finite_nonnegative(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _validate_target_domain_row(row, scale, site_tolerance):
    boolean_fields = (
        "target_contained_in_keepin",
        "exact_keepin_target_site_present",
        "exact_obstacle_free_target_site_present",
    )
    distance_fields = (
        "minimum_keepin_target_distance",
        "minimum_keepin_target_distance_mm",
        "minimum_obstacle_free_target_distance",
        "minimum_obstacle_free_target_distance_mm",
        "target_fixed_obstacle_overlap_area",
        "target_fixed_obstacle_overlap_area_mm2",
    )
    if any(type(row.get(field)) is not bool for field in boolean_fields) or any(
        not _finite_nonnegative(row.get(field)) for field in distance_fields
    ):
        raise ValueError("candidate target domain metrics are invalid")
    keepin_count = row.get("keepin_candidate_count")
    obstacle_free_count = row.get("obstacle_free_candidate_count")
    keepin_index = row.get("nearest_keepin_region_index")
    obstacle_free_index = row.get("nearest_obstacle_free_region_index")
    centers = (
        row.get("nearest_keepin_center"),
        row.get("nearest_obstacle_free_center"),
    )
    if (
        not isinstance(keepin_count, int)
        or isinstance(keepin_count, bool)
        or keepin_count <= 0
        or not isinstance(obstacle_free_count, int)
        or isinstance(obstacle_free_count, bool)
        or obstacle_free_count <= 0
        or obstacle_free_count > keepin_count
        or not isinstance(keepin_index, int)
        or isinstance(keepin_index, bool)
        or keepin_index < 0
        or keepin_index >= keepin_count
        or not isinstance(obstacle_free_index, int)
        or isinstance(obstacle_free_index, bool)
        or obstacle_free_index < 0
        or obstacle_free_index >= keepin_count
        or any(
            not isinstance(center, list)
            or len(center) != 2
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in center
            )
            for center in centers
        )
    ):
        raise ValueError("candidate target domain identity is invalid")
    if not math.isclose(
        row["minimum_keepin_target_distance_mm"],
        row["minimum_keepin_target_distance"] / scale,
        abs_tol=1e-12,
    ) or not math.isclose(
        row["minimum_obstacle_free_target_distance_mm"],
        row["minimum_obstacle_free_target_distance"] / scale,
        abs_tol=1e-12,
    ):
        raise ValueError("candidate target domain distance scale changed")
    if row["exact_keepin_target_site_present"] != (
        row["minimum_keepin_target_distance"] <= site_tolerance
    ) or row["exact_obstacle_free_target_site_present"] != (
        row["minimum_obstacle_free_target_distance"] <= site_tolerance
    ):
        raise ValueError("candidate target domain exactness is inconsistent")

    overlaps = row.get("target_fixed_obstacle_overlaps")
    refdes = row.get("target_fixed_obstacle_refdes")
    if (
        not isinstance(overlaps, list)
        or not isinstance(refdes, list)
        or refdes != sorted(refdes)
        or len(set(refdes)) != len(refdes)
        or row.get("target_fixed_obstacle_overlap_count") != len(overlaps)
        or refdes != [overlap.get("refdes") for overlap in overlaps]
    ):
        raise ValueError("candidate target obstacle identity is invalid")
    for overlap in overlaps:
        if (
            not isinstance(overlap.get("refdes"), str)
            or not overlap["refdes"]
            or not _finite_nonnegative(overlap.get("area"))
            or overlap["area"] <= 0
            or not _finite_nonnegative(overlap.get("area_mm2"))
            or not math.isclose(
                overlap["area_mm2"],
                overlap["area"] / scale**2,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("candidate target obstacle metric is invalid")
    if not math.isclose(
        row["target_fixed_obstacle_overlap_area"],
        sum(overlap["area"] for overlap in overlaps),
        abs_tol=1e-12,
    ) or not math.isclose(
        row["target_fixed_obstacle_overlap_area_mm2"],
        sum(overlap["area_mm2"] for overlap in overlaps),
        abs_tol=1e-12,
    ):
        raise ValueError("candidate target obstacle totals are inconsistent")


def _resolve_result_dependency(result_path: Path, value) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = result_path.parent / path
    return path.resolve()


def _portable_dependency(result_path, repository_root, value, label):
    path = _resolve_result_dependency(result_path, value)
    if not path.is_file():
        raise FileNotFoundError(f"candidate coverage {label} is missing: {path}")
    try:
        relative = path.relative_to(repository_root)
    except ValueError as error:
        raise ValueError(
            f"candidate coverage {label} is outside the repository: {path}"
        ) from error
    return {
        "path": relative.as_posix(),
        "sha256": _sha256_file(path),
    }


def _validate_audit(audit):
    if not isinstance(audit, dict) or not audit.get("enabled"):
        raise ValueError("candidate coverage audit is not enabled")
    if audit.get("schema") != AUDIT_SCHEMA:
        raise ValueError("candidate coverage audit schema is unsupported")
    scale = audit.get("coordinate_units_per_mm")
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("candidate coverage coordinate scale is invalid")
    site_tolerance = audit.get("site_tolerance")
    if not _finite_nonnegative(site_tolerance):
        raise ValueError("candidate coverage site tolerance is invalid")
    target_domain_enabled = audit.get(
        "target_domain_coverage_enabled", False
    )
    if type(target_domain_enabled) is not bool:
        raise ValueError("candidate target domain mode is invalid")
    components = audit.get("components")
    scope = audit.get("scope_refdes")
    if (
        not isinstance(components, dict)
        or not components
        or scope != sorted(components)
        or audit.get("scope_count") != len(components)
    ):
        raise ValueError("candidate coverage component scope is invalid")
    guide_count = audit.get("guide_count")
    guides = audit.get("guides")
    if (
        not isinstance(guide_count, int)
        or guide_count <= 0
        or not isinstance(guides, list)
        or [row.get("guide_index") for row in guides]
        != list(range(guide_count))
    ):
        raise ValueError("candidate coverage guide summary is invalid")

    candidate_count = 0
    attributed_counts = [0] * guide_count
    exact_target_counts = [0] * guide_count
    exact_keepin_counts = [0] * guide_count
    exact_obstacle_free_counts = [0] * guide_count
    continuous_keepin_counts = [0] * guide_count
    fixed_obstacle_counts = [0] * guide_count
    for refdes, component in components.items():
        indices = component.get("candidate_region_indices")
        rows = component.get("guide_coverage")
        if (
            component.get("refdes") != refdes
            or not isinstance(indices, list)
            or not indices
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in indices
            )
            or len(set(indices)) != len(indices)
            or component.get("candidate_count") != len(indices)
            or component.get("candidate_region_indices_sha256")
            != _sha256_json(indices)
            or not isinstance(component.get("domain_sha256"), str)
            or len(component["domain_sha256"]) != 64
            or not isinstance(rows, list)
            or [row.get("guide_index") for row in rows]
            != list(range(guide_count))
        ):
            raise ValueError(
                f"candidate coverage component {refdes} is invalid"
            )
        component_attributed = 0
        for guide_index, row in enumerate(rows):
            count = row.get("attributed_candidate_count")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError("candidate coverage attribution is invalid")
            if type(row.get("exact_target_site_present")) is not bool:
                raise ValueError(
                    "candidate selected target exactness is invalid"
                )
            if not _finite_nonnegative(
                row.get("minimum_target_distance")
            ) or not _finite_nonnegative(
                row.get("minimum_target_distance_mm")
            ):
                raise ValueError("candidate selected target distance is invalid")
            if not math.isclose(
                row["minimum_target_distance_mm"],
                row["minimum_target_distance"] / scale,
                abs_tol=1e-12,
            ) or row["exact_target_site_present"] != (
                row["minimum_target_distance"] <= site_tolerance
            ):
                raise ValueError("candidate selected target replay failed")
            component_attributed += count
            attributed_counts[guide_index] += count
            exact_target_counts[guide_index] += int(
                row["exact_target_site_present"]
            )
            has_domain = "exact_obstacle_free_target_site_present" in row
            if has_domain != target_domain_enabled:
                raise ValueError(
                    "candidate target domain coverage is incomplete"
                )
            if target_domain_enabled:
                _validate_target_domain_row(row, scale, site_tolerance)
                exact_keepin_counts[guide_index] += int(
                    row["exact_keepin_target_site_present"]
                )
                exact_obstacle_free_counts[guide_index] += int(
                    row["exact_obstacle_free_target_site_present"]
                )
                continuous_keepin_counts[guide_index] += int(
                    row["target_contained_in_keepin"]
                )
                fixed_obstacle_counts[guide_index] += int(
                    row["target_fixed_obstacle_overlap_count"] > 0
                )
        if component_attributed != len(indices):
            raise ValueError(
                f"candidate coverage attribution does not cover {refdes}"
            )
        candidate_count += len(indices)
    if audit.get("candidate_count") != candidate_count:
        raise ValueError("candidate coverage total count is invalid")
    if [row.get("attributed_candidate_count") for row in guides] != attributed_counts:
        raise ValueError("candidate coverage guide attribution is inconsistent")
    if [
        row.get("exact_target_component_count") for row in guides
    ] != exact_target_counts:
        raise ValueError("candidate coverage exact target totals changed")
    if target_domain_enabled and (
        [
            row.get("exact_keepin_target_component_count")
            for row in guides
        ]
        != exact_keepin_counts
        or [
            row.get("exact_obstacle_free_target_component_count")
            for row in guides
        ]
        != exact_obstacle_free_counts
        or [
            row.get("continuous_keepin_target_component_count")
            for row in guides
        ]
        != continuous_keepin_counts
        or [
            row.get("fixed_obstacle_target_component_count")
            for row in guides
        ]
        != fixed_obstacle_counts
    ):
        raise ValueError("candidate target domain guide totals changed")

    for row in audit.get("net_endpoint_coverage", []):
        endpoints = row.get("endpoint_refdes")
        if (
            not isinstance(row.get("net_name"), str)
            or not isinstance(endpoints, list)
            or not endpoints
            or len(set(endpoints)) != len(endpoints)
            or not set(endpoints) <= set(components)
            or row.get("endpoint_count") != len(endpoints)
        ):
            raise ValueError("candidate coverage net endpoints are invalid")
        net_guides = row.get("guides")
        if (
            not isinstance(net_guides, list)
            or [guide.get("guide_index") for guide in net_guides]
            != list(range(guide_count))
        ):
            raise ValueError("candidate coverage net guide rows are invalid")
        for guide_index, guide in enumerate(net_guides):
            endpoint_rows = [
                components[refdes]["guide_coverage"][guide_index]
                for refdes in endpoints
            ]
            if guide.get("exact_target_endpoint_count") != sum(
                endpoint["exact_target_site_present"]
                for endpoint in endpoint_rows
            ):
                raise ValueError("candidate coverage net exact totals changed")
            if target_domain_enabled and (
                guide.get("continuous_keepin_target_endpoint_count")
                != sum(
                    endpoint["target_contained_in_keepin"]
                    for endpoint in endpoint_rows
                )
                or guide.get("exact_keepin_target_endpoint_count")
                != sum(
                    endpoint["exact_keepin_target_site_present"]
                    for endpoint in endpoint_rows
                )
                or guide.get("exact_obstacle_free_target_endpoint_count")
                != sum(
                    endpoint["exact_obstacle_free_target_site_present"]
                    for endpoint in endpoint_rows
                )
                or guide.get("fixed_obstacle_target_endpoint_count")
                != sum(
                    endpoint["target_fixed_obstacle_overlap_count"] > 0
                    for endpoint in endpoint_rows
                )
            ):
                raise ValueError(
                    "candidate target domain net totals changed"
                )


def export_candidate_coverage(
    result_path: Path,
    output_path: Path,
    repository_root: Path = ROOT,
):
    result_path = Path(result_path).resolve()
    output_path = Path(output_path).resolve()
    repository_root = Path(repository_root).resolve()
    result = json.loads(result_path.read_text())
    if not result.get("candidate_domain_overlap_model_exact"):
        raise ValueError("candidate coverage result used relaxed collisions")
    audit = copy.deepcopy(result.get("candidate_coverage_audit"))
    _validate_audit(audit)

    guide_dependencies = [
        _portable_dependency(
            result_path, repository_root, value, f"guide {index}"
        )
        for index, value in enumerate(result.get("guide_jsons", []))
    ]
    if len(guide_dependencies) != audit["guide_count"]:
        raise ValueError("candidate coverage result guide counts do not align")
    for summary, dependency in zip(audit["guides"], guide_dependencies):
        summary["guide_json"] = dependency["path"]

    reference = audit.get("reference_comparison", {})
    if reference.get("configured"):
        dependency = _portable_dependency(
            result_path,
            repository_root,
            reference.get("reference_json"),
            "reference",
        )
        if dependency["sha256"] != reference.get("reference_sha256"):
            raise ValueError("candidate coverage reference hash changed")
        reference["reference_json"] = dependency["path"]

    source = _portable_dependency(
        result_path, repository_root, result.get("source_json"), "source"
    )
    assignment = _portable_dependency(
        result_path,
        repository_root,
        result.get("assignment_json"),
        "assignment",
    )
    hint = _portable_dependency(
        result_path, repository_root, result.get("hint_json"), "hint"
    )
    checkpoint = {
        "schema": CHECKPOINT_SCHEMA,
        "source_result_sha256": _sha256_file(result_path),
        "candidate_coverage_audit_sha256": _sha256_json(audit),
        "contract": {
            "source": source,
            "assignment": assignment,
            "guides": guide_dependencies,
            "hint": hint,
            "grid_mm": result.get("grid_mm"),
            "packing_side": result.get("packing_side"),
            "manual_baseline_endpoints": result.get(
                "manual_baseline_endpoints"
            ),
            "candidate_limit": result.get("candidate_limit"),
            "expanded_candidate_limit": result.get(
                "expanded_candidate_limit"
            ),
            "expanded_refdes": result.get("expanded_refdes"),
            "candidate_guide_weights": result.get(
                "candidate_guide_weights"
            ),
            "fix_guide": result.get("fix_guide"),
            "movable_refdes": result.get("movable_refdes"),
            "integer_scale": result.get("integer_scale"),
            "interval_inset": result.get("interval_inset"),
            "nonrect_mode": result.get("nonrect_mode"),
            "candidate_count": result.get("candidate_count"),
            "candidate_counts": result.get("candidate_counts"),
        },
        "candidate_coverage_audit": audit,
    }
    if output_path.exists():
        raise FileExistsError(
            f"candidate coverage output already exists: {output_path}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(checkpoint, stream, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        temporary.chmod(0o644)
        temporary.replace(output_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return checkpoint


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checkpoint = export_candidate_coverage(args.result, args.output)
    print(
        json.dumps(
            {
                "schema": checkpoint["schema"],
                "source_result_sha256": checkpoint[
                    "source_result_sha256"
                ],
                "candidate_coverage_audit_sha256": checkpoint[
                    "candidate_coverage_audit_sha256"
                ],
                "output": str(args.output.resolve()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
