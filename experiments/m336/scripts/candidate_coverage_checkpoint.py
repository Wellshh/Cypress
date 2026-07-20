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
            component_attributed += count
            attributed_counts[guide_index] += count
        if component_attributed != len(indices):
            raise ValueError(
                f"candidate coverage attribution does not cover {refdes}"
            )
        candidate_count += len(indices)
    if audit.get("candidate_count") != candidate_count:
        raise ValueError("candidate coverage total count is invalid")
    if [row.get("attributed_candidate_count") for row in guides] != attributed_counts:
        raise ValueError("candidate coverage guide attribution is inconsistent")

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
